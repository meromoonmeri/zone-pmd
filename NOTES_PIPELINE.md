# Zone Forge — fonds de zone style PMD (originaux)

## Ce qui a été fait

1. **Étude de style** — les 338 fonds de l'album *Map Backgrounds* (Project Pokémon,
   rips PMD Explorers of Sky) ont été téléchargés dans `ref/` et analysés :
   * grille de **24 × 24 px** confirmée (toutes les dimensions en sont multiples) ;
   * **30 à 145 couleurs** par fond, toutes dans l'espace **DS 5 bits/canal**
     (valeurs 0x07, 0x0f, 0x17… = `(v>>3)*8+7`) ;
   * grammaire visuelle récurrente : cadre sombre de végétation/roche, bande de
     terrain intermédiaire, clairière organique claire au centre, contours durs 1 px,
     tramage ordonné entre les paliers de valeur.

2. **Zones redessinées** — `assets/` contient 6 fonds **originaux** produits dans cette
   esthétique, puis ramenés aux contraintes techniques du support :
   * résolution native **504 × 456** = **21 × 19 tuiles** de 24 px ;
   * palette indexée **≤ 64 couleurs**, quantifiée en espace DS 5 bits ;
   * pas de flou, pas d'anti-aliasing parasite.

## Contenu — 16 zones (`assets/`)

| Fichier | Zone | Famille |
|---|---|---|
| `zone_jungle_clairiere.png` | Clairière de la Jungle | Extérieur |
| `zone_prairie_ruisseau.png` | Prairie au Ruisseau | Extérieur |
| `zone_champ_fleurs.png` | Champ de Fleurs | Extérieur |
| `zone_foret_automne.png` | Forêt d'Automne | Extérieur |
| `zone_foret_bambous.png` | Bosquet de Bambous | Extérieur |
| `zone_cascade_foret.png` | Cascade Sylvestre | Eau |
| `zone_marais_brumeux.png` | Marais Brumeux | Eau |
| `zone_crique_plage.png` | Crique de Sable | Côte |
| `zone_falaise_cotiere.png` | Falaise Côtière | Côte |
| `zone_canyon_desert.png` | Canyon Aride | Aride |
| `zone_sommet_montagne.png` | Sommet Rocheux | Aride |
| `zone_banquise_glacier.png` | Banquise | Froid |
| `zone_caverne_cristal.png` | Caverne de Cristal | Souterrain |
| `zone_caverne_lave.png` | Caverne de Lave | Souterrain |
| `zone_grotte_moussue.png` | Grotte Moussue | Souterrain |
| `zone_ruines_englouties.png` | Ruines Englouties | Ruines |

**En attente (limite de 10 images/tour atteinte)** : Lac Tranquille, Oasis des Dunes,
Gorge et Pont, Temple Doré, Forêt Nocturne, Grottes Marines.

* `assets/x3_apercu/` — les mêmes en ×3 plus proche voisin, pour vérifier le pixel.
* `planche_zones.html` — planche contact à ouvrir dans le navigateur.
* `ref/` — les 338 références (**étude uniquement**, à ne pas livrer avec ton jeu).

## Le générateur procédural (`forge/`)

En bonus, un moteur Python qui fabrique des zones **entièrement au code** — bruit fractal,
Worley pour le grain des sols, rampes de palette, tramage Bayer, contours, props
paramétriques (fougère, buisson, rocher, cristal, colonne, cactus…), placement en
painter's algorithm.

```python
from forge.zone import build_zone
from PIL import Image
img = build_zone("jungle", tiles_w=21, tiles_h=19, seed=7, water_pool=True)
Image.fromarray(img, "RGBA").save("ma_zone.png")
```

Biomes disponibles : `jungle`, `meadow`, `beach`, `cave`, `crystal`, `desert`, `ruins`.
Il est encore un cran en dessous des zones de `assets/` côté finition — il sert à générer
des **variantes infinies** d'une même zone (change juste `seed`), pas à remplacer la passe
artistique.

## Point important

Les 338 références sont des rips d'un jeu Nintendo. Les réutiliser telles quelles dans un
fan game te met en risque et, surtout, elles ne seraient pas « à toi ». Ce qui est dans
`assets/` est original : même langage visuel, aucun pixel repris. C'est ça que tu peux
revendiquer sans mentir.

---

## Pipeline par calques (nouvelle méthode)

