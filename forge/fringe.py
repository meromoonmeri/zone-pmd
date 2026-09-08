"""
forge/fringe.py — le calque Fringe de Palika, celui qui me manquait.

Sur `altere_pond`, Fringe pose 2 075 tuiles et il est dessine **en dernier**,
donc par-dessus le joueur : ce sont les debords d'herbe, les levres de roche et
les liserés de rive qui recouvrent ce qui passe dessous. Chez moi ce n'etait
qu'un contour d'un pixel a 102 tuiles.

Principe de pose : on prend le **bord bas** d'un masque de terrain (les pixels
du masque dont le voisin du dessous n'est pas dans le masque), on le decoupe en
segments horizontaux, et on aligne des bandes le long du segment, sommet cale
sur le bord. La bande retombe donc sur ce qui est en dessous, exactement comme
un debord.
"""
import numpy as np


def bord_bas(mask, mini=10, interdit=None):
    """Segments horizontaux du bord inferieur d'un masque.

    Renvoie une liste de (y, x0, x1) : les runs assez longs pour porter une
    bande. Un bord vertical ne donne rien, et c'est voulu — une bande de debord
    posee sur un bord vertical se lit comme un accident.
    """
    m = mask.astype(bool)
    dessous = np.zeros_like(m)
    dessous[:-1] = m[1:]
    bord = m & ~dessous
    if interdit is not None:
        # Un debord ne doit jamais retomber dans l'eau : il y ferait un banc
        # opaque en travers de la nappe. On coupe ces bords-la.
        sous = np.zeros_like(m)
        sous[:-3] = interdit[3:]
        bord &= ~sous & ~interdit
    segments = []
    for y in range(bord.shape[0]):
        ligne = bord[y]
        if not ligne.any():
            continue
        x = 0
        idx = np.flatnonzero(ligne)
        deb = idx[0]
        prec = idx[0]
        for x in idx[1:]:
            if x != prec + 1:
                if prec - deb + 1 >= mini:
                    segments.append((y, deb, prec))
                deb = x
            prec = x
        if prec - deb + 1 >= mini:
            segments.append((y, deb, prec))
    return segments


def poser(mask, objets, rng, mini=10, recouvrement=0.82, saut=1,
          decalage_y=-2, max_pieces=4000, interdit=None):
    """Aligne des bandes le long du bord bas de `mask`.

    `recouvrement` : pas d'avance en fraction de la largeur de la bande. En
    dessous de 1 les bandes se chevauchent un peu, ce qui evite les coutures.
    `decalage_y` : remonte legerement la bande pour qu'elle morde sur le terrain
    au lieu de flotter.
    """
    if not objets:
        return []
    segs = bord_bas(mask, mini, interdit)
    rng.shuffle(segs)
    poses = []
    for k, (y, x0, x1) in enumerate(segs):
        if k % saut:
            continue
        x = x0
        garde = 0
        while x < x1 and garde < 400 and len(poses) < max_pieces:
            garde += 1
            o = objets[int(rng.integers(0, len(objets)))]
            w = o["img"].shape[1]
            poses.append((y + decalage_y, int(x), o))
            x += max(4, int(w * recouvrement))
    return poses


def poser_surplomb(mask, objets, rng, nombre=26, marge=8):
    """Feuillage suspendu, pour Objects Over : cale sur le bord HAUT du masque.

    Chez lui, Objects Over ne compte que 150 tuiles : c'est ponctuel, pas un
    tapis. On en pose donc peu, et seulement la ou il y a de quoi surplomber.
    """
    if not objets:
        return []
    m = mask.astype(bool)
    dessus = np.zeros_like(m)
    dessus[1:] = m[:-1]
    bord = m & ~dessus
    ys, xs = np.nonzero(bord)
    if len(xs) == 0:
        return []
    poses, pris = [], []
    for _ in range(nombre * 6):
        if len(poses) >= nombre:
            break
        i = int(rng.integers(0, len(xs)))
        x, y = int(xs[i]), int(ys[i])
        if any((x - a) ** 2 + (y - b) ** 2 < 34 ** 2 for a, b in pris):
            continue
        pris.append((x, y))
        o = objets[int(rng.integers(0, len(objets)))]
        poses.append((y - marge, x - o["img"].shape[1] // 2, o))
    return poses
