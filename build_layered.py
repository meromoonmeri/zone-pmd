"""
build_layered.py — assemblage de zones à partir de calques séparés.

Placement piloté par des RÈGLES explicites (catégorie d'objet x surface cible x
quota x plafond par objet) : plus de ponton dupliqué cinq fois, plus de nénuphar
sur la berge. Les masques viennent du terrain lui-même, pas d'une devinette.

Sortie par zone dans layers/rendu/<zone>/ :
    00_terrain.png      fond statique (dégradé de bord appliqué)
    01_water/f##.png    nappe animée, masque exact (trou magenta du terrain)
    02_props/f##.png    végétation/objets animés (cisaillement, base fixe)
    03_canopy/f##.png   cadre de canopée animé (phase lente)
    frames/f##.png      composite final
    <zone>.gif          boucle
    manifest.json       ordre des calques, techniques, quotas
"""
import sys, os, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glob
import numpy as np
from PIL import Image

from forge import core as C
from forge.water_pmd import water_layer, preuve as preuve_eau
from forge.water_halcyon import (water_layer as water_layer_hal,
                                 preuve as preuve_eau_hal)
from forge import calques_halcyon as CH
from forge.compose import (W, H, N, MS, load_terrain, hsv_mask,
                           load_objects, shear_sway, alpha_paste, contact_shadow,
                           apply_light, LIGHT_GRADES, enrich_terrain)
from forge.animate import fbm, build_lut, palette_of, snap

RAMP_LAKE = ["#0d2f3a", "#113c4a", "#154a5a", "#1a5c6b", "#20707c", "#28858e", "#38a0a3", "#55bcb8"]
FOAM_LAKE = "#a8ded8"


# --------------------------------------------------------------------------- #
#  Objets + tags
# --------------------------------------------------------------------------- #

def load_tagged(cut_dir, tag_file=None):
    objs = load_objects(cut_dir)
    tags = {}
    if tag_file and os.path.exists(tag_file):
        for cat, ids in json.load(open(tag_file)).items():
            for i in ids:
                if i < len(objs):
                    tags.setdefault(cat, []).append(objs[i])
    else:
        tags["all"] = objs
    return objs, tags


def veg_score(obj):
    a = obj["img"]; m = a[..., 3] > 127
    if m.sum() == 0:
        return 0.0
    g = hsv_mask(a[..., :3], 0.17, 0.47, smin=0.15, vmin=0.08)
    return float((g & m).sum()) / float(m.sum())


# --------------------------------------------------------------------------- #
#  Placement par règles
# --------------------------------------------------------------------------- #

