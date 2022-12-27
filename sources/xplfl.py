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
import subprocess, threading, atexit, time, operator, shlex
from logging import debug, info, warning, error

assert sys.hexversion >= 0x03070000


# ############################################################################

class results():

    class result:
        def __init__(self, variant, flags, values=None):
            self.variant = variant
            self.flags = flags
            self.values = values

        def value(self, index=-1):
            try: return self.values[index]
            except: return None

        @staticmethod
        def fromstr(str):
            words = str.strip().split(';')
            return results.result(
                words[1], words[0][1:-1], list(map(int, words[2:])))

    @staticmethod
    def compute_frontier(results):
        maybe_on_frontier, mustbe_on_frontier = list(results), set()
        for c1 in results:
            on_frontier = True
            maybe_on_frontier.remove(c1)
            for c2 in itertools.chain(mustbe_on_frontier, maybe_on_frontier):
                if (c2.values == c1.values):
                    pass
                elif all(c2.decreases[x] > c1.decreases[x]
                         for x in range(len(c2.values))):
                    on_frontier = False
                    break
            if on_frontier: mustbe_on_frontier.add(c1)
            c1.on_frontier = on_frontier

    @staticmethod
    def compute_decreases(results):
        # compute speedup / size reduction / ...?
        ref = results[0]
        for result in results:
            result.decreases = []
            for (n, v) in enumerate(result.values): result.decreases.append(
                    100. * (1.0 - (float(v) / float(ref.values[n]))))

    # run_id to result map {run_id: result}
    results = {}

    # used for locking result map
    lock = threading.Lock()

    # update results table given run command output
    @staticmethod
    def update(run_id, config, status, output):
        res_lines = not status and list(
            line for line in output.splitlines() if line.startswith('XRES'))
        try:
            values = list(int(w) for w in res_lines[-1].split()[1:])
            assert values
        except: values = None
        with results.lock:
            # XRES CYCLES SIZE
            res = results.result(run_id, config, values)
            results.results.update({run_id: res})
            # output log
            sys.stdout.write(
                '%s XRES %s %s\n' % (run_id, ' '.join(map(str, values)), config)
                if values else '%s XFAIL %s\n' % (run_id, config))
            sys.stdout.flush()
            # results file
            if values and not sys.stderr.isatty():
                sys.stderr.write('"%s";%s;%s\n' % (
                    config, run_id, ';'.join(map(str, values))))
                sys.stderr.flush()


# ############################################################################

