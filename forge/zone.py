"""
zone.py — le constructeur de zones.

Empile : sol de fond -> terrain intermédiaire -> clairière -> falaises/eau
-> décor de bordure -> props -> éclairage global. Sortie calée sur la grille
24 px et quantifiée en couleurs DS.
"""
import numpy as np
from . import core as C
from . import materials as M
from . import props as PR
from .palettes import P, BIOMES


def _layer(mask, kind, ramp, seed, h, w, bright=0.0, dither=0.9):
    rgb = M.render(kind, h, w, ramp, seed=seed, bright=bright, dither=dither)
    img = C.new_rgba(h, w)
    img[..., :3] = rgb
    img[..., 3] = np.where(mask, 255, 0)
    return img


def _edge_treatment(img, mask, dark="#0a1410", light=None, r=2):
    """Rim sombre à l'intérieur du bord + liseré clair sur le haut (relief PMD)."""
    inner = C.edge(mask, r)
    img[inner, :3] = C.ds_quant(img[inner, :3] * 0.62)
    if light:
        top = mask & ~C.shift(mask, 1, 0, False)
        img[top, :3] = C.ds_quant(C.hex2rgb(light))
    return img


PROFILES = {
    "jungle": dict(
        base_mat="foliage", mid_mat="grass", ground_mat="sand",
        border=[("tree_canopy", 46, 26), ("fern", 30, 22), ("bush", 34, 18)],
        inner=[("fern", 22, 7), ("bush", 20, 5), ("rock", 18, 3), ("flower_tuft", 16, 4)],
        ambient="#0b2a1e", light="#eaf7c0",
    ),
    "meadow": dict(
        base_mat="foliage", mid_mat="grass", ground_mat="sand",
        border=[("tree_canopy", 44, 20), ("bush", 30, 16), ("fern", 24, 10)],
        inner=[("flower_tuft", 18, 9), ("bush", 20, 5), ("rock", 18, 4), ("reed", 20, 3)],
        ambient="#12301c", light="#fff4c8",
    ),
    "beach": dict(
        base_mat="water", mid_mat="sand", ground_mat="sand",
        border=[("palm_leaf", 44, 12), ("bush", 30, 8), ("rock", 26, 12)],
        inner=[("rock", 20, 6), ("reed", 20, 3), ("flower_tuft", 16, 3), ("log", 26, 2)],
        ambient="#0d3550", light="#fff8d8",
    ),
    "cave": dict(
        base_mat="rock", mid_mat="rock", ground_mat="sand",
        border=[("stalagmite", 44, 22), ("rock", 34, 16)],
        inner=[("rock", 22, 8), ("stalagmite", 26, 4), ("crystal", 22, 3)],
        ambient="#0a0e18", light="#9fd8ff",
    ),
    "crystal": dict(
        base_mat="rock", mid_mat="crystal", ground_mat="rock",
        border=[("crystal", 46, 20), ("stalagmite", 38, 10)],
        inner=[("crystal", 26, 9), ("rock", 20, 4)],
        ambient="#0b1830", light="#cdf2ff",
    ),
    "desert": dict(
        base_mat="rock", mid_mat="sand", ground_mat="sand",
        border=[("rock", 46, 24), ("cactus", 34, 6)],
        inner=[("rock", 20, 8), ("cactus", 28, 3), ("bush", 18, 3)],
        ambient="#3a2410", light="#fff0bc",
    ),
    "ruins": dict(
        base_mat="foliage", mid_mat="stone", ground_mat="stone",
        border=[("tree_canopy", 44, 18), ("ruin_block", 34, 12), ("bush", 28, 10)],
        inner=[("ruin_block", 26, 7), ("rock", 20, 5), ("bush", 20, 4), ("fern", 20, 3)],
        ambient="#14261a", light="#ffeec0",
    ),
}


