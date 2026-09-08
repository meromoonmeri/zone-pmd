"""
forge/tile_rogue.py — ecrire une banque de tuiles `.tile` de RogueEssence.

Format releve par retro-ingenierie sur `Content/Tile/*.tile` de
`Palikadude/Halcyon` :

    int32   taille de tuile (8)
    int32   nombre d'entrees
    n x (int64 cle, int64 offset)          table d'index
    a chaque offset : int64 longueur, puis les octets d'un PNG

La cle encode la position dans la planche : `y = cle >> 32`, `x = cle & 0xffffffff`.

Deux constats qui changent tout sur sa methode :

  * la banque **n'est pas dedupliquee**. `Metano_Town_Base` compte 35 646
    entrees pour 189 x 189 = 35 721 positions : il stocke chaque case, il
    n'omet que les cases entierement vides. Ce n'est donc pas un tileset
    modulaire, c'est **une image peinte tranchee en cases de 8 px** ;
  * `Crooked_Cavern_Base` fait 320 x 240 px, soit **exactement un viewport**,
    avec un reemploi de 1,41x. Une carte d'entree de donjon, chez lui, c'est
    un ecran peint d'un seul tenant.
"""
import io
import struct

import numpy as np
from PIL import Image

TUILE = 8


def _png(arr):
    b = io.BytesIO()
    Image.fromarray(arr, "RGBA").save(b, "PNG", optimize=True)
    return b.getvalue()


def ecrire(chemin, image, tuile=TUILE, garder_vides=False):
    """Tranche `image` (HxWx4 uint8 ou chemin PNG) et ecrit la banque .tile.

    Renvoie un dict de controle : nombre d'entrees, positions vides omises,
    taux de reemploi (a titre indicatif, la banque n'est pas dedupliquee).
    """
    if isinstance(image, str):
        image = np.array(Image.open(image).convert("RGBA"))
    h, w = image.shape[:2]
    gh, gw = h // tuile, w // tuile

    entrees = []
    vides = 0
    for y in range(gh):
        for x in range(gw):
            case = image[y * tuile:(y + 1) * tuile, x * tuile:(x + 1) * tuile]
            if not garder_vides and case[..., 3].max() == 0:
                vides += 1
                continue
            entrees.append(((y << 32) | x, _png(np.ascontiguousarray(case))))

    tete = struct.pack("<ii", tuile, len(entrees))
    taille_table = len(entrees) * 16
    debut = len(tete) + taille_table
    table = b""
    corps = b""
    pos = debut
    for cle, octets in entrees:
        table += struct.pack("<qq", cle, pos)
        corps += struct.pack("<q", len(octets)) + octets
        pos += 8 + len(octets)
    with open(chemin, "wb") as f:
        f.write(tete + table + corps)

    import hashlib
    uniq = len({hashlib.md5(o).digest() for _, o in entrees})
    return dict(entrees=len(entrees), positions=gh * gw, vides_omises=vides,
                uniques=uniq,
                reemploi=round(len(entrees) / max(1, uniq), 2),
                planche=[w, h], tuile=tuile, octets=pos)


def lire(chemin):
    """Relit une banque .tile — la sienne comme la mienne."""
    b = open(chemin, "rb").read()
    tuile, n = struct.unpack("<ii", b[:8])
    off = 8
    cases = {}
    for _ in range(n):
        cle, o = struct.unpack("<qq", b[off:off + 16])
        off += 16
        ln, = struct.unpack("<q", b[o:o + 8])
        cases[((cle >> 32) & 0xffffffff, cle & 0xffffffff)] = \
            Image.open(io.BytesIO(b[o + 8:o + 8 + ln])).convert("RGBA")
    return tuile, cases


def recomposer(chemin):
    """Reassemble la planche a partir de la banque. Sert de controle."""
    tuile, cases = lire(chemin)
    ys = [y for y, _ in cases]
    xs = [x for _, x in cases]
    im = Image.new("RGBA", ((max(xs) + 1) * tuile, (max(ys) + 1) * tuile),
                   (0, 0, 0, 0))
    for (y, x), c in cases.items():
        im.paste(c, (x * tuile, y * tuile))
    return im
