#!/usr/bin/env python3

import sys, re, math, operator, optparse, itertools, signal
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm


# ####################################################################

class repeatalarm():
    # from atos-utils/atoslib/atos_lib.py
    current_timer = None

    @staticmethod
    def _on_timer(signum, frame):
        assert repeatalarm.current_timer is not None
        repeatalarm.current_timer.func()
        repeatalarm.current_timer.start()

    def __init__(self, func, pause=1.0):
        assert repeatalarm.current_timer is None
        repeatalarm.current_timer = self
        self.pause = max(int(pause), 1)
        self.func = func
        signal.alarm(0)
        signal.signal(signal.SIGALRM, repeatalarm._on_timer)

    def start(self):
        assert repeatalarm.current_timer == self
        signal.alarm(self.pause)
        return self

    def stop(self):
        if repeatalarm.current_timer is None:
            return
        assert repeatalarm.current_timer == self
        signal.alarm(0)
        signal.signal(signal.SIGALRM, signal.SIG_DFL)
        repeatalarm.current_timer = None


# ####################################################################


colors = {
    'default-mrk': '#3cb4e6', 'default-edg': '#03234b',
    'frontier': '#e6007e', 'selected': '#e6007e',
    'highlight': ['#ffd200', '#e6007e', '#8c0078', '#49b170', '#ffffff'],
    'reflines': '#070707', 'grid': '#666666', 'title': '#666666', 'face': '#f0f0f0',
}


attrmaps = {
    'selected': {
        'color': colors['selected'],
        'marker': 'o', 'markersize': 20,  'alpha': 0.4 },
    'new-pt': {
        'color': colors['selected'],
        'marker': 'o', 'markersize': 20, 'alpha': 0.4, 'zorder': 1},
    'frontier': {
        'color': colors['frontier'],
        'marker': 'x', 'markersize': 10, 'mew': 2,
        'linestyle': 'dashed', 'linewidth': 2, 'label': '_nolegend_', 'zorder': 1 },
    'scatter-def': {
        'color': colors['default-mrk'], 'edgecolor': colors['default-edg'],
        's': 30, 'linewidth': 1, 'alpha': 1.0, 'label': '_nolegend_', 'zorder': 2 },
    'highlight': {
        'edgecolor': colors['default-edg'], 's': 40, 'alpha': 1.0, 'zorder': 4 },
    'tradeoff-pt': {
        'markersize': 20, 'linewidth': 0, 'label': '_nolegend_', 'alpha': 0.4 },
    'tradeoff-ln': {
        'marker': '', 'linewidth': 2, 'linestyle': 'solid' },
    'reflines': {
        'color': colors['reflines'],
        'lw': 2, 'linestyle': 'dashed', 'alpha': 0.6 },
    'minor-grid': {
        'linestyle': '--', 'linewidth': 0.5, 'alpha': 0.4 },
    'axis-labels': {
        'size': 10, 'weight': 'bold' },
    'title': {
        'size': 11, 'weight': 'bold' },
}


# ####################################################################

