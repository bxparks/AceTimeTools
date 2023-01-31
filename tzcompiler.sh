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

# Can't use $(realpath $(dirname $0)) because realpath doesn't exist on MacOS
DIRNAME=$(dirname $0)

# Location of the TZDB files
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

tag=''
tzrepo=''
while [[ $# -gt 0 ]]; do
    case $1 in
        --tag) shift; tag=$1 ;;
        --tzrepo) shift; tzrepo=$1 ;;
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

# Copy the tz git repo at the specified tag. If no tag given, copy the current
# state of the repo and label it HEAD. Create a 'trap' to auto-clean up the
# 'tzfiles' temporary directory.
echo "+ $DIRNAME/copytz.sh --tag '$tag' $tzrepo $TZFILES"
$DIRNAME/copytz.sh --tag "$tag" $tzrepo $TZFILES
if [[ "$tag" == '' ]]; then
    tz_version='HEAD'
else
    tz_version=$tag
fi
trap clean_tzfiles EXIT

# Run the tzcompiler.py.
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
