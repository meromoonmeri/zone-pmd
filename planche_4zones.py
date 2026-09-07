"""
planche_4zones.py — galerie HTML autonome (data-URI) des 4 nouvelles zones
en calques : plage, prairie, marais, cristal.
"""
import os, io, json, glob, base64, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
import build_zones4 as Z

OUT = "planche_4zones.html"
REP = json.load(open("layers/rendu/rapport_4zones.json"))

TITRES = {"plage": "Crique tropicale", "prairie": "Prairie au ruisseau",
          "marais": "Marais brumeux", "cristal": "Caverne de cristal"}
NOTES = {
    "plage":   "Sable clair, ourlet d'ecume, cocotiers en cadre. L'ocean occupe la"
               " bande haute : houle en bandes sinusoidales brisees par deux termes en x,"
               " pour eviter les rayures pleine largeur typiques du sinus global.",
    "prairie": "Ruisseau turquoise en diagonale, sentier de terre, canopee empruntee"
               " a la jungle pour fermer le cadre. Fleurs et touffes oscillent par"
               " cisaillement vertical, base fixe.",
    "marais":  "Eau olive tres sombre, calme 0.45 : la houle est presque plate, ce sont"
               " les nappes d'algues et les roseaux qui portent le mouvement. Arbres morts"
               " et planches pourries en jalons de lecture.",
    "cristal": "Souterrain : pas de canopee, une flaque unique bleu nuit. Le sentier"
               " sortait sable chaud du generateur, il a ete rebascule vers un gris-bleu"
               " mineral a luminance conservee (fonction cool_path).",
}
LAYER_LABEL = {"00_terrain.png": "00 terrain (statique)", "01_water": "01 eau (12 frames)",
               "02_props": "02 props (12 frames)", "03_canopy": "03 canopee (12 frames)"}


def b64(path):
    return base64.b64encode(open(path, "rb").read()).decode()