def draw_graph(getgraph, opts):
    fg = plt.figure(layout="constrained")
    ax = fg.add_subplot(111)

    global graph_plots, all_points
    graph_plots, all_points = [], []

    def draw_tradeoff_plots(ratio, points, attrs):
        # select tradeoff given ratio
        best = select_tradeoff(points, ratio)
        # graph limits
        xmin = min([p.sizered for p in points])
        xmax = max([p.sizered for p in points])
        ymin = min([p.speedup for p in points])
        ymax = max([p.speedup for p in points])
        # number of points on ratio line
        nbtk = int((ratio >= 1 and 2 or 1 / ratio) * 32)
        # ratio line points coordinates
        xtk = [xmin + i * ((xmax - xmin) / nbtk) for i in range(nbtk + 1)]
        ytk = [best.speedup + (1.0 / ratio) * (best.sizered - x) for x in xtk]
        coords = filter(lambda x_y: x_y[1] >= ymin and x_y[1] <= ymax, zip(xtk, ytk))
        # first plot: selected tradeoff point
        attrs.update(attrmaps['tradeoff-pt'])
        plots = [(([best.sizered], [best.speedup]), dict(attrs))]
        # second plot: ratio line
        attrs.update(attrmaps['tradeoff-ln'])
        crds = list(zip(*coords))
        plots.append(((crds[0], crds[1]), dict(attrs)))
        return plots

    def draw_all():
        global graph_plots, all_points, selected_points  # :(

        # remove old plots
        old_points = [(p.sizered, p.speedup, p.variant) for p in all_points]
        for x in list(graph_plots):
            graph_plots.remove(x)
            x.remove()

        # get graph values
        scatters, plots = getgraph()
        all_points = sum([x[0] for x in scatters + plots], [])

        # draw scatters
        for (points, attrs) in scatters:
            xy = list(zip(*[(p.sizered, p.speedup) for p in points]))
            gr = ax.scatter(*xy, **attrs)
            graph_plots.append(gr)

        # draw line plots (frontiers)
        for (points, attrs) in plots:
            xy = list(zip(*sorted([(p.sizered, p.speedup) for p in points])))
            gr, = ax.plot(xy[0], xy[1], **attrs)
            graph_plots.append(gr)

            # show tradeoffs for each frontier
            for ratio in opts.tradeoffs or []:
                for ((xcrd, ycrd), attrs) in draw_tradeoff_plots(
                        ratio, points, dict(attrs)):
                    graph_plots.append(ax.plot(xcrd, ycrd, **attrs)[0])

        # draw selected points (hidden)
        if all_points:
            # workaround pb with pick_event event ind (4000)
            xy = list(zip(*sorted([(p.sizered, p.speedup) for p in all_points])))
            selected_points, = ax.plot(
                xy[0], xy[1], visible=False, picker=4000, **attrmaps['selected'])
            graph_plots.append(selected_points)

        # highlight new points
        if opts.follow and old_points:
            new_points = list(filter(
                lambda p: (p.sizered, p.speedup, p.variant) not in old_points,
                all_points))
            if new_points:
                xy = list(zip(*[(p.sizered, p.speedup) for p in new_points]))
                new_points, = ax.plot(*xy, **attrmaps['new-pt'])
                graph_plots.append(new_points)

        # redraw legend and figure
        if opts.xlim: plt.xlim([float(l) for l in opts.xlim.split(',')])
        if opts.ylim: plt.ylim([float(l) for l in opts.ylim.split(',')])

        if any(not g._label.startswith('_') for g in graph_plots):
            ax.legend(loc='best')
        fg.canvas.draw()

    # https://stackoverflow.com/a/42014041
    def get_aspect_ratio():
        # total figure size
        figW, figH = ax.get_figure().get_size_inches()
        # axis size on figure
        _, _, w, h = ax.get_position().bounds
        # ratio of display units
        disp_ratio = (figH * h) / (figW * w)
        # ratio of data units
        # negative over negative because of the order of subtraction
        data_ratio = operator.sub(*ax.get_ylim()) / operator.sub(*ax.get_xlim())
        return disp_ratio / data_ratio

    # dynamic annotations
    def on_pick(event):
        def closest(x, y):
            r = get_aspect_ratio()
            dp = sorted([(math.hypot(
                (p.sizered - x) / r, p.speedup - y), p) for p in all_points],
                        key=operator.itemgetter(0))
            distmin, closest = dp[0]
            closests = set(
                map(operator.itemgetter(1), filter(lambda d_p: d_p[0] == distmin, dp)))
            for (n, point) in enumerate(closests):
                # print point on console
                print( '-' * 20, n )
                print( point_str(point) )
            return closest

        def unhighlight():
            selected_points.set_visible(False)
            fg.canvas.draw()

        def highlight(p):
            # highlight point
            selected_points.set_visible(True)
            selected_points.set_data(p.sizered, p.speedup)
            # selected point legend
            main_legend = ax.legend_
            lg = point_str(p, short=True)
            lp = plt.legend([selected_points], [lg], loc='lower left', numpoints=1)
            plt.setp(lp.get_texts(), fontsize='medium')
            lp.get_frame().set_alpha(0.5)
            fg.canvas.draw()
            ax.legend_ = main_legend

        highlight(closest(event.mouseevent.xdata, event.mouseevent.ydata)
                  ) if not event.mouseevent.dblclick else unhighlight()

    # live plotting
    def on_timer(): draw_all()

    # draw graph for the first time
    draw_all()

    # redraw axis, set labels, legend, grid, ...
    def labelfmt(x, pos=0): return '%.2f%%' % (x)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(labelfmt))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(labelfmt))

    if opts.xlim: plt.xlim([float(l) for l in opts.xlim.split(',')])
    if opts.ylim: plt.ylim([float(l) for l in opts.ylim.split(',')])

    # graph title
    title = 'OPTIMIZATION SPACE FOR %s' % (opts.id)
    plt.xlabel('SIZE REDUCTION (HIGHER IS BETTER) → ')
    plt.ylabel('SPEEDUP (HIGHER IS BETTER) → ')

    #
    ax.axhline(0, **attrmaps['reflines'])
    ax.axvline(0, **attrmaps['reflines'])
    ax.tick_params(axis='both', colors=colors['grid'], labelsize=9)
    ax.xaxis.label.set_fontproperties(fm.FontProperties(**attrmaps['axis-labels']))
    ax.yaxis.label.set_fontproperties(fm.FontProperties(**attrmaps['axis-labels']))
    ax.xaxis.label.set_color(colors['grid'])
    ax.yaxis.label.set_color(colors['grid'])
    ax.set_facecolor(colors['face'])
    for spine in ax.spines.values():
        spine.set_color(colors['grid'])
    plt.grid(True, which='major', color=colors['grid'])
    plt.grid(True, which='minor', color=colors['grid'], **attrmaps['minor-grid'])
    plt.minorticks_on()
    plt.title(title, color=colors['title'], **attrmaps['title'])
    if opts.outfile:
        fg.savefig(opts.outfile)
    fg.canvas.mpl_connect('pick_event', on_pick)
    if opts.follow:
        timer = repeatalarm(on_timer, 1.0).start()
    plt.show()
    if opts.follow:
        timer.stop()


