"""
materials.py — textures de sol procédurales (24x24 compatibles, sans couture).

Chaque fonction renvoie un champ de luminosité 0..1 que `core.ramp_shade`
transforme en pixel-art tramé sur une rampe de palette.
"""
import numpy as np
from . import core as C


def cellular(h, w, cell=14, seed=0, jitter=0.85):
    """Worley : renvoie (bord, id_cellule) — donne le grain 'écailles' des sols PMD."""
    r = C.rng(seed)
    gy = h // cell + 3
    gx = w // cell + 3
    px = (np.arange(gx)[None, :] - 1 + r.random((gy, gx)) * jitter) * cell
    py = (np.arange(gy)[:, None] - 1 + r.random((gy, gx)) * jitter) * cell
    ids = r.random((gy, gx))

    yy, xx = np.mgrid[0:h, 0:w]
    d1 = np.full((h, w), 1e9); d2 = np.full((h, w), 1e9)
    best = np.zeros((h, w))
    for j in range(gy):
        for i in range(gx):
            d = (xx - px[j, i]) ** 2 + (yy - py[j, i]) ** 2
            closer = d < d1
            d2 = np.where(closer, d1, np.minimum(d2, d))
            best = np.where(closer, ids[j, i], best)
            d1 = np.where(closer, d, d1)
    border = np.sqrt(d2) - np.sqrt(d1)
    return border, best


def _light(field, strength=1.0):
    """Éclairage lambert bon marché depuis la hauteur (soleil haut-gauche)."""
    gy, gx = np.gradient(field)
    return np.clip(0.5 + (-gy * 2.2 - gx * 1.6) * strength * 8, 0, 1)


# --------------------------------------------------------------------------- #
#  Sols
# --------------------------------------------------------------------------- #

def mat_sand(h, w, seed=0):
    """Sable / terre battue : plaques cellulaires + micro-grain + galets."""
    b, ids = cellular(h, w, cell=11, seed=seed)
    plates = np.clip(b / 6.0, 0, 1) * 0.16 + ids * 0.10
    grain = C.fbm(h, w, 26, 3, seed=seed + 5) * 0.16
    broad = C.fbm(h, w, 3, 4, seed=seed + 9) * 0.44
    patch = C.fbm(h, w, 7, 3, seed=seed + 13)
    t = 0.34 + plates + grain + broad + (patch - 0.5) * 0.22
    t += (C.bayer(h, w) - 0.5) * 0.05
    return np.clip(t, 0, 1)


def mat_grass(h, w, seed=0):
    """Herbe : touffes courtes orientées + variation large."""
    r = C.rng(seed)
    broad = C.fbm(h, w, 4, 4, seed=seed) * 0.45
    tuft = C.fbm(h, w, 30, 2, seed=seed + 3)
    tuft = np.clip((tuft - 0.5) * 3.2, -1, 1)
    tuft = np.where(tuft > 0.25, 0.30, np.where(tuft < -0.35, -0.16, 0.0))
    streak = C.value_noise(h, w, 60, seed + 17)
    t = 0.34 + broad + tuft + (streak - 0.5) * 0.14
    return np.clip(t, 0, 1)


def mat_foliage(h, w, seed=0):
    """Masse de feuillage : amas de blobs éclairés par le haut."""
    b, ids = cellular(h, w, cell=9, seed=seed, jitter=1.0)
    lobes = np.clip(b / 3.2, 0, 1)
    hgt = C.fbm(h, w, 6, 4, seed=seed + 2)
    t = 0.18 + lobes * 0.42 + hgt * 0.34 + ids * 0.10
    t += _light(C.blur(lobes, 1), 0.20) * 0.14
    return np.clip(t, 0, 1)


def mat_rock(h, w, seed=0):
    """Roche : strates + fissures nettes."""
    strata = C.fbm(h, w, 5, 4, seed=seed)
    strata = (strata * 5 % 1.0) * 0.22 + strata * 0.5
    crack, _ = cellular(h, w, cell=17, seed=seed + 4)
    crackm = np.clip(crack / 2.2, 0, 1)
    t = 0.22 + strata + crackm * 0.34 + C.fbm(h, w, 26, 2, seed=seed + 8) * 0.14
    return np.clip(t, 0, 1)


def mat_water(h, w, seed=0):
    """Eau : ondulations horizontales + reflets clairs."""
    yy, xx = np.mgrid[0:h, 0:w]
    wave = np.sin((yy * 0.55 + C.fbm(h, w, 5, 3, seed=seed) * 9) * 1.0)
    ripple = C.fbm(h, w, 9, 3, seed=seed + 6)
    t = 0.34 + wave * 0.11 + ripple * 0.42
    spark = (C.fbm(h, w, 40, 2, seed=seed + 12) > 0.86) & (ripple > 0.55)
    t = np.where(spark, 1.0, t)
    return np.clip(t, 0, 1)


def mat_crystal(h, w, seed=0):
    """Cristal : facettes anguleuses à fort contraste."""
    b, ids = cellular(h, w, cell=15, seed=seed, jitter=1.0)
    facet = ids * 0.62 + np.clip(b / 3.0, 0, 1) * 0.28
    t = 0.16 + facet + C.fbm(h, w, 8, 3, seed=seed + 1) * 0.16
    t = np.where(np.clip(b / 1.4, 0, 1) < 0.35, t * 0.45, t)   # arêtes sombres
    return np.clip(t, 0, 1)


def mat_stone_floor(h, w, seed=0):
    """Dallage taillé : joints réguliers + usure."""
    yy, xx = np.mgrid[0:h, 0:w]
    tile = 24
    off = ((yy // tile) % 2) * (tile // 2)
    gx = ((xx + off) % tile); gy = (yy % tile)
    joint = (gx < 2) | (gy < 2)
    wear = C.fbm(h, w, 7, 4, seed=seed) * 0.42 + C.fbm(h, w, 24, 2, seed=seed + 3) * 0.16
    t = 0.42 + wear
    t = np.where(joint, t * 0.52, t)
    t = np.where((gx == 2) | (gy == 2), np.clip(t + 0.16, 0, 1), t)   # arête éclairée
    return np.clip(t, 0, 1)


MATERIALS = {
    "sand": mat_sand, "grass": mat_grass, "foliage": mat_foliage,
    "rock": mat_rock, "water": mat_water, "crystal": mat_crystal,
    "stone": mat_stone_floor,
}


def render(kind, h, w, ramp, seed=0, dither=0.9, bright=0.0):
    t = MATERIALS[kind](h, w, seed)
    if bright:
        t = np.clip(t + bright, 0, 1)
    return C.ramp_shade(t, ramp, dither=dither, seed=seed)
