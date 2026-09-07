"""
aseprite_export.py — écrit un vrai fichier .aseprite (v1.3) multi-calques / multi-frames.

Format binaire documenté (ase-file-specs) :
  header 128 o -> pour chaque frame : header 16 o + chunks
  chunk 0x2004 = calque   (déclarés une seule fois, sur la frame 0)
  chunk 0x2005 = cel      (type 2 = image RGBA compressée zlib)

Un parseur de contrôle (`verify`) relit le fichier produit et recompose les
pixels, ce qui garantit que la structure est cohérente.
"""
import struct, zlib, os
import numpy as np
from PIL import Image


def _u8(v):  return struct.pack("<B", v)
def _u16(v): return struct.pack("<H", v)
def _i16(v): return struct.pack("<h", v)
def _u32(v): return struct.pack("<I", v)
def _str(s):
    b = s.encode("utf-8")
    return _u16(len(b)) + b


def _chunk(ctype, data):
    return _u32(len(data) + 6) + _u16(ctype) + data


def _layer_chunk(name, visible=True, opacity=255):
    d = _u16(1 if visible else 0)      # flags : 1 = visible
    d += _u16(0)                       # type : 0 = image normale
    d += _u16(0)                       # child level
    d += _u16(0) + _u16(0)             # default w/h (ignorés)
    d += _u16(0)                       # blend mode : normal
    d += _u8(opacity) + b"\x00" * 3
    d += _str(name)
    return _chunk(0x2004, d)


def _cel_chunk(layer_index, rgba, x=0, y=0, opacity=255):
    h, w = rgba.shape[:2]
    d = _u16(layer_index) + _i16(x) + _i16(y) + _u8(opacity)
    d += _u16(2)                       # cel type 2 = image compressée
    d += _i16(0)                       # z-index
    d += b"\x00" * 5                   # réservé
    d += _u16(w) + _u16(h)
    d += zlib.compress(rgba.astype(np.uint8).tobytes(), 9)
    return _chunk(0x2005, d)


def write(path, width, height, layers, n_frames, frame_ms=110, grid=24):
    """
    layers : liste de dicts {name, frames:[HxWx4 uint8 ou None] (len == n_frames)}
             L'ordre de la liste = du fond vers l'avant (comme Aseprite).
    """
    body = b""
    for f in range(n_frames):
        chunks = b""
        nchunk = 0
        if f == 0:
            for L in layers:
                chunks += _layer_chunk(L["name"], L.get("visible", True))
                nchunk += 1
        for i, L in enumerate(layers):
            img = L["frames"][f % len(L["frames"])]
            if img is None:
                continue
            chunks += _cel_chunk(i, img)
            nchunk += 1
        fh = _u16(0xF1FA) + _u16(min(nchunk, 0xFFFF)) + _u16(frame_ms) + b"\x00" * 2 + _u32(nchunk)
        frame = _u32(16 + len(chunks)) + fh + chunks
        body += frame

    hdr = (_u16(0xA5E0) + _u16(n_frames) + _u16(width) + _u16(height) + _u16(32)
           + _u32(1) + _u16(frame_ms) + _u32(0) + _u32(0)
           + _u8(0) + b"\x00" * 3 + _u16(0) + _u8(1) + _u8(1)
           + _i16(0) + _i16(0) + _u16(grid) + _u16(grid) + b"\x00" * 84)
    data = _u32(128 + len(body)) + hdr + body
    assert len(_u32(0) + hdr) == 128, len(hdr) + 4
    with open(path, "wb") as fh_:
        fh_.write(data)
    return len(data)


# --------------------------------------------------------------------------- #
#  Relecture de contrôle
# --------------------------------------------------------------------------- #

def verify(path):
    b = open(path, "rb").read()
    size, magic, frames, w, h, depth = struct.unpack_from("<IHHHHH", b, 0)
    assert magic == 0xA5E0, "magic header invalide"
    assert size == len(b), f"taille annoncée {size} != réelle {len(b)}"
    off = 128
    names, cels = [], 0
    for f in range(frames):
        fsize, fmagic, _old, dur, _r, nch = struct.unpack_from("<IHHHHI", b, off)
        assert fmagic == 0xF1FA, "magic frame invalide"
        p = off + 16
        for _ in range(nch):
            csize, ctype = struct.unpack_from("<IH", b, p)
            d = b[p + 6:p + csize]
            if ctype == 0x2004:
                ln = struct.unpack_from("<H", d, 16)[0]
                names.append(d[18:18 + ln].decode("utf-8"))
            elif ctype == 0x2005:
                cw, ch = struct.unpack_from("<HH", d, 16)
                raw = zlib.decompress(d[20:])
                assert len(raw) == cw * ch * 4, "taille de cel incohérente"
                cels += 1
            p += csize
        off += fsize
    assert off == len(b), "octets résiduels en fin de fichier"
    return dict(frames=frames, size=[w, h], depth=depth, layers=names, cels=cels,
                octets=len(b))


# --------------------------------------------------------------------------- #
#  Script d'import Lua (solution de repli / édition assistée)
# --------------------------------------------------------------------------- #

LUA = '''-- {zone} : reconstruit le document en calques dans Aseprite
-- Aseprite > File > Scripts > Open Scripts Folder, y déposer ce fichier, puis l'exécuter.
local base = app.fs.filePath(app.fs.normalizePath(debug.getinfo(1).source:sub(2)))
local W, H, NF, MS = {w}, {h}, {nf}, {ms}
local defs = {defs}

local spr = Sprite(W, H, ColorMode.RGB)
spr.filename = app.fs.joinPath(base, "{zone}.aseprite")
while #spr.frames < NF do spr:newEmptyFrame() end
for _, fr in ipairs(spr.frames) do fr.duration = MS / 1000.0 end
spr:deleteLayer(spr.layers[1])

for _, d in ipairs(defs) do
  local lay = spr:newLayer()
  lay.name = d.name
  for f = 1, NF do
    local idx = d.static and 0 or (f - 1)
    local path = app.fs.joinPath(base, d.dir, string.format("f%02d.png", idx))
    if app.fs.isFile(path) then
      local img = Image{{ fromFile = path }}
      spr:newCel(lay, f, img, Point(0, 0))
    end
  end
end
app.refresh()
'''


def write_lua(path, zone, w, h, nf, ms, defs):
    lua_defs = "{\n" + ",\n".join(
        '  {{ name = "{n}", dir = "{d}", static = {s} }}'.format(
            n=d["name"], d=d["dir"], s="true" if d.get("static") else "false")
        for d in defs) + "\n}"
    with open(path, "w") as f:
        f.write(LUA.format(zone=zone, w=w, h=h, nf=nf, ms=ms, defs=lua_defs))