class runner():

    @staticmethod
    def quote_args(args):
        def sh_quote(arg):
            return _quote_pos.sub('\\\\', arg)
        _quote_pos = re.compile('(?=[^-0-9a-zA-Z%+./:=@_])')
        return ' '.join([sh_quote(a) for a in args])

    @staticmethod
    def setup(jobs=1, run_cmd=None, dryrun=False, **kwargs):
        assert jobs
        runner.dryrun = dryrun or not run_cmd
        runner.slots = threading.BoundedSemaphore(value=jobs)
        runner.command = run_cmd or ''
        runner.threads = {}  # {run_id: thread}

    @staticmethod
    def subcall(args):
        debug('XRUN %s' % runner.quote_args(args))
        if runner.dryrun:
            return 0, 'XRES %d' % (random.randint(5, 10))
        p = subprocess.Popen(
            args, close_fds=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = p.communicate()
        return p.returncode, stdout

    @staticmethod
    def finalize():
        runner.wait()

    @staticmethod
    def new_id(config):
        return 'RUN-' + str(int(time.time() * 1000000))

    @staticmethod
    def wait(run_ids=None):
        run_ids = run_ids or list(runner.threads.keys())
        for run_id in run_ids: runner.threads[run_id].join()

    @staticmethod
    def start(config):
        def run_wrapper(config, run_id):
            try:
                status, output = runner.subcall(
                    ['/usr/bin/env', 'XRUNID=' + run_id, 'XFLAGS=' + config]
                    + shlex.split(runner.command))
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

        def str(self):
            if self.range:
                flag, min, max, step = self.range
                stepstr = (",%d" % step) if (step != 1) else ""
                return '%s[%d..%d%s]' % (flag, min, max, stepstr)
            return '|'.join(self.choice)

        @staticmethod
        def flag_name(s):
            # bad idea - not unique
            # should not be used except for debug messages
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

    def __init__(self, filename=None):
        self.flags = []
        if not filename: return
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
            if flag.choice:
                if flagstr in flag.choice: return flag
            elif flag.range:
                # TODO: stop using flag_name here. potential issue if several
                # range flags (with different ranges) share the same name
                if (opt_flag_list.opt_flag.flag_name(flag.rand()) ==
                    opt_flag_list.opt_flag.flag_name(flagstr)): return flag
            else: assert 0
        return None

    @staticmethod
    def parse_line(cmdline):
        cmdline = cmdline or ''
        cmd = list(filter(bool, [
            x.strip() for x in cmdline.strip().split(' ')]))
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

        # exploration
        group = optparse.OptionGroup(
            parser, 'Exploration', 'common flags for exploration')
        group.add_option('-f', '--flags', dest='flags_list',
                          action='store', type='string', default=None,
                          help='exploration flags filename')
        group.add_option('-b', '--base', dest='base_list',
                          action='append', type='string', default=None,
                          help='base flags for exploration')
        group.add_option('-s', '--seed', dest='seed',
                          action='store', type='int', default=None,
                          help='seed for random generator')
        group.add_option('--max', dest='maxiter',
                          action='store', type='int', default=None,
                          help='maximum number of iterations')
        parser.add_option_group(group)

        # generators
        group = optparse.OptionGroup(
            parser, 'Generators', 'list of available generators')
        parser.set_defaults(generator=None)

        def optcallback(option, opt, value, parser, args):
            assert not parser.values.generator, 'only one generator'
            genargs = value.split(',') if not value is None else []
            parser.values.generator = (args, genargs)

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
        option_name = '--' + self.func.__name__.replace('_', '-')
        option_narg = self.func.__code__.co_argcount
        option_help = self.func.__doc__
        option_args = option_narg and ','.join(
            self.func.__code__.co_varnames[:option_narg]).upper()
        return option_name, option_narg and 1 or 0, option_help, option_args


class exploration():

    flags_list = None
    base_flags = None

    @staticmethod
    def setup(generator=None, flags_list=None, base_list=None, seed=None,
              maxiter=None, **kwargs):
        assert generator
        random.seed(seed)
        exploration.flags_list = opt_flag_list(flags_list)
        exploration.base_list = base_list or ['']
        exploration.maxiter = maxiter
        exploration.generator = generator

    @staticmethod
    def flags(*flags):
        # add base_flags and clean resulting list (no dups)
        flags = list(f if isinstance(f, list) else [f] for f in flags)
        flags = ' '.join(
            sum(flags, [exploration.base_flags]))
        # [(flag, (index, flag_str))]
        flags = list(
            (exploration.flags_list.find(ix[1]) or ix[1], ix)
            for ix in enumerate(exploration.flags_list.parse_line(flags)))
        # dict(...) will keep only last occurence of each flag
        flags = ' '.join(
            map(operator.itemgetter(1), sorted(dict(flags).values())))
        return flags

    # ########################################################################

    @generator
    def gen_base():
        """reference runs with only base flags"""
        yield ''

    @generator
    def gen_random_uniform(prob='0.5'):
        """random combinations of compiler flags"""
        assert exploration.flags_list
        while True:
            flags = list(f for f in exploration.flags_list.flags if (
                random.random() < float(prob)))
            yield list(f.rand() for f in flags)

    @generator
    def gen_random_fixed(seqlen='5'):
        """random combinations of fixed length"""
        assert exploration.flags_list
        while True:
            flags = random.sample(exploration.flags_list.flags, int(seqlen))
            yield list(f.rand() for f in flags)

    @generator
    def gen_one_by_one(base_flags):
        """try all flags one by one"""
        assert exploration.flags_list
        base_flags = base_flags.split("/")
        # reference ids { baseflag: ref_id }
        ref_ids = {}
        for base in base_flags:
            run_id = yield [base]
            ref_ids.update({base: run_id})
        # run each flag values separately for each base flags
        run_flr = {} # flag -> [ids]
        for flag in exploration.flags_list.flags:
            for base in base_flags:
                res_base = [ref_ids[base]]
                for flag_val in flag.values(nb=6):
                    run_id = yield [base, flag_val]
                    res_base.append(run_id)
                run_flr.setdefault(flag, []).append(res_base)
        runner.wait(list(ref_ids.values()) + sum(sum(run_flr.values(), []), []))
        # look at results for each flags
        always_same, sometimes_fail, keep = [], [], []
        for flag in exploration.flags_list.flags:
            flag_res = list(list(
                results.results[i].value(-1) for i in l) for l in run_flr[flag])
            if None in sum(flag_res, []):
                sometimes_fail.append(flag)
            elif set(len(set(x)) for x in flag_res) == set([1]):
                always_same.append(flag)
            else: keep.append(flag)
        # print results
        for flag in always_same:
            print('# SAME', flag.str())
        for flag in sometimes_fail:
            print('# FAIL', flag.str())
        for flag in keep:
            print(flag.str())

    @generator
    def gen_all_combinations():
        """all combinations of compiler flags"""
        assert exploration.flags_list
        flags_values = list(
            flag.values() for flag in exploration.flags_list.flags)
        for combination in itertools.product(*flags_values):
            yield list(combination)

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
            runner.wait(list(flag_runs.keys()))
            flag_results = list(
                (results.results[k].value(-1), len(flag_runs[k]), k)
                for k in flag_runs.keys())
            flag_results = list(
                (r, l, k) for (r, l, k) in flag_results if r)
            best_flag_str = flag_runs[sorted(flag_results)[0][2]]
            new_flags = new_flags.replace(flag_str, best_flag_str).strip()
        print('BEST_FLAGS', new_flags, file=sys.stderr)

    @generator
    def gen_frontier(result_file):
        """get list of frontier results"""
        all_results = list(
            results.result.fromstr(line)
            for line in open(result_file).read().splitlines())
        results.compute_decreases(all_results)
        results.compute_frontier(all_results)
        for result in all_results:
            if not result.on_frontier: continue
            print(result.flags)
        return; yield

    # ########################################################################

    @staticmethod
    def loop_base():
        base_list = []
        for base_flags in exploration.base_list:
            if os.path.isfile(base_flags):
                base_list.extend(filter(
                    bool, open(base_flags).read().splitlines()))
            else: base_list.extend(base_flags.split(','))
        for base_flags in base_list:
            exploration.base_flags = base_flags
            yield

    @staticmethod
    def loop():
        for _ in exploration.loop_base():
            result = None
            generator = exploration.generator[0](*exploration.generator[1])
            for n in itertools.count(1):
                try:
                    config = generator.send(result)
                except StopIteration:
                    break
                result = runner.start(exploration.flags(config))
                if n == exploration.maxiter:
                    break


# ############################################################################

if __name__ == '__main__':
    (opts, args) = cmdline.argparser().parse_args(sys.argv[1:] or ["-h"])
    logger.setup(**vars(opts))
    runner.setup(**vars(opts))
    exploration.setup(**vars(opts))
    exploration.loop()
    runner.finalize()


# ############################################################################

# TODO
# - graphes
# - better gcc/llvm flags extraction
# - complete example (dhrystone/coremark/?)
# - lto/fdo support/examples
# - xplfl flags descr format
# - better logger output
# - new generators
# -   one run
# -   random combinations
# -   staged exploration, ...
# - unit tests
