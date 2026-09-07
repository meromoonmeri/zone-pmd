"""
animate.py — animation de fonds façon DS/GBA.

Techniques d'époque uniquement, aucun effet "moderne" :
  * palette cycling  : rotation d'une rampe de couleurs (eau, lave, cristaux)
  * pixel sway       : décalage entier de ±1..2 px sur les masques végétaux
  * scanline shimmer : échantillonnage sinusoïdal des bandes d'eau
  * dappled light    : champ de bruit qui défile, quantifié sur 1 palier
  * sparkles         : pixels de highlight allumés/éteints par un bruit mobile

Toutes les frames sont reprojetées sur la palette EXACTE du fond de base
(LUT sur le cube couleur DS 5 bits) : le nombre de couleurs ne bouge jamais.
"""
import numpy as np
from PIL import Image
import colorsys, os

N_FRAMES = 12
FRAME_MS = 110


# --------------------------------------------------------------------------- #
#  Bruit (indépendant de forge/, pour que le module soit autonome)
# --------------------------------------------------------------------------- #

def _vnoise(h, w, cells, seed):
    r = np.random.default_rng(seed)
    ch = max(2, int(round(cells * h / w)) + 1); cw = max(2, cells + 1)
    g = r.random((ch + 1, cw + 1))
    ys = np.linspace(0, ch, h, endpoint=False); xs = np.linspace(0, cw, w, endpoint=False)
    y0 = np.floor(ys).astype(int); x0 = np.floor(xs).astype(int)
    fy = (lambda t: t * t * (3 - 2 * t))(ys - y0)[:, None]
    fx = (lambda t: t * t * (3 - 2 * t))(xs - x0)[None, :]
    a = g[np.ix_(y0, x0)] * (1 - fx) + g[np.ix_(y0, x0 + 1)] * fx
    b = g[np.ix_(y0 + 1, x0)] * (1 - fx) + g[np.ix_(y0 + 1, x0 + 1)] * fx
    return a * (1 - fy) + b * fy


def fbm(h, w, cells=4, oct_=4, seed=0):
    o = np.zeros((h, w)); amp = 1.0; tot = 0.0; c = cells
    for i in range(oct_):
        o += amp * _vnoise(h, w, int(c), seed * 131 + i * 17); tot += amp
        amp *= 0.5; c *= 2
    o /= tot
    return (o - o.min()) / max(np.ptp(o), 1e-9)


# --------------------------------------------------------------------------- #
#  Palette : classification + LUT de reprojection
# --------------------------------------------------------------------------- #

def palette_of(arr):
    return np.unique(arr.reshape(-1, 3), axis=0)


def classify(pal):
    """Range chaque couleur de la palette dans une catégorie animable."""
    cls = []
    for r, g, b in pal / 255.0:
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        if 0.475 <= h <= 0.70 and s > 0.24 and v > 0.13:
            c = "water"
        elif (h < 0.085 or h > 0.955) and s > 0.50 and v > 0.42:
            c = "lava"
        elif 0.17 <= h < 0.475 and s > 0.17 and v > 0.10:
            c = "veg"
        elif v > 0.78 and (s < 0.32 or 0.72 < h < 0.95 or 0.10 < h < 0.18):
            c = "accent"          # fleurs, écume, lucioles, highlights
        else:
            c = "solid"
        cls.append(c)
    return np.array(cls)


def build_lut(pal):
    """LUT 32³ (cube DS) -> index de palette le plus proche."""
    lv = np.arange(32) * 8 + 7
    cube = np.stack(np.meshgrid(lv, lv, lv, indexing="ij"), -1).reshape(-1, 3).astype(np.int32)
    out = np.empty(cube.shape[0], np.int32)
    step = 4096
    p = pal.astype(np.int32)
    for i in range(0, cube.shape[0], step):
        d = ((cube[i:i + step, None, :] - p[None, :, :]) ** 2).sum(-1)
        out[i:i + step] = d.argmin(1)
    return out.reshape(32, 32, 32)


def snap(arr, pal, lut):
    idx = lut[arr[..., 0] >> 3, arr[..., 1] >> 3, arr[..., 2] >> 3]
    return pal[idx]


def lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def box_mean(a, r):
    f = a.astype(np.float32)
    c = np.cumsum(np.cumsum(np.pad(f, r + 1, mode="edge"), 0), 1)
    h, w = a.shape
    ys, xs = np.mgrid[0:h, 0:w]
    y0, y1 = ys, ys + 2 * r + 1
    x0, x1 = xs, xs + 2 * r + 1
    tot = c[y1, x1] - c[y0, x1] - c[y1, x0] + c[y0, x0]
    return tot / ((2 * r + 1) ** 2)


def compact(mask, r=5, thr=0.55):
    """Ne garde que les zones denses : une nappe d'eau, pas 3 pixels de feuillage."""
    if not mask.any():
        return mask
    return mask & (box_mean(mask, r) > thr)


# --------------------------------------------------------------------------- #
#  Effets
# --------------------------------------------------------------------------- #

def sample(base, sy, sx):
    h, w = base.shape[:2]
    return base[np.clip(sy, 0, h - 1), np.clip(sx, 0, w - 1)]


def animate_zone(path, out_dir, n=N_FRAMES, seed=0):
    base = np.array(Image.open(path).convert("RGB"))
    h, w = base.shape[:2]
    pal = palette_of(base)
    cls = classify(pal)
    lut = build_lut(pal)

    # index de chaque pixel dans la palette -> masques par catégorie
    pidx = lut[base[..., 0] >> 3, base[..., 1] >> 3, base[..., 2] >> 3]
    m = {k: np.isin(pidx, np.where(cls == k)[0]) for k in ("water", "lava", "veg", "accent")}
    m["water"] = compact(m["water"], 5, 0.58)
    m["lava"] = compact(m["lava"], 4, 0.45)

    yy, xx = np.mgrid[0:h, 0:w]

    # rampes cyclables, triées par luminance
    ramps = {}
    for k in ("water", "lava"):
        ids = np.where(cls == k)[0]
        if len(ids) >= 3:
            ramps[k] = ids[np.argsort([lum(pal[i]) for i in ids])]

    # champs de bruit statiques réutilisés d'une frame à l'autre
    gust = fbm(h, w, 3, 3, seed + 5)            # variation de force du vent
    dapple = fbm(h, w, 5, 4, seed + 9)          # taches de lumière
    twk = np.random.default_rng(seed + 21).random((h, w))   # bruit blanc : points isolés
    twk_ph = np.random.default_rng(seed + 22).random((h, w)) * 2 * np.pi

    frames = []
    for t in range(n):
        ph = 2 * np.pi * t / n
        cur = base.copy()

        # 1. SWAY — végétation et fleurs, décalage entier ±1/2 px ------------ #
        veg = m["veg"] | m["accent"]
        if veg.any():
            amp = 0.9 + gust * 1.5
            dx = np.round(amp * np.sin(ph + xx * 0.045 + yy * 0.018 + gust * 4)).astype(int)
            dy = np.round(0.45 * amp * np.sin(ph * 2 + xx * 0.03)).astype(int)
            swayed = sample(base, yy + dy, xx + dx)
            cur[veg] = swayed[veg]

        # 2. EAU — houle par échantillonnage + cycling de la rampe ----------- #
        if m["water"].any():
            sy = yy + np.round(1.7 * np.sin(ph + yy * 0.22 + xx * 0.03)).astype(int)
            sx = xx + np.round(1.3 * np.sin(ph * 1.5 + xx * 0.10)).astype(int)
            wav = sample(base, sy, sx)
            src_is_water = sample(m["water"][..., None].astype(np.uint8), sy, sx)[..., 0] > 0
            keep = m["water"] & src_is_water
            cur[keep] = wav[keep]
            if "water" in ramps:                      # palette cycling (1 cran / 2 frames)
                r = ramps["water"]; k = (t // 2) % len(r)
                rot = np.roll(r, k)
                remap = np.arange(len(pal)); remap[r] = rot
                widx = remap[lut[cur[..., 0] >> 3, cur[..., 1] >> 3, cur[..., 2] >> 3]]
                cyc = pal[widx]
                cur[m["water"]] = cyc[m["water"]]
            # sparkles : ~0.35 % des pixels d'eau, allumés à tour de rôle
            if "water" in ramps:
                bright = lum(cur.astype(np.float32).transpose(2, 0, 1))
                hi = bright > np.percentile(bright[m["water"]], 55)
                spark = m["water"] & hi & (twk > 0.9965) & (np.sin(ph * 2 + twk_ph) > 0.55)
                cur[spark] = pal[ramps["water"][-1]]

        # 3. LAVE — cycling rapide, sens inverse ------------------------------ #
        if "lava" in ramps and m["lava"].any():
            r = ramps["lava"]; rot = np.roll(r, -(t % len(r)))
            remap = np.arange(len(pal)); remap[r] = rot
            lidx = remap[lut[cur[..., 0] >> 3, cur[..., 1] >> 3, cur[..., 2] >> 3]]
            cyc = pal[lidx]
            cur[m["lava"]] = cyc[m["lava"]]

        # 4. LUMIÈRE — taches qui défilent, 1 palier de gain ------------------ #
        drift = np.roll(np.roll(dapple, int(t * 1.6), 0), int(t * 2.4), 1)
        lit = (drift > 0.62) & ~m["water"] & ~m["lava"]
        soft = 1.0 + 0.10 * np.sin(ph)                       # respiration globale
        cur = cur.astype(np.float32)
        cur[lit] *= 1.11
        cur *= soft
        cur = np.clip(cur, 0, 255).astype(np.uint8)

        # 5. reprojection sur la palette d'origine ---------------------------- #
        cur = snap(cur, pal, lut).astype(np.uint8)
        frames.append(cur)

    # --- écriture -------------------------------------------------------- #
    name = os.path.splitext(os.path.basename(path))[0]
    os.makedirs(f"{out_dir}/frames/{name}", exist_ok=True)
    os.makedirs(f"{out_dir}/sheets", exist_ok=True)
    imgs = []
    for i, f in enumerate(frames):
        im = Image.fromarray(f, "RGB")
        im.save(f"{out_dir}/frames/{name}/f{i:02d}.png")
        imgs.append(im)

    # spritesheet 4 colonnes
    cols = 4; rows = (n + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * h))
    for i, im in enumerate(imgs):
        sheet.paste(im, ((i % cols) * w, (i // cols) * h))
    sheet.save(f"{out_dir}/sheets/{name}_sheet.png")

    gif = [im.quantize(colors=len(pal), method=Image.MEDIANCUT, dither=Image.Dither.NONE)
           for im in imgs]
    gif[0].save(f"{out_dir}/{name}.gif", save_all=True, append_images=gif[1:],
                duration=FRAME_MS, loop=0, optimize=True, disposal=1)
    return name, len(pal), {k: int(v.sum()) for k, v in m.items()}


# --------------------------------------------------------------------------- #
#  Variantes d'éclairage (layouts jour / crépuscule / nuit)
# --------------------------------------------------------------------------- #

GRADES = {
    "jour":       dict(mul=(1.00, 1.00, 1.00), lift=(0, 0, 0),      sat=1.00, gamma=1.00),
    "crepuscule": dict(mul=(1.06, 0.84, 0.66), lift=(18, 4, 10),    sat=0.92, gamma=1.05),
    "nuit":       dict(mul=(0.42, 0.52, 0.86), lift=(6, 10, 30),    sat=0.72, gamma=1.12),
}


def regrade(path, out_dir, grade):
    g = GRADES[grade]
    a = np.array(Image.open(path).convert("RGB")).astype(np.float32) / 255.0
    l = (a * np.array([0.299, 0.587, 0.114])).sum(-1, keepdims=True)
    a = l + (a - l) * g["sat"]
    a = np.clip(a, 0, 1) ** g["gamma"]
    a = a * np.array(g["mul"]) + np.array(g["lift"]) / 255.0
    a = np.clip(a * 255, 0, 255)
    a = ((a.astype(np.uint8) >> 3) * 8 + 7)
    im = Image.fromarray(a.astype(np.uint8), "RGB")
    im = im.quantize(colors=64, method=Image.MEDIANCUT, dither=Image.Dither.NONE).convert("RGB")
    name = os.path.splitext(os.path.basename(path))[0]
    os.makedirs(out_dir, exist_ok=True)
    im.save(f"{out_dir}/{name}__{grade}.png")
    return im
