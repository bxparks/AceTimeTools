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
#   $ tzcompiler.sh --tag {tag} [--skip_checkout] [tzcompiler_py_flags...]

set -eu

# Can't use $(realpath $(dirname $0)) because realpath doesn't exist on MacOS
DIRNAME=$(dirname $0)

# The master TZ git repository, assumed to be a sibling of AceTime repository.
TZDB_REPO=$(realpath $DIRNAME/../tz)

# Location of the TZDB files
TZDB_FILES=$PWD/tzfiles

# Output generated code to the current directory
OUTPUT_DIR=$PWD

function usage() {
    echo 'Usage: tzcompiler.sh --tag tag [--tzfiles tzfiles] [--skip_checkout]'
    echo '    [--skip_cleanup] [...other python_flags...]'
    exit 1
}

pass_thru_flags=''
tag=''
skip_checkout=0
skip_cleanup=0
tzfiles=$TZDB_FILES
while [[ $# -gt 0 ]]; do
    case $1 in
        --tag) shift; tag=$1 ;;
        --tzfiles) shift; tzfiles=$1 ;;
        --skip_checkout) skip_checkout=1 ;;
        --skip_cleanup) skip_cleanup=1 ;;
        --help|-h) usage ;;
        -*) break ;;
        *) break ;;
    esac
    shift
done
if [[ "$tag" == '' ]]; then
    usage
fi

# Check out the TZDB repo at the specified tag
echo "+ git -c advice.detachedHead=false clone --quiet --branch $tag $TZDB_REPO $tzfiles"
git -c advice.detachedHead=false clone --quiet --branch $tag $TZDB_REPO $tzfiles

# Run the tzcompiler.py.
echo "+ $DIRNAME/src/acetimetools/tzcompiler.py" \
    --input_dir $tzfiles \
    --output_dir $OUTPUT_DIR \
    --tz_version $tag \
    $@
$DIRNAME/src/acetimetools/tzcompiler.py \
    --input_dir $tzfiles \
    --output_dir $OUTPUT_DIR \
    --tz_version $tag \
    "$@"

# Clean up the tzfiles/ directory
if [[ $skip_cleanup == 0 ]]; then
    echo "+ rm -rf $tzfiles"
    rm -rf $tzfiles
fi
