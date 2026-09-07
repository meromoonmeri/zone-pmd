"""
build_zones4.py — passe 4 zones supplémentaires dans le pipeline par calques,
puis exporte chacune vers Tiled (tuiles animées) et Aseprite (calques x frames).
"""
import sys, os, json, glob, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image

import build_layered as B
from forge.tiled_export import export as tiled_export
from forge.aseprite_export import write as ase_write, verify as ase_verify, write_lua

TAGS = {
    "plage_props_sheet":   {"palm": [0, 2, 4], "log": [1], "shell": [3, 11, 12],
                            "rock": [5, 6, 7], "grass": [8, 9, 10, 13]},
    "prairie_props_sheet": {"tree": [0, 1, 2, 3, 4, 5], "rock": [6, 7],
                            "stone": [8, 9, 14], "flower": [10, 11, 12, 13, 15],
                            "grass": [16]},
    "marais_props_sheet":  {"deadtree": [0, 1, 5, 7], "plank": [2, 15], "vine": [3],
                            "algae": [4, 8, 9, 10, 12, 13, 17],
                            "moss": [6, 14, 16], "reed": [11, 18]},
    "cristal_props_sheet": {"crystal": [0, 1, 3, 5, 7, 10, 11, 14],
                            "mushroom": [2, 12], "stalagmite": [4, 6, 9], "rock": [8, 13]},
}

RAMPS = {
    "plage":   (["#0a3a5e", "#0f4d76", "#146390", "#1b7daa", "#2a9cc2", "#45b9d6", "#7fd8e4"],
                "#eaf8ff", 1.15),
    "prairie": (["#12454f", "#176070", "#1d7b8c", "#2699a6", "#37b6bd", "#59d0cf"],
                "#d9f6f2", 0.95),
    "marais":  (["#161e12", "#1f2917", "#2a361d", "#374425", "#46542e", "#586739"],
                "#8f9c66", 0.45),
    "cristal": (["#0a1d3a", "#0e2a4f", "#123a68", "#184e85", "#2166a4", "#2f83c4"],
                "#9fe0ff", 0.75),
}

ZONES = {
    "plage": dict(
        terrain="layers/src/plage_terrain.png", sheet="plage_props_sheet", canopy=None,
        tint="#123044", strength=0.42, seed=101,
        rules=[
            dict(cats=["palm"],  surface="midband", count=11, cap=5, min_dist=40, sway=2),
            dict(cats=["rock"],  surface="shore",   count=7,  cap=3, min_dist=34, sway=0),
            dict(cats=["grass"], surface="ground",  count=16, cap=5, min_dist=24, sway=2),
            dict(cats=["log"],   surface="ground",  count=1,  cap=1, sway=0),
            dict(cats=["shell"], surface="ground",  count=6,  cap=3, min_dist=30, sway=0),
        ]),
    "prairie": dict(
        terrain="layers/src/prairie_terrain.png", sheet="prairie_props_sheet",
        canopy="layers/cut/jungle_canopy_sheet",
        tint="#12301c", strength=0.48, seed=202,
        rules=[
            dict(cats=["tree"],   surface="midband", count=16, cap=4, min_dist=40, sway=2),
            dict(cats=["flower"], surface="ground",  count=20, cap=6, min_dist=22, sway=2),
            dict(cats=["grass"],  surface="ground",  count=12, cap=8, min_dist=22, sway=2),
            dict(cats=["rock"],   surface="ground",  count=6,  cap=4, min_dist=44, sway=0),
            dict(cats=["stone"],  surface="water",   count=4,  cap=3, min_dist=26, sway=0),
        ]),
    "marais": dict(
        terrain="layers/src/marais_terrain.png", sheet="marais_props_sheet",
        canopy="layers/cut/jungle_canopy_sheet",
        tint="#141a10", strength=0.55, seed=303,
        rules=[
            dict(cats=["deadtree"], surface="midband", count=10, cap=4, min_dist=46, sway=1),
            dict(cats=["reed"],     surface="shore",   count=14, cap=7, min_dist=20, sway=2),
            dict(cats=["algae"],    surface="water",   count=18, cap=4, min_dist=24, sway=1),
            dict(cats=["plank"],    surface="water",   count=2,  cap=1, min_dist=90, sway=0),
            dict(cats=["moss"],     surface="ground",  count=7,  cap=3, min_dist=36, sway=0),
            dict(cats=["vine"],     surface="midband", count=3,  cap=3, min_dist=60, sway=2),
        ]),
    "cristal": dict(
        terrain="layers/src/cristal_terrain_cool.png", sheet="cristal_props_sheet", canopy=None,
        tint="#080d18", strength=0.58, seed=404,
        rules=[
            dict(cats=["crystal"],    surface="midband", count=16, cap=4, min_dist=34, sway=0),
            dict(cats=["crystal"],    surface="inner",   count=8,  cap=3, min_dist=44, sway=0),
            dict(cats=["stalagmite"], surface="midband", count=9,  cap=4, min_dist=38, sway=0),
            dict(cats=["mushroom"],   surface="ground",  count=7,  cap=4, min_dist=32, sway=1),
            dict(cats=["rock"],       surface="ground",  count=6,  cap=3, min_dist=40, sway=0),
        ]),
}



