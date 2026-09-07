"""
props.py — sprites de décor dessinés procéduralement (RGBA, contour 1 px).

Chaque prop : masque -> ombrage top-lit -> quantification sur rampe -> contour
sombre -> ombre portée elliptique. C'est la grammaire visuelle des fonds PMD.
"""
import numpy as np
from . import core as C


# --------------------------------------------------------------------------- #
#  Rasterisation
# --------------------------------------------------------------------------- #

def _grid(h, w):
    return np.mgrid[0:h, 0:w]


def disc(h, w, cy, cx, ry, rx):
    yy, xx = _grid(h, w)
    return ((yy - cy) / max(ry, .5)) ** 2 + ((xx - cx) / max(rx, .5)) ** 2 <= 1.0


def lens(h, w, cy, cx, ang, length, width):
    """Feuille / fronde : lentille orientée."""
    yy, xx = _grid(h, w)
    ca, sa = np.cos(ang), np.sin(ang)
    u = (xx - cx) * ca + (yy - cy) * sa
    v = -(xx - cx) * sa + (yy - cy) * ca
    t = np.clip(u / max(length, .5), -1, 1)
    halfw = width * np.sqrt(np.clip(1 - t ** 2, 0, 1)) * (0.45 + 0.55 * (1 - np.abs(t)))
    return (np.abs(u) <= length) & (np.abs(v) <= np.maximum(halfw, 0.4))


def poly(h, w, pts):
    yy, xx = _grid(h, w)
    inside = np.zeros((h, w), bool)
    n = len(pts)
    for i in range(n):
        y0, x0 = pts[i]; y1, x1 = pts[(i + 1) % n]
        cond = ((y0 > yy) != (y1 > yy))
        with np.errstate(divide='ignore', invalid='ignore'):
            xint = (x1 - x0) * (yy - y0) / np.where(y1 - y0 == 0, 1e-9, y1 - y0) + x0
        inside ^= cond & (xx < xint)
    return inside


def blob(h, w, cy, cx, r, seed, wob=0.34, lobes=7):
    yy, xx = _grid(h, w)
    ang = np.arctan2(yy - cy, xx - cx)
    d = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    rr = C.rng(seed)
    m = np.ones_like(ang) * r
    for k in range(2, lobes):
        m = m * (1 + wob / k * np.sin(k * ang + rr.random() * 6.283))
    return d <= m


# --------------------------------------------------------------------------- #
#  Finition commune
# --------------------------------------------------------------------------- #

def finish(mask, t, ramp, outline="#050b09", out_alpha=255, rim=None, seed=0):
    """mask (bool) + t (0..1 luminosité) -> RGBA avec contour sombre 1 px."""
    h, w = mask.shape
    img = C.new_rgba(h, w)
    rgb = C.ramp_shade(np.clip(t, 0, 1), ramp, dither=0.75, seed=seed)
    img[..., :3] = rgb
    img[..., 3] = np.where(mask, 255, 0)

    ol = C.dilate(mask, 1) & ~mask
    img[ol, :3] = C.ds_quant(C.hex2rgb(outline))
    img[ol, 3] = out_alpha

    if rim:                                     # liseré lumineux en haut
        top = mask & ~C.shift(mask, 1, 0, False)
        img[top, :3] = C.ds_quant(C.hex2rgb(rim))
    return img


def drop_shadow(h, w, cy, cx, ry, rx, alpha=110):
    img = C.new_rgba(h, w)
    m = disc(h, w, cy, cx, ry, rx)
    img[m, :3] = C.ds_quant(C.hex2rgb("#0a1310"))
    img[m, 3] = alpha
    return img


def _toplit(mask, power=1.0):
    """Luminosité : clair en haut / au centre, sombre en bas et sur les bords."""
    h, w = mask.shape
    yy, _ = _grid(h, w)
    inner = mask.astype(float)
    for _ in range(3):
        inner = np.minimum(inner, C.blur(mask.astype(float), 1))
    depth = C.blur(mask.astype(float), 2, 2)
    vert = 1.0 - (yy / max(h - 1, 1))
    return np.clip((vert * 0.62 + depth * 0.55) * power, 0, 1)


# --------------------------------------------------------------------------- #
#  Catalogue
# --------------------------------------------------------------------------- #

def fern(size, ramp, seed=0, fronds=9):
    """Fougère en éventail — la signature des jungles PMD."""
    h = w = size
    r = C.rng(seed)
    m = np.zeros((h, w), bool)
    cy, cx = h - 3, w / 2
    for i in range(fronds):
        a = np.pi * (0.06 + 0.88 * i / (fronds - 1)) + np.pi
        L = size * (0.34 + 0.14 * r.random()) * (0.72 + 0.4 * np.sin(np.pi * i / (fronds - 1)))
        m |= lens(h, w, cy + np.sin(a) * L, cx + np.cos(a) * L, a, L, size * 0.075)
    m |= disc(h, w, cy, cx, size * 0.07, size * 0.10)
    t = _toplit(m, 1.05)
    t += (C.fbm(h, w, 5, 2, seed=seed) - 0.5) * 0.25
    img = finish(m, t, ramp, seed=seed)
    return img


