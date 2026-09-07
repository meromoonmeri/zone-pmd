"""
pmdo/audit_echelle.py — controle d'echelle des zones face aux references PMDO.

Applique la methode de ANALYSE_ECHELLE.md (branche arena/…-guilde-treehouse-pmd) :
  * unite de lecture   = case de 24 px
  * grille de collision = 8 px (ground map RogueEssence)
  * viewport logique   = 320 x 240 px
  * sprite Pokemon     = 19-27 x 20-22 px, un sprite remplit ~1 case
Les sprites de controle sont extraits de .chara de Halcyon (Palikadude/Halcyon),
utilises comme etalon de mesure uniquement — ils ne sont pas redistribues.
"""
import os, sys, io, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw

TILE = 24          # case de lecture PMD
CELL = 8           # cellule de collision PMDO
VIEW = (320, 240)  # viewport logique du moteur
SPRITE_REF = (26, 22)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RENDU = os.path.join(ROOT, "layers", "rendu")

# fourchettes Halcyon relevees dans ANALYSE_ECHELLE.md (cases de 24 px)
HALCYON = {
    "chambre":  dict(sol=(50, 55),   emprise=(9, 14),  largeur=(1.1, 1.7), decor=(35, 40)),
    "salle":    dict(sol=(38, 80),   emprise=(4, 16),  largeur=(0.8, 1.9), decor=(46, 59)),
    "hub":      dict(sol=(158, 193), emprise=(11, 33), largeur=(2.1, 2.2), decor=(24, 36)),
}
# une zone d'exterieur n'est pas une piece de guilde : la reference utile est le
# hub (la plus grande piece jouable de Halcyon) et le nombre d'ecrans.
CIBLE_EXT = dict(ecrans=(1.0, 4.0), largeur=(1.0, 3.0), decor=(18, 45))


def sprite_from_chara(path):
    """Premiere frame utile d'un .chara RogueEssence, rognee au contenu.
    (portage local de analyse_echelle/apercus.py, pour rester autonome)"""
    d = open(path, "rb").read()
    o = d.find(b"\x89PNG\r\n\x1a\n")
    im = Image.open(io.BytesIO(d[o:])).convert("RGBA")
    im.load()
    a = np.array(im)[:, :, 3]

    def runs(v):
        out, st = [], None
        for i, x in enumerate(v > 0):
            if x and st is None:
                st = i
            elif not x and st is not None:
                out.append((st, i)); st = None
        if st is not None:
            out.append((st, len(v)))
        return out
    x0, x1 = runs(a.sum(0))[0]
    y0, y1 = runs(a.sum(1))[0]
    return im.crop((x0, y0, x1, y1))


def sprites_ref():
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, "pmdo", "ref_sprites", "*.chara"))):
        try:
            out.append(sprite_from_chara(p))
        except Exception:
            pass
    if not out:                       # etalon neutre si les .chara manquent
        s = Image.new("RGBA", SPRITE_REF, (0, 0, 0, 0))
        ImageDraw.Draw(s).ellipse([0, 0, SPRITE_REF[0] - 1, SPRITE_REF[1] - 1],
                                  fill=(255, 90, 140, 230), outline=(30, 0, 20, 255))
        out = [s]
    return out


# ------------------------------------------------------------------ masques

ROLE = {          # mot-cle du nom de calque -> role de collision
    "ciel": "libre", "terrain": "libre", "herbe": "libre", "sol": "libre",
    "eau": "eau", "water": "eau",
    "montagne": "bloc", "falaise": "bloc", "canopy": "bloc", "canopee": "bloc",
    "props": "bloc_pied",
    "fleur": "libre", "touffe": "libre",
}


def role_of(name):
    for k, v in ROLE.items():
        if k in name.lower():
            return v
    return "bloc_pied"


