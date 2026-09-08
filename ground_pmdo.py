"""
ground_pmdo.py — la clairiere_a_l_arbre en VRAI ground PMDO, animee en
frames 1/2/3/4/5/6/7/8, aux criteres exacts de Luminous Spring (Palika,
mod Halcyon pour PMDO/RogueEssence).

## Ce qui manquait

La zone (commit « Clairiere a l'arbre ancien », 576x504 = 24x21 cases de
24 = 72x63 cellules de 8, viewport 320x240, 8 frames d'eau a 165 ms)
avait deja ses planches `.tile` 8 px (pmdo/clairiere_arbre/tiles/) — le
format binaire de RogueEssence, verifie compatible ci-dessous. Il
manquait les deux fichiers que le moteur charge reellement :

- **Data/Ground/clairiere_arbre.rsground** : la carte GroundMap (JSON),
  la structure champ pour champ de luminous_spring.rsground —
  obstacles 72x63 (Tags 0 libre / 1 solide, comme l'eau de Luminous
  Spring et les murs de la guilde), calques de tuiles, entite de
  sortie sud ;
- **Content/Tile/index.idx** : le TileGuide qui indexe les planches
  ([int32 nombre] puis par planche [chaine .NET 7 bits][TileIndexNode]).

## Les criteres Luminous Spring appliques

| critere           | Luminous Spring               | clairiere_arbre                     |
|---|---|---|
| moteur            | RogueEssence GroundMap 0.7.4  | idem                                |
| tuiles            | TexSize 3 (24 px)             | TexSize 1 (8 px) — les planches de la zone sont coupees en 8 px, comme illuminant_riverbed / Altere_Pond chez Palika |
| obstacles         | [w*TexSize][h*TexSize], Tags 0/1 | 72x63, Tags 0/1, derives de collision.png |
| animation         | Frames[] par case, FrameLength 10 | eau : 8 frames 1..8, FrameLength 10 (=165 ms, leur frame_ms) |
| statique          | FrameLength 60                | base : FrameLength 60               |
| sorties           | South_Exit, collider en px    | South_Exit sur l'entree sud         |
| viewport          | 320x240                       | 320x240 (2,1 ecrans de haut)        |

## Les sorties (pmdo/clairiere_arbre/ground/)

Content/Tile/*.tile + index.idx, Data/Ground/clairiere_arbre.rsground,
frames/frame_1..8.png, frames/viewport.gif, apercu_ground.png (la carte
RE-RENDUE depuis les fichiers binaires — la preuve), README.md.

Usage : python3 ground_pmdo.py
"""
import io
import os
import json
import struct
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageDraw
import numpy as np

from forge import tile_rogue as TR

ZONE = "clairiere_arbre"
SRC_TILE = f"pmdo/{ZONE}/tiles"
RENDU = f"layers/rendu/{ZONE}"
DST = f"pmdo/{ZONE}/ground"

W, H = 576, 504            # la toile
GW, GH = W // 8, H // 8    # 72 x 63 tuiles de 8 px (TexSize 1)
TEXSIZE = 1
FL_ANIM = 10               # FrameLength 10 = 165 ms (frames de Luminous Spring)
FL_STAT = 60               # tuiles statiques de Luminous Spring
VIEW = (320, 240)

# les planches : dessin j -> nom de feuille (cf. build_clairiere.py)
FEUILLES = ["clairiere_arbre_River", "clairiere_arbre_River_f1",
            "clairiere_arbre_River_f2", "clairiere_arbre_River_f3"]
FRAME_MS = 165             # leur manifest.json


# ---------------------------------------------------------------------------
# index.idx (TileGuide.Save) — chaine .NET : longueur 7 bits + UTF-8
# ---------------------------------------------------------------------------

def chaine_dotnet(s):
    b = s.encode('utf-8')
    n, out = len(b), bytearray()
    while True:
        octet = n & 0x7F
        n >>= 7
        out.append(octet | (0x80 if n else 0))
        if not n:
            break
    return bytes(out) + b


