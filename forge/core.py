"""
core.py — briques bas niveau du "Zone Forge" (pixel-art style PMD/DS).

Tout est généré procéduralement : bruit -> ombrage -> quantification sur rampe
-> tramage ordonné (Bayer) -> contours. Aucun pixel n'est copié d'un jeu.

Contraintes techniques respectées :
  * grille de 24x24 px (tuile PMD Explorers)
  * couleurs ramenées à l'espace DS 5 bits/canal (v = (v>>3)*8+7)
"""
import numpy as np

# --------------------------------------------------------------------------- #
#  Aléatoire / bruit
# --------------------------------------------------------------------------- #

def rng(seed):
    return np.random.default_rng(seed)


def _smoothstep(t):
    return t * t * (3.0 - 2.0 * t)


def value_noise(h, w, cells, seed):
    """Bruit de valeur lissé, résolution `cells` (en cellules sur la largeur)."""
    r = rng(seed)
    ch = max(2, int(round(cells * h / max(w, 1))) + 1)
    cw = max(2, int(cells) + 1)
    grid = r.random((ch + 1, cw + 1))

    ys = np.linspace(0, ch, h, endpoint=False)
    xs = np.linspace(0, cw, w, endpoint=False)
    y0 = np.floor(ys).astype(int); x0 = np.floor(xs).astype(int)
    fy = _smoothstep(ys - y0)[:, None]
    fx = _smoothstep(xs - x0)[None, :]

    g00 = grid[np.ix_(y0, x0)]; g01 = grid[np.ix_(y0, x0 + 1)]
    g10 = grid[np.ix_(y0 + 1, x0)]; g11 = grid[np.ix_(y0 + 1, x0 + 1)]
    top = g00 * (1 - fx) + g01 * fx
    bot = g10 * (1 - fx) + g11 * fx
    return top * (1 - fy) + bot * fy


def fbm(h, w, cells=4, octaves=5, gain=0.5, lacunarity=2.0, seed=0):
    """Bruit fractal normalisé 0..1."""
    out = np.zeros((h, w)); amp = 1.0; tot = 0.0; c = cells
    for o in range(octaves):
        out += amp * value_noise(h, w, c, seed * 977 + o * 131 + 7)
        tot += amp; amp *= gain; c *= lacunarity
    out /= tot
    out -= out.min()
    m = out.max()
    return out / m if m > 0 else out


def ridged(h, w, cells=4, octaves=5, seed=0):
    n = fbm(h, w, cells, octaves, seed=seed)
    n = 1.0 - np.abs(n * 2 - 1)
    return (n - n.min()) / max(n.ptp(), 1e-6)


def warp(field_fn, h, w, amount=8.0, cells=3, seed=0):
    """Domain warping : décale les coordonnées avec du bruit -> formes organiques."""
    dx = (fbm(h, w, cells, 3, seed=seed + 11) - 0.5) * 2 * amount
    dy = (fbm(h, w, cells, 3, seed=seed + 23) - 0.5) * 2 * amount
    yy, xx = np.mgrid[0:h, 0:w]
    sy = np.clip((yy + dy).astype(int), 0, h - 1)
    sx = np.clip((xx + dx).astype(int), 0, w - 1)
    base = field_fn(h, w)
    return base[sy, sx]


# --------------------------------------------------------------------------- #
#  Couleur : rampes, DS 5 bits, tramage
# --------------------------------------------------------------------------- #