def _grid(alpha, gh, gw, seuil, base_only=False):
    a = (np.asarray(alpha) > 40).astype(np.float32)
    if base_only:                 # seul le pied d'un objet haut bloque
        keep = np.zeros_like(a)
        for x in range(a.shape[1]):
            col = np.nonzero(a[:, x])[0]
            if col.size:
                keep[col.max() - min(col.size, 22) + 1: col.max() + 1, x] = 1
        a = keep
    c = a[:gh * CELL, :gw * CELL].reshape(gh, CELL, gw, CELL).mean((1, 3))
    return c > seuil


def masque_obstacles(zone):
    """Grille de collision 8 px, deduite des calques declares au manifeste.

    L'eau bloque, les reliefs bloquent en entier, les props bloquent par le pied
    (au-dela de 45 % de la cellule), la vegetation basse et le ciel ne bloquent pas.
    """
    d = os.path.join(RENDU, zone)
    man = json.load(open(f"{d}/manifest.json"))
    W, H = man["size"]
    gw, gh = W // CELL, H // CELL
    bloc = np.zeros((gh, gw), bool)
    eau = np.zeros((gh, gw), bool)

    for L in man["layers"]:
        r = role_of(L["name"])
        if r == "libre":
            continue
        if L.get("file"):
            fs = [f"{d}/{L['file']}"]
        elif L.get("dir"):
            fs = sorted(glob.glob(f"{d}/{L['dir']}/*.png"))
        else:
            continue
        if not fs:
            continue
        al = np.asarray(Image.open(fs[0]).convert("RGBA"))[..., 3]
        if r == "eau":
            g = _grid(al, gh, gw, 0.55)
            eau |= g
        elif r == "bloc":
            g = _grid(al, gh, gw, 0.30)
        else:
            g = _grid(al, gh, gw, 0.45, base_only=True)
        bloc |= g
    return bloc, (W, H), eau


def largeur_locale(free):
    """2 x distance a l'obstacle le plus proche, en cases, mediane sur le sol."""
    from scipy import ndimage
    d = ndimage.distance_transform_edt(free) * CELL / TILE
    v = d[free]
    return (float(np.median(v)) * 2, float(v.max()) * 2) if v.size else (0.0, 0.0)


def audit(zone):
    block, (W, H), water = masque_obstacles(zone)
    free = ~block
    gh, gw = block.shape
    sol_cases = free.sum() * (CELL * CELL) / (TILE * TILE)
    lm, lmax = largeur_locale(free)
    decor = 100.0 * (block & ~water).sum() / block.size
    part_eau = 100.0 * water.sum() / block.size
    ecrans = (W / VIEW[0]) * (H / VIEW[1])
    return dict(
        zone=zone, px=[W, H],
        cases=[round(W / TILE, 2), round(H / TILE, 2)],
        cellules_8px=[gw, gh],
        multiple_de_8=(W % CELL == 0 and H % CELL == 0),
        multiple_de_24=(W % TILE == 0 and H % TILE == 0),
        sol_cases2=round(float(sol_cases), 1),
        sol_par_sprite=round(float(sol_cases) * TILE * TILE / (SPRITE_REF[0] * SPRITE_REF[1]), 1),
        largeur_locale_mediane=round(lm, 2),
        plus_grand_vide=round(lmax, 2),
        occupation_decor=round(float(decor), 1),
        part_eau=round(float(part_eau), 1),
        ecrans=round(float(ecrans), 2),
        eau_cellules=int(water.sum()),
    )


def verdict(a):
    m = []
    lo, hi = CIBLE_EXT["ecrans"]
    m.append(("emprise", lo <= a["ecrans"] <= hi,
              f'{a["ecrans"]} ecran(s) de 320x240 (cible {lo}-{hi})'))
    lo, hi = CIBLE_EXT["largeur"]
    m.append(("largeur locale", lo <= a["largeur_locale_mediane"] <= hi,
              f'{a["largeur_locale_mediane"]} case(s) (cible {lo}-{hi})'))
    lo, hi = CIBLE_EXT["decor"]
    m.append(("occupation decor", lo <= a["occupation_decor"] <= hi,
              f'{a["occupation_decor"]} % hors eau, eau {a["part_eau"]} % (cible {lo}-{hi} %)'))
    m.append(("grille 8 px", a["multiple_de_8"], f'{a["cellules_8px"][0]}x{a["cellules_8px"][1]} cellules'))
    m.append(("grille 24 px", a["multiple_de_24"], f'{a["cases"][0]}x{a["cases"][1]} cases'))
    return m


