# zone-pmd

Zones originales pour fan game **Pokémon Donjon Mystère**, dessinées dans le style
*Explorers of Sky*, montées **en calques animés** et livrées **à l'échelle PMDO
(RogueEssence)** avec leur grille de collision de 8 px.

> **Aucun pixel rippé.** Tous les assets de ce dépôt sont générés puis retravaillés
> ici. Les 338 fonds de map originaux de *Explorers of Sky* ont servi d'**étude de
> style** en local uniquement — ils sont exclus par `.gitignore` et ne sont pas
> publiés. Idem pour les `.chara` de Halcyon, utilisés comme étalon de mesure.

---

## Ce qu'il y a dedans

| Dossier | Contenu |
|---|---|
| `layers/src/` | planches sources : terrains nus et feuilles de props sur fond magenta |
| `layers/cut/` | catalogues d'objets détourés, un PNG par objet |
| `layers/tags/` | catégorie → index d'objet, par feuille |
| `layers/rendu/` | sortie du pipeline : calques, frames, GIF, `manifest.json` |
| `pmdo/` | **pack PMDO** : fond, calques en bandes, collision 8 px, `ground.json` |
| `tiled/` | cartes Tiled 24 px avec tuiles animées natives |
| `aseprite/` | `.aseprite` natifs (calques × frames) + importeurs Lua |
| `assets/` | 22 zones de la première passe, encore aplaties (en cours de reprise) |
| `forge/` | la bibliothèque : palettes, matières, props, eau, lumière, exports |

---

## Le pipeline en une page

1. **Générer les éléments séparément**, jamais une image déjà aplatie.
   Terrain nu d'un côté (« ground layer only, no props »), planche d'objets de
   l'autre, sur **fond magenta pur** `#FF00FF` avec de l'espace vide entre chaque
   objet.
2. **Détourer** objet par objet : clé magenta à pleine résolution → prémultiplication
   → redimensionnement → seuil alpha. *Dans cet ordre*, sinon franges violettes.
3. **Taguer** les objets par catégorie (`palm`, `rock`, `algae`, `crystal`…).
4. **Peupler** sous contraintes : surface d'accueil, distance minimale, plafond par
   objet, dispersion par foyers. Un tirage uniforme donne un tapis illisible.
5. **Animer calque par calque**, techniques d'époque : cisaillement vertical à base
   fixe pour la végétation, bandes sinusoïdales + scintillement pour l'eau, dérive
   ping-pong pour les nuages, voile de brume pour les reliefs.
6. **Quantifier DS** : `v = (v>>3)*8 + 7`, palette bornée à 64 couleurs.
7. **Exporter** vers Tiled, Aseprite et le pack PMDO.

---

## Échelle PMDO

La méthode vient de `ANALYSE_ECHELLE.md` (dépôt `guilde-treehouse-pmd`, branches
`arena/…`), rejouée ici sur des zones d'extérieur.

| Grandeur | Valeur |
|---|---|
| Cellule de collision d'une ground map | **8 px** |
| Case de lecture PMD | **24 px** = 3 × 3 cellules |
| Viewport logique du moteur | **320 × 240 px** |
| Sprite Pokémon | 19–27 × 20–22 px (≈ 1 case) |

Les toiles font 504 × 456 et 504 × 504 : **multiples de 8 et de 24**. La grille de
collision tombe donc pile sur l'art existant — *aucun rééchantillonnage*, donc aucune
perte de netteté du pixel art.

```bash
python3 pmdo/audit_echelle.py           # controle chiffre + planches 1:1
python3 pmdo/export_pmdo.py             # pack PMDO de chaque zone
```

