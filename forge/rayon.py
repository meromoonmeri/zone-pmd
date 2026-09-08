"""
forge/rayon.py — colonne de lumiere arc-en-ciel, animee par palette cycling.

Demande : « la colonne de lumiere doit avoir des frames qui montrent des airs
arc-en-ciel ». Autrement dit ce n'est pas un degrade arc-en-ciel fige, c'est la
TEINTE qui defile au fil des frames.

Technique retenue, la meme que l'eau d'Explorers of Sky : **aucun pixel ne
bouge**. On calcule une fois pour toutes un champ d'indices — quelle bande de
la colonne chaque pixel occupe — et a chaque frame on ne change que la couleur
associee a chaque indice. La teinte tourne donc dans le spectre pendant que la
geometrie reste immobile.

La translucidite est faite au TRAMAGE, pas en alpha : la DS melangeait par
stipple ordonne. Un Bayer 4x4 module par l'intensite donne ce grain-la, et ca
evite le voile lisse et moderne qui trahirait tout de suite un effet actuel.
"""
import colorsys

import numpy as np

from . import core as C

BAYER4 = np.array([[0, 8, 2, 10],
                   [12, 4, 14, 6],
                   [3, 11, 1, 9],
                   [15, 7, 13, 5]], np.float32) / 16.0

BANDES = 12          # nombre de bandes dans l'epaisseur du faisceau


def champ(h, w, x_centre, y_haut, y_bas, large_haut, large_bas,
          seed=0, flou=0.30, bandes=BANDES):
    """Geometrie du faisceau, calculee une seule fois.

    Renvoie (intensite, indice, axe) :
      intensite  float 0..1, la force lumineuse en chaque pixel
      indice     uint8, la bande du spectre a laquelle le pixel appartient
      axe        float 0..1, 1 sur l'axe du faisceau et 0 sur ses bords.
                 Sert a blanchir le coeur : sans lui, les bandes jaunes se
                 confondaient avec le sable et la colonne devenait illisible
                 entre les racines et le bassin.
    """
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)

    # profil vertical : le faisceau s'ouvre en descendant
    t = np.clip((yy - y_haut) / max(1.0, (y_bas - y_haut)), 0.0, 1.0)
    demi = (large_haut + (large_bas - large_haut) * t) * 0.5

    # ondulation douce du bord, pour que la colonne ne soit pas un rectangle
    onde = (np.sin(yy / 23.0 + 0.7) * 2.4 + np.sin(yy / 9.0) * 1.1)
    dx = np.abs(xx - (x_centre + onde))
    u = dx / np.maximum(demi, 1.0)              # 0 au coeur, 1 au bord

    dedans = (yy >= y_haut) & (yy <= y_bas + 26)
    # Profil en PLATEAU, pas en puissance : un faisceau de lumiere volumetrique
    # a un coeur d'intensite constante et des bords qui s'estompent. Une courbe
    # en puissance ne laissait qu'un filet brillant au centre.
    coeur = np.clip((1.0 - u) / max(0.05, flou), 0.0, 1.0)
    inten = coeur * 0.86 + 0.14 * np.clip(1.0 - u, 0.0, 1.0)

    # attenuation en haut (la lumiere naît dans le feuillage). En bas le
    # faisceau doit ATTEINDRE le sol : l'attenuation precedente le coupait
    # avant le bassin et laissait un trou entre le rayon et sa flaque.
    inten *= np.clip((yy - y_haut) / 22.0, 0.0, 1.0)
    inten *= np.clip((y_bas + 54 - yy) / 46.0, 0.0, 1.0)
    inten *= dedans

    # un peu de grain vertical : des filets de poussiere dans le faisceau
    filet = 0.82 + 0.18 * np.sin(xx * 1.7 + rng.random() * 6.28)
    inten *= filet

    # l'indice de bande suit la POSITION dans l'epaisseur, pas l'intensite :
    # c'est ce qui donne des lames de couleur bien lisibles quand la teinte
    # defile.
    sens = np.sign(xx - x_centre)
    v = np.clip(0.5 + 0.5 * sens * u, 0.0, 1.0)
    idx = np.clip((v * (bandes - 1)).round(), 0, bandes - 1).astype(np.uint8)
    axe = (np.clip(1.0 - u, 0.0, 1.0) * dedans).astype(np.float32)
    return inten.astype(np.float32), idx, axe


