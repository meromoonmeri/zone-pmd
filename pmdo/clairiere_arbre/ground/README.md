# clairiere_arbre — le ground PMDO complet, aux criteres de Luminous Spring

La zone « Clairiere a l'arbre ancien » (576×504, 24×21 cases de 24,
72×63 cellules de 8, viewport 320×240, eau animee en 8 frames de 165 ms)
montee en **vrai ground PMDO** — le format que charge RogueEssence, tel
que le Luminous Spring de Palika (mod [Halcyon](https://github.com/Palikadude/Halcyon)
pour [PMDO](https://github.com/audinowho/PMDODump/)).

## Les criteres Luminous Spring, point par point

| critere | Luminous Spring | clairiere_arbre |
|---|---|---|
| carte | `Data/Ground/luminous_spring.rsground` (GroundMap 0.7.4.0) | `Data/Ground/clairiere_arbre.rsground` (idem, champ pour champ) |
| tuiles | TexSize 3 (24 px) | **TexSize 1 (8 px)** — les planches de la zone sont coupees en 8 px, comme `illuminant_riverbed` / `Altere_Pond` chez Palika |
| obstacles | `[w×TexSize][h×TexSize]` murs 8 px, `Tags` 0 libre / 1 solide | 72×63, `Tags` 0/1, derives de `collision.png` (2445 solides) |
| animation | `Frames[]` par case, `FrameLength` 10 | eau : **frames 1/2/3/4/5/6/7/8** (4 dessins, maintien 2), `FrameLength` 10 = 165 ms |
| statique | `FrameLength` 60 | base : `FrameLength` 60 |
| planches | `Content/Tile/*.tile` (binaire, tuiles 8×8, index + PNG) | idem — les 6 planches de la zone, reusees telles quelles |
| index | `Content/Tile/index.idx` (TileGuide) | idem — **fusionne avec l'index du mod** (187 planches) |
| sorties | `South_Exit`, collider en px | `South_Exit` sur l'entree sud (x 264-336, y 496) |
| viewport | 320×240 | 320×240 (1,8×2,1 ecrans) |

## Contenu

```
Content/Tile/            les 6 planches .tile + index.idx (fusionne)
Data/Ground/clairiere_arbre.rsground   LA carte que charge le moteur
frames/frame_1..8.png    les 8 frames de la zone (1/2/3/4/5/6/7/8)
frames/viewport.gif      ce que voit le joueur : 320×240 sur le bassin
apercu_ground.png        preuve : la carte re-rendue DEPUIS les fichiers binaires
index_mod_PDM-New-Era.idx  l'index du mod cible, source de la fusion
```

## Installation (drop-in)

Copier `Content/` et `Data/` a la racine du mod (PDM-New-Era) :

```
MODS/PDM-New-Era-Abyss-to-Ascension/
├── Content/Tile/clairiere_arbre_*.tile   <- ajoutes
├── Content/Tile/index.idx                <- REMPLACE (contient deja les 187 planches)
└── Data/Ground/clairiere_arbre.rsground  <- ajoute
```

L'`index.idx` fourni est celui du mod **plus** les 6 planches de la zone :
il remplace l'existant sans rien perdre. Pour un autre mod, fusionner de
la meme facon (le moteur charge les index en fallforth, cle par cle).

## La preuve (verifiee par `python3 ground_pmdo.py`)

1. les 6 planches relues : toutes les entrees sont des PNG 8×8,
   l'encodage d'index `(y<<32)|x` == les deux int32 du moteur ;
2. les 4 dessins d'eau couvrent les memes 292 cases ;
3. l'index round-trip : 187 planches, chaque Loc resolu ;
4. **la carte re-rendue depuis les fichiers binaires == les frames
   livrees, ecart max 0 sur les 8 frames** ;
5. les obstacles == `collision.png` ;
6. le format valide sur les vrais fichiers de Halcyon : leur
   `index.idx` (181 planches) et leurs `.tile` se relisent avec le meme
   code, le schema du `.rsground` est identique a celui de
   `luminous_spring.rsground` (les seules cles absentes sont celles des
   NPC/spawners, vides ici).

## Rejouer

```bash
python3 ground_pmdo.py     # reconstruit tout + re-verifie (TOUT EST EXACT)
```

Les planches `.tile` viennent de `pmdo/clairiere_arbre/tiles/` (construites
par `build_clairiere.py`), la collision de `pmdo/clairiere_arbre/collision.png`,
les frames de `layers/rendu/clairiere_arbre/frames/`.
