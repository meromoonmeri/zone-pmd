#!/usr/bin/env bash
# Pousse l'etat courant du workspace vers meromoonmeri/zone-pmd.
#
# Par defaut le mode est ADDITIF : les fichiers presents dans le workspace sont
# ajoutes ou mis a jour, mais rien n'est supprime du depot. C'est indispensable
# ici, le workspace etant volontairement allege (voir ETAT_LOCAL.md) — un push
# en miroir effacerait tous les rendus du depot. Ca s'est produit une fois.
#
# Pour supprimer reellement des fichiers du depot : ./.git-push.sh "msg" --miroir
#
# Le .git n'est pas conserve dans le workspace (95 Mo, plafond de snapshot).
set -euo pipefail
TOK="${GH_TOKEN:?export GH_TOKEN=ghp_...}"
MSG="${1:-maj}"
MODE="${2:-additif}"
W=/home/user/pmd
T=/tmp/zp
EXCL='^ref_etude/|^ref/|^pmdo/ref_sprites/|^pmdo/methode/|__pycache__|\.pyc$|^\.git/'
rm -rf "$T"
git clone --depth 1 -q "https://meromoonmeri:${TOK}@github.com/meromoonmeri/zone-pmd.git" "$T"
if [ "$MODE" = "--miroir" ]; then
  echo "MODE MIROIR : le depot sera aligne sur le workspace, suppressions comprises."
  find "$T" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
fi
cd "$W"
n=0
while read -r f; do
  mkdir -p "$T/$(dirname "$f")"; cp "$f" "$T/$f"; n=$((n+1))
done < <(find . -type f | sed 's|^\./||' | grep -Ev "$EXCL")
echo "$n fichiers synchronises ($MODE)"
cd "$T"
git config user.email "agent@arena.ai"; git config user.name "zone-pmd builder"
git add -A
git commit -q -m "$MSG" || { echo "rien a commiter"; exit 0; }
git push -q origin HEAD:main
git log --oneline -1