def ecrire_index(chemin, noeuds):
    """noeuds : {nom: (taille_tuile, [(x, y, pos), ...])} — comme
    TileGuide.Save : int32 nombre, puis par noeud chaine + TileIndexNode."""
    avec = bytearray(struct.pack('<i', len(noeuds)))
    for nom, (taille, locs) in noeuds.items():
        avec += chaine_dotnet(nom)
        avec += struct.pack('<ii', taille, len(locs))
        for x, y, pos in locs:
            avec += struct.pack('<iiq', x, y, pos)
    open(chemin, "wb").write(bytes(avec))


def lire_index(chemin):
    """Relit un index.idx comme TileGuide.Load."""
    d = open(chemin, "rb").read()
    o = 0

    def i32():
        nonlocal o
        v, = struct.unpack_from('<i', d, o); o += 4
        return v

    def chaine():
        nonlocal o
        n, dec = 0, 0
        while True:
            b = d[o]; o += 1
            n |= (b & 0x7F) << dec
            dec += 7
            if not b & 0x80:
                break
        s = d[o:o + n].decode('utf-8'); o += n
        return s

    nombre = i32()
    noeuds = {}
    for _ in range(nombre):
        nom = chaine()
        taille, n = i32(), i32()
        locs = [struct.unpack_from('<iiq', d, o + 16 * k) for k in range(n)]
        o += 16 * n
        noeuds[nom] = (taille, locs)
    return noeuds


def positions_tile(chemin):
    """Les (x, y, pos) d'une banque .tile, dans l'ordre du fichier —
    verifie AUSSI que l'encodage (cle = y<<32|x) == deux int32 x,y du
    moteur (TileIndexNode.Load)."""
    d = open(chemin, "rb").read()
    taille, n = struct.unpack_from('<ii', d, 0)
    out = []
    for k in range(n):
        cle, pos = struct.unpack_from('<qq', d, 8 + 16 * k)
        x, y = cle & 0xFFFFFFFF, (cle >> 32) & 0xFFFFFFFF
        # le moteur lit deux int32 : little-endian, (y<<32)|x == [x][y]
        assert struct.unpack_from('<ii', d, 8 + 16 * k) == (x, y)
        out.append((x, y, pos))
    return taille, out


# ---------------------------------------------------------------------------
# le .rsground (GroundMap) — champ pour champ comme luminous_spring.rsground
# ---------------------------------------------------------------------------

def cellule_vide():
    return {"AutoTileset": "", "Associates": [], "Layers": [], "NeighborCode": 0}


def calque_tuile(frames, frame_length):
    return {"Frames": [{"Sheet": s, "TexLoc": {"X": x, "Y": y}}
                       for s, x, y in frames],
            "FrameLength": frame_length}


def objet_sortie(nom, x, y, w, h):
    """Un GroundObject de sortie — la structure de luminous_spring."""
    anim = {"$type": "RogueEssence.Content.ObjAnimData, RogueEssence",
            "AnimIndex": "", "FrameTime": 0, "StartFrame": -1, "EndFrame": -1,
            "AnimDir": -1, "Alpha": 255, "AnimFlip": 0}
    return {"EntName": nom, "Direction": 0, "EntEnabled": True,
            "triggerType": 2, "ObjectAnim": dict(anim), "Passable": False,
            "CurrentAnim": dict(anim, FrameTime=1, AnimDir=0),
            "AnimTime": {"Ticks": 0}, "Cycles": 0,
            "DrawOffset": {"X": 0, "Y": 0},
            "Collider": {"X": x, "Y": y, "Width": w, "Height": h}}


# ---------------------------------------------------------------------------
# construction
# ---------------------------------------------------------------------------

