"""
build_arenes.py — 40 arenes de Pokemon legendaire, 10 biomes x 4 variantes.

Montage : structure de calques de Palika (Base / River / Cliffs / Shadows /
Objects Under / Objects / Objects Over / Fringe) et colorimetrie stricte de
Halcyon (sa palette de 654 couleurs, sa grille multiple de 8, 8 couleurs par
tuile de 8 px, son exposition).

Aucun Pokemon n'est represente : ce sont les LIEUX de combat, pas les
creatures. Les 40 sols sortent de 10 peintures d'arene, declinees en 4
orientations chacune, puis habillees de props, d'eclairages et de fluides
differents. Les 4 variantes d'un biome ne se ressemblent donc pas.

Usage : python3 build_arenes.py <zone...>      (ou --liste pour les enumerer)
"""
import os
import sys

from PIL import Image

import build_zones18 as BZ

R = BZ.R

# --- les 4 declinaisons d'une meme peinture d'arene ------------------------ #
# orientation, eclairage, densite relative de props, suffixe
# 4 par biome : deux vues de dessus, deux vues 3/4 (celle des ground maps PMD
# officiels, ou l'on voit la face avant des rebords et des murs).
# vue, orientation, eclairage, densite de props, suffixe
VARIANTES = [
    ("dessus", "miroir_v", "jour",       1.00, "aube"),
    ("dessus", "rot180",   "nuit",       0.70, "nuit"),
    ("34",     "identite", "crepuscule", 1.25, "crepuscule"),
    ("34",     "miroir_h", "jour",       1.50, "assaut"),
]

_TRANSFO = {
    "identite": lambda im: im,
    "miroir_h": lambda im: im.transpose(Image.FLIP_LEFT_RIGHT),
    "rot180":   lambda im: im.transpose(Image.ROTATE_180),
    "miroir_v": lambda im: im.transpose(Image.FLIP_TOP_BOTTOM),
}


def _r(cats, surface, count, cap=4, min_dist=30, sway=0, f=1.0):
    """Une regle de pose, ponderee par la densite de la variante."""
    return R(cats, surface, max(1, round(count * f)), cap, min_dist, sway)


