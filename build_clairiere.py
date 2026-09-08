"""
build_clairiere.py — la clairiere CORRIGEE et decomposee en 3 layouts (etages).

Le defaut, mesure sur les essais precedents (`recup_clairiere_v1..v3`) :
    la reference (`layers/src/recup_reference.png`) a un centre SABLE CHAUD
    (#d3c688, L=195) ; les essais sortaient un centre gris-vert (#879d85 ->
    #a2b3a6, L=148-177), ecart moyen 17,7 sur le meilleur des trois.
La correction ne retouche pas les essais : on repeint le terrain directement
dans la grammaire EoS relevee sur la reference :

    cadre sombre de vegetation -> bande d'herbe intermediaire ->
    clairiere organique sableuse claire au centre, contours durs 1 px,
    tramage ordonne entre les paliers de valeur.

Les rampes de couleur sont EXTRAITES de la reference (pas inventees) :
classe hue/luminance -> 3 tons p22/p50/p80 par materiel.

Les plaques du commit precedent sont CONSERVEES et UTILISEES :
`bordure_feuillue_sheet.png` est detouree par chroma key et ses morceaux
poses sur le cadre, en calque Objects, ou ils bloquent la marche.

Decomposition en layouts — 3 etages jouables, meme grammaire, meme palette :

    clairiere_b1f  "Lisiere du Bosquet"   jour       clairiere ouverte, sentier sud
    clairiere_b2f  "Clairiere Sacree"     crepuscule grande clairiere + mare
    clairiere_b3f  "Coeur du Bosquet"     nuit       cadre epais, mare centrale

Chaque etage sort avec son pack complet : layers/rendu/, tiled/ (24 px,
tuiles animees natives), aseprite/, pmdo/ (collision 8 px, ground.json).
`layouts/clairiere_sacree.json` decrit le donjon (etages, entrees, liens).
`planche_clairiere.html` est la planche de controle.

Usage :  python3 build_clairiere.py            # tout
         python3 build_clairiere.py --terrain  # seulement peindre les terrains
"""
import os
import sys
import json
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from PIL import Image

import forge.core as C
import forge.chroma as CHROMA
import build_zones18 as BZ

W, H = 504, 456            # la toile du depot : 21 x 19 cases de 24 px
MAGENTA = np.array([255, 0, 255], np.uint8)
COULOIR = (0.44, 0.56)     # entree sud protegee des props (convention arenes)

# --------------------------------------------------------------------------- #
# 1. Les rampes, relevees sur la reference
# --------------------------------------------------------------------------- #

DEF_CADRE = np.array([[0x3f, 0x6d, 0x34], [0x4f, 0x8d, 0x3f], [0x53, 0x85, 0x3e]], np.float32)
DEF_SOMBRE = np.array([[0x27, 0x42, 0x22], [0x27, 0x58, 0x2a], [0x32, 0x48, 0x1e]], np.float32)
DEF_HERBE = np.array([[0x47, 0x6f, 0x3a], [0x5a, 0x7d, 0x40], [0x72, 0x97, 0x54]], np.float32)
DEF_CLAIR = np.array([[0x48, 0xa7, 0x3f], [0x58, 0xa7, 0x40], [0x5c, 0xca, 0x57]], np.float32)
DEF_SABLE = np.array([[0xc6, 0xb3, 0x6c], [0xd3, 0xc6, 0x88], [0xef, 0xc6, 0x8a],
                      [0xf0, 0xd7, 0x94]], np.float32)


def extraire_rampes(chemin="layers/src/recup_reference.png"):
    """Classe les pixels de la reference par hue/luminance et releve les tons
    par materiel. Les couleurs ne sont pas choisies : elles sont prelevees.

    Le profil radial de la reference dit : pourtour vert moyen (L~110,
    #53853e) qui continue en champ, transition, puis coeur sable LUMINEUX
    (L~215, #f0d794). Le 'cadre sombre' des fonds EoS est sombre RELATIVEMENT
    au coeur — pas noir : on releve donc le cadre dans l'ANNEAU externe, et
    on garde les verts profond (v<0.40) comme accents."""
    a = np.asarray(Image.open(chemin).convert("RGB")).astype(np.float32)
    h_, w_ = a.shape[:2]
    yy, xx = np.mgrid[0:h_, 0:w_]
    dist = np.minimum(np.minimum(xx, w_ - 1 - xx),
                      np.minimum(yy, h_ - 1 - yy)) / min(w_, h_)
    mx = a.max(-1); mn = a.min(-1); d = mx - mn + 1e-9
    s = d / np.maximum(mx, 1e-9); v = mx
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    h = np.zeros_like(v)
    h = np.where(mx == r, ((g - b) / d) % 6, h)
    h = np.where(mx == g, (b - r) / d + 2, h)
    h = np.where(mx == b, (r - g) / d + 4, h)
    h = (h / 6) % 1
    vert = (h >= 0.20) & (h <= 0.44) & (s >= 0.22)
    sable = (h >= 0.055) & (h <= 0.16) & (v >= 0.58) & (s >= 0.20)

    def tons(mask, defaut, qs=(0.22, 0.50, 0.80)):
        px = a[mask]
        if len(px) < 400:
            return np.array(defaut, np.float32)
        lum = px @ np.array([0.299, 0.587, 0.114], np.float32)
        px = px[np.argsort(lum)]
        return np.array([px[int(q * (len(px) - 1))] for q in qs], np.float32)

    return dict(
        # le cadre : releve dans l'anneau externe de la reference (L~110)
        cadre=tons(vert & (dist < 0.25), DEF_CADRE),
        # les verts profonds : accents, trous de feuillage (L~72)
        sombre=tons(vert & (v < 0.40), DEF_SOMBRE),
        herbe=tons(vert & (v >= 0.40) & (v < 0.66), DEF_HERBE),
        clair=tons(vert & (v >= 0.66), DEF_CLAIR),
        # 4 tons pour le sable : la reference va du tan a coeur #f0d794 (L=215)
        sable=tons(sable, DEF_SABLE, qs=(0.15, 0.40, 0.68, 0.90)),
    )


