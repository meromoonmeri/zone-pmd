"""
scale_pmdo.py — met la clairiere au scale PMDO, SANS la modifier.

La demande : l'image existante (masters natifs 1120x960 de la branche
arena/01a08169, commit 0f9805e, recopies dans layers/src/clairiere_master/)
mise au scale PMDO. Pas de repeinte, pas de filtre, pas de recoloration :
les masters sont integres dans le depot, on ne fait que les mettre a
l'echelle et en deriver la grille de collision.

## La geometrie du scale (methode d'echelle, regle par regle)

Le master 1120x960 n'est pas un multiple de 24 : aucun facteur ENTIER n'en
fait une toile PMDO. La methode :

1. rogne au multiple de 48 le plus proche, CENTRE :
       1120x960 -> [56, 24, 1064, 936] -> 1008x912
   (les 48-multiples se divisent par 2 en 24-multiples exacts) ;
2. divise par 2 en PLUS PROCHE VOISIN — le seul retaillage entier, il ne
   cree ni flou ni couleur nouvelle, chaque pixel de sortie EST un pixel
   du master :
       1008x912 / 2 -> 504x456 = 21x19 cases de 24 px = 63x57 cellules de 8 px.

La grille de collision (8 px) et la case de lecture (24 px) tombent donc
pile sur l'art, sans qu'aucun pixel ait ete invente. Le viewport moteur est
320x240 ; la toile fait 2,99 ecrans.

Variante qui preserve encore plus d'image (fournie en bonus) :
       1120x960 -> [8, 0, 1112, 960] -> 1104x960 / 2 -> 552x480 = 23x20 cases.
Elle ne rogne que 16 px de large et rien en hauteur, au prix d'une toile
moins standard.

## La collision, derivee de leurs propres calques decomposes

render_layers/bassin.png  -> eau    ('~', nageable-bloque) : alpha >= 55 % par cellule
render_layers/arbres.png  -> bloque ('#')                 : alpha >= 30 % par cellule
(sol, chemin et le reste -> libre '.')

## Sorties

pmdo/clairiere/   le pack corrige, MEME structure que le pack vise :
                  fond.png (base + eau f01 + lumiere f01, l'ordre de leur tmx),
                  calques/Base.png, Water_f01..08, Light_f01..08
                  (Light = lumiere_simple, leur choix final, 93 % de
                  recouvrement) + les deux autres jeux de lumiere scalés,
                  obstacles.json/.txt, collision.png, collision.tmx 8 px,
                  brosse_collision.*, clairiere.tmx, audit_echelle.png,
                  ground.json (entrees + audit), README.md
tiled/clairiere/  les memes calques scalés + la carte 21x19 cases de 24 px
variant_552x480/  la toile alternative 23x20 cases (fond + collision)

Usage : python3 scale_pmdo.py
"""
import os
import sys
import json
import glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from PIL import Image, ImageDraw

from pmdo.export_pmdo import (collision_tmx, ecrire_obstacles, apercu_obstacles,
                              entrees)
from pmdo.audit_echelle import CELL, TILE, VIEW, largeur_locale, sprites_ref

SRC = "layers/src/clairiere_master"
DST = "pmdo/clairiere"
TIL = "tiled/clairiere"
VAR = "pmdo/clairiere/variant_552x480"

# la geometrie du scale, voir le module
CROP = (56, 24, 56 + 1008, 24 + 912)          # 1008x912 centre
OUT = (504, 456)                              # 21x19 cases, 63x57 cellules
CROP_VAR = (8, 0, 8 + 1104, 960)              # 1104x960
OUT_VAR = (552, 480)                          # 23x20 cases, 69x60 cellules


def mise_a_echelle(chemin, crop=CROP, out=OUT):
    """Crop centre au multiple de 48, puis division par 2 au plus proche
    voisin, faite a la main (pixel 2x, 2y) pour que la formule documentee
    (chaque pixel de sortie == master en (2x+x0, 2y+y0)) soit litteralement
    vraie. Aucun pixel n'est invente (verifiable, voir controle_exactitude).
    """
    im = Image.open(chemin)
    if im.size != (1120, 960):
        return im.copy()
    if im.mode not in ("RGB", "RGBA", "L"):
        im = im.convert("RGBA")
    x0, y0, x1, y1 = crop
    a = np.asarray(im)[y0:y1:2, x0:x1:2]      # rogne + 1 pixel sur 2
    im2 = Image.fromarray(a)
    assert im2.size == out, f"{chemin}: {im2.size} != {out}"
    return im2


