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
| `layouts/` | descripteurs de donjons multi-étages (zones chaînées en layouts) |

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

## La colorimetrie stricte de Halcyon

Relevee sur 5 de ses banques `.tile` (Altere Pond Base, Objects, Cliffs,
Fringe, Metano Town Objects), soit **36 326 cases de 8 px** :

| Critere | Halcyon | Mon rendu avant | Mon rendu apres |
|---|---|---|---|
| Grille de couleur | **multiples de 8** (`v>>3<<3`), 70,9 % des pixels | `(v>>3)*8+7` — **7 crans trop clair** | multiples de 8, 100 % |
| Couleurs par tuile 8x8 | mediane **7**, 97,1 % a 16 ou moins | non contraint | mediane **8**, 100 % |
| Luminance p50 | **158** | 97 | **147** |
| Saturation p50 | **0,63** | 0,58 | 0,57 |
| Ecart Lab a sa palette | — | 11,8 | **0,00** |

Trois choses en sont sorties.

**1. Mon quantificateur DS etait faux.** `core.ds_quant` faisait `(v>>3)*8+7`.
Lui est sur les multiples de 8. Chaque composante de chaque pixel etait donc
**7 niveaux trop claire**, systematiquement. `palette_halcyon.ds8()` corrige.

**2. Il respecte la contrainte DS des 16 couleurs par tuile de 8 px** — celle
que documente le wiki SkyTemple pour Tilequant. Sa mediane est meme a 7.
`contraindre_tuiles()` la force ; a 8 couleurs par tuile la difference avec 16
est invisible au zoom x2 (voir `comparaison_tuiles.png`).

**3. Sa direction artistique est bien plus claire que la mienne** : L p50 158
contre 97. `exposer()` recale p5, p50 et p95 sur les siens par une courbe
monotone, sans toucher aux teintes.

Sa palette : **746 couleurs couvrent 99 % de ses pixels**, ramenees a **654**
apres alignement sur la grille de 8. Elles sont dans
`assets/palette_halcyon.json`, le nuancier dans `palette_halcyon.png`.

`COLORIMETRIE = "halcyon"` en tete de `build_zones18.py` ; `"libre"` revient au
median-cut a 64 couleurs.

### Ce que sa palette ne couvre pas

Elle vient d'une ville, d'une mare et d'une caverne de gres : riche en verts,
ocres et bruns, **pauvre en bleus profonds, violets et tons de glace**.
`couverture()` mesure l'ecart Lab avant contrainte :

| Terrain nu | Ecart moyen | Verdict |
|---|---|---|
| `foret_automne` | 7,09 | entre dans sa colorimetrie |
| `bassin_sentier` | 11,83 | limite |
| `banquise_glacier` | 12,97 | limite |
| `caverne_lave` | 17,69 | **hors de sa palette** |

Contraindre une banquise ou une coulee de lave a ses 654 couleurs deplace
fortement les teintes. Pour ces biomes il faudrait relever une palette sur un
de ses lieux froids ou volcaniques, s'il en a.

### Sur le reemploi de tuiles

Son `Metano_Town_Base` reemploie 9,07x, mais son `Crooked_Cavern_Base` seulement
1,41x. Le premier est une ville a grandes pelouses plates, le second un ecran
peint. Mes zones sont a 1,04x : **en ligne avec sa carte peinte, pas avec sa
ville**. Serrer les couleurs par tuile n'y change rien (verifie de 16 a 6
couleurs : le reemploi reste a 1,04x) — il faudrait un motif de sol repetitif,
pas un bruit continu.


---

## Les zones montees sur sa structure de calques

Releve sur `Data/Ground/altere_pond.rsground` : son ground map compte **huit
calques nommes, dans un ordre fixe**, chacun avec **son propre tilesheet**
baptise `<Carte>_<Calque>`.

