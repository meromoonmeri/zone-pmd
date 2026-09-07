"""
build_zones18.py — reprise des 18 zones encore aplaties avec le pipeline par calques.

Les 10 planches d'objets sont mutualisees par famille de biome : une zone pioche
dans une ou plusieurs feuilles. Seul le TERRAIN est propre a chaque zone.

Etat : TAGS et ZONES sont complets et valides. Il manque les terrains nus
(layers/src/<zone>_terrain.png) — un par zone, generes par vagues de 10.
Lancer :  python3 build_zones18.py            (toutes les zones pretes)
          python3 build_zones18.py foret_automne oasis_dunes   (au choix)
"""
import sys, os, json, glob, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image

import build_layered as B
from build_zones4 import export_tools, cool_path

# --------------------------------------------------------------------------- #
# Catalogues mutualises. Index releves sur index_lot1.png / index_lot2.png.
# --------------------------------------------------------------------------- #
TAGS = {
 "automne_props_sheet": {
    "tree":   [1, 4, 6, 7, 13], "bush": [0, 3, 11], "log": [2, 10, 12],
    "stump":  [14], "rock": [9], "leaves": [5, 8, 15, 16, 17, 18]},
 "bambou_props_sheet": {
    "bamboo": [0, 3, 5, 6, 7, 9, 10, 11], "stump": [1, 2], "fence": [4],
    "fern":   [8, 13, 16], "grass": [12, 14, 15], "stone": [17, 18],
    "lantern": [19], "shoot": [20, 21, 22]},
 "desert_props_sheet": {
    "cactus": [0, 2, 3], "rock": [1, 4, 7], "shrub": [5, 6], "skull": [8],
    "tumbleweed": [9], "branch": [10, 12], "pebble": [11, 13, 15],
    "drygrass": [14, 16], "post": [17]},
 "montagne_props_sheet": {
    "conifer": [0, 4, 8], "rock": [1, 5, 7, 11], "cairn": [2, 3],
    "plank": [6, 9], "snow": [10], "tuft": [12, 14, 15], "scree": [13, 16]},
 "glace_props_sheet": {
    "shard": [2, 3, 6], "mound": [0, 1, 8, 9, 10, 12], "icicle": [11, 14],
    "frozenbush": [5, 7], "frost": [4, 13, 16, 21], "boulder": [15, 17],
    "drift": [18, 19, 20]},
 "lave_props_sheet": {
    "rock": [0, 3], "obsidian": [1, 5, 6, 9, 10, 15], "stump": [2, 4, 13],
    "lava": [7, 8, 14], "ember": [11, 12]},
 "mousse_props_sheet": {
    "boulder": [0, 1, 9, 13], "moss": [2, 5, 7, 17], "mushroom": [3, 4, 6, 20],
    "roots": [8, 10], "stalagmite": [11, 12, 14], "fern": [15, 18, 19, 21],
    "pebble": [16, 22]},
 "ruines_props_sheet": {
    "column": [0, 3, 4, 5], "coralpillar": [6, 9], "block": [2, 7, 12],
    "arch": [10], "rock": [13, 14, 15], "seaweed": [1, 8, 11],
    "seagrass": [16, 17], "urn": [18]},
 # 6, 7, 10, 12, 13, 18 sont des MOTS peints par le generateur, pas des objets.
 "temple_props_sheet": {
    "banner": [0, 3], "statue": [1, 4], "brazier": [2, 5], "urn": [8, 11],
    "pillar": [9, 14, 15], "tile": [16, 17, 19], "coins": [20, 22],
    "altar": [21]},
 "corail_props_sheet": {
    "coral": [0, 3, 6, 11], "kelp": [2, 4], "shell": [1, 5, 8, 13, 15, 21],
    "rock": [7, 10, 14, 18, 19], "starfish": [12, 16], "barnacle": [9, 17],
    "driftwood": [20]},
}
REJET_TEMPLE = [6, 7, 10, 12, 13, 18]

