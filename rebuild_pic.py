"""
rebuild_pic.py — reconstruit "Pic Fleuri" à partir des calques survivants.

Les bandes sources (ciel / montagnes / nuages) sont reprises telles quelles ;
les falaises, fleurs et touffes sont REPLACÉES, avec cette fois le catalogue de
falaises doublé par miroir horizontal (plus de silhouettes, moins de répétition).
"""
import sys, os, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image

from forge import core as C
from forge.compose import shear_sway, alpha_paste, contact_shadow
from forge.animate import build_lut, palette_of, snap
from build_pic import scatter, scatter_patches, chain, load_cut, blank, N, MS, W, H, HORIZON

SRC = "layers/rendu/pic_fleuri_src"
OUT = "layers/rendu/pic_fleuri"
REF = "/home/user/uploads/IMG_4856.png"


def load_seq(sub):
    fs = sorted(glob.glob(f"{SRC}/{sub}/*.png"))
    return [np.array(Image.open(f).convert("RGBA")) for f in fs]


def build(seed=7):
    rng = np.random.default_rng(seed)
    for sub in ("00_ciel", "01_montagnes", "02_nuages", "03_herbe",
                "04_falaises", "05_fleurs", "06_touffes", "frames"):
        os.makedirs(f"{OUT}/{sub}", exist_ok=True)

    ciel = load_seq("00_ciel")[0]
    mts = load_seq("01_montagnes")
    nua = load_seq("02_nuages")
    grass = load_seq("03_herbe")[0]
    for i, a in enumerate(mts):
        Image.fromarray(a, "RGBA").save(f"{OUT}/01_montagnes/f{i:02d}.png")
    for i, a in enumerate(nua):
        Image.fromarray(a, "RGBA").save(f"{OUT}/02_nuages/f{i:02d}.png")
    Image.fromarray(ciel, "RGBA").save(f"{OUT}/00_ciel/f00.png")
    Image.fromarray(grass, "RGBA").save(f"{OUT}/03_herbe/f00.png")

    # --- catalogue : falaises doublées par miroir ------------------------- #
    cliffs = load_cut("pic_cliffs_sheet", 0.36, 300)
    cliffs += [dict(name=o["name"] + "_m", img=o["img"][:, ::-1].copy(),
                    h=o["h"], w=o["w"]) for o in cliffs]
    flowers = load_cut("pic_flowers_sheet", 0.22, 60)
    tufts = load_cut("pic_tufts_sheet", 0.20, 30)

    grass_mask = grass[..., 3] > 127
    tall = [o for o in cliffs if o["h"] > o["w"] * 1.05]
    wide = [o for o in cliffs if o not in tall]

    cl = []
    cl += chain(tall or cliffs, rng, 6, HORIZON + 50, H + 40, 122, 16)
    cl += chain(tall or cliffs, rng, W - 6, HORIZON + 36, H + 40, 126, 16)
    cl += chain(tall or cliffs, rng, 168, HORIZON + 58, HORIZON + 214, 112, 26)
    cl += chain(tall or cliffs, rng, 356, H - 196, H - 40, 114, 26)
    cl += scatter(grass_mask, wide or cliffs, 4, rng, 120)
    cl.sort(key=lambda p: p[0] + p[2]["h"])

    cliff_layer = blank()
    for y, x, o in cl:
        contact_shadow(cliff_layer, o["img"], y, x, 0.30)
        alpha_paste(cliff_layer, o["img"], y, x)
    Image.fromarray(cliff_layer, "RGBA").save(f"{OUT}/04_falaises/f00.png")

    free = C.erode(grass_mask & (cliff_layer[..., 3] < 128), 3)
    taken = []
    fl = scatter_patches(free, flowers * 10, 82, rng, 8, 98, 24, taken)
    tf = scatter(free, tufts * 10, 62, rng, 20, taken)
    fl = [(y, x, o, 2, float(rng.random() * 2 * np.pi)) for y, x, o in fl]
    tf = [(y, x, o, 2, float(rng.random() * 2 * np.pi)) for y, x, o in tf]
    fl.sort(key=lambda p: p[0] + p[2]["h"])
    tf.sort(key=lambda p: p[0] + p[2]["h"])

    ref = np.array(Image.open(REF).convert("RGB"))
    pal = palette_of(ref); lut = build_lut(pal)

    finals = []
    for t in range(N):
        ph = 2 * np.pi * t / N
        frame = ciel.copy()
        alpha_paste(frame, mts[t % len(mts)], 0, 0)
        alpha_paste(frame, nua[t % len(nua)], 0, 0)
        alpha_paste(frame, grass, 0, 0)
        alpha_paste(frame, cliff_layer, 0, 0)

        fll = blank()
        for y, x, o, sw, phz in fl:
            alpha_paste(fll, shear_sway(o["img"], sw, phz, t, N),
                        y + (1 if np.sin(phz + ph) > 0.7 else 0), x)
        alpha_paste(frame, fll, 0, 0)
        Image.fromarray(fll, "RGBA").save(f"{OUT}/05_fleurs/f{t:02d}.png")

        tfl = blank()
        for y, x, o, sw, phz in tf:
            alpha_paste(tfl, shear_sway(o["img"], sw, phz, t, N), y, x)
        alpha_paste(frame, tfl, 0, 0)
        Image.fromarray(tfl, "RGBA").save(f"{OUT}/06_touffes/f{t:02d}.png")

        finals.append(snap(frame[..., :3], pal, lut).astype(np.uint8))

    imgs = []
    for t, f in enumerate(finals):
        im = Image.fromarray(f, "RGB"); im.save(f"{OUT}/frames/f{t:02d}.png"); imgs.append(im)
    g = [im.quantize(colors=min(255, len(pal)), method=Image.MEDIANCUT,
                     dither=Image.Dither.NONE) for im in imgs]
    g[0].save(f"{OUT}/pic_fleuri.gif", save_all=True, append_images=g[1:],
              duration=MS, loop=0, optimize=True, disposal=1)

    man = dict(zone="pic_fleuri", size=[W, H], tile=24, frames=N, frame_ms=MS,
               palette=int(len(pal)),
               palette_source="reference fournie (117 couleurs, DS 5 bits)",
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
                      technique="chaines verticales, catalogue double par miroir"),
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
