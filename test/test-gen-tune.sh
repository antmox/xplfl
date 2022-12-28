# RUN: split-file %s %t ; cd %t; bash -ex test.sh

#--- test.sh

rm -f results.txt

$XPLFL/sources/xplfl.py --flags=flags.txt --run="bash run.sh" --base=front.txt --gen-tune=1 --res=results.txt | tee log1.txt
$XPLFL/sources/xplfl.py --flags=flags.txt --run="bash run.sh" --base=front.txt --gen-tune=0 --res=results.txt | tee log2.txt

[ $(cat log1.txt | grep XRES | wc -l) -eq 32 ]
[ $(cat log1.txt | grep BEST | grep 'FLAGS -Oz -f1=10$' | wc -l) -eq 2 ]
[ $(cat log2.txt | grep XRES | wc -l) -eq 32 ]
[ $(cat log2.txt | grep BEST | grep 'FLAGS -O3$' | wc -l) -eq 2 ]

# 4 + 4 + 4 + 4

#--- front.txt

-Oz -f1=10 -fbad=20 -f3=10
-O3 -f1=30 -fbad=30 -f3=30

#--- flags.txt

-Oz|-O2|-O3
-f1=10|-f1=20|-f1=30
-fbad=10|-fbad=20|-fbad=30
-f3=10|-f3=20|-f3=30

#--- run.sh

# XRES CYCLES SIZE

SZ=100; CY=100

for flag in $XFLAGS; do
    case $flag in
        -Oz) SZ=$(( SZ - 10 )) ; CY=$(( CY + 10 )) ;;
        -O2) SZ=$(( SZ + 20 )) ; CY=$(( CY - 10 )) ;;
        -O3) SZ=$(( SZ + 30 )) ; CY=$(( CY - 20 )) ;;
        -f1=10)  SZ=$(( SZ - 10 )) ;;
        -f1=20)  SZ=$(( SZ + 10 )) ;;
        -f1=30)  SZ=$(( SZ )) ;;
        -fbad=*) SZ=$(( SZ + 10 )) ;;
        *) ;;
    esac
done
echo "XRES $CY $SZ"
