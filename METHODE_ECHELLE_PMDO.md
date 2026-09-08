# La méthode « scale to PMDO » — expliquée, puis appliquée à la clairière

## D'où vient la méthode

Elle a été relevée dans **`guilde-treehouse-pmd`** (`ANALYSE_ECHELLE.md`, branches
`arena/…`) : l'étude des ground maps de RogueEssence/PMDO et des banques `.tile`
de Halcyon. Ce dépôt est privé et **inaccessible depuis cette session** (404,
token bot sans invitation) — mais la méthode y est intégralement **rejouée dans
zone-pmd** : section *Échelle PMDO* du `README.md` et implémentation chiffrée
dans `pmdo/audit_echelle.py`. C'est cette implémentation de référence que
j'applique ci-dessous, mesure par mesure.

## Les règles, mesurées sur le moteur

| # | Règle | Valeur | Pourquoi |
|---|---|---|---|
| 1 | Cellule de collision d'une ground map | **8 px** | c'est la granularité du moteur |
| 2 | Case de lecture PMD | **24 px = 3×3 cellules** | le pas du décor et des sprites |
| 3 | Viewport logique | **320×240 px** | ce que l'écran montre |
| 4 | Sprite Pokémon | 19-27 × 20-22 px (≈ 1 case) | l'étalon de lisibilité |
| 5 | Toile | **504×456 (21×19 cases)** — multiple de 8 **et** de 24 | la grille de collision tombe **pile** sur l'art |
| 6 | **Zéro rééchantillonnage** | l'art est **produit** à cette résolution | un master réduit ne retombe jamais juste : flou + grille décalée |
| 7 | Couleurs | espace DS (grille des multiples de 8, ≤ 16 couleurs par tuile 8×8) | la contrainte matérielle |
| 8 | Audit chiffré | emprise 1-4 écrans, largeur locale 1-3 cases, occupation 18-45 %, sprites étalon posés **à 1:1**, entrées relevées sur la grille | la conformité se prouve, elle ne se déclare pas |

La règle 6 est celle qui décide de tout : **une ground map PMDO n'est pas une
tilemap**, c'est une image de fond **plus** une grille de collision. Si l'image
a été réduite d'un master, les cellules de 8 px ne tombent plus sur les
contours du pixel art — la collision coupe les sprites en travers et le rendu
est flou. D'où la règle du dépôt : *« la grille de collision tombe donc pile
sur l'art existant — aucun rééchantillonnage, donc aucune perte de netteté »*.

## L'autopsie du commit `0f9805e` (branche `arena/01a08169-zone-pmd`)

« Reconstruit la clairiere au format PMDO Tiled » — vérifié au pixel, ce
commit viole six des huit règles :

| Mesure | Règle | Leur export | Méthode |
|---|---|---|---|
| Toile du fond (`base.png`) | 504×456 | **1088×976** — ni 21×19 cases, ni multiple de 24 | 504×456 natif |
| Calques « PMDO » | natif | **rééchantillonnés** d'un master 1120×960 (facteur 0,45) | peints en 504×456 |
| Grille DS (multiples de 8) | 100 % | **0 %** | **100 %** |
| Contours durs 1 px (netteté) | contours EoS | **2,7 %** (flou de resample) | 6-10 % |
| Couleurs (espace DS borné) | ≤ 64 | **~21 000** | ≤ 466 |
| Collision 8 px (`obstacles.json`, `collision.tmx`) | obligatoire | **absente** | fournie + brosse Tiled |
| Tileset 24 px animé | `tiled/` natif | **absent** (3 imagelayers ; les frames f01..f08 existent mais le tmx n'en câble aucune) | `.tmx`/`.tsx` avec `<animation>` |
| Audit d'échelle (`ground.json`) | obligatoire | **absent** | 5/5 (voir plus bas) |

Le README du pack prétendait « exports lossless à la résolution PMDO, sans
rééchantillonnage » — le fichier `base.png` ne fait même pas la taille annoncée.
`comparaison_pmdo.png` montre les deux exports côte à côte avec un zoom ×4 sur
la même zone : à gauche le flou du rééchantillonnage, à droite les contours
durs 1 px.

## L'application correcte : la zone `clairiere`

Reconstruite de zéro par `build_clairiere.py`, **peinte nativement en
504×456** (règle 6) dans la grammaire de la référence — jamais passée par un
master 1120×960 :

* **Terrain** : cadre organique → herbe → clairière sableuse + sentier sud +
  bassin, rampes extraites de `recup_reference.png`, contours durs 1 px,
  tramage ordonné, 100 % des pixels sur la grille DS.
* **Pack `pmdo/clairiere/`** : `fond.png`, `fond_frames.png` (24 frames),
  `calques/` (Base, River, Shadows, Objects, Objects Over, Fringe — structure
  Halcyon), `sheets/` (planche par calque animé, période 504 px),
  **`obstacles.json`/`.txt` + `collision.png` + `collision.tmx` + brosse 8 px**
  (libre / bloqué / eau), et **`ground.json`**.
* **`tiled/clairiere/`** : `clairiere_tuiles.tmx`/`.tsx` — tileset **24 px avec
  tuiles animées natives Tiled** — plus `clairiere_calques.tmx` (imagelayers).
* **`pmdo/audit/clairiere_echelle.png`** : sprites étalon posés à 1:1, cadre du
  viewport 320×240, grille 8 px et lignes 24 px.

### L'audit, chiffre par chiffre (5/5)

| Critère | Cible | `clairiere` |
|---|---|---|
| Emprise | 1,0-4,0 écrans | **2,99** |
| Largeur locale médiane | 1,0-3,0 cases | **2,4** |
| Occupation du décor | 18-45 % | **33,9 %** (eau 4,3 %) |
| Grille 8 px | multiple | **63×57 cellules** |
| Grille 24 px | multiple | **21×19 cases** |
| Entrée sud | ouverte au bord | **profondeur 0** |

## Reproduire / vérifier

```bash
python3 build_clairiere.py          # la carte + les 3 étages + audits + planche
python3 pmdo/audit_echelle.py clairiere   # re-vérifie l'audit et la planche 1:1
python3 pmdo/export_pmdo.py clairiere     # re-sort le pack complet
```

La planche de contrôle : `planche_clairiere.html` (référence, essais, LA carte,
les 3 étages du Bosquet Sacré, audits et collisions).
