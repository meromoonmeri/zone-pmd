"""
pmdo/export_tile.py — sortir chaque calque d'une zone en banque `.tile`
RogueEssence, au format de Palika.

Une banque par calque et par dessin : pour un calque anime a K dessins, on
ecrit `<Zone>_<Calque>.tile` (le dessin 0) et `<Zone>_<Calque>_f<k>.tile` pour
les suivants, comme il a `Altere_Pond_River_Animations` en 4 copies.

Usage : python3 pmdo/export_tile.py zone [zone...]
"""
import glob
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from forge import calques_halcyon as CH          # noqa: E402
from forge import tile_rogue as TR               # noqa: E402

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def exporter(zone):
    src = os.path.join(RACINE, "layers", "rendu", zone)
    man = json.load(open(os.path.join(src, "manifest.json")))
    dst = os.path.join(RACINE, "pmdo", zone, "tiles")
    os.makedirs(dst, exist_ok=True)
    n = man["frames"]
    rap = []
    for c in man.get("calques_halcyon", []):
        d = os.path.join(src, c["dossier"])
        fs = sorted(glob.glob(os.path.join(d, "*.png")))
        if not fs:
            continue
        k = c["frames"]
        idx, _ = CH.dessins(n, k)
        vus, choisis = [], []
        for t, i in enumerate(idx):
            if i not in vus and t < len(fs):
                vus.append(i)
                choisis.append(fs[t])
        if len(fs) == 1:
            choisis = fs[:1]
        slug = c["nom"].replace(" ", "_")
        for j, f in enumerate(choisis):
            nom = f"{zone}_{slug}.tile" if j == 0 else f"{zone}_{slug}_f{j}.tile"
            im = np.array(Image.open(f).convert("RGBA"))
            info = TR.ecrire(os.path.join(dst, nom), im)
            if j == 0:
                rap.append(dict(calque=c["nom"], banque=nom, dessins=len(choisis),
                                **{x: info[x] for x in
                                   ("entrees", "positions", "vides_omises",
                                    "uniques", "reemploi", "planche", "octets")}))
    json.dump(rap, open(os.path.join(dst, "rapport.json"), "w"), indent=1)
    return rap


if __name__ == "__main__":
    for z in sys.argv[1:]:
        r = exporter(z)
        tot = sum(x["entrees"] for x in r)
        print(f"{z}")
        print(f"   {'calque':16s} {'banques':>7s} {'entrees':>8s} {'uniques':>8s} "
              f"{'reemploi':>8s} {'Ko':>7s}")
        for x in r:
            print(f"   {x['calque']:16s} {x['dessins']:7d} {x['entrees']:8d} "
                  f"{x['uniques']:8d} {x['reemploi']:7.2f}x {x['octets']//1024:6d}")
        print(f"   total {tot} cases de 8 px")
