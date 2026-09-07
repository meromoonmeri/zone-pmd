#!/usr/bin/env bash
# Recupere depuis meromoonmeri/zone-pmd des chemins effaces du workspace.
#   ./.git-restore.sh layers/rendu/pic_fleuri_src layers/src
# Sans argument : restaure tout le depot.
set -euo pipefail
TOK="${GH_TOKEN:?export GH_TOKEN=ghp_...}"
W=/home/user/pmd
T=/tmp/zr
rm -rf "$T"
git clone --depth 1 -q "https://meromoonmeri:${TOK}@github.com/meromoonmeri/zone-pmd.git" "$T"
if [ $# -eq 0 ]; then set -- .; fi
for p in "$@"; do
  if [ -e "$T/$p" ]; then
    mkdir -p "$W/$(dirname "$p")"
    cp -r "$T/$p" "$W/$(dirname "$p")/"
    echo "restaure : $p"
  else
    echo "absent du depot : $p" >&2
  fi
done
rm -rf "$T"
