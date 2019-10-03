#!/bin/bash
set -e
source ~/cnd3
# environment created with `conda create -n codescan python=2.7 pip`
# and then `pip install scancode-toolkit`
conda activate codescan
echo $1
OUTFOLDER=`pwd`/licencescans
BASE=$(basename "$1")
mkdir -p $OUTFOLDER
echo $OUTFOLDER
extractcode $1
scancode --json-pp $OUTFOLDER/${BASE}.json --license --copyright $1-extract
trash $1-extract