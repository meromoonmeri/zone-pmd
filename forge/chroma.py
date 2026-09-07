"""
chroma.py — détourage des planches d'assets sur fond magenta + découpe en objets.

Entrée  : une planche PNG avec des objets isolés sur #FF00FF
Sortie  : un PNG RGBA par objet, recadré au plus juste, avec son ancre au sol.
"""
import numpy as np
from PIL import Image
import os, json


def key_out(path, tol=90, despill=True):
    """Retire le fond magenta. Renvoie un RGBA."""
    im = np.array(Image.open(path).convert("RGB")).astype(np.int32)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    # magenta = R et B hauts, G bas
    is_key = (r > 150) & (b > 150) & (g < 130) & ((r - g) > tol) & ((b - g) > tol)

    rgba = np.zeros(im.shape[:2] + (4,), np.uint8)
    rgba[..., :3] = im
    rgba[..., 3] = np.where(is_key, 0, 255)

    # frange : pixels partiellement fondus avec le fond, non captés par la clé
    r_, g_, b_ = im[..., 0], im[..., 1], im[..., 2]
    fringe = (~is_key) & (r_ - g_ > 22) & (b_ - g_ > 22) & (r_ > 85) & (b_ > 85)
    rgba[..., 3] = np.where(fringe, 0, rgba[..., 3])

    if despill:                      # tue la frange magenta des pixels de bord
        edge = (rgba[..., 3] > 0)
        rr, gg, bb = rgba[..., 0].astype(np.int32), rgba[..., 1].astype(np.int32), rgba[..., 2].astype(np.int32)
        spill = edge & (rr > gg + 40) & (bb > gg + 40)
        mx = np.maximum(gg, (rr + bb) // 2 - 30)
        rgba[..., 0] = np.where(spill, np.minimum(rr, mx), rr)
        rgba[..., 2] = np.where(spill, np.minimum(bb, mx), bb)
    return rgba


def _label(mask):
    """Composantes connexes 8-voisins, sans scipy (union-find sur les lignes)."""
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    parent = [0]

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    nxt = 1
    for y in range(h):
        row = mask[y]
        for x in np.flatnonzero(row):
            nb = []
            if x > 0 and lab[y, x - 1]:
                nb.append(lab[y, x - 1])
            if y > 0:
                for dx in (-1, 0, 1):
                    xx = x + dx
                    if 0 <= xx < w and lab[y - 1, xx]:
                        nb.append(lab[y - 1, xx])
            if nb:
                m = min(nb); lab[y, x] = m
                for n_ in nb:
                    union(m, n_)
            else:
                parent.append(nxt); lab[y, x] = nxt; nxt += 1
    for y in range(h):
        nz = lab[y] > 0
        lab[y, nz] = [find(v) for v in lab[y, nz]]
    return lab


def scale_rgba(rgba, scale):
    """Redimensionne en alpha prémultiplié (sinon le magenta bave sur les bords)."""
    h, w = rgba.shape[:2]
    nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    a = rgba[..., 3:4].astype(np.float32) / 255.0
    pm = np.concatenate([rgba[..., :3].astype(np.float32) * a, a * 255], -1)
    im = Image.fromarray(np.clip(pm, 0, 255).astype(np.uint8), "RGBA").resize((nw, nh), Image.LANCZOS)
    pm = np.array(im).astype(np.float32)
    na = pm[..., 3:4] / 255.0
    rgb = np.where(na > 0.02, pm[..., :3] / np.maximum(na, 1e-3), 0)
    out = np.zeros((nh, nw, 4), np.uint8)
    out[..., :3] = ((np.clip(rgb, 0, 255).astype(np.uint8) >> 3) * 8 + 7)   # DS 5 bits
    out[..., 3] = np.where(na[..., 0] > 0.5, 255, 0)                        # alpha 1 bit
    return out


def cut_objects(path, out_dir, min_px=900, pad=1, prefix="obj", scale=1.0):
    """Détoure, met à l'échelle native, puis découpe chaque objet en PNG RGBA."""
    rgba = key_out(path)
    if scale != 1.0:
        rgba = scale_rgba(rgba, scale)
    mask = rgba[..., 3] > 0
    lab = _label(mask)
    ids, counts = np.unique(lab[lab > 0], return_counts=True)

    os.makedirs(out_dir, exist_ok=True)
    meta = []
    keep = [i for i, c in zip(ids, counts) if c >= min_px]
    # tri lecture : haut->bas puis gauche->droite
    boxes = {}
    for i in keep:
        ys, xs = np.where(lab == i)
        boxes[i] = (ys.min(), ys.max(), xs.min(), xs.max())
    keep.sort(key=lambda i: (boxes[i][0] // 120, boxes[i][2]))

    for k, i in enumerate(keep):
        y0, y1, x0, x1 = boxes[i]
        y0, x0 = max(0, y0 - pad), max(0, x0 - pad)
        y1, x1 = min(rgba.shape[0] - 1, y1 + pad), min(rgba.shape[1] - 1, x1 + pad)
        sub = rgba[y0:y1 + 1, x0:x1 + 1].copy()
        m = (lab[y0:y1 + 1, x0:x1 + 1] == i)
        sub[~m, 3] = 0                                  # isole l'objet
        name = f"{prefix}_{k:02d}.png"
        Image.fromarray(sub, "RGBA").save(os.path.join(out_dir, name))
        meta.append(dict(file=name, w=int(x1 - x0 + 1), h=int(y1 - y0 + 1),
                         px=int(m.sum()), anchor_y=int(y1 - y0 + 1)))
    with open(os.path.join(out_dir, "index.json"), "w") as f:
        json.dump(meta, f, indent=1)
    return meta