def place(surface, pool, count, rng, min_dist=0, taken=None, margin=2):
    """Place `count` objets tirés de `pool` : la BASE du sprite doit toucher la surface."""
    h, w = surface.shape
    out = []
    taken = taken if taken is not None else []
    order = list(pool)
    rng.shuffle(order)
    for o in order[:count]:
        ow, oh = o["w"], o["h"]
        for _ in range(200):
            x = int(rng.integers(-ow // 5, w - ow * 4 // 5))
            y = int(rng.integers(-oh // 5, h - oh * 4 // 5))
            by, bx = y + oh - margin, x + ow // 2
            if not (0 <= by < h and 0 <= bx < w) or not surface[by, bx]:
                continue
            if min_dist and any((by - py) ** 2 + (bx - px) ** 2 < min_dist ** 2
                                for py, px in taken):
                continue
            out.append((y, x, o)); taken.append((by, bx))
            break
    return out


def pool_of(tags, cats, cap):
    p = []
    for c in cats:
        for o in tags.get(c, []):
            p += [o] * cap
    return p


def ring_positions(objs, rng, step=44):
    out = []
    for x in range(-34, W + 34, step):
        for oy, sgn in ((0, 1), (1, -1)):
            o = objs[int(rng.integers(0, len(objs)))]
            y = int(-o["h"] * 0.44 + rng.integers(-10, 16)) if sgn > 0 else \
                int(H - o["h"] * 0.60 + rng.integers(-14, 12))
            out.append((y, x + int(rng.integers(-11, 11)), o))
    for y in range(-24, H + 24, step):
        for sgn in (1, -1):
            o = objs[int(rng.integers(0, len(objs)))]
            x = int(-o["w"] * 0.42 + rng.integers(-10, 12)) if sgn > 0 else \
                int(W - o["w"] * 0.58 + rng.integers(-12, 10))
            out.append((y + int(rng.integers(-11, 11)), x, o))
    return out


# --------------------------------------------------------------------------- #
#  Terrain : dégradé de bord pour marier le fond et la canopée
# --------------------------------------------------------------------------- #

def grade_terrain(rgb, tint_hex, strength=0.55, pad=0.20):
    f = C.frame_falloff(H, W, pad)
    a = rgb.astype(np.float32)
    t = C.hex2rgb(tint_hex)
    k = ((1.0 - f) * strength)[..., None]
    return C.ds_quant(a * (1 - k) + t * k)


# --------------------------------------------------------------------------- #
#  Rendu
# --------------------------------------------------------------------------- #

def render(zone, terrain_src, cut_dir, tag_file=None, canopy_dir=None,
           rules=None, water_ramp=None, foam=None, calm=1.0, eau_emissive=False,
           style_eau="sky",
           terrain_tint="#0a1c14", terrain_strength=0.55,
           seed=1, grade="jour"):
    rng = np.random.default_rng(seed)
    terrain, key = load_terrain(terrain_src)
    out_dir = f"layers/rendu/{zone}"
    os.makedirs(out_dir, exist_ok=True)

    water_mask = key if key.sum() > 500 else None
    grass = hsv_mask(terrain, 0.17, 0.47, smin=0.13, vmin=0.06)
    sand = hsv_mask(terrain, 0.04, 0.20, smin=0.08, vmin=0.18)
    grey = ~grass & ~sand & (key == False)
    ground = grass | sand | grey
    if water_mask is not None:
        ground &= ~C.dilate(water_mask, 1)

    fall = C.frame_falloff(H, W, 0.17)
    surfaces = {
        "ground": ground & (fall > 0.42),
        "inner": ground & (fall > 0.62),
        "midband": ground & (fall > 0.16) & (fall < 0.62),
        "grass": grass & (fall > 0.42),
        "sand": sand & (fall > 0.45),
    }
    if water_mask is not None:
        surfaces["water"] = C.erode(water_mask, 6)
        surfaces["shore"] = C.dilate(water_mask, 8) & ~water_mask & ground
        surfaces["shore_bottom"] = surfaces["shore"] & (np.mgrid[0:H, 0:W][0] > H * 0.52)
        surfaces["outer"] = ground & ~C.dilate(water_mask, 12)

    objs, tags = load_tagged(cut_dir, tag_file)
    for o in objs:
        o["veg"] = veg_score(o)
    canopy = load_objects(canopy_dir) if canopy_dir else []
    for o in canopy:
        o["veg"] = 1.0

    # --- application des règles ------------------------------------------ #
    placed, taken = [], []
    for r in (rules or []):
        surf = surfaces.get(r["surface"])
        if surf is None or not surf.any():
            continue
        pool = pool_of(tags, r["cats"], r.get("cap", 3))
        if not pool:
            continue
        got = place(surf, pool, r["count"], rng, r.get("min_dist", 0), taken)
        for y, x, o in got:
            placed.append((y, x, o, r.get("sway", 2 if o["veg"] > 0.5 else 0),
                           float(rng.random() * 2 * np.pi), tuple(r["cats"])))
    placed.sort(key=lambda p: p[0] + p[2]["h"])

    canopy_placed = []
    if canopy:
        for y, x, o in ring_positions(canopy, rng):
            canopy_placed.append((y, x, o, 1, float(rng.random() * 2 * np.pi),
                                  ("canopy",)))
        canopy_placed.sort(key=lambda p: p[0] + p[2]["h"])

    # --- calques ----------------------------------------------------------- #
    terrain = enrich_terrain(terrain, {"grass": grass, "sand": sand}, seed, 0.10)
    terrain_g = grade_terrain(terrain, terrain_tint, terrain_strength)
    dap = fbm(H, W, 5, 4, seed + 40)
    vig = C.frame_falloff(H, W, 0.15)
    # Structure de calques de Palika : Base / River / Cliffs / Shadows /
    # Objects Under / Objects / Objects Over / Fringe, dans cet ordre.
    for sub in (list(CH.DOSSIERS.values())
                + ["frames", "01_water", "02_props", "03_canopy"]):
        os.makedirs(f"{out_dir}/{sub}", exist_ok=True)
    Image.fromarray(terrain_g, "RGB").save(
        f"{out_dir}/{CH.DOSSIERS['Base']}/f00.png")
    Image.fromarray(terrain_g, "RGB").save(f"{out_dir}/00_terrain.png")

    # Repartition des props sur ses trois calques d'objets.
    seaux = {"Cliffs": [], "Objects Under": [], "Objects": []}
    for p_ in placed:
        seaux[CH.calque_de(p_[5])].append(p_)
    # Fringe : le liseré de raccord entre terrains, dessine PAR-DESSUS tout.
    fringe = np.zeros((H, W, 4), np.uint8)
    bord = C.dilate(ground, 1) & ~ground
    if water_mask is not None:
        bord |= C.dilate(water_mask, 1) & ~water_mask
    fringe[bord] = (0, 0, 0, 70)
    Image.fromarray(fringe, "RGBA").save(f"{out_dir}/{CH.DOSSIERS['Fringe']}/f00.png")

    # Nombre de dessins distincts par calque anime, comme chez lui.
    d_river, _ = CH.dessins(N, 4)
    d_under, _ = CH.dessins(N, 4)
    d_obj, _ = CH.dessins(N, 4)
    d_over, _ = CH.dessins(N, 3)
    cache = {}

    # Eau : palette cycling a la maniere d'Explorers of Sky. Le champ d'indices
    # est fige, seules les 12 entrees de reflet changent de couleur, un pas
    # toutes les 3 frames (330 ms, la cadence relevee sur Beach Cave).
    wl = pr = None
    if water_mask is not None:
        # "sky"     : palette cycling d'Explorers of Sky, aucun pixel ne bouge
        # "halcyon" : 4 frames redessinees, a la maniere de Palika
        _wl = water_layer_hal if style_eau == "halcyon" else water_layer
        _pr = preuve_eau_hal if style_eau == "halcyon" else preuve_eau
        wl = _wl(water_mask, water_ramp or RAMP_LAKE, N, seed + 3,
                 foam_color=foam or FOAM_LAKE, calm=calm, maintien=3)
        pr = _pr(water_mask, water_ramp or RAMP_LAKE,
                 foam or FOAM_LAKE, seed=seed + 3, maintien=3, n=N)

    finals, finals_tiles = [], []
    for t in range(N):
        frame = np.zeros((H, W, 4), np.uint8)
        frame[..., :3] = terrain_g; frame[..., 3] = 255
        # --- 1 River : 4 dessins, comme sa Altere_Pond_River_Animations
        if water_mask is not None:
            alpha_paste(frame, wl[t], 0, 0)
            Image.fromarray(wl[t], "RGBA").save(
                f"{out_dir}/{CH.DOSSIERS['River']}/f{t:02d}.png")
            Image.fromarray(wl[t], "RGBA").save(f"{out_dir}/01_water/f{t:02d}.png")

        def _bucket(nom, lot, dsn, ralenti=1.0):
            """Rend un calque de props avec un nombre FIXE de dessins."""
            cle = (nom, dsn[t])
            if cle not in cache:
                buf = np.zeros((H, W, 4), np.uint8)
                # on echantillonne la houle sur le dessin, pas sur la frame :
                # 4 dessins distincts dans la boucle, pas douze.
                tt = dsn[t] * (N / max(1, max(dsn) + 1))
                for y, x, o, sw, phz, *_ in lot:
                    alpha_paste(buf, shear_sway(o["img"], sw, phz * ralenti, tt, N), y, x)
                cache[cle] = buf
            return cache[cle]

        # --- 3 Shadows : chez lui c'est un calque a part entiere
        sh = np.zeros((H, W, 4), np.uint8)
        base_sh = np.zeros((H, W, 3), np.uint8)
        base_sh[:] = 255
        tmp = np.dstack([base_sh, np.full((H, W, 1), 255, np.uint8)])
        for y, x, o, sw, phz, *_ in placed:
            contact_shadow(tmp, shear_sway(o["img"], sw, phz, t, N), y, x, 0.36)
        manque = 255 - tmp[..., 0]
        sh[..., 3] = manque
        if t == 0:
            Image.fromarray(sh, "RGBA").save(f"{out_dir}/{CH.DOSSIERS['Shadows']}/f00.png")
        alpha_paste(frame, sh, 0, 0)

        # --- 2 Cliffs, 4 Objects Under, 5 Objects
        lp = np.zeros((H, W, 4), np.uint8)
        for nom, dsn in (("Cliffs", None), ("Objects Under", d_under), ("Objects", d_obj)):
            lot = seaux[nom]
            if not lot:
                continue
            if dsn is None:
                cle = (nom, 0)
                if cle not in cache:
                    buf = np.zeros((H, W, 4), np.uint8)
                    for y, x, o, sw, phz, *_ in lot:
                        alpha_paste(buf, o["img"], y, x)
                    cache[cle] = buf
                b = cache[cle]
            else:
                b = _bucket(nom, lot, dsn)
            alpha_paste(frame, b, 0, 0)
            alpha_paste(lp, b, 0, 0)
            Image.fromarray(b, "RGBA").save(
                f"{out_dir}/{CH.DOSSIERS[nom]}/f{t:02d}.png")
        Image.fromarray(lp, "RGBA").save(f"{out_dir}/02_props/f{t:02d}.png")

        # --- 6 Objects Over : 3 dessins, sa valeur pour ce calque
        if canopy_placed:
            lc = _bucket("Objects Over", canopy_placed, d_over, ralenti=0.5)
            alpha_paste(frame, lc, 0, 0)
            Image.fromarray(lc, "RGBA").save(
                f"{out_dir}/{CH.DOSSIERS['Objects Over']}/f{t:02d}.png")
            Image.fromarray(lc, "RGBA").save(f"{out_dir}/03_canopy/f{t:02d}.png")

        # --- 7 Fringe : en dernier, par-dessus le joueur
        alpha_paste(frame, fringe, 0, 0)

        # calque lumiere : c'est un effet d'ecran, pas de la donnee de tuile.
        # -> jeu "frames" (GIF/Aseprite) avec lumiere animee,
        #    jeu "frames_tiles" (Tiled) avec la meme lumiere figee sur t=0.
        # une coulee de lave, une flaque phosphorescente : ca EMET de la lumiere,
        # ca n'en recoit pas. On repose donc le calque d'eau par-dessus le grade.
        stat = apply_light(frame.copy(), 0, N, dap, vig, grade, seed)
        if eau_emissive and wl is not None:
            alpha_paste(stat, wl[t], 0, 0)
        stat[..., :3] = C.ds_quant(stat[..., :3])
        finals_tiles.append(stat[..., :3].copy())
        frame = apply_light(frame, t, N, dap, vig, grade, seed)
        if eau_emissive and wl is not None:
            alpha_paste(frame, wl[t], 0, 0)
        frame[..., :3] = C.ds_quant(frame[..., :3])
        finals.append(frame[..., :3].copy())

    # --- palette finale : la ligne de l'eau est RESERVEE ------------------- #
    # Le DS attribue une palette de 16 couleurs par tuile 8x8 ; l'eau a la
    # sienne. Quantifier toute l'image d'un bloc ecrasait les bleus sous le
    # sable et faisait virer les reflets au jaune. On protege donc les couleurs
    # de l'eau (elles sont peu nombreuses et connues d'avance) et on ne
    # median-cut que le reste.
    pal_eau = np.zeros((0, 3), np.uint8)
    if wl is not None:
        tous = np.concatenate([f[..., :3][f[..., 3] > 0] for f in wl], 0)
        pal_eau = np.unique(C.ds_quant(tous.reshape(1, -1, 3)).reshape(-1, 3), axis=0)
    reste = max(16, 64 - len(pal_eau))
    src = finals[0].copy()
    if wl is not None:
        # on retire l'eau du calcul pour ne pas lui depenser de slots en double
        trou = wl[0][..., 3] > 0
        if (~trou).any():
            src[trou] = np.median(src[~trou].reshape(-1, 3), 0).astype(np.uint8)
    ref = Image.fromarray(src, "RGB").quantize(colors=reste, method=Image.MEDIANCUT,
                                               dither=Image.Dither.NONE).convert("RGB")
    pal = palette_of(np.array(ref))
    if len(pal_eau):
        pal = np.unique(np.concatenate([pal_eau, pal], 0), axis=0)
    lut = build_lut(pal)
    imgs = []
    for t, f in enumerate(finals):
        im = Image.fromarray(snap(f, pal, lut).astype(np.uint8), "RGB")
        im.save(f"{out_dir}/frames/f{t:02d}.png"); imgs.append(im)
    os.makedirs(f"{out_dir}/frames_tiles", exist_ok=True)
    for t, f in enumerate(finals_tiles):
        Image.fromarray(snap(f, pal, lut).astype(np.uint8), "RGB").save(
            f"{out_dir}/frames_tiles/f{t:02d}.png")
    gif = [im.quantize(colors=len(pal), method=Image.MEDIANCUT, dither=Image.Dither.NONE)
           for im in imgs]
    gif[0].save(f"{out_dir}/{zone}.gif", save_all=True, append_images=gif[1:],
                duration=MS, loop=0, optimize=True, disposal=1)

    # --- planches par calque, a sa mise en page : K dessins bout a bout ----- #
    dossier_sheets = f"pmdo/{zone}/sheets"
    planches, compte, animes = {}, {}, {}
    for nom, ordre, k in CH.CALQUES:
        d = f"{out_dir}/{CH.DOSSIERS[nom]}"
        fs = sorted(glob.glob(f"{d}/*.png"))
        if not fs:
            continue
        idx, _ = CH.dessins(N, k)
        vus, ims = [], []
        for t, i in enumerate(idx):
            if i in vus or t >= len(fs):
                continue
            vus.append(i)
            ims.append(np.array(Image.open(fs[min(t, len(fs) - 1)]).convert("RGBA")))
        if len(fs) == 1:
            ims = [np.array(Image.open(fs[0]).convert("RGBA"))]
        chemin, larg, per = CH.ecrire_planche(zone, nom, ims, dossier_sheets)
        planches[nom] = dict(sheet=os.path.basename(chemin), periode=per,
                             dessins=len(ims), largeur=larg)
        a0 = ims[0]
        occ = (a0[..., 3] > 8) if a0.shape[2] == 4 else np.ones(a0.shape[:2], bool)
        tw = 8
        gh, gw = H // tw, W // tw

        def _cases(m):
            return m[:gh * tw, :gw * tw].reshape(gh, tw, gw, tw).any((1, 3))

        compte[nom] = int(_cases(occ).sum())
        # Une tuile n'est "animee" que si elle CHANGE reellement d'un dessin a
        # l'autre. Chez lui, Objects pose 4 604 tuiles dont seulement 592
        # bougent : la plupart des props sont immobiles.
        bouge = np.zeros((H, W), bool)
        for a in ims[1:]:
            bouge |= (a != a0).any(-1)
        animes[nom] = int(_cases(bouge).sum()) if len(ims) > 1 else 0

    man = dict(zone=zone, size=[W, H], tile=24, frames=N, frame_ms=MS,
               calques_halcyon=CH.table(compte, animes, planches, N),
               palette=int(len(pal)), grade=grade,
               layers=[
                 dict(order=0, name="terrain", file="00_terrain.png", animated=False),
                 dict(order=1, name="water", dir="01_water",
                      animated=water_mask is not None,
                      technique=("palette cycling EoS : indices figes, 16 entrees "
                                 "(3 nuances plates + 12 reflets cycles + ecume), "
                                 "tramage ordonne 4x4, un pas toutes les 330 ms"),
                      palette_animee=pr),
                 dict(order=2, name="props", dir="02_props", animated=True,
                      technique="cisaillement vertical, base fixe"),
                 dict(order=3, name="canopy", dir="03_canopy",
                      animated=bool(canopy_placed),
                      technique="cisaillement lent, phase decalee"),
                 dict(order=4, name="light", animated=True,
                      technique="taches de bruit derivantes + vignette",
                      grades=list(LIGHT_GRADES)),
               ],
               counts=dict(props=len(placed), canopy=len(canopy_placed),
                           water_px=int(water_mask.sum()) if water_mask is not None else 0))
    json.dump(man, open(f"{out_dir}/manifest.json", "w"), indent=1)
    return man


# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    m = render(
        "jungle_clairiere", "layers/src/jungle_terrain.png",
        "layers/cut/jungle_props_sheet", "layers/tags/jungle_props_sheet.json",
        "layers/cut/jungle_canopy_sheet",
        rules=[
            dict(cats=["bush", "fern"], surface="midband", count=26, cap=6, min_dist=18, sway=2),
            dict(cats=["fern"],   surface="inner",  count=9,  cap=4, min_dist=34, sway=2),
            dict(cats=["bush"],   surface="grass",  count=7,  cap=4, min_dist=40, sway=2),
            dict(cats=["rock"],   surface="inner",  count=6,  cap=3, min_dist=44, sway=0),
            dict(cats=["flower"], surface="grass",  count=9,  cap=5, min_dist=26, sway=2),
            dict(cats=["flower"], surface="sand",   count=2,  cap=2, min_dist=30, sway=2),
        ],
        terrain_tint="#08190f", terrain_strength=0.55, seed=11)
    print("jungle", m["counts"])

    m = render(
        "lac_foret", "layers/src/lac_terrain.png",
        "layers/cut/lac_props_sheet", "layers/tags/lac_props_sheet.json", None,
        rules=[
            dict(cats=["jetty"],   surface="shore_bottom", count=1,  cap=1, sway=0),
            dict(cats=["lilies"],  surface="water",  count=17, cap=2, min_dist=22, sway=1),
            dict(cats=["reeds"],   surface="shore",  count=15, cap=4, min_dist=20, sway=2),
            dict(cats=["rock"],    surface="shore",  count=5,  cap=5, min_dist=40, sway=0),
            dict(cats=["conifer"], surface="outer",  count=9,  cap=6, min_dist=42, sway=1),
            dict(cats=["reeds"],   surface="outer",  count=6,  cap=4, min_dist=30, sway=2),
        ],
        water_ramp=RAMP_LAKE, foam=FOAM_LAKE, calm=0.85,
        terrain_tint="#0c1a12", terrain_strength=0.38, seed=23)
    print("lac", m["counts"])
