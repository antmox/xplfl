#!/usr/bin/env bash

set -e

# ####################################################################

cleanup() {
    local exit=$?
    trap - INT QUIT TERM EXIT
    [ -d "$TSTDIR" ] && /bin/rm -fr $TSTDIR
    trap - EXIT
    exit $exit
}

trap "cleanup" INT QUIT TERM EXIT

# ####################################################################

WORKSPACE=$(dirname $(readlink -f $0))
TSTDIR=$(mktemp -d $WORKSPACE/test.XXXXXX)
cd $TSTDIR

# ####################################################################

cat > br.sh <<EOF
    set -e

    # default flags
    CFLAGS="-O2 -D TIME"

    # uncompress sources
    /bin/sh $WORKSPACE/dhry-c.sh

    # compile with xplfl flags XFLAGS
    gcc \$CFLAGS $XFLAGS -c dhry_1.c -o dhry_1.o
    gcc \$CFLAGS $XFLAGS -c dhry_2.c -o dhry_2.o
    gcc dhry_1.o dhry_2.o -o dhry

    # execute
    echo 1000 | qemu-x86_64 -tcg-plugin icount dhry
EOF

timeout 10 bash ./br.sh > log 2>&1

# get number of executed instructions from log file
NBINSTR=$(cat log | grep "number of executed instructions" | sed 's/.* = //')

# print result for xplfl (XRES result)
echo "XRES $NBINSTR"