def palette(phase, bandes=BANDES, satur=0.90, valeur=1.0, etendue=0.85):
    """Les `bandes` couleurs du spectre, decalees de `phase` (0..1).

    `etendue` < 1 evite de reboucler exactement sur le rouge : le faisceau
    balaie une portion du spectre plutot que la roue entiere, ce qui se lit
    mieux qu'un arc-en-ciel complet ecrase dans quelques pixels.
    """
    out = []
    for i in range(bandes):
        h = ((i / max(1, bandes - 1)) * etendue + phase) % 1.0
        r, g, b = colorsys.hsv_to_rgb(h, satur, valeur)
        out.append([int(r * 255), int(g * 255), int(b * 255)])
    return np.array(C.ds_quant(np.array(out, np.uint8).reshape(1, -1, 3))[0],
                    np.int16)


def poser(fond, inten, idx, phase, force=0.85, seuil=0.05, bandes=BANDES,
          rng=None, melange=0.95, axe=None):
    """Compose le faisceau sur une frame RGB deja rendue.

    Transparence a la DS : `Bayer4 < intensite` decide QUELS pixels sont
    allumes ; les autres gardent le decor intact. C'est ce stipple qui fait
    voir le tronc AU TRAVERS du faisceau au lieu d'un bandeau opaque.

    Sur les pixels allumes on tire vers la couleur plutot que d'additionner :
    l'addition pure saturait vers le blanc sur le sable clair et effacait la
    teinte, ce qui ruinait l'arc-en-ciel.
    """
    a = np.asarray(fond)[..., :3].astype(np.int16)
    h, w = a.shape[:2]
    pal = palette(phase, bandes)
    seuils = np.tile(BAYER4, (h // 4 + 1, w // 4 + 1))[:h, :w]
    force_px = np.clip(inten * force, 0.0, 1.0)
    pris = (force_px > seuil) & (seuils < force_px)
    if not pris.any():
        return a.astype(np.uint8)
    couleur = pal[idx[pris]].astype(np.float32)
    p = (force_px[pris][:, None] * melange)
    # SCREEN, pas une interpolation lineaire. De la lumiere ne peut
    # qu'eclaircir : en interpolation, les bandes bleues et violettes — dont la
    # luminance est basse — ASSOMBRISSAIENT le sable, ce qui donnait un
    # faisceau sale au lieu d'un voile lumineux.
    d = a[pris].astype(np.float32)
    # Deux operateurs combines, et on garde le plus clair des deux :
    #  - SCREEN, qui rend bien sur le tronc sombre mais s'annule sur le sable
    #    clair, ou le faisceau devenait invisible ;
    #  - un fondu vers une version PASTEL de la teinte (couleur eclaircie vers
    #    le blanc), qui reste lisible sur un fond clair.
    # Une colonne de lumiere dans l'air se voit quel que soit ce qu'il y a
    # derriere ; il faut donc un plancher de clarte, pas seulement un additif.
    ecran = 255.0 - (255.0 - d) * (255.0 - couleur * p) / 255.0
    # Le pastel doit rester TEINTE, sinon le faisceau se confond avec le sable
    # clair : c'est ce qui le faisait disparaitre entre les racines et le
    # bassin. On blanchit seulement le coeur, en fonction de l'intensite.
    # Coeur blanc, franges colorees — la structure d'un vrai puits de lumiere,
    # et celle de la reference. `axe` vaut 1 sur l'axe et 0 sur les bords.
    ax = (np.clip(axe, 0.0, 1.0) if axe is not None else np.clip(inten, 0, 1))
    bl = ax[pris][:, None]
    part_blanc = 0.16 + 0.74 * bl ** 1.5
    pastel = couleur * (1.0 - part_blanc) + 255.0 * part_blanc
    fondu = d * (1.0 - p) + pastel * p
    a[pris] = np.clip(np.maximum(ecran, fondu), 0, 255).astype(np.int16)
    return a.astype(np.uint8)


def flaque(h, w, cx, cy, rx, ry):
    """La tache de lumiere au pied du faisceau, sur le bassin."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = ((xx - cx) / max(1.0, rx)) ** 2 + ((yy - cy) / max(1.0, ry)) ** 2
    return np.clip(1.0 - d, 0.0, 1.0) ** 1.4


def preuve(inten, idx, n, bandes=BANDES):  # noqa: D401
    """Controle : la geometrie ne bouge pas, seule la palette tourne."""
    pals = [palette(t / n, bandes).tolist() for t in range(n)]
    distinctes = len({tuple(map(tuple, p)) for p in pals})
    return dict(technique="palette cycling : le champ d'indices est fige, "
                          "seules les couleurs des bandes changent",
                bandes=bandes, palettes_distinctes=distinctes, frames=n,
                pixels_du_faisceau=int((inten > 0.06).sum()),
                tramage="Bayer 4x4 module par l'intensite, pas d'alpha lisse")
