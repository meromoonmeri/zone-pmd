"""
build_pic.py — zone "Pic Fleuri" montée en 7 calques séparés.

DA calée sur la référence fournie : la composition finale est reprojetée sur la
palette EXACTE de l'image de référence (117 couleurs, espace DS 5 bits).

Calques (du fond vers l'avant), chacun exporté frame par frame :
    0 ciel        statique   dégradé procédural
    1 montagnes   ANIMÉ      brume qui dérive sur les sommets
    2 nuages      ANIMÉ      dérive horizontale ping-pong + houle + cycling
    3 herbe       statique   terrain, bord supérieur organique
    4 falaises    statique   pièces rocheuses en chaînes verticales
    5 fleurs      ANIMÉ      cisaillement, phase aléatoire par touffe
    6 touffes     ANIMÉ      idem, amplitude plus forte
"""
import sys, os, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image

from forge import core as C
from forge.chroma import key_out, scale_rgba, cut_objects
from forge.compose import shear_sway, alpha_paste, contact_shadow, hsv_mask
from forge.animate import fbm, build_lut, palette_of, snap

W = H = 21 * 24          # 504 x 504, comme la référence
N = 12
MS = 110
REF = "/home/user/uploads/IMG_4856.png"
OUT = "layers/rendu/pic_fleuri"

HORIZON = 134            # ligne où l'herbe rencontre la mer de nuages
SKY_BAND = 50            # bande de ciel pur en haut

RAMP_MTS = ["#47607f", "#5b7598", "#6f89a8", "#87a1bd", "#a3bad2", "#c3d5e7", "#e3eefb"]
RAMP_CLOUD = ["#8fa7d7", "#a7bfe7", "#c7d7ef", "#cfdff7", "#d7e7f7", "#dfe7ff",
              "#e7efff", "#eff7ff", "#ffffff"]
SKY_TOP, SKY_HORIZON = "#0f4fff", "#3f8fff"


# --------------------------------------------------------------------------- #

def blank(h=H, w=W):
    return np.zeros((h, w, 4), np.uint8)


def recolor(rgba, ramp, lo=0.0, hi=1.0):
    """Remappe la luminance d'un calque sur une rampe : conformité DA garantie."""
    a = rgba[..., :3].astype(np.float32) / 255.0
    l = (a * np.array([0.299, 0.587, 0.114])).sum(-1)
    m = rgba[..., 3] > 127
    if m.sum() == 0:
        return rgba
    lo_v, hi_v = np.percentile(l[m], 3), np.percentile(l[m], 97)
    t = np.clip((l - lo_v) / max(hi_v - lo_v, 1e-6), 0, 1) * (hi - lo) + lo
    out = rgba.copy()
    out[..., :3] = C.ramp_shade(t, ramp, dither=0.35, seed=1)
    out[..., 3] = np.where(m, 255, 0)
    return out


def fit_strip(path, target_w, ramp=None, key_tol=60):
    """Détoure une bande (nuages / montagnes), recadre sur son contenu, met à l'échelle."""
    rgba = key_out(path, tol=key_tol)
    m = rgba[..., 3] > 127
    ys, xs = np.where(m)
    rgba = rgba[ys.min():ys.max() + 1, max(0, xs.min()):xs.max() + 1]
    rgba = scale_rgba(rgba, target_w / rgba.shape[1])
    if ramp:
        rgba = recolor(rgba, ramp)
    return rgba


def fit_box(rgba, target_w, target_h):
    """Redimensionnement NON uniforme (prémultiplié) : on impose largeur ET hauteur."""
    h, w = rgba.shape[:2]
    a = rgba[..., 3:4].astype(np.float32) / 255.0
    pm = np.concatenate([rgba[..., :3].astype(np.float32) * a, a * 255], -1)
    im = Image.fromarray(np.clip(pm, 0, 255).astype(np.uint8), "RGBA").resize(
        (int(target_w), int(target_h)), Image.LANCZOS)
    pm = np.array(im).astype(np.float32)
    na = pm[..., 3:4] / 255.0
    rgb = np.where(na > 0.02, pm[..., :3] / np.maximum(na, 1e-3), 0)
    out = np.zeros((int(target_h), int(target_w), 4), np.uint8)
    out[..., :3] = ((np.clip(rgb, 0, 255).astype(np.uint8) >> 3) * 8 + 7)
    out[..., 3] = np.where(na[..., 0] > 0.5, 255, 0)
    return out