# ------------------------------------------------------------------ planche

def put(canvas, spr, fx, fy):
    ov = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(ov).ellipse([fx - spr.width // 2, fy - 3,
                                fx + spr.width // 2, fy + 3], fill=(0, 0, 0, 80))
    canvas.alpha_composite(ov)
    canvas.alpha_composite(spr, (int(fx - spr.width / 2), int(fy - spr.height)))


def points(free, n):
    """n points de sol bien etales (echantillonnage du plus eloigne)."""
    ys, xs = np.nonzero(free)
    if not len(xs):
        return []
    rng = np.random.default_rng(7)
    idx = [rng.integers(len(xs))]
    for _ in range(n - 1):
        d = np.full(len(xs), 1e18)
        for j in idx:
            d = np.minimum(d, (xs - xs[j]) ** 2 + (ys - ys[j]) ** 2)
        idx.append(int(d.argmax()))
    return [(int(xs[i] * CELL + CELL // 2), int(ys[i] * CELL + CELL)) for i in idx]


def planche(zone, sprites, out):
    d = os.path.join(RENDU, zone)
    bg = Image.open(sorted(glob.glob(f"{d}/frames/*.png"))[0]).convert("RGBA")
    block, (W, H), _w = masque_obstacles(zone)
    free = ~block

    # 1 : rendu + sprites 1:1 + viewport
    a = bg.copy()
    for i, (x, y) in enumerate(points(free, 6)):
        put(a, sprites[i % len(sprites)], x, y)
    dr = ImageDraw.Draw(a)
    vx, vy = (W - VIEW[0]) // 2, (H - VIEW[1]) // 2
    dr.rectangle([vx, vy, vx + VIEW[0], vy + VIEW[1]], outline=(90, 190, 255, 255), width=2)

    # 2 : grille de collision 8 px
    b = bg.copy()
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    gh, gw = block.shape
    for gy in range(gh):
        for gx in range(gw):
            if block[gy, gx]:
                od.rectangle([gx * CELL, gy * CELL, gx * CELL + CELL - 1, gy * CELL + CELL - 1],
                             fill=(255, 60, 90, 90))
    for x in range(0, W + 1, TILE):
        od.line([x, 0, x, H], fill=(255, 255, 255, 46))
    for y in range(0, H + 1, TILE):
        od.line([0, y, W, y], fill=(255, 255, 255, 46))
    b.alpha_composite(ov)

    card = Image.new("RGBA", (W * 2 + 36, H + 24), (12, 16, 19, 255))
    card.alpha_composite(a, (12, 12))
    card.alpha_composite(b, (W + 24, 12))
    card.convert("RGB").save(out)
    return out


if __name__ == "__main__":
    zones = sys.argv[1:] or sorted(
        z for z in os.listdir(RENDU)
        if os.path.isdir(os.path.join(RENDU, z)) and not z.endswith("_src"))
    spr = sprites_ref()
    print("sprites etalon :", [s.size for s in spr])
    os.makedirs(os.path.join(ROOT, "pmdo", "audit"), exist_ok=True)
    rep = {}
    for z in zones:
        a = audit(z)
        rep[z] = a
        planche(z, spr, os.path.join(ROOT, "pmdo", "audit", f"{z}_echelle.png"))
        print(f"\n== {z}  {a['px'][0]}x{a['px'][1]} px | {a['cases'][0]}x{a['cases'][1]} cases "
              f"| {a['cellules_8px'][0]}x{a['cellules_8px'][1]} cellules 8px")
        for nom, ok, txt in verdict(a):
            print(f"   [{'OK ' if ok else '!! '}] {nom:15s} {txt}")
    json.dump(rep, open(os.path.join(ROOT, "pmdo", "audit", "echelle.json"), "w"), indent=1)
