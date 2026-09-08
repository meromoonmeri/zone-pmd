"""
build_clairiere.py — montage de la clairiere a l'arbre ancien.

Trois demandes traitees :

1. **Ombres PMD.** La plaque a deja les ombres sous les petits arbres, que
   l'utilisateur valide. Il manquait celle du GRAND arbre, qui flottait sur le
   sable. On projette donc une ombre portee depuis le houppier, decalee vers le
   bas, **tramee en Bayer 4x4** et non en alpha lisse — c'est le grain des
   ombres deja presentes, et c'est ce que faisait la DS.

2. **Calque d'eau separe et anime.** Le bassin est detoure de la plaque, son
   trou est rebouche par le lit du bassin, et l'eau devient un calque a part
   anime par la methode de Palika : 4 dessins redessines, releves sur
   `Altere_Pond_River_Animations.tile`.

3. **Grille stricte PMDO / RogueEssence.** Sortie en **576 x 504** :
   72 x 63 cellules de 8 px et 24 x 21 cases de 24 px — entier dans les deux
   grilles, au ratio de la plaque d'origine. Viewport 320 x 240, soit
   1,80 x 2,10 ecrans.

Usage : python3 build_clairiere.py
"""
import json
import os

import numpy as np
from PIL import Image
from scipy import ndimage

from forge import core as C
from forge import calques_halcyon as CH
from forge import tile_rogue as TR
from forge.water_halcyon import _traits, LISERE

SRC = "layers/src/clairiere_ref.png"
ZONE = "clairiere_arbre"
W, H = 576, 504            # 72x63 cellules de 8 px, 24x21 cases de 24 px
N, MS, MAINTIEN = 8, 165, 2   # 4 dessins d'eau, 330 ms chacun (cadence EoS)
SORTIE = f"layers/rendu/{ZONE}"

BAYER4 = np.array([[0, 8, 2, 10],
                   [12, 4, 14, 6],
                   [3, 11, 1, 9],
                   [15, 7, 13, 5]], np.float32) / 16.0