def crop_peaks(rgba, cover=0.93):
    """Coupe le socle plein peint sous les sommets : on ne garde que la silhouette."""
    cov = (rgba[..., 3] > 127).mean(1)
    solid = np.flatnonzero(cov > cover)
    if len(solid):
        rgba = rgba[:solid[0]]
    m = rgba[..., 3] > 127
    ys, xs = np.where(m)
    return rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def sky_layer():
    yy = np.mgrid[0:H, 0:W][0]
    t = np.clip(yy / (HORIZON + 40.0), 0, 1) ** 0.75
    ramp = [SKY_TOP, "#1757ff", "#1f67ff", "#2f7fff", SKY_HORIZON]
    img = blank()
    img[..., :3] = C.ramp_shade(t, ramp, dither=0.5, seed=4)
    img[..., 3] = 255
    return img


def grass_layer(path, seed=0):
    """Terrain + découpe du bord supérieur en silhouette organique."""
    im = Image.open(path).convert("RGB")
    s = max(W / im.width, (H - HORIZON + 60) / im.height)
    im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
    a = np.array(im)[:H, :W]
    if a.shape[0] < H:
        a = np.vstack([a, np.repeat(a[-1:], H - a.shape[0], 0)])
    img = blank()
    img[..., :3] = C.ds_quant(a)
    edge = HORIZON + (fbm(1, W, 7, 3, seed + 2)[0] - 0.5) * 30
    yy = np.mgrid[0:H, 0:W][0]
    img[..., 3] = np.where(yy >= edge[None, :], 255, 0)
    return img


# --------------------------------------------------------------------------- #
#  Placements
# --------------------------------------------------------------------------- #

def chain(objs, rng, x_center, y0, y1, step, jitter_x=26, scale_pick=None):
    """Chaîne verticale de rochers -> forme une crête / un couloir."""
    out = []
    y = y0
    while y < y1:
        o = objs[int(rng.integers(0, len(objs)))]
        if scale_pick and not scale_pick(o):
            y += 8
            continue
        x = int(x_center - o["w"] / 2 + rng.integers(-jitter_x, jitter_x))
        out.append((int(y - o["h"] * 0.55), x, o))
        y += step + int(rng.integers(-14, 18))
    return out


