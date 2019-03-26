#!/usr/bin/env bash

TMPDIR="/tmp/wyag-unpack"
mkdir -p $TMPDIR
mv ./.git/objects/pack/* $TMPDIR
find $TMPDIR -name "*.pack" -exec bash -c "git unpack-objects < {}" \;
rm -rf $TMPDIR