def cool_path(src, dst, h_lo=28, h_hi=72, s_min=0.18, v_min=0.30,
              hue_out=214.0, sat_out=0.15, val_mul=0.94):
    """Le sentier de la grotte de cristal sortait sable chaud : on le bascule
    vers un gris-bleu mineral en conservant la luminance (donc la texture)."""
    a = np.array(Image.open(src).convert("RGB")).astype(np.float32) / 255.0
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(2), a.min(2)
    d = mx - mn + 1e-6
    v = mx
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    h = np.zeros_like(mx)
    i = (mx == r); h[i] = ((g - b)[i] / d[i]) % 6
    i = (mx == g); h[i] = ((b - r)[i] / d[i]) + 2
    i = (mx == b); h[i] = ((r - g)[i] / d[i]) + 4
    h *= 60.0
    m = (h >= h_lo) & (h <= h_hi) & (sat > s_min) & (v > v_min)
    hh = np.full(m.sum(), hue_out / 360.0)
    ss = np.full(m.sum(), sat_out)
    vv = np.clip(v[m] * val_mul, 0, 1)
    k = hh * 6.0
    ii = np.floor(k).astype(int) % 6
    f = k - np.floor(k)
    pp = vv * (1 - ss); qq = vv * (1 - ss * f); tt = vv * (1 - ss * (1 - f))
    out = np.stack([np.select([ii == 0, ii == 1, ii == 2, ii == 3, ii == 4, ii == 5],
                              [vv, qq, pp, pp, tt, vv]),
                    np.select([ii == 0, ii == 1, ii == 2, ii == 3, ii == 4, ii == 5],
                              [tt, vv, vv, qq, pp, pp]),
                    np.select([ii == 0, ii == 1, ii == 2, ii == 3, ii == 4, ii == 5],
                              [pp, pp, tt, vv, vv, qq])], 1)
    a[m] = out
    Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8), "RGB").save(dst)
    return int(m.sum())


def write_tags():
    os.makedirs("layers/tags", exist_ok=True)
    for sheet, t in TAGS.items():
        json.dump(t, open(f"layers/tags/{sheet}.json", "w"), indent=1)


def export_tools(zone):
    src = f"layers/rendu/{zone}"
    man = json.load(open(f"{src}/manifest.json"))
    # ---- Tiled ---------------------------------------------------------- #
    tout = f"tiled/{zone}"
    os.makedirs(f"{tout}/calques", exist_ok=True)
    lay = []
    for L in man["layers"]:
        if not L.get("dir") and not L.get("file"):
            continue
        if L.get("file"):
            s = f"{src}/{L['file']}"
        else:
            g = sorted(glob.glob(f"{src}/{L['dir']}/*.png"))
            if not g:
                continue
            s = g[0]
        dst = f"calques/{L['name']}.png"
        shutil.copy(s, f"{tout}/{dst}")
        lay.append(dict(name=f"{L['order']}_{L['name']}", image=dst,
                        props={"anime": "oui" if L.get("animated") else "non",
                               "technique": L.get("technique", "")}))
    fdir = f"{src}/frames_tiles" if os.path.isdir(f"{src}/frames_tiles") else f"{src}/frames"
    tr = tiled_export(zone, fdir, tout, layers=lay, frame_ms=man["frame_ms"])

    # ---- Aseprite -------------------------------------------------------- #
    aout = f"aseprite/{zone}"
    os.makedirs(aout, exist_ok=True)
    layers, defs = [], []
    for L in man["layers"]:
        if L.get("file"):
            fs = [f"{src}/{L['file']}"]
        elif L.get("dir"):
            fs = sorted(glob.glob(f"{src}/{L['dir']}/*.png"))
        else:
            continue
        if not fs:
            continue
        fr = [np.array(Image.open(p).convert("RGBA")) for p in fs]
        if len(fr) == 1:
            fr = fr * man["frames"]
        layers.append(dict(name=f"{L['order']}_{L['name']}", frames=fr))
        d = L.get("dir") or "."
        os.makedirs(f"{aout}/{d}", exist_ok=True)
        for p in fs:
            shutil.copy(p, f"{aout}/{d}/")
        defs.append(dict(name=f"{L['order']}_{L['name']}", dir=d,
                         static=not L.get("animated")))
    ase_write(f"{aout}/{zone}.aseprite", man["size"][0], man["size"][1],
              layers, man["frames"], man["frame_ms"], grid=24)
    av = ase_verify(f"{aout}/{zone}.aseprite")
    write_lua(f"{aout}/importer_{zone}.lua", zone, man["size"][0], man["size"][1],
              man["frames"], man["frame_ms"], defs)
    return tr, av


if __name__ == "__main__":
    write_tags()
    print("sentier refroidi :", cool_path("layers/src/cristal_terrain.png",
          "layers/src/cristal_terrain_cool.png"), "px")
    report = {}
    for zone, spec in ZONES.items():
        ramp, foam, calm = RAMPS[zone]
        m = B.render(zone, spec["terrain"], f"layers/cut/{spec['sheet']}",
                     f"layers/tags/{spec['sheet']}.json", spec["canopy"],
                     rules=spec["rules"], water_ramp=ramp, foam=foam, calm=calm,
                     terrain_tint=spec["tint"], terrain_strength=spec["strength"],
                     seed=spec["seed"])
        tr, av = export_tools(zone)
        report[zone] = dict(compo=m["counts"], palette=m["palette"],
                            tiled=dict(tuiles=tr["tuiles_uniques"],
                                       animees=tr["tuiles_animees"],
                                       cases_animees=tr["cases_animees"]),
                            aseprite=dict(calques=len(av["layers"]), cels=av["cels"]))
        print(zone, "OK")
    json.dump(report, open("layers/rendu/rapport_4zones.json", "w"), indent=1)
    print(json.dumps(report, indent=1))