# --------------------------------------------------------------------------- #
# Rampes d'eau : (tons du plus profond au plus clair, ecume, calme)
# --------------------------------------------------------------------------- #
RAMPS = {
 "cascade":  (["#123c52", "#17567a", "#1e73a0", "#2a93c0", "#48b2d6", "#86d9ea"], "#f2fdff", 1.35),
 "lac":      (["#123044", "#164a68", "#1c6690", "#2585b2", "#3aa5cc", "#67c9e0"], "#e6f9ff", 0.80),
 "mer":      (["#0a3a5e", "#0f4d76", "#146390", "#1b7daa", "#2a9cc2", "#45b9d6", "#7fd8e4"], "#eaf8ff", 1.10),
 "oasis":    (["#0f4a4a", "#146a66", "#1b8a82", "#25a89a", "#3ec6b4", "#6fe2d0"], "#e2fff8", 0.70),
 "lave":     (["#3a0a06", "#66150a", "#96280c", "#c74a10", "#e8781a", "#ffb43a"], "#ffe08a", 0.55),
 "souterrain": (["#0a1d3a", "#0e2a4f", "#123a68", "#184e85", "#2166a4", "#2f83c4"], "#9fe0ff", 0.75),
 "glace":    (["#123a5e", "#1a5480", "#2571a4", "#3a92c2", "#63b4da", "#9ad8ee"], "#f4fdff", 0.35),
 "jungle":   (["#12454f", "#176070", "#1d7b8c", "#2699a6", "#37b6bd", "#59d0cf"], "#d9f6f2", 0.95),
}

CUT = "layers/cut"
JUNGLE_CANOPY = f"{CUT}/jungle_canopy_sheet"

# --------------------------------------------------------------------------- #
# Les 18 zones. `sheets` = feuilles piochees (la 1re donne le nom du fichier de
# tags fusionne). `grade` = jour / crepuscule / nuit.
# --------------------------------------------------------------------------- #
# L'audit d'echelle sortait 3 a 5 % d'occupation du decor pour une cible de
# 18 a 45 %, et une largeur locale de 3 a 5 cases pour une cible de 1 a 3 : on
# marchait cinq cases sans que rien ne change a l'ecran. On monte donc la
# densite d'un coup, en un seul endroit.
DENSITE = 1.35


def R(cats, surface, count, cap=4, min_dist=30, sway=0):
    return dict(cats=cats, surface=surface,
                count=max(1, round(count * DENSITE)),
                cap=max(1, round(cap * DENSITE)),
                min_dist=max(12, round(min_dist / (DENSITE ** 0.5))),
                sway=sway)

