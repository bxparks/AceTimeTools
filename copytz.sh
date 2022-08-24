#!/usr/bin/env bash
#
# Copyright 2020 Brian T. Park
#
# MIT License
#
# Copy the local git repo that tracks the IANA TZ database at
# https://github.com/eggert/tz/ to the destination repo, using a specific tag
# (e.g. 2022b).
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
    echo 'Usage: copytz.sh --tag tag source target'
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
if [[ "$tag" == '' ]]; then
    echo "Missing required --tag flag"
    usage
fi
if [[ $# -ne 2 ]]; then
    echo "Missing source or target"
    usage
fi
src=$1
dst=$2

# Check out TZDB repo at the $tag, unless --skip_checkout flag is given.
echo "==== Cloning TZ files from '$src' to '$dst' at tag '$tag'"
echo "+ git -c advice.detachedHead=false clone --quiet --branch $tag $src $dst"
git -c advice.detachedHead=false clone --quiet --branch $tag $src $dst
