# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Safeguarded Illinois root search with explicit termination failures."""

import math

from .delivery_contracts import DeliveryError


def shrink_bracket(g, lo, g_lo, hi, g_hi, *, width=0.0, relative=0.0, accept=None, max_steps=200):
    """Narrow a sign bracket until hi - lo <= width + relative * abs(hi).

    ``g_lo`` and ``g_hi`` are g(lo) and g(hi) with opposite signs (either may be
    zero). ``accept(x, g_x, lo, hi)`` may end the search early at an evaluated
    point. Returns the final (lo, hi); both equal x when g(x) is exactly zero
    or the caller's accept predicate succeeds. Nonfinite/invalid inputs fail;
    an exhausted budget or unattainable width raises nonconvergent. Function
    continuity and the accuracy of supplied endpoint values remain caller duties.
    """
    if not all(math.isfinite(v) for v in (lo, hi, g_lo, g_hi, width, relative)):
        raise ValueError('root bracket and tolerances must be finite')
    if lo > hi or width < 0 or relative < 0 or type(max_steps) is not int or max_steps < 1:
        raise ValueError('invalid root bracket, tolerance or step budget')
    if g_lo == 0:
        return lo, lo
    if g_hi == 0:
        return hi, hi
    if (g_lo > 0) == (g_hi > 0):
        raise ValueError('root endpoints must have opposite signs')
    side = 0
    widths = [hi - lo]
    low_positive = g_lo > 0
    iteration = 0
    while True:
        allowance = width + relative * abs(hi)
        if not math.isfinite(allowance):
            raise ValueError('root width allowance overflowed')
        if hi - lo <= allowance:
            return lo, hi
        if iteration == max_steps:
            raise DeliveryError('nonconvergent', 'root search exhausted its step budget')
        iteration += 1
        scale = max(abs(g_lo), abs(g_hi))
        fraction = (abs(g_lo) / scale) / (abs(g_lo) / scale + abs(g_hi) / scale)
        x = lo * (1 - fraction) + hi * fraction
        # Guarantee progress: bisect when two steps have not halved the bracket.
        if not lo < x < hi or (len(widths) >= 3 and widths[-1] > widths[-3] / 2):
            x = lo / 2 + hi / 2
        if not lo < x < hi:
            raise DeliveryError('nonconvergent', 'root width is below floating-point resolution')
        g_x = g(x)
        if not math.isfinite(g_x):
            raise DeliveryError('nonconvergent', 'root evaluation is nonfinite')
        if g_x == 0:
            return x, x
        if (g_x > 0) == low_positive:
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