ZONES = {
 # Zone demandee : sentier qui monte du sud vers un bassin au nord, rive animee.
 # Pas de canopee en cadre : elle boucherait l'entree sud du sentier, qui doit
 # rester une entree jouable pour PMDO.
 "bassin_sentier": dict(
    sheets=["lac_props_sheet", "prairie_props_sheet"], canopy=None, eau="lac",
    tint="#12301c", strength=0.44, grade="jour", seed=1019,
    rules=[R(["reeds"], "shore", 18, 6, 20, 2), R(["lilies"], "water", 14, 5, 26, 1),
           R(["conifer"], "midband", 6, 3, 52, 1), R(["tree"], "midband", 8, 3, 46, 2),
           R(["rock"], "shore", 9, 4, 32), R(["stone"], "water", 3, 2, 34),
           R(["flower"], "ground", 16, 5, 22, 2), R(["grass"], "ground", 14, 6, 22, 2),
           R(["jetty"], "shore", 1, 1)]),

 # --- Demande : sommet, pied de montagne, et des entrees de donjon ---------- #
 "pied_montagne": dict(
    sheets=["montagne_props_sheet", "prairie_props_sheet", "pic_tufts_sheet"],
    canopy=None, eau="cascade", tint="#172a24", strength=0.42, grade="jour", seed=1020,
    rules=[R(["conifer"], "midband", 10, 3, 44, 1), R(["scree"], "midband", 12, 4, 30),
           R(["rock"], "ground", 14, 4, 32), R(["tree"], "ground", 7, 3, 46, 2),
           R(["tuft"], "ground", 18, 6, 22, 2), R(["grass"], "ground", 16, 6, 22, 2),
           R(["flower"], "ground", 12, 5, 24, 2), R(["stone"], "shore", 8, 4, 26)]),

 "entree_grotte": dict(
    sheets=["mousse_props_sheet", "montagne_props_sheet"], canopy=None, eau=None,
    tint="#16241e", strength=0.46, grade="jour", seed=1021,
    rules=[R(["boulder"], "midband", 9, 3, 42), R(["stalagmite"], "midband", 7, 3, 38),
           R(["rock"], "ground", 14, 4, 30), R(["fern"], "ground", 16, 5, 24, 2),
           R(["moss"], "ground", 14, 5, 22), R(["mushroom"], "ground", 10, 4, 24),
           R(["pebble"], "ground", 12, 5, 22), R(["tuft"], "ground", 12, 5, 24, 2)]),

 "entree_ruines": dict(
    sheets=["ruines_props_sheet", "temple_props_sheet", "prairie_props_sheet"],
    canopy=None, eau=None, tint="#2a2a1e", strength=0.30, grade="jour", seed=1022,
    rules=[R(["column"], "midband", 8, 3, 46), R(["arch"], "midband", 4, 2, 60),
           R(["block"], "ground", 9, 3, 34), R(["urn"], "ground", 3, 2, 46),
           R(["pillar"], "midband", 4, 2, 56), R(["rock"], "ground", 10, 4, 28),
           R(["grass"], "ground", 18, 6, 20, 2), R(["flower"], "ground", 10, 4, 24, 2)]),

 "entree_arbre": dict(
    sheets=["automne_props_sheet", "mousse_props_sheet"], canopy=None, eau=None,
    tint="#1d2612", strength=0.48, grade="jour", seed=1023,
    rules=[R(["bush"], "midband", 7, 3, 44, 2), R(["stump"], "ground", 5, 2, 46),
           R(["log"], "ground", 7, 3, 40), R(["roots"], "ground", 8, 3, 34),
           R(["fern"], "ground", 16, 5, 22, 2), R(["moss"], "ground", 14, 5, 22),
           R(["mushroom"], "ground", 12, 4, 22), R(["leaves"], "ground", 7, 3, 30, 1),
           R(["rock"], "ground", 9, 4, 28)]),

 "entree_source": dict(
    sheets=["temple_props_sheet", "lac_props_sheet", "prairie_props_sheet"],
    canopy=None, eau="lac", tint="#1a2632", strength=0.36, grade="jour", seed=1024,
    # pas de "tile" : dans temple_props_sheet ce sont des plaques de bois, elles
    # flottaient comme des cartons poses sur la terrasse.
    rules=[R(["pillar"], "midband", 5, 2, 52), R(["brazier"], "ground", 5, 2, 44),
           R(["urn"], "ground", 3, 2, 44),
           R(["lilies"], "water", 8, 4, 24, 1), R(["reeds"], "shore", 10, 4, 22, 2),
           R(["grass"], "ground", 16, 6, 22, 2), R(["flower"], "ground", 12, 5, 22, 2)]),

 "jungle_clairiere": dict(
    sheets=["jungle_props_sheet"], canopy=JUNGLE_CANOPY, eau="jungle",
    tint="#123018", strength=0.50, grade="jour", seed=1001,
    rules=[R(["fern"], "ground", 14, 5, 24, 2), R(["bush"], "midband", 10, 4, 30, 2),
           R(["rock"], "ground", 8, 4, 36), R(["flower"], "ground", 12, 5, 22, 2)]),

 "champ_fleurs": dict(
    sheets=["pic_flowers_sheet", "pic_tufts_sheet"], canopy=None, eau=None,
    tint="#1a3a14", strength=0.36, grade="jour", seed=1002,
    rules=[R(["flower"], "ground", 46, 12, 18, 2), R(["tuft"], "ground", 34, 12, 18, 2)]),

 "foret_automne": dict(
    sheets=["automne_props_sheet"], canopy=JUNGLE_CANOPY, eau=None,
    tint="#2a1a0c", strength=0.48, grade="crepuscule", seed=1003,
    rules=[R(["tree"], "midband", 14, 4, 42, 2), R(["bush"], "ground", 12, 5, 28, 2),
           R(["leaves"], "ground", 22, 6, 20), R(["log"], "ground", 4, 2, 60),
           R(["stump"], "ground", 3, 2, 70), R(["rock"], "ground", 5, 3, 44)]),

 "foret_bambous": dict(
    sheets=["bambou_props_sheet"], canopy=None, eau=None,
    tint="#12280f", strength=0.44, grade="jour", seed=1004,
    rules=[R(["bamboo"], "midband", 26, 6, 22, 3), R(["shoot"], "ground", 10, 4, 26, 2),
           R(["fern"], "ground", 12, 4, 26, 2), R(["grass"], "ground", 14, 6, 22, 2),
           R(["stone"], "ground", 6, 3, 40), R(["stump"], "ground", 4, 2, 50),
           R(["lantern"], "ground", 1, 1), R(["fence"], "midband", 2, 1, 90)]),

 "foret_nocturne": dict(
    sheets=["jungle_props_sheet"], canopy=JUNGLE_CANOPY, eau=None,
    tint="#0a1424", strength=0.62, grade="nuit", seed=1005,
    rules=[R(["fern"], "ground", 12, 5, 26, 2), R(["bush"], "midband", 12, 4, 30, 2),
           R(["rock"], "ground", 8, 4, 36), R(["flower"], "ground", 14, 5, 22, 2)]),

 "cascade_foret": dict(
    sheets=["jungle_props_sheet", "mousse_props_sheet"], canopy=JUNGLE_CANOPY, eau="cascade",
    tint="#0f2a20", strength=0.50, grade="jour", seed=1006,
    rules=[R(["fern"], "ground", 12, 5, 26, 2), R(["moss"], "shore", 10, 4, 26),
           R(["boulder"], "shore", 8, 3, 38), R(["rock"], "water", 5, 3, 30),
           R(["flower"], "ground", 8, 4, 24, 2)]),

 "lac_foret": dict(
    sheets=["lac_props_sheet"], canopy=JUNGLE_CANOPY, eau="lac",
    tint="#102c26", strength=0.46, grade="jour", seed=1007,
    rules=[R(["reeds"], "shore", 16, 6, 22, 2), R(["lilies"], "water", 20, 5, 26, 1),
           R(["conifer"], "midband", 8, 3, 46, 1), R(["rock"], "shore", 6, 3, 38),
           R(["jetty"], "shore", 1, 1)]),

 "falaise_cotiere": dict(
    sheets=["plage_props_sheet", "pic_cliffs_sheet"], canopy=None, eau="mer",
    tint="#123044", strength=0.44, grade="jour", seed=1008,
    rules=[R(["cliff"], "midband", 9, 3, 54), R(["rock"], "shore", 9, 4, 34),
           R(["grass"], "ground", 16, 6, 24, 2), R(["shell"], "ground", 6, 3, 30),
           R(["palm"], "ground", 5, 3, 44, 2)]),

 "grottes_marines": dict(
    sheets=["corail_props_sheet"], canopy=None, eau="souterrain",
    tint="#08182c", strength=0.56, grade="nuit", seed=1009,
    rules=[R(["coral"], "shore", 12, 4, 28, 1), R(["rock"], "ground", 12, 4, 34),
           R(["shell"], "ground", 10, 4, 28), R(["kelp"], "water", 8, 4, 30, 2),
           R(["starfish"], "ground", 5, 3, 34), R(["barnacle"], "shore", 6, 3, 30),
           R(["driftwood"], "ground", 2, 1, 80)]),

 "canyon_desert": dict(
    sheets=["desert_props_sheet"], canopy=None, eau=None,
    tint="#3a2010", strength=0.40, grade="crepuscule", seed=1010,
    rules=[R(["rock"], "midband", 12, 4, 44), R(["cactus"], "ground", 9, 4, 38),
           R(["shrub"], "ground", 10, 4, 30), R(["drygrass"], "ground", 12, 5, 24, 2),
           R(["pebble"], "ground", 10, 4, 26), R(["skull"], "ground", 1, 1),
           R(["tumbleweed"], "ground", 2, 2, 70, 2), R(["branch"], "ground", 4, 2, 50)]),

 "sommet_montagne": dict(
    sheets=["montagne_props_sheet", "pic_cliffs_sheet"], canopy=None, eau=None,
    tint="#1a2434", strength=0.46, grade="jour", seed=1011,
    # pas de prop "cliff" ici : ce sont les tours a chapeau d'herbe du pic
    # fleuri, absurdes sur un sommet mineral. Roche, eboulis, neige, cairns.
    rules=[R(["conifer"], "midband", 3, 2, 64, 1),
           R(["rock"], "ground", 20, 5, 30), R(["snow"], "ground", 16, 5, 28),
           R(["scree"], "ground", 18, 6, 24),
           R(["tuft"], "ground", 12, 5, 24, 2), R(["cairn"], "ground", 3, 2, 60),
           R(["scree"], "ground", 8, 4, 28)]),

 "oasis_dunes": dict(
    sheets=["desert_props_sheet", "plage_props_sheet"], canopy=None, eau="oasis",
    tint="#3a2a12", strength=0.38, grade="jour", seed=1012,
    rules=[R(["palm"], "shore", 10, 4, 40, 2), R(["grass"], "shore", 12, 5, 24, 2),
           R(["rock"], "ground", 8, 4, 40), R(["shrub"], "ground", 7, 3, 32),
           R(["drygrass"], "ground", 10, 4, 26, 2), R(["pebble"], "ground", 8, 4, 28)]),

 "gorge_pont": dict(
    sheets=["montagne_props_sheet", "pic_cliffs_sheet"], canopy=None, eau="cascade",
    tint="#1c2430", strength=0.50, grade="jour", seed=1013,
    rules=[R(["cliff"], "midband", 10, 3, 52), R(["plank"], "water", 3, 2, 80),
           R(["rock"], "shore", 10, 4, 34), R(["conifer"], "midband", 6, 3, 48, 1),
           R(["tuft"], "ground", 10, 5, 24, 2), R(["scree"], "shore", 8, 4, 28)]),

 "banquise_glacier": dict(
    sheets=["glace_props_sheet"], canopy=None, eau="glace",
    tint="#16304c", strength=0.34, grade="jour", seed=1014,
    rules=[R(["shard"], "midband", 10, 4, 38), R(["mound"], "ground", 14, 5, 30),
           R(["boulder"], "ground", 8, 4, 36), R(["icicle"], "midband", 6, 3, 40),
           R(["frozenbush"], "ground", 7, 3, 32, 1), R(["drift"], "ground", 8, 4, 28),
           R(["frost"], "ground", 10, 4, 24, 1)]),

 "caverne_lave": dict(
    sheets=["lave_props_sheet"], canopy=None, eau="lave",
    tint="#2a0c06", strength=0.60, grade="nuit", seed=1015, emissive=True,
    rules=[R(["rock"], "midband", 10, 4, 38), R(["obsidian"], "ground", 14, 5, 28),
           R(["stump"], "ground", 5, 3, 46), R(["lava"], "shore", 8, 4, 32),
           R(["ember"], "ground", 8, 4, 30)]),

 "grotte_moussue": dict(
    sheets=["mousse_props_sheet"], canopy=None, eau="souterrain",
    tint="#0e1c12", strength=0.56, grade="nuit", seed=1016,
    rules=[R(["boulder"], "midband", 10, 4, 38), R(["stalagmite"], "midband", 9, 4, 34),
           R(["mushroom"], "ground", 12, 4, 28, 1), R(["moss"], "ground", 14, 5, 24),
           R(["fern"], "ground", 12, 5, 26, 2), R(["roots"], "midband", 5, 2, 50, 2),
           R(["pebble"], "ground", 8, 4, 28)]),

 "ruines_englouties": dict(
    sheets=["ruines_props_sheet", "corail_props_sheet"], canopy=None, eau="souterrain",
    tint="#0c2434", strength=0.52, grade="jour", seed=1017,
    rules=[R(["column"], "midband", 9, 3, 46), R(["coralpillar"], "midband", 4, 2, 54),
           R(["block"], "ground", 10, 4, 34), R(["arch"], "midband", 2, 1, 90),
           R(["rock"], "ground", 8, 4, 34), R(["seaweed"], "water", 10, 4, 28, 2),
           R(["seagrass"], "shore", 10, 4, 26, 2), R(["urn"], "ground", 2, 1, 70),
           R(["coral"], "water", 6, 3, 32, 1)]),

 "temple_dore": dict(
    sheets=["temple_props_sheet"], canopy=None, eau=None,
    tint="#2c1c06", strength=0.44, grade="crepuscule", seed=1018,
    rules=[R(["pillar"], "midband", 10, 4, 44), R(["brazier"], "midband", 5, 3, 50),
           R(["tile"], "ground", 10, 4, 34), R(["statue"], "midband", 4, 2, 56),
           R(["urn"], "ground", 6, 3, 34), R(["banner"], "midband", 4, 2, 60, 1),
           R(["coins"], "ground", 5, 3, 32), R(["altar"], "ground", 1, 1)]),
}


