#!/usr/bin/env bash

set -e

# usage: extract_gcc_flags.sh
#   extracts available optimization flags and parameters for the
#   gcc compiler found in $PATH

# ####################################################################
#
#  optimization flags
#

while read -r line; do

    flag=$(echo $line | cut -d' ' -f1 | grep "^-f") || true
    desc=$(echo $line | sed 's/[^\ ]*\ *//')

    [ -z $flag ] && continue

    echo "# $flag"
    echo -n "#  "
    echo $desc | fold -w 70 -s | sed ':a;N;$!ba;s/\n/\n#  /g'

    if [ $(echo $desc | grep -e "\[.*|.*\]"  | wc -l) -ne 0 ]; then
        # -flag=[A|B|C] ?
        choices=$(echo "$desc" | sed 's/.*\[\(.*\)\].*/\1/')
        echo $flag$(echo $choices | sed "s/|/|$flag/g")

    elif [ $(echo $flag | grep "=" | wc -l) -eq 0 ]; then
        # -flag|-fno-lag ?
        echo "$flag|"$(echo $flag | sed "s/-f/-fno-/")

    else
        # -flag=?
        echo "# XXX $flag"

    fi

    echo
done < <(gcc --help=optimizers)


# ####################################################################
#
#  parameters
#

while read -r line; do

    param=$(echo $line | cut -d' ' -f1)
    desc=$(echo $line | sed 's/[^\ ]*\ *//')

    [ -z $param ] && continue

    echo "# $param"
    echo -n "#  "
    echo $desc | fold -w 70 -s | sed ':a;N;$!ba;s/\n/\n#  /g'

    defl=$(gcc -Q --help=params | grep " $param ") || true
    vmin=$(echo $defl | awk '{ print $5 }' | grep "^[0-9]*$") || true
    vmax=$(echo $defl | awk '{ print $7 }' | grep "^[0-9]*$") || true
    vdef=$(echo $defl | awk '{ print $3 }' | grep "^[0-9]*$") || true
    echo "#  $defl"

    if [ "$vmin" != "" -a "$vmax" != "" -a "$vmax" != "0" -a "$vmin" != "$vmax" ]; then
        echo "--param $param=[$vmin..$vmax]"

    elif [ "$vmin" != "" -a "$vdef" != "" -a "$vdef" != "0" ]; then
        echo "--param $param=[$(expr $vdef / 4 + $vmin)..$(expr $vdef \* 4 + $vmin)]"

    else
        echo "# XXX --param $param"

    fi

    echo
done < <(gcc --help=params)
