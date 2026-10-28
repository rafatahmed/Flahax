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
from fractions import Fraction as F
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


def _charge_constrained_step(
    matrix, rhs, tolerance, budget, lower=None, upper=None, diagnostics=None
):
    """Solve a nonnegative linearized least-squares problem with charge equality.

    A scalar dual search changes the charge-row aim. Its monotone response is
    bracketed before bisection. Failure is only a local-step failure. The returned
    L1 merit weight exceeds the recovered equality multiplier in scaled units.
    """

    def linear_solve(a, b):
        if lower is None:
            return nnls(a, b)
        from .joint_linear import bounded_lstsq

        return bounded_lstsq(a, b, lower, upper, budget * len(lower))

    row = matrix[-1]
    norm = math.hypot(*row)
    if norm == 0:
        if abs(rhs[-1]) <= tolerance:
            return linear_solve(matrix[:-1], rhs[:-1]), 1.0
        raise ValueError('unresolved charge sensitivity')
    normal = [v / norm for v in row]
    target = rhs[-1] / norm
    system = matrix[:-1] + [normal]

    def at(aim):
        proposal = linear_solve(system, rhs[:-1] + [aim])
        return math.fsum(v * x for v, x in zip(normal, proposal)) - target, proposal

    gap, proposal = at(target)
    allowance = tolerance / norm
    aim = target
    if abs(gap) > allowance:
        step = max(1.0, abs(target))
        direction = -1 if gap > 0 else 1
        previous = (target, gap, proposal)
        for _ in range(budget):
            aim = target + direction * step
            value, point = at(aim)
            if value == 0 or (value > 0) != (gap > 0):
                left, right = sorted([previous, (aim, value, point)])
                break
            previous = (aim, value, point)
            step *= 2
        else:
            raise ValueError('linearized charge equality not bracketed')
        # A residual that passes feasibility may still leave a poor multiplier
        # near stationarity. Use the supplied budget and retain the closest point.
        best = min([left, right, (target, gap, proposal)], key=lambda item: abs(item[1]))
        for _ in range(2 * budget):
            aim = (left[0] + right[0]) / 2
            gap, proposal = at(aim)
            if abs(gap) < abs(best[1]):
                best = (aim, gap, proposal)
            if gap == 0:
                break
            if gap > 0:
                right = (aim, gap, proposal)
            else:
                left = (aim, gap, proposal)
        aim, gap, proposal = best
        if abs(gap) > allowance:
            raise ValueError('linearized charge equality unresolved')
    multiplier = 2 * (math.fsum(v * x for v, x in zip(normal, proposal)) - aim) / norm
    if not math.isfinite(multiplier):
        raise ValueError('nonfinite linearized charge multiplier')
    if diagnostics is not None:
        diagnostics['chargeMultiplier'] = multiplier
    return proposal, 1 + abs(multiplier)


def _stationarity(point, value, matrix, constraints, relative_tolerance, active_tolerance):
    """First-order KKT evidence only; not a minimum or global-optimality proof."""
    gradient = [
        2 * math.fsum(row[j] * r for row, r in zip(matrix[:-1], value[1][:-1]))
        for j in range(len(point))
    ]
    charge = matrix[-1]
    columns = [charge, [-v for v in charge]]
    active = []
    for index, (row, bound) in enumerate(constraints):
        norm = math.hypot(*row)
        if norm:
            slack = (bound - math.fsum(a * x for a, x in zip(row, point))) / norm
            if 0 <= slack <= active_tolerance:
                active.append((index, slack))
                columns.append([v / norm for v in row])
    multipliers = nnls([list(row) for row in zip(*columns)], [-v for v in gradient])
    terms = [[v * lam for v in col] for col, lam in zip(columns, multipliers)]
    residual = [g + math.fsum(row[j] for row in terms) for j, g in enumerate(gradient)]
    scale = max(
        [math.ulp(1.0)]
        + [
            2 * math.fsum(abs(row[j] * r) for row, r in zip(matrix[:-1], value[1][:-1]))
            for j in range(len(point))
        ]
        + [abs(v) for v in gradient]
        + [abs(v) for row in terms for v in row]
    )
    relative = max(map(abs, residual), default=0) / scale
    complementarity = max(
        [0.0] + [abs(lam * slack) for lam, (_, slack) in zip(multipliers[2:], active)]
    )
    return dict(
        passed=relative <= relative_tolerance
        and complementarity <= relative_tolerance * max(1.0, value[0]['loss']),
        relativeResidual=relative,
        complementarity=complementarity,
        chargeMultiplier=multipliers[0] - multipliers[1],
        activeMultipliers=[
            dict(constraint=i, multiplier=lam, scaledSlack=slack)
            for lam, (i, slack) in zip(multipliers[2:], active)
        ],
        gradient=gradient,
        chargeGradient=charge,
        qualification='First-order local stationarity only; no minimum or global optimum proven.',
    )