# --------------------------------------------------------------------------- #

# feuilles mono-categorie heritees de Pic Fleuri : tout l'index dans une categorie
MONO = {"pic_cliffs_sheet": "cliff", "pic_flowers_sheet": "flower",
        "pic_tufts_sheet": "tuft"}


def write_tags():
    """Ecrit un fichier de tags par feuille, plus un fichier fusionne par zone
    (les index des feuilles suivantes sont decales du nombre d'objets deja pris)."""
    os.makedirs("layers/tags", exist_ok=True)
    for sheet, t in TAGS.items():
        json.dump(t, open(f"layers/tags/{sheet}.json", "w"), indent=1)
    for sheet, cat in MONO.items():
        n = len(glob.glob(f"{CUT}/{sheet}/*.png"))
        if n:
            json.dump({cat: list(range(n))},
                      open(f"layers/tags/{sheet}.json", "w"), indent=1)


def fusion(zone, spec):
    """Concatene les catalogues des feuilles d'une zone dans un dossier unique,
    et produit le fichier de tags correspondant avec les index recales."""
    dst = f"{CUT}/_mix_{zone}"
    shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(dst)
    tags, n = {}, 0
    for sh in spec["sheets"]:
        src = f"{CUT}/{sh}"
        fs = sorted(glob.glob(f"{src}/*.png"))
        if not fs:
            raise FileNotFoundError(src)
        t = json.load(open(f"layers/tags/{sh}.json"))
        for i, p in enumerate(fs):
            shutil.copy(p, f"{dst}/obj{n + i:03d}.png")
        for cat, idx in t.items():
            tags.setdefault(cat, []).extend(i + n for i in idx)
        n += len(fs)
    tp = f"layers/tags/_mix_{zone}.json"
    json.dump(tags, open(tp, "w"), indent=1)
    return dst, tp, n