# --------------------------------------------------------------------------- #
# 2. Le peintre de terrain
# --------------------------------------------------------------------------- #

def _dither(seed):
    """0.70 Bayer + 0.30 aleatoire : la trame ordonnee qui ne se voit pas
    comme une grille (regle relevee sur l'eau, appliquee aux sols)."""
    rng = np.random.default_rng(seed)
    b = np.tile(C.BAYER8, (H // 8 + 2, W // 8 + 2))[:H, :W]
    return 0.70 * b + 0.30 * rng.random((H, W))


def _bord_interne(mask):
    """Les pixels du masque adjacents a son exterieur -> pose des contours durs."""
    e = np.zeros_like(mask)
    e[1:, :] |= ~mask[:-1, :]
    e[:-1, :] |= ~mask[1:, :]
    e[:, 1:] |= ~mask[:, :-1]
    e[:, :-1] |= ~mask[:, 1:]
    return e & mask


def peindre_terrain(rampes, spec):
    """Un terrain 504x456 dans la grammaire de la reference.

    Ordre : herbe de fond -> cadre sombre -> clairiere + sentier sableux ->
    mare en magenta (trou d'eau exact pour le pipeline) -> contours durs 1 px.
    """
    seed = spec["seed"]
    rng = np.random.default_rng(seed)
    dith = _dither(seed)
    n_herbe = C.fbm(H, W, 7, 4, seed=seed + 1)
    n_cadre = C.fbm(H, W, 5, 4, seed=seed + 2)
    n_sable = C.fbm(H, W, 6, 4, seed=seed + 3)
    touffes = C.fbm(H, W, 9, 3, seed=seed + 4)
    feuilles = C.fbm(H, W, 8, 3, seed=seed + 5)
    yy, xx = np.mgrid[0:H, 0:W]

    # le cadre suit les bords de la carte, avec une limite interieure organique
    fall = C.frame_falloff(H, W, spec["pad"])
    wob = (C.fbm(H, W, 4, 3, seed=seed + 6) - 0.5) * 2 * spec["wobble_cadre"]
    cadre = fall < spec["cadre_thr"] + wob

    # la clairiere : une tache organique claire au centre
    cl = spec["clair"]
    clair = C.blob_mask(H, W, seed + 7, cl["cx"], cl["cy"], cl["rx"], cl["ry"],
                        cl["wobble"], 3)

    # le sentier sud : bande sableuse qui part du coeur et sort au bord bas,
    # gardee dans le couloir protege (0.44-0.56 de largeur) pour rester libre
    xs = W * 0.5 + spec["chemin_sinus"] * np.sin(yy / H * 2.4 + seed * 0.37)
    chemin = (np.abs(xx - xs) < spec["chemin_larg"]) & \
             (yy > (cl["cy"] + cl["ry"] * 0.45) * H - 24)
    sable = clair | chemin

    # la mare : magenta pur, le pipeline en fait le masque d'eau au pixel pres
    mare = None
    if spec.get("mare"):
        m = spec["mare"]
        mare = C.blob_mask(H, W, seed + 8, m["cx"], m["cy"], m["rx"], m["ry"],
                           m["wobble"], 3)
        if m.get("ruisseau"):
            ys = H * m["cy"] + (xx - W * m["cx"]) * 0.38 + \
                 10 * np.sin(xx / W * 9.1 + seed)
            mare |= (np.abs(yy - ys) < m["ruisseau"]) & \
                    (xx > W * (m["cx"] + m["rx"] * 0.55))

    img = np.zeros((H, W, 3), np.float32)

    # --- herbe intermediaire, 3 tons trames -------------------------------- #
    k = np.clip((n_herbe * 3 + dith).astype(int), 0, 2)
    for i in range(3):
        img[k == i] = rampes["herbe"][i]
    img[(touffes > 0.74) & (touffes <= 0.86)] = rampes["clair"][1]
    img[touffes > 0.86] = rampes["clair"][2]
    specks = rng.random((H, W)) < 0.010
    img[specks] = rampes["sombre"][1]

    # --- cadre : verts moyens de l'anneau externe + accents ---------------- #
    kc = np.clip((n_cadre * 3 + dith).astype(int), 0, 2)
    for i in range(3):
        img[cadre & (kc == i)] = rampes["cadre"][i]
    img[(feuilles > 0.72) & cadre] = rampes["herbe"][2]   # grappes eclairees
    img[(feuilles < 0.16) & cadre] = rampes["sombre"][1]  # trous de feuillage

    # --- clairiere + sentier sableux (par-dessus le cadre : le sentier
    #     entaille visiblement la vegetation jusqu'a l'entree sud) ---------- #
    ks = np.clip((n_sable * 4 + dith).astype(int), 0, 3)
    for i in range(4):
        img[sable & (ks == i)] = rampes["sable"][i]
    img[(rng.random((H, W)) < 0.016) & sable] = rampes["herbe"][1]  # brins
    img[(rng.random((H, W)) < 0.0028) & sable] = (0x8a, 0x80, 0x70)  # galets

    # --- contours durs 1 px, la signature des fonds EoS -------------------- #
    bord_sable = _bord_interne(sable) & ~cadre
    img[bord_sable] = rampes["sable"][0] * 0.90         # levre foncee du sable
    bord_cadre = _bord_interne(cadre) & ~sable
    img[bord_cadre] = rampes["sombre"][0] * 0.85        # ligne de tenebre

    out = np.clip(img + 0.5, 0, 255).astype(np.uint8)
    out = poser_bordures(out, spec)
    if mare is not None:
        out[mare] = MAGENTA
    return out


# --------------------------------------------------------------------------- #
# 2bis. La bordure feuillue en kit : posee sur le cadre du terrain
# --------------------------------------------------------------------------- #

_BORD_CACHE = None


def _charger_bordures(d="layers/cut/bordure_feuillue_sheet"):
    """Les morceaux du commit precedent, en RGBA numpy, tries par forme."""
    global _BORD_CACHE
    if _BORD_CACHE is None:
        import glob as _g
        pieces = []
        for f in sorted(_g.glob(f"{d}/bord_*.png")):
            a = np.asarray(Image.open(f).convert("RGBA"))
            if a[..., 3].sum() < 4000:
                continue
            vis = a[a[..., 3] > 0][:, :3].astype(np.float32)
            lum = (vis @ np.array([0.299, 0.587, 0.114], np.float32)).mean()
            pieces.append(dict(img=a, med_l=float(lum)))
        _BORD_CACHE = pieces
    return _BORD_CACHE


def _remonte(piece, cible=95.0):
    """La planche etait peinte 'sans rayon' (L=24-62), trop sombre pour la
    grammaire de la reference (anneau externe L~110). On remonte la
    luminance sans toucher aux teintes : le feuillage garde ses valeurs
    relatives et se pose comme un clair-obscur sur le cadre."""
    k = float(np.clip(cible / max(piece["med_l"], 1.0), 1.15, 2.3))
    a = piece["img"].astype(np.float32)
    a[..., :3] = np.clip(a[..., :3] * k, 0, 255)
    return a.astype(np.uint8), k


def _tampon(piece, echelle, rng, cible=95.0):
    """Un morceau pret a poser : remonte en luminance, mis a l'echelle,
    eventuellement miroite."""
    a, _ = _remonte(piece, cible)
    im = Image.fromarray(a)
    if rng.random() < 0.5:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    w, h = max(8, int(im.width * echelle)), max(8, int(im.height * echelle))
    return np.asarray(im.resize((w, h), Image.NEAREST))


def _poser_rgba(img, rgba, x, y):
    """Compose un RGBA sur le terrain RGB, avec clip aux bords de la toile."""
    h, w = img.shape[:2]
    ph, pw = rgba.shape[:2]
    x, y = int(x), int(y)
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(w, x + pw), min(h, y + ph)
    if x1 <= x0 or y1 <= y0:
        return
    sub = rgba[y0 - y:y1 - y, x0 - x:x1 - x]
    al = sub[..., 3:4].astype(np.float32) / 255.0
    zone = img[y0:y1, x0:x1].astype(np.float32)
    img[y0:y1, x0:x1] = (zone * (1 - al) + sub[..., :3] * al).astype(np.uint8)


def poser_bordures(img, spec, echelle=0.46):
    """Le kit de bordures feuillues du commit precedent, pose autour du cadre.

    Gros morceaux (200-440 px) le long des bords, remontes en luminance :
    c'est le feuillage peint qui habille le cadre procedural. Le couloir
    d'entree sud reste degage — la chaussee doit rester lisible jusqu'au bord.
    """
    pieces = _charger_bordures()
    if not pieces:
        return img
    rng = np.random.default_rng(spec["seed"] * 31 + 5)
    rng.shuffle(pieces)
    larges = [p for p in pieces if p["img"].shape[1] > 1.25 * p["img"].shape[0]]
    hauts = [p for p in pieces if p["img"].shape[0] > 1.25 * p["img"].shape[1]]
    pris = {id(p) for p in larges} | {id(p) for p in hauts}
    cubes = [p for p in pieces if id(p) not in pris]

    def prendre(pool, i):
        if not pool:
            pool = cubes or pieces
        return pool[i % len(pool)]

    coul_a, coul_b = int(COULOIR[0] * W) - 6, int(COULOIR[1] * W) + 6

    # bord haut : trois morceaux qui se chevauchent
    for i, x in enumerate((-30, 168, 368)):
        t = _tampon(prendre(larges, i), echelle + rng.random() * 0.06, rng)
        _poser_rgba(img, t, x, -t.shape[0] // 6)
    # flancs : deux a trois morceaux chacun
    for cote, gx in (("g", -14), ("d", W - 60)):
        for i, y in enumerate((-10, 150, 300)):
            if cote == "d" and i == 2 and y > H - 170:
                continue
            t = _tampon(prendre(hauts + cubes, i + (2 if cote == "d" else 0)),
                        echelle + rng.random() * 0.06, rng)
            _poser_rgba(img, t, gx + rng.integers(-6, 7), y)
    # bord bas : les coins seulement, le centre reste l'entree sud
    for gx in (-16, W - 88):
        t = _tampon(prendre(cubes, 3), echelle * 0.92, rng)
        _poser_rgba(img, t, gx, H - t.shape[0] + 14)
        if coul_a > 150:  # un morceau entre le coin et le couloir, s'il tient
            t2 = _tampon(prendre(larges, 5), echelle * 0.8, rng)
            if 90 + t2.shape[1] < coul_a - 8:
                _poser_rgba(img, t2, 74, H - t2.shape[0] + 10)
            t3 = _tampon(prendre(larges, 6), echelle * 0.8, rng)
            if W - 74 - t3.shape[1] > coul_b + 8:
                _poser_rgba(img, t3, W - 74 - t3.shape[1], H - t3.shape[0] + 10)
    return img


# --------------------------------------------------------------------------- #
# 3. Les trois layouts
# --------------------------------------------------------------------------- #

FLOORS = {
    "clairiere_b1f": dict(
        titre="Lisiere du Bosquet", grade="jour",
        pad=0.185, cadre_thr=0.30, wobble_cadre=0.16,
        clair=dict(cx=0.50, cy=0.54, rx=0.265, ry=0.235, wobble=0.50),
        chemin_sinus=11, chemin_larg=20, mare=None, seed=2101,
    ),
    "clairiere_b2f": dict(
        titre="Clairiere Sacree", grade="crepuscule",
        pad=0.165, cadre_thr=0.24, wobble_cadre=0.18,
        clair=dict(cx=0.47, cy=0.56, rx=0.315, ry=0.27, wobble=0.55),
        chemin_sinus=9, chemin_larg=21,
        mare=dict(cx=0.665, cy=0.38, rx=0.150, ry=0.130, wobble=0.62), seed=2102,
    ),
    "clairiere_b3f": dict(
        titre="Coeur du Bosquet", grade="nuit",
        pad=0.215, cadre_thr=0.22, wobble_cadre=0.20,
        clair=dict(cx=0.53, cy=0.60, rx=0.235, ry=0.205, wobble=0.58),
        chemin_sinus=10, chemin_larg=19,
        mare=dict(cx=0.42, cy=0.44, rx=0.165, ry=0.145, wobble=0.68,
                  ruisseau=7), seed=2103,
    ),
}

# LA carte definitive : la clairiere demandee sur la reference, en UNE map.
# C'est la reponse au faux export PMDO de la branche parallele : peinte
# NATIVEMENT en 504x456 (aucun passage par un master 1120x960, donc aucun
# reechantillonnage), avec le pack complet — collision 8 px comprise.
CLAIRIERE = dict(
    titre="La Clairiere", grade="jour",
    pad=0.175, cadre_thr=0.26, wobble_cadre=0.17,
    clair=dict(cx=0.50, cy=0.55, rx=0.295, ry=0.255, wobble=0.52),
    chemin_sinus=10, chemin_larg=20,
    mare=dict(cx=0.68, cy=0.36, rx=0.115, ry=0.100, wobble=0.62), seed=2100,
)


def R(cats, surface, count, cap=4, min_dist=30, sway=0):
    """Regle de pose locale, sans le DENSITE global : les comptes ci-dessous
    sont deja cales pour atteindre 18-45 % d'occupation (audit d'echelle)."""
    return dict(cats=cats, surface=surface, count=count, cap=cap,
                min_dist=min_dist, sway=sway)


def specs_clairiere():
    """Les specs injectees dans build_zones18.ZONES, une par etage."""
    s = {}
    s["clairiere"] = dict(           # LA carte definitive, jour, bassin compris
        titre="La Clairiere — carte corrigee",
        sheets=["prairie_props_sheet", "pic_flowers_sheet", "mousse_props_sheet",
                "lac_props_sheet", "bordure_feuillue_sheet"],
        canopy=BZ.JUNGLE_CANOPY, eau="lac",
        tint="#1c3a22", strength=0.40, grade="jour", seed=2100, couloir=COULOIR,
        rules=[
            R(["bordure"], "midband", 12, 3, 48, 1),
            R(["tree"], "midband", 15, 4, 36, 2),      # la couronne d'arbres
            R(["conifer"], "midband", 4, 2, 44, 1),
            R(["flower"], "ground", 30, 8, 16, 2),     # la clairiere fleurie
            R(["grass"], "ground", 18, 6, 18, 2),
            R(["stone"], "midband", 10, 3, 28),        # pierres du bosquet
            R(["stone"], "inner", 2, 1, 60),
            R(["reeds"], "shore", 12, 4, 20, 2),       # le bassin
            R(["lilies"], "water", 10, 4, 24, 1),
            R(["rock"], "shore", 6, 3, 30),
            R(["moss"], "ground", 12, 4, 24),
            R(["fern"], "ground", 8, 4, 26, 2),
            R(["mushroom"], "inner", 6, 3, 24, 1),
        ])
    s["clairiere_b1f"] = dict(
        titre="Lisiere du Bosquet — B1F",
        sheets=["prairie_props_sheet", "pic_flowers_sheet", "mousse_props_sheet",
                "bordure_feuillue_sheet"],
        canopy=BZ.JUNGLE_CANOPY, eau=None,
        tint="#1c3a22", strength=0.40, grade="jour", seed=2101, couloir=COULOIR,
        rules=[
            R(["bordure"], "midband", 10, 3, 56, 1),   # le cadre pose ses feuilles
            R(["tree"], "midband", 12, 4, 40, 2),      # la lisiere boisee
            R(["tree"], "ground", 10, 3, 54, 2),       # arbres epars dans le champ
            R(["boulder"], "ground", 6, 2, 40),        # rochers mousseux du bosquet
            R(["flower"], "ground", 26, 6, 18, 2),
            R(["grass"], "ground", 22, 6, 18, 2),
            R(["stone"], "midband", 7, 3, 34),
            R(["mushroom"], "inner", 8, 3, 24, 1),
            R(["fern"], "ground", 10, 4, 26, 2),
            R(["moss"], "ground", 12, 4, 24),
        ])
    s["clairiere_b2f"] = dict(
        titre="Clairiere Sacree — B2F",
        sheets=["prairie_props_sheet", "pic_flowers_sheet", "mousse_props_sheet",
                "lac_props_sheet", "bordure_feuillue_sheet"],
        canopy=BZ.JUNGLE_CANOPY, eau="lac",
        tint="#243620", strength=0.44, grade="crepuscule", seed=2102, couloir=COULOIR,
        rules=[
            R(["bordure"], "midband", 14, 3, 48, 1),
            R(["tree"], "midband", 16, 4, 34, 2),      # la couronne d'arbres
            R(["conifer"], "midband", 5, 2, 44, 1),    # silhouettes verticales
            R(["flower"], "ground", 34, 8, 16, 2),     # la clairiere fleurie
            R(["grass"], "ground", 18, 6, 18, 2),
            R(["stone"], "midband", 12, 3, 28),        # cercle de pierres
            R(["stone"], "inner", 3, 1, 60),
            R(["reeds"], "shore", 12, 4, 20, 2),       # la mare
            R(["lilies"], "water", 12, 4, 24, 1),
            R(["rock"], "shore", 8, 3, 30),
            R(["moss"], "ground", 10, 4, 24),
        ])
    s["clairiere_b3f"] = dict(
        titre="Coeur du Bosquet — B3F",
        sheets=["prairie_props_sheet", "pic_flowers_sheet", "mousse_props_sheet",
                "lac_props_sheet", "bordure_feuillue_sheet"],
        canopy=BZ.JUNGLE_CANOPY, eau="lac",
        tint="#0e1e2e", strength=0.58, grade="nuit", seed=2103, couloir=COULOIR,
        rules=[
            R(["bordure"], "midband", 14, 3, 48, 1),   # le cadre se resserre
            R(["tree"], "midband", 13, 4, 38, 2),      # futaie dense
            R(["mushroom"], "inner", 14, 5, 20, 1),    # champignons nocturnes
            R(["moss"], "ground", 16, 5, 20),
            R(["fern"], "ground", 12, 4, 24, 2),
            R(["rock"], "ground", 7, 3, 34),
            R(["reeds"], "shore", 14, 4, 18, 2),
            R(["lilies"], "water", 8, 3, 26, 1),
            R(["flower"], "ground", 8, 4, 24, 2),
        ])
    return s


# --------------------------------------------------------------------------- #
# 4. La bordure feuillue du commit precedent : on la garde, on l'utilise
# --------------------------------------------------------------------------- #

def _pngs(d):
    return [f for f in sorted(os.listdir(d)) if f.endswith(".png")] \
        if os.path.isdir(d) else []


def couper_bordures(src="layers/src/bordure_feuillue_sheet.png",
                    dst="layers/cut/bordure_feuillue_sheet",
                    tags_path="layers/tags/bordure_feuillue_sheet.json"):
    """Detoure la planche (chroma key) et publie le catalogue.

    Les GROS morceaux (plus de 140 px) sont poses par `poser_bordures` sur le
    cadre du terrain : ils ne sont pas des props. Le catalogue ne garde que
    les petits — des touffes de feuillage posables par le pipeline."""
    if not _pngs(dst):
        meta = CHROMA.cut_objects(src, dst, min_px=700, pad=1, prefix="bord")
        print(f"  bordure_feuillue : {len(meta)} morceaux detoures")
    idx = json.load(open(f"{dst}/index.json"))
    petits = [i for i, e in enumerate(idx)
              if e["w"] <= 140 and e["h"] <= 140]
    json.dump({"bordure": petits}, open(tags_path, "w"), indent=1)
    return len(petits)


# --------------------------------------------------------------------------- #
# 5. Assemblage, export PMDO, descripteur de donjon, planche
# --------------------------------------------------------------------------- #

def construire_etages(noms):
    import build_layered as B
    BZ.ZONES.update(specs_clairiere())

    # La canopee est posee en anneau (ring_positions) sans connaitre le
    # couloir d'entree sud : elle refermait la chaussee. On filtre les
    # morceaux du BAS qui chevauchent le couloir — l'entree reste ouverte,
    # tous les exports (rendu, Tiled, Aseprite, PMDO) suivent.
    _ring = B.ring_positions

    def ring_couloir(objs, rng, step=44):
        out = _ring(objs, rng, step)
        xa, xb = int(COULOIR[0] * W) - 14, int(COULOIR[1] * W) + 14
        garde = []
        for y, x, o in out:
            if y > H * 0.72 and x + o["w"] * 0.55 > xa and x - o["w"] * 0.55 < xb:
                continue      # un feuillage qui barre l'entree sud
            garde.append((y, x, o))
        return garde
    B.ring_positions = ring_couloir

    rap = {}
    try:
        for z in noms:
            r, err = BZ.construire(z)
            if err:
                print(f"-- {z} : {err}")
                continue
            rap[z] = r
            print(f"{z:16s} props {r['compo']['props']:3d}  palette {r['palette']:3d}  "
                  f"tuiles {r['tiled']['tuiles']:5d}  animees {r['tiled']['cases_animees']:3d}")
    finally:
        B.ring_positions = _ring
    return rap


def exporter_pmdo(noms):
    r = subprocess.run([sys.executable, "pmdo/export_pmdo.py"] + noms,
                       capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode:
        print(r.stderr.strip()[-600:])


def ecrire_layouts(noms, rap):
    """layouts/clairiere_sacree.json — le donjon : etages, entrees, liens.
    C'est la piece qui 'decompose en plusieurs layouts' : chaque etage garde
    son pack independant, le descripteur les chaine en donjon PMD."""
    ordre = ["B1F", "B2F", "B3F"]
    etages, liens = [], []
    for i, z in enumerate(noms):
        g = json.load(open(f"pmdo/{z}/ground.json")) \
            if os.path.exists(f"pmdo/{z}/ground.json") else {}
        r = rap.get(z, {})
        t = r.get("tiled", {})
        etages.append(dict(
            id=ordre[i], zone=z, titre=FLOORS[z]["titre"],
            grade=FLOORS[z]["grade"],
            eau=bool(FLOORS[z].get("mare")),
            entrees=g.get("entrees", {}),
            echelle=g.get("echelle", {}),
            props=r.get("compo", {}).get("props"),
            tuiles=dict(tuiles=t.get("tuiles"), animees=t.get("tuiles_animees"),
                        cases_animees=t.get("cases_animees")),
            packs=dict(rendu=f"layers/rendu/{z}", tiled=f"tiled/{z}",
                       aseprite=f"aseprite/{z}", pmdo=f"pmdo/{z}"),
            sortie_sud=ordre[i + 1] if i + 1 < len(noms) else None,
        ))
        if i + 1 < len(noms):
            liens.append(dict(de=ordre[i], vers=ordre[i + 1], cote="sud",
                              type="escalier"))
    doc = dict(
        nom="clairiere_sacree",
        titre="Le Bosquet Sacre",
        description=("Donjon exterieur en 3 etages, grammaire des fonds EoS "
                     "(cadre sombre, bande d'herbe, clairiere sableuse). "
                     "Corrige sur recup_reference.png : centre sable chaud "
                     "#d3c688, L=195."),
        toile=[W, H], case=24, cellule=8, cases=[21, 19],
        correction=("centre gris-vert des essais v1-v3 (L=148-177) -> "
                    "sable chaud de la reference"),
        etages=etages, liens=liens,
        variantes_existantes=["arene_bosquet_nu", "arene_bosquet_crepuscule",
                              "arene_bosquet_aube", "arene_bosquet_nuit",
                              "arene_bosquet_assaut"],
    )
    os.makedirs("layouts", exist_ok=True)
    json.dump(doc, open("layouts/clairiere_sacree.json", "w"), indent=1,
              ensure_ascii=False)
    return doc


def _b64(path, x2=False):
    import base64, io
    im = Image.open(path)
    if x2:
        im = im.resize((im.width * 2, im.height * 2), Image.NEAREST)
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _fmt_pct(x):
    return "-" if x is None else f"{x*100:.0f} %"


def planche(doc):
    """planche_clairiere.html — planche de controle autonome (data-URI)."""
    def cell(img, legend, cls=""):
        return (f'<figure class="c {cls}"><img src="{img}" alt=""/>'
                f"<figcaption>{legend}</figcaption></figure>")

    cartes = []
    for e in doc["etages"]:
        z = e["zone"]
        fond = _b64(f"pmdo/{z}/fond.png", x2=True)
        obst = _b64(f"pmdo/{z}/obstacles.png")
        ech = e.get("echelle") or {}
        cartes.append(f"""
      <section class="etage">
        <h2>{e['id']} — {e['titre']} <span class="grade">{e['grade']}</span></h2>
        <div class="duo">{cell(fond, "fond &times;2 (pixel net)")}
        {cell(obst, "collision 8 px : libre / bloqu&eacute; / eau")}</div>
        <table>
          <tr><th>props</th><td>{e.get('props') or '-'}</td>
              <th>tuiles 24 px</th><td>{(e.get('tuiles') or {}).get('tuiles') or '-'}</td>
              <th>cases anim&eacute;es</th><td>{(e.get('tuiles') or {}).get('cases_animees') or '-'}</td></tr>
          <tr><th>occupation</th><td>{_fmt_pct(ech.get('occupation_decor'))}</td>
              <th>part d'eau</th><td>{_fmt_pct(ech.get('part_eau'))}</td>
              <th>packs</th><td>rendu, tiled, aseprite, pmdo : <code>{z}/</code></td></tr>
        </table>
      </section>""")

    ref = _b64("layers/src/recup_reference.png")
    v3 = _b64("layers/src/recup_clairiere_v3.png")
    b1f = _b64("pmdo/clairiere_b1f/fond.png")

    # la carte definitive, avec son audit d'echelle (sprites 1:1 + viewport)
    carte_def = ""
    if os.path.exists("pmdo/clairiere/fond.png"):
        g = json.load(open("pmdo/clairiere/ground.json")) \
            if os.path.exists("pmdo/clairiere/ground.json") else {}
        e = g.get("echelle", {})
        fond = _b64("pmdo/clairiere/fond.png", x2=True)
        aud = _b64("pmdo/audit/clairiere_echelle.png") \
            if os.path.exists("pmdo/audit/clairiere_echelle.png") else None
        aud_cell = cell(aud, "audit d'&eacute;chelle : sprites &eacute;talon 1:1, "
                             "viewport 320&times;240, grille 8 px") if aud else ""
        occ = _fmt_pct(e.get("occupation_decor"))
        lar = e.get("largeur_locale_mediane", "-")
        eau = _fmt_pct(e.get("part_eau"))
        carte_def = f"""
  <section class="etage">
    <h2>LA carte — <code>clairiere</code> <span class="grade">jour · pack PMDO complet</span></h2>
    <div class="duo">{cell(fond, "fond &times;2 — peint NATIVEMENT en 504&times;456, z&eacute;ro r&eacute;&eacute;chantillonnage")}
    {aud_cell}</div>
    <table>
      <tr><th>occupation</th><td>{occ}</td><th>largeur locale</th><td>{lar} cases</td>
          <th>part d'eau</th><td>{eau}</td></tr>
      <tr><th>pack</th><td colspan="5"><code>pmdo/clairiere/</code> : fond, frames,
          calques (Base/River/Shadows/Objects/Fringe), sheets,
          obstacles.json + collision.tmx 8 px, brosse, ground.json ·
          <code>tiled/clairiere/</code> : tuiles 24 px anim&eacute;es natives</td></tr>
    </table>
  </section>"""
    html = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<title>Le Bosquet Sacr&eacute; — clairi&egrave;re corrig&eacute;e, 3 layouts</title>
<style>
 body{{background:#101410;color:#dfe7d8;font:14px/1.5 system-ui,sans-serif;
      margin:0;padding:24px}}
 h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:16px;color:#9fd08a}}
 .grade{{background:#2c4a2c;border-radius:8px;padding:1px 10px;font-size:12px;
        color:#cfe8bd;margin-left:8px}}
 .sous{{color:#8fa383;margin-bottom:20px}}
 .correction{{display:flex;gap:14px;flex-wrap:wrap;background:#182018;
             border:1px solid #2c3a2c;border-radius:10px;padding:14px;margin-bottom:22px}}
 .c{{margin:0;text-align:center}} .c img{{image-rendering:pixelated;
      border-radius:6px;display:block}}
 figcaption{{font-size:11px;color:#93a58a;margin-top:6px}}
 .etage{{background:#182018;border:1px solid #2c3a2c;border-radius:10px;
         padding:14px;margin-bottom:20px}}
 .duo{{display:flex;gap:14px;flex-wrap:wrap}}
 table{{border-collapse:collapse;margin-top:10px;font-size:12.5px}}
 th{{text-align:right;color:#8fa383;padding:2px 8px}} td{{padding:2px 8px}}
 .verdict{{color:#ffd98a}} .fix{{color:#9fd08a}}
 .diagram{{display:flex;align-items:center;gap:10px;justify-content:center;
          margin:10px 0 24px;font-size:13px}}
 .box{{background:#22321f;border:1px solid #3c5538;border-radius:10px;
      padding:8px 14px;text-align:center}}
 .arrow{{color:#7a9a72;font-size:20px}}
 code{{background:#0c100c;padding:1px 6px;border-radius:6px;color:#cfe8bd}}
</style></head><body>
<h1>Le Bosquet Sacr&eacute; — la clairi&egrave;re corrig&eacute;e, d&eacute;compos&eacute;e en layouts</h1>
<p class="sous">D&eacute;faut mesur&eacute; : la r&eacute;f&eacute;rence a un centre <b>sable chaud</b>
(<code>#d3c688</code>, L=195) ; les essais pr&eacute;c&eacute;dents sortaient un centre gris-vert
(<code>#a2b3a6</code>, L=173, &eacute;cart 17,7). Correction : terrain repeint dans la
grammaire EoS, rampes <b>extraites de la r&eacute;f&eacute;rence</b>. Rien n'a &eacute;t&eacute;
supprim&eacute; : les essais v1-v3 et la bordure feuillue du commit pr&eacute;c&eacute;dent sont
conserv&eacute;s — la bordure est m&ecirc;me pos&eacute;e sur le cadre.</p>
<div class="correction">
  {cell(ref, "la r&eacute;f&eacute;rence (cible)")}
  {cell(v3, "essai pr&eacute;c&eacute;dent v3 — centre gris-vert", "verdict")}
  {cell(b1f, "corrig&eacute; B1F — centre sable chaud", "fix")}
</div>
<div class="diagram">
  <div class="box">B1F<br/>Lisi&egrave;re<br/><small>jour</small></div><div class="arrow">&rarr;</div>
  <div class="box">B2F<br/>Clairi&egrave;re Sacr&eacute;e<br/><small>cr&eacute;puscule + mare</small></div>
  <div class="arrow">&rarr;</div>
  <div class="box">B3F<br/>C&oelig;ur du Bosquet<br/><small>nuit + mare</small></div>
</div>
{carte_def}
{''.join(cartes)}
<p class="sous">Descripteur du donjon : <code>layouts/clairiere_sacree.json</code> —
&eacute;tages, entr&eacute;es relev&eacute;es sur la grille 8 px, liens, packs. Les 5 variantes
d'ar&egrave;ne bosquet existantes restent inchang&eacute;es.</p>
</body></html>"""
    open("planche_clairiere.html", "w").write(html)
    print("planche_clairiere.html")


if __name__ == "__main__":
    noms = list(FLOORS)
    definitive = "clairiere"

    print("== rampes extraites de la reference")
    rampes = extraire_rampes()
    for nom, r in rampes.items():
        tons = " ".join(f"#{int(c[0]):02x}{int(c[1]):02x}{int(c[2]):02x}" for c in r)
        print(f"  {nom:6s} {tons}")
    for z, spec in list(FLOORS.items()) + [(definitive, CLAIRIERE)]:
        img = peindre_terrain(rampes, spec)
        Image.fromarray(img).save(f"layers/src/{z}_terrain.png")
        mag = ((img[..., 0] > 150) & (img[..., 2] > 150) & (img[..., 1] < 130))
        print(f"  {z}_terrain.png  eau {mag.mean()*100:.1f}%")
    if "--terrain" in sys.argv:
        sys.exit(0)

    print("== bordure feuillue (planche du commit precedent, gardee)")
    n = couper_bordures()
    print(f"  catalogue : {n} morceaux -> layers/cut/bordure_feuillue_sheet/")

    print("== construction : la carte definitive + les 3 etages")
    rap = construire_etages([definitive] + noms)
    if not rap:
        sys.exit(1)

    print("== export PMDO")
    exporter_pmdo(list(rap))

    print("== audit d'echelle (sprites 1:1 + viewport + grille)")
    from pmdo.audit_echelle import sprites_ref, planche as planche_audit
    spr = sprites_ref()
    os.makedirs("pmdo/audit", exist_ok=True)
    for z in rap:
        planche_audit(z, spr, f"pmdo/audit/{z}_echelle.png")
        print(f"  pmdo/audit/{z}_echelle.png")

    doc = ecrire_layouts([z for z in noms if z in rap], rap)
    planche(doc)
    print("\nlayouts/clairiere_sacree.json + planche_clairiere.html")
