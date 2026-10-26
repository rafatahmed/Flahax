# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Safeguarded local joint search; numerical candidates are not accepted plans.

Numerical scales, sensitivity criteria, stopping criteria and budgets are supplied
explicitly. No new production tolerance or global optimality certificate is defined.
"""

import math
from collections.abc import Mapping
from .joint_problem import JointProblem, _number, _profile_doses
from .delivery_contracts import DeliveryError
from .engine import nnls


def _constraints(problem, scales):
    sources = (*problem.fertilizers, problem.reagent)
    n = len(sources)
    rows = [([-float(i == j) for j in range(n)], 0.0) for i in range(n)]
    limits = dict(problem.maximum_concentrations)
    limits.update({k: 0.0 for k, t in problem.targets.items() if t == 0})
    rows += [
        (
            [1000 * s.nutrients.get(k, 0) * h for s, h in zip(sources, scales)],
            limit - problem.water.get(k, 0),
        )
        for k, limit in limits.items()
    ]
    rows.append(
        (
            [0.0] * (n - 1) + [scales[-1] * problem.final_volume_litres],
            problem.maximum_reagent_mass_g,
        )
    )
    rows.append(
        (
            [
                s.solvent_fraction * h * problem.final_volume_litres / 1000
                for s, h in zip(sources, scales)
            ],
            problem.solvent_mass_kg,
        )
    )
    density = problem.reagent.density_kg_per_litre
    if density is not None:
        cap = problem.final_volume_litres
        if problem.maximum_reagent_volume_litres is not None:
            cap = min(cap, problem.maximum_reagent_volume_litres)
        rows.append(
            ([0.0] * (n - 1) + [scales[-1] * problem.final_volume_litres / (1000 * density)], cap)
        )
    if not all(math.isfinite(v) for a, b in rows for v in (*a, b)):
        raise DeliveryError('numerical_failure', 'constraint scaling overflow')
    return rows


def _fraction(point, direction, constraints):
    """Largest feasible fraction up to one; step inside rounded upper boundaries."""
    alpha = 1.0
    for row, bound in constraints:
        slope = sum(a * d for a, d in zip(row, direction))
        if slope > 0:
            slack = bound - sum(a * x for a, x in zip(row, point))
            alpha = min(alpha, max(0.0, slack / slope))
    return math.nextafter(alpha, 0.0) if 0 < alpha < 1 else alpha


def solve_joint_problem(
    problem,
    fertilizer_doses,
    reagent_dose,
    *,
    dose_steps,
    charge_scale,
    charge_tolerance,
    loss_tolerance,
    sensitivity_tolerance,
    trust_radius,
    max_iterations,
    max_backtracks,
):
    """Search one immutable JointProblem from an explicitly supplied start.

    dose_steps maps every fertilizer/reagent ID to a positive g/L finite-difference
    scale. trust_radius bounds the infinity norm of steps in those scaled variables.
    Charge controls are mol/kg solvent; loss_tolerance bounds the original summed
    squared relative nutrient errors. sensitivity_tolerance is relative agreement
    of differences at h and h/2. All controls are caller inputs, not scientific defaults.

    Returns numerical_candidate only after fresh final residual/constraint checks;
    accepted is always False pending separate model/phase/acceptance qualification.
    Exhaustion, bad trials, failed sensitivities and stalled local searches return
    search_incomplete, never a global infeasibility or optimality claim.
    """
    if not isinstance(problem, JointProblem):
        raise DeliveryError('invalid_type', 'problem must be a JointProblem')
    sources = (*problem.fertilizers, problem.reagent)
    identifiers = [s.product_id for s in sources]
    if not isinstance(dose_steps, Mapping) or set(dose_steps) != set(identifiers):
        raise DeliveryError('invalid_value', 'dose_steps must name every supplied variable')
    scales = [_number(dose_steps[k], 'dose step', positive=True) for k in identifiers]
    for name, value in [
        ('charge scale', charge_scale),
        ('charge tolerance', charge_tolerance),
        ('sensitivity tolerance', sensitivity_tolerance),
        ('trust radius', trust_radius),
    ]:
        _number(value, name, positive=True)
    _number(loss_tolerance, 'loss tolerance')
    for budget in (max_iterations, max_backtracks):
        if type(budget) is not int or budget < 1:
            raise DeliveryError('invalid_value', 'iteration budgets must be positive integers')
    start = _profile_doses(fertilizer_doses, problem.fertilizers)
    doses = [start.get(k, 0.0) for k in identifiers[:-1]] + [_number(reagent_dose, 'reagent dose')]
    point = [_number(x / h, 'scaled initial dose') for x, h in zip(doses, scales)]
    constraints = _constraints(problem, scales)
    diagnostics = dict(
        evaluations=0,
        rejectedTrials=0,
        sensitivityFailures=0,
        linearFailures=0,
        linearSolves=[],
        iterations=0,
        lastError=None,
    )

    def evaluate(u):
        diagnostics['evaluations'] += 1
        if any(sum(a * x for a, x in zip(row, u)) > bound for row, bound in constraints):
            diagnostics['rejectedTrials'] += 1
            diagnostics['lastError'] = 'linear_constraint'
            return None
        try:
            x = [v * h for v, h in zip(u, scales)]
            state = problem.evaluate(dict(zip(identifiers[:-1], x[:-1])), x[-1])
            if state['status'] == 'missing_chemistry' or state['violations']:
                raise DeliveryError(
                    'unusable_trial', 'missing chemistry or hard constraint violation'
                )
            residual = [
                (r['final'] - r['target']) / r['target']
                for r in state['rows']
                if r['target'] is not None and r['target'] > 0
            ]
            residual.append(state['chargeResidual'] / charge_scale)
            merit = sum(r * r for r in residual)
            if not math.isfinite(merit):
                raise DeliveryError('numerical_failure', 'nonfinite scaled residual')
            return state, residual, merit
        except (DeliveryError, OverflowError) as exc:
            diagnostics['rejectedTrials'] += 1
            diagnostics['lastError'] = getattr(exc, 'code', type(exc).__name__)
            return None

    def meets(value):
        return (
            value is not None
            and value[0]['loss'] <= loss_tolerance
            and abs(value[0]['chargeResidual']) <= charge_tolerance
        )

    def finish(u, value, reason):
        # Fresh evaluation, not a report copied from an endpoint or derivative probe.
        final = evaluate(u) if value is not None else None
        success = meets(final)
        x = [v * h for v, h in zip(u, scales)]
        return dict(
            status='numerical_candidate' if success else 'search_incomplete',
            reason='residual_criteria_met' if success else reason,
            accepted=False,
            fertilizerDoses=dict(zip(identifiers[:-1], x[:-1])),
            reagentDose=x[-1],
            evaluation=None if final is None else final[0],
            diagnostics=diagnostics,
            globalOptimalityProven=False,
        )

    current = evaluate(point)
    if current is None:
        return finish(point, None, 'initial_evaluation_failed')
    radius = trust_radius
    n = len(point)
    for iteration in range(max_iterations):
        diagnostics['iterations'] = iteration
        if meets(current):
            return finish(point, current, 'final_verification_failed')
        candidates = []

        def trial(direction):
            size = max(map(abs, direction))
            if size == 0:
                return
            direction = [d * min(1.0, radius / size) for d in direction]
            alpha = _fraction(point, direction, constraints)
            for _ in range(max_backtracks):
                u = [max(0.0, x + alpha * d) for x, d in zip(point, direction)]
                if u == point:
                    return
                result = evaluate(u)
                if result is not None and (meets(result) or result[2] < current[2]):
                    candidates.append((u, result))
                    return
                alpha /= 2

        columns = []
        for j in range(n):
            direction = [float(i == j) * min(1.0, radius) for i in range(n)]
            alpha = _fraction(point, direction, constraints)
            if alpha == 0:
                direction[j] *= -1
                alpha = _fraction(point, direction, constraints)
            h = direction[j] * alpha
            values = []
            for step in (h, h / 2):
                u = point.copy()
                u[j] += step
                result = evaluate(u) if u[j] != point[j] else None
                values.append(result)
                if result is not None and (meets(result) or result[2] < current[2]):
                    candidates.append((u, result))
            if h == 0 or any(v is None for v in values):
                columns.append([0.0] * len(current[1]))
                diagnostics['sensitivityFailures'] += 1
                continue
            coarse = [(a - b) / h for a, b in zip(values[0][1], current[1])]
            fine = [(a - b) / (h / 2) for a, b in zip(values[1][1], current[1])]
            norm = max([abs(v) for v in coarse + fine])
            if max(abs(a - b) for a, b in zip(coarse, fine)) > sensitivity_tolerance * norm:
                columns.append([0.0] * len(current[1]))
                diagnostics['sensitivityFailures'] += 1
            else:
                columns.append(fine)
        matrix = [list(row) for row in zip(*columns)]
        rhs = [sum(a * x for a, x in zip(row, point)) - r for row, r in zip(matrix, current[1])]
        linear = {}
        try:
            proposal = nnls(matrix, rhs, diagnostics=linear)
            trial([v - x for v, x in zip(proposal, point)])
        except (ValueError, OverflowError) as exc:
            diagnostics['linearFailures'] += 1
            diagnostics['lastError'] = str(exc)
        diagnostics['linearSolves'].append(linear)
        if not candidates:
            # Coordinate and cap-tangent exchanges avoid making rank failure a verdict.
            for j in range(n):
                for sign in (-1, 1):
                    trial([sign * radius if i == j else 0.0 for i in range(n)])
            for row, _ in constraints:
                for j in range(n):
                    for k in range(j):
                        if row[j] > 0 and row[k] > 0:
                            direction = [0.0] * n
                            direction[j], direction[k] = row[k], -row[j]
                            trial(direction)
                            trial([-v for v in direction])
        if candidates:
            point, current = min(candidates, key=lambda pair: (not meets(pair[1]), pair[1][2]))
        else:
            radius /= 2
    return finish(point, current, 'iteration_budget_exhausted')