def _implicit_matrix(problem, value, scales, charge_scale):
    from .joint_sensitivity import equilibrium_charge_gradient

    sources = (*problem.fertilizers, problem.reagent)
    matrix = [
        [
            1000 * source.nutrients.get(row['symbol'], 0) * scale / row['target']
            for source, scale in zip(sources, scales)
        ]
        for row in value[0]['rows']
        if row['target'] is not None and row['target'] > 0
    ]
    gradient = equilibrium_charge_gradient(problem, value[0])
    matrix.append([v * h / charge_scale for v, h in zip(gradient, scales)])
    return matrix


def _chemical_widths(problem, value, scales, radius):
    # These are local trust widths, not hard product restrictions. They update
    # with the current analytical inventory and permit growth from zero doses.
    totals = value[0]['equilibrium'].totals
    widths = []
    for source, scale in zip((*problem.fertilizers, problem.reagent), scales):
        capacities = [
            totals[b]
            * problem.solvent_mass_kg
            / (coefficient * problem.final_volume_litres * scale)
            for b, coefficient in source.components.items()
            if coefficient > 0 and totals.get(b, 0) > 0
        ]
        widths.append(min([radius] + capacities))
    return widths


def _polish_direction(
    problem,
    point,
    value,
    matrix,
    scales,
    constraints,
    charge_scale,
    charge_tolerance,
    sensitivity_tolerance,
    radius,
    budget,
    evaluate,
    active_tolerance=0.0,
):
    """Positive-curvature coordinate Newton proposal on the charge manifold."""
    n = len(point)
    gradient = [
        2 * math.fsum(row[j] * r for row, r in zip(matrix[:-1], value[1][:-1])) for j in range(n)
    ]
    pivots = [j for j in range(n) if point[j] > active_tolerance and matrix[-1][j] != 0]
    if not pivots:
        return None
    pivot = n - 1 if n - 1 in pivots else max(pivots, key=lambda j: abs(matrix[-1][j]))
    multiplier = -gradient[pivot] / matrix[-1][pivot]
    reduced = [gradient[j] + multiplier * matrix[-1][j] for j in range(n)]
    eligible = [
        j for j in range(n) if j != pivot and (point[j] > active_tolerance or reduced[j] < 0)
    ]
    if not eligible:
        return None
    j = max(eligible, key=lambda k: abs(reduced[k]))
    width = _chemical_widths(problem, value, scales, radius)[j]
    h = min([1.0, width] + ([point[j]] if point[j] > 0 else [])) * sensitivity_tolerance
    direction = [0.0] * n
    direction[j] = h
    direction[pivot] = -h * matrix[-1][j] / matrix[-1][pivot]
    fraction = _fraction(point, direction, constraints)
    if not fraction:
        direction = [-v for v in direction]
        fraction = _fraction(point, direction, constraints)
    probe = [max(0.0, x + fraction * d) for x, d in zip(point, direction)]
    probe_value = evaluate(probe) if probe != point else None
    if probe_value is None:
        return None
    for _ in range(budget):
        if abs(probe_value[0]['chargeResidual']) <= charge_tolerance:
            break
        correction = [0.0] * n
        correction[pivot] = -probe_value[1][-1] / matrix[-1][pivot]
        fraction = _fraction(probe, correction, constraints)
        next_probe = [max(0.0, x + fraction * d) for x, d in zip(probe, correction)]
        next_value = evaluate(next_probe) if next_probe != probe else None
        if next_value is None or abs(next_value[1][-1]) >= abs(probe_value[1][-1]):
            break
        probe, probe_value = next_probe, next_value
    if abs(probe_value[0]['chargeResidual']) > charge_tolerance or probe[j] == point[j]:
        return None
    probe_matrix = _implicit_matrix(problem, probe_value, scales, charge_scale)
    probe_gradient = [
        2 * math.fsum(row[k] * r for row, r in zip(matrix[:-1], probe_value[1][:-1]))
        for k in range(n)
    ]
    if not probe_matrix[-1][pivot]:
        return None
    probe_reduced = (
        probe_gradient[j] - probe_gradient[pivot] * probe_matrix[-1][j] / probe_matrix[-1][pivot]
    )
    curvature = (probe_reduced - reduced[j]) / (probe[j] - point[j])
    if curvature <= 0 or not math.isfinite(curvature):
        return None
    direction = [0.0] * n
    direction[j] = -reduced[j] / curvature
    direction[pivot] = -direction[j] * matrix[-1][j] / matrix[-1][pivot]
    return direction, multiplier, j


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
    objective_gap_tolerance=None,
    stationarity_tolerance=None,
    active_bound_tolerance=None,
    sensitivity_method='finite_difference',
    curvature_block=False,
):
    """Search one immutable JointProblem from an explicitly supplied start.

    dose_steps maps every fertilizer/reagent ID to a positive g/L finite-difference
    scale. trust_radius bounds the infinity norm of steps in those scaled variables.
    Charge controls are mol/kg solvent; loss_tolerance bounds the original summed
    squared relative nutrient errors. sensitivity_tolerance is relative agreement
    of differences at h and h/2. All controls are caller inputs, not scientific defaults.

    Optional objective_gap_tolerance bounds the certified absolute objective gap,
    not the nutrient loss. Optional stationarity_tolerance (relative KKT residual)
    and active_bound_tolerance (distance in scaled variables) must be supplied
    together. They enable local first-order stationarity, not a minimum proof.
    These modes use linearized charge equality, adaptive derivative probes and
    an L1 merit weight above the equality multiplier outside charge feasibility.
    Feasible comparisons use exact nutrient loss plus the signed charge multiplier
    term to avoid masking progress with charge roundoff. All are opt-in caller policy.

    Returns numerical_candidate only after fresh final residual/constraint checks;
    accepted is always False pending separate model/phase/acceptance qualification.
    Exhaustion, bad trials, failed sensitivities and stalled local searches return
    search_incomplete, never a global infeasibility or optimality claim.
    """
    if not isinstance(curvature_block, bool):
        raise DeliveryError('invalid_value', 'curvature_block must be boolean')
    if curvature_block and sensitivity_method != 'equilibrium':
        raise DeliveryError('invalid_value', 'curvature_block requires equilibrium sensitivities')
    if sensitivity_method not in ('finite_difference', 'equilibrium'):
        raise DeliveryError('invalid_value', 'unknown joint sensitivity method')
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
    if objective_gap_tolerance is not None:
        _number(objective_gap_tolerance, 'objective gap tolerance')
    if (stationarity_tolerance is None) != (active_bound_tolerance is None):
        raise DeliveryError(
            'invalid_value', 'stationarity and active-bound controls must be supplied together'
        )
    if stationarity_tolerance is not None:
        _number(stationarity_tolerance, 'stationarity tolerance', positive=True)
        _number(active_bound_tolerance, 'active bound tolerance')
    for budget in (max_iterations, max_backtracks):
        if type(budget) is not int or budget < 1:
            raise DeliveryError('invalid_value', 'iteration budgets must be positive integers')
    start = _profile_doses(fertilizer_doses, problem.fertilizers)
    doses = [start.get(k, 0.0) for k in identifiers[:-1]] + [_number(reagent_dose, 'reagent dose')]
    point = [_number(x / h, 'scaled initial dose') for x, h in zip(doses, scales)]
    constraints = _constraints(problem, scales)
    exact_model = None
    if objective_gap_tolerance is not None or stationarity_tolerance is not None:
        exact_model = [
            (
                [
                    (j, F(1000) * F(source.nutrients.get(k, 0)) / F(target))
                    for j, source in enumerate(sources)
                    if source.nutrients.get(k, 0)
                ],
                (F(target) - F(problem.water.get(k, 0))) / F(target),
            )
            for k, target in problem.targets.items()
            if target > 0
        ]
    diagnostics = dict(
        evaluations=0,
        rejectedTrials=0,
        sensitivityFailures=0,
        linearFailures=0,
        linearSolves=[],
        iterations=0,
        lastError=None,
        history=[],
        chargeRestorations=0,
        trialChargeCorrections=0,
        finalColdCorrections=0,
        feasibleModelSteps=0,
        sensitivityMethod=sensitivity_method,
        curvatureBlock=curvature_block,
    )

    equilibrium_seed = None

    def evaluate(u, *, cold=False):
        diagnostics['evaluations'] += 1
        if any(sum(a * x for a, x in zip(row, u)) > bound for row, bound in constraints):
            diagnostics['rejectedTrials'] += 1
            diagnostics['lastError'] = 'linear_constraint'
            return None
        try:
            x = [v * h for v, h in zip(u, scales)]
            if sensitivity_method == 'equilibrium':
                state = problem.evaluate(
                    dict(zip(identifiers[:-1], x[:-1])),
                    x[-1],
                    equilibrium_start=None if cold else equilibrium_seed,
                )
            else:
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
            exact = state['loss']
            if exact_model is not None:
                rational_doses = list(map(F, x))
                exact = sum(
                    (sum(a * rational_doses[j] for j, a in row) - target) ** 2
                    for row, target in exact_model
                )
            return state, residual, merit, exact
        except (DeliveryError, OverflowError) as exc:
            diagnostics['rejectedTrials'] += 1
            diagnostics['lastError'] = getattr(exc, 'code', type(exc).__name__)
            return None

    def certificate(u):
        from .joint_optimality import objective_certificate

        x = [v * h for v, h in zip(u, scales)]
        return objective_certificate(problem, dict(zip(identifiers[:-1], x[:-1])), x[-1])

    def bounded(u, value):
        if (
            objective_gap_tolerance is None
            or value is None
            or abs(value[0]['chargeResidual']) > charge_tolerance
        ):
            return None
        from fractions import Fraction

        proof = certificate(u)
        if proof['linearFeasible'] and 0 <= Fraction(proof['exactGap']) <= Fraction(
            objective_gap_tolerance
        ):
            return proof
        return None

    def meets(value):
        return (
            value is not None
            and value[0]['loss'] <= loss_tolerance
            and abs(value[0]['chargeResidual']) <= charge_tolerance
        )

    def finish(u, value, reason, stationary=None):
        # Fresh evaluation, not a report copied from an endpoint or derivative probe.
        final = evaluate(u, cold=True) if value is not None else None
        if (
            sensitivity_method == 'equilibrium'
            and final is not None
            and abs(value[0]['chargeResidual']) <= charge_tolerance
            and abs(final[0]['chargeResidual']) > charge_tolerance
        ):
            # A warm equilibrium seed can hide inner-solve roundoff in charge.
            # Correct on cold states only, then rebuild every final certificate.
            origin = u.copy()
            for _ in range(max_backtracks):
                try:
                    row = _implicit_matrix(problem, final, scales, charge_scale)[-1]
                except (DeliveryError, ValueError, OverflowError) as error:
                    diagnostics['lastError'] = str(error)
                    break
                order = sorted(
                    range(len(u)),
                    key=lambda j: (u[j] > (active_bound_tolerance or 0), abs(row[j])),
                    reverse=True,
                )
                corrected = None
                for j in order:
                    if not row[j]:
                        continue
                    direction = [0.0] * len(u)
                    direction[j] = -final[1][-1] / row[j]
                    alpha = _fraction(u, direction, constraints)
                    for _ in range(max_backtracks):
                        probe = [max(0.0, x + alpha * d) for x, d in zip(u, direction)]
                        if probe == u:
                            break
                        if max(abs(x - y) for x, y in zip(probe, origin)) <= trust_radius:
                            trial_value = evaluate(probe, cold=True)
                            if trial_value is not None and abs(
                                trial_value[0]['chargeResidual']
                            ) < abs(final[0]['chargeResidual']):
                                corrected = probe, trial_value
                                break
                        alpha /= 2
                    if corrected is not None:
                        break
                if corrected is None:
                    break
                u, final = corrected
                value = final
                diagnostics['finalColdCorrections'] += 1
                if abs(final[0]['chargeResidual']) <= charge_tolerance:
                    break
        if stationary is not None and final is not None and sensitivity_method == 'equilibrium':
            try:
                fresh_matrix = _implicit_matrix(problem, final, scales, charge_scale)
                stationary = _stationarity(
                    u,
                    final,
                    fresh_matrix,
                    constraints,
                    stationarity_tolerance,
                    active_bound_tolerance,
                )
                stationary['sensitivityMethod'] = 'equilibrium'
            except (DeliveryError, ValueError, OverflowError) as error:
                diagnostics['lastError'] = str(error)
                stationary = None
        success = meets(final)
        proof = bounded(u, final) if not success else None
        local = (
            stationary is not None
            and stationary['passed']
            and final is not None
            and abs(final[0]['chargeResidual']) <= charge_tolerance
            and final[0]['rows'] == value[0]['rows']
            and (
                sensitivity_method == 'equilibrium'
                or final[0]['chargeResidual'] == value[0]['chargeResidual']
            )
            and certificate(u)['linearFeasible']
        )
        x = [v * h for v, h in zip(u, scales)]
        return dict(
            status='numerical_candidate'
            if success
            else (
                'bounded_best_fit'
                if proof
                else ('stationary_point' if local else 'search_incomplete')
            ),
            reason='residual_criteria_met'
            if success
            else (
                'objective_gap_verified'
                if proof
                else ('first_order_stationarity' if local else reason)
            ),
            stationarity=stationary if local else None,
            objectiveCertificate=proof,
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
        equilibrium_seed = current[0]['equilibrium']
        if meets(current) or bounded(point, current):
            return finish(point, current, 'final_verification_failed')
        diagnostics['unreliableColumns'] = []
        diagnostics['differenceSteps'] = []
        candidates = []
        penalty = None

        def merit(value):
            if penalty is None:
                return value[2]
            # On the already feasible manifold, the signed Lagrangian cancels
            # first-order objective changes caused by charge-rounding corrections.
            # Final charge and stationarity checks retain their original limits.
            if (
                'chargeMultiplier' in linear
                and abs(value[0]['chargeResidual']) <= charge_tolerance
                and abs(current[0]['chargeResidual']) <= charge_tolerance
            ):
                return value[3] + F(linear['chargeMultiplier']) * F(value[1][-1])
            return value[3] + F(penalty) * abs(F(value[1][-1]))

        def trial(direction, correct_charge=False):
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
                # A second-order charge correction avoids rejecting a useful
                # tangent step solely because the equality is nonlinear.
                if correct_charge and result is not None:
                    for _ in range(max_backtracks):
                        if abs(result[0]['chargeResidual']) <= charge_tolerance:
                            break
                        corrections = []
                        for j, derivative in enumerate(matrix[-1]):
                            if derivative:
                                correction = [0.0] * n
                                correction[j] = -result[1][-1] / derivative
                                fraction = _fraction(u, correction, constraints)
                                endpoint = point[j] + math.copysign(radius, correction[j])
                                fraction = min(
                                    fraction, max(0.0, (endpoint - u[j]) / correction[j])
                                )
                                if fraction:
                                    corrections.append(
                                        (j != n - 1, abs(correction[j]), correction, fraction)
                                    )
                        improved = False
                        for _, _, correction, fraction in sorted(corrections):
                            corrected = [max(0.0, x + fraction * d) for x, d in zip(u, correction)]
                            checked = evaluate(corrected)
                            if checked is not None and abs(checked[1][-1]) < abs(result[1][-1]):
                                u, result = corrected, checked
                                diagnostics['trialChargeCorrections'] += 1
                                improved = True
                                break
                        if not improved:
                            break
                improves = result is not None and (meets(result) or merit(result) < merit(current))
                if (
                    not improves
                    and correct_charge
                    and result is not None
                    and 'chargeMultiplier' in linear
                    and abs(current[0]['chargeResidual']) <= charge_tolerance
                    and abs(result[0]['chargeResidual']) <= charge_tolerance
                ):
                    multiplier = F(linear['chargeMultiplier'])
                    predicted = (
                        result[3]
                        - current[3]
                        + multiplier
                        * sum(F(a) * (F(y) - F(x)) for a, x, y in zip(matrix[-1], point, u))
                    )
                    # Explore model descent within the caller's feasible charge
                    # band when residual precision masks the merit improvement.
                    # Both endpoints and the final KKT check retain their limits.
                    allowance = 2 * abs(multiplier) * F(charge_tolerance) / F(charge_scale)
                    improves = predicted < 0 and merit(result) - merit(current) <= allowance
                    if improves:
                        diagnostics['feasibleModelSteps'] += 1
                if improves:
                    candidates.append((u, result))
                    return
                alpha /= 2

        if sensitivity_method == 'equilibrium':
            try:
                matrix = _implicit_matrix(problem, current, scales, charge_scale)
            except (DeliveryError, ValueError, OverflowError) as error:
                diagnostics['lastError'] = str(error)
                diagnostics['sensitivityFailures'] += 1
                # A tiny positive dose may sit in mass-action clipping while its
                # exact nonnegative boundary has a well-defined one-sided limit.
                # This is a re-evaluated candidate, never an unconditional snap.
                recovered = None
                if active_bound_tolerance is not None:
                    for j in sorted(range(n), key=lambda k: point[k]):
                        if not 0 < point[j] <= active_bound_tolerance:
                            continue
                        endpoint = point.copy()
                        endpoint[j] = 0.0
                        checked = evaluate(endpoint, cold=True)
                        if (
                            checked is not None
                            and checked[3] <= current[3]
                            and abs(checked[0]['chargeResidual']) <= charge_tolerance
                            and certificate(endpoint)['linearFeasible']
                        ):
                            try:
                                _implicit_matrix(problem, checked, scales, charge_scale)
                            except (DeliveryError, ValueError, OverflowError):
                                continue
                            recovered = endpoint, checked
                            break
                if recovered is None:
                    return finish(point, current, 'sensitivity_failed')
                point, current = recovered
                diagnostics['history'].append(dict(iteration=iteration, boundaryRecovery=True))
                continue
            reliable = True
            diagnostics['differenceSteps'] = None
        else:
            columns = []
            reliable = True
            for j in range(n):
                direction = [float(i == j) * min(1.0, radius) for i in range(n)]
                alpha = _fraction(point, direction, constraints)
                if alpha == 0:
                    direction[j] *= -1
                    alpha = _fraction(point, direction, constraints)
                h = direction[j] * alpha
                values = []
                agreed = False
                attempts = (
                    max_backtracks
                    if (objective_gap_tolerance is not None or stationarity_tolerance is not None)
                    else 1
                )
                for attempt in range(attempts):
                    values = []
                    for step in (h, h / 2):
                        u = point.copy()
                        u[j] += step
                        result = evaluate(u) if u[j] != point[j] else None
                        values.append(result)
                        if result is not None and (meets(result) or result[2] < current[2]):
                            candidates.append((u, result))
                    if h != 0 and all(v is not None for v in values):
                        coarse = [(a - b) / h for a, b in zip(values[0][1], current[1])]
                        fine = [(a - b) / (h / 2) for a, b in zip(values[1][1], current[1])]
                        norm = max(abs(coarse[-1]), abs(fine[-1]))
                        if abs(coarse[-1] - fine[-1]) <= sensitivity_tolerance * norm:
                            agreed = True
                            break
                    if attempt + 1 < attempts:
                        h /= 2
                diagnostics['differenceSteps'].append(h)
                if not agreed:
                    columns.append([0.0] * len(current[1]))
                    diagnostics['sensitivityFailures'] += 1
                    reliable = False
                    diagnostics['unreliableColumns'].append(identifiers[j])
                else:
                    # Nutrient balances are linear in the declared product doses.
                    # Differentiate those coefficients directly; only charge needs
                    # numerical probes. Subtraction would lose small gradient changes.
                    nutrient_column = [
                        1000
                        * sources[j].nutrients.get(row['symbol'], 0)
                        * scales[j]
                        / row['target']
                        for row in current[0]['rows']
                        if row['target'] is not None and row['target'] > 0
                    ]
                    columns.append(nutrient_column + [2 * fine[-1] - coarse[-1]])
            matrix = [list(row) for row in zip(*columns)]
        rhs = [sum(a * x for a, x in zip(row, point)) - r for row, r in zip(matrix, current[1])]
        linear = {}
        # Restore the nonlinear charge equality before testing stationarity.
        # This changes the actual reagent dose and re-evaluates every residual;
        # it never rescales targets or substitutes a failed undosed recipe.
        if (
            (objective_gap_tolerance is not None or stationarity_tolerance is not None)
            and abs(current[0]['chargeResidual']) > charge_tolerance
            and matrix[-1][-1] != 0
        ):
            direction = [0.0] * n
            direction[-1] = -current[1][-1] / matrix[-1][-1]
            alpha = _fraction(point, direction, constraints)
            restored = False
            for _ in range(max_backtracks):
                u = [max(0.0, x + alpha * d) for x, d in zip(point, direction)]
                if u == point:
                    break
                value = evaluate(u)
                if value is not None and abs(value[0]['chargeResidual']) < abs(
                    current[0]['chargeResidual']
                ):
                    point, current = u, value
                    diagnostics['chargeRestorations'] += 1
                    restored = True
                    break
                alpha /= 2
            if restored:
                diagnostics['history'].append(
                    dict(
                        iteration=iteration,
                        loss=current[0]['loss'],
                        chargeResidual=current[0]['chargeResidual'],
                        meritPenalty=None,
                        restoration=True,
                    )
                )
                continue
        # A bound reagent cannot always restore charge on its own. In the
        # explicit equilibrium path, allow fertilizer coordinates to restore
        # feasibility before asking nutrient merit to select an optimum.
        if (
            sensitivity_method == 'equilibrium'
            and reliable
            and abs(current[0]['chargeResidual']) > charge_tolerance
        ):
            restorations = []
            for j, derivative in enumerate(matrix[-1]):
                if derivative == 0:
                    continue
                direction = [0.0] * n
                direction[j] = max(-radius, min(radius, -current[1][-1] / derivative))
                alpha = _fraction(point, direction, constraints)
                for _ in range(max_backtracks):
                    u = [max(0.0, x + alpha * d) for x, d in zip(point, direction)]
                    if u == point:
                        break
                    value = evaluate(u)
                    if value is not None and abs(value[0]['chargeResidual']) < abs(
                        current[0]['chargeResidual']
                    ):
                        restorations.append((u, value))
                        break
                    alpha /= 2
            if restorations:
                # Prefer low nutrient loss among steps that halve the charge
                # error; otherwise take the largest actual charge reduction.
                sufficient = [
                    pair
                    for pair in restorations
                    if abs(pair[1][0]['chargeResidual'])
                    <= max(charge_tolerance, abs(current[0]['chargeResidual']) / 2)
                ]
                point, current = min(
                    sufficient or restorations,
                    key=lambda pair: (
                        pair[1][0]['loss'] if sufficient else abs(pair[1][0]['chargeResidual'])
                    ),
                )
                diagnostics['chargeRestorations'] += 1
                diagnostics['history'].append(
                    dict(
                        iteration=iteration,
                        loss=current[0]['loss'],
                        chargeResidual=current[0]['chargeResidual'],
                        meritPenalty=None,
                        restoration=True,
                        fertilizerRestoration=True,
                    )
                )
                continue
        if (
            stationarity_tolerance is not None
            and reliable
            and abs(current[0]['chargeResidual']) <= charge_tolerance
        ):
            try:
                stationary = _stationarity(
                    point,
                    current,
                    matrix,
                    constraints,
                    stationarity_tolerance,
                    active_bound_tolerance,
                )
                stationary['sensitivityMethod'] = sensitivity_method
                if sensitivity_method == 'finite_difference':
                    stationary['differenceSteps'] = diagnostics['differenceSteps'].copy()
                diagnostics['stationarity'] = stationary
                if stationary['passed']:
                    return finish(point, current, 'final_verification_failed', stationary)
            except (ValueError, OverflowError) as exc:
                diagnostics['lastError'] = str(exc)
                diagnostics['linearFailures'] += 1
        if (
            sensitivity_method == 'equilibrium'
            and abs(current[0]['chargeResidual']) <= charge_tolerance
        ):
            try:
                polishing = _polish_direction(
                    problem,
                    point,
                    current,
                    matrix,
                    scales,
                    constraints,
                    charge_scale,
                    charge_tolerance,
                    sensitivity_tolerance,
                    radius,
                    max_backtracks,
                    evaluate,
                    active_tolerance=active_bound_tolerance or 0.0,
                )
            except (DeliveryError, ValueError, OverflowError) as error:
                diagnostics['lastError'] = str(error)
                polishing = None
            if polishing is not None:
                direction, multiplier, index = polishing
                linear['chargeMultiplier'] = multiplier
                penalty = 1 + abs(multiplier)
                if curvature_block:
                    from .joint_polishing import block_polish_direction

                    try:
                        block = block_polish_direction(
                            problem,
                            point,
                            current,
                            matrix,
                            scales,
                            constraints,
                            charge_scale,
                            charge_tolerance,
                            sensitivity_tolerance,
                            radius,
                            max_backtracks,
                            evaluate,
                            polishing,
                            active_tolerance=active_bound_tolerance or 0.0,
                        )
                    except (DeliveryError, ValueError, OverflowError, ZeroDivisionError):
                        block = None
                    if block is not None:
                        trial(block[0], correct_charge=True)
                if not candidates:
                    trial(direction, correct_charge=True)
                # Compare curvature polishing with the full coupled proposal.
                # Taking every improving coordinate step immediately can prevent
                # progress along the other, correlated fertilizer directions.
                linear['coordinateNewton'] = identifiers[index]
                # Periodically revisit all coupled directions rather than paying
                # for a full bounded subproblem after each local improvement.
                if candidates and (iteration + 1) % n:
                    point, current = min(candidates, key=lambda pair: merit(pair[1]))
                    diagnostics['history'].append(
                        dict(
                            iteration=iteration,
                            loss=current[0]['loss'],
                            chargeResidual=current[0]['chargeResidual'],
                            coordinateNewton=identifiers[index],
                        )
                    )
                    continue
        try:
            if objective_gap_tolerance is not None or stationarity_tolerance is not None:
                widths = [
                    min(radius, abs(h) / sensitivity_tolerance)
                    if abs(h) < min(1.0, radius)
                    else radius
                    for h in (diagnostics['differenceSteps'] or [])
                ]
                if sensitivity_method == 'equilibrium':
                    widths = _chemical_widths(problem, current, scales, radius)
                proposal, penalty = _charge_constrained_step(
                    matrix,
                    rhs,
                    charge_tolerance / charge_scale,
                    max_backtracks,
                    [max(0.0, v - width) for v, width in zip(point, widths)],
                    [v + width for v, width in zip(point, widths)],
                    diagnostics=linear,
                )
                linear['chargeEquality'] = True
                linear['meritPenalty'] = penalty
                candidates = [
                    (u, v) for u, v in candidates if meets(v) or merit(v) < merit(current)
                ]
            else:
                proposal = nnls(matrix, rhs, diagnostics=linear)
            if penalty is not None:
                probes = candidates
                candidates = []
                trial([v - x for v, x in zip(proposal, point)], correct_charge=True)
                if sensitivity_method == 'equilibrium':
                    candidates.extend(probes)
                elif not candidates:
                    candidates = probes
            else:
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
            point, current = min(candidates, key=lambda pair: (not meets(pair[1]), merit(pair[1])))
        else:
            radius /= 2
        diagnostics['history'].append(
            dict(
                iteration=iteration,
                loss=current[0]['loss'],
                chargeResidual=current[0]['chargeResidual'],
                meritPenalty=penalty,
            )
        )
    return finish(point, current, 'iteration_budget_exhausted')