Animer une image **aplatie** oblige à deviner les masques — et ça rate : sur le premier
lot, le canyon désertique se retrouvait classé « lave » sur 95 000 px et la forêt nocturne
« eau » sur 230 000 px. La bonne méthode est de **produire les éléments séparément, puis
de composer**.

### Chaîne

| Étape | Fichier | Ce qui se passe |
|---|---|---|
| 1. Génération séparée | `layers/src/` | terrain plein cadre + planches d'objets sur fond **magenta pur** |
| 2. Détourage | `forge/chroma.py` | chroma key + suppression de frange + composantes connexes → un PNG RGBA par objet, mis à l'échelle native |
| 3. Masques | `forge/compose.py` | le trou magenta du terrain **est** le masque d'eau, au pixel près ; herbe/sable/roche par seuillage HSV |
| 4. Placement | `build_layered.py` | règles explicites : catégorie × surface × quota × plafond par objet (fini les 5 pontons) |
| 5. Animation | `forge/compose.py` | eau procédurale, cisaillement végétal, dérive de lumière |
| 6. Sortie | `layers/out/<zone>/` | un dossier PNG par calque et par frame + composite + GIF + `manifest.json` |

### Techniques d'animation (époque DS/GBA uniquement)

* **Eau** — bandes sinusoïdales + gradient de profondeur lissé + stries de reflet qui
  glissent + écume qui ondule le long du rivage + sparkles isolés. Boucle exacte sur 12 frames.
* **Végétation** — cisaillement vertical : la base du sprite reste clouée au sol, le sommet
  se décale de ±1 à 2 px. Phase aléatoire par objet, donc pas d'effet « tout bouge ensemble ».
* **Canopée** — même cisaillement, amplitude 1 px, phase deux fois plus lente.
* **Lumière** — taches de bruit qui dérivent + respiration globale + vignette.
  Trois layouts : `jour`, `crepuscule`, `nuit`.

### Résultat

`planche_calques.html` — vue éclatée des calques, les 3 layouts lumière, et le tableau
des techniques pour chaque zone.

