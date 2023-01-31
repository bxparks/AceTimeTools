#!/usr/bin/env bash
#
# Copyright 2020 Brian T. Park
#
# MIT License
#
# Copy the local git repo that tracks the IANA TZ database at
# https://github.com/eggert/tz/ to the destination repo, using a specific tag
# (e.g. 2022b). Then remove all files other than the raw TZDB files.
#
# Usage:
#
#   $ copytz.sh --tag tag source target
#
# Example:
#
#   $ copytz.sh --tag 2022b ~/src/tz ~/tmp/tz

set -eu

function usage() {
    echo 'Usage: copytz.sh [--tag tag] source target'
    exit 1
}

tag=''
src=''
dst=''
while [[ $# -gt 0 ]]; do
    case $1 in
        --tag) shift; tag=$1 ;;
        --help|-h) usage ;;
        -*) echo "Unknown flag '$1'"; usage ;;
        *) break ;;
    esac
    shift
done
if [[ $# -ne 2 ]]; then
    echo "Missing source or target"
    usage
fi
src=$1
dst=$2

# Either the current repo, or perform a shallow clone at the given '$tag'.
if [[ -e "$dst" ]]; then
    echo "ERROR: Cannot overwrite existing '$dst'"
    exit 1
fi
if [[ "$tag" == '' ]]; then
    echo "+ cp -a $src/ $dst/"
    cp -a $src/ $dst/
else
    # Check out TZDB repo at the $tag, unless --skip_checkout flag is given.
    echo "+ git clone --quiet --branch $tag $src $dst"
    git -c advice.detachedHead=false clone --quiet --branch $tag $src $dst
fi

# Remove all files other than the zone info files with Rule and Zone entries.
# In particular, remove *.c and *.h to prevent EpoxyDuino from trying to compile
# them recursively in the zonedb/ and zonedbx/ directories. See
# src/acetimetools/extractor/extractor.py for the master list of zone info
# files.
echo "+ rm -rf $dst/{clutter}"
shopt -s extglob # in case it isn't enabled by default
cd $dst
rm -rf !(\
africa|\
antarctica|\
asia|\
australasia|\
backward|\
etcetera|\
europe|\
northamerica|\
southamerica|\
backzone|\
systemv)
