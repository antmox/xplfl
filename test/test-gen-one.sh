# RUN: split-file %s %t ; cd %t; bash -ex test.sh

#--- test.sh

$XPLFL/sources/xplfl.py --seed=0 --flags=flags.txt --run="bash run.sh" --gen-one-by-one= --res=results.txt | tee log.txt

# "" ; -O1 ; -Oz ; -Os ; -O2 ; -O3 ; -Ofail ; -O1 ; -O0 ; -O0

[ $(cat results.txt | wc -l) -eq 9 ]
[ $(cat log.txt | grep -w XRES | wc -l) -eq 9 ]
[ $(cat log.txt | grep -w XFAIL | wc -l) -eq 1 ]
[ $(cat log.txt | grep -w SAME | wc -l) -eq 1 ]
[ $(cat log.txt | grep -w FAIL | wc -l) -eq 1 ]

#--- flags.txt

-O1|-Oz|-Os|-O2|-O3
-Ofail|-O1
-O0|-O0

#--- run.sh

# XRES CYCLES SIZE

case $XFLAGS in
    ""|-O0) echo "XRES 400 400" ;;
    -O1) echo "XRES 200 200" ;;
    -O2) echo "XRES 100 100" ;;
    -O3) echo "XRES 75 125"  ;;
    -Os) echo "XRES 125 75"  ;;
    -Oz) echo "XRES 150 50"  ;;
    *) exit 1 ;;
esac
