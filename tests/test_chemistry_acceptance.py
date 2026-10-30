# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Acceptance invariants independent of the PHREEQC output comparator."""

import math
import unittest
from flahax import (
    load_library,
    DeliveryError,
    FertilizerTotals,
    solve_mixed_fertilizer_equilibrium,
)
from flahax.aqueous_model import chemistry, solve, nitric_target
from flahax.product_conversion import (
    catalogue_dose_totals,
    convert_catalogue_product_dose,
    solve_catalogue_product_doses,
)
from tests.catalogue_history import historical_catalogue


class ChemistryAcceptanceTests(unittest.TestCase):
    # Catalogue v0.0: re-enable in PR 4 (G5)
    def test_every_product_assay_survives_the_analytical_boundary(self):
        self.enterContext(historical_catalogue())
        for product in load_library()['salts']:
            name = product['name']
            with self.subTest(product=name):
                converted = convert_catalogue_product_dose(product, 0.01)
                basis = catalogue_dose_totals({name: 0.01})
                self.assertTrue(basis)
                for key, amount in converted.totals.items():
                    mapping = {
                        'Ca': 'Ca+2',
                        'Mg': 'Mg+2',
                        'K': 'K+',
                        'Na': 'Na+',
                        'Fe': 'Fe+2' if 'Iron II' in name else 'Fe+3',
                        'Mn': 'Mn+2',
                        'Zn': 'Zn+2',
                        'Cu': 'Cu+2',
                        'phosphate': 'PO4-3',
                        'sulfate': 'SO4-2',
                        'boron': 'H3BO3',
                        'molybdate': 'MoO4-2',
                        'ammonium': 'NH4+',
                        'nitrate': 'NO3-',
                        'urea': 'Ure',
                        'Cl': 'Cl-',
                    }
                    self.assertAlmostEqual(basis[mapping[key]], amount, places=15)
                result = solve_catalogue_product_doses(
                    {name: 0.01}, 6.0, allow_precipitation=False
                ).aqueous
                for b, v in result.residuals.items():
                    self.assertLess(abs(v), 1e-9 * result.totals[b] + 1e-15)

    def test_urea_and_potassium_carbonate_stoichiometry(self):
        urea = catalogue_dose_totals({'Urea': 1.0})
        self.assertAlmostEqual(2 * urea['Ure'], 0.46646 / 14.0067)
        carbonate = catalogue_dose_totals({'Potassium Carbonate': 1.0})
        self.assertEqual(carbonate['K+'], 2 * carbonate['CO3-2'])

    def test_near_singular_newton_step_does_not_stall(self):
        # Cold start at this pH met a near-singular Jacobian (Fe-EDDHA) and raised
        # 'line search stalled'; a damped least-squares step now recovers.
        from benchmarks.cases import read_fixture

        totals = read_fixture('products/mixed_target_ph_nitric')['runtime_totals']
        for ph in (7.3962594096730125, 7.406259409673012):
            with self.subTest(ph=ph):
                result = solve(totals, ph)
                for component, residual in result.residuals.items():
                    self.assertLess(abs(residual), 1e-9 * result.totals[component] + 1e-15)

    def test_low_ph_chelate_mixtures_converge(self):
        # #52: below pH ~5.05 the cold start left Newton crawling toward strongly
        # complexed free ions (EDTA/DTPA/EDDHA with Fe and Cu) until its iteration limit.
        from benchmarks.cases import read_fixture

        for name in ('products/mixed_products', 'phases/mixed_product_phases'):
            data = read_fixture(name)
            for ph in (4.2, 4.3, 4.5, 4.7, 4.9, 5.0):
                with self.subTest(fixture=name, ph=ph):
                    result = solve(data['runtime_totals'], ph, phases=data.get('phases', ()))
                    for component, residual in result.residuals.items():
                        self.assertLess(abs(residual), 1e-9 * result.totals[component] + 1e-15)

    def test_acid_target_at_ph_five_for_chelate_mixture(self):
        # Failed on main with 'aqueous Newton iteration limit' (#52).
        from benchmarks.cases import read_fixture

        data = read_fixture('products/mixed_target_ph_nitric')
        result = nitric_target(data['runtime_totals'], data['initial_ph'], 5.0)
        self.assertAlmostEqual(result.target.ph, 5.0)
        self.assertGreater(result.nitric_acid_molal, 0.0)
        self.assertAlmostEqual(
            result.target.totals['NO3-'] - data['runtime_totals']['NO3-'],
            result.nitric_acid_molal,
            places=14,
        )

    def test_converging_solves_do_not_use_the_restart(self):
        import flahax.aqueous_model as model
        from benchmarks.cases import read_fixture

        calls = []
        original = model._continued_fraction
        model._continued_fraction = lambda *a, **k: calls.append(1) or original(*a, **k)
        try:
            solve(read_fixture('products/mixed_products')['runtime_totals'], 6.0)
        finally:
            model._continued_fraction = original
        self.assertEqual(calls, [])

    def test_chloride_salts_keep_chloride_and_add_no_nitrate(self):
        self.enterContext(historical_catalogue())
        calcium = catalogue_dose_totals({'Calcium Chloride (Dihydrate)': 1.0})
        self.assertNotIn('NO3-', calcium)
        self.assertAlmostEqual(calcium['Cl-'], 2 * calcium['Ca+2'], places=12)
        potassium = catalogue_dose_totals({'Potassium Chloride': 1.0})
        self.assertNotIn('NO3-', potassium)
        self.assertAlmostEqual(potassium['Cl-'], potassium['K+'], places=12)
        self.assertAlmostEqual(potassium['K+'], 0.5244693708642584 / 39.0983, places=12)

    def test_no_extra_dtpa_or_eddha_metal_families(self):
        for r in chemistry()['aqueous']:
            if set(r['powers']) & {'Dtp-5', 'Edd-4'}:
                self.assertFalse(
                    set(r['powers']) & {'Ca+2', 'Mg+2', 'Mn+2', 'Zn+2', 'Cu+2', 'Fe+2'}
                )

    def test_simultaneous_ligands_are_order_independent(self):
        totals = {
            'Fe+3': 3e-5,
            'Edta-4': 1e-5,
            'Dtp-5': 1e-5,
            'Edd-4': 1e-5,
            'Ca+2': 0.001,
            'NO3-': 0.002,
        }
        a = solve(totals, 6.0)
        b = solve(dict(reversed(list(totals.items()))), 6.0)
        for key, value in a.species.items():
            self.assertAlmostEqual(value, b.species[key], delta=1e-12 + abs(value) * 1e-8)
        for r in chemistry()['aqueous']:
            if r['name'] in a.species and set(r['powers']) <= (set(totals) | {'H+', 'H2O'}):
                expected = r['beta'] + sum(
                    v * math.log10(a.activities[k]) for k, v in r['powers'].items()
                )
                self.assertAlmostEqual(math.log10(a.activities[r['name']]), expected, places=9)

    def test_zero_dilute_domain_and_temperature_boundaries(self):
        self.assertGreater(solve({}, 7.0).species['H+'], 0)
        self.assertLess(solve({'Na+': 1e-12, 'Cl-': 1e-12}, 7.0).ionic_strength, 1e-6)
        for args in (
            {'totals': {'Na+': 0.2, 'Cl-': 0.2}, 'ph': 6.0},
            {'totals': {'Na+': 0.2, 'Cl-': 0.2}, 'ph': 6.0, 'ionic_strength': 0.01},
            {'totals': {}, 'ph': 6.0, 'ionic_strength': 0.10001},
            {'totals': {}, 'ph': 6.0, 'temperature_c': 30},
        ):
            with self.assertRaises(DeliveryError):
                solve(**args)

    def test_phase_complementarity_and_element_conservation(self):
        totals = {
            'Ca+2': 0.001,
            'Mg+2': 0.001,
            'PO4-3': 0.001,
            'CO3-2': 0.001,
            'SO4-2': 0.001,
            'Fe+3': 2e-5,
            'Zn+2': 1e-5,
            'Cu+2': 1e-5,
            'Mn+2': 1e-5,
            'Na+': 0.005,
            'Cl-': 0.005,
        }
        phases = [r['name'] for r in chemistry()['phases']]
        result = solve(totals, 8.0, phases=phases)
        self.assertTrue(result.precipitated)
        for p, si in result.saturation_indices.items():
            self.assertLessEqual(si, 1e-7, p)
            if result.precipitated.get(p, 0) > 1e-12:
                self.assertAlmostEqual(si, 0.0, places=7, msg=p)
        for b, v in result.residuals.items():
            self.assertLess(abs(v), 1e-9 * totals[b] + 1e-15, b)

    def test_macro_entry_point_honours_precipitation_flag(self):
        totals = FertilizerTotals(calcium=0.001, carbonate=0.002, sodium=0.002)
        without = solve_mixed_fertilizer_equilibrium(totals, 9.0, allow_precipitation=False)
        with_phases = solve_mixed_fertilizer_equilibrium(totals, 9.0, allow_precipitation=True)
        self.assertGreater(without.macro.saturation_indices['Calcite'], 0)
        self.assertFalse(without.macro.phase_allocations)
        self.assertGreater(with_phases.aqueous.precipitated['Calcite'], 0)

    def test_nitric_plan_preserves_nitrate_and_protonation_demand(self):
        totals = {
            'CO3-2': 0.001,
            'Na+': 0.002,
            'Cl-': 0.001,
            'H3BO3': 1e-4,
            'Dtp-5': 1e-5,
            'Fe+3': 1e-5,
        }
        result = nitric_target(totals, 7.4, 6.0)
        self.assertGreater(result.nitric_acid_molal, 0)
        self.assertAlmostEqual(result.target.totals['NO3-'], result.nitric_acid_molal, places=14)
        self.assertAlmostEqual(
            result.initial.charge_balance, result.target.charge_balance, places=12
        )
        self.assertEqual(result.target.totals['Dtp-5'], totals['Dtp-5'])
        self.assertTrue(result.post_mix_measurement_required)
        with self.assertRaises(DeliveryError):
            nitric_target(totals, 6.0, 7.0)
