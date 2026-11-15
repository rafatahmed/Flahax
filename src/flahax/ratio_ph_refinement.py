"""Bounded adaptive sampling; observed features are not continuous extrema proofs."""

import math

from .delivery_contracts import DeliveryError

LOCAL_PH_RESOLUTION = 1e-5
MAX_ADDITIONAL_POINTS = 256
MAX_ROUNDS = 16


def refine_ph(solve_at, base_grid, phases, si_limit):
    """Refine observed maxima and crossings, reporting unresolved work explicitly."""
    states = {}

    def evaluate(ph):
        state = solve_at(ph)
        for phase in phases:
            si = state.saturation_indices.get(phase)
            if si is None or not math.isfinite(si):
                raise DeliveryError("phase_unavailable", f"Missing finite SI for {phase}")
        states[ph] = state

    for ph in sorted(set(base_grid)):
        evaluate(ph)
    base_count = len(states)
    rounds = 0
    while True:
        grid = sorted(states)
        pending = set()
        neighbours, crossings = {}, {}

        def consider(a, b):
            if b - a > LOCAL_PH_RESOLUTION:
                pending.add((a, b))

        for phase in phases:
            values = [states[p].saturation_indices[phase] for p in grid]
            peak = max(range(len(grid)), key=values.__getitem__)
            neighbours[phase] = []
            for j in (peak - 1, peak):
                if 0 <= j < len(grid) - 1:
                    interval = [grid[j], grid[j + 1]]
                    neighbours[phase].append(interval)
                    consider(*interval)
            # Retain every observed local peak, not just the currently highest one.
            for j in range(1, len(grid) - 1):
                if values[j] >= max(values[j - 1], values[j + 1]) and values[j] > min(
                    values[j - 1], values[j + 1]
                ):
                    consider(grid[j - 1], grid[j])
                    consider(grid[j], grid[j + 1])
            crossings[phase] = []
            for threshold in sorted({0.0, si_limit}):
                for j, (a, b) in enumerate(zip(grid, grid[1:])):
                    left, right = values[j] - threshold, values[j + 1] - threshold
                    if left * right < 0 or ((left == 0) != (right == 0)):
                        crossings[phase].append(dict(threshold=threshold, ph_interval=[a, b]))
                        consider(a, b)
        if not pending or rounds >= MAX_ROUNDS:
            break
        new = sorted({(a + b) / 2 for a, b in pending} - states.keys())
        if len(states) - base_count + len(new) > MAX_ADDITIONAL_POINTS or not new:
            break
        for ph in new:
            evaluate(ph)
        rounds += 1
    return states, dict(
        complete=not pending,
        local_ph_resolution=LOCAL_PH_RESOLUTION,
        added_points=len(states) - base_count,
        base_points=base_count,
        evaluated_points=len(states),
        rounds=rounds,
        max_rounds=MAX_ROUNDS,
        max_additional_points=MAX_ADDITIONAL_POINTS,
        unresolved_intervals=[list(p) for p in sorted(pending)],
        maximum_neighbour_intervals=neighbours,
        crossing_brackets=crossings,
        continuous_extrema_proved=False,
        qualification=(
            "Refines observed peaks and SI threshold crossings only. "
            "Narrow unsampled features may remain; this is not a continuous bound."
        ),
    )
