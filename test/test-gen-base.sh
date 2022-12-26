# RUN: split-file %s %t ; cd %t; bash -ex test.sh

#--- test.sh

#   -O0 / -O2 / -O3
# *
#   "" / -f1 / -f2

$XPLFL/sources/xplfl.py --flags=flags.txt --gen-one-by-one= --base=-O0 --base=base.txt --dryrun | tee results.txt

[ $(cat results.txt | grep XRES | wc -l) -eq 9 ]

#   -O9 / -O8
# *
#   5

$XPLFL/sources/xplfl.py --flags=flags.txt --gen-random-fixed=1 --base=-O9 --base=-O8 --dryrun --max=5 | tee results.txt

[ $(cat results.txt | grep XRES | wc -l) -eq 10 ]

#--- base.txt

-O2
-O3

#--- flags.txt

-f1|-f2
