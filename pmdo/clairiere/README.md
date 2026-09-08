# Clairiere — pack PMDO, au scale demande

L'image source (masters natifs 1120x960) mise au scale PMDO **sans etre
modifiee** : ni repeinte, ni filtree, ni recoloree.

## La mise a l'echelle, exactement

1. master `1120x960` -> rogne au centre au multiple de 48 : `1008x912`
   (on perd 112 px de large et 48 px de haut, symetriquement) ;
2. division par 2 **au plus proche voisin** -> `504x456`
   = **21 x 19 cases de 24 px** = **63 x 57 cellules de 8 px**.

Controle d'exactitude : chaque pixel de sortie est EGAL au pixel du master
situé en (2x+56, 2y+24) — verifie pixel par pixel : True.
Aucune couleur n'est inventee ni modifiee (palette du fond : 110013 couleurs,
celle du master).

## Contenu

| fichier | role |
|---|---|
| `fond.png` | Base + Water f01 + Light f01, l'ordre du tmx |
| `calques/Base.png` | le master scale, intact |
| `calques/Water_f01..08.png` | les 8 frames d'eau, scalées |
| `calques/Light_f01..08.png` | les 8 frames de lumiere (`lumiere_simple`, leur choix final) |
| `calques/lumiere_evolution/`, `calques/lumiere_validee/` | les deux autres jeux, scalés aussi |
| `obstacles.json` / `.txt` | grille 8 px : `.` libre, `#` bloque, `~` eau |
| `collision.png`, `collision.tmx` + `brosse_collision.*` | la collision, editable a la souris dans Tiled |
| `clairiere.tmx` | leur carte 3 imagelayers, sur les fichiers corriges |
| `audit_echelle.png` | sprites etalon 1:1 + viewport 320x240 |
| `ground.json` | descripteur complet + audit chiffre |
| `variant_552x480/` | toile alternative 23x20 cases (ne rogne que 16 px de large) |

## La collision, derivee de leurs calques decomposes

`render_layers/bassin.png` -> eau (`~`) ; `render_layers/arbres.png` ->
bloque (`#`). 2788 cellules libres, 803 bloquees, 248 d'eau.

## Audit d'echelle

| critere | valeur |
|---|---|
| cases 24 px | 21 x 19 |
| cellules 8 px | 63 x 57 |
| occupation du decor | 22.4 % (hors eau) |
| part d'eau | 6.9 % |
| largeur locale mediane | 9.33 cases |
| emprise | 2.99 ecrans de 320x240 |

Les masters restent dans `layers/src/clairiere_master/` ; la variante large
dans `variant_552x480/`.
