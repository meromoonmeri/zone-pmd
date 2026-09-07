"""
forge/water_pmd.py — eau animee EXACTEMENT comme dans Explorers of Sky.

La technique du jeu, et rien d'autre :

  * les pixels de l'eau ne bougent JAMAIS. Le champ d'indices est calcule une
    fois pour toutes ;
  * l'animation est un **palette cycling** : seules les entrees de la ligne de
    palette affectee a l'eau changent de couleur au fil du temps ;
  * les demi-teintes viennent d'un **tramage ordonne** entre deux nuances
    voisines, pas d'un degrade continu (le DS n'a que 16 couleurs par tuile) ;
  * le pas d'animation est lent et discret : Beach Cave change de couleur
    toutes les 20 frames moteur, soit ~333 ms. Pas d'interpolation.

Sources : SilverDeoxys563 (rip des tilesets EoS), TCRF (« palette animation for
the water as well as dithering between water color shades »), wiki SkyTemple
(« [dungeon backgrounds] can not have animated chunks but they can have
animated palettes »).

Budget palette : le DS donne 16 couleurs par tuile 8x8. Les 16 sont utilisees :

    index  0 ..  2  eau plate, 3 nuances de profondeur   (STATIQUE)
    index  3 .. 14  reflets animes = 3 nuances x 4 phases (CYCLE)
    index 15        ecume de rive                         (CYCLE aussi)

La majeure partie de la nappe est donc un degrade tramé immobile ; seuls les
tirets de reflet cyclent. C'est ce que donnent les fonds de map d'EoS. Pour
l'eau de donjon, ou toute la ligne de palette cycle, passer `tout_anime=True`.

A chaque pas, la couleur de la phase a devient celle de la phase (a + s) % 4 :
la crete de lumiere saute de tiret en tiret sans qu'un seul pixel ait change
d'index.
"""
import numpy as np

from . import core as C
from .animate import fbm

# tramage ordonne 8x8 (Bayer). C'est la trame que le DS utilise pour fondre
# deux nuances voisines sans avoir de troisieme couleur a depenser.
# Bayer 4x4 : c'est la trame serree du DS. En 8x8 la grille se voit a l'oeil nu
# sur les grandes surfaces, ce qui ne ressemble a rien de ce que fait le jeu.
BAYER4 = np.array([[0, 8, 2, 10],
                   [12, 4, 14, 6],
                   [3, 11, 1, 9],
                   [15, 7, 13, 5]], np.float32) / 16.0

NIVEAUX = 3       # nuances de profondeur (le DS en met peu, la trame comble)
PHASES = 4        # phases de reflet par nuance
IDX_PLAT = 0      # 0..2   : eau plate
IDX_REFLET = 3    # 3..14  : reflets animes
IDX_ECUME = 15    # 15     : ecume de rive

# profil de crete : une bande vive, une tiede, deux eteintes.
# En tournant d'un cran par pas, la bande vive traverse la nappe.
# Mesure faite sur les vrais fonds du jeu (ref_etude/D17P31A) : entre le bleu de
# fond et une ligne de reseau il n'y a qu'une VINGTAINE de niveaux de luminance.
# La crete precedente en mettait 99 : ca donnait des traits blancs colles sur un
# aplat, ce qui ne ressemble a rien de ce que fait EoS.
CRETE = np.array([1.00, 0.55, 0.15, 0.00], np.float32)

# la rive respire sur le meme cycle : l'ecume s'allume et s'eteint entre le ton
# clair de l'eau et la couleur d'ecume. Une seule entree, quatre valeurs.
RIVE = np.array([1.00, 0.62, 0.30, 0.62], np.float32)

# Le blanc vif existe bien dans EoS, mais UNIQUEMENT colle a la berge : sur
# D01P41A, 22 % des pixels a 1 px du bord depassent L=200, contre 11 % au large.
# C'est l'ecume (index 15) qui le porte, pas le corps de la nappe.


