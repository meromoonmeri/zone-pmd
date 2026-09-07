"""
pmdo/export_pmdo.py — sortie PMDO / RogueEssence d'une zone montee en calques.

Ce que le moteur attend (releve dans ANALYSE_ECHELLE.md et dans rsread.py) :
  * une ground map est decoupee sur une grille de **8 px** ;
  * la collision (`obstacles`) est declaree cellule par cellule sur cette grille ;
  * l'unite de lecture reste la case de 24 px = 3 x 3 cellules ;
  * le viewport logique est 320 x 240 px.

Aucun pixel n'est rescale ici : la toile est deja un multiple de 8 ET de 24, donc
la grille 8 px tombe pile sur l'art existant. On ajoute la couche de donnees qui
manquait, pas une reinterpretation du visuel.

Produit par zone, dans pmdo/<zone>/ :
  fond.png             composite frame 0 (fond de ground map)
  frames/              les 12 frames du composite
  calques/             un PNG par calque du pipeline
  obstacles.json       grille 8 px : '.' libre, '#' bloque, '~' eau
  obstacles.png        la meme grille en surimpression, pour relecture humaine
  collision.png        masque 1 px par cellule (noir = libre, blanc = bloque)
  ground.json          descripteur de la carte (taille, calques, anim, entrees)
  collision.tmx / brosse_collision.tsx  carte Tiled sur cellules de 8 px, ou la
                       couche de tuiles ne contient QUE la collision (3 pinceaux :
                       libre / bloque / eau) posee sur le fond en imagelayer.
                       C'est editable a la souris et relisible par script.

Pourquoi pas de tileset graphique en 8 px : un decoupage 8 px du decor donne
23 000 a 34 000 tuiles uniques (le tramage DS ne se repete pas a cette echelle).
En PMDO une ground map n'est pas une tilemap : c'est une image de fond plus une
grille de collision. Le tileset 24 px anime, lui, reste produit dans tiled/.
"""
import os, sys, json, glob, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from PIL import Image, ImageDraw

from pmdo.audit_echelle import (CELL, TILE, VIEW, masque_obstacles, audit,
                                verdict, RENDU, ROOT)

OUT = os.path.join(ROOT, "pmdo")



def strip(fichiers, sortie):
    """Empile n frames en une bande horizontale (1 fichier au lieu de n)."""
    ims = [Image.open(p).convert("RGBA") for p in fichiers]
    w, h = ims[0].size
    band = Image.new("RGBA", (w * len(ims), h), (0, 0, 0, 0))
    for i, im in enumerate(ims):
        band.paste(im, (i * w, 0))
    band.save(sortie)
    return dict(fichier=os.path.basename(sortie), frames=len(ims), frame=[w, h])


BROSSE = [("libre", (0, 0, 0, 0)), ("bloque", (220, 40, 70, 150)),
          ("eau", (60, 140, 255, 150))]


def collision_tmx(zone, bloc, eau, dossier):
    """Carte Tiled 8 px : le fond en imagelayer, la collision en couche de tuiles.

    Trois pinceaux seulement. On peint la collision a la souris dans Tiled, on
    relit le .tmx par script, et la grille reste exactement celle de PMDO.
    """
    gh, gw = bloc.shape
    # tileset : 3 cases de 8 px, cote a cote
    ts = Image.new("RGBA", (CELL * 3, CELL), (0, 0, 0, 0))
    for i, (_, c) in enumerate(BROSSE):
        ts.paste(Image.new("RGBA", (CELL, CELL), c), (i * CELL, 0))
    ts.save(f"{dossier}/brosse_collision.png")

    tsx = ['<?xml version="1.0" encoding="UTF-8"?>',
           f'<tileset version="1.10" tiledversion="1.10.2" name="brosse_collision" '
           f'tilewidth="{CELL}" tileheight="{CELL}" tilecount="3" columns="3">',
           f' <image source="brosse_collision.png" width="{CELL * 3}" height="{CELL}"/>']
    for i, (nom, _) in enumerate(BROSSE):
        tsx.append(f' <tile id="{i}"><properties>'
                   f'<property name="collision" value="{nom}"/></properties></tile>')
    tsx.append('</tileset>')
    open(f"{dossier}/brosse_collision.tsx", "w").write("\n".join(tsx))

    rows = []
    for y in range(gh):
        rows.append(",".join(str(3 if eau[y, x] else (2 if bloc[y, x] else 1))
                             for x in range(gw)))
    W, H = gw * CELL, gh * CELL
    tmx = ['<?xml version="1.0" encoding="UTF-8"?>',
           f'<map version="1.10" tiledversion="1.10.2" orientation="orthogonal" '
           f'renderorder="right-down" width="{gw}" height="{gh}" '
           f'tilewidth="{CELL}" tileheight="{CELL}" infinite="0" nextlayerid="4" nextobjectid="1">',
           ' <properties>',
           f'  <property name="moteur" value="RogueEssence / PMDO"/>',
           f'  <property name="case_lecture_px" type="int" value="{TILE}"/>',
           f'  <property name="viewport" value="{VIEW[0]}x{VIEW[1]}"/>',
           ' </properties>',
           ' <tileset firstgid="1" source="brosse_collision.tsx"/>',
           f' <imagelayer id="1" name="fond">',
           f'  <image source="fond.png" width="{W}" height="{H}"/>',
           ' </imagelayer>',
           f' <layer id="2" name="collision_8px" width="{gw}" height="{gh}" opacity="0.55">',
           '  <data encoding="csv">',
           ",\n".join(rows),
           '  </data>',
           ' </layer>',
           '</map>']
    open(f"{dossier}/collision.tmx", "w").write("\n".join(tmx))
    return dict(tmx="collision.tmx", tsx="brosse_collision.tsx",
                cellules=[gw, gh], pinceaux=[n for n, _ in BROSSE])