| # | Calque | Lui, Altere Pond | Ce que j'y mets |
|---|---|---|---|
| 0 | Base | 10 251 tuiles, 1 frame | le terrain |
| 1 | River | 1 036 tuiles, **toutes** en 4 frames | la nappe d'eau |
| 2 | Cliffs | 1 840 tuiles, 1 frame | falaises, colonnes, stalagmites, piliers |
| 3 | Shadows | 56 tuiles, 1 frame | les ombres de contact, **en calque a part** |
| 4 | Objects Under | 841 tuiles, 232 en 4 frames | ce sur quoi on marche : nenuphars, mousse, litiere, dalles |
| 5 | Objects | 4 604 tuiles, 592 en 4 et 8 frames | les props principaux |
| 6 | Objects Over | 150 tuiles, 74 en **3 frames** | la canopee, ce qui recouvre le joueur |
| 7 | Fringe | 2 075 tuiles, 1 frame | les raccords, dessines **en dernier** |

Trois choses que j'ai reprises et qui changent le montage :

1. **Les ombres portees deviennent un calque.** Elles etaient cuites sous les
   props ; elles sont maintenant extraites et empilees a part, entre Cliffs et
   Objects Under. Controle sur `bassin_sentier` : 86 taches pour 91 props.
2. **Fringe passe apres tout le monde**, donc par-dessus le joueur.
3. **Le nombre de dessins distincts d'un calque anime est petit et fixe** : 4
   pour River, Objects Under et Objects, **3** pour Objects Over. Avant, la
   houle etait echantillonnee sur les 12 frames de sortie, ce qui faisait 12
   dessins la ou il en a 4. La boucle rend toujours 12 frames, mais elles ne
   piochent que dans K dessins.

Le tilesheet d'un calque anime est le calque **dessine K fois de suite
horizontalement sur fond magenta**, exactement comme sa
`Altere_Pond_River_Animations` (4 copies, periode 336 px). Chez moi :
`pmdo/<zone>/sheets/<zone>_River.png`, 2016 x 456, periode 504 px.

`ground.json` porte la table complete sous `calques_halcyon` : par calque,
l'ordre, le nom, le dossier, le sheet, la periode, les tuiles posees, les
tuiles reellement animees et la tenue en frames.

### 20 zones montees

| Zone | Calques utilises | Tuiles 8 px | Animees |
|---|---|---|---|
| `lac_foret` | 7 | 8 861 | 2 691 |
| `foret_automne` | 5 | 7 969 | 1 779 |
| `cascade_foret` | 8 | 7 583 | 1 813 |
| `falaise_cotiere` | 7 | 7 096 | 1 023 |
| `gorge_pont` | 7 | 7 084 | 730 |
| `entree_grotte` | 5 | 6 623 | 489 |
| `entree_arbre` | 4 | 6 503 | 730 |
| `ruines_englouties` | 7 | 6 485 | 1 035 |
| `bassin_sentier` | 6 | 6 443 | 1 359 |
| `caverne_lave` | 7 | 6 548 | 582 |
| `pied_montagne` | 6 | 6 521 | 1 003 |
| `banquise_glacier` | 7 | 6 375 | 353 |
| `grotte_moussue` | 7 | 6 203 | 558 |
| `forest_bambous` | 3 | 5 776 | 1 101 |
| `canyon_desert` | 4 | 5 693 | 221 |
| `grottes_marines` | 6 | 5 543 | 602 |
| `entree_source` | 7 | 5 369 | 647 |
| `temple_dore` | 5 | 5 365 | 0 |
| `entree_ruines` | 4 | 5 187 | 179 |
| `sommet_montagne` | 4 | 5 145 | 140 |

Une zone n'utilise que les calques dont elle a besoin : `temple_dore` n'a ni
riviere ni canopee, `foret_bambous` n'en remplit que trois.

### Ce qui reste en dessous de lui

Mon **Fringe est pauvre** : 102 tuiles la ou il en a 2 075. Chez lui c'est un
vrai tileset de raccords, dessine a la main, avec des debords d'herbe et de
roche qui recouvrent le joueur. Chez moi ce n'est qu'un liseré de contact d'un
pixel. Le combler demande de dessiner des tuiles de transition, pas de changer
le montage.

Et ses **props a 8 frames** (160 tuiles chez lui) sont ramenes a 4 : avec une
boucle de 12 frames, 8 ne tombe pas juste. Il faudrait passer la boucle a 24.


---

## L'eau a la maniere de Palika (Halcyon)

