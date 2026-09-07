"""
forge/water_halcyon.py — l'eau a la maniere de Palika (Halcyon, PMDO).

Releve fait directement sur ses fichiers : `Content/Tile/Altere_Pond_River_
Animations.tile` decode en planche, et `Data/Ground/altere_pond.rsground`.

Ce qu'il fait, et qui n'a RIEN a voir avec le palette cycling d'Explorers of Sky :

  * la nappe est animee par de **vraies frames redessinees**. Sa planche
    contient la meme mare **quatre fois de suite**, sur fond magenta, avec une
    periode de 336 px ; le ground map pointe des listes `Frames` de longueur 4
    (1 700 tuiles) ou 8 (160 tuiles) ;
  * le corps de l'eau est **un aplat d'une seule couleur**. Sur Altere Pond,
    #83dae6 couvre 78,6 % de la nappe. Pas de tramage, pas de degrade, pas de
    reseau ;
  * toute l'eau ne compte que **15 couleurs** ;
  * la berge porte une **bande sombre** de 2 a 4 px (#5787bf, #5291c5) qui suit
    le rivage, avec un bord interieur adouci ;
  * l'animation, ce sont quelques **traits clairs** en virgule plaques contre
    cette bande, redessines a chaque frame. Entre deux frames, ~6 600 px
    changent, dont 5 575 a l'interieur et seulement 1 063 sur le liseré : ce
    sont bien les traits qui bougent, pas le contour.

On garde sa structure et ses rapports de valeurs, mais les teintes viennent de
la rampe de la zone : une mare de village reste cyan clair, une coulee de lave
reste orange. C'est sa methode, pas ses pixels.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import core as C

FRAMES = 4          # comme sa planche : 4 copies cote a cote
LISERE = 4          # epaisseur totale de la bande de berge, en px


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def palette(ramp, ecume, clarte=1.0):
    """Les 5 tons d'une nappe facon Halcyon, tires de la rampe de la zone.

    Palika n'en utilise pas davantage : un aplat, deux tons de liseré, deux
    tons de trait clair.
    """
    r = [np.array(_rgb(c), np.float32) for c in ramp]
    n = len(r)

    def pt(u):
        u = float(np.clip(u, 0, 1)) * (n - 1)
        i = int(np.floor(u)); f = u - i
        j = min(i + 1, n - 1)
        return r[i] * (1 - f) + r[j] * f

    corps = pt(0.78 + 0.16 * clarte)          # l'aplat : le haut de la rampe
    lis_i = pt(0.46)                          # liseré interieur
    lis_m = pt(0.34)                          # liseré median
    lis_e = pt(0.20)                          # liseré exterieur, le plus sombre
    ec = np.array(_rgb(ecume), np.float32)
    # Palika compte 15 couleurs, pas 5 : il y a des tons intermediaires entre
    # l'aplat et le trait clair, et le liseré est adouci sur trois valeurs.
    trait = ec * 0.55 + corps * 0.45
    trait2 = ec * 0.75 + corps * 0.25
    eclat = ec * 0.98 + np.float32(6.0)
    creux = corps * 0.80 + lis_i * 0.20       # leger creux, sous l'aplat
    tons = [corps, lis_i, lis_m, lis_e, trait, trait2, eclat, creux]
    return [tuple(int(v) for v in C.ds_quant(np.clip(t, 0, 255)
                                             .astype(np.uint8).reshape(1, 1, 3))[0, 0])
            for t in tons]


def _traits(dist, dedans, rng, n_traits, longueur, large=False, ecart=11):
    """Les virgules claires plaquees contre la berge, pour UNE frame."""
    h, w = dist.shape
    toile = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(toile)

    # candidats : une couronne juste en dedans du liseré, comme chez lui
    # Palika ne colle pas tout au bord : 84 % de ce qui bouge est a l'interieur.
    plafond = LISERE + (0.55 * float(dist.max()) if large else 10.0)
    zone = dedans & (dist > LISERE + 1) & (dist < plafond)
    ys, xs = np.nonzero(zone)
    if len(xs) == 0:
        return np.zeros((h, w), bool)

    # gradient de la distance = normale au rivage ; on trace le long du rivage
    gy, gx = np.gradient(dist)
    pris = rng.choice(len(xs), size=min(n_traits, len(xs)), replace=False)
    place = []
    for k in pris:
        x0, y0 = int(xs[k]), int(ys[k])
        if any((x0 - a) ** 2 + (y0 - b) ** 2 < ecart ** 2 for a, b in place):
            continue
        place.append((x0, y0))
        nx, ny = gx[y0, x0], gy[y0, x0]
        m = np.hypot(nx, ny) or 1.0
        tx, ty = -ny / m, nx / m               # tangente au rivage
        L = longueur * (0.7 + 0.6 * rng.random())
        courbe = (rng.random() - 0.5) * 0.9
        pts = []
        for s in np.linspace(-0.5, 0.5, 7):
            cx = x0 + tx * L * s - nx / m * courbe * L * (0.25 - s * s)
            cy = y0 + ty * L * s - ny / m * courbe * L * (0.25 - s * s)
            pts.append((cx, cy))
        d.line(pts, fill=255, width=1)
    return np.array(toile) > 0


def water_layer(mask, ramp, n=12, seed=0, foam="#ffffff", foam_color=None,
                calm=1.0, maintien=None, **_):
    """n calques RGBA. L'animation est un cycle de FRAMES dessins differents.

    `maintien` : nombre de frames de sortie par dessin. Par defaut n // FRAMES,
    ce qui donne pile un tour de cycle sur la boucle.
    """
    from scipy import ndimage
    ecume = foam_color or foam
    dedans = mask.astype(bool)
    h, w = dedans.shape
    dist = ndimage.distance_transform_edt(dedans).astype(np.float32)
    (corps, lis_i, lis_m, lis_e, trait, trait2, eclat,
     creux) = palette(ramp, ecume, clarte=float(np.clip(calm, 0, 1.5)))

    if maintien is None:
        maintien = max(1, n // FRAMES)

    # --- la partie fixe : aplat + liseré ---------------------------------- #
    fixe = np.zeros((h, w, 4), np.uint8)
    fixe[dedans] = (*corps, 255)
    fixe[dedans & (dist <= LISERE + 2)] = (*lis_i, 255)
    fixe[dedans & (dist <= LISERE)] = (*lis_m, 255)
    fixe[dedans & (dist <= LISERE / 2)] = (*lis_e, 255)

    dessins = []
    for f in range(FRAMES):
        rng = np.random.default_rng(seed * 977 + f * 31 + 7)
        a = fixe.copy()
        # deux passes : des traits longs pales, des ponctuations courtes vives
        # Chez lui ~6 600 px changent d'une frame a l'autre, dont 84 % a
        # l'interieur de la nappe : ce sont bien les traits qui bougent.
        t0 = _traits(dist, dedans, rng, 260, 16.0, large=True)
        t1 = _traits(dist, dedans, rng, 220, 12.0)
        t2 = _traits(dist, dedans, rng, 120, 6.0)
        a[t0 & dedans] = (*creux, 255)
        a[t1 & dedans] = (*trait, 255)
        a[t2 & dedans] = (*trait2, 255)
        a[t2 & dedans & (dist > LISERE + 3)] = (*eclat, 255)
        dessins.append(a)

    return [dessins[(t // maintien) % FRAMES] for t in range(n)]


def preuve(mask, ramp, foam, seed=0, n=12, maintien=None, **_):
    """Le meme controle que pour l'eau Sky, mais sur les criteres de Palika."""
    couches = water_layer(mask, ramp, n=n, seed=seed, foam_color=foam,
                          maintien=maintien)
    dedans = mask.astype(bool)
    uniques = []
    for a in couches:
        uniques.append({tuple(v) for v in a[dedans][:, :3]})
    toutes = set().union(*uniques)
    a0 = couches[0]
    vals, cpt = np.unique(a0[dedans][:, :3], axis=0, return_counts=True)
    part_aplat = float(cpt.max()) / max(1, cpt.sum())
    distincts = []
    for a in couches:
        if not any((a[dedans] == b[dedans]).all() for b in distincts):
            distincts.append(a)
    diffs = []
    for k in range(1, len(distincts)):
        diffs.append(int(((distincts[k] != distincts[0]).any(-1) & dedans).sum()))
    return dict(methode="frames redessinees (Palika / Halcyon)",
                frames_du_cycle=FRAMES,
                dessins_distincts=len(distincts),
                couleurs_totales=len(toutes),
                part_de_l_aplat=round(part_aplat, 3),
                px_changes_par_frame=diffs,
                liseré_px=LISERE,
                ms_par_dessin=None)
