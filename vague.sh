#!/bin/bash
# Une vague : restaure les terrains, reconstruit, exporte, pousse, allege.
# Usage : ./vague.sh zone1 zone2 ...
set -e
cd /home/user/pmd
export TMPDIR=/home/user/build
mkdir -p /home/user/build

ARGS=""
for z in "$@"; do
  [ -f "layers/src/${z}_terrain.png" ] || ARGS="$ARGS layers/src/${z}_terrain.png"
done
[ -n "$ARGS" ] && ./.git-restore.sh $ARGS >/dev/null 2>&1

python3 build_zones18.py "$@" 2>&1 | tail -n $(($#+2))
python3 pmdo/export_pmdo.py "$@" 2>&1 | tail -n $#
./.git-push.sh "Calques a la structure de Palika : $*" 2>&1 | tail -1

rm -rf aseprite tiled
for z in "$@"; do
  rm -rf "layers/rendu/$z" "pmdo/$z" "layers/src/${z}_terrain.png"
done
rm -rf __pycache__ */__pycache__ /home/user/build
du -sh .
