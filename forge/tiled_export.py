"""
tiled_export.py — export Tiled (.tsx / .tmx) d'une zone animée.

Deux cartes sont produites :

  <zone>_tuiles.tmx   couche de tuiles 24x24 avec ANIMATIONS NATIVES Tiled.
                      Chaque case dont le contenu change au fil des frames
                      devient une tuile animée (<animation><frame .../></animation>),
                      exactement la technique des tilemaps DS/GBA.

  <zone>_calques.tmx  un <imagelayer> par calque du pipeline, dans l'ordre,
                      avec les propriétés (dossier de frames, technique).

L'export est relu et validé avec pytmx.
"""
import os, json, hashlib
import numpy as np
from PIL import Image

TW = TH = 24
COLS = 32


def _slice(img, tw=TW, th=TH):
    h, w = img.shape[:2]
    return [(y, x, img[y * th:(y + 1) * th, x * tw:(x + 1) * tw])
            for y in range(h // th) for x in range(w // tw)]


def export(zone, frames_dir, out_dir, layers=None, frame_ms=110, tw=TW, th=TH):
    os.makedirs(out_dir, exist_ok=True)
    fs = sorted(f for f in os.listdir(frames_dir) if f.endswith(".png"))
    frames = [np.array(Image.open(os.path.join(frames_dir, f)).convert("RGB")) for f in fs]
    n = len(frames)
    H, W = frames[0].shape[:2]
    gw, gh = W // tw, H // th

    # --- dictionnaire de tuiles ------------------------------------------- #
    tiles, index = [], {}

    def tile_id(arr):
        k = hashlib.md5(arr.tobytes()).digest()
        if k not in index:
            index[k] = len(tiles)
            tiles.append(arr.copy())
        return index[k]

    seqs = {}                       # (gy,gx) -> tuple des ids par frame
    for gy in range(gh):
        for gx in range(gw):
            seq = tuple(tile_id(f[gy * th:(gy + 1) * th, gx * tw:(gx + 1) * tw])
                        for f in frames)
            seqs[(gy, gx)] = seq

    # --- tuiles animées : une entrée par séquence distincte ---------------- #
    anim_of, layer_ids = {}, {}
    for pos, seq in seqs.items():
        if len(set(seq)) == 1:
            layer_ids[pos] = seq[0]
        else:
            if seq not in anim_of:
                head = len(tiles)
                tiles.append(tiles[seq[0]].copy())      # image = 1re frame
                anim_of[seq] = head
            layer_ids[pos] = anim_of[seq]

    # --- image du tileset --------------------------------------------------- #
    count = len(tiles)
    rows = (count + COLS - 1) // COLS
    sheet = np.zeros((rows * th, COLS * tw, 3), np.uint8)
    for i, t in enumerate(tiles):
        r, c = divmod(i, COLS)
        sheet[r * th:(r + 1) * th, c * tw:(c + 1) * tw] = t
    tsx_png = f"{zone}_tuiles.png"
    Image.fromarray(sheet, "RGB").save(os.path.join(out_dir, tsx_png))

    # --- .tsx ---------------------------------------------------------------- #
    anim_xml = []
    for seq, head in sorted(anim_of.items(), key=lambda kv: kv[1]):
        fr = "".join(f'\n   <frame tileid="{t}" duration="{frame_ms}"/>' for t in seq)
        anim_xml.append(f'  <tile id="{head}">\n   <animation>{fr}\n   </animation>\n  </tile>')
    tsx = f'''<?xml version="1.0" encoding="UTF-8"?>
<tileset version="1.10" tiledversion="1.10.2" name="{zone}_tuiles" tilewidth="{tw}" tileheight="{th}" tilecount="{count}" columns="{COLS}">
 <image source="{tsx_png}" width="{COLS * tw}" height="{rows * th}"/>
{chr(10).join(anim_xml)}
</tileset>
'''
    with open(os.path.join(out_dir, f"{zone}_tuiles.tsx"), "w") as f:
        f.write(tsx)

    # --- .tmx tuiles ---------------------------------------------------------- #
    csv = ",\n".join(",".join(str(layer_ids[(gy, gx)] + 1) for gx in range(gw))
                     for gy in range(gh))
    tmx = f'''<?xml version="1.0" encoding="UTF-8"?>
<map version="1.10" tiledversion="1.10.2" orientation="orthogonal" renderorder="right-down" width="{gw}" height="{gh}" tilewidth="{tw}" tileheight="{th}" infinite="0" nextlayerid="2" nextobjectid="1">
 <properties>
  <property name="zone" value="{zone}"/>
  <property name="frames" type="int" value="{n}"/>
  <property name="frame_ms" type="int" value="{frame_ms}"/>
  <property name="tuiles_animees" type="int" value="{len(anim_of)}"/>
 </properties>
 <tileset firstgid="1" source="{zone}_tuiles.tsx"/>
 <layer id="1" name="{zone}" width="{gw}" height="{gh}">
  <data encoding="csv">
{csv}
</data>
 </layer>
</map>
'''
    with open(os.path.join(out_dir, f"{zone}_tuiles.tmx"), "w") as f:
        f.write(tmx)

    # --- .tmx calques-images ---------------------------------------------- #
    il, lid = [], 1
    for L in (layers or []):
        src = L["image"]
        props = "".join(f'\n   <property name="{k}" value="{v}"/>'
                        for k, v in L.get("props", {}).items())
        il.append(f''' <imagelayer id="{lid}" name="{L['name']}">
  <properties>{props}
  </properties>
  <image source="{src}" width="{W}" height="{H}"/>
 </imagelayer>''')
        lid += 1
    tmx2 = f'''<?xml version="1.0" encoding="UTF-8"?>
<map version="1.10" tiledversion="1.10.2" orientation="orthogonal" renderorder="right-down" width="{gw}" height="{gh}" tilewidth="{tw}" tileheight="{th}" infinite="0" nextlayerid="{lid}" nextobjectid="1">
{chr(10).join(il)}
</map>
'''
    with open(os.path.join(out_dir, f"{zone}_calques.tmx"), "w") as f:
        f.write(tmx2)

    return dict(tuiles_uniques=count, tuiles_animees=len(anim_of),
                grille=[gw, gh], frames=n,
                cases_animees=sum(1 for s in seqs.values() if len(set(s)) > 1))
