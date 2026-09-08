"""
forge/calques_halcyon.py — la structure de calques de Palika, relevee sur
`Data/Ground/altere_pond.rsground` (Halcyon).

Son ground map compte **huit calques nommes, dans un ordre fixe**, chacun avec
**son propre tilesheet** baptise `<Carte>_<Calque>` :

    #  calque          tuiles posees  animees  longueurs de Frames
    0  Base                   10 251        0  {1}
    1  River                   1 036    1 036  {4}
    2  Cliffs                  1 840        0  {1}
    3  Shadows                    56        0  {1}
    4  Objects Under             841      232  {1, 4}
    5  Objects                 4 604      592  {1, 4, 8}
    6  Objects Over              150       74  {1, 3}
    7  Fringe                  2 075        0  {1}

Grille 116 x 96 tuiles de 8 px. Trois choses a retenir :

  * **les ombres portees sont un calque a part**, pas un aplat cuit sous les
    props ;
  * **Fringe passe en dernier**, donc par-dessus tout le reste : ce sont les
    raccords de terrain et les debords qui recouvrent le joueur ;
  * le nombre de dessins distincts d'un calque anime est petit et fixe — 4 pour
    la riviere, 3 pour Objects Over.

Le tilesheet d'un calque anime est simplement le calque **dessine K fois de
suite horizontalement** sur fond magenta ; le ground map pointe une position
(x, y) differente par frame. C'est exactement ce qu'on lit sur
`Altere_Pond_River_Animations.tile` : 4 copies, periode 336 px.
"""
import os

import numpy as np
from PIL import Image

# ordre de dessin, du fond vers le dessus. Les noms sont les siens.
CALQUES = [
    ("Base",          0, 1),
    ("River",         1, 4),
    ("Cliffs",        2, 1),
    ("Shadows",       3, 1),
    ("Objects Under", 4, 4),
    ("Objects",       5, 8),   # 4 et 8 chez lui : deux sheets cohabitent
    ("Objects Over",  6, 3),
    ("Fringe",        7, 1),
]

# Repartition des props par calque. Chez lui, "Objects Under" recoit ce sur quoi
# le joueur marche, "Objects Over" ce qui le recouvre.
CAT_CLIFFS = {"cliff", "boulder", "stalagmite", "column", "pillar", "arch",
              "obsidian", "coralpillar", "icicle", "mound"}
CAT_UNDER = {"lilies", "moss", "pebble", "leaves", "tile", "coins", "shell",
             "starfish", "frost", "scree", "drygrass", "seagrass", "kelp",
             "roots", "ember", "lava", "drift", "plank", "jetty"}

DOSSIERS = {n: f"{o:02d}_{n.lower().replace(' ', '_')}" for n, o, _ in CALQUES}


def calque_de(cats):
    """Dans quel calque tombe un prop, d'apres ses categories."""
    c = set(cats if isinstance(cats, (list, tuple, set)) else [cats])
    if c & CAT_CLIFFS:
        return "Cliffs"
    if c & CAT_UNDER:
        return "Objects Under"
    return "Objects"


def dessins(n_frames, k):
    """Indice du dessin a utiliser pour chaque frame de sortie.

    K dessins distincts etales sur n_frames. K doit diviser n_frames, sinon la
    tenue est inegale et on le signale.
    """
    tenue = n_frames / k
    return [int(t // tenue) % k for t in range(n_frames)], (n_frames % k == 0)


def ecrire_planche(zone, nom, images, dossier, magenta=(255, 0, 255)):
    """Le tilesheet d'un calque : ses K dessins mis bout a bout, fond magenta.

    C'est la mise en page de Palika. Renvoie (chemin, largeur, periode).
    """
    os.makedirs(dossier, exist_ok=True)
    k = len(images)
    h, w = images[0].shape[:2]
    planche = np.zeros((h, w * k, 3), np.uint8)
    planche[:] = magenta
    for i, im in enumerate(images):
        if im.shape[2] == 4:
            a = im[..., 3:4].astype(np.float32) / 255.0
            bloc = (im[..., :3] * a + np.array(magenta, np.float32) * (1 - a))
        else:
            bloc = im[..., :3].astype(np.float32)
        planche[:, i * w:(i + 1) * w] = bloc.astype(np.uint8)
    slug = nom.replace(" ", "_")
    chemin = os.path.join(dossier, f"{zone}_{slug}.png")
    Image.fromarray(planche, "RGB").save(chemin)
    return chemin, w * k, w


def table(compte, animes, planches, n_frames):
    """La table de calques, dans son ordre et avec ses champs."""
    out = []
    for nom, ordre, k in CALQUES:
        d, regulier = dessins(n_frames, k)
        p = planches.get(nom, {})
        out.append(dict(
            ordre=ordre, nom=nom, dossier=DOSSIERS[nom],
            sheet=p.get("sheet"), periode_px=p.get("periode"),
            tuiles_posees=int(compte.get(nom, 0)),
            tuiles_animees=int(animes.get(nom, 0)),
            frames=k if animes.get(nom, 0) else 1,
            tenue_frames=(n_frames // k if regulier else None),
            tenue_reguliere=regulier,
        ))
    return out
