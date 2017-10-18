#!/usr/bin/env python

import sys, os, textwrap, re

# usage: extract_llvm_flags.py llvm_source_dir [old_llvm_flags_file]
#   extracts available flags and parameters for llvm from its source files


# ####################################################################

if len(sys.argv) < 2 or not all(map(os.path.exists, sys.argv[1:])):
    print >>sys.stderr, 'usage: %s llvm_src_dir [old_llvm_flags_list]' % (
        os.path.basename(sys.argv[0]))
    sys.exit(1)

old_flags = {}

if len(sys.argv) > 2:
    for line in open(sys.argv[2]):
        re_obj = re.match('#?\s*-mllvm -([^=]*)=', line)
        if not re_obj:
            continue
        old_flags[re_obj.group(1)] = line

root_dir = sys.argv[1]
for dir_name, subdir_list, file_list in os.walk(root_dir):
    for f in file_list:
        if not f.lower().endswith('.cpp'): continue
        llvm_file = os.path.join(dir_name, f)
        cl_opt = None
        for line in open(llvm_file):
            if '//' in line: line = line[:line.find('//')]
            line = line.strip()
            if not cl_opt:
                if line.startswith('static cl::opt<') or line.startswith('cl::opt<'):
                    cl_opt = line
            else: cl_opt += ' ' + line
            if cl_opt and cl_opt[-1] == ';':
                line = str(cl_opt)
                cl_opt = None

                # flag
                re_obj = re.search('cl::opt<.*>\s*\w*\(\s*"([^"]*)', line)
                if not re_obj: continue
                flag_str = str(re_obj.group(1))
                # file
                flag_file = llvm_file
                # type
                re_obj = re.search('cl::opt<([^,>]*)', line)
                assert re_obj
                flag_type = str(re_obj.group(1))
                # name
                re_obj = re.search('cl::opt<.*>\s*(\w*)\(', line)
                assert re_obj
                flag_name = str(re_obj.group(1))
                # desc
                re_obj = re.search('desc\(([^)]*)\)', line)
                flag_desc = re_obj and str(re_obj.group(1).strip()[1:-1]) or ""
                # init
                re_obj = re.search('init\(([^)]*)\)', line)
                flag_init = re_obj and str(re_obj.group(1).strip()) or ""

                print '#', '-%s' % flag_str, '(%s)' % (flag_file)
                print '#  ', flag_name, '-', flag_desc
                print '#  ', flag_type, '(default: %s)' % flag_init

                if flag_str in old_flags:
                    print '# XXX-KNOWN', old_flags[flag_str],
                elif flag_type == 'bool':
                    print '# XXX-BOOL -mllvm -%s=true|-mllvm -%s=false' % (flag_str, flag_str)
                elif flag_type in ['uint32_t', 'unsigned']:
                    print '# XXX-UINT -mllvm -%s=[%s..%s]' % (flag_str, flag_init, flag_init)
                elif flag_type in ['int', 'signed']:
                    print '# XXX-SINT -mllvm -%s=[%s..%s]' % (flag_str, flag_init, flag_init)
                else:
                    print '# XXX-OTHER -mllvm -%s=%s' % (flag_str, flag_init)
                print