def ecrire_obstacles(zone, bloc, eau, dossier):
    gh, gw = bloc.shape
    lignes = []
    for y in range(gh):
        lignes.append("".join("~" if eau[y, x] else ("#" if bloc[y, x] else ".")
                              for x in range(gw)))
    json.dump(dict(zone=zone, cellule=CELL, largeur=gw, hauteur=gh,
                   legende={".": "libre", "#": "bloque", "~": "eau (bloque, nageable)"},
                   grille=lignes),
              open(f"{dossier}/obstacles.json", "w"), indent=1)
    with open(f"{dossier}/obstacles.txt", "w") as f:
        f.write("\n".join(lignes) + "\n")

    m = Image.fromarray((bloc * 255).astype(np.uint8), "L")
    m.save(f"{dossier}/collision.png")
    return lignes


def apercu_obstacles(zone, bloc, eau, fond, dossier):
    W, H = fond.size
    im = fond.convert("RGBA").copy()
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    gh, gw = bloc.shape
    for y in range(gh):
        for x in range(gw):
            if eau[y, x]:
                c = (70, 150, 255, 95)
            elif bloc[y, x]:
                c = (255, 60, 90, 95)
            else:
                continue
            d.rectangle([x * CELL, y * CELL, x * CELL + CELL - 1, y * CELL + CELL - 1], fill=c)
    for x in range(0, W + 1, CELL):
        d.line([x, 0, x, H], fill=(255, 255, 255, 26))
    for y in range(0, H + 1, CELL):
        d.line([0, y, W, y], fill=(255, 255, 255, 26))
    for x in range(0, W + 1, TILE):
        d.line([x, 0, x, H], fill=(255, 255, 255, 70))
    for y in range(0, H + 1, TILE):
        d.line([0, y, W, y], fill=(255, 255, 255, 70))
    im.alpha_composite(ov)
    im.convert("RGB").save(f"{dossier}/obstacles.png")