def charger():
    im = Image.open(SRC).convert("RGB")
    # recadrage au ratio cible AVANT redimensionnement, comme load_terrain
    rs, rd = im.width / im.height, W / H
    if rs > rd:
        nw = int(im.height * rd)
        im = im.crop(((im.width - nw) // 2, 0, (im.width + nw) // 2, im.height))
    else:
        nh = int(im.width / rd)
        im = im.crop((0, (im.height - nh) // 2, im.width, (im.height + nh) // 2))
    return np.array(im.resize((W, H), Image.LANCZOS)).astype(np.int16)


def masque_bassin(a):
    """Le bassin : la grande nappe bleue claire au centre, et elle seule.

    Le feuillage sombre du cadre tire aussi vers le bleu-vert ; on le rejette
    par la clarte et par la connexite avec le centre de l'image.
    """
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    L = 0.299 * r + 0.587 * g + 0.114 * b
    bleu = (b > r + 25) & (b > 130) & (L > 95) & (g < b + 10)
    bleu = ndimage.binary_closing(bleu, np.ones((5, 5)))
    lab, n = ndimage.label(bleu)
    if n == 0:
        raise SystemExit("bassin introuvable")
    # on garde la composante la plus grande qui touche le tiers central
    cy0, cy1 = int(H * 0.30), int(H * 0.80)
    cx0, cx1 = int(W * 0.20), int(W * 0.80)
    scores = []
    for i in range(1, n + 1):
        m = lab == i
        scores.append((int(m[cy0:cy1, cx0:cx1].sum()), int(m.sum()), i))
    scores.sort(reverse=True)
    m = lab == scores[0][2]
    m = ndimage.binary_fill_holes(m)
    m = ndimage.binary_opening(m, np.ones((3, 3)))
    return m


def reboucher(a, masque):
    """Rebouche le trou du bassin avec la couleur du lit, pour le calque Base.

    On tire la teinte du pourtour immediat : le fond garde ainsi une cuvette
    credible si l'eau est masquee dans l'editeur.
    """
    out = a.copy()
    bord = C.dilate(masque, 4) & ~masque
    teinte = np.median(a[bord].reshape(-1, 3), 0) * 0.72
    ind = ndimage.distance_transform_edt(masque, return_distances=False,
                                         return_indices=True)
    proche = a[tuple(i[masque] for i in ind)]
    out[masque] = (proche * 0.35 + teinte * 0.65).astype(np.int16)
    return out


def houppiers(a, bassin):
    """Repere les masses de feuillage : le grand arbre et les arbres ronds."""
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    L = 0.299 * r + 0.587 * g + 0.114 * b
    vert = (g > r + 14) & (g > b + 14) & (L > 70) & ~bassin
    vert = ndimage.binary_closing(vert, np.ones((7, 7)))
    vert = ndimage.binary_opening(vert, np.ones((5, 5)))
    lab, n = ndimage.label(vert)
    blobs = []
    for i in range(1, n + 1):
        m = lab == i
        s = int(m.sum())
        if s < 900:
            continue
        ys, xs = np.nonzero(m)
        blobs.append(dict(masque=m, aire=s,
                          x0=int(xs.min()), x1=int(xs.max()),
                          y0=int(ys.min()), y1=int(ys.max())))
    blobs.sort(key=lambda d: -d["aire"])
    return blobs


def tronc(a, bassin):
    """Le tronc du grand arbre : la masse brune du haut de la carte."""
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    brun = (r > g + 14) & (g > b + 8) & (r > 70) & (r < 205) & ~bassin
    haut = np.zeros((H, W), bool)
    haut[:int(H * 0.62)] = True
    brun &= haut
    brun = ndimage.binary_closing(brun, np.ones((7, 7)))
    lab, n = ndimage.label(brun)
    if n == 0:
        return None
    tailles = ndimage.sum(brun, lab, range(1, n + 1))
    m = lab == (int(np.argmax(tailles)) + 1)
    if m.sum() < 1500:
        return None
    return ndimage.binary_fill_holes(m)


def ombre_arbre(m_tronc, sol, force=0.40):
    """UNE ombre portee, sous le grand arbre seulement.

    Les petits arbres ont deja la leur sur la plaque et l'utilisateur la
    valide : on n'y touche pas. Ici on ne comble que celle qui manquait, celle
    du grand arbre, qui flottait sur le sable.
    """
    acc = np.zeros((H, W), np.float32)
    if m_tronc is None:
        return acc, 0
    ys, xs = np.nonzero(m_tronc)
    cx = float(xs.mean())
    ybas = float(np.percentile(ys, 97))
    rx = max(28.0, (xs.max() - xs.min()) * 0.72)
    ry = max(14.0, rx * 0.34)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = ((xx - cx) / rx) ** 2 + ((yy - (ybas + ry * 0.55)) / ry) ** 2
    acc = np.clip(1.0 - d, 0.0, 1.0) ** 0.85 * force
    acc *= sol & ~m_tronc
    return acc, 1


def appliquer_ombre(a, acc):
    """Assombrit par TRAMAGE Bayer, pas par alpha : c'est le grain de la DS.

    Le tramage est module par l'intensite BRUTE, pas normalisee : une ombre
    faible ne doit assombrir qu'une fraction des pixels. La normalisation
    precedente etalait l'ombre sur toute la clairiere.
    """
    out = a.copy()
    seuils = np.tile(BAYER4, (H // 4 + 1, W // 4 + 1))[:H, :W]
    pris = seuils < np.clip(acc, 0.0, 1.0)
    out[pris] = (out[pris] * 0.66).astype(np.int16)
    fort = pris & (acc > 0.30)
    out[fort] = (out[fort] * 0.86).astype(np.int16)
    return out


def eau_animee(a, masque, n, maintien, seed=41):
    """Calque d'eau : la peinture d'origine + des reflets redessines.

    Palika redessine 4 dessins complets, mais son corps d'eau est un aplat.
    Ici le bassin est PEINT — nenuphars, ombre du liseré de pierre, degrade du
    fond. Le remplacer par un aplat detruisait le travail. On garde donc les
    pixels peints comme corps, et on n'anime que ce que lui anime vraiment :
    les traits clairs en virgule pres de la berge. 4 dessins, 330 ms chacun.
    """
    dist = ndimage.distance_transform_edt(masque).astype(np.float32)
    v = a[masque].reshape(-1, 3)
    L = 0.299 * v[:, 0] + 0.587 * v[:, 1] + 0.114 * v[:, 2]
    clair = np.median(v[L > np.percentile(L, 88)], 0)
    trait = np.clip(clair * 0.55 + 255 * 0.45, 0, 255)
    eclat = np.clip(clair * 0.22 + 255 * 0.78, 0, 255)
    trait = C.ds_quant(trait.astype(np.uint8).reshape(1, 1, 3))[0, 0]
    eclat = C.ds_quant(eclat.astype(np.uint8).reshape(1, 1, 3))[0, 0]

    fixe = np.zeros((H, W, 4), np.uint8)
    fixe[masque] = np.concatenate(
        [np.clip(a[masque], 0, 255).astype(np.uint8),
         np.full((int(masque.sum()), 1), 255, np.uint8)], 1)

    dessins = []
    for k in range(4):
        rng = np.random.default_rng(seed * 131 + k * 17)
        im = fixe.copy()
        t1 = _traits(dist, masque, rng, 150, 13.0)
        t2 = _traits(dist, masque, rng, 70, 6.0)
        im[t1 & masque] = (*trait, 255)
        im[t2 & masque & (dist > LISERE + 2)] = (*eclat, 255)
        dessins.append(im)
    return [dessins[(t // maintien) % 4] for t in range(n)], dessins


def rampe_du_bassin(a, masque):
    """La rampe de l'eau, tiree des pixels peints du bassin lui-meme.

    On ne plaque pas une rampe generique : la teinte du bassin de la plaque est
    conservee, seule l'animation est ajoutee.
    """
    v = a[masque].reshape(-1, 3)
    L = 0.299 * v[:, 0] + 0.587 * v[:, 1] + 0.114 * v[:, 2]
    q = np.percentile(L, [4, 20, 40, 60, 80, 96])
    rampe = []
    for x in q:
        sel = v[np.abs(L - x) < 9]
        c = np.median(sel if len(sel) else v, 0)
        c = C.ds_quant(np.clip(c, 0, 255).astype(np.uint8).reshape(1, 1, 3))[0, 0]
        rampe.append("#%02x%02x%02x" % tuple(int(t) for t in c))
    ecume = "#eaf8ff"
    return rampe, ecume


def main():
    os.makedirs(SORTIE, exist_ok=True)
    a = charger()
    bassin = masque_bassin(a)
    print(f"bassin : {int(bassin.sum())} px ({bassin.mean()*100:.1f} % de la carte)")

    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    sable = (r > 140) & (g > 100) & (r > b + 35) & ~bassin

    blobs = houppiers(a, bassin)
    print(f"masses de feuillage : {len(blobs)}  "
          f"(la plus grande {blobs[0]['aire']} px)" if blobs else "aucune")

    m_tronc = tronc(a, bassin)
    feuille = np.any([d["masque"] for d in blobs], 0) if blobs else np.zeros((H, W), bool)
    sol = ~feuille & ~bassin
    acc, ngros = ombre_arbre(m_tronc, sol)
    print(f"tronc du grand arbre : {int(m_tronc.sum()) if m_tronc is not None else 0} px"
          f"   ombre portee ajoutee : {ngros}")

    base = reboucher(a, bassin)
    base = appliquer_ombre(base, acc)

    # --- calques, dans l'ordre de Palika ---------------------------------- #
    for nom in CH.DOSSIERS.values():
        os.makedirs(f"{SORTIE}/{nom}", exist_ok=True)
    os.makedirs(f"{SORTIE}/frames", exist_ok=True)

    Image.fromarray(base.astype(np.uint8), "RGB").save(
        f"{SORTIE}/{CH.DOSSIERS['Base']}/f00.png")

    ombre_rgba = np.zeros((H, W, 4), np.uint8)
    ombre_rgba[..., 3] = np.clip(acc * 255, 0, 255).astype(np.uint8)
    Image.fromarray(ombre_rgba, "RGBA").save(
        f"{SORTIE}/{CH.DOSSIERS['Shadows']}/f00.png")

    rampe, ecume = rampe_du_bassin(a, bassin)
    print("rampe du bassin :", " ".join(rampe))
    wl, dessins_eau = eau_animee(a, bassin, N, MAINTIEN)
    for t in range(N):
        Image.fromarray(wl[t], "RGBA").save(
            f"{SORTIE}/{CH.DOSSIERS['River']}/f{t:02d}.png")

    # --- frames finales ---------------------------------------------------- #
    frames = []
    for t in range(N):
        f = np.dstack([base.astype(np.uint8),
                       np.full((H, W, 1), 255, np.uint8)])
        al = wl[t][..., 3:4].astype(np.float32) / 255.0
        f[..., :3] = (f[..., :3] * (1 - al) + wl[t][..., :3] * al).astype(np.uint8)
        im = Image.fromarray(f[..., :3], "RGB")
        im.save(f"{SORTIE}/frames/f{t:02d}.png")
        frames.append(im)
    gif = [i.quantize(colors=256, method=Image.MEDIANCUT, dither=Image.Dither.NONE)
           for i in frames]
    gif[0].save(f"{SORTIE}/{ZONE}.gif", save_all=True, append_images=gif[1:],
                duration=MS, loop=0, optimize=True, disposal=1)

    # --- banques .tile de 8 px -------------------------------------------- #
    dtile = f"pmdo/{ZONE}/tiles"
    os.makedirs(dtile, exist_ok=True)
    rap = []
    for nom, ordre, k in CH.CALQUES:
        d = f"{SORTIE}/{CH.DOSSIERS[nom]}"
        fs = sorted(f for f in os.listdir(d)) if os.path.isdir(d) else []
        if not fs:
            continue
        idx, _ = CH.dessins(N, k)
        vus, choisis = [], []
        for t, i in enumerate(idx):
            if i not in vus and t < len(fs):
                vus.append(i)
                choisis.append(f"{d}/{fs[t]}")
        if len(fs) == 1:
            choisis = [f"{d}/{fs[0]}"]
        slug = nom.replace(" ", "_")
        for j, f in enumerate(choisis):
            cible = f"{dtile}/{ZONE}_{slug}.tile" if j == 0 else \
                    f"{dtile}/{ZONE}_{slug}_f{j}.tile"
            info = TR.ecrire(cible, np.array(Image.open(f).convert("RGBA")))
            if j == 0:
                rap.append(dict(calque=nom, dessins=len(choisis), **info))

    # --- collision 8 px + entree sud -------------------------------------- #
    gh, gw = H // 8, W // 8
    bloc_eau = bassin[:gh * 8, :gw * 8].reshape(gh, 8, gw, 8).mean((1, 3)) > 0.55
    sombre = (0.299 * base[..., 0] + 0.587 * base[..., 1] + 0.114 * base[..., 2]) < 62
    bloc_feuille = sombre[:gh * 8, :gw * 8].reshape(gh, 8, gw, 8).mean((1, 3)) > 0.60
    trunc = np.zeros((H, W), bool)
    if blobs:
        trunc = blobs[0]["masque"]
    bloc_tronc = trunc[:gh * 8, :gw * 8].reshape(gh, 8, gw, 8).mean((1, 3)) > 0.55
    bloque = bloc_eau | bloc_feuille | bloc_tronc
    libre = ~bloque
    lab, _ = ndimage.label(libre)
    sud = set(lab[gh - 1][libre[gh - 1]].tolist())
    c = lab[gh // 2 - 2:gh // 2 + 2, gw // 2 - 2:gw // 2 + 2]
    entree = bool(set(c[c > 0].tolist()) & sud)

    os.makedirs(f"pmdo/{ZONE}", exist_ok=True)
    Image.fromarray((bloque * 255).astype(np.uint8), "L").save(
        f"pmdo/{ZONE}/collision.png")
    Image.fromarray(np.array(frames[0]), "RGB").save(f"pmdo/{ZONE}/fond.png")

    man = dict(
        zone=ZONE, moteur="PMDO / RogueEssence",
        taille_px=[W, H], cellules_8px=[gw, gh], cases_24px=[W // 24, H // 24],
        viewport=[320, 240], viewports=[round(W / 320, 2), round(H / 240, 2)],
        frames=N, frame_ms=MS,
        eau=dict(technique="4 dessins redessines, methode Palika "
                           "(Altere_Pond_River_Animations)",
                 dessins=4, maintien_frames=MAINTIEN, ms_par_dessin=MS * MAINTIEN,
                 corps="pixels peints d'origine conserves ; seuls les reflets "
                       "sont redessines d'un dessin a l'autre",
                 px=int(bassin.sum()), rampe=rampe),
        ombres=dict(technique="ombre portee tramee Bayer 4x4, pas d'alpha lisse",
                    masses_traitees=ngros),
        collision=dict(libres=int(libre.sum()), bloquees=int(bloque.sum()),
                       eau=int(bloc_eau.sum()), entree_sud_continue=entree),
        tiles=rap,
    )
    json.dump(man, open(f"pmdo/{ZONE}/ground.json", "w"), indent=1,
              ensure_ascii=False)
    json.dump(man, open(f"{SORTIE}/manifest.json", "w"), indent=1,
              ensure_ascii=False)

    print(f"\n{W}x{H} px = {gw}x{gh} cellules 8px = {W//24}x{H//24} cases 24px "
          f"= {W/320:.2f}x{H/240:.2f} viewport")
    print(f"collision : {int(libre.sum())} libres, {int(bloque.sum())} bloquees, "
          f"entree sud continue : {'OUI' if entree else 'NON'}")
    for x in rap:
        print(f"   {x['calque']:14s} {x['dessins']} banque(s)  "
              f"{x['entrees']:5d} cases  {x['octets']//1024:5d} Ko")


if __name__ == "__main__":
    main()
