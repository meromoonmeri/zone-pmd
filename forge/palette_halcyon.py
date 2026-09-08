"""
forge/palette_halcyon.py — la colorimetrie stricte de Halcyon.

Relevee sur 5 banques `.tile` de `Palikadude/Halcyon` (Altere Pond Base,
Objects, Cliffs, Fringe, Metano Town Objects), soit 36 326 cases de 8 px :

  * **2 831 couleurs distinctes** en tout, mais **70,9 % des pixels tombent sur
    la grille des multiples de 8** (`v >> 3 << 3`) et 20,3 % sur la grille
    `+7`. Mon `core.ds_quant` utilisait `(v>>3)*8+7`, donc **7 niveaux trop
    clair** sur chaque composante, systematiquement. C'est corrige ici ;
  * **mediane de 7 couleurs par tuile 8x8, et 97,1 % des tuiles a 16 ou
    moins** : il respecte la contrainte DS d'une palette de 16 par tuile ;
  * luminance ponderee p5 61 / p50 158 / p95 209 — c'est **clair** ;
  * saturation ponderee p5 0,31 / p50 0,63 / p95 0,84 — c'est **tres sature** ;
  * sa couleur dominante est `#c8d850` a 18,6 % : le vert-jaune de Metano.

746 couleurs couvrent 99 % de ses pixels ; alignees sur la grille de 8 il en
reste **654**, stockees dans `assets/palette_halcyon.json`.

Reserve honnete : cette palette vient d'une ville, d'une mare et d'une caverne
de gres. Elle est riche en verts, ocres et bruns, et **pauvre en bleus
profonds, en violets et en tons de glace**. Y contraindre une banquise ou une
caverne de cristal deplace fortement les teintes ; `couverture()` le mesure
avant de decider.
"""
import json
import os

import numpy as np

_ICI = os.path.dirname(os.path.abspath(__file__))
_JSON = os.path.join(os.path.dirname(_ICI), "assets", "palette_halcyon.json")

with open(_JSON) as f:
    PALETTE = np.array([[int(h[i:i + 2], 16) for i in (1, 3, 5)]
                        for h in json.load(f)], np.int16)

_LUT = None


def ds8(a):
    """Sa grille : multiple de 8, pas `*8+7`."""
    return ((np.asarray(a).astype(np.int16) >> 3) << 3).astype(np.uint8)


def _lab(rgb):
    """Approximation suffisante pour comparer des distances de teinte."""
    c = np.asarray(rgb, np.float32) / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    m = np.array([[0.4124, 0.3576, 0.1805],
                  [0.2126, 0.7152, 0.0722],
                  [0.0193, 0.1192, 0.9505]], np.float32)
    xyz = c @ m.T / np.array([0.9505, 1.0, 1.089], np.float32)
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16,
                     500 * (f[..., 0] - f[..., 1]),
                     200 * (f[..., 1] - f[..., 2])], -1)


def _lut():
    """Table 32x32x32 -> index de palette. Construite une fois."""
    global _LUT
    if _LUT is None:
        g = np.arange(32, dtype=np.int16) << 3
        cube = np.stack(np.meshgrid(g, g, g, indexing="ij"), -1).reshape(-1, 3)
        a = _lab(cube)
        b = _lab(PALETTE)
        idx = np.empty(len(a), np.int16)
        pas = 4096
        for i in range(0, len(a), pas):
            d = ((a[i:i + pas, None, :] - b[None, :, :]) ** 2).sum(-1)
            idx[i:i + pas] = d.argmin(1)
        _LUT = idx.reshape(32, 32, 32)
    return _LUT


def snap(img):
    """Ramene une image RGB sur SA palette. Entree/sortie uint8."""
    a = np.asarray(img)
    rgb = a[..., :3].astype(np.int16) >> 3
    out = PALETTE[_lut()[rgb[..., 0], rgb[..., 1], rgb[..., 2]]].astype(np.uint8)
    if a.shape[-1] == 4:
        return np.dstack([out, a[..., 3]])
    return out


