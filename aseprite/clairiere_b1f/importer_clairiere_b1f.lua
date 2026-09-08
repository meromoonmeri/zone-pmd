-- clairiere_b1f : reconstruit le document en calques dans Aseprite
-- Aseprite > File > Scripts > Open Scripts Folder, y déposer ce fichier, puis l'exécuter.
local base = app.fs.filePath(app.fs.normalizePath(debug.getinfo(1).source:sub(2)))
local W, H, NF, MS = 504, 456, 24, 110
local defs = {
  { name = "0_Base", dir = "00_base", static = true },
  { name = "2_Cliffs", dir = "02_cliffs", static = true },
  { name = "3_Shadows", dir = "03_shadows", static = true },
  { name = "4_Objects Under", dir = "04_objects_under", static = true },
  { name = "5_Objects", dir = "05_objects", static = false },
  { name = "6_Objects Over", dir = "06_objects_over", static = false },
  { name = "7_Fringe", dir = "07_fringe", static = true }
}

local spr = Sprite(W, H, ColorMode.RGB)
spr.filename = app.fs.joinPath(base, "clairiere_b1f.aseprite")
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