# --- les 10 biomes --------------------------------------------------------- #
# chaque entree : le sol, les planches de props, le fluide, la teinte de grade,
# et une fabrique de regles qui prend le facteur de densite de la variante.
BIOMES = {
 "volcan": dict(
    titre="Caldeira", sheets=["lave_props_sheet", "montagne_props_sheet"],
    eau="lave", emissive=True, tint="#2a0e08", strength=0.40, canopy=None,
    regles=lambda f: [
        _r(["obsidian"], "midband", 14, 4, 30, 0, f), _r(["rock"], "ground", 16, 4, 28, 0, f),
        _r(["ember"], "shore", 12, 5, 22, 0, f),      _r(["stump"], "ground", 5, 2, 44, 0, f),
        _r(["scree"], "midband", 10, 4, 26, 0, f),    _r(["cairn"], "inner", 3, 1, 60, 0, f)]),

 "banquise": dict(
    titre="Glacier", sheets=["glace_props_sheet", "montagne_props_sheet"],
    eau="glace", emissive=False, tint="#16283c", strength=0.34, canopy=None,
    regles=lambda f: [
        _r(["shard"], "midband", 15, 5, 26, 0, f),    _r(["icicle"], "shore", 10, 4, 24, 0, f),
        _r(["mound"], "ground", 9, 3, 34, 0, f),      _r(["frost"], "ground", 16, 6, 20, 0, f),
        _r(["boulder"], "midband", 8, 3, 38, 0, f),   _r(["frozenbush"], "inner", 6, 3, 30, 1, f)]),

 "ciel": dict(
    titre="Pilier celeste", sheets=["montagne_props_sheet", "ruines_props_sheet"],
    eau="souterrain", emissive=False, tint="#1c2438", strength=0.38, canopy=None,
    regles=lambda f: [
        _r(["column"], "midband", 8, 3, 42, 0, f),    _r(["block"], "ground", 12, 4, 28, 0, f),
        _r(["arch"], "inner", 2, 1, 70, 0, f),        _r(["rock"], "ground", 12, 4, 28, 0, f),
        _r(["cairn"], "midband", 6, 2, 40, 0, f),     _r(["tuft"], "inner", 10, 5, 24, 2, f)]),

 "abysse": dict(
    titre="Fosse engloutie", sheets=["corail_props_sheet", "ruines_props_sheet"],
    eau="mer", emissive=False, tint="#0c2436", strength=0.46, canopy=None,
    regles=lambda f: [
        _r(["coral"], "midband", 14, 5, 26, 1, f),    _r(["kelp"], "shore", 12, 5, 24, 2, f),
        _r(["coralpillar"], "ground", 7, 3, 40, 0, f), _r(["shell"], "ground", 12, 5, 22, 0, f),
        _r(["starfish"], "inner", 8, 4, 26, 0, f),    _r(["barnacle"], "shore", 9, 4, 24, 0, f),
        _r(["seagrass"], "water", 8, 4, 26, 2, f)]),

 "cristal": dict(
    titre="Chambre de cristal", sheets=["cristal_props_sheet", "mousse_props_sheet"],
    eau="souterrain", emissive=False, tint="#1a1630", strength=0.42, canopy=None,
    regles=lambda f: [
        _r(["crystal"], "midband", 16, 5, 26, 0, f),  _r(["stalagmite"], "ground", 11, 4, 30, 0, f),
        _r(["rock"], "ground", 12, 4, 28, 0, f),      _r(["mushroom"], "inner", 9, 4, 26, 1, f),
        _r(["boulder"], "midband", 7, 3, 36, 0, f)]),

 "temple": dict(
    titre="Sanctuaire", sheets=["temple_props_sheet", "ruines_props_sheet"],
    eau=None, emissive=False, tint="#2a2a1e", strength=0.30, canopy=None,
    regles=lambda f: [
        _r(["pillar"], "midband", 10, 3, 44, 0, f),   _r(["statue"], "ground", 5, 2, 54, 0, f),
        _r(["brazier"], "inner", 6, 2, 44, 0, f),     _r(["urn"], "ground", 6, 3, 34, 0, f),
        _r(["block"], "midband", 10, 4, 30, 0, f),    _r(["altar"], "inner", 1, 1, 90, 0, f),
        _r(["banner"], "midband", 5, 2, 46, 1, f)]),

 "bosquet": dict(
    titre="Clairiere sacree", sheets=["prairie_props_sheet", "pic_flowers_sheet",
                                      "mousse_props_sheet"],
    eau="oasis", emissive=False, tint="#12301c", strength=0.44,
    canopy="layers/cut/automne_props_sheet",
    regles=lambda f: [
        _r(["tree"], "midband", 9, 3, 46, 2, f),      _r(["flower"], "ground", 22, 6, 20, 2, f),
        _r(["grass"], "ground", 18, 6, 20, 2, f),     _r(["moss"], "ground", 12, 5, 24, 0, f),
        _r(["mushroom"], "inner", 8, 4, 26, 1, f),    _r(["stone"], "midband", 8, 3, 34, 0, f)]),

 "desert": dict(
    titre="Bassin aride", sheets=["desert_props_sheet", "ruines_props_sheet"],
    eau="oasis", emissive=False, tint="#2c2010", strength=0.36, canopy=None,
    regles=lambda f: [
        _r(["rock"], "midband", 14, 4, 28, 0, f),     _r(["cactus"], "ground", 8, 3, 38, 1, f),
        _r(["drygrass"], "ground", 14, 6, 22, 2, f),  _r(["skull"], "inner", 4, 2, 50, 0, f),
        _r(["post"], "midband", 6, 2, 42, 0, f),      _r(["pebble"], "ground", 16, 6, 20, 0, f),
        _r(["column"], "midband", 5, 2, 48, 0, f)]),

 "distorsion": dict(
    titre="Faille", sheets=["mousse_props_sheet", "ruines_props_sheet"],
    eau="jungle", emissive=True, tint="#1a1226", strength=0.50, canopy=None,
    regles=lambda f: [
        _r(["stalagmite"], "midband", 13, 4, 28, 0, f), _r(["block"], "ground", 12, 4, 28, 0, f),
        _r(["roots"], "ground", 10, 4, 26, 1, f),      _r(["boulder"], "midband", 8, 3, 36, 0, f),
        _r(["column"], "inner", 5, 2, 46, 0, f),       _r(["moss"], "ground", 12, 5, 24, 0, f)]),

 "orage": dict(
    titre="Cime foudroyee", sheets=["montagne_props_sheet", "ruines_props_sheet"],
    eau=None, emissive=False, tint="#1e2230", strength=0.44, canopy=None,
    regles=lambda f: [
        _r(["rock"], "midband", 16, 5, 26, 0, f),     _r(["scree"], "ground", 16, 6, 22, 0, f),
        _r(["cairn"], "midband", 8, 3, 36, 0, f),     _r(["block"], "ground", 9, 3, 32, 0, f),
        _r(["snow"], "inner", 7, 3, 30, 0, f),        _r(["column"], "midband", 4, 2, 52, 0, f)]),
}


