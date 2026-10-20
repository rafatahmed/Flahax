"""Bracketed root finding shared by the acid-dose and alkalinity searches.

Each search previously bisected a fixed number of times, solving the full
equilibrium model at every step. Illinois false position keeps the same sign
bracket and the same stopping rule but converges superlinearly on these smooth
monotonic functions. A step outside the bracket, or two steps that fail to halve
it, fall back to bisection, so the worst case stays within twice bisection's.
"""


def shrink_bracket(g, lo, g_lo, hi, g_hi, *, width=0., relative=0., accept=None, max_steps=200):
    """Narrow [lo, hi], where g changes sign, until hi - lo <= width + relative * hi.

    ``g_lo`` and ``g_hi`` are g(lo) and g(hi) with opposite signs (either may be
    zero). ``accept(x, g_x, lo, hi)`` may end the search early at an evaluated
    point. Returns the final (lo, hi); both equal x when g(x) is exactly zero.
    """
    if g_lo == 0:
        return lo, lo
    if g_hi == 0:
        return hi, hi
    side = 0
    widths = [hi - lo]
    for _ in range(max_steps):
        if hi - lo <= width + relative * abs(hi):
            break
        x = hi - g_hi * (hi - lo) / (g_hi - g_lo) if g_hi != g_lo else (lo + hi) / 2
        # Guarantee progress: bisect when two steps have not halved the bracket.
        if not lo < x < hi or (len(widths) >= 3 and widths[-1] > widths[-3] / 2):
            x = (lo + hi) / 2
        g_x = g(x)
        if g_x == 0:
            return x, x
        if (g_x > 0) == (g_lo > 0):
            lo, g_lo = x, g_x
            if side == -1:
                g_hi /= 2
            side = -1
        else:
            hi, g_hi = x, g_x
            if side == 1:
                g_lo /= 2
            side = 1
        widths.append(hi - lo)
        if accept is not None and accept(x, g_x, lo, hi):
            return x, x
    return lo, hi
