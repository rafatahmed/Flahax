# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Kernel contracts: independent balances, domain guards and injected solver failures.

Fault injection verifies rejection/retry contracts, not chemical accuracy.
Legacy checks retain their explicitly limited reaction systems.
"""

import math
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from flahax import aqueous_model as aq
from flahax import fertilizer_equilibrium as fe
from flahax import phosphate_complexes as pc
from flahax import struvite_mixture as sm
from flahax.ammonia import ammonia_speciation
from flahax.competition import carbonate_competition, calcium_sulfate_struvite_competition
from flahax.delivery_contracts import DeliveryError
from flahax.equilibrium import (
    calcite_co2_reference_values,
    gypsum_reference_values,
    davies_gamma,
    solve_calcite_co2_equilibrium,
    solve_gypsum_equilibrium,
)
from flahax.mixed_equilibrium import solve_mixed_fertilizer_equilibrium
from flahax.phase_allocation import phase_allocation
from flahax.phosphate import orthophosphate_speciation
from flahax.struvite import struvite_saturation_index
from flahax.thermodynamics import MineralPhase, phase_saturation_index
from flahax.trace_equilibrium import ChMicroTotals, ChMicroProductDose, solve_ch_micro_equilibrium


class KernelDomainTests(unittest.TestCase):
    def rejected(self, function, *args, **kwargs):
        with self.assertRaises(DeliveryError):
            function(*args, **kwargs)

    def test_phase_and_trace_domains(self):
        for name in ('', ' ', None, 3):
            self.rejected(phase_allocation, name, 0, 1)
        for v in (-1, math.nan, math.inf):
            self.rejected(phase_allocation, 'Calcite', v, 0)
            self.rejected(phase_allocation, 'Calcite', 0, v)
            for field in ChMicroTotals.__dataclass_fields__:
                self.rejected(ChMicroTotals, **{field: v})
            self.rejected(ChMicroProductDose, v)
            self.rejected(ChMicroProductDose(1).totals, calcium=v)
        self.rejected(solve_ch_micro_equilibrium, {}, 7, 0.01)
        for ph in (-1, 15, math.nan):
            self.rejected(solve_ch_micro_equilibrium, ChMicroTotals(), ph, 0.01)
        for strength in (-1, 0.11, math.inf):
            self.rejected(solve_ch_micro_equilibrium, ChMicroTotals(), 7, strength)

    def test_acid_forms_and_competition_domains(self):
        for function in (ammonia_speciation, orthophosphate_speciation):
            for args in ((math.nan, 7, 0.01), (-1, 7, 0.01), (1, 15, 0.01), (1, 7, 0.11)):
                self.rejected(function, *args)
        for bad in (0, -1, math.nan, math.inf):
            self.rejected(struvite_saturation_index, bad, 1, 1)
            self.rejected(calcium_sulfate_struvite_competition, bad, 1, 1, 1, 1)
            self.rejected(carbonate_competition, 1, bad, 1, 1, 1, 1)
            self.rejected(pc.hydroxyapatite_hpo4_activity_at_equilibrium, bad, 7)
        self.rejected(pc.hydroxyapatite_hpo4_activity_at_equilibrium, 0.001, 15)
        for args in (
            (math.nan, 1, 1, 1, 7, 0.01),
            (0, 1, 1, 1, 7, 0.01),
            (1, 1, 1, 1, 15, 0.01),
            (1, 1, 1, 1, 7, 0.11),
        ):
            self.rejected(pc.calcium_magnesium_phosphate_speciation, *args)
            self.rejected(sm.struvite_mixture_speciation, *args)
        for bad in (-1, math.inf, math.nan):
            self.rejected(
                sm.solve_charge_balanced_struvite_mixture, 0.001, 0.001, 0.001, 0.001, bad
            )

    def test_mineral_reaction_schema_and_activity_guards(self):
        good = dict(
            name='Test',
            dissolved_species={'A': 2, 'B': -1},
            log_k=-3,
            database='declared synthetic reaction',
            temperature_c=25,
        )
        for change in (
            dict(name=''),
            dict(database=''),
            dict(dissolved_species={}),
            dict(dissolved_species={'': 1}),
            dict(dissolved_species={'A': True}),
            dict(dissolved_species={'A': object()}),
            dict(dissolved_species={'A': 0}),
            dict(log_k=math.inf),
            dict(temperature_c=math.nan),
        ):
            self.rejected(MineralPhase, **(good | change))
        phase = MineralPhase(**good)
        self.assertAlmostEqual(phase_saturation_index(phase, {'A': 0.01, 'B': 0.1}), 0)
        self.assertAlmostEqual(phase_saturation_index(phase, {'A': 0.1, 'B': 0.1}), 2)
        self.rejected(phase_saturation_index, None, {})
        self.rejected(phase_saturation_index, phase, [])
        for values in ({}, {'A': 'bad', 'B': 1}, {'A': 0, 'B': 1}, {'A': math.inf, 'B': 1}):
            self.rejected(phase_saturation_index, phase, values)

    def test_legacy_and_public_entry_domains(self):
        for field in fe.FertilizerTotals.__dataclass_fields__:
            self.rejected(fe.FertilizerTotals, **{field: -1})
        self.rejected(fe.solve_legacy_phreeqc_macro, {}, 7)
        self.rejected(fe.solve_legacy_phreeqc_macro, fe.FertilizerTotals(), 15)
        self.rejected(fe.plan_legacy_phreeqc_nitric, fe.FertilizerTotals(), 7, 6, trace_totals={})
        self.rejected(fe.plan_legacy_phreeqc_nitric, fe.FertilizerTotals(), 6, 7)
        self.rejected(fe.plan_nitric_acid_target, {}, 7, 6)
        self.rejected(solve_mixed_fertilizer_equilibrium, {}, 7)
        self.rejected(
            solve_mixed_fertilizer_equilibrium, fe.FertilizerTotals(), 7, trace_totals={}
        )
        for converter in (calcite_co2_reference_values, gypsum_reference_values):
            with self.assertRaises(TypeError):
                converter(None)
        self.rejected(solve_calcite_co2_equilibrium, math.nan)
        self.rejected(solve_calcite_co2_equilibrium, -3, temperature_c=30)
        self.rejected(solve_gypsum_equilibrium, temperature_c=30)
        for bad in (-1, math.nan):
            self.rejected(davies_gamma, 1, bad)


class KernelInvariantTests(unittest.TestCase):
    def test_acid_form_conservation_and_scaling(self):
        # At I=0 activities equal molalities; at the NH4 pKa both forms are equal.
        half = ammonia_speciation(0.002, 9.252, 0)
        self.assertAlmostEqual(half.ammonium_molal, 0.001, places=15)
        self.assertAlmostEqual(half.ammonia_molal, 0.001, places=15)
        for ph in (0, 4, 7, 10, 14):
            for strength in (0, 0.01, 0.1):
                for total in (0, 1e-10, 0.001):
                    a = ammonia_speciation(total, ph, strength)
                    self.assertAlmostEqual(a.ammonium_molal + a.ammonia_molal, total, delta=1e-15)
                    p = orthophosphate_speciation(total, ph, strength)
                    self.assertAlmostEqual(
                        p.po4_molal + p.hpo4_molal + p.h2po4_molal + p.h3po4_molal,
                        total,
                        delta=1e-15,
                    )
                    doubled = orthophosphate_speciation(2 * total, ph, strength)
                    self.assertEqual(doubled.po4_molal, 2 * p.po4_molal)

    def test_component_order_and_independent_balances(self):
        totals = {
            'Ca+2': 0.001,
            'Mg+2': 0.001,
            'PO4-3': 0.001,
            'CO3-2': 0.001,
            'NH4+': 0.001,
            'SO4-2': 0.001,
            'Edta-4': 1e-5,
            'Fe+3': 1e-5,
        }
        phases = ('Calcite', 'Gypsum', 'Hydroxylapatite', 'Struvite')
        result = aq.solve(totals, 8, phases=phases)
        reverse = aq.solve(dict(reversed(list(totals.items()))), 8, phases=tuple(reversed(phases)))
        # Balance is independently accumulated from exported species and reaction
        # stoichiometry, never from result.residuals or the solver's diagnostic norm.
        records = aq.chemistry()['aqueous']
        minerals = {r['name']: r for r in aq.chemistry()['phases']}
        for base, total in totals.items():
            dissolved = math.fsum(
                result.species.get(r['name'], 0) * r['powers'].get(base, 0)
                for r in records
                if r['name'] != 'H2O'
            )
            solid = math.fsum(
                amount * minerals[p]['powers'].get(base, 0)
                for p, amount in result.precipitated.items()
            )
            self.assertAlmostEqual(dissolved + solid, total, delta=total * 1e-8)
            self.assertAlmostEqual(
                result.activities[base],
                reverse.activities[base],
                delta=max(result.activities[base] * 1e-7, 1e-30),
            )
        for phase in phases:
            r = minerals[phase]
            si = (
                math.fsum(v * math.log10(result.activities[b]) for b, v in r['powers'].items())
                - r['beta']
            )
            self.assertAlmostEqual(si, result.saturation_indices[phase], delta=1e-9)
            self.assertLessEqual(si, 1e-8)
            self.assertGreaterEqual(result.precipitated.get(phase, 0), 0)
            if result.precipitated.get(phase, 0) > 1e-13:
                self.assertAlmostEqual(si, 0, delta=1e-8)
        mixed = solve_mixed_fertilizer_equilibrium(
            fe.FertilizerTotals(potassium=0.001), 7, allow_precipitation=False
        )
        self.assertEqual(mixed.species['K+'], mixed.aqueous.species['K+'])

    def test_phase_transfer_and_legacy_stoichiometry(self):
        for initial, final in ((0, 1), (1, 0), (1, 1)):
            transfer = phase_allocation('Calcite', initial, final)
            self.assertEqual(
                transfer.dissolved_moles - transfer.precipitated_moles, initial - final
            )
        totals = fe.FertilizerTotals(
            calcium=0.005,
            magnesium=0.003,
            phosphate=0.002,
            ammonium=0.001,
            sulfate=0.004,
            carbonate=0.003,
        )
        for phase, expected in (
            ('Calcite', 0.003),
            ('Gypsum', 0.004),
            ('Hydroxyapatite', 0.002 / 3),
            ('Struvite', 0.001),
        ):
            self.assertEqual(fe._phase_limit(totals, phase), expected)
            removed = fe._remove_for_phase(totals, phase, expected)
            self.assertEqual(fe._phase_limit(removed, phase), 0)
        blank = fe.solve_legacy_phreeqc_macro(fe.FertilizerTotals(), 7)
        self.assertFalse(blank.phase_allocations)
        self.assertEqual(blank.precipitation_moles, {})
        self.assertEqual(fe._phosphate_complexes(0, 0, 0, 0, 7, 1, 1, 1)['po4'], 0)


class KernelFailureTests(unittest.TestCase):
    def test_damped_step_reduces_merit_or_reports_failure(self):
        got = aq._damped_step(lambda x: ([x[0] - 2], []), [0], [-2], [[1]])
        self.assertLess(abs(got[0] - 2), 2)
        self.assertIsNone(aq._damped_step(lambda x: None, [0], [1], [[1]]))
        self.assertIsNone(aq._damped_step(lambda x: ([1], []), [0], [1], [[1]]))
        with patch.object(aq, 'linear', side_effect=DeliveryError('nonconvergent', 'injected')):
            self.assertIsNone(aq._damped_step(lambda x: ([0], []), [0], [1], [[1]]))

    def test_retry_only_numerical_failures_and_seed_sequence(self):
        success = object()
        failure = DeliveryError('nonconvergent', 'injected')
        with patch.object(aq, '_solve', side_effect=[failure, failure, success]) as solver:
            self.assertIs(aq.solve({}, 7, start=success), success)
            self.assertIs(solver.call_args_list[0].kwargs['start'], success)
            self.assertTrue(solver.call_args_list[-1].kwargs['presolve'])
        for start in (None, success):
            with patch.object(
                aq, '_solve', side_effect=DeliveryError('invalid_totals', 'injected')
            ) as solver:
                with self.assertRaisesRegex(DeliveryError, 'injected'):
                    aq.solve({}, 7, start=start)
                self.assertEqual(solver.call_count, 1)

    def test_continued_fraction_handles_empty_component_and_iteration(self):
        self.assertEqual(aq._continued_fraction([-3], {'X': 0.001}, ['X'], [], [], 7, 0), [-3])
        result = aq._continued_fraction(
            [-6],
            {'X': 0.001},
            ['X'],
            [{'beta': 0, 'powers': {'X': 1}, 'charge': 0}],
            [[(0, 1)]],
            7,
            0,
        )
        self.assertAlmostEqual(result[0], -3)

    def test_stagnant_newton_fails_and_damped_recovery_is_used(self):
        with patch.object(aq, 'linear', side_effect=lambda a, b: [0] * len(b)):
            with patch.object(aq, '_damped_step', return_value=None):
                with self.assertRaisesRegex(DeliveryError, 'line search stalled'):
                    aq._solve({'K+': 0.001}, 7)
        original = aq.linear
        calls = [0]

        def zero_first(a, b):
            calls[0] += 1
            return [0] * len(b) if calls[0] == 1 else original(a, b)

        with patch.object(aq, 'linear', side_effect=zero_first):
            result = aq._solve({'K+': 0.001}, 7)
        self.assertAlmostEqual(result.species['K+'], 0.001, delta=1e-12)

    def test_phosphate_singular_and_stagnant_iterations(self):
        with self.assertRaisesRegex(DeliveryError, 'singular'):
            pc._solve_linear3([[0] * 3 for _ in range(3)], [1] * 3)
        with patch.object(pc, '_solve_linear3', return_value=[0, 0, 0]):
            with self.assertRaisesRegex(DeliveryError, 'did not converge'):
                pc.calcium_magnesium_phosphate_speciation(0.001, 0.001, 0.001, 0.001, 7, 0.01)

    def test_legacy_ionic_strength_failure_contracts(self):
        with self.assertRaisesRegex(DeliveryError, 'limited'):
            fe._fixed_ph_equilibrium(fe.FertilizerTotals(potassium=1), 7)
        with patch.object(fe, '_ionic_strength', side_effect=[0.02, 0.04] * 15):
            with self.assertRaisesRegex(DeliveryError, 'did not converge'):
                fe._fixed_ph_equilibrium(fe.FertilizerTotals(), 7)

    def test_nitric_direction_and_expanding_bracket(self):
        with self.assertRaisesRegex(DeliveryError, 'requires base'):
            aq.nitric_target({}, 7, 8)
        initial = SimpleNamespace(charge_balance=0)
        wrong = SimpleNamespace(charge_balance=-1)
        with patch.object(aq, 'solve', side_effect=[initial, wrong]):
            with self.assertRaisesRegex(DeliveryError, 'requires base'):
                aq.nitric_target({}, 7, 6)

        # Synthetic linear charge law: tests bracketing independently of chemistry.
        def state(totals, ph, **kwargs):
            return SimpleNamespace(charge_balance=0 if ph == 7 else 0.005 - totals.get('NO3-', 0))

        with patch.object(aq, 'solve', side_effect=state):
            result = aq.nitric_target({}, 7, 6)
        self.assertAlmostEqual(result.nitric_acid_molal, 0.005, delta=1e-14)
        self.assertAlmostEqual(result.target.charge_balance, 0, delta=1e-14)


class RetainedPairBalanceTests(unittest.TestCase):
    def test_pair_conservation_and_independent_decimal_root(self):
        from decimal import Decimal, localcontext

        for ca, sulfate in (
            (0, 0),
            (0, 0.01),
            (0.01, 0),
            (0.001, 0.01),
            (0.05, 0.05),
            (0.1, 0.1),
            (1, 0.01),
        ):
            for strength in (0, 0.01, 0.1):
                free_ca, free_sulfate, pair = sm._calcium_sulfate_free_totals(
                    ca, sulfate, strength
                )
                self.assertGreaterEqual(min(free_ca, free_sulfate, pair), 0)
                self.assertAlmostEqual(free_ca + pair, ca, delta=1e-15)
                self.assertAlmostEqual(free_sulfate + pair, sulfate, delta=1e-15)
                k = 10**2.14 * davies_gamma(2, strength) ** 2
                self.assertAlmostEqual(pair, k * free_ca * free_sulfate, delta=1e-14)
                # Independent bisection with Decimal arithmetic on the pair amount.
                with localcontext() as context:
                    context.prec = 60
                    c, s, coefficient = map(Decimal, map(str, (ca, sulfate, k)))
                    lo, hi = Decimal(0), min(c, s)
                    for _ in range(200):
                        mid = (lo + hi) / 2
                        if coefficient * (c - mid) * (s - mid) > mid:
                            lo = mid
                        else:
                            hi = mid
                    self.assertAlmostEqual(pair, float((lo + hi) / 2), delta=1e-15)


class KernelIterationPathTests(unittest.TestCase):
    """Reduced budgets exercise finite termination paths, not numerical accuracy.

    Module-local range injection leaves all other module loops unchanged.
    Retained kernels must also reject exhausted iteration budgets.
    """

    @staticmethod
    def budget(limit, replacement=1):
        return lambda *args: range(replacement) if args == (limit,) else range(*args)

    def test_current_solver_exhaustion_is_explicit(self):
        for limit, message in (
            (150, 'Newton iteration'),
            (80, 'active set'),
            (100, 'ionic strength/water'),
        ):
            totals = {'Ca+2': 0.001, 'CO3-2': 0.001} if limit == 80 else {'K+': 0.001}
            with patch.object(aq, 'range', self.budget(limit), create=True):
                with self.assertRaisesRegex(DeliveryError, message):
                    aq._solve(totals, 8, phases=('Calcite',))

    def test_aqueous_guards_and_partial_warm_seed(self):
        for totals, kwargs in (
            ({'unrecognized': 1}, {}),
            ({'K+': -1}, {}),
            ({}, {'phases': ('unrecognized',)}),
        ):
            with self.assertRaises(DeliveryError):
                aq._solve(totals, 7, **kwargs)
        self.assertEqual(davies_gamma(0, 0.01), 1)
        initial = aq.solve({'K+': 0.001}, 7)
        self.assertEqual(aq.nitric_target({'K+': 0.001}, 7, 7).nitric_acid_molal, 0)
        partial = aq.solve({'K+': 0.001, 'Cl-': 0.001}, 7, start=initial)
        self.assertAlmostEqual(partial.species['Cl-'], 0.001, delta=1e-12)

    def test_legacy_iteration_exhaustion_is_explicit(self):
        from flahax import equilibrium as eq

        for module, limit, function, args in (
            (eq, 100, solve_calcite_co2_equilibrium, (-3,)),
            (fe, 60, fe._phosphate_complexes, (0.001, 0.001, 0.001, 0.001, 7, 1, 1, 1)),
            (
                fe,
                100,
                fe._at_fixed_ionic_strength,
                (fe.FertilizerTotals(calcium=0.001, sulfate=0.001), 7, 0.01),
            ),
            (
                sm,
                60,
                sm.solve_charge_balanced_struvite_mixture,
                (0.001, 0.001, 0.001, 0.001, 0.003),
            ),
        ):
            with patch.object(module, 'range', self.budget(limit), create=True):
                with self.assertRaisesRegex(DeliveryError, 'iteration limit'):
                    function(*args)

    def test_legacy_precipitation_transfer_on_real_carbonate_case(self):
        totals = fe.FertilizerTotals(calcium=0.001, carbonate=0.001)
        result = fe.solve_legacy_phreeqc_macro(totals, 8.5)
        amount = sum(a.precipitated_moles for a in result.phase_allocations)
        self.assertGreater(amount, 0)
        self.assertAlmostEqual(result.totals.calcium + amount, totals.calcium, delta=1e-15)
        self.assertAlmostEqual(result.totals.carbonate + amount, totals.carbonate, delta=1e-15)
        acid = fe.plan_nitric_acid_target(fe.FertilizerTotals(), 7, 6)
        self.assertGreater(acid.nitric_acid_molal, 0)

    def test_legacy_phase_selection_tiny_amount_and_missing_inventory(self):
        # Synthetic SI response isolates phase selection and ledger bookkeeping;
        # it is not presented as a thermodynamic test.
        totals = fe.FertilizerTotals(calcium=1, carbonate=1)

        def state(current, ph):
            return fe.FertilizerEquilibrium(
                current,
                ph,
                0,
                {},
                {},
                {
                    'Hydroxyapatite': 1,
                    'Calcite': current.calcium - 0.5,
                    'Gypsum': -1,
                    'Struvite': -1,
                },
                (),
            )

        with patch.object(fe, '_fixed_ph_equilibrium', side_effect=state):
            result = fe.solve_legacy_phreeqc_macro(totals, 7)
        self.assertAlmostEqual(result.totals.calcium, 0.5, delta=1e-8)
        with patch.object(fe, '_fixed_ph_equilibrium', side_effect=state):
            with patch.object(fe, '_phase_limit', return_value=1e-16):
                with self.assertRaisesRegex(DeliveryError, "phase allocation iteration limit"):
                    fe.solve_legacy_phreeqc_macro(totals, 7)
        with patch.object(fe, '_fixed_ph_equilibrium', side_effect=state):
            with patch.object(fe, 'range', self.budget(4), create=True):
                result = fe.solve_legacy_phreeqc_macro(totals, 7)
        self.assertTrue(result.phase_allocations)


class WarmSeedInvariantTests(unittest.TestCase):
    def test_fixed_strength_and_distant_strength_seeds_preserve_solution(self):
        from dataclasses import replace

        for totals, ph in (
            ({'K+': 0.001, 'Cl-': 0.001}, 7),
            ({'Ca+2': 0.02, 'SO4-2': 0.02}, 7),
            ({'Fe+3': 0.001, 'Edta-4': 0.001}, 6),
            ({'PO4-3': 0.01, 'Na+': 0.02}, 8),
        ):
            cold = aq.solve(totals, ph)
            for strength in (0, 1e-8, 0.1):
                seed = replace(cold, ionic_strength=strength)
                warm = aq.solve(totals, ph, start=seed)
                self.assertAlmostEqual(warm.ionic_strength, cold.ionic_strength, delta=2e-11)
                for base in totals:
                    self.assertAlmostEqual(
                        warm.activities[base],
                        cold.activities[base],
                        delta=max(cold.activities[base] * 1e-7, 1e-30),
                    )
            fixed = aq.solve(totals, ph, ionic_strength=0.01)
            warm_fixed = aq.solve(totals, ph, ionic_strength=0.01, start=fixed)
            self.assertEqual(warm_fixed.ionic_strength, 0.01)


class RetainedIterationBalanceTests(unittest.TestCase):
    def test_converged_legacy_pairing_retains_both_components(self):
        for ca, sulfate in ((0.001, 0.001), (0.002, 0.001), (0, 0.001)):
            totals = fe.FertilizerTotals(calcium=ca, sulfate=sulfate)
            species, activities, _ = fe._at_fixed_ionic_strength(totals, 7, 0.01)
            self.assertAlmostEqual(species['Ca+2'] + species['CaSO4'], ca, delta=2e-14)
            self.assertAlmostEqual(species['SO4-2'] + species['CaSO4'], sulfate, delta=2e-14)
            self.assertAlmostEqual(
                species['CaSO4'], 10**2.25 * activities['Ca+2'] * activities['SO4-2'], delta=2e-14
            )