RATIO = 504 / 456     # le format des zones

# Chaque arene doit avoir une ENTREE SUD CONTINUE : une chaussee qui part du
# bord bas de la carte et rejoint la plateforme sans etre coupee par la douve.
COULOIR = (0.44, 0.56)      # bornes en fraction de largeur


def _nettoyer_magenta(im):
    """Ne garde que la plus grande nappe de magenta.

    Le generateur laisse parfois un trait magenta EN TRAVERS de la plateforme
    (vu sur `arene34_orage`) : il deviendrait un trou dans le sol. On ne
    conserve que la composante connexe la plus large, celle qui entoure
    l'arene.
    """
    import numpy as np
    from scipy import ndimage
    a = np.array(im.convert("RGB"))
    mag = (a[..., 0] > 200) & (a[..., 2] > 200) & (a[..., 1] < 60)
    if not mag.any():
        return im
    lab, n = ndimage.label(mag)
    if n > 1:
        t = ndimage.sum(mag, lab, range(1, n + 1))
        garde = int(np.argmax(t)) + 1
        perdus = mag & (lab != garde)
        if perdus.any():
            # on rebouche avec la couleur voisine la plus proche
            ind = ndimage.distance_transform_edt(
                mag, return_distances=False, return_indices=True)
            a[perdus] = a[tuple(i[perdus] for i in ind)]
    return Image.fromarray(a, "RGB")


def _chaussee(im, bornes=COULOIR):
    """Taille une chaussee du bord SUD jusqu'a la plateforme.

    On remplit le magenta de la bande centrale avec la texture de la
    plateforme elle-meme, prelevee juste au-dessus de son bord bas : la
    chaussee est donc du meme materiau que l'arene, et le joueur peut entrer
    par le sud sans traverser la lave ou l'eau.
    """
    import numpy as np
    a = np.array(im.convert("RGB"))
    h, w = a.shape[:2]
    mag = (a[..., 0] > 200) & (a[..., 2] > 200) & (a[..., 1] < 60)
    xa, xb = int(bornes[0] * w), int(bornes[1] * w)
    bande = mag[:, xa:xb]
    if bande[-1].mean() < 0.10:
        return im, False           # le sud est deja ouvert           # deja continu, rien a tailler
    plein = ~bande
    if not plein.any():
        return im, False
    # On cherche la derniere ligne REELLEMENT pleine, pas celle ou traine un
    # pixel d'antialiasing : sur l'arene celeste, un seul pixel en bas de bande
    # faisait croire que la chaussee existait deja, et l'acces restait ferme.
    frac = plein.mean(1)
    lignes = np.flatnonzero(frac >= 0.60)
    if len(lignes) == 0:
        lignes = np.flatnonzero(frac >= 0.25)
    if len(lignes) == 0:
        return im, False
    y_bas = int(lignes.max())      # bord bas de la plateforme dans la bande
    k = max(8, min(56, y_bas))
    motif = a[y_bas - k + 1:y_bas + 1, xa:xb].copy()
    if motif.shape[0] == 0:
        return im, False
    y = y_bas + 1
    while y < h:
        n = min(k, h - y)
        cible = a[y:y + n, xa:xb]
        m = mag[y:y + n, xa:xb]
        cible[m] = motif[:n][m]
        y += n
    # deux liserés sombres pour que la chaussee se lise comme un ouvrage
    for dx in (0, (xb - xa) - 1):
        col = a[y_bas:, xa + dx]
        a[y_bas:, xa + dx] = (col.astype(np.int16) * 0.62).astype(np.uint8)
    return Image.fromarray(a, "RGB"), True