def bush(size, ramp, seed=0, lobes=5):
    h = w = size
    r = C.rng(seed)
    m = np.zeros((h, w), bool)
    for i in range(lobes):
        a = np.pi * (0.15 + 0.7 * i / max(lobes - 1, 1))
        cx = w / 2 + np.cos(a) * size * 0.26
        cy = h * 0.62 - np.sin(a) * size * 0.20
        m |= blob(h, w, cy, cx, size * (0.20 + 0.09 * r.random()), seed + i)
    m &= disc(h, w, h * 0.60, w / 2, h * 0.46, w * 0.50)
    t = _toplit(m, 1.0)
    b, ids = np.zeros((h, w)), C.fbm(h, w, 7, 3, seed=seed + 4)
    t = np.clip(t * 0.8 + ids * 0.34, 0, 1)
    return finish(m, t, ramp, seed=seed)


def rock(size, ramp, seed=0, flat=0.78):
    h = w = size
    r = C.rng(seed)
    n = 7
    pts = []
    for i in range(n):
        a = 2 * np.pi * i / n + r.random() * 0.25
        rad = size * (0.30 + 0.14 * r.random())
        pts.append((h * 0.55 - np.sin(a) * rad * flat, w / 2 + np.cos(a) * rad))
    m = poly(h, w, pts)
    m = C.dilate(m, 1) & C.dilate(m, 1)
    t = _toplit(m, 1.1)
    t = np.clip(t + (C.fbm(h, w, 4, 3, seed=seed + 2) - 0.5) * 0.30, 0, 1)
    img = finish(m, t, ramp, seed=seed)
    sh = drop_shadow(h, w, h * 0.80, w / 2, size * 0.09, size * 0.30, 95)
    C.paste(sh, img, 0, 0)
    return sh


def crystal(size, ramp, seed=0, shards=3):
    h = w = size
    r = C.rng(seed)
    out = C.new_rgba(h, w)
    for i in range(shards):
        bx = w / 2 + (r.random() - 0.5) * size * 0.42
        by = h * 0.88
        hgt = size * (0.42 + 0.44 * r.random())
        wid = size * (0.09 + 0.07 * r.random())
        tipx = bx + (r.random() - 0.5) * size * 0.16
        pts = [(by, bx - wid), (by - hgt * 0.55, bx - wid * 0.9),
               (by - hgt, tipx), (by - hgt * 0.55, bx + wid * 0.9), (by, bx + wid)]
        m = poly(h, w, pts)
        yy, xx = _grid(h, w)
        t = np.clip(0.30 + (1 - yy / h) * 0.55 + ((xx - bx) < 0) * 0.22, 0, 1)
        t = np.where(np.abs(xx - tipx) < wid * 0.35, np.clip(t + 0.3, 0, 1), t)
        C.paste(out, finish(m, t, ramp, outline="#0a1622", rim="#dff6ff", seed=seed + i), 0, 0)
    return out


def tree_canopy(size, ramp, seed=0):
    """Houppier vu de dessus/trois-quarts pour les bordures de carte."""
    h = w = size
    r = C.rng(seed)
    m = np.zeros((h, w), bool)
    for i in range(9):
        a = 2 * np.pi * r.random()
        rad = size * (0.16 + 0.12 * r.random())
        cy = h * 0.48 + np.sin(a) * size * 0.22
        cx = w * 0.50 + np.cos(a) * size * 0.26
        m |= blob(h, w, cy, cx, rad, seed + i, wob=0.30)
    t = _toplit(m, 1.0) * 0.72 + C.fbm(h, w, 6, 4, seed=seed + 3) * 0.44
    return finish(m, t, ramp, seed=seed)


def palm_leaf(size, ramp, seed=0):
    h = w = size
    r = C.rng(seed)
    m = np.zeros((h, w), bool)
    cy, cx = h * 0.92, w * 0.5
    for i in range(7):
        a = np.pi + np.pi * (0.1 + 0.8 * i / 6)
        L = size * (0.40 + 0.10 * r.random())
        ey, ex = cy + np.sin(a) * L, cx + np.cos(a) * L
        m |= lens(h, w, (cy + ey) / 2, (cx + ex) / 2, a, L * 0.55, size * 0.05)
        for k in range(5):                             # folioles
            f = 0.25 + 0.72 * k / 4
            py, px = cy + np.sin(a) * L * f, cx + np.cos(a) * L * f
            m |= lens(h, w, py, px, a + 1.1, size * 0.10, size * 0.035)
            m |= lens(h, w, py, px, a - 1.1, size * 0.10, size * 0.035)
    t = _toplit(m, 1.05)
    return finish(m, t, ramp, seed=seed)


