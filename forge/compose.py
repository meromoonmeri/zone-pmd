"""
compose.py — composition par calques.

Au lieu d'animer une image aplatie (et de devoir DEVINER ce qui est de l'eau ou
du feuillage), on assemble la zone à partir d'éléments produits séparément :

    terrain (fond)  <-  PNG plein cadre
    eau             <-  procédurale, masque EXACT donné par le trou magenta
    props / végétation <- objets RGBA détourés, placés un par un
    canopée (cadre) <-  objets RGBA détourés, placés sur la bande de bord
    lumière         <-  calque procédural qui défile

Chaque calque connaît sa propre animation (cisaillement pour les plantes,
palette cycling pour l'eau, dérive pour la lumière) : les masques sont exacts,
plus aucune classification à l'aveugle.
"""
import numpy as np
from PIL import Image
import os, json, glob, colorsys

from . import core as C
from .animate import fbm, build_lut, palette_of, snap

W, H = 21 * 24, 19 * 24
N = 12
MS = 110
MAGENTA = None   # détecté dynamiquement


# --------------------------------------------------------------------------- #
#  Chargement / masques
# --------------------------------------------------------------------------- #

def load_terrain(path, w=W, h=H):
    im = Image.open(path).convert("RGB")
    rs, rd = im.width / im.height, w / h
    if rs > rd:
        nw = int(im.height * rd); im = im.crop(((im.width - nw) // 2, 0, (im.width + nw) // 2, im.height))
    else:
        nh = int(im.width / rd); im = im.crop((0, (im.height - nh) // 2, im.width, (im.height + nh) // 2))
    a = np.array(im.resize((w, h), Image.LANCZOS)).astype(np.int32)
    key = (a[..., 0] > 150) & (a[..., 2] > 150) & (a[..., 1] < 130) & \
          ((a[..., 0] - a[..., 1]) > 70) & ((a[..., 2] - a[..., 1]) > 70)
    rgb = ((a.astype(np.uint8) >> 3) * 8 + 7)
    return rgb, key


def hsv_mask(rgb, hlo, hhi, smin=0.0, vmin=0.0, vmax=1.0):
    a = rgb.astype(np.float32) / 255.0
    mx = a.max(-1); mn = a.min(-1); d = mx - mn
    v = mx; s = np.where(mx > 0, d / np.maximum(mx, 1e-6), 0)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    h = np.zeros_like(v)
    nz = d > 1e-6
    h = np.where(nz & (mx == r), ((g - b) / np.maximum(d, 1e-6)) % 6, h)
    h = np.where(nz & (mx == g), (b - r) / np.maximum(d, 1e-6) + 2, h)
    h = np.where(nz & (mx == b), (r - g) / np.maximum(d, 1e-6) + 4, h)
    h = (h / 6.0) % 1.0
    return (h >= hlo) & (h <= hhi) & (s >= smin) & (v >= vmin) & (v <= vmax)


def shore_depth(mask, steps=18):
    """Distance lissée au rivage : gradient propre, sans marches d'érosion."""
    d = C.blur(mask.astype(np.float32), 5, 4)
    d = np.clip((d - 0.30) / 0.62, 0, 1)
    return d * mask


# --------------------------------------------------------------------------- #
#  Calque EAU (procédural, masque exact)
# --------------------------------------------------------------------------- #

def water_layer(mask, ramp, n=N, seed=0, foam=True, foam_color=None, calm=1.0):
    """Renvoie n RGBA : houle en bandes, reflet central, écume au rivage."""
    h, w = mask.shape
    yy, xx = np.mgrid[0:h, 0:w]
    dep = shore_depth(mask)
    warp = fbm(h, w, 4, 3, seed + 1)
    fine = fbm(h, w, 11, 3, seed + 2)
    # tache de reflet, centrée sur le barycentre de la nappe
    ys, xs = np.where(mask)
    cy, cx = (ys.mean(), xs.mean()) if len(ys) else (h / 2, w / 2)
    glint = np.exp(-(((yy - cy) / (h * 0.13)) ** 2 + ((xx - cx) / (w * 0.22)) ** 2))
    rim = C.edge(mask, 2)
    twk = np.random.default_rng(seed + 7).random((h, w))
    tph = np.random.default_rng(seed + 8).random((h, w)) * 2 * np.pi

    out = []
    for t in range(n):
        ph = 2 * np.pi * t / n
        f = (0.30
             + 0.26 * dep                                          # profondeur
             + calm * 0.085 * np.sin(yy * 0.23 + warp * 1.6 - ph)  # houle lente
             + calm * 0.045 * np.sin(xx * 0.070 + ph * 2.0)        # clapot
             + 0.030 * fine
             + 0.22 * glint * (0.80 + 0.20 * np.sin(ph)))
        # stries de reflet : fines lignes claires qui glissent (signature DS)
        # rupture des lignes : le terme en x empeche les rayures pleine largeur
        streak = np.sin(yy * 0.62 + warp * 3.8
                        + 1.10 * np.sin(xx * 0.021 + 0.7)
                        + 0.55 * np.sin(xx * 0.053 - 1.9)
                        - ph * 1.0)
        f = f + 0.075 * (streak > 0.88) + 0.042 * (streak > 0.66)
        rgb = C.ramp_shade(np.clip(f, 0, 1), ramp, dither=0.42, seed=seed)
        img = np.zeros((h, w, 4), np.uint8)
        img[..., :3] = rgb
        img[..., 3] = np.where(mask, 255, 0)
        # écume : liseré clair qui ondule le long du rivage
        if foam:
            band = rim & (np.sin(xx * 0.30 + yy * 0.22 - ph * 2) > 0.15)
            img[band, :3] = C.ds_quant(C.hex2rgb(foam_color or ramp[-1]))
        # sparkles : points isolés qui s'allument à tour de rôle
        sp = mask & (dep > 0.25) & (twk > 0.9972) & (np.sin(ph * 2 + tph) > 0.5)
        img[sp, :3] = C.ds_quant(C.hex2rgb(foam_color or ramp[-1]))
        out.append(img)
    return out


# --------------------------------------------------------------------------- #
#  Props : chargement, cisaillement (sway), placement
# --------------------------------------------------------------------------- #

def load_objects(d):
    objs = []
    for f in sorted(glob.glob(os.path.join(d, "*.png"))):
        a = np.array(Image.open(f).convert("RGBA"))
        if a[..., 3].sum() == 0:
            continue
        objs.append(dict(name=os.path.basename(f), img=a,
                         h=a.shape[0], w=a.shape[1]))
    return objs


def shear_sway(img, amp, phase, t, n):
    """Plie le sprite : la base reste fixe, le sommet se décale de ±amp px."""
    if amp <= 0:
        return img
    h, w = img.shape[:2]
    out = np.zeros_like(img)
    ph = 2 * np.pi * t / n + phase
    for y in range(h):
        k = (1.0 - y / max(h - 1, 1)) ** 1.6
        dx = int(round(amp * k * np.sin(ph)))
        if dx == 0:
            out[y] = img[y]
        elif dx > 0:
            out[y, dx:] = img[y, :w - dx]
        else:
            out[y, :w + dx] = img[y, -dx:]
    return out


def alpha_paste(dst, src, y, x):
    Hh, Ww = dst.shape[:2]; sh, sw = src.shape[:2]
    y0, x0 = max(0, y), max(0, x)
    y1, x1 = min(Hh, y + sh), min(Ww, x + sw)
    if y0 >= y1 or x0 >= x1:
        return
    s = src[y0 - y:y1 - y, x0 - x:x1 - x]
    m = s[..., 3] > 127
    dst[y0:y1, x0:x1][m] = s[m]


def contact_shadow(dst, src, y, x, alpha=0.42):
    """Ombre de contact aplatie sous l'objet — ancre le prop au sol."""
    sh, sw = src.shape[:2]
    m = src[..., 3] > 127
    cols = np.flatnonzero(m.any(0))
    if len(cols) == 0:
        return
    base = np.zeros((max(6, sh // 5), sw), bool)
    bh = base.shape[0]
    yy, xx = np.mgrid[0:bh, 0:sw]
    ccx = (cols.min() + cols.max()) / 2
    rx = max(3.0, (cols.max() - cols.min()) * 0.46)
    base = ((yy - bh / 2) / (bh / 2.0)) ** 2 + ((xx - ccx) / rx) ** 2 <= 1.0
    oy = y + sh - bh // 2 - 1
    Hh, Ww = dst.shape[:2]
    y0, x0 = max(0, oy), max(0, x)
    y1, x1 = min(Hh, oy + bh), min(Ww, x + sw)
    if y0 >= y1 or x0 >= x1:
        return
    b = base[y0 - oy:y1 - oy, x0 - x:x1 - x]
    reg = dst[y0:y1, x0:x1]
    reg[..., :3] = np.where(b[..., None],
                            C.ds_quant(reg[..., :3].astype(np.float32) * (1 - alpha)),
                            reg[..., :3])


def scatter(mask, objs, count, rng, band=None, avoid=None, margin=2):
    """Tire des positions valides : la BASE du sprite doit toucher le masque."""
    h, w = mask.shape
    out = []
    for _ in range(count):
        o = objs[int(rng.integers(0, len(objs)))]
        ow, oh = o["w"], o["h"]
        for _try in range(120):
            x = int(rng.integers(-ow // 4, w - ow * 3 // 4))
            y = int(rng.integers(-oh // 4, h - oh * 3 // 4))
            by, bx = y + oh - margin, x + ow // 2
            if not (0 <= by < h and 0 <= bx < w):
                continue
            if not mask[by, bx]:
                continue
            if band is not None and not band[by, bx]:
                continue
            if avoid is not None and avoid[by, bx]:
                continue
            out.append((y, x, o))
            break
    return out


# --------------------------------------------------------------------------- #
#  Calque LUMIÈRE
# --------------------------------------------------------------------------- #

LIGHT_GRADES = {
    "jour":       dict(mul=(1.00, 1.00, 1.00), amb=(0, 0, 0), dap=0.11, vig=0.25),
    "crepuscule": dict(mul=(1.05, 0.83, 0.66), amb=(20, 4, 12), dap=0.13, vig=0.44),
    "nuit":       dict(mul=(0.44, 0.54, 0.88), amb=(4, 8, 26), dap=0.07, vig=0.52),
}


def apply_light(frame, t, n, dap_field, vig, grade="jour", seed=0):
    g = LIGHT_GRADES[grade]
    a = frame[..., :3].astype(np.float32)
    drift = np.roll(np.roll(dap_field, int(t * 1.7), 0), int(t * 2.5), 1)
    lit = drift > 0.63
    a[lit] *= (1.0 + g["dap"])
    a *= (1.0 + 0.05 * np.sin(2 * np.pi * t / n))          # respiration
    a *= np.array(g["mul"])
    a += np.array(g["amb"])
    a *= (1.0 - g["vig"] * (1.0 - vig)[..., None])
    frame[..., :3] = np.clip(a, 0, 255).astype(np.uint8)
    return frame


def enrich_terrain(rgb, masks, seed=0, amount=0.10):
    """Rajoute le grain du support (touffes d'herbe, plaques de sable) par
    modulation de luminance : le calque terrain garde sa couleur, gagne sa texture."""
    from . import materials as M
    h, w = rgb.shape[:2]
    a = rgb.astype(np.float32)
    for kind, m in masks.items():
        if m is None or not m.any():
            continue
        f = M.MATERIALS[kind](h, w, seed + (abs(hash(kind)) % 997))
        k = (1.0 + (f - 0.5) * 2.0 * amount)[..., None]
        a = np.where(m[..., None], a * k, a)
    return C.ds_quant(np.clip(a, 0, 255))
