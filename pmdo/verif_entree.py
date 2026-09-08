"""
pmdo/verif_entree.py — verifie qu'une zone a bien une ENTREE SUD CONTINUE.

On repart de la grille de collision 8 px du pack PMDO, on inonde depuis les
cases libres du bord bas, et on regarde si l'inondation atteint le centre de
la carte. Si elle ne l'atteint pas, l'arene n'est pas jouable par le sud.

Usage : python3 pmdo/verif_entree.py <zone...>
"""
import json
import os
import sys

import numpy as np
from scipy import ndimage

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def verifier(zone):
    g = json.load(open(os.path.join(RACINE, "pmdo", zone, "ground.json")))
    col = g["collision"]
    grille = np.array(col["grille"] if "grille" in col else col.get("cellules"),
                      dtype=object) if isinstance(col, dict) else None
    chemin = os.path.join(RACINE, "pmdo", zone, "collision.npy")
    if os.path.exists(chemin):
        libre = np.load(chemin) == 0
    else:
        # repli : on relit le masque depuis le TMX de collision
        import re
        tmx = os.path.join(RACINE, "tiled", zone, "collision.tmx")
        t = open(tmx).read()
        m = re.search(r'<data encoding="csv">(.*?)</data>', t, re.S)
        vals = [int(v) for v in m.group(1).replace("\n", "").split(",") if v.strip()]
        h = g["cellules_8px"][1] if isinstance(g["cellules_8px"], list) else None
        w = g["cellules_8px"][0]
        libre = (np.array(vals).reshape(-1, w) == 1)
    h, w = libre.shape
    depart = np.zeros_like(libre)
    depart[h - 1] = libre[h - 1]
    if not depart.any():
        return dict(zone=zone, entree_sud=False, motif="bord sud entierement bloque")
    lab, _ = ndimage.label(libre)
    ids = set(lab[h - 1][libre[h - 1]].tolist())
    centre = lab[h // 2 - 4:h // 2 + 4, w // 2 - 4:w // 2 + 4]
    atteint = bool(set(centre[centre > 0].tolist()) & ids)
    zone_sud = int(libre[h - 1].sum())
    return dict(zone=zone, entree_sud=atteint, cases_libres_bord_sud=zone_sud,
                largeur_grille=w)


if __name__ == "__main__":
    ok = 0
    for z in sys.argv[1:]:
        try:
            r = verifier(z)
        except Exception as e:
            print(f"{z:30s} ERREUR {e}")
            continue
        ok += bool(r["entree_sud"])
        etat = "OUI" if r["entree_sud"] else "NON"
        print(f"{z:30s} entree sud continue : {etat:3s}  "
              f"({r.get('cases_libres_bord_sud', 0)} cases libres au bord sud)")
    print(f"\n{ok}/{len(sys.argv[1:])} zone(s) avec entree sud continue")