Releve fait directement sur ses fichiers, pas de memoire :
`Content/Tile/Altere_Pond_River_Animations.tile` decode en planche, et
`Data/Ground/altere_pond.rsground` lu pour la structure d'animation.

Le `.tile` de RogueEssence est une banque de tuiles 8x8 : entete
`int32 taille, int32 nombre`, puis `nombre` x `(int64 cle, int64 offset)`, et a
chaque offset un `int64 longueur` suivi du PNG. La cle encode la position :
`y = cle >> 32`, `x = cle & 0xffffffff`. Recomposee, la planche fait
1368 x 480 px.

**Et la, tout devient clair : il n'y a pas de palette cycling.** Sa planche
contient **la meme mare quatre fois de suite**, periode 336 px, sur fond
magenta. Le ground map pointe des listes `Frames` de longueur 4 (1 700 tuiles)
et 8 (160 tuiles). Ce sont de **vraies frames redessinees**.

Ce que mesure sa nappe :

| | Palika, Altere Pond |
|---|---|
| Corps de l'eau | **un aplat**, `#83dae6` sur 78,6 % des pixels |
| Couleurs totales | 15 |
| Liseré de berge | 4 px, trois valeurs (`#5787bf`, `#5291c5`, …) |
| Px changeant par frame | ~6 600, dont **84 % a l'interieur** |
| Frames | 4 |

Autrement dit : le contour ne bouge presque pas, ce sont les petits **traits
clairs en virgule** plaques dans la nappe qui sont redessines.

### Ce que ca change chez moi

`forge/water_halcyon.py` reprend sa structure et ses rapports de valeurs, mais
tire les teintes de la rampe de la zone : une mare de village reste cyan clair,
une coulee de lave resterait orange. **Sa methode, pas ses pixels.**

Controle sur `bassin_sentier` :

| | Palika | moi |
|---|---|---|
| Part de l'aplat | 78,6 % | **79,3 %** |
| Couleurs dans l'eau | 15 | 8 |
| Px changeant par frame | ~6 600 | 1 400 – 4 800 |

Zones repassees a sa methode : `bassin_sentier`, `lac_foret`, `cascade_foret`,
`entree_source`, `gorge_pont`, `falaise_cotiere`, `pied_montagne`.

### Attention, les deux methodes se contredisent

La consigne precedente etait « l'eau exactement comme dans PMD Sky », c'est-a-dire
**palette cycling, aucun pixel ne bouge**. Palika fait l'inverse : il redessine.
Les deux sont justes, mais pour des cibles differentes — le palette cycling est
la contrainte du **fond de donjon DS**, les frames redessinees sont ce que
permet **RogueEssence sur un ground map**.

Les deux restent dans le depot :

* `forge/water_pmd.py` → `style_eau="sky"` (palette cycling, 16 entrees)
* `forge/water_halcyon.py` → `style_eau="halcyon"` (4 frames) — **defaut actuel**,
  regle par `STYLE_EAU` en tete de `build_zones18.py`.

Les fichiers de Palika servent de **reference d'etude uniquement** : ils sont
dans `ref_etude/halcyon/`, qui est exclu du depot. Aucun de ses pixels n'est
livre ici.


---

## L'eau, deuxieme passe : ce que montrent les vrais fonds

Le premier jet mettait des **tirets clairs horizontaux** sur un aplat bleu. Vu
sur la zone, ca faisait des traits blancs colles sur l'eau. J'ai repris les
fonds originaux gardes dans `ref_etude/` pour mesurer au lieu de deviner.

Ce que disent les mesures (luminance, 0-255) :

| | corps de l'eau p5 / p50 / p95 | ecart des reflets |
|---|---|---|
| `D17P31A` (nappe pleine) | 59 / 95 / 196 | ~20 |
| `D01P41A` (grotte de la plage) | 57 / 89 / 234 | ~20 |
| moi, 1re version | **80 / 80 / 179** | **+99** |
| moi, apres correction | 80 / 80 / 191 | ~20 |

Trois erreurs, trois corrections :

1. **Le corps etait un aplat parfait** (p5 = p50 = 80). Sur les vrais fonds la
   surface est nuancee partout. → la profondeur est melangee a un grain fbm
   avant tramage.