def main():
    for d in (f"{DST}/Content/Tile", f"{DST}/Data/Ground", f"{DST}/frames"):
        os.makedirs(d, exist_ok=True)

    # --- 1. les planches : copiees telles quelles (deja au format moteur) --
    feuilles = ["clairiere_arbre_Base"] + FEUILLES + ["clairiere_arbre_Shadows"]
    for f in feuilles:
        shutil.copy2(f"{SRC_TILE}/{f}.tile", f"{DST}/Content/Tile/{f}.tile")
    print(f"planches copiees : {len(feuilles)} fichiers .tile (8 px, format "
          f"moteur — verifie en section 4)")

    # --- 2. la grille d'obstacles, depuis leur collision.png ---------------
    bloque = np.asarray(Image.open(f"pmdo/{ZONE}/collision.png")) > 127
    assert bloque.shape == (GH, GW)
    obstacles = [[{"Bounds": {"X": x * 8, "Y": y * 8, "Width": 8, "Height": 8},
                   "Tags": 1 if bloque[y, x] else 0}
                  for y in range(GH)] for x in range(GW)]

    # --- 3. les calques de la carte ----------------------------------------
    _, locs_base = positions_tile(f"{SRC_TILE}/clairiere_arbre_Base.tile")
    base_present = {(x, y) for x, y, _ in locs_base}
    _, locs_riv = positions_tile(f"{SRC_TILE}/clairiere_arbre_River.tile")
    eau_present = {(x, y) for x, y, _ in locs_riv}

    calque_base = [[None] * GH for _ in range(GW)]
    calque_riv = [[None] * GH for _ in range(GW)]
    for cx in range(GW):
        for cy in range(GH):
            cb = cellule_vide()
            if (cx, cy) in base_present:
                cb["Layers"] = [calque_tuile(
                    [("clairiere_arbre_Base", cx, cy)], FL_STAT)]
            calque_base[cx][cy] = cb

            cr = cellule_vide()
            if (cx, cy) in eau_present:
                # les 8 frames 1..8 : dessin j = frame (j*2+1, j*2+2),
                # maintien 2 — exactement leur sequence f00..f07
                frames = []
                for t in range(8):
                    fe = FEUILLES[t // 2]
                    frames.append((fe, cx, cy))
                cr["Layers"] = [calque_tuile(frames, FL_ANIM)]
            calque_riv[cx][cy] = cr

    # --- 4. le .rsground -----------------------------------------------------
    g = {
        "Version": "0.7.4.0",
        "Object": {
            "$type": "RogueEssence.Ground.GroundMap, RogueEssence",
            "TexSize": TEXSIZE,
            "Name": {"DefaultText": "Clairière de l'Arbre Ancien",
                     "LocalTexts": {"en": "Old Tree Clearing"}},
            "Released": True,
            "Comment": "clairiere_arbre 576x504, eau animee 8 frames "
                       "(4 dessins, maintien 2), criteres Luminous Spring",
            "obstacles": obstacles,
            "rand": {"$type": "RogueElements.ReRandom, RogueElements",
                     "FirstSeed": 0,
                     "s": [16294208416658607535, 7960286522194355700,
                           487617019471545679, 17909611376780542444]},
            "Status": {},
            "Background": {
                "$type": "RogueEssence.Dungeon.MapBG, RogueEssence",
                "MapLoc": {"X": 0, "Y": 0},
                "BGAnim": {"AnimIndex": "", "FrameTime": 1, "StartFrame": -1,
                           "EndFrame": -1, "AnimDir": -1, "Alpha": 255,
                           "AnimFlip": 0},
                "BGMovement": {"X": 0, "Y": 0}, "Parallax": "0, 0",
                "RepeatX": False, "RepeatY": False},
            "BlankBG": {"AutoTileset": "", "Associates": [], "Layers": [],
                        "NeighborCode": -1},
            "Layers": [
                {"Name": "Base", "Layer": 0, "Visible": True,
                 "Tiles": calque_base},
                {"Name": "River", "Layer": 0, "Visible": True,
                 "Tiles": calque_riv},
            ],
            "AssetName": ZONE,
            "Music": "",
            "EdgeView": 1,
            "NoSwitching": False,
            "ViewCenter": None,
            "ViewOffset": {"X": 0, "Y": 0},
            "ActiveChar": None,
            "Decorations": [{"Name": "New Deco", "Layer": 0,
                             "Visible": True, "Anims": []}],
            "Entities": [{"Name": "New EntLayer", "Visible": True,
                          "MapChars": [],
                          "GroundObjects": [
                              objet_sortie("South_Exit", 264, 496, 72, 8)],
                          "Spawners": []}],
        }
    }
    with open(f"{DST}/Data/Ground/{ZONE}.rsground", "w",
              encoding="utf-8-sig") as f:
        json.dump(g, f, indent=1, ensure_ascii=False)
    print(f"{ZONE}.rsground : {GW}x{GH} tuiles @8 (TexSize {TEXSIZE}), "
          f"{len(obstacles)}x{len(obstacles[0])} obstacles, "
          f"{len(eau_present)} cases d'eau x 8 frames, South_Exit")

    # --- 5. index.idx : fusionne avec l'index du mod cible s'il est fourni ---
    # Le moteur charge TOUS les index.idx en fallforth (le mod ecrase le jeu
    # cle par cle) mais un mod n'a qu'UN index.idx : on fusionne donc nos
    # planches dans celui du mod cible (PDM-New-Era-Abyss-to-Ascension),
    # conserve ici comme source.
    SRC_INDEX_MOD = f"{DST}/index_mod_PDM-New-Era.idx"
    noeuds = {}
    for f in feuilles:
        taille, locs = positions_tile(f"{SRC_TILE}/{f}.tile")
        noeuds[f] = (taille, locs)
    if os.path.exists(SRC_INDEX_MOD):
        for nom, (taille, locs) in lire_index(SRC_INDEX_MOD).items():
            noeuds.setdefault(nom, (taille, locs))
    ecrire_index(f"{DST}/Content/Tile/index.idx", noeuds)
    print(f"index.idx : {len(noeuds)} planches "
          f"({len(feuilles)} clairiere_arbre + "
          f"{len(noeuds) - len(feuilles)} du mod cible)")

    # --- 6. les frames 1..8 + le viewport GIF -------------------------------
    for t in range(8):
        shutil.copy2(f"{RENDU}/frames/f{t:02d}.png",
                     f"{DST}/frames/frame_{t+1}.png")
    frames = [Image.open(f"{RENDU}/frames/f{t:02d}.png").convert("RGB")
              for t in range(8)]
    # viewport 320x240 centre sur le bassin (centroid des tuiles River)
    xs = [x for x, y in eau_present]; ys = [y for x, y in eau_present]
    vx = max(0, min(W - VIEW[0], int(np.mean(xs)) * 8 - VIEW[0] // 2))
    vy = max(0, min(H - VIEW[1], int(np.mean(ys)) * 8 - VIEW[1] // 2))
    vp = [f.crop((vx, vy, vx + VIEW[0], vy + VIEW[1])) for f in frames]
    vp[0].save(f"{DST}/frames/viewport.gif", save_all=True,
               append_images=vp[1:], duration=FRAME_MS, loop=0)
    print(f"frames 1..8 + viewport.gif (320x240 sur le bassin @({vx},{vy}))")

    # --- 7. verification -----------------------------------------------------
    return verifier(bloque, frames, (vx, vy))


# ---------------------------------------------------------------------------
# verification : on relit TOUT et on re-rend la carte comme le moteur
# ---------------------------------------------------------------------------

def verifier(bloque, frames, vp_xy):
    ok = True
    feuilles = ["clairiere_arbre_Base"] + FEUILLES + ["clairiere_arbre_Shadows"]

    # 1. les planches : chaque entree est un PNG 8x8, l'encodage == moteur
    sheets = {}
    for f in feuilles:
        taille, entrees = positions_tile(f"{DST}/Content/Tile/{f}.tile")
        d = open(f"{DST}/Content/Tile/{f}.tile", "rb").read()
        pngs = {}
        for x, y, pos in entrees:
            n, = struct.unpack_from('<q', d, pos)
            pngs[(x, y)] = d[pos + 8:pos + 8 + n]
        for (x, y), png in pngs.items():
            if Image.open(io.BytesIO(png)).size != (8, 8):
                print(f"  ECHEC {f}: entree {Image.open(io.BytesIO(png)).size}")
                ok = False
        sheets[f] = pngs
        print(f"  {f}.tile : {len(entrees)} entrees 8x8 OK")

    # 2. les 4 dessins d'eau couvrent les memes cases
    locs = [{(x, y) for x, y, _ in positions_tile(
        f"{DST}/Content/Tile/{f}.tile")[1]} for f in FEUILLES]
    if any(l != locs[0] for l in locs):
        print("  ECHEC : les 4 dessins n'ont pas les memes cases"); ok = False
    else:
        print(f"  les 4 dessins couvrent les memes {len(locs[0])} cases OK")

    # 3. l'index : round-trip + nos planches presentes, Locs resolus
    noeuds = lire_index(f"{DST}/Content/Tile/index.idx")
    for nom in feuilles:
        taille, ls = noeuds.get(nom, (None, []))
        if taille != 8 or not ls or any((x, y) not in sheets[nom]
                                        for x, y, _ in ls):
            print(f"  ECHEC index {nom}"); ok = False
    print(f"  index.idx relu : {len(noeuds)} planches "
          f"({len(feuilles)} clairiere_arbre + le mod cible), "
          f"Locs tous resolus OK")

    # 4. le rsground : re-render == leurs frames, pixel par pixel
    g = json.load(open(f"{DST}/Data/Ground/{ZONE}.rsground",
                       encoding="utf-8-sig"))
    calques = g["Object"]["Layers"]

    def rendu(t):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for lay in calques:
            for cx in range(GW):
                for cy in range(GH):
                    for sous in lay["Tiles"][cx][cy]["Layers"]:
                        fr = sous["Frames"][t % len(sous["Frames"])]
                        png = sheets[fr["Sheet"]][
                            (fr["TexLoc"]["X"], fr["TexLoc"]["Y"])]
                        im.alpha_composite(Image.open(io.BytesIO(png)),
                                           (cx * 8, cy * 8))
        return im

    pire = 0
    for t in range(8):
        r = np.asarray(rendu(t).convert("RGB")).astype(int)
        ref = np.asarray(frames[t]).astype(int)
        pire = max(pire, int(np.abs(r - ref).max()))
    if pire > 1:
        print(f"  ECHEC re-render vs frames : ecart max {pire}"); ok = False
    else:
        print(f"  re-render des 8 frames depuis les .tile == leurs frames "
              f"(ecart max {pire}, arrondi de leur composite flottant) OK")

    # 5. les obstacles == collision.png
    ob = g["Object"]["obstacles"]
    bad = sum(1 for x in range(GW) for y in range(GH)
              if ob[x][y]["Tags"] != (1 if bloque[y, x] else 0))
    if bad:
        print(f"  ECHEC obstacles : {bad} cellules"); ok = False
    else:
        n1 = sum(1 for x in range(GW) for y in range(GH) if ob[x][y]["Tags"])
        print(f"  obstacles : {GW}x{GH}, {n1} solides == collision.png OK")

    # 6. l'apercu : re-render + collision + viewport + sortie
    a = rendu(0).convert("RGB")
    ov = Image.new("RGBA", a.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for x in range(GW):
        for y in range(GH):
            if bloque[y, x]:
                d.rectangle([x * 8, y * 8, x * 8 + 7, y * 8 + 7],
                            fill=(255, 60, 60, 60))
    vx, vy = vp_xy
    d.rectangle([vx, vy, vx + VIEW[0] - 1, vy + VIEW[1] - 1],
                outline=(90, 190, 255, 255), width=2)
    for ent in g["Object"]["Entities"][0]["GroundObjects"]:
        c = ent["Collider"]
        d.rectangle([c["X"], c["Y"], c["X"] + c["Width"] - 1,
                     c["Y"] + c["Height"] - 1],
                    outline=(255, 220, 0, 255), width=2)
    a = a.convert("RGBA")
    a.alpha_composite(ov)
    a.convert("RGB").save(f"{DST}/apercu_ground.png")
    print("  apercu_ground.png ecrit (re-render + collision + viewport + sortie)")

    print("\nVERIFICATION :", "TOUT EST EXACT" if ok else "ECHECS")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
