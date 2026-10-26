# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""One dependency-free mass-action solver for the pinned 25 C reaction set.

Every analytical component and ligand is solved simultaneously in log activity
space. Phase amounts are additional unknowns; an active-set method enforces
nonnegative solid amounts and nonpositive SI for every allowed absent phase.
Redox valences are separate conserved inputs, as in PHREEQC SOLUTION speciation.
"""

from dataclasses import dataclass, field
from functools import lru_cache
from importlib.resources import files
import json
import math
from .delivery_contracts import DeliveryError
from .root_finding import shrink_bracket

LN10 = math.log(10.0)
# Continued-fraction sweeps before Newton when the cold start does not converge (#52).
PRESOLVE_SWEEPS = 200


@lru_cache(maxsize=1)
def chemistry():
    """The packaged 25 °C thermodynamic data (``data/chemistry_25c.json``), loaded once."""
    return json.loads(files('flahax').joinpath('data/chemistry_25c.json').read_text())


@dataclass(frozen=True)
class AqueousResult:
    """A solved solution: totals, pH, ionic strength, species, activities, saturation indices,
    precipitated phases, residuals and charge balance.

    model_limitations identifies omitted positive ligand/metal competition and
    selected profile assumptions. model_domain states the numerical/chemical
    conventions; a converged result does not establish physical applicability.
    """

    totals: dict
    ph: float
    ionic_strength: float
    species: dict
    activities: dict
    saturation_indices: dict
    precipitated: dict
    residuals: dict
    iterations: int
    charge_balance: float
    water_activity: float
    model_limitations: tuple = ()
    model_domain: dict = field(default_factory=dict)
    numerical_diagnostics: dict = field(default_factory=dict)


def model_qualification(totals):
    """Scope of the pinned equations, not a claim of experimentally verified accuracy.

    Positive ligand/metal pairs without a complex in the selected reaction set
    are explicit limitations. A zero input does not activate competition. The
    list concerns these selected chelators and metals, not every possible omitted
    reaction. Numerical convergence cannot remove a model-coverage limitation.
    """
    data = chemistry()
    limitations = []
    for ligand in ('Edta-4', 'Citrate-3', 'Dtp-5', 'Edd-4'):
        if totals.get(ligand, 0) <= 0:
            continue
        for metal in ('Ca+2', 'Mg+2', 'Fe+2', 'Fe+3', 'Mn+2', 'Zn+2', 'Cu+2'):
            if totals.get(metal, 0) > 0 and not any(
                r['powers'].get(ligand, 0) > 0 and r['powers'].get(metal, 0) > 0
                for r in data['aqueous']
            ):
                limitations.append(
                    dict(
                        code='omitted_competition',
                        components=(ligand, metal),
                        reason='No complex for this positive ligand/metal pair exists in the '
                        'selected reaction set; calculated partitioning is conditional '
                        'on its omission.',
                    )
                )
    if any(totals.get(ligand, 0) > 0 for ligand in ('Dtp-5', 'Edd-4')):
        limitations.append(
            dict(
                code='selected_chelate_profile',
                components=tuple(k for k in ('Dtp-5', 'Edd-4') if totals.get(k, 0) > 0),
                reason='Selected project-profile constants; electrolyte/isomer and '
                'concentration-to-activity transfer are not independently requalified.',
            )
        )
    domain = dict(
        temperature_c=data['temperature_c'],
        ionic_strength_max_mol_per_kg_water=0.1,
        numerical_ph_interval=(0, 14),
        concentration_basis='mol/kg water',
        standard_state='dimensionless molal activities; unit activity of pure solids',
        activity_model='Davies charged species; neutral log10(gamma)=0.1 I',
        water_activity='max(0.9, 1 - sum(aqueous molalities)/55.5084)',
        valence_policy='fixed analytical oxidation states; no electron/redox equilibration',
        carbon_boundary='closed analytical carbon; no imposed gas reservoir',
        database_sha256=data['database_sha256'],
        qualification='equations of the selected model only; numerical bounds are not '
        'experimental applicability or a physical-validation claim',
    )
    return tuple(limitations), domain


def linear(a, b):
    """Row-equilibrated elimination; zero pivots fail without an absolute floor.

    Row scaling preserves the system while avoiding a unit-dependent singularity
    decision. A small backward residual is checked separately by the nonlinear
    iteration; this solve alone does not certify forward accuracy or conditioning.
    """
    rows = []
    for row, value in zip(a, b):
        scale = max(map(abs, row), default=0.0)
        if scale == 0 or not math.isfinite(scale):
            raise DeliveryError('nonconvergent', 'singular or nonfinite equilibrium Jacobian')
        rows.append([v / scale for v in row] + [value / scale])
    a = rows
    n = len(b)
    for k in range(n):
        p = max(range(k, n), key=lambda i: abs(a[i][k]))
        a[k], a[p] = a[p], a[k]
        if a[k][k] == 0:
            raise DeliveryError('nonconvergent', 'singular equilibrium Jacobian')
        for i in range(k + 1, n):
            f = a[i][k] / a[k][k]
            for j in range(k + 1, n + 1):
                a[i][j] -= f * a[k][j]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (a[i][n] - sum(a[i][j] * x[j] for j in range(i + 1, n))) / a[i][i]
    if not all(map(math.isfinite, x)):
        raise DeliveryError('nonconvergent', 'nonfinite equilibrium linear solution')
    return x


def _damped_step(evaluate, x, residual, matrix):
    """Levenberg-Marquardt step that lowers the squared residual, or None."""
    m = len(residual)
    normal = [
        [sum(matrix[r][i] * matrix[r][j] for r in range(m)) for j in range(m)] for i in range(m)
    ]
    gradient = [sum(matrix[r][i] * residual[r] for r in range(m)) for i in range(m)]
    scale = [max(normal[i][i], 1e-300) for i in range(m)]
    merit = sum(v * v for v in residual)
    damping = 1e-3
    for _ in range(40):
        system = [
            [normal[i][j] + (damping * scale[i] if i == j else 0.0) for j in range(m)]
            for i in range(m)
        ]
        try:
            step = linear(system, [-g for g in gradient])
        except DeliveryError:
            step = None
        if step is not None:
            trial = [v + d for v, d in zip(x, step)]
            got = evaluate(trial)
            if got and sum(v * v for v in got[0]) < merit:
                return trial
        damping *= 10
    return None


def _continued_fraction(
    logs, totals, bases, records, sparse, ph, strength, sweeps=PRESOLVE_SWEEPS
):
    """Mass-balance pre-iteration (Wigley 1977 continued fraction): rescale each free
    activity by total/sum, damped by its largest stoichiometric coefficient."""
    root = math.sqrt(strength)

    def lgamma(z):
        return -0.509 * z * z * (root / (1 + root) - 0.3 * strength) if z else 0.1 * strength

    offsets = [r['beta'] - ph * r['powers'].get('H+', 0) - lgamma(r['charge']) for r in records]
    power = [
        max([abs(v) for nz in sparse for j, v in nz if j == k] + [1.0]) for k in range(len(bases))
    ]
    logs = list(logs)
    for _ in range(sweeps):
        sums = [0.0] * len(bases)
        for o, nz in zip(offsets, sparse):
            a = 10.0 ** max(-300, min(100, o + sum(v * logs[j] for j, v in nz)))
            for j, v in nz:
                sums[j] += a * v
        worst = 0.0
        for k, b in enumerate(bases):
            if sums[k] <= 0:
                continue
            change = (math.log10(totals[b]) - math.log10(sums[k])) / power[k]
            logs[k] += change
            worst = max(worst, abs(change))
        if worst < 1e-3:
            break
    return logs


def solve(totals, ph, *, phases=(), ionic_strength=None, temperature_c=25.0, start=None):
    """Equilibrium at fixed pH. ``start`` (an AqueousResult of a nearby state, such as
    the previous step of a dose or pH search) only seeds the iteration; the converged
    state is the same within solver tolerance, and a failed warm start falls back to
    the cold start below."""
    if start is not None:
        try:
            return _solve(
                totals,
                ph,
                phases=phases,
                ionic_strength=ionic_strength,
                temperature_c=temperature_c,
                start=start,
            )
        except DeliveryError as exc:
            if exc.code != 'nonconvergent':
                raise
    try:
        return _solve(
            totals, ph, phases=phases, ionic_strength=ionic_strength, temperature_c=temperature_c
        )
    except DeliveryError as exc:
        if exc.code != 'nonconvergent':
            raise
    # The cold start (every free activity at total/1000) can leave Newton crawling far
    # from strongly complexed free ions (#52); restart from a continued-fraction estimate.
    return _solve(
        totals,
        ph,
        phases=phases,
        ionic_strength=ionic_strength,
        temperature_c=temperature_c,
        presolve=True,
    )


def _solve(
    totals, ph, *, phases=(), ionic_strength=None, temperature_c=25.0, presolve=False, start=None
):
    if temperature_c != 25:
        raise DeliveryError('temperature_out_of_range', 'reaction dataset is restricted to 25 C')
    if not math.isfinite(ph) or not 0 <= ph <= 14:
        raise DeliveryError('out_of_range', 'pH must be finite in [0,14]')
    for name, value in totals.items():
        if name not in chemistry()['bases'] or not math.isfinite(value) or value < 0:
            raise DeliveryError('invalid_totals', f'invalid analytical component {name}: {value}')
    if ionic_strength is not None and (
        not math.isfinite(ionic_strength) or not 0 <= ionic_strength <= 0.1
    ):
        raise DeliveryError(
            'activity_model_out_of_range', 'Davies model requires I <= 0.1 mol/kgw'
        )
    totals = {n: v for n, v in totals.items() if v > 0}
    bases = list(totals)
    n = len(bases)
    permitted = set(bases) | {'H+', 'H2O'}
    records = [
        r for r in chemistry()['aqueous'] if r['name'] != 'H2O' and set(r['powers']) <= permitted
    ]
    all_phases = {r['name']: r for r in chemistry()['phases']}
    phases = [chemistry()['aliases'].get(p, p) for p in phases]
    if any(p not in all_phases for p in phases):
        raise DeliveryError('unknown_phase', 'phase not in the pinned reaction set')
    candidates = {p: all_phases[p] for p in phases if set(all_phases[p]['powers']) <= permitted}
    stoich = [[r['powers'].get(b, 0.0) for b in bases] for r in records]
    # Each species involves few components; iterate only its non-zero stoichiometry.
    sparse = [[(j, v) for j, v in enumerate(s) if v] for s in stoich]
    strength = (
        ionic_strength
        if ionic_strength is not None
        else min(0.05, max(1e-8, sum(totals.values())))
    )
    logs = [math.log10(totals[b]) - 3 for b in bases]
    if presolve:
        logs = _continued_fraction(logs, totals, bases, records, sparse, ph, strength)
    active = []
    solids = {}
    water = 1.0
    if start is not None:
        logs = [
            math.log10(start.activities[b]) if start.activities.get(b, 0) > 0 else v
            for b, v in zip(bases, logs)
        ]
        if ionic_strength is None:
            strength = min(0.1, max(1e-8, start.ionic_strength))
        water = start.water_activity
        active = [p for p, v in start.precipitated.items() if v > 0 and p in candidates]
        solids = {p: start.precipitated[p] for p in active}
    count = 0
    previous = None

    def lgamma(z):
        root = math.sqrt(strength)
        return -0.509 * z * z * (root / (1 + root) - 0.3 * strength) if z else 0.1 * strength

    for outer in range(100):
        offsets = [
            r['beta']
            - ph * r['powers'].get('H+', 0)
            + math.log10(water) * r['powers'].get('H2O', 0)
            - lgamma(r['charge'])
            for r in records
        ]

        def evaluate(x, jacobian=False):
            amounts = [
                10.0 ** max(-300, min(100, o + sum(v * x[j] for j, v in nz)))
                for o, nz in zip(offsets, sparse)
            ]
            sums = [0.0] * n
            for a, nz in zip(amounts, sparse):
                for j, v in nz:
                    sums[j] += a * v
            for k, p in enumerate(active):
                for j, b in enumerate(bases):
                    sums[j] += x[n + k] * all_phases[p]['powers'].get(b, 0.0)
            if any(v <= 0 for v in sums):
                return None
            residual = [math.log10(v / totals[b]) for b, v in zip(bases, sums)]
            for p in active:
                r = all_phases[p]
                residual.append(
                    sum(r['powers'].get(b, 0) * x[j] for j, b in enumerate(bases))
                    - ph * r['powers'].get('H+', 0)
                    + math.log10(water) * r['powers'].get('H2O', 0)
                    - r['beta']
                )
            if not jacobian:
                return residual, amounts
            moments = [[0.0] * n for _ in range(n)]
            for a, nz in zip(amounts, sparse):
                for j, vj in nz:
                    weighted = a * vj
                    row = moments[j]
                    for k, vk in nz:
                        row[k] += weighted * vk
            matrix = []
            for j, b in enumerate(bases):
                row = [value / sums[j] for value in moments[j]]
                row += [all_phases[p]['powers'].get(b, 0.0) / (sums[j] * LN10) for p in active]
                matrix.append(row)
            for p in active:
                matrix.append(
                    [all_phases[p]['powers'].get(b, 0.0) for b in bases] + [0.0] * len(active)
                )
            return residual, amounts, matrix

        for phase_step in range(80):
            x = logs + [solids.get(p, 0.0) for p in active]
            for iteration in range(150):
                count += 1
                residual, amounts, matrix = evaluate(x, True)
                norm = max(map(abs, residual), default=0.0)
                # A warm start can begin inside the tolerance with the previous state's
                # residual; one Newton step restores the cold path's quadratic finish (#61).
                if norm < 2e-10 and (iteration or start is None or norm < 1e-14):
                    break
                step = linear(matrix, [-r for r in residual])
                alpha = min(1.0, 4 / max([abs(v) for v in step[:n]] + [4.0]))
                for _ in range(50):
                    trial = [v + alpha * d for v, d in zip(x, step)]
                    got = evaluate(trial)
                    if got and max(map(abs, got[0]), default=0.0) < norm:
                        x = trial
                        break
                    alpha *= 0.5
                else:
                    # A near-singular Jacobian can give a useless Newton direction
                    # (seen after a cold start with a strong chelate); take a damped
                    # least-squares step instead. Paths that converge today are unchanged.
                    x = _damped_step(evaluate, x, residual, matrix)
                    if x is None:
                        raise DeliveryError(
                            'nonconvergent', f'equilibrium line search stalled (residual {norm:g})'
                        )
            else:
                raise DeliveryError('nonconvergent', 'aqueous Newton iteration limit')
            logs = x[:n]
            solids = dict(zip(active, x[n:]))
            negative = [p for p in active if solids[p] < -1e-13]
            if negative:
                active.remove(min(negative, key=solids.get))
                continue
            loga = dict(zip(bases, logs)) | {'H+': -ph, 'H2O': math.log10(water)}
            saturation = {
                p: sum(v * loga[b] for b, v in r['powers'].items()) - r['beta']
                for p, r in all_phases.items()
                if set(r['powers']) <= permitted
            }
            excess = [p for p in candidates if p not in active and saturation[p] > 1e-8]
            if not excess:
                break
            active.append(max(excess, key=saturation.get))
        else:
            raise DeliveryError('nonconvergent', 'phase active set iteration limit')
        species = {r['name']: a for r, a in zip(records, amounts)}
        updated = 0.5 * sum(a * r['charge'] ** 2 for a, r in zip(amounts, records))
        next_water = max(0.9, 1 - sum(amounts) / 55.5084)
        if updated > 0.1:
            raise DeliveryError(
                'activity_model_out_of_range', f'Davies ionic strength {updated:g} exceeds 0.1'
            )
        if (ionic_strength is not None or abs(updated - strength) < 1e-12) and abs(
            next_water - water
        ) < 1e-12:
            activities = {
                r['name']: species[r['name']] * 10 ** lgamma(r['charge']) for r in records
            }
            activities['H2O'] = water
            residuals = {
                b: sum(a * s[j] for a, s in zip(amounts, stoich))
                + sum(max(0, v) * all_phases[p]['powers'].get(b, 0.0) for p, v in solids.items())
                - totals[b]
                for j, b in enumerate(bases)
            }
            limitations, domain = model_qualification(totals)
            return AqueousResult(
                totals,
                ph,
                strength,
                species,
                activities,
                saturation,
                {p: max(0, v) for p, v in solids.items()},
                residuals,
                count,
                sum(a * r['charge'] for a, r in zip(amounts, records)),
                water,
                limitations,
                domain,
                dict(
                    mass_action_log_residual=norm,
                    maximum_relative_balance=max(
                        (abs(v) / totals[b] for b, v in residuals.items()), default=0.0
                    ),
                    ionic_strength_update=abs(updated - strength),
                    fixed_ionic_strength=ionic_strength is not None,
                    water_activity_update=abs(next_water - water),
                    log_residual_limit=2e-10,
                    ionic_strength_update_limit=1e-12,
                    water_activity_update_limit=1e-12,
                    qualification='iteration residuals; forward/physical accuracy not certified',
                ),
            )
        if ionic_strength is None:
            # Secant step on g(I) = I(speciation at I) - I, which converges superlinearly
            # whether ion pairing makes g's slope positive or negative; the plain average
            # (linear, ~35 passes to 1e-12, #61) remains the fallback.
            gap = updated - strength
            step = (strength + updated) / 2
            if previous is not None and gap != previous[1]:
                secant = strength - gap * (strength - previous[0]) / (gap - previous[1])
                if 0 < secant <= 0.1:
                    step = secant
            previous = (strength, gap)
            strength = step
        # Water activity depends only weakly on itself (through H2O-bearing species).
        water = next_water
    raise DeliveryError('nonconvergent', 'ionic strength/water iteration limit')


@dataclass(frozen=True)
class AcidResult:
    """Nitric acid needed to move a solution from its initial pH to the target, with both solved
    states; the pH must still be measured after mixing.
    """

    initial: AqueousResult
    target: AqueousResult
    nitric_acid_molal: float
    post_mix_measurement_required: bool = True


def nitric_target(totals, initial_ph, target_ph, *, phases=()):
    """Conserve every component, including added nitrate, through the same solve.

    Initial residual charge defines the strong-ion inventory (water alkalinity
    need not be guessed). HNO3 is neutral as a reagent: the final residual
    electrical charge equals the initial residual charge, after adding nitrate.
    """
    initial = solve(totals, initial_ph, phases=phases)
    if target_ph == initial_ph:
        return AcidResult(initial, initial, 0.0)
    if target_ph > initial_ph:
        raise DeliveryError('wrong_reagent_direction', 'target requires base')
    lo, hi = 0.0, 0.001
    last = [initial]

    def at(dose):
        # Warm-start each dose from the previous solve (#61); only the iteration path changes.
        last[0] = solve(
            dict(totals) | {'NO3-': totals.get('NO3-', 0.0) + dose},
            target_ph,
            phases=phases,
            start=last[0],
        )
        return last[0]

    target = at(0.0)
    if target.charge_balance < initial.charge_balance - 1e-12:
        raise DeliveryError('wrong_reagent_direction', 'target requires base')
    f_lo = target.charge_balance - initial.charge_balance
    while (f_hi := at(hi).charge_balance - initial.charge_balance) > 0:
        lo, f_lo = hi, f_hi
        hi *= 2
    # Same final width as 40 bisection steps from [0, hi], in far fewer solves.
    lo, hi = shrink_bracket(
        lambda dose: at(dose).charge_balance - initial.charge_balance,
        lo,
        f_lo,
        hi,
        f_hi,
        width=hi * 2.0**-40,
    )
    dose = (lo + hi) / 2
    return AcidResult(initial, at(dose), dose)
