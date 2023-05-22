#!/usr/bin/env bash
#
# Copyright 2018 Brian T. Park
#
# MIT License
#
# Shell script wrapper around tzcompiler.py. The main purpose is to run 'git
# checkout' on the TZ Database repository (located at $PWD/../../tz) to retrieve
# the TZ version specified by the (--tag). It then runs the tzcompiler.py
# script to process the zone files. The location of the TZ Database is passed
# into the tzcompiler.py using the --input_dir flag. The various 'validation_*'
# files are produced in the directory specified by the --output_dir flag.
#
# Usage:
#
#   $ tzcompiler.sh -tzrepo repo [--tag tag] [tzcompiler_py_flags...]

set -eu
shopt -s extglob # needed by copy_tzfiles()

# Can't use $(realpath $(dirname $0)) because realpath doesn't exist on MacOS
DIRNAME=$(dirname $0)

# Location of the TZDB files after copying them from the source git repo.
TZFILES=$PWD/tzfiles

# Output generated code to the current directory
OUTPUT_DIR=$PWD

function usage() {
    echo 'Usage: tzcompiler.sh --tzrepo repo [--tag tag] [python_flags...]'
    exit 1
}

function clean_tzfiles() {
    echo "+ rm -rf $TZFILES"
    rm -fr $TZFILES
}

# Copy the tz git repo at the specified tag. If no tag given, copy the current
# state of the repo and label it HEAD. Create a 'trap' to auto-clean up the
# 'tzfiles' temporary directory.
function copy_tzfiles() {
    local src=$1
    local dst=$2

    # Check for existence of $dst.
    if [[ -e "$dst" ]]; then
        echo "ERROR: Cannot overwrite existing '$dst'"
        exit 1
    fi

    # Copy or clone the repo, depending on the $tag.
    if [[ "$tag" == '' ]]; then
        echo "+ cp -a $src/ $dst/"
        cp -a $src/ $dst/
    else
        # Check out TZDB repo at the $tag, unless --skip_checkout flag is given.
        echo "+ git clone --quiet --branch $tag $src $dst"
        git -c advice.detachedHead=false clone --quiet --branch $tag $src $dst
    fi

    # Remove all files other than the zone info files with Rule and Zone
    # entries. In particular, remove *.c and *.h to prevent EpoxyDuino from
    # trying to compile them recursively in the zonedb/ and zonedbx/
    # directories. See src/acetimetools/extractor/extractor.py for the master
    # list of zone info files. This requires the 'shopt -s extglob' to be set.
    echo "+ rm -rf $dst/{clutter}"
    (cd $dst; rm -rf !(\
africa|\
antarctica|\
asia|\
australasia|\
backward|\
etcetera|\
europe|\
northamerica|\
southamerica|\
))
}

# Run the tzcompiler.py.
function run_tzcompiler() {
    echo "+ $DIRNAME/src/acetimetools/tzcompiler.py" \
        --input_dir $TZFILES \
        --output_dir $OUTPUT_DIR \
        --tz_version $tz_version \
        $@
    $DIRNAME/src/acetimetools/tzcompiler.py \
        --input_dir $TZFILES \
        --output_dir $OUTPUT_DIR \
        --tz_version $tz_version \
        "$@"
}

# Parse command line flags.
tag=''
tzrepo=''
cleanup=1
while [[ $# -gt 0 ]]; do
    case $1 in
        --tag) shift; tag=$1 ;;
        --tzrepo) shift; tzrepo=$1 ;;
        --nocleanup) cleanup=0 ;;
        --help|-h) usage ;;
        -*) break ;;
        *) break ;;
    esac
    shift
done
if [[ "$tzrepo" == '' ]]; then
    echo 'ERROR: Must provide --tzrepo flag'
    exit 1
fi
if [[ "$tag" == '' ]]; then
    tz_version='HEAD'
else
    tz_version=$tag
fi

# Install a trap to delete the tzfile/ temp directory, but disable it if
# --nocleanup given for debugging.
if [[ $cleanup == 1 ]]; then
    trap clean_tzfiles EXIT
fi

# Do the actual work.
copy_tzfiles $tzrepo $TZFILES
run_tzcompiler "$@"