def reed(size, ramp, seed=0, n=6):
    h = w = size
    r = C.rng(seed)
    m = np.zeros((h, w), bool)
    for i in range(n):
        x0 = w * (0.2 + 0.6 * r.random())
        L = size * (0.45 + 0.4 * r.random())
        a = -np.pi / 2 + (r.random() - 0.5) * 0.7
        m |= lens(h, w, h - L / 2, x0 + np.cos(a) * L * 0.3, a, L / 2, size * 0.035)
    t = _toplit(m, 1.15)
    return finish(m, t, ramp, seed=seed)


def flower_tuft(size, ramp, petal="#ffe9a8", seed=0):
    h = w = size
    r = C.rng(seed)
    m = np.zeros((h, w), bool)
    for i in range(5):
        m |= lens(h, w, h * 0.75, w * (0.25 + 0.5 * r.random()), -np.pi / 2 + (r.random() - .5),
                  size * 0.22, size * 0.045)
    img = finish(m, _toplit(m, 1.1), ramp, seed=seed)
    for i in range(3):
        cy, cx = h * (0.32 + 0.2 * r.random()), w * (0.25 + 0.5 * r.random())
        d = disc(h, w, cy, cx, size * 0.07, size * 0.07)
        img[d, :3] = C.ds_quant(C.hex2rgb(petal)); img[d, 3] = 255
    return img


def log(size, ramp, seed=0):
    h = w = size
    m = disc(h, w, h * 0.62, w * 0.5, size * 0.16, size * 0.42)
    yy, xx = _grid(h, w)
    t = np.clip(0.75 - (yy - h * 0.46) / (size * 0.6), 0, 1)
    t += (C.fbm(h, w, 12, 2, seed=seed) - 0.5) * 0.22
    img = finish(m, t, ramp, seed=seed)
    ring = disc(h, w, h * 0.62, w * 0.5 - size * 0.38, size * 0.15, size * 0.06)
    img[ring & m, :3] = C.ds_quant(C.hex2rgb("#3a2a1c"))
    return img


def stalagmite(size, ramp, seed=0, flip=False):
    h = w = size
    r = C.rng(seed)
    pts = [(h * 0.97, w * 0.5 - size * 0.20), (h * 0.5, w * 0.5 - size * 0.11),
           (h * 0.06, w * 0.5 + (r.random() - .5) * size * 0.14),
           (h * 0.5, w * 0.5 + size * 0.11), (h * 0.97, w * 0.5 + size * 0.20)]
    if flip:
        pts = [(h - y, x) for y, x in pts]
    m = poly(h, w, pts)
    yy, xx = _grid(h, w)
    t = np.clip(0.30 + (1 - np.abs(xx - w * 0.42) / (size * 0.4)) * 0.55, 0, 1)
    return finish(m, t, ramp, seed=seed)


def ruin_block(size, ramp, seed=0):
    h = w = size
    top = h * 0.30
    m = poly(h, w, [(top, w * 0.18), (top, w * 0.82), (h * 0.86, w * 0.86), (h * 0.86, w * 0.14)])
    yy, xx = _grid(h, w)
    t = np.clip(0.72 - (yy - top) / (h * 0.9) + (C.fbm(h, w, 6, 3, seed=seed) - .5) * .3, 0, 1)
    face = m & (yy > top + 2)
    t = np.where(face, t * 0.9, t)
    img = finish(m, t, ramp, seed=seed)
    sh = drop_shadow(h, w, h * 0.88, w * 0.5, size * 0.07, size * 0.36, 100)
    C.paste(sh, img, 0, 0)
    return sh


def cactus(size, ramp, seed=0):
    h = w = size
    m = disc(h, w, h * 0.62, w * 0.5, size * 0.34, size * 0.11)
    m |= disc(h, w, h * 0.55, w * 0.30, size * 0.16, size * 0.075)
    m |= disc(h, w, h * 0.48, w * 0.70, size * 0.20, size * 0.075)
    yy, xx = _grid(h, w)
    t = np.clip(0.36 + (1 - np.abs(xx - w * 0.42) / (size * 0.35)) * 0.5, 0, 1)
    t = np.where((xx.astype(int) % 4) == 0, np.clip(t - 0.14, 0, 1), t)
    return finish(m, t, ramp, seed=seed)


CATALOG = {
    "fern": fern, "bush": bush, "rock": rock, "crystal": crystal,
    "tree_canopy": tree_canopy, "palm_leaf": palm_leaf, "reed": reed,
    "flower_tuft": flower_tuft, "log": log, "stalagmite": stalagmite,
    "ruin_block": ruin_block, "cactus": cactus,
}
