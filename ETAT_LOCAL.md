# Etat du workspace local

Le workspace est volontairement allege : il ne garde que ce qui sert a **produire**.
Tous les rendus sont sur https://github.com/meromoonmeri/zone-pmd

## Garde en local

| Chemin | Pourquoi |
|---|---|
| `*.py`, `forge/`, `pmdo/*.py` | le code |
| `layers/cut/`, `layers/tags/` | catalogues d'objets detoures + tags (leger, sert a chaque build) |
| `assets/zone_*.png` | images d'ancrage pour la generation des terrains |
| `ref_etude/` | 338 vignettes d'etude — **absentes du depot** (rips Nintendo) |
| `pmdo/methode/`, `pmdo/ref_sprites/` | methode d'echelle + sprites etalon — **absents du depot** (tiers) |
| `preuve_eau_pmd.png/.json`, `planche_*.html` | pieces de controle a montrer |

## Efface en local, present sur le depot

`layers/src/` (planches sources) · `layers/rendu/` (calques, frames, GIF) ·
`aseprite/` · `tiled/` · `pmdo/<zone>/`

## Recuperer

```bash
export GH_TOKEN=ghp_...
./.git-restore.sh layers/src layers/rendu     # ou sans argument pour tout
./.git-push.sh "message"                      # renvoyer l'etat courant
```
