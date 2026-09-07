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
