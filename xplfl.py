#!/usr/bin/env python
#
# XPLFL random optimization flags exploration
# Copyright (C) 2017 STMicroelectronics
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

import os, sys, re, random, hashlib, optparse, logging, itertools
import subprocess, threading, atexit, time, operator
from logging import debug, info, warning, error


# ############################################################################

class results():

    # run_id to result map {run_id: result}
    results = {}

    # used for locking result map
    lock = threading.Lock()

    # update results table given run command output
    @staticmethod
    def update(run_id, config, status, output):
        res_lines = not status and filter(
            lambda x: x.startswith('XRES'), output.splitlines())
        try: res = int(res_lines[-1].split()[1])
        except: res = -1
        with results.lock:
            debug('XRES %d %s %s' % (res, run_id, config))
            results.results.update({run_id: res})
            print >>sys.stdout, 'XRES %d %s %s' % (res, run_id, config)
            sys.stdout.flush()


# ############################################################################

class runner():

    @staticmethod
    def setup(jobs=1, run_cmd=None, dryrun=False, **kwargs):
        assert jobs
        runner.dryrun = dryrun or not run_cmd
        runner.slots = threading.BoundedSemaphore(value=jobs)
        runner.command = run_cmd or ''
        runner.threads = {}  # {run_id: thread}

    @staticmethod
    def subcall(*args):
        debug('XRUN %s' % (' '.join(args)))
        if runner.dryrun:
            time.sleep(0.2)
            return 0, 'XRES %d' % (random.randint(5, 10))
        p = subprocess.Popen(
            args, close_fds=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = p.communicate()
        return p.returncode, stdout

    @staticmethod
    def finalize():
        runner.wait()

    @staticmethod
    def new_id(config):
        # hashlib.sha1(config).hexdigest()
        return 'RUN-' + str(int(time.time() * 1000000))

    @staticmethod
    def wait(run_ids=None):
        run_ids = run_ids or runner.threads.keys()
        for run_id in run_ids: runner.threads[run_id].join()

    @staticmethod
    def start(config):
        def run_wrapper(config, run_id):
            try:
                status, output = runner.subcall(
                    '/usr/bin/env', 'XFLAGS=' + config, runner.command)
                results.update(run_id, config, status, output)
            finally:
                runner.slots.release()
        runner.slots.acquire()
        run_id = runner.new_id(config)
        run_th = threading.Thread(
            target=run_wrapper, args=(config, run_id))
        runner.threads.update({run_id: run_th})
        run_th.start()
        return run_id


# ############################################################################

class opt_flag_list():

    class opt_flag():

        def __init__(self, frange=None, fchoice=None):
            self.range, self.choice = None, None
            if frange:
                flag, min, max, step = frange
                self.range = (flag, int(min), int(max), int(step or 1))
            elif fchoice:
                self.choice = fchoice
            else: assert 0

        def rand(self):
            if self.range:
                flag, min, max, step = self.range
                val = min + random.randint(0, (max - min) / step) * step
                return '%s%d' % (flag, val)
            elif self.choice:
                return random.choice(self.choice)
            else: assert 0

        def values(self, nb=3):
            # TODO: not optimal when int range smaller than nb
            if self.range:
                def frange(min, max, step):
                    val = float(min)
                    while int(val) <= max:
                        yield int(val)
                        val = val + step
                flag, min, max, step = self.range
                return ['%s%d' % (flag, v) for v in frange(
                        min, max, float(max - min) / (nb - 1))]
            elif self.choice:
                return list(self.choice)
            else: assert 0

        @staticmethod
        def flag_name(s):
            i = s.find('=')
            if i != -1:
                s = s[:i + 1]
            if s.startswith('-fno-'):
                s = s.replace('no-', '', 1)
            if s.startswith('-O'):
                s = '-O'
            return s

        def __repr__(self):
            return opt_flag_list.opt_flag.flag_name(self.rand())

    def __init__(self, filename):
        self.flags = []
        # parse flags file
        for line in open(filename):
            line = line.split('#', 1)[0].strip()
            line = line.split('//', 1)[0].strip()
            if not line: continue
            # range flag
            reobj = re.match('^(.*)\[(.*)\.\.([^,]*)(?:,(.*))?\]', line)
            if reobj:
                self.flags.extend(
                    [opt_flag_list.opt_flag(frange=reobj.groups())])
                continue
            # choice flag
            choices = [w.strip() for w in line.split('|')]
            self.flags.extend([opt_flag_list.opt_flag(fchoice=choices)])

    def find(self, flagstr):
        for flag in self.flags:
            if (opt_flag_list.opt_flag.flag_name(flag.rand()) ==
                opt_flag_list.opt_flag.flag_name(flagstr)): return flag
        return None

    @staticmethod
    def parse_line(cmdline):
        cmdline = cmdline or ''
        cmd = filter(bool, [x.strip() for x in cmdline.strip().split(' ')])
        result, idx, cmdlen = [], 0, len(cmd)
        while idx < cmdlen:
            flag = cmd[idx]
            if flag in ['--param', '-mllvm', '-Xclang'] and idx + 1 < cmdlen:
                flag += ' ' + cmd[idx + 1]
                idx += 1
            result += [flag]
            idx += 1
        return result


# ############################################################################

class cmdline():

    @staticmethod
    def argparser():
        parser = optparse.OptionParser(
            description='Optimization Space Exploration')
        parser.add_option('-d', '--debug', dest='debug',
                          action='store_const', const=10, default=20,
                          help='print debug information (default: False)')
        parser.add_option('-n', '--dryrun', dest='dryrun',
                          action='store_true', default=False,
                          help='only print commands (default: False)')
        parser.add_option('-r', '--run', dest='run_cmd',
                          action='store', type='string', default=None,
                          help='set the run script name (default: None)')
        parser.add_option('-j', '--jobs', dest='jobs',
                          action='store', type='int', default=1,
                          help='number of parallel jobs (default: 1)')

        # generators
        group = optparse.OptionGroup(
            parser, 'Exploration', 'common flags for exploration')
        group.add_option('-f', '--flags', dest='flags_list',
                          action='store', type='string', default=None,
                          help='exploration flags filename')
        group.add_option('-b', '--base-flags', dest='base_flags',
                          action='store', type='string', default=None,
                          help='base flags for exploration')
        parser.add_option_group(group)

        # generators
        group = optparse.OptionGroup(
            parser, 'Generators', 'list of available generators')
        parser.set_defaults(generator=None)

        def optcallback(option, opt, value, parser, args):
            assert not parser.values.generator, 'only one generator'
            genargs = value and value.split(',') or []
            parser.values.generator = args(*genargs)

        for gen in generator.generators:
            name, nargs, help, meta = gen.descr()
            group.add_option(name, nargs=nargs, help=help, action='callback',
                             type=(nargs and 'string' or None), metavar=meta,
                             callback=optcallback, callback_args=(gen,))
        parser.add_option_group(group)

        return parser


class logger():

    @staticmethod
    def setup(debug=10, **kwargs):
        fmtlog = '# %(asctime)-15s %(levelname)s: %(message)s'
        fmtdate = '[%d-%m %H:%M:%S]'
        logging.getLogger().setLevel(0)
        conslog = logging.StreamHandler()
        conslog.setLevel(opts.debug)
        conslog.setFormatter(logging.Formatter(fmtlog, fmtdate))
        logging.getLogger().addHandler(conslog)


# ############################################################################

class generator():

    generators = []

    def __init__(self, func):
        self.func = func
        generator.generators += [self]

    def __call__(self, *args):
        return self.func(*args)

    def descr(self):
        option_name = '--' + self.func.func_name.replace('_', '-')
        option_narg = self.func.func_code.co_argcount
        option_help = self.func.func_doc
        option_args = option_narg and ','.join(
            self.func.func_code.co_varnames[:option_narg]).upper()
        return option_name, option_narg and 1 or 0, option_help, option_args


class exploration():

    flags_list = None
    base_flags = None

    @staticmethod
    def setup(generator=None, flags_list=None, base_flags=None, **kwargs):
        assert generator
        exploration.flags_list = flags_list and opt_flag_list(flags_list)
        exploration.base_flags = base_flags or ''
        exploration.generator = generator

    @staticmethod
    def flags(*flags):
        # add base_flags and clean resulting list (no dups)
        flags = map(
            lambda f: f if isinstance(f, list) else [f], flags)
        flags = ' '.join(
            sum(flags, [exploration.base_flags]))
        # [(flag, (index, flag_str))]
        flags = map(
            lambda (i, x): (exploration.flags_list.find(x) or x, (i, x)),
            enumerate(exploration.flags_list.parse_line(flags)))
        # dict(...) will keep only last occurence of each flag
        flags = ' '.join(
            map(operator.itemgetter(1), sorted(dict(flags).values())))
        return flags

    @generator
    def gen_one_by_one():
        """try all flags one by one"""
        assert exploration.flags_list
        # reference run (no flags)
        ref_id = yield []
        # run each flag values separately
        run_ids = {}
        for flag in exploration.flags_list.flags:
            for flag_val in flag.values(nb=10):
                run_id = yield [flag_val]
                run_ids.update({run_id: flag_val})
        runner.wait(run_ids.keys())
        # display flags partition
        run_res = map(
            lambda k: (results.results[k], k, run_ids[k]), run_ids.keys())
        #    bad flags (slowdown)
        flg = filter(
            lambda (r, i, f): (r > results.results[ref_id]), run_res)
        for (r, i, f) in flg:
            print >>sys.stderr, 'FLAG-BAD  ', i, r, f
        #    error flags
        flg = filter(
            lambda (r, i, f): (r == -1), run_res)
        for (r, i, f) in flg:
            print >>sys.stderr, 'FLAG-ERROR', i, r, f
        #    good flags (speedup)
        flg = filter(
            lambda (r, i, f): (0 < r < results.results[ref_id]), run_res)
        for (r, i, f) in flg:
            print >>sys.stderr, 'FLAG-GOOD ', i, r, f

    @generator
    def gen_all_combinations():
        """all combinations of compiler flags"""
        assert exploration.flags_list
        flags_values = map(
            lambda flag: flag.values(), exploration.flags_list.flags)
        for combination in itertools.product(*flags_values):
            yield list(combination)

    @generator
    def gen_random_uniform(prob='0.5'):
        """random combinations of compiler flags"""
        assert exploration.flags_list
        while True:
            flags = filter(
                lambda f: random.random() < float(prob),
                exploration.flags_list.flags)
            yield map(lambda f: f.rand(), flags)

    @generator
    def gen_random_fixed(seqlen='5'):
        """random combinations of fixed length"""
        assert exploration.flags_list
        while True:
            flags = random.sample(exploration.flags_list.flags, int(seqlen))
            yield map(lambda f: f.rand(), flags)

    @generator
    def gen_tune(base_flags):
        """pruning/fine-tuning of a given configuration"""
        assert exploration.flags_list
        new_flags = str(base_flags)
        for flag_str in exploration.flags_list.parse_line(base_flags):
            flag, flag_runs = exploration.flags_list.find(flag_str), {}
            if not flag: continue
            for flag_value in [''] + flag.values(nb=10):
                run_id = yield new_flags.replace(flag_str, flag_value)
                flag_runs.update({run_id: flag_value})
            runner.wait(flag_runs.keys())
            flag_results = map(lambda k: (
                results.results[k], len(flag_runs[k]), k), flag_runs.keys())
            flag_results = filter(lambda (r, l, k): r > 0, flag_results)
            best_flag_str = flag_runs[sorted(flag_results)[0][2]]
            new_flags = new_flags.replace(flag_str, best_flag_str).strip()
        print >>sys.stderr, 'BEST_FLAGS', new_flags

    @staticmethod
    def loop():
        result = None
        while True:
            try:
                config = exploration.generator.send(result)
            except StopIteration:
                break
            result = runner.start(exploration.flags(config))


# ############################################################################

if __name__ == '__main__':
    (opts, args) = cmdline.argparser().parse_args()
    logger.setup(**vars(opts))
    runner.setup(**vars(opts))
    exploration.setup(**vars(opts))
    exploration.loop()
    runner.finalize()


# ############################################################################

# TODO
# - graphes
# - better gcc/llvm flags extraction
# - results on benchmarks (dhrystone/coremark/specs?)
# - lto/fdo support/examples
# - unit tests :)
# - xplfl flags descr
# - better logger output
# - new generators
# -   one run
# -   random combinations
# -   staged exploration, ...