def _terrain(biome, vue, transfo):
    """Le sol d'une variante : la peinture du biome, nettoyee, mise au format,
    puis reorientee.

    On NE ROGNE PAS. `load_terrain` recadre au ratio avant de redimensionner ;
    sur une peinture carree il mangeait les coins — et les coins, sur une
    arene, c'est justement la douve de lave ou d'eau. On pose donc la peinture
    entiere sur une toile deja au bon ratio, remplie de magenta : la douve
    s'elargit au lieu de disparaitre.
    """
    base = "arene" if vue == "dessus" else "arene34"
    src = f"layers/src/{base}_{biome}_terrain.png"
    dst = f"layers/src/{base}_{biome}_{transfo}_cadre_terrain.png"
    if os.path.exists(dst):
        return dst
    if not os.path.exists(src):
        # Repli : les 10 peintures en vue de dessus ont ete perdues et le
        # generateur plafonne a 10 images par tour. On prend la peinture 3/4
        # du meme biome en attendant ; des que le fichier de la bonne vue
        # revient dans layers/src, la variante repasse dessus toute seule.
        autre = "arene34" if base == "arene" else "arene"
        src = f"layers/src/{autre}_{biome}_terrain.png"
        dst = f"layers/src/{autre}_{biome}_{transfo}_cadre_terrain.png"
        if os.path.exists(dst):
            return dst
        if not os.path.exists(src):
            return f"layers/src/{base}_{biome}_terrain.png"
    im = _nettoyer_magenta(Image.open(src).convert("RGB"))
    w, h = im.size
    W2 = max(w, int(round(h * RATIO)))
    H2 = max(h, int(round(w / RATIO)))
    toile = Image.new("RGB", (W2, H2), (255, 0, 255))
    toile.paste(im, ((W2 - w) // 2, (H2 - h) // 2))
    # on oriente D'ABORD, on taille la chaussee ENSUITE : l'entree doit tomber
    # au sud quelle que soit la rotation appliquee a la peinture.
    toile = _TRANSFO[transfo](toile)
    toile, _ = _chaussee(toile)
    toile.save(dst)
    return dst


def construire_specs():
    """Les 40 specs, injectees dans build_zones18.ZONES."""
    specs = {}
    for bi, (biome, b) in enumerate(BIOMES.items()):
        for vi, (vue, transfo, grade, dens, suffixe) in enumerate(VARIANTES):
            nom = f"arene_{biome}_{suffixe}"
            specs[nom] = dict(
                sheets=b["sheets"], canopy=b["canopy"], eau=b["eau"],
                tint=b["tint"], strength=b["strength"], grade=grade,
                emissive=b["emissive"],
                seed=7000 + bi * 40 + vi * 7,
                rules=b["regles"](dens),
                _terrain=_terrain(biome, vue, transfo),
                _vue=("vue de dessus" if vue == "dessus" else "vue 3/4"),
                couloir=COULOIR,
                _titre=f"{b['titre']} — {suffixe} ({vue})",
            )
    return specs


def construire_specs_nues():
    """Les memes arenes, mais VIDES : aucun prop pose par moi.

    Demande explicite : c'est l'utilisateur qui posera les roches, l'herbe et
    les fleurs. On ne garde donc que ce qui est du TERRAIN — le sol, ses murs,
    la douve animee et l'entree sud — plus les ombres, qui n'existent que s'il
    y a des props, donc vides elles aussi.
    """
    specs = {}
    for bi, (biome, b) in enumerate(BIOMES.items()):
        nom = f"arene_{biome}_nu"
        specs[nom] = dict(
            sheets=b["sheets"], canopy=None, eau=b["eau"],
            tint=b["tint"], strength=b["strength"], grade="jour",
            emissive=b["emissive"], seed=9000 + bi * 13,
            rules=[],                      # <- aucun prop
            _terrain=_terrain(biome, "34", "identite"),
            _vue="vue 3/4", couloir=COULOIR, fringe_props=False,
            _titre=f"{b['titre']} — nu",
        )
    return specs


SPECS = construire_specs()
SPECS.update(construire_specs_nues())
BZ.ZONES.update(SPECS)

# `construire` cherche layers/src/<zone>_terrain.png ; on pointe le fichier
# reoriente du biome a la place.
_construire = BZ.construire


def construire(zone):
    spec = BZ.ZONES[zone]
    ter = spec.get("_terrain")
    attendu = f"layers/src/{zone}_terrain.png"
    if ter and os.path.exists(ter) and not os.path.exists(attendu):
        os.symlink(os.path.abspath(ter), attendu)
    return _construire(zone)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "--liste":
        print(f"{len(SPECS)} arenes, {len(BIOMES)} biomes x {len(VARIANTES)} variantes\n")
        for biome, b in BIOMES.items():
            noms = [f"arene_{biome}_{v[3]}" for v in VARIANTES]
            print(f"  {b['titre']:22s} {' '.join(n.split('_', 2)[2] for n in noms)}")
            print(f"    {'':22s} {noms[0]} ...")
        sys.exit(0)
    ok = 0
    for z in args:
        if z not in BZ.ZONES:
            print(f"inconnue : {z}")
            continue
        r, err = construire(z)
        if err:
            print(f"{z:30s} {err}")
            continue
        ok += 1
        print(f"{z:30s} props {r['compo']['props']:3d}  palette {r['palette']:3d}  "
              f"tuiles {r['tiled']['tuiles']:5d}  animees {r['tiled']['cases_animees']:3d}")
    print(f"\n{ok} arene(s) construite(s)")