def hex2rgb(s):
    s = s.lstrip('#')
    return np.array([int(s[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float64)


def ds_quant(img_u8):
    """Ramène dans l'espace couleur DS (5 bits par canal)."""
    a = img_u8.astype(np.uint8)
    return ((a >> 3) * 8 + 7).astype(np.uint8)


BAYER8 = np.array([
    [0, 32, 8, 40, 2, 34, 10, 42], [48, 16, 56, 24, 50, 18, 58, 26],
    [12, 44, 4, 36, 14, 46, 6, 38], [60, 28, 52, 20, 62, 30, 54, 22],
    [3, 35, 11, 43, 1, 33, 9, 41], [51, 19, 59, 27, 49, 17, 57, 25],
    [15, 47, 7, 39, 13, 45, 5, 37], [63, 31, 55, 23, 61, 29, 53, 21],
], dtype=np.float64) / 64.0


def bayer(h, w, offset=(0, 0)):
    oy, ox = offset
    return np.tile(BAYER8, (h // 8 + 2, w // 8 + 2))[oy:oy + h, ox:ox + w]


def ramp_shade(t, ramp, dither=0.9, seed=0, jitter=0.0):
    """
    t : champ 0..1 (luminosité). ramp : liste de couleurs hex, sombre -> clair.
    Renvoie un tableau HxWx3 uint8 quantifié DS, avec tramage ordonné entre
    les paliers (le "grain" caractéristique des fonds DS).
    """
    h, w = t.shape
    cols = np.stack([hex2rgb(c) for c in ramp])          # (n,3)
    n = len(ramp)
    tt = np.clip(t, 0, 1) * (n - 1)
    if jitter:
        tt = tt + (rng(seed).random((h, w)) - 0.5) * jitter
    d = (bayer(h, w, (seed % 8, (seed * 3) % 8)) - 0.5) * dither
    idx = np.clip(np.round(tt + d), 0, n - 1).astype(int)
    return ds_quant(cols[idx])


# --------------------------------------------------------------------------- #
#  Masques / morphologie (sans scipy)
# --------------------------------------------------------------------------- #

def shift(a, dy, dx, fill=0):
    out = np.full_like(a, fill)
    h, w = a.shape
    ys, ye = max(0, dy), min(h, h + dy)
    xs, xe = max(0, dx), min(w, w + dx)
    out[ys:ye, xs:xe] = a[ys - dy:ye - dy, xs - dx:xe - dx]
    return out


def dilate(mask, r=1):
    out = mask.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dy * dy + dx * dx <= r * r + 1:
                out |= shift(mask, dy, dx, False)
    return out


def erode(mask, r=1):
    return ~dilate(~mask, r)


def edge(mask, r=1, inner=True):
    return (mask & ~erode(mask, r)) if inner else (dilate(mask, r) & ~mask)


def blur(a, r=2, it=1):
    out = a.astype(np.float64)
    for _ in range(it):
        acc = np.zeros_like(out); n = 0
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                acc += shift(out, dy, dx, 0.0); n += 1
        out = acc / n
    return out


def blob_mask(h, w, seed, cx=0.5, cy=0.5, rx=0.34, ry=0.34, wobble=0.42, cells=3):
    """Tache organique (ellipse + bruit) -> clairières, mares, plaques de sable."""
    yy, xx = np.mgrid[0:h, 0:w]
    nx = (xx - cx * w) / (rx * w)
    ny = (yy - cy * h) / (ry * h)
    d = np.sqrt(nx ** 2 + ny ** 2)
    n = fbm(h, w, cells, 4, seed=seed)
    return d + (n - 0.5) * 2 * wobble < 1.0


def frame_falloff(h, w, pad=0.18):
    """1 au centre, 0 sur les bords — sert au cadrage sombre des zones PMD."""
    yy, xx = np.mgrid[0:h, 0:w]
    fx = np.clip(np.minimum(xx, w - 1 - xx) / (pad * w), 0, 1)
    fy = np.clip(np.minimum(yy, h - 1 - yy) / (pad * h), 0, 1)
    return _smoothstep(np.minimum(fx, fy))


# --------------------------------------------------------------------------- #
#  Composition RGBA
# --------------------------------------------------------------------------- #

def new_rgba(h, w):
    return np.zeros((h, w, 4), dtype=np.uint8)


def paste(dst, src, y, x):
    """Alpha-blend `src` (HxWx4) dans `dst` (HxWx4) en (y,x). Modifie dst."""
    H, W = dst.shape[:2]; sh, sw = src.shape[:2]
    y0, x0 = max(0, y), max(0, x)
    y1, x1 = min(H, y + sh), min(W, x + sw)
    if y0 >= y1 or x0 >= x1:
        return dst
    s = src[y0 - y:y1 - y, x0 - x:x1 - x].astype(np.float64)
    d = dst[y0:y1, x0:x1].astype(np.float64)
    sa = s[..., 3:4] / 255.0; da = d[..., 3:4] / 255.0
    oa = sa + da * (1 - sa)
    rgb = np.where(oa > 0, (s[..., :3] * sa + d[..., :3] * da * (1 - sa)) / np.maximum(oa, 1e-6), 0)
    dst[y0:y1, x0:x1, :3] = ds_quant(np.clip(rgb, 0, 255))
    dst[y0:y1, x0:x1, 3:4] = np.clip(oa * 255, 0, 255).astype(np.uint8)
    return dst


def mul_shadow(dst, mask, strength=0.35):
    """Assombrit dst là où mask est vrai (ombres portées, cadrage)."""
    m = np.clip(mask, 0, 1)[..., None]
    dst[..., :3] = ds_quant(dst[..., :3].astype(np.float64) * (1 - strength * m))
    return dst


def tint(dst, color, amount):
    c = hex2rgb(color)
    a = np.clip(amount, 0, 1)
    if np.ndim(a) == 2:
        a = a[..., None]
    dst[..., :3] = ds_quant(dst[..., :3] * (1 - a) + c * a)
    return dst