def thumb_b64(path, w=248, bg=None):
    im = Image.open(path).convert("RGBA")
    if bg:
        under = Image.new("RGBA", im.size, bg)
        im = Image.alpha_composite(under, im)
    im = im.resize((w, round(im.height * w / im.width)), Image.NEAREST)
    buf = io.BytesIO(); im.convert("RGB").save(buf, "PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def swatches(colors):
    return "".join(f'<i style="background:{c}" title="{c}"></i>' for c in colors)


CSS = """*{box-sizing:border-box}body{margin:0;padding:34px;background:#0c1013;color:#dce4ea;
font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px}
h1{margin:0 0 6px;font-size:22px;color:#7fd1e8;letter-spacing:.07em}
p.sub{margin:0 0 8px;color:#7d8f9b;font-size:12.5px;max-width:88ch;line-height:1.8}
section{margin:0 0 30px;padding:22px;background:#121a20;border:1px solid #223038;border-radius:9px}
h2{margin:0 0 4px;font-size:15px;color:#a9e4f5;letter-spacing:.04em}
h2 small{color:#5f7683;font-size:11px;letter-spacing:.1em;text-transform:uppercase;margin-left:10px}
p.note{margin:0 0 16px;color:#829aa8;font-size:12px;line-height:1.75;max-width:96ch}
h3{margin:20px 0 9px;font-size:11px;color:#6d8794;letter-spacing:.11em;text-transform:uppercase;font-weight:400}
img{display:block;max-width:100%;height:auto;image-rendering:pixelated;
border:1px solid #223038;border-radius:6px}
.duo{display:flex;gap:22px;flex-wrap:wrap;align-items:flex-start}
figure{margin:0} figcaption{margin-top:7px;color:#6d8794;font-size:10.5px;
text-transform:uppercase;letter-spacing:.06em}
.cal{display:flex;gap:14px;flex-wrap:wrap}
.cal figure{flex:0 0 248px}
table{border-collapse:collapse;width:100%;font-size:11.5px;margin-top:4px}
th{text-align:left;color:#6d8794;font-weight:400;padding:6px 10px;border-bottom:1px solid #26343d}
td{padding:6px 10px;border-bottom:1px solid #1a252b;color:#b3c6d1} td b{color:#9fe0f5}
.ramp{display:flex;gap:0;margin:6px 0 2px;border:1px solid #26343d;border-radius:4px;overflow:hidden;width:max-content}
.ramp i{display:block;width:34px;height:22px}
.tags span{display:inline-block;margin:0 6px 6px 0;padding:3px 9px;border:1px solid #2a3a44;
border-radius:11px;color:#95b0bd;font-size:11px}
.tags b{color:#9fe0f5;font-weight:400}
footer{color:#5f7683;font-size:11.5px;line-height:1.8;max-width:92ch;margin-top:8px}
"""

html = ['<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">',
        '<title>4 zones en calques — plage / prairie / marais / cristal</title>',
        f'<style>{CSS}</style></head><body>',
        '<h1>Quatre zones supplementaires, montees en calques</h1>',
        '<p class="sub">Meme chaine que Pic Fleuri : planches d\'assets generees sur fond '
        'magenta pur, detourage objet par objet, tri par categorie, dispersion sous '
        'contraintes (surface, distance minimale, plafond par objet), puis animation '
        'calque par calque a 12 frames. Rien n\'est anime sur une image aplatie. '
        'Chaque zone ressort en 504 x 504 px, grille 24, couleurs quantifiees DS 5 bits '
        'par canal, palette bornee a 64 teintes.</p>',
        '<p class="sub">La lumiere est traitee comme un effet d\'ecran et non comme de la '
        'donnee de tuile : le GIF et le fichier Aseprite portent la respiration lumineuse '
        'animee, tandis que l\'export Tiled est calcule sur un jeu de frames a lumiere '
        'figee. Sans cette separation, la moindre variation globale rendait 399 cases sur '
        '399 « animees » et faisait exploser le tileset.</p>']

for z in ["plage", "prairie", "marais", "cristal"]:
    src = f"layers/rendu/{z}"
    man = json.load(open(f"{src}/manifest.json"))
    r = REP[z]
    ramp, foam, calm = Z.RAMPS[z]
    tags = Z.TAGS[f"{z}_props_sheet"]
    html.append(f'<section><h2>{TITRES[z]} <small>{z}</small></h2>')
    html.append(f'<p class="note">{NOTES[z]}</p>')

    html.append('<div class="duo"><figure>')
    html.append(f'<img src="data:image/gif;base64,{b64(f"{src}/{z}.gif")}" width="504">')
    html.append(f'<figcaption>rendu anime — {man["frames"]} frames, {man["frame_ms"]} ms</figcaption></figure>')
    html.append('<figure style="flex:1 1 320px">')
    html.append('<table>')
    html.append(f'<tr><th>props places</th><td><b>{r["compo"]["props"]}</b></td></tr>')
    html.append(f'<tr><th>elements de canopee</th><td><b>{r["compo"]["canopy"]}</b></td></tr>')
    html.append(f'<tr><th>pixels d\'eau</th><td><b>{r["compo"]["water_px"]:,}</b></td></tr>'.replace(",", " "))
    html.append(f'<tr><th>palette finale</th><td><b>{r["palette"]}</b> couleurs</td></tr>')
    html.append(f'<tr><th>Tiled — tuiles uniques</th><td><b>{r["tiled"]["tuiles"]}</b></td></tr>')
    html.append(f'<tr><th>Tiled — cases animees</th><td><b>{r["tiled"]["cases_animees"]}</b> / 399</td></tr>')
    html.append(f'<tr><th>Aseprite</th><td><b>{r["aseprite"]["calques"]}</b> calques, '
                f'<b>{r["aseprite"]["cels"]}</b> cels</td></tr>')
    html.append('</table>')
    html.append(f'<h3>rampe d\'eau — calme {calm}</h3><div class="ramp">{swatches(ramp)}'
                f'<i style="background:{foam}" title="{foam} (ecume)"></i></div>')
    html.append('<h3>categories detourees</h3><div class="tags">')
    for k, v in tags.items():
        html.append(f'<span>{k} <b>x{len(v)}</b></span>')
    html.append('</div></figure></div>')

    html.append('<h3>calques, frame 0</h3><div class="cal">')
    for key, lab in LAYER_LABEL.items():
        p = f"{src}/{key}"
        if key.endswith(".png"):
            if not os.path.exists(p):
                continue
            html.append(f'<figure><img src="data:image/png;base64,{thumb_b64(p)}">'
                        f'<figcaption>{lab}</figcaption></figure>')
        else:
            g = sorted(glob.glob(f"{p}/*.png"))
            if not g:
                continue
            html.append(f'<figure><img src="data:image/png;base64,'
                        f'{thumb_b64(g[0], bg=(255, 0, 255, 255))}">'
                        f'<figcaption>{lab}</figcaption></figure>')
    html.append('</div></section>')

html.append('<footer>Fonds magenta visibles sur les vignettes de calques : c\'est la '
            'couleur-cle de transparence, elle n\'existe pas dans le rendu final. '
            'Livrables par zone : <code>layers/rendu/&lt;zone&gt;/</code> (calques + frames + GIF '
            '+ manifest), <code>tiled/&lt;zone&gt;/</code> (.tmx, tileset dedoublonne MD5, '
            'tuiles animees) et <code>aseprite/&lt;zone&gt;/</code> (.aseprite natif + importeur Lua). '
            'Aucun pixel rippe : les planches sources sont redessinees, les 338 fonds '
            'originaux ne servent que d\'etude de style dans <code>ref_etude/</code>.</footer>')
html.append('</body></html>')

open(OUT, "w").write("\n".join(html))
print(OUT, round(os.path.getsize(OUT) / 1e6, 2), "Mo")