def scatter(surface, pool, count, rng, min_dist=0, taken=None):
    h, w = surface.shape
    out = []
    taken = taken if taken is not None else []
    order = list(pool); rng.shuffle(order)
    for o in order[:count]:
        for _ in range(240):
            x = int(rng.integers(-o["w"] // 5, w - o["w"] * 4 // 5))
            y = int(rng.integers(-o["h"] // 5, h - o["h"] * 4 // 5))
            by, bx = y + o["h"] - 2, x + o["w"] // 2
            if not (0 <= by < h and 0 <= bx < w) or not surface[by, bx]:
                continue
            if min_dist and any((by - py) ** 2 + (bx - px) ** 2 < min_dist ** 2
                                for py, px in taken):
                continue
            out.append((y, x, o)); taken.append((by, bx)); break
    return out


def scatter_patches(surface, pool, count, rng, n_patches, radius, min_dist, taken):
    """Répartit en TACHES plutôt qu'uniformément : c'est la lecture de la référence."""
    h, w = surface.shape
    ys, xs = np.where(surface)
    if len(ys) == 0:
        return []
    idx = rng.choice(len(ys), size=min(n_patches, len(ys)), replace=False)
    centers = [(ys[i], xs[i]) for i in idx]
    out = []
    order = list(pool); rng.shuffle(order)
    for o in order[:count]:
        cy, cx = centers[int(rng.integers(0, len(centers)))]
        for _ in range(260):
            y = int(cy + rng.normal(0, radius * 0.42)) - o["h"] + 2
            x = int(cx + rng.normal(0, radius * 0.55)) - o["w"] // 2
            by, bx = y + o["h"] - 2, x + o["w"] // 2
            if not (0 <= by < h and 0 <= bx < w) or not surface[by, bx]:
                continue
            if any((by - py) ** 2 + (bx - px) ** 2 < min_dist ** 2 for py, px in taken):
                continue
            out.append((y, x, o)); taken.append((by, bx)); break
    return out


def load_cut(sheet, scale, min_px=40):
    d = f"layers/cut/{sheet}"
    if not os.path.isdir(d) or not glob.glob(d + "/*.png"):
        cut_objects(f"layers/src/{sheet}.png", d, min_px=min_px,
                    prefix=sheet[:5], scale=scale)
    objs = []
    for f in sorted(glob.glob(d + "/*.png")):
        a = np.array(Image.open(f).convert("RGBA"))
        if a[..., 3].sum():
            objs.append(dict(name=os.path.basename(f), img=a, h=a.shape[0], w=a.shape[1]))
    return objs


# --------------------------------------------------------------------------- #

def build(seed=7):
    rng = np.random.default_rng(seed)
    for sub in ("00_ciel", "01_montagnes", "02_nuages", "03_herbe",
                "04_falaises", "05_fleurs", "06_touffes", "frames"):
        os.makedirs(f"{OUT}/{sub}", exist_ok=True)

    # ---- calques de fond -------------------------------------------------- #
    sky = sky_layer()
    Image.fromarray(sky, "RGBA").save(f"{OUT}/00_ciel/f00.png")

    mts = key_out("layers/src/pic_mountains_strip.png", tol=60)
    mts = crop_peaks(mts)
    mts = fit_box(mts, W + 24, 94)
    mts = recolor(mts, RAMP_MTS)
    clouds = key_out("layers/src/pic_clouds_strip.png", tol=60)
    m = clouds[..., 3] > 127; ys, xs = np.where(m)
    clouds = clouds[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    clouds = fit_box(clouds, W + 28, 78)
    clouds = recolor(clouds, RAMP_CLOUD)

    grass = grass_layer("layers/src/pic_grass_terrain.png", seed)
    Image.fromarray(grass, "RGBA").save(f"{OUT}/03_herbe/f00.png")

    # ---- objets ------------------------------------------------------------ #
    cliffs = load_cut("pic_cliffs_sheet", 0.36, 300)
    cliffs = cliffs + [dict(name=o["name"] + "_m", img=o["img"][:, ::-1].copy(),
                            h=o["h"], w=o["w"]) for o in cliffs]
    flowers = load_cut("pic_flowers_sheet", 0.22, 60)
    tufts = load_cut("pic_tufts_sheet", 0.20, 30)

    grass_mask = grass[..., 3] > 127

    # ---- falaises : crêtes verticales, comme sur la référence -------------- #
    tall = [o for o in cliffs if o["h"] > o["w"] * 1.05]
    wide = [o for o in cliffs if o not in tall]
    cl = []
    cl += chain(tall or cliffs, rng, 6, HORIZON + 50, H + 40, 128, 16)
    cl += chain(tall or cliffs, rng, W - 6, HORIZON + 36, H + 40, 132, 16)
    cl += chain(tall or cliffs, rng, 168, HORIZON + 58, HORIZON + 210, 118, 26)
    cl += chain(tall or cliffs, rng, 356, H - 190, H - 44, 120, 26)
    cl += scatter(grass_mask, wide or cliffs, 3, rng, 130)
    cl.sort(key=lambda p: p[0] + p[2]["h"])

    cliff_layer = blank()
    for y, x, o in cl:
        contact_shadow(cliff_layer, o["img"], y, x, 0.30)
        alpha_paste(cliff_layer, o["img"], y, x)
    Image.fromarray(cliff_layer, "RGBA").save(f"{OUT}/04_falaises/f00.png")

    free = grass_mask & (cliff_layer[..., 3] < 128)
    free = C.erode(free, 3)

    # ---- fleurs & touffes --------------------------------------------------- #
    taken = []
    fl = scatter_patches(free, flowers * 10, 82, rng, 8, 98, 24, taken)
    tf = scatter(free, tufts * 10, 62, rng, 20, taken)
    fl = [(y, x, o, 2, float(rng.random() * 2 * np.pi)) for y, x, o in fl]
    tf = [(y, x, o, 2, float(rng.random() * 2 * np.pi)) for y, x, o in tf]
    fl.sort(key=lambda p: p[0] + p[2]["h"])
    tf.sort(key=lambda p: p[0] + p[2]["h"])

    # ---- palette cible = celle de la référence ------------------------------ #
    ref = np.array(Image.open(REF).convert("RGB"))
    pal = palette_of(ref); lut = build_lut(pal)

    finals = []
    for t in range(N):
        ph = 2 * np.pi * t / N
        frame = sky.copy()

        # montagnes : voile de brume qui glisse
        ml = blank()
        alpha_paste(ml, mts, 34, -12)
        haze = np.mgrid[0:H, 0:W][1]
        band = (np.sin(haze * 0.018 + ph) > 0.55) & (ml[..., 3] > 127)
        ml[band, :3] = C.ds_quant(ml[band, :3].astype(np.float32) * 0.55 +
                                  C.hex2rgb("#e7efff") * 0.45)
        alpha_paste(frame, ml, 0, 0)
        Image.fromarray(ml, "RGBA").save(f"{OUT}/01_montagnes/f{t:02d}.png")

        # nuages : dérive ping-pong + houle verticale + cycling du highlight
        dx = int(round(5 * np.sin(ph)))
        dy = int(round(1.6 * np.sin(ph * 2)))
        cl_l = blank()
        alpha_paste(cl_l, clouds, 80 + dy, -14 + dx)
        hi = C.ds_quant(C.hex2rgb(RAMP_CLOUD[-1]))
        cm = cl_l[..., 3] > 127
        crest = cm & ~C.erode(cm, 3)                      # 3 px du bord réel du nuage
        xg = np.mgrid[0:H, 0:W][1]
        crest &= (np.sin(xg * 0.055 - ph * 1.0) > 0.45)   # vague qui parcourt la crête
        cl_l[crest, :3] = hi
        alpha_paste(frame, cl_l, 0, 0)
        Image.fromarray(cl_l, "RGBA").save(f"{OUT}/02_nuages/f{t:02d}.png")

        alpha_paste(frame, grass, 0, 0)
        alpha_paste(frame, cliff_layer, 0, 0)

        fll = blank()
        for y, x, o, sw, phz in fl:
            spr = shear_sway(o["img"], sw, phz, t, N)
            alpha_paste(fll, spr, y + (1 if np.sin(phz + ph) > 0.7 else 0), x)
        alpha_paste(frame, fll, 0, 0)
        Image.fromarray(fll, "RGBA").save(f"{OUT}/05_fleurs/f{t:02d}.png")

        tfl = blank()
        for y, x, o, sw, phz in tf:
            alpha_paste(tfl, shear_sway(o["img"], sw, phz, t, N), y, x)
        alpha_paste(frame, tfl, 0, 0)
        Image.fromarray(tfl, "RGBA").save(f"{OUT}/06_touffes/f{t:02d}.png")

        rgb = snap(frame[..., :3], pal, lut).astype(np.uint8)
        finals.append(rgb)

    imgs = []
    for t, f in enumerate(finals):
        im = Image.fromarray(f, "RGB"); im.save(f"{OUT}/frames/f{t:02d}.png"); imgs.append(im)
    gif = [im.quantize(colors=min(255, len(pal)), method=Image.MEDIANCUT,
                       dither=Image.Dither.NONE) for im in imgs]
    gif[0].save(f"{OUT}/pic_fleuri.gif", save_all=True, append_images=gif[1:],
                duration=MS, loop=0, optimize=True, disposal=1)

    man = dict(zone="pic_fleuri", size=[W, H], tile=24, frames=N, frame_ms=MS,
               palette=int(len(pal)), palette_source="reference fournie (117 couleurs, DS 5 bits)",
               layers=[
                 dict(order=0, name="ciel", dir="00_ciel", animated=False,
                      technique="degrade procedural"),
                 dict(order=1, name="montagnes", dir="01_montagnes", animated=True,
                      technique="voile de brume glissant"),
                 dict(order=2, name="nuages", dir="02_nuages", animated=True,
                      technique="derive ping-pong + houle + cycling des cretes"),
                 dict(order=3, name="herbe", dir="03_herbe", animated=False,
                      technique="bord superieur organique (fbm)"),
                 dict(order=4, name="falaises", dir="04_falaises", animated=False,
                      technique="chaines verticales + ombres de contact"),
                 dict(order=5, name="fleurs", dir="05_fleurs", animated=True,
                      technique="cisaillement + bob 1px, phase aleatoire"),
                 dict(order=6, name="touffes", dir="06_touffes", animated=True,
                      technique="cisaillement, phase aleatoire"),
               ],
               counts=dict(falaises=len(cl), fleurs=len(fl), touffes=len(tf)))
    json.dump(man, open(f"{OUT}/manifest.json", "w"), indent=1)
    return man


if __name__ == "__main__":
    print(json.dumps(build()["counts"], indent=1))