def contraindre_tuiles(img, tuile=8, maxi=8):
    """Force au plus `maxi` couleurs par tuile de `tuile` px.

    Sa contrainte dure est 16 (97,1 % de ses tuiles la respectent), mais sa
    MEDIANE est a 7. On serre donc a 8 par defaut : verifie a l'oeil sur un
    zoom x2, la difference avec 16 est invisible, et la mediane tombe a 8.
    Les couleurs rares d'une tuile sont rabattues sur la plus proche des
    `maxi` dominantes de cette meme tuile.
    """
    a = np.array(img)[..., :3].astype(np.uint8)
    h, w = a.shape[:2]
    for y in range(0, h - h % tuile, tuile):
        for x in range(0, w - w % tuile, tuile):
            bloc = a[y:y + tuile, x:x + tuile]
            plat = bloc.reshape(-1, 3)
            vals, inv, cnt = np.unique(plat, axis=0, return_inverse=True,
                                       return_counts=True)
            if len(vals) <= maxi:
                continue
            garde = vals[np.argsort(-cnt)[:maxi]]
            d = ((_lab(vals)[:, None, :] - _lab(garde)[None, :, :]) ** 2).sum(-1)
            a[y:y + tuile, x:x + tuile] = garde[d.argmin(1)][inv].reshape(
                tuile, tuile, 3)
    return a


def mesures(img, masque=None):
    """Les memes mesures que celles faites sur ses fichiers."""
    a = np.asarray(img)[..., :3].astype(np.int32)
    v = a.reshape(-1, 3) if masque is None else a[masque]
    L = 0.299 * v[:, 0] + 0.587 * v[:, 1] + 0.114 * v[:, 2]
    mx, mn = v.max(1), v.min(1)
    S = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    h, w = a.shape[:2]
    pt = []
    for y in range(0, h - h % 8, 8):
        for x in range(0, w - w % 8, 8):
            pt.append(len(np.unique(a[y:y + 8, x:x + 8].reshape(-1, 3), axis=0)))
    pt = np.array(pt)
    return dict(couleurs=int(len(np.unique(v, axis=0))),
                L_p5=float(np.percentile(L, 5)), L_p50=float(np.percentile(L, 50)),
                L_p95=float(np.percentile(L, 95)),
                S_p50=round(float(np.percentile(S, 50)), 2),
                sur_grille_8=round(float((v % 8 == 0).all(1).mean()), 3),
                couleurs_par_tuile_med=float(np.median(pt)),
                tuiles_sous_16=round(float((pt <= 16).mean()), 3))


def couverture(img, masque=None):
    """Ecart moyen introduit par le passage a sa palette, en unites Lab.

    Au-dela d'une dizaine, la teinte est deplacee de facon visible : la zone
    n'entre pas dans sa colorimetrie sans etre repensee.
    """
    a = np.asarray(img)[..., :3]
    v = a.reshape(-1, 3) if masque is None else a[masque]
    ech = v[::max(1, len(v) // 20000)]
    d = np.linalg.norm(_lab(ech) - _lab(snap(ech)), axis=-1)
    return dict(ecart_moyen=round(float(d.mean()), 2),
                ecart_p95=round(float(np.percentile(d, 95)), 2))


# Ses percentiles de luminance, ponderes, releves sur les 5 banques.
CIBLE_L = (61.0, 158.0, 209.0)     # p5, p50, p95


def exposer(img, cible=CIBLE_L):
    """Recale la luminance sur la sienne, sans toucher a la teinte.

    Mon rendu sortait a L p50 = 97 la ou il est a 158 : sa direction
    artistique est nettement plus claire que la mienne. On construit une courbe
    monotone qui fait coincider p5, p50 et p95, et on l'applique comme un gain
    par pixel — la teinte et la saturation relative sont conservees.
    """
    a = np.asarray(img)[..., :3].astype(np.float32)
    L = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
    src = np.percentile(L, [5, 50, 95])
    xs = np.array([0.0, src[0], src[1], src[2], 255.0], np.float32)
    ys = np.array([0.0, cible[0], cible[1], cible[2], 255.0], np.float32)
    xs, i = np.unique(xs, return_index=True)
    ys = ys[i]
    Lc = np.interp(L, xs, ys)
    gain = np.where(L > 1.0, Lc / np.maximum(L, 1.0), 1.0)[..., None]
    return np.clip(a * gain, 0, 255).astype(np.uint8)