`audit_echelle.py` pose de vrais sprites Pokémon à 1:1 sur chaque zone, trace le cadre
du viewport, mesure la surface de sol praticable en cases², la largeur locale médiane
(2 × distance à l'obstacle le plus proche), la plus grande poche de vide et le taux
d'occupation, puis compare aux fourchettes relevées chez Halcyon.

### Pack PMDO, par zone

```
pmdo/<zone>/
  fond.png                 composite frame 0
  fond_frames.png          les 12 frames en bande horizontale
  calques/NN_<nom>.png     un fichier par calque (bande si animé)
  obstacles.json / .txt    grille 8 px  '.' libre  '#' bloqué  '~' eau
  collision.png            masque 1 px par cellule
  obstacles.png            la grille en surimpression, pour relecture humaine
  collision.tmx            carte Tiled 8 px éditable à la souris
  brosse_collision.tsx     3 pinceaux : libre / bloqué / eau
  ground.json              descripteur : taille, calques, entrées, audit d'échelle
```

**Pourquoi pas de tileset graphique en 8 px :** découper le décor en tuiles de 8 px
donne 23 000 à 34 000 tuiles uniques — le tramage DS ne se répète pas à cette échelle.
En PMDO une ground map n'est de toute façon pas une tilemap : c'est une image de fond
plus une grille de collision. Le tileset 24 px animé, lui, reste produit dans `tiled/`.

---

## L'eau : la technique d'Explorers of Sky, à la lettre

**Aucun pixel de l'eau ne bouge.** C'est le point que j'avais raté au premier jet,
et c'est tout le sujet.

> « Les tuiles ne changent jamais de graphisme pour s'animer. L'eau donne l'illusion
> de bouger parce que sa **ligne de palette change de couleur**. Pour Beach Cave,
> l'eau change de couleur toutes les **20 frames**. »
> — SilverDeoxys563, qui a rippé les tilesets d'EoS

TCRF confirme pour les fonds de map : *« palette animation for the water as well as
dithering between water color shades »*. Et le wiki SkyTemple, pour les fonds de
donjon : *« they can not have animated chunks but they can have animated palettes »*.

`forge/water_pmd.py` implémente exactement ça.

### Les 16 entrées de la ligne de palette

| Index | Rôle | Animé |
|---|---|---|
| 0 – 2 | eau plate, 3 nuances de profondeur | non |
| 3 – 14 | reflets = 3 nuances × 4 phases | **oui** |
| 15 | écume de rive | non |

À chaque pas, la couleur de la phase `a` devient celle de la phase `(a + s) % 4`.
La crête de lumière saute de tiret en tiret sans qu'un seul pixel ait changé d'index.

### Cadence

Un pas toutes les **3 frames de sortie**, soit 3 × 110 = **330 ms** — la cadence
relevée sur Beach Cave (20 frames moteur à 60 Hz = 333 ms). Sur une boucle de 12
frames, l'eau n'a donc que **4 états distincts**, tenus 3 frames chacun. Pas
d'interpolation : le jeu ne fait pas de fondu, il change la couleur d'un coup.

### Les demi-teintes

Pas de dégradé continu — le DS n'a pas les couleurs pour. **Tramage ordonné 4 × 4**
entre deux nuances voisines. J'avais d'abord pris du Bayer 8 × 8 : sur une grande
nappe la grille se voit à l'œil nu, ce que le jeu ne fait jamais.

### Portée de la bande de rive

Proportionnelle à la nappe (85 % du 92ᵉ centile de la distance au rivage, bornée à
5–40 px). En fixe, un ruisseau ressortait entièrement clair et un océan entièrement
sombre.

### La palette de l'eau est réservée

Le DS donne à chaque tuile 8 × 8 sa propre palette de 16 couleurs. Quantifier toute
l'image sur une seule palette de 64 écrasait les bleus sous le sable et faisait
**virer les reflets au jaune**. Les couleurs de l'eau sont donc protégées, et seul le
reste passe au median-cut.

### Preuve

`preuve_eau_pmd.png` : le champ d'indices en fausses couleurs, les 4 pas de la
palette, et les 4 états rendus. `preuve_eau_pmd.json` contient la vérification
automatique — les frames sont re-rendues avec une palette de debug figée et comparées
deux à deux :

```
indices_constants : true      # aucun pixel n'a changé d'index
entrees_utilisees : 16        # la ligne de palette est pleine
couleurs_par_frame: 13        # ≤ 16, la limite matérielle
etats_distincts   : 4
ms_par_pas        : 330
```

---

## Zone `bassin_sentier`

Sentier qui entre par le **sud**, remonte vers le **nord** avec deux courbes, et
débouche sur un **bassin** bordé d'une rive de terre caillouteuse. Pas de canopée
en cadre : elle boucherait l'entrée sud, qui doit rester une entrée jouable.

La rive est animée. À l'entrée 15 de la palette près, tout est comme décrit plus
haut ; cette entrée-là cycle désormais aussi, entre le ton clair de l'eau et
l'écume : `#e7ffff → #b7e7f7 → #8fd7ef → #b7e7f7`. Le bord du bassin respire sans
qu'un pixel bouge.

68 props : roseaux et rochers sur la rive, nénuphars sur l'eau, conifères et arbres
en fond, fleurs et touffes sur l'herbe, un ponton.

## Les 10 nouvelles zones

| Zone | Props | Palette | Tuiles | Cases animées | Cellules eau |
|---|---|---|---|---|---|
| `bassin_sentier` | 68 | 64 | 2 198 | 243 | 533 |
| `foret_automne` | 55 + 50 canopée | 64 | 2 013 | 238 | – |
| `foret_bambous` | 71 | 64 | 2 300 | 236 | – |
| `canyon_desert` | 55 | 64 | 776 | 49 | – |
| `grotte_moussue` | 67 | 64 | 1 269 | 148 | 242 |
| `banquise_glacier` | 62 | 63 | 812 | 83 | 175 |
| `caverne_lave` | 43 | 64 | 718 | 90 | 603 |
| `temple_dore` | 40 | 64 | 395 | 0 | – |
| `ruines_englouties` | 52 | 64 | 1 132 | 102 | 852 |
| `grottes_marines` | 47 | 64 | 944 | 77 | 432 |

### Eau émissive

Une coulée de lave **émet** de la lumière, elle n'en reçoit pas. Sur
`caverne_lave` le grade « nuit » (×0,44 ×0,54 ×0,88) l'écrasait en brun terne. Le
calque d'eau est maintenant reposé par-dessus l'éclairage quand
`emissive=True`.

### Défaut connu : les nouvelles zones sont trop vides

L'audit d'échelle est net et je ne le maquille pas :

| Critère | Nouvelles zones | Cible (méthode) |
|---|---|---|
| Occupation du décor | **2,6 – 4,9 %** (sauf `foret_automne` à 36,8 %) | 18 – 45 % |
| Largeur locale médiane | **3,0 – 5,4 cases** | 1,0 – 3,0 |

Traduction : on peut marcher 4 à 5 cases sans que rien ne change à l'écran, ce que
la méthode interdit explicitement. Seule `foret_automne` passe, parce qu'elle a une
canopée. Le correctif est un réglage, pas une reprise : monter les `count` dans
`build_zones18.ZONES` et rejouer. À faire avant de considérer ces zones finies.

### Reste à faire

8 zones sur 18 : `jungle_clairiere`, `champ_fleurs`, `foret_nocturne`,
`cascade_foret`, `lac_foret`, `falaise_cotiere`, `sommet_montagne`, `oasis_dunes`,
`gorge_pont`. Leurs catalogues d'objets sont prêts, il ne manque que les terrains.

---

## Zones livrées

| Zone | Toile | Cases | Cellules 8 px | Calques | Frames |
|---|---|---|---|---|---|
| Pic Fleuri | 504 × 504 | 21 × 21 | 63 × 63 | 7 | 12 |
| Crique tropicale | 504 × 456 | 21 × 19 | 63 × 57 | 3 | 12 |
| Prairie au ruisseau | 504 × 456 | 21 × 19 | 63 × 57 | 4 | 12 |
| Marais brumeux | 504 × 456 | 21 × 19 | 63 × 57 | 4 | 12 |
| Caverne de cristal | 504 × 456 | 21 × 19 | 63 × 57 | 3 | 12 |

22 zones supplémentaires existent en version aplatie dans `assets/` : elles sont en
cours de reprise avec le même pipeline.

---

## Galeries

* `NOTES_PIPELINE.md` — le journal technique detaille (choix, echecs, corrections)
* `planche_pic_fleuri.html` — les 7 calques de Pic Fleuri, détaillés
* `planche_4zones.html` — les quatre zones suivantes
* `pmdo/audit/*_echelle.png` — sprites à 1:1 + grille de collision, zone par zone

Les galeries embarquent leurs images en data-URI : elles s'ouvrent hors ligne.

---

## Reproduire

```bash
pip install pillow numpy scipy pytmx
python3 rebuild_pic.py        # Pic Fleuri
python3 build_zones4.py       # plage, prairie, marais, cristal + exports
python3 pmdo/export_pmdo.py   # pack PMDO
python3 planche_4zones.py     # galerie
```