def entrees(bloc, eau):
    """Points d'apparition : la cellule libre la plus proche de chaque bord,
    prise au milieu du cote. Une bordure entierement fermee (canopee qui fait le
    tour) n'empeche pas d'entrer : le marqueur recule simplement vers l'interieur.
    """
    gh, gw = bloc.shape
    libre = ~bloc
    out = {}
    milieu_x, milieu_y = gw / 2, gh / 2

    def choisir(cands):
        if not cands:
            return None
        x, y, prof = min(cands, key=lambda c: (c[2], abs(c[0] - milieu_x) + abs(c[1] - milieu_y)))
        return dict(cellule=[int(x), int(y)],
                    px=[int(x) * CELL + CELL // 2, int(y) * CELL + CELL // 2],
                    profondeur_cellules=int(prof),
                    sur_bordure=bool(prof == 0))

    bande = max(3, gw // 6)
    for cote in ("nord", "sud", "ouest", "est"):
        c = []
        if cote in ("nord", "sud"):
            xs = range(max(0, gw // 2 - bande), min(gw, gw // 2 + bande + 1))
            for x in xs:
                col = np.nonzero(libre[:, x])[0]
                if not col.size:
                    continue
                y = col.min() if cote == "nord" else col.max()
                c.append((x, y, y if cote == "nord" else gh - 1 - y))
        else:
            ys = range(max(0, gh // 2 - bande), min(gh, gh // 2 + bande + 1))
            for y in ys:
                row = np.nonzero(libre[y])[0]
                if not row.size:
                    continue
                x = row.min() if cote == "ouest" else row.max()
                c.append((x, y, x if cote == "ouest" else gw - 1 - x))
        e = choisir(c)
        if e:
            out[cote] = e
    return out


def export_zone(zone, tuiles_8px=True):
    src = os.path.join(RENDU, zone)
    man = json.load(open(f"{src}/manifest.json"))
    dst = os.path.join(OUT, zone)
    os.makedirs(f"{dst}/calques", exist_ok=True)

    fr = sorted(glob.glob(f"{src}/frames/*.png"))
    fond = Image.open(fr[0]).convert("RGB")
    fond.save(f"{dst}/fond.png")
    strip(fr, f"{dst}/fond_frames.png")          # 12 frames en bande horizontale

    infos = []
    for L in man["layers"]:
        if L.get("file"):
            fs = [f"{src}/{L['file']}"]
        elif L.get("dir"):
            fs = sorted(glob.glob(f"{src}/{L['dir']}/*.png"))
        else:
            continue
        if not fs:
            continue
        nom = f"{L['order']:02d}_{L['name']}"
        if len(fs) == 1:
            shutil.copy(fs[0], f"{dst}/calques/{nom}.png")
            chemin = f"calques/{nom}.png"
        else:
            strip(fs, f"{dst}/calques/{nom}.png")   # bande de len(fs) frames
            chemin = f"calques/{nom}.png"
        infos.append(dict(ordre=L["order"], nom=L["name"], chemin=chemin,
                          anime=bool(L.get("animated")), frames=len(fs),
                          technique=L.get("technique", "")))

    bloc, (W, H), eau = masque_obstacles(zone)
    ecrire_obstacles(zone, bloc, eau, dst)
    apercu_obstacles(zone, bloc, eau, fond, dst)

    tr = collision_tmx(zone, bloc, eau, dst) if tuiles_8px else None

    a = audit(zone)
    gh, gw = bloc.shape
    g = dict(
        nom=zone, moteur="RogueEssence / PMDO",
        taille_px=[W, H],
        cellules_8px=[gw, gh],
        cases_24px=[W // TILE, H // TILE],
        cellule=CELL, case=TILE, viewport=list(VIEW),
        fond="fond.png", frames="fond_frames.png", frame_ms=man["frame_ms"],
        nb_frames=man["frames"], palette=man["palette"],
        calques=infos,
        collision=dict(fichier="obstacles.json", masque="collision.png",
                       libres=int((~bloc).sum()), bloquees=int(bloc.sum()),
                       eau=int(eau.sum())),
        entrees=(lambda e: e)(entrees(bloc, eau)),
        bordure_fermee=[c for c, v in entrees(bloc, eau).items() if not v["sur_bordure"]],
        echelle=a,
        collision_tiled=tr,
        note=("Toile multiple de 8 et de 24 : la grille de collision PMDO tombe "
              "sur l'art sans reechantillonnage. Aucun pixel n'a ete redimensionne."),
    )
    json.dump(g, open(f"{dst}/ground.json", "w"), indent=1)
    return g


if __name__ == "__main__":
    zones = sys.argv[1:] or sorted(
        z for z in os.listdir(RENDU)
        if os.path.isdir(os.path.join(RENDU, z)) and not z.endswith("_src"))
    rap = {}
    for z in zones:
        g = export_zone(z)
        rap[z] = dict(cellules=g["cellules_8px"], cases=g["cases_24px"],
                      collision=g["collision"],
                      tmx=g["collision_tiled"],
                      entrees=list(g["entrees"]))
        print(f"{z:12s} {g['cellules_8px'][0]}x{g['cellules_8px'][1]} cellules  "
              f"libre {g['collision']['libres']:5d}  bloque {g['collision']['bloquees']:5d}  "
              f"eau {g['collision']['eau']:5d}  {g['echelle']['cases_24px'] if 'cases_24px' in g['echelle'] else ''}")
    json.dump(rap, open(os.path.join(OUT, "rapport_pmdo.json"), "w"), indent=1)
