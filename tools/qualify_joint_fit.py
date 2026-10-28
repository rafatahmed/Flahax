# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Independent accounting and multistart evidence for an explicit joint problem.

This is a qualification utility, not a production acceptance policy. Controls are
supplied by the caller. It retains unsuccessful starts and never certifies global
optimality from a local solver status or from agreement between starting points.
"""

from fractions import Fraction
import math

from flahax import solve_joint_problem
from flahax.delivery_contracts import DeliveryError


def independent_accounting(problem, doses, reagent_dose):
    """Exact rational arithmetic on the supplied binary input coefficients.

    The water-only excess is a valid objective lower bound because every source
    coefficient and dose is nonnegative. It omits charge and other constraints,
    so a nonzero gap is not evidence that a better feasible recipe exists.
    """
    sources = (*problem.fertilizers, problem.reagent)
    amounts = [doses.get(s.product_id, 0) for s in problem.fertilizers] + [reagent_dose]
    if any(not math.isfinite(x) or x < 0 for x in amounts):
        raise ValueError('invalid candidate dose')
    f = Fraction
    symbols = set(problem.water) | set(problem.targets) | set(problem.maximum_concentrations)
    for source in sources:
        symbols.update(source.nutrients)
    totals = {
        k: f(problem.water.get(k, 0))
        + sum(f(1000) * f(s.nutrients.get(k, 0)) * f(x) for s, x in zip(sources, amounts))
        for k in symbols
    }
    loss = sum(((totals[k] - f(t)) / f(t)) ** 2 for k, t in problem.targets.items() if t > 0)
    lower = sum(
        (max(f(0), f(problem.water.get(k, 0)) - f(t)) / f(t)) ** 2
        for k, t in problem.targets.items()
        if t > 0
    )
    violations = [k for k, t in problem.targets.items() if t == 0 and totals[k] > 0]
    violations += [k for k, cap in problem.maximum_concentrations.items() if totals[k] > f(cap)]
    return dict(
        concentrations={k: float(v) for k, v in totals.items()},
        exactLoss=str(loss),
        loss=float(loss),
        objectiveLowerBound=float(lower),
        lowerBoundGap=float(loss - lower),
        exactNutrientLimitViolations=sorted(set(violations)),
    )


def relaxed_objective_bound(problem):
    """Exact dual certificate for a nutrient-only nonnegative relaxation.

    Drop charge, phase and upper constraints. NNLS supplies a proposed residual;
    rational arithmetic shifts it into the dual-feasible cone. Only the verified
    dual value is a lower bound; the numerical NNLS objective is never used as one.
    """
    from flahax.engine import nnls

    sources = (*problem.fertilizers, problem.reagent)
    positive = [(k, t) for k, t in problem.targets.items() if t > 0]
    if not positive:
        return dict(lowerBound=0.0, exactLowerBound='0', dualFeasible=True)
    f = Fraction
    a = [[f(1000) * f(s.nutrients.get(k, 0)) / f(t) for s in sources] for k, t in positive]
    b = [(f(t) - f(problem.water.get(k, 0))) / f(t) for k, t in positive]
    x = nnls([[float(v) for v in row] for row in a], [float(v) for v in b])
    residual = [sum(v * f(d) for v, d in zip(row, x)) - target for row, target in zip(a, b)]
    columns = list(zip(*a))
    shift = max(
        [f(0)]
        + [
            -sum(v * r for v, r in zip(col, residual)) / sum(col)
            for col in columns
            if sum(col) > 0
        ]
    )
    dual = [r + shift for r in residual]
    assert all(sum(v * r for v, r in zip(col, dual)) >= 0 for col in columns)
    bound = max(f(0), -2 * sum(v * r for v, r in zip(b, dual)) - sum(r * r for r in dual))
    return dict(lowerBound=float(bound), exactLowerBound=str(bound), dualFeasible=True)


def verify_objective_certificate(problem, doses, reagent_dose, proof):
    """Check a supplied rational dual witness without running an optimizer."""
    try:
        f = Fraction
        products = [*problem.fertilizers, problem.reagent]
        targets = [(k, v) for k, v in problem.targets.items() if v > 0]
        dual = [f(v) for v in proof['dualVector']]
        multipliers = [f(v) for v in proof['upperMultipliers']]
        limits = dict(problem.maximum_concentrations)
        limits.update({k: 0 for k, v in problem.targets.items() if v == 0})
        rows = [
            (
                [1000 * f(p.nutrients.get(k, 0)) for p in products],
                f(cap) - f(problem.water.get(k, 0)),
            )
            for k, cap in limits.items()
        ]
        volume = f(problem.final_volume_litres)
        rows += [
            ([f(0)] * len(problem.fertilizers) + [volume], f(problem.maximum_reagent_mass_g)),
            (
                [f(p.solvent_fraction) * volume / 1000 for p in products],
                f(problem.solvent_mass_kg),
            ),
        ]
        density = problem.reagent.density_kg_per_litre
        if density is not None:
            cap = min(
                problem.final_volume_litres,
                problem.maximum_reagent_volume_litres
                if problem.maximum_reagent_volume_litres is not None
                else problem.final_volume_litres,
            )
            rows.append(
                ([f(0)] * len(problem.fertilizers) + [volume / (1000 * f(density))], f(cap))
            )
        if (
            len(dual) != len(targets)
            or len(multipliers) != len(rows)
            or any(v < 0 for v in multipliers)
        ):
            return False
        for j, product in enumerate(products):
            gradient = 2 * sum(
                r * 1000 * f(product.nutrients.get(k, 0)) / f(t)
                for r, (k, t) in zip(dual, targets)
            )
            gradient += sum(lam * row[j] for lam, (row, _) in zip(multipliers, rows))
            if gradient < 0:
                return False
        bound = (
            -2
            * sum(
                r * (f(t) - f(problem.water.get(k, 0))) / f(t) for r, (k, t) in zip(dual, targets)
            )
            - sum(r * r for r in dual)
            - sum(lam * b for lam, (_, b) in zip(multipliers, rows))
        )
        accounting = independent_accounting(problem, doses, reagent_dose)
        amounts = [f(doses.get(p.product_id, 0)) for p in problem.fertilizers] + [f(reagent_dose)]
        feasible = all(sum(v * x for v, x in zip(row, amounts)) <= b for row, b in rows)
        return (
            feasible
            and bound == f(proof['exactLowerBound'])
            and f(accounting['exactLoss']) - bound == f(proof['exactGap'])
        )
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return False


def verify_stationarity(problem, result, controls):
    """Recheck KKT residuals using exact nutrient gradients and independent charge derivatives.

    This verifies a local first-order claim only. It does not certify a minimum.
    """
    from flahax.joint_solver import _constraints
    from flahax.joint_optimality import objective_certificate

    proof = result.get('stationarity')
    if not proof or controls.get('stationarity_tolerance') is None:
        return False
    sources = (*problem.fertilizers, problem.reagent)
    identifiers = [s.product_id for s in sources]
    scales = [controls['dose_steps'][key] for key in identifiers]
    x = [result['fertilizerDoses'].get(key, 0) for key in identifiers[:-1]] + [
        result['reagentDose']
    ]
    point = [v / h for v, h in zip(x, scales)]
    state = problem.evaluate(result['fertilizerDoses'], result['reagentDose'])
    if state['violations'] or abs(state['chargeResidual']) > controls['charge_tolerance']:
        return False
    if not objective_certificate(problem, result['fertilizerDoses'], result['reagentDose'])[
        'linearFeasible'
    ]:
        return False
    targets = [(k, t) for k, t in problem.targets.items() if t > 0]
    f = Fraction
    residual = [
        (
            f(problem.water.get(k, 0))
            + sum(1000 * f(s.nutrients.get(k, 0)) * f(d) for s, d in zip(sources, x))
            - f(t)
        )
        / f(t)
        for k, t in targets
    ]
    gradient = [
        float(
            2
            * f(h)
            * sum(
                r * 1000 * f(s.nutrients.get(k, 0)) / f(t) for r, (k, t) in zip(residual, targets)
            )
        )
        for s, h in zip(sources, scales)
    ]
    method = controls.get('sensitivity_method', 'finite_difference')
    if proof.get('sensitivityMethod', 'finite_difference') != method:
        return False
    if method == 'equilibrium':
        from tools.verify_joint_sensitivity import independent_charge_gradient

        try:
            independent = independent_charge_gradient(
                problem, state, controls['sensitivity_tolerance']
            )
        except (ValueError, DeliveryError, OverflowError):
            return False
        charge = [v * h / controls['charge_scale'] for v, h in zip(independent, scales)]
    else:
        charge = []
        for j, h in enumerate(scales):
            normalized_step = proof['differenceSteps'][j]
            samples = []
            for sign in (1, -1):
                samples = []
                for factor in (0.25, 0.125):
                    doses = x.copy()
                    doses[j] += sign * h * normalized_step * factor
                    if doses[j] < 0:
                        break
                    value = problem.evaluate(dict(zip(identifiers[:-1], doses[:-1])), doses[-1])
                    if value['violations'] or value['chargeResidual'] is None:
                        break
                    samples.append(
                        (value['chargeResidual'] - state['chargeResidual'])
                        / (sign * factor * normalized_step * controls['charge_scale'])
                    )
                if len(samples) == 2:
                    break
            if len(samples) != 2:
                return False
            coarse, fine = samples
            if abs(coarse - fine) > controls['sensitivity_tolerance'] * max(
                abs(coarse), abs(fine)
            ):
                return False
            charge.append(2 * fine - coarse)
    terms = [[proof['chargeMultiplier'] * v for v in charge]]
    constraints = _constraints(problem, scales)
    complementarity = 0
    for entry in proof['activeMultipliers']:
        row, bound = constraints[entry['constraint']]
        norm = math.hypot(*row)
        slack = (bound - math.fsum(v * d for v, d in zip(row, point))) / norm
        lam = entry['multiplier']
        if lam < 0 or not 0 <= slack <= controls['active_bound_tolerance']:
            return False
        terms.append([lam * v / norm for v in row])
        complementarity = max(complementarity, lam * slack)
    scale = max(
        [math.ulp(1.0)]
        + [
            float(
                2
                * f(h)
                * sum(
                    abs(r * 1000 * f(source.nutrients.get(k, 0)) / f(t))
                    for r, (k, t) in zip(residual, targets)
                )
            )
            for source, h in zip(sources, scales)
        ]
        + [abs(v) for v in gradient]
        + [abs(v) for row in terms for v in row]
    )
    error = (
        max(abs(g + math.fsum(row[j] for row in terms)) for j, g in enumerate(gradient)) / scale
    )
    return error <= controls['stationarity_tolerance'] and complementarity <= controls[
        'stationarity_tolerance'
    ] * max(1.0, state['loss'])


def qualify_starts(problem, starts, controls):
    """Record every start, independent residuals and a conservative completion gate.

    A numerical candidate is not accepted for production. The gate checks every
    supplied start; it cannot hide a failed start by selecting the best one.
    """
    if not starts:
        raise ValueError('at least one explicit start is required')
    records = []
    for doses, reagent in starts:
        try:
            result = solve_joint_problem(problem, doses, reagent, **controls)
            independent = independent_accounting(
                problem, result['fertilizerDoses'], result['reagentDose']
            )
            state = result['evaluation']
            gap_ok = (
                result['status'] == 'bounded_best_fit'
                and controls.get('objective_gap_tolerance') is not None
                and verify_objective_certificate(
                    problem,
                    result['fertilizerDoses'],
                    result['reagentDose'],
                    result.get('objectiveCertificate', {}),
                )
                and 0
                <= Fraction(result['objectiveCertificate']['exactGap'])
                <= Fraction(controls['objective_gap_tolerance'])
            )
            stationary_ok = result['status'] == 'stationary_point' and verify_stationarity(
                problem, result, controls
            )
            numerical = (
                (result['status'] == 'numerical_candidate' or gap_ok or stationary_ok)
                and state is not None
                and not independent['exactNutrientLimitViolations']
                and (independent['loss'] <= controls['loss_tolerance'] or gap_ok or stationary_ok)
                and abs(state['chargeResidual']) <= controls['charge_tolerance']
                and not state['violations']
            )
            records.append(
                dict(
                    status='verified_numerical_candidate' if numerical else 'unqualified',
                    solverStatus=result['status'],
                    objectiveCertificate=result.get('objectiveCertificate'),
                    stationarity=result.get('stationarity'),
                    independentStationarityVerified=stationary_ok,
                    reason=result['reason'],
                    fertilizerDoses=result['fertilizerDoses'],
                    reagentDose=result['reagentDose'],
                    independent=independent,
                    chargeResidual=None if state is None else state['chargeResidual'],
                    diagnostics=result['diagnostics'],
                )
            )
        except (DeliveryError, ValueError, OverflowError) as error:
            records.append(
                dict(
                    status='unqualified',
                    error=str(error),
                    errorCode=getattr(error, 'code', type(error).__name__),
                )
            )
    verified = all(r['status'] == 'verified_numerical_candidate' for r in records)
    return dict(
        status='numerical_checks_passed' if verified else 'qualification_incomplete',
        starts=records,
        accepted=False,
        globalOptimalityProven=False,
        remaining='Model/phase applicability, reference agreement and production acceptance.',
    )