2. **Les reflets etaient des tirets horizontaux.** Sur `D17P31A` ce sont des
   **boucles fermees fines et irregulieres** qui se croisent. → les reflets sont
   maintenant les **lignes de niveau** d'un champ fbm lisse : `|u - round(u)| <
   epaisseur`. Chaque anneau demarre sur une phase differente, donc la crete de
   lumiere traverse le reseau de boucle en boucle.
3. **L'ecart de luminance etait cinq fois trop grand** (+99 au lieu de ~20).
   → `CRETE` adoucie et amplitude ramenee de `0.30 + 0.16·calme` a
   `0.11 + 0.07·calme`.

Et le blanc vif ? Il existe bien dans EoS, mais **colle a la berge** : sur
`D01P41A`, 22 % des pixels a 1 px du bord depassent L=200 contre 11 % au large.
C'est l'ecume (entree 15) qui le porte, pas le corps de la nappe.

### Le tramage ne doit pas se voir comme une grille

Premiere correction faite, un damier regulier apparaissait sur toute la nappe :
la valeur restait au milieu de la plage, donc Bayer 4x4 alternait un pixel sur
deux partout. Deux ajustements :

* la valeur est **saturee** (`0.5 + (v-0.5)·2.6`) : les tons sont pleins, la
  trame n'apparait plus que dans la bande de transition entre deux tons ;
* la trame est **bruitee** (`0.70·Bayer + 0.30·aleatoire`). Les fonds d'EoS sont
  trames a la main, le motif n'y est pas mecaniquement regulier.

Le principe n'a pas bouge : **aucun pixel ne se deplace**, seule la ligne de
palette change au fil des pas.

## Sommet, pied de montagne, entrees de donjon

| Zone | Ce que c'est | Eau | Props | Tuiles | Cases animees |
|---|---|---|---|---|---|
| `sommet_montagne` | plateau mineral, a-pics, cairns | – | 66 | 669 | 46 |
| `pied_montagne` | prairie montant vers la falaise, ruisseau | oui | 108 | 2 075 | 238 |
| `entree_grotte` | clairiere, gueule de grotte au nord | – | 125 | 1 406 | 139 |
| `entree_arbre` | creux d'un arbre colossal | – | 100 | 1 670 | 188 |
| `entree_ruines` | escalier de pierre descendant dans le noir | – | 70 | 879 | 70 |
| `entree_source` | terrasse a anneaux, source ronde | oui | 65 | 1 398 | 116 |
| `cascade_foret` | vasque et ruisseau | oui | 54 + 50 | 2 349 | 322 |
| `lac_foret` | grand lac et ilot | oui | 61 + 50 | 2 821 | 355 |
| `gorge_pont` | chasme, riviere, ponts de planches | oui | 60 | 1 139 | 150 |
| `falaise_cotiere` | falaise, greve, mer | oui | 56 | 1 559 | 196 |

Les quatre entrees de donjon ont toutes le meme parti : le chemin entre par le
**bord sud**, l'ouverture est au **nord**, l'interieur est noir plein. C'est
directement jouable comme point d'entree PMDO.

Densite relevee au passage (`DENSITE = 1.35` dans `build_zones18.py`, un seul
reglage pour toutes les zones) apres l'audit qui donnait 3 a 5 % d'occupation.
Un essai a 2.4 donnait un tapis de props illisible : 1.35 est le compromis.


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

## La clairière corrigée — Le Bosquet Sacré, 3 étages

La map demandée sur `recup_reference.png` avait un défaut mesuré : la référence
montre un centre **sable chaud** (#d3c688, L=195), les trois essais précédents
(`recup_clairiere_v1..v3`) sortaient un centre **gris-vert** (#879d85 → #a2b3a6,
L=148-177). La correction repeint le terrain dans la grammaire exacte de la
référence — les rampes sont **extraites de ses pixels**, pas choisies :

| Profil radial | Référence | Corrigé |
|---|---|---|
| Anneau externe (0-25 % du bord) | vert moyen **L≈110** (#53853f) | **L=110-114** |
| Cœur de clairière | sable **L≈215** (#f0d794) | **L=185-193** avant grade |
| Bordure feuillue « sans rayon » (L=24-62) | — | remontée à L≈95, posée sur le cadre |

`build_clairiere.py` produit tout : terrains, découpe et pose de la bordure
feuillue du commit précédent (conservée et utilisée), composition, exports.

### Décomposition en layouts : 3 étages chaînés

| Étage | Titre | Lumière | Eau | Occupation | Largeur locale |
|---|---|---|---|---|---|
| `clairiere_b1f` | Lisière du Bosquet | jour | – | 34,6 % | 3,33 cases* |
| `clairiere_b2f` | Clairière Sacrée | crépuscule | mare, 4,7 % | 35,4 % | 2,67 |
| `clairiere_b3f` | Cœur du Bosquet | nuit | mare + ruisseau, 11,2 % | 34,9 % | 2,00 |

\* l'étage d'entrée est volontairement le plus ouvert ; les cibles de la
méthode sont 18-45 % et 1-3 cases.

Chaque étage est un pack complet et indépendant (`layers/rendu/`, `tiled/`,
`aseprite/`, `pmdo/` avec collision 8 px et `ground.json`), et les trois sont
chaînés en donjon par **`layouts/clairiere_sacree.json`** : étages, entrées
relevées sur la grille, liens sud → étage suivant, variantes d'arène bosquet
existantes référencées. Les entrées sud sont ouvertes au bord (profondeur 0) :
la canopée est filtrée sur le couloir d'entrée pour ne pas le refermer.

`planche_clairiere.html` — la planche de contrôle : référence vs essai v3 vs
corrigé, les trois étages, leurs collisions, les chiffres.

```bash
python3 build_clairiere.py            # les 3 étages + planche + descripteur
python3 build_clairiere.py --terrain  # seulement repeindre les terrains
```

---

## La clairière du dépôt voisin, au scale PMDO — l'image intacte

L'autre clairière (masters natifs **1120 × 960**, branche
`arena/01a08169`, recopiés dans `layers/src/clairiere_master/`) mise au
scale PMDO **sans être modifiée** : ni repeinte, ni filtrée, ni recolorée.

**La géométrie du scale.** 1120 × 960 n'est pas un multiple de 24 : aucun
facteur entier n'en fait une toile PMDO. On rogne donc au centre au multiple
de 48 (**1008 × 912**, −112 px de large, −48 px de haut) puis on divise par
2 **au plus proche voisin** → **504 × 456 = 21 × 19 cases = 63 × 57 cellules
de 8 px**. La grille de collision tombe pile sur l'art.

**La preuve que rien n'est inventé.** La division est faite à la main
(pixel 2x, 2y) : chaque pixel de sortie est **égal** au pixel du master en
(2x+56, 2y+24) — vérifié pixel par pixel sur les 39 fichiers, et la palette
de la sortie est un sous-ensemble strict de celle du master
(102 675 couleurs conservées, **0 inventée**).

**La collision vient de leurs propres calques décomposés** :
`render_layers/bassin.png` → eau (`~`, ≥ 55 %/cellule),
`render_layers/arbres.png` → bloqué (`#`, ≥ 30 %/cellule). La canopée
couvre toute la moitié haute chez eux (43,8 % d'alpha) : la bande bloquée
du haut est fidèle à leur art, pas un artefact.

Pack complet dans `pmdo/clairiere/` (fond, calques Base/Water_f01-08/
Light_f01-08 — Light = `lumiere_simple`, leur choix final —, les deux
autres jeux de lumière scalés aussi, obstacles, `collision.tmx` 8 px éditable
à la brosse, `clairiere.tmx` 3 imagelayers, `audit_echelle.png`,
`ground.json`, `README.md`), calques + carte côté `tiled/clairiere/`, et la
**variante 552 × 480** (23 × 20 cases) qui ne rogne que 16 px de large
(98,6 % de l'image conservée) dans `pmdo/clairiere/variant_552x480/`.

Audit : occupation 22,4 %, eau 6,9 %, largeur locale 9,3 cases, 2,99 écrans.
Entrées ouvertes : sud, ouest, est.

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
python3 scale_pmdo.py         # la clairiere 1120x960 au scale PMDO, intacte
python3 planche_4zones.py     # galerie
```