def construire(zone):
    spec = ZONES[zone]
    ter = f"layers/src/{zone}_terrain.png"
    if not os.path.exists(ter):
        return None, f"terrain manquant : {ter}"
    cut, tagp, n = fusion(zone, spec)
    ramp = foam = None
    calm = 1.0
    if spec["eau"]:
        ramp, foam, calm = RAMPS[spec["eau"]]
    m = B.render(zone, ter, cut, tagp, spec["canopy"],
                 rules=spec["rules"], water_ramp=ramp, foam=foam, calm=calm,
                 terrain_tint=spec["tint"], terrain_strength=spec["strength"],
                 grade=spec.get("grade", "jour"), seed=spec["seed"],
                 eau_emissive=spec.get("emissive", False))
    tr, av = export_tools(zone)
    return dict(compo=m["counts"], palette=m["palette"], objets_catalogue=n,
                tiled=dict(tuiles=tr["tuiles_uniques"], animees=tr["tuiles_animees"],
                           cases_animees=tr["cases_animees"]),
                aseprite=dict(calques=len(av["layers"]), cels=av["cels"])), None


if __name__ == "__main__":
    write_tags()
    demandees = sys.argv[1:] or list(ZONES)
    rap, manque = {}, []
    for z in demandees:
        r, err = construire(z)
        if err:
            manque.append(err); print("--", err); continue
        rap[z] = r
        print(f"{z:20s} props {r['compo']['props']:3d}  canopee {r['compo']['canopy']:3d}  "
              f"palette {r['palette']:3d}  tuiles {r['tiled']['tuiles']:5d}  "
              f"animees {r['tiled']['cases_animees']:3d}")
    if rap:
        os.makedirs("layers/rendu", exist_ok=True)
        json.dump(rap, open("layers/rendu/rapport_18zones.json", "w"), indent=1)
    print(f"\n{len(rap)} zone(s) construite(s), {len(manque)} terrain(s) manquant(s)")