Zones montées en calques : **Clairière de la Jungle** (59 props + 50 éléments de canopée)
et **Lac Tranquille** (51 props, 95 991 px d'eau au masque exact).

### Réexécuter / étendre

```bash
python3 build_layered.py          # recompose les deux zones
```

Pour une nouvelle zone : générer `layers/src/<zone>_terrain.png` (avec un aplat magenta
là où il faut de l'eau) et `layers/src/<zone>_props_sheet.png` (objets isolés sur magenta),
découper avec `forge.chroma.cut_objects`, taguer dans `layers/tags/`, puis appeler
`render()` avec les règles de placement.

---

## Zone « Pic Fleuri » — DA imposée par la référence

Montée en **7 calques séparés**, à partir d'éléments générés un par un sur fond magenta.

| # | calque | état | technique |
|---|---|---|---|
| 0 | ciel | statique | dégradé procédural |
| 1 | montagnes | **animé** | voile de brume qui glisse sur les sommets |
| 2 | nuages | **animé** | dérive ping-pong ±5 px + houle + cycling des crêtes |
| 3 | herbe | statique | bord supérieur organique (fbm) |
| 4 | falaises | statique | chaînes verticales + ombres de contact |
| 5 | fleurs | **animé** | cisaillement + bob 1 px, phase aléatoire par touffe |
| 6 | touffes | **animé** | cisaillement, phase aléatoire |

**Conformité DA** : la composition finale est reprojetée sur la palette *exacte* de la
référence fournie — 117 couleurs, espace DS 5 bits — via une LUT sur le cube couleur.
504 × 504, soit 21 × 21 tuiles de 24 px.

### Exports outils

* `tiled/pic_fleuri/pic_fleuri_tuiles.tmx` + `.tsx` + `.png`
  → 3 567 tuiles uniques, **319 tuiles animées natives Tiled** (12 frames à 110 ms).
  Chaque case dont le contenu bouge devient une `<animation>` : c'est la technique
  tilemap DS/GBA, directement éditable.
* `tiled/pic_fleuri/pic_fleuri_calques.tmx`
  → un `<imagelayer>` par calque, avec propriétés (technique, dossier de frames).
* `aseprite/pic_fleuri/pic_fleuri.aseprite`
  → 7 calques × 12 frames = 84 cels, RGBA 32 bits, grille 24 px.
  Écrit au format binaire v1.3 et **relu par un parseur de contrôle** (`forge/aseprite_export.verify`).
* `aseprite/pic_fleuri/importer_pic_fleuri.lua`
  → script d'import Aseprite, solution de repli si le binaire pose problème.

### Reconstruire

```bash
python3 rebuild_pic.py        # recompose la zone et ses 7 calques
```

**Note** : le lien GitHub fourni (`meromoonmeri/guilde-treehouse-pmd`) renvoie un 404 —
dépôt privé ou branche absente. La méthode ci-dessus est donc la mienne, pas celle de
ton autre agent.

---

## Quatre zones supplémentaires en calques

`plage`, `prairie`, `marais`, `cristal` — même chaîne que Pic Fleuri, pilotée par
un seul script.

```bash
python3 build_zones4.py       # compose les 4 zones + exports Tiled et Aseprite
python3 planche_4zones.py     # regénère la galerie HTML autonome
```

| zone | props | canopée | palette | tuiles Tiled | cases animées | cels Aseprite |
|---|---|---|---|---|---|---|
| Crique tropicale (`plage`) | 39 | – | 62 | 2 896 | 273 / 399 | 36 |
| Prairie au ruisseau (`prairie`) | 54 | 50 | 63 | 2 659 | 280 / 399 | 48 |
| Marais brumeux (`marais`) | 50 | 50 | 64 | 4 010 | 361 / 399 | 48 |
| Caverne de cristal (`cristal`) | 46 | – | 64 | 859 | 50 / 399 | 36 |

Chaque zone : 504 × 504 (21 × 19 tuiles de 24 px), 12 frames à 110 ms, quantification
DS 5 bits par canal.

### Trois décisions techniques de cette passe

**La lumière n'est pas de la donnée de tuile.** La respiration lumineuse et les taches
de soleil dérivantes modifient *tous* les pixels à chaque frame. Bakées dans le tileset,
elles rendaient 399 cases sur 399 « animées » et gonflaient les tilesets jusqu'à 5 000
tuiles. Le rendu produit donc deux jeux de frames : `frames/` (lumière animée → GIF et
Aseprite) et un jeu à lumière figée qui sert de source à l'export Tiled. La caverne de
cristal passe ainsi de 3 909 à **859 tuiles**, et seules les 50 cases de la flaque
bougent réellement.

**Les rayures d'eau.** Une houle en `sin(y·k + warp − φ)` produit des bandes horizontales
pleine largeur : effet moquette côtelée, très visible sur l'océan de la plage. Deux
termes en `x` de fréquences incommensurables ont été ajoutés dans le seuil de strie, ce
qui casse les lignes en clapot sans toucher au dégradé de profondeur.

**Le sentier de la caverne.** Le générateur sortait un sable chaud, incohérent sous
terre. `build_zones4.cool_path()` isole les pixels de teinte 28°–72° et les rebascule
vers un gris-bleu minéral **à luminance conservée** : la couleur change, la texture
pixel par pixel reste intacte.

### Répartition des props

Dispersion sous contraintes plutôt que tirage uniforme — un tirage uniforme donne un
tapis illisible et cinq pontons identiques. Chaque règle déclare sa surface d'accueil
(`ground`, `shore`, `midband`, `water`, `inner`), une distance minimale, un plafond par
objet et une amplitude de cisaillement.

### Galerie

`planche_4zones.html` — les quatre zones animées, leurs calques frame 0 (fond magenta
visible : c'est la couleur-clé), rampes d'eau, catégories détourées et compteurs.

---

## La clairière corrigée, décomposée en 3 étages (Le Bosquet Sacré)

Reprise du travail interrompu du commit « plaques de base de la clairière avec
bordures feuillues, sans rayon ». Rien n'a été supprimé : les essais
`recup_clairiere_v1..v3`, les plaques `clairiere_base_a/b` et la planche
`bordure_feuillue_sheet` sont conservés — la bordure est même découpée et posée.

**Le défaut, mesuré.** La référence (423×400, 182 couleurs) a un profil radial
net : anneau externe vert moyen L≈110 (#53853e), transition L≈161, cœur sable
L≈215 (#f0d794). Les trois essais précédents sortaient un centre gris-vert
(L=148/177/173) : la clairière n'était jamais sableuse. Écart moyen du meilleur
essai : 17,7.

**La correction.** Le terrain est repeint au code, 504×456, dans la grammaire
relevée : cadre organique (frame_falloff + wobble fbm) → bande d'herbe →
clairière sableuse en blob fbm + sentier sud en sinus garé dans le couloir.
Les rampes sont extraites de la référence par classe hue/luminance (p22/p50/p80,
4 tons pour le sable). Trame 0,70 Bayer + 0,30 aléatoire, contours durs 1 px
(levre sombre du sable, ligne de tenebre du cadre). Contrôle après peinture :
anneau L=110-114 (réf 110), cœur L=185-193.

**La bordure feuillue « sans rayon ».** La planche est un kit : 15 morceaux,
dont 12 de 200-440 px. Trop sombres (L=24-62) pour l'anneau L≈110 : leur
luminance est remontée (gain borné 1,15-2,3, cible L≈95) sans toucher aux
teintes, puis les gros morceaux sont posés le long des bords (haut, flancs,
coins bas — le couloir sud reste dégagé), mis à l'échelle 0,46, miroités.
Les 5 petits deviennent un catalogue de props « bordure » pour le pipeline.

**Trois layouts = trois étages.** B1F Lisière (jour, ouverte, arbres épars,
largeur 3,33 — l'étage d'entrée le plus ouvert), B2F Clairière Sacrée
(crépuscule, mare + roseaux + nénuphars, couronne d'arbres), B3F Cœur
(nuit, mare centrale + ruisseau qui sort à l'est, futaie dense). Occupation
34,6-35,4 % (cible 18-45), largeur locale 2,00-3,33 (cible 1-3).

**Deux pièges corrigés en route.**
1. La canopée pose en anneau sans connaître le couloir : elle refermait
   l'entrée sud (profondeur 4-5). `build_clairiere` filtre les morceaux du bas
   qui chevauchent le couloir — les trois entrées sud tombent au bord (prof 0).
2. Sans canopée, B2F n'avait que 4,8 % de cellules bloquées et une largeur
   locale de 5,7 : la canopée est un calque « bloc » chez PMDO, c'est elle qui
   ferme la lisière. B2F l'a récupérée (35,4 % / 2,67).

**Descripteur de donjon.** `layouts/clairiere_sacree.json` chaîne les étages
(entrées relevées sur la grille 8 px, lien sud → étage suivant, variantes
d'arène bosquet référencées). `planche_clairiere.html` : référence vs v3 vs
corrigé, les trois étages et leurs collisions, les chiffres de l'audit.

## La clairière de l'utilisateur, au scale PMDO — intacte

**La demande, corrigée après un impair.** Une première livraison a repeint
l'image au style Explorers of Sky : rejetée (« retire j'ai pas demandé que
tu modifies mon image ») — revert propre, puis reprise depuis les masters
natifs 1120 × 960 de la branche `arena/01a08169` (commit 0f9805e), recopiés
intégralement dans `layers/src/clairiere_master/`. Cette fois l'image est
mise au scale **telle quelle** : ni filtre, ni recoloration, ni snap DS.

**La géométrie.** 1120 × 960 n'est pas un multiple de 24 → aucun facteur
entier. Méthode : rognage centré au multiple de 48 (1008 × 912 : −112 px
de large, −48 px de haut), puis division par 2 au plus proche voisin →
504 × 456 = 21 × 19 cases = 63 × 57 cellules de 8 px, 2,99 écrans.

**Deux pièges corrigés en route.**
1. Le plus proche voisin de PIL échantillonne les indices *impairs*
   (2x+1) : la formule documentée (master en 2x+56, 2y+24) était fausse.
   La division est refaite à la main en numpy (`[::2, ::2]`) pour que la
   preuve soit littérale — les 39 fichiers sont vérifiés pixel par pixel,
   et la palette de sortie est un sous-ensemble strict de celle du master
   (102 675 couleurs conservées, 0 inventée).
2. Les exports PMDO de la branche voisine sont resamplés en flou
   (base 1088 × 976, calques 504 × 456 non alignés, aucune collision) :
   remplacés par le pack recalculé, même structure (Base/Water/Light,
   Light = `lumiere_simple` — 93 % de recouvrement après scale, leur
   choix final).

**La collision vient de leurs calques décomposés.** `render_layers/bassin.png`
→ eau (≥ 55 %/cellule), `render_layers/arbres.png` → bloqué
(≥ 30 %/cellule). `arbres.png` et `vegetation.png` sont identiques (un
seul compte). La canopée couvre 43,8 % de la moitié haute du master : la
bande bloquée du haut de la grille est fidèle à leur art. Occupation
22,4 %, eau 6,9 %, largeur locale 9,3 cases — l'image est plus ouverte
que les cibles du générateur, c'est la leur.

**Livrables.** `pmdo/clairiere/` (fond composite Base + Water f01 +
Light f01 dans l'ordre de leur tmx, calques animés, les trois jeux de
lumière scalés, obstacles.json/.txt, collision.tmx 8 px + brosse,
clairiere.tmx 3 imagelayers, audit_echelle.png, ground.json, README.md,
entrée `clairiere` ajoutée au rapport — 14 zones),
`tiled/clairiere/` (calques + carte 21 × 19 @24 + render_layers scalés),
et la variante `variant_552x480/` (1104 × 960 → 552 × 480 = 23 × 20
cases) qui ne rogne que 16 px de large : 98,6 % de l'image conservée.
Tout est produit par `scale_pmdo.py`, rejouable.

---

## Le ground PMDO de la clairière à l'arbre ancien — critères Luminous Spring

**La demande.** La zone en frames 1/2/3/4/5/6/7/8, aux mêmes critères
PMDO que le Luminous Spring de Palika (mod Halcyon) : dimension,
viewport, grille, etc. La zone avait déjà ses planches `.tile` 8 px —
il manquait les deux fichiers que le moteur charge réellement.

**Rétro-ingénierie depuis les sources RogueEssence (RogueCollab).** Le
`.rsground` est un JSON `GroundMap` : `TexSize` donne la taille de case
(1→8 px, 3→24 px), `obstacles` est `[l×TexSize][h×TexSize]` murs de
8 px en **pixels**, `Tags` est un bitmask où 0 = libre et tout le reste
bloque (`SlideResponse`) — l'eau de Luminous Spring et les murs de la
guilde sont tous `1`. Les calques sont `Tiles[x][y]` d'`AutoTile`, dont
la liste `Layers` de `TileLayer` anime `Frames[]` toutes les
`FrameLength` frames de 120 ticks ; l'animation par case, pas par
plancher. Le `.tile` est un binaire : entête `TileIndexNode`
[ int32 tailleTuile ][ int32 nombre ] puis `nombre × (int32 x, int32 y,
int64 position)` et les entrées `[ int64 longueur ][ PNG 8×8 ]` —
l'encodage d'index de notre `forge/tile_rogue.py` (`clé = y<<32|x`)
est byte-à-byte celui du moteur en little-endian. L'`index.idx` est un
`TileGuide` : [ int32 nombre ] puis par planche une chaîne .NET
(longueur 7 bits + UTF-8) et son `TileIndexNode` ; le moteur les
fusionne en fallforth, clé par clé — d'où la fusion additive avec
l'index du mod cible (181 + 6 = 187 planches).

**La construction.** TexSize 1 (nos planches sont en 8 px, comme
`illuminant_riverbed`/`Altere_Pond` chez Palika ; Luminous Spring est
en 24 px — les deux sont des cartes moteur valides, la taille suit
l'art). Obstacles dérivés de `collision.png` (2445 solides). Calque
Base (statique, FrameLength 60) + calque River : les 292 cases d'eau
avec **8 frames** (4 dessins × maintien 2, FrameLength 10 = 165 ms, le
`frame_ms` du manifest), chaque frame pointant la planche de son
dessin. `South_Exit` en entité sur l'entrée sud (collider 72×8 px).
Les ombres sont déjà cuites dans la base — le calque `Shadows` n'est
pas référencé par la carte (il serait doublé), il reste indexé et
disponible.

**La preuve.** `ground_pmdo.py` relit tout et re-rend la carte comme le
moteur : les 8 frames re-rendues depuis les binaires == les frames
livrées, **écart max 0** ; obstacles == collision.png ; l'index
round-trip ; et le code de lecture valide sur les vrais fichiers
Halcyon (leur `index.idx` de 181 planches, les positions
`Illuminant_Riverbed_River_Animations` pointent des PNG 8×8 valides).
Le schéma du `.rsground` est comparé clé par clé à celui de
`luminous_spring.rsground` — seules manquent les clés des NPC/spawners,
vides ici.

**Livraison.** `pmdo/clairiere_arbre/ground/` : `Content/Tile/`
(6 planches + index fusionné), `Data/Ground/clairiere_arbre.rsground`,
`frames/frame_1..8.png` + `viewport.gif` (320×240 sur le bassin),
`apercu_ground.png`, README d'installation drop-in.