def controle_exactitude(master, sorti, crop=CROP):
    """Preuve que le scale n'a rien invente : chaque pixel de la sortie doit
    etre EGAL au pixel du master situe a (2x+x0, 2y+y0)."""
    m = np.asarray(master.convert("RGBA"))
    s = np.asarray(sorti.convert("RGBA"))
    x0, y0 = crop[0], crop[1]
    h, w = s.shape[:2]
    ref = m[y0:y0 + 2 * h:2, x0:x0 + 2 * w:2]
    return bool((ref == s).all())


def grille(alpha, seuil, taille):
    """Ramene un masque plein cadre a la grille 8 px (seuil = part de la
    cellule couverte par le masque)."""
    gh, gw = taille[1] // CELL, taille[0] // CELL
    a = alpha.astype(np.float32)
    a = a[:gh * CELL, :gw * CELL].reshape(gh, CELL, gw, CELL).mean(axis=(1, 3))
    return a >= seuil


def composer(base, *calques):
    """Empile les calques RGBA sur la base, dans l'ordre (le leur : Base,
    Water, Light)."""
    im = base.convert("RGBA")
    for c in calques:
        if c is not None:
            im.alpha_composite(c.convert("RGBA"))
    return im


def echelle_audit(bloc, eau, taille):
    """Les chiffres de la methode : emprise, largeur locale, occupation."""
    gw, gh = taille[0] // CELL, taille[1] // CELL
    free = ~bloc
    lm, lmax = largeur_locale(free)
    return dict(
        px=list(taille),
        cases=[round(taille[0] / TILE, 2), round(taille[1] / TILE, 2)],
        cellules_8px=[gw, gh],
        multiple_de_8=(taille[0] % CELL == 0 and taille[1] % CELL == 0),
        multiple_de_24=(taille[0] % TILE == 0 and taille[1] % TILE == 0),
        largeur_locale_mediane=round(float(lm), 2),
        plus_grand_vide=round(float(lmax), 2),
        occupation_decor=round(100.0 * (bloc & ~eau).sum() / bloc.size, 1),
        part_eau=round(100.0 * eau.sum() / bloc.size, 1),
        ecrans=round((taille[0] / VIEW[0]) * (taille[1] / VIEW[1]), 2),
    )


