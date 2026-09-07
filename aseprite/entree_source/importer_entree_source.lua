-- entree_source : reconstruit le document en calques dans Aseprite
-- Aseprite > File > Scripts > Open Scripts Folder, y déposer ce fichier, puis l'exécuter.
local base = app.fs.filePath(app.fs.normalizePath(debug.getinfo(1).source:sub(2)))
local W, H, NF, MS = 504, 456, 12, 110
local defs = {
  { name = "0_terrain", dir = ".", static = true },
  { name = "1_water", dir = "01_water", static = false },
  { name = "2_props", dir = "02_props", static = false }
}

local spr = Sprite(W, H, ColorMode.RGB)
spr.filename = app.fs.joinPath(base, "entree_source.aseprite")
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
      local img = Image{ fromFile = path }
      spr:newCel(lay, f, img, Point(0, 0))
    end
  end
end
app.refresh()