def champ_indices(mask, seed=0, bande=11.0, ondulation=6.0, rive=2,
                  portee=None, durcissement=1.9, densite=0.46,
                  tout_anime=False, finesse=0.085, epaisseur_reseau=0.17):
    """Champ d'indices de palette, calcule UNE FOIS. Ne bougera plus jamais.

    Renvoie (idx, infos) avec idx : uint8, 255 = hors de l'eau.
    """
    h, w = mask.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    dedans = mask.astype(bool)

    # --- profondeur : distance reelle au rivage, pas un flou --------------- #
    from scipy import ndimage
    dist = ndimage.distance_transform_edt(dedans).astype(np.float32)
    # Bande de rive etroite, pas un degrade sur toute la nappe : le jeu
    # eclaircit le bord sur quelques cases, le large reste d'un bleu uni.
    # La portee suit la taille de la nappe, sinon un ruisseau ressort tout clair
    # et un ocean tout sombre.
    if portee is None:
        large = float(np.percentile(dist[dedans], 92)) if dedans.any() else 8.0
        portee = float(np.clip(large * 0.85, 5.0, 40.0))
    clair = (1.0 - np.clip(dist / portee, 0, 1)) ** durcissement

    # --- le corps de la nappe n'est JAMAIS un aplat -------------------------- #
    # Sur D17P31A la luminance de l'eau va de 56 (p5) a 199 (p95) sans trou : la
    # surface est mouchetee partout. Un aplat + des traits clairs, c'est ce qui
    # faisait "pas PMD". On melange donc la profondeur avec un grain fbm avant
    # de tramer, pour que chaque coin de la nappe ait sa propre nuance.
    grain = 0.62 * fbm(h, w, 4, 3, seed + 11) + 0.38 * fbm(h, w, 9, 2, seed + 12)
    valeur = np.clip(0.70 * clair + 0.72 * (grain - 0.5) + 0.12, 0, 1)
    # Sature : sans ca la valeur reste au milieu de la plage sur de grandes
    # surfaces, et le tramage ordonne y dessine un damier regulier visible a
    # l'oeil. Sur les vrais fonds les tons sont PLEINS, et la trame n'apparait
    # que dans la bande de transition entre deux tons.
    valeur = np.clip(0.5 + (valeur - 0.5) * 2.6, 0, 1)

    # --- trame ordonnee entre deux nuances voisines ------------------------ #
    x = valeur * (NIVEAUX - 1)
    bas = np.floor(x)
    # Les fonds d'EoS sont trames a la main : le motif n'est pas parfaitement
    # regulier. On casse donc la grille de Bayer avec un peu de bruit, sinon on
    # lit un damier mecanique la ou le jeu montre un moucheté organique.
    rng = np.random.default_rng(seed + 77)
    trame = (0.70 * np.tile(BAYER4, (h // 4 + 1, w // 4 + 1))[:h, :w]
             + 0.30 * rng.random((h, w)).astype(np.float32))
    niv = np.clip(bas + ((x - bas) > trame), 0, NIVEAUX - 1).astype(np.int32)

    # --- reflets : un RESEAU de lignes de niveau, pas des tirets ------------ #
    # C'est la forme exacte qu'on lit sur D17P31A : des boucles fermees, fines,
    # irregulieres, qui se croisent. On les obtient comme lignes de niveau d'un
    # champ fbm lisse : |u - round(u)| petit => on est sur un contour.
    lisse = fbm(h, w, 4, 4, seed + 21) + 0.35 * fbm(h, w, 8, 3, seed + 23)
    lisse = (lisse - lisse.min()) / max(1e-6, np.ptp(lisse))
    u = lisse / max(1e-4, finesse)
    anneau = np.round(u).astype(np.int32)
    ecart = np.abs(u - anneau)                     # 0 exactement sur la ligne
    # epaisseur modulee : les lignes s'amincissent et se coupent, comme dans le jeu
    ep = epaisseur_reseau * (0.45 + 1.10 * fbm(h, w, 9, 2, seed + 22))
    tiret = dedans & (ecart < ep)
    if tout_anime:                                 # mode eau de donjon
        tiret = dedans
    idx = np.full((h, w), 255, np.uint8)
    idx[dedans] = (IDX_PLAT + niv[dedans]).astype(np.uint8)
    # chaque anneau du reseau demarre sur une phase differente : au fil des pas,
    # la crete de lumiere traverse le reseau de boucle en boucle.
    phase = np.mod(anneau + (3.0 * fbm(h, w, 6, 2, seed + 24)).astype(np.int32), PHASES)
    idx[tiret] = (IDX_REFLET + niv[tiret] * PHASES + phase[tiret]).astype(np.uint8)

    # --- ecume de rive, tramee : le DS ne peut pas faire de degrade -------- #
    bord = dedans & (dist <= rive + 1)
    dens_ecume = np.clip((rive + 1 - dist) / (rive + 1), 0, 1)
    idx[bord & (dens_ecume > trame)] = IDX_ECUME

    infos = dict(niveaux=NIVEAUX, phases=PHASES, entrees=16, portee_px=round(portee, 1),
                 index_ecume=IDX_ECUME, index_reflet=IDX_REFLET,
                 bande_px=bande, densite_reflets=float(tiret.sum()) / max(1, dedans.sum()),
                 tout_anime=bool(tout_anime))
    return idx, infos


def palette(ramp, ecume, pas, calme=1.0, depart=0.32):
    """Table de 16 couleurs a l'instant `pas`. C'est la SEULE chose qui change.

    Entrees 0..2 et 15 : constantes. Entrees 3..14 : cyclees.
    """
    # On ne prend PAS le ton le plus sombre de la rampe comme fond : dans EoS
    # le corps de l'eau est une teinte moyenne, le tres sombre ne sert que de
    # reserve pour les grands fonds. D'ou le decalage `depart`.
    tons = _echantillonner(ramp, NIVEAUX, depart=depart)
    crete = np.array(C.hex2rgb(ecume), np.float32)
    pal = np.zeros((16, 3), np.float32)
    for b in range(NIVEAUX):
        pal[IDX_PLAT + b] = tons[b]
    clair = np.array(tons[-1], np.float32)
    pal[IDX_ECUME] = clair + (crete - clair) * float(RIVE[pas % PHASES])
    amp = 0.11 + 0.07 * min(1.5, calme)
    for b in range(NIVEAUX):
        base = np.array(tons[b], np.float32)
        for a in range(PHASES):
            k = float(CRETE[(a + pas) % PHASES])
            pal[IDX_REFLET + b * PHASES + a] = base + (crete - base) * (amp * k)
    return C.ds_quant(np.clip(pal, 0, 255).astype(np.uint8).reshape(1, 16, 3)).reshape(16, 3)


def _echantillonner(ramp, k, depart=0.0):
    """k nuances prises dans la portion [depart, 1] d'une rampe hexadecimale."""
    cols = [C.hex2rgb(c) for c in ramp]
    out = []
    lo = depart * (len(cols) - 1)
    for i in range(k):
        p = lo + i * ((len(cols) - 1) - lo) / max(1, k - 1)
        a, b = int(np.floor(p)), min(len(cols) - 1, int(np.ceil(p)))
        f = p - a
        out.append(tuple(int(round(cols[a][c] * (1 - f) + cols[b][c] * f)) for c in range(3)))
    return out


def water_layer(mask, ramp, n=12, seed=0, foam=True, foam_color=None, calm=1.0,
                maintien=3, bande=11.0, tout_anime=False, depart=0.32):
    """n RGBA de la nappe d'eau, a la maniere EoS.

    `maintien` : nombre de frames de sortie pendant lesquelles la palette ne
    bouge pas. Avec n=12 et maintien=3, la palette avance 4 fois par boucle,
    soit un pas toutes les 3 x 110 = 330 ms — la cadence relevee sur Beach Cave
    (20 frames moteur a 60 Hz = 333 ms).
    """
    if not mask.any():
        return [np.zeros(mask.shape + (4,), np.uint8) for _ in range(n)]
    idx, infos = champ_indices(mask, seed=seed, bande=bande,
                               rive=2 if foam else 0, tout_anime=tout_anime)
    ec = foam_color or ramp[-1]
    dedans = idx != 255
    sortie = []
    for t in range(n):
        pas = (t // maintien) % PHASES
        pal = palette(ramp, ec, pas, calme=calm, depart=depart)
        img = np.zeros(mask.shape + (4,), np.uint8)
        img[dedans, :3] = pal[idx[dedans]]
        img[..., 3] = np.where(dedans, 255, 0)
        sortie.append(img)
    return sortie


def preuve(mask, ramp, foam_color, seed=0, maintien=3, n=12, tout_anime=False):
    """Materiel de controle. Prouve que l'animation ne touche QUE la palette.

    Methode : on re-rend les n frames avec une palette DEBUG de 16 couleurs
    toutes distinctes et constantes. Si le champ d'indices ne bouge pas, les n
    images sortent rigoureusement identiques.
    """
    idx, infos = champ_indices(mask, seed=seed, tout_anime=tout_anime)
    pals = [palette(ramp, foam_color, s) for s in range(PHASES)]
    debug = np.array([[(i * 16 + 8), (255 - i * 15), ((i * 37) % 256)]
                      for i in range(16)], np.uint8)
    dedans = idx != 255
    ref = None
    identique = True
    for t in range(n):
        img = np.zeros(mask.shape + (3,), np.uint8)
        img[dedans] = debug[idx[dedans]]           # palette figee -> image figee
        if ref is None:
            ref = img
        elif not np.array_equal(ref, img):
            identique = False
    frames = water_layer(mask, ramp, n=n, seed=seed, foam_color=foam_color,
                         maintien=maintien, tout_anime=tout_anime)
    couleurs = [len(np.unique(f[..., :3][f[..., 3] > 0].reshape(-1, 3), axis=0))
                for f in frames]
    import hashlib
    etats = len({hashlib.md5(f.tobytes()).digest() for f in frames})
    return dict(infos=infos, palettes=[p.tolist() for p in pals],
                indices_constants=bool(identique),
                entrees_utilisees=int(len(np.unique(idx[idx != 255]))),
                couleurs_par_frame=couleurs, etats_distincts=etats,
                ms_par_pas=maintien * 110)