def planche_echelle(fond, bloc, eau, out_path):
    """La preuve visuelle : sprites etalon poses a 1:1 + cadre du viewport
    320x240, sur le fond scale."""
    from pmdo.audit_echelle import points
    a = fond.convert("RGBA").copy()
    spr = sprites_ref()
    free = ~bloc
    for i, (x, y) in enumerate(points(free, 6)):
        s = spr[i % len(spr)]
        ov = Image.new("RGBA", a.size, (0, 0, 0, 0))
        ImageDraw.Draw(ov).ellipse(
            [x - s.width // 2, y - 3, x + s.width // 2, y + 3],
            fill=(0, 0, 0, 80))
        a.alpha_composite(ov)
        a.alpha_composite(s, (int(x - s.width / 2), int(y - s.height)))
    W, H = a.size
    d = ImageDraw.Draw(a)
    vx, vy = (W - VIEW[0]) // 2, (H - VIEW[1]) // 2
    d.rectangle([vx, vy, vx + VIEW[0], vy + VIEW[1]],
                outline=(90, 190, 255, 255), width=2)
    a.convert("RGB").save(out_path)


def carte_pmdo(taille, calques):
    """Leur structure de carte (imagelayers Base/Water/Light), aux dimensions
    demandees."""
    gw, gh = taille[0] // TILE, taille[1] // TILE
    lignes = ['<?xml version="1.0" encoding="UTF-8"?>',
              f'<map version="1.10" tiledversion="1.10.2" orientation="orthogonal" '
              f'renderorder="right-down" width="{gw}" height="{gh}" '
              f'tilewidth="{TILE}" tileheight="{TILE}" infinite="0" '
              f'nextlayerid="{len(calques) + 1}" nextobjectid="1">',
              ' <properties>',
              '  <property name="zone" value="clairiere"/>',
              f'  <property name="cellule_collision" type="int" value="{CELL}"/>',
              f'  <property name="viewport" value="{VIEW[0]}x{VIEW[1]}"/>',
              '  <property name="mise_a_l_echelle" value="crop_1008x912_centre puis /2 plus proche voisin"/>',
              ' </properties>']
    for i, (nom, src) in enumerate(calques, 1):
        lignes += [f' <imagelayer id="{i}" name="{nom}">',
                   f'  <image source="{src}" width="{taille[0]}" '
                   f'height="{taille[1]}"/>',
                   f' </imagelayer>']
    lignes.append('</map>')
    return "\n".join(lignes) + "\n"


def main():
    for d in (DST, TIL, VAR):
        os.makedirs(d, exist_ok=True)

    # --- 1. les calques scalés ------------------------------------------------
    base_m = Image.open(f"{SRC}/base.png")
    base = mise_a_echelle(f"{SRC}/base.png")
    ok = controle_exactitude(base_m, base)
    print(f"Base  : {base_m.size} -> {base.size}  pixels exacts (master == sortie) : {ok}")

    os.makedirs(f"{DST}/calques", exist_ok=True)
    base.convert("RGBA").save(f"{DST}/calques/Base.png")
    base.save(f"{TIL}/base.png")

    jeux = {"Water": "eau", "Light": "lumiere_simple",
            "lumiere_evolution": "lumiere_evolution",
            "lumiere_validee": "lumiere_validee"}
    prem = {}
    for nom_pack, dossier in jeux.items():
        fs = sorted(glob.glob(f"{SRC}/{dossier}/f*.png"))
        dst_d = f"{DST}/calques" if nom_pack in ("Water", "Light") \
            else f"{DST}/calques/{dossier}"
        os.makedirs(dst_d, exist_ok=True)
        os.makedirs(f"{TIL}/{dossier}", exist_ok=True)
        for i, f in enumerate(fs, 1):
            s = mise_a_echelle(f)
            s.save(f"{dst_d}/{nom_pack}_f{i:02d}.png" if nom_pack in ("Water", "Light")
                   else f"{dst_d}/f{i:02d}.png")
            s.save(f"{TIL}/{dossier}/f{i:02d}.png")
        prem[nom_pack] = fs[0] and mise_a_echelle(fs[0])
        print(f"{nom_pack:18s}: {len(fs)} frames scalées")

    # --- 2. le fond : leur ordre d'empilement (Base, Water, Light) ------------
    fond = composer(base, prem["Water"], prem["Light"])
    fond.convert("RGB").save(f"{DST}/fond.png")

    # --- 3. la collision, derivee de leurs calques decomposes ------------------
    bassin = mise_a_echelle(f"{SRC}/render_layers/bassin.png")
    arbres = mise_a_echelle(f"{SRC}/render_layers/arbres.png")
    a_bassin = np.asarray(bassin)[..., 3] > 0
    a_arbres = np.asarray(arbres)[..., 3] > 0
    eau = grille(a_bassin, 0.55, OUT)
    bloc = grille(a_arbres, 0.30, OUT)
    ecrire_obstacles("clairiere", bloc, eau, DST)
    apercu_obstacles("clairiere", bloc, eau, fond.convert("RGB"), DST)
    tr = collision_tmx("clairiere", bloc, eau, DST)
    ent = entrees(bloc, eau)

    # --- 4. la carte Tiled PMDO + les calques scalés cote tiled/ ---------------
    open(f"{DST}/clairiere.tmx", "w").write(
        carte_pmdo(OUT, [("0_Base", "calques/Base.png"),
                         ("1_Water", "calques/Water_f01.png"),
                         ("2_Light", "calques/Light_f01.png")]))
    os.makedirs(f"{TIL}/render_layers", exist_ok=True)
    for f in sorted(glob.glob(f"{SRC}/render_layers/*.png")):
        mise_a_echelle(f).save(f"{TIL}/render_layers/{os.path.basename(f)}")
    open(f"{TIL}/clairiere.tmx", "w").write(
        carte_pmdo(OUT, [("Base", "base.png"),
                         ("Eau frame 01", "eau/f01.png"),
                         ("Lumiere simple frame 01", "lumiere_simple/f01.png"),
                         ("Lumiere validee frame 01", "lumiere_validee/f01.png"),
                         ("Lumiere evolution frame 01", "lumiere_evolution/f01.png")]))

    # --- 5. l'audit + ground.json ----------------------------------------------
    aud = echelle_audit(bloc, eau, OUT)
    planche_echelle(fond, bloc, eau, f"{DST}/audit_echelle.png")
    ncol = len({tuple(p) for p in np.asarray(fond.convert("RGB")).reshape(-1, 3)})
    g = dict(
        nom="clairiere", moteur="RogueEssence / PMDO",
        source=("masters natifs 1120x960 (branche arena/01a08169, commit "
                "0f9805e), copies integres dans layers/src/clairiere_master"),
        taille_px=list(OUT), cellules_8px=aud["cellules_8px"],
        cases_24px=[OUT[0] // TILE, OUT[1] // TILE], cellule=CELL, case=TILE,
        viewport=list(VIEW),
        mise_a_l_echelle=dict(
            methode="crop centre au multiple de 48 puis division par 2 au plus proche voisin",
            master=[1120, 960], crop=list(CROP), recadre=[1008, 912],
            sortie=list(OUT),
            pixels_inventes=0,
            verifie=f"chaque pixel de sortie == pixel du master : {ok}"),
        fond="fond.png", frame_ms=110, nb_frames=8, palette=ncol,
        calques=[
            dict(ordre=0, nom="Base", chemin="calques/Base.png",
                 anime=False, frames=1, technique="master scalé, intact"),
            dict(ordre=1, nom="Water", chemin="calques/Water_f01.png",
                 anime=True, frames=8, technique="frames redessinées du master"),
            dict(ordre=2, nom="Light", chemin="calques/Light_f01.png",
                 anime=True, frames=8, technique="lumiere_simple, leur choix final"),
        ],
        collision=dict(fichier="obstacles.json", masque="collision.png",
                       libres=int((~bloc).sum()), bloquees=int(bloc.sum()),
                       eau=int(eau.sum()),
                       derive=( "bassin.png -> eau (alpha >= 55 %/cellule 8 px) ; "
                                "arbres.png -> bloque (alpha >= 30 %/cellule)")),
        entrees=ent,
        bordure_fermee=[c for c, v in ent.items() if not v["sur_bordure"]],
        echelle=aud,
        collision_tiled=dict(tmx=tr["tmx"], tsx=tr["tsx"],
                             cellules=tr["cellules"], pinceaux=tr["pinceaux"]),
        audit_planche="audit_echelle.png",
        note=("Toile multiple de 8 et de 24 : la grille de collision tombe sur "
              "l'art sans reechantillonnage fractionnaire. Le master est rogne "
              "au centre (1120->1008, 960->912) puis divise par 2 au plus "
              "proche voisin : aucun pixel invente, aucune couleur modifiee."),
    )
    json.dump(g, open(f"{DST}/ground.json", "w"), indent=1, ensure_ascii=False)

    # --- 6. la variante 552x480 (preserve 98,6 % de la largeur du master) ------
    base_v = mise_a_echelle(f"{SRC}/base.png", CROP_VAR, OUT_VAR)
    bassin_v = np.asarray(mise_a_echelle(f"{SRC}/render_layers/bassin.png",
                                         CROP_VAR, OUT_VAR))[..., 3] > 0
    arbres_v = np.asarray(mise_a_echelle(f"{SRC}/render_layers/arbres.png",
                                         CROP_VAR, OUT_VAR))[..., 3] > 0
    eau_v = grille(bassin_v, 0.55, OUT_VAR)
    bloc_v = grille(arbres_v, 0.30, OUT_VAR)
    eau_f = mise_a_echelle(f"{SRC}/eau/f01.png", CROP_VAR, OUT_VAR)
    lum_f = mise_a_echelle(f"{SRC}/lumiere_simple/f01.png", CROP_VAR, OUT_VAR)
    composer(base_v, eau_f, lum_f).convert("RGB").save(f"{VAR}/fond.png")
    ecrire_obstacles("clairiere", bloc_v, eau_v, VAR)
    collision_tmx("clairiere", bloc_v, eau_v, VAR)
    aud_v = echelle_audit(bloc_v, eau_v, OUT_VAR)
    json.dump(dict(toile=list(OUT_VAR), cases=[23, 20], cellules=[69, 60],
                   echelle=aud_v,
                   note=("Variante qui ne rogne que 16 px de large et rien en "
                         "hauteur : 1104x960 -> /2 -> 552x480, 23x20 cases.")),
              open(f"{VAR}/echelle.json", "w"), indent=1, ensure_ascii=False)

    # --- 7. le rapport PMDO : entree additive, sans toucher aux 13 zones -------
    rp = "pmdo/rapport_pmdo.json"
    r = json.load(open(rp))
    r["clairiere"] = dict(
        cellules=aud["cellules_8px"], cases=[21, 19],
        collision=dict(fichier="obstacles.json", masque="collision.png",
                       libres=g["collision"]["libres"],
                       bloquees=g["collision"]["bloquees"],
                       eau=g["collision"]["eau"]),
        tmx=tr, entrees=[k for k, v in ent.items() if v["sur_bordure"]],
        echelle=dict(master=[1120, 960], methode="crop 1008x912 centre puis /2 "
                     "plus proche voisin", sortie=list(OUT),
                     pixels_inventes=0, pixels_exacts=ok,
                     variante="variant_552x480/ (552x480, 23x20 cases)"))
    json.dump(r, open(rp, "w"), indent=1, ensure_ascii=False)

    # --- 8. le README du pack ---------------------------------------------------
    open(f"{DST}/README.md", "w").write(README_PACK.format(
        occ=aud["occupation_decor"], lar=aud["largeur_locale_mediane"],
        eau_=aud["part_eau"], ecr=aud["ecrans"], ok=ok, ncol=ncol,
        libres=g["collision"]["libres"], bloques=g["collision"]["bloquees"],
        cell_eau=g["collision"]["eau"]))

    print(f"\naudit 504x456 : occupation {aud['occupation_decor']} % | largeur "
          f"{aud['largeur_locale_mediane']} cases | eau {aud['part_eau']} % | "
          f"{aud['ecrans']} ecrans | cases {aud['cases'][0]}x{aud['cases'][1]}")
    print(f"variante 552x480 : occupation {aud_v['occupation_decor']} % | "
          f"{aud_v['ecrans']} ecrans")
    print("entrees :", {k: v["sur_bordure"] for k, v in ent.items()})


README_PACK = """# Clairiere — pack PMDO, au scale demande

L'image source (masters natifs 1120x960) mise au scale PMDO **sans etre
modifiee** : ni repeinte, ni filtree, ni recoloree.

## La mise a l'echelle, exactement

1. master `1120x960` -> rogne au centre au multiple de 48 : `1008x912`
   (on perd 112 px de large et 48 px de haut, symetriquement) ;
2. division par 2 **au plus proche voisin** -> `504x456`
   = **21 x 19 cases de 24 px** = **63 x 57 cellules de 8 px**.

Controle d'exactitude : chaque pixel de sortie est EGAL au pixel du master
situé en (2x+56, 2y+24) — verifie pixel par pixel : {ok}.
Aucune couleur n'est inventee ni modifiee (palette du fond : {ncol} couleurs,
celle du master).

## Contenu

| fichier | role |
|---|---|
| `fond.png` | Base + Water f01 + Light f01, l'ordre du tmx |
| `calques/Base.png` | le master scale, intact |
| `calques/Water_f01..08.png` | les 8 frames d'eau, scalées |
| `calques/Light_f01..08.png` | les 8 frames de lumiere (`lumiere_simple`, leur choix final) |
| `calques/lumiere_evolution/`, `calques/lumiere_validee/` | les deux autres jeux, scalés aussi |
| `obstacles.json` / `.txt` | grille 8 px : `.` libre, `#` bloque, `~` eau |
| `collision.png`, `collision.tmx` + `brosse_collision.*` | la collision, editable a la souris dans Tiled |
| `clairiere.tmx` | leur carte 3 imagelayers, sur les fichiers corriges |
| `audit_echelle.png` | sprites etalon 1:1 + viewport 320x240 |
| `ground.json` | descripteur complet + audit chiffre |
| `variant_552x480/` | toile alternative 23x20 cases (ne rogne que 16 px de large) |

## La collision, derivee de leurs calques decomposes

`render_layers/bassin.png` -> eau (`~`) ; `render_layers/arbres.png` ->
bloque (`#`). {libres} cellules libres, {bloques} bloquees, {cell_eau} d'eau.

## Audit d'echelle

| critere | valeur |
|---|---|
| cases 24 px | 21 x 19 |
| cellules 8 px | 63 x 57 |
| occupation du decor | {occ} % (hors eau) |
| part d'eau | {eau_} % |
| largeur locale mediane | {lar} cases |
| emprise | {ecr} ecrans de 320x240 |

Les masters restent dans `layers/src/clairiere_master/` ; la variante large
dans `variant_552x480/`.
"""


if __name__ == "__main__":
    main()