# ####################################################################


def point_str(point, short=False):
    flags = point.flags if (len(point.flags) < 28 or not short) else (
        point.flags[:25] + '...')
    res = point.variant + '\n'
    res += 'speedup=%.2f%%\n' % (point.speedup)
    res += 'sizered=%.2f%%\n' % (point.sizered)
    res += 'flags=%s' % (flags)
    return res


class point:
    def __init__(self, time, size, variant, flags=None):
        self.variant = variant
        self.time = time
        self.size = size
        self.flags = flags
        self.speedup = None
        self.sizered = None


def select_tradeoff(frontier, perf_size_ratio=4):
    if not frontier: return None
    # speedups must be already computed
    assert all(map(lambda x: getattr(
                x, 'speedup', None) is not None, frontier))
    # find best tradeoff (ratio * speedup + sizered)
    # this is the higher ordinate value at abscisse 0
    tradeoffs = list(map(lambda x: (
            (perf_size_ratio * x.speedup) + x.sizered, x),
                    frontier))
    # also sort by variant_id (to get a deterministic behavior)
    tradeoffs = sorted(tradeoffs, key=lambda x: (x[0], x[1].variant))
    return tradeoffs[-1][1]


def compute_frontier(results):
    maybe_on_frontier, mustbe_on_frontier = list(results), set()
    for c1 in results:
        on_frontier = True
        maybe_on_frontier.remove(c1)
        for c2 in itertools.chain(mustbe_on_frontier, maybe_on_frontier):
            if (c2.speedup == c1.speedup and c2.sizered == c1.sizered):
                pass
            elif c2.speedup > c1.speedup and c2.sizered > c1.sizered:
                on_frontier = False
                break
        if on_frontier: mustbe_on_frontier.add(c1)
        c1.on_frontier = on_frontier


def getoptcases(resfile, opts):
    results = []
    for line in open(resfile):
        words = line.strip().split(';')
        time = float(words[2])
        size = float(words[3])
        variant = words[1]
        flags = words[0][1:-1]
        results.append(point(time, size, variant, flags))
    if opts.refid:
        refres = list(
            filter(lambda p: p.variant == opts.refid, results))
        assert refres
        ref = refres[0]
    else: # ref by default is the 1st point
        ref = results[0]
    for res in results:
        res.speedup = 100. * ((float(ref.time) / float(res.time)) - 1.0)
        res.sizered = 100. * (1.0 - (float(res.size) / float(ref.size)))
    compute_frontier(results)
    print( 'n=%d' % len(results) )
    return results


def optgraph(opts):
    optcases = getoptcases(opts.resfile, opts)
    scatters, plots = [], []

    # scatters definition
    scatters_def = []
    for (n, high_def) in enumerate(opts.highlight):
        high_reg, high_leg = (
            high_def.split(',') if (',' in high_def) else (high_def, '_nolegend_'))
        attrs = dict(attrmaps['highlight'])
        attrs.update({
            'label': high_leg,
            'color': colors['highlight'][n % len(colors['highlight'])]})
        scatters_def.append((high_reg, attrs))
    scatters_def.append(('.*', attrmaps['scatter-def']))

    # scatters list - partionning points into scatters
    partitions, attrs_values = {}, dict(scatters_def)
    for c in optcases:
        for (opt, val) in scatters_def:
            if not (re.match(opt, c.variant) or re.match(opt, c.flags)): continue
            partitions.setdefault(opt, []).append(c)
            break
    partkeys = [x[0] for x in scatters_def if x[0] in partitions.keys()]
    scatters = list(map(lambda opt: (partitions[opt], attrs_values[opt]), partkeys))

    # frontier line
    plots.append(([c for c in optcases if c.on_frontier], attrmaps['frontier']))

    return scatters, plots



# # ####################################################################


if __name__ == '__main__':

    parser = optparse.OptionParser(
        description='Show optimization space exploration results',
        usage='Usage: %prog [options] results')
    parser.add_option(
        '--tradeoffs', dest='tradeoffs', action='append',
        type=float, help='selected tradeoff given size/perf ratio')
    parser.add_option(
        '--highlight', dest='highlight', action='append', default=[],
        help='highlight points given a regexp')
    #
    parser.add_option(
        '--follow', dest='follow', action='store_true', default=False,
        help='continuously update graph with new results')
    #
    parser.add_option(
        '--refid', dest='refid',
        help='identifier of the reference run')
    #
    parser.add_option(
        '--identifier', dest='id',
        help='identifier of the run')
    parser.add_option(
        '--xlim', dest='xlim',
        help='defines the x axis limits')
    parser.add_option(
        '--ylim', dest='ylim',
        help='defines the y axis limits')
    parser.add_option(
        '--outfile', dest='outfile',
        help='output file name')

    (opts, args) = parser.parse_args()

    opts.resfile = args and args[0]

    draw_graph(lambda: optgraph(opts), opts)