def build_zone(biome="jungle", tiles_w=21, tiles_h=19, seed=1, water_pool=False,
               clearing=(0.5, 0.52, 0.36, 0.34)):
    """Construit une zone complète. Renvoie un tableau RGBA (H, W, 4)."""
    w, h = tiles_w * 24, tiles_h * 24
    pal = BIOMES[biome]; prof = PROFILES[biome]
    r = C.rng(seed)

    canvas = C.new_rgba(h, w)

    # 1. fond -------------------------------------------------------------- #
    full = np.ones((h, w), bool)
    C.paste(canvas, _layer(full, prof["base_mat"], P[pal["base"]], seed, h, w, bright=-0.18), 0, 0)

    # 2. terrain intermédiaire (zone jouable) -------------------------------- #
    mid = C.blob_mask(h, w, seed + 3, 0.5, 0.5, 0.44, 0.44, wobble=0.30, cells=3)
    mid |= C.blob_mask(h, w, seed + 4, 0.35, 0.4, 0.26, 0.26, wobble=0.35)
    mid |= C.blob_mask(h, w, seed + 5, 0.68, 0.6, 0.24, 0.24, wobble=0.35)
    mid &= C.erode(np.ones((h, w), bool), 0)
    midimg = _layer(mid, prof["mid_mat"], P[pal["mid"]], seed + 10, h, w)
    _edge_treatment(midimg, mid, r=2)
    C.paste(canvas, midimg, 0, 0)

    # 3. clairière / chemin -------------------------------------------------- #
    cx, cy, rx, ry = clearing
    gr = C.blob_mask(h, w, seed + 7, cx, cy, rx, ry, wobble=0.30, cells=4) & C.erode(mid, 5)
    grimg = _layer(gr, prof["ground_mat"], P[pal["ground"]], seed + 20, h, w)
    _edge_treatment(grimg, gr, r=2)
    C.paste(canvas, grimg, 0, 0)
    # halo sombre autour de la clairière
    C.mul_shadow(canvas, C.blur((C.dilate(gr, 3) & ~gr).astype(float), 2), 0.30)

    # 4. mare optionnelle ---------------------------------------------------- #
    if water_pool:
        pw = C.blob_mask(h, w, seed + 31, 0.30 + 0.4 * r.random(), 0.62,
                         0.13, 0.10, wobble=0.30) & C.erode(mid, 8)
        wimg = _layer(pw, "water", P[pal["water"]], seed + 40, h, w)
        rim = C.edge(pw, 2)
        wimg[rim, :3] = C.ds_quant(wimg[rim, :3] * 0.7)
        C.paste(canvas, wimg, 0, 0)
        C.mul_shadow(canvas, C.blur((C.dilate(pw, 2) & ~pw).astype(float), 1), 0.35)

    # 5. décor de bordure ---------------------------------------------------- #
    fall = C.frame_falloff(h, w, 0.16)
    border_zone = fall < 0.85
    placements = []
    for name, size, count in prof["border"]:
        for _ in range(count):
            for _try in range(40):
                x = int(r.integers(-size // 2, w - size // 2))
                y = int(r.integers(-size // 2, h - size // 2))
                py, px = np.clip(y + size // 2, 0, h - 1), np.clip(x + size // 2, 0, w - 1)
                if border_zone[py, px] and not mid[py, px]:
                    placements.append((y, x, name, size, int(r.integers(0, 10 ** 6))))
                    break

    # 6. props internes ------------------------------------------------------ #
    inner_ok = (mid | gr) & C.erode(mid, 3)
    for name, size, count in prof["inner"]:
        for _ in range(count):
            for _try in range(60):
                x = int(r.integers(0, w - size)); y = int(r.integers(0, h - size))
                py, px = y + size - 4, x + size // 2
                if 0 <= py < h and inner_ok[py, px]:
                    placements.append((y, x, name, size, int(r.integers(0, 10 ** 6))))
                    break

    ramp_for = {
        "fern": P[pal["accent"]], "bush": P[pal["mid"]], "tree_canopy": P[pal["base"]],
        "palm_leaf": P[pal["accent"]], "rock": P[pal["rock"]], "crystal": P[pal["accent"]],
        "reed": P[pal["accent"]], "flower_tuft": P[pal["mid"]], "log": P["dirt_path"],
        "stalagmite": P[pal["rock"]], "ruin_block": P["ruin_stone"], "cactus": P["grass_meadow"],
    }

    placements.sort(key=lambda p: p[0] + p[3])          # painter's algorithm
    for y, x, name, size, s in placements:
        sprite = PR.CATALOG[name](size, ramp_for[name], seed=s)
        if name in ("fern", "bush", "tree_canopy", "palm_leaf", "reed"):
            sh = PR.drop_shadow(size, size, size * 0.90, size * 0.5, size * 0.07, size * 0.30, 90)
            C.paste(canvas, sh, y, x)
        C.paste(canvas, sprite, y, x)

    # 7. éclairage global ---------------------------------------------------- #
    yy, _ = np.mgrid[0:h, 0:w]
    vert = (yy / h)
    C.tint(canvas, prof["ambient"], vert * 0.22)                      # bas plus sombre
    C.tint(canvas, prof["light"], np.clip(1 - vert * 1.4, 0, 1) * 0.10)
    C.mul_shadow(canvas, 1 - C.frame_falloff(h, w, 0.13), 0.42)       # cadrage
    canvas[..., 3] = 255
    canvas[..., :3] = C.ds_quant(canvas[..., :3])
    return canvas
