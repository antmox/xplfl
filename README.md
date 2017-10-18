# XPLFL

XPLFL helps to find the best compiler optimization flags for a given objective (like execution time or code-size)

XPLFL is derived from ATOS tools (https://github.com/atos-tools/atos-utils)


## example of simple exploration

    # edit a build-run script
    # - this script must exit with code 0 on success
    # - this script must give $XFLAGS flags to the compiler
    # - this script must print "XRES xxxx" on stdout
    #   (xxxx being the result, like an execution time, a number of executed instructions, a code size, ...)
    # - this script must be callable in parallel (by handling its temporary directory for ex)
    # see example/build-run.sh for example
    
    # first step: try each flag one by one
    
    $ xplfl.py -f flags_gcc_63_small.txt -r ./build-run.sh -b "-O2" -j 8 --gen-one-by-one | tee expl1.log
    
    # eventually filter out bad flags from flags list (crashs, huge slowdowns, ...)
    
    # second step: random exploration
    
    $ xplfl.py -f flags_gcc_63_small.txt -r ./build-run.sh -b "-O2" -j 8 --gen-random-fixed=8 | tee expl2.log
    
    # select one or more of the bests flags combinations
    $ flags=$(cat expl2.log | sort -nr | tail -1 | sed 's/.*RUN-\w* //')
    
    # finally tune this/these combination(s)
    $ xplfl.py -f flags_gcc_63_small.txt -r ./build-run.sh -j 8 --gen-tune="$flags" | tee expl3.log
    
    # exentually, restart from second step with new flags


## flags files format

    # two kind of flags file entries:
    
    # - choices:
    -mllvm -unroll-runtime=true|-mllvm -unroll-runtime=false
    -O0 | -O1 | -O2 | -O3 | -Ofast | -Os
    
    # - ranges:
    -mllvm -inline-threshold=[100..2000]
