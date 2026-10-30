# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Public joint quantities, fresh diagnosis, hard limits and unresolved searches."""

import unittest
from unittest.mock import patch
from flahax import load_library, plan_fertilizer_workflow, VolumeLitres
from flahax.ph_adjustment import nutrient_salts
from tests.test_ph_adjustment import ACIDS, RO, FORMULAS, LIBRARY, amended_ph
from tests.catalogue_history import historical_catalogue


def configuration(pool, product, **changes):
    controls = (
        dict(
            dose_steps={p['id']: 1e-4 for p in [*pool, product]},
            charge_scale=0.001,
            charge_tolerance=2e-12,
            loss_tolerance=1e-16,
            sensitivity_tolerance=0.01,
            trust_radius=10000,
            max_iterations=20,
            max_backtracks=20,
        )
        | changes
    )
    return dict(
        controls=controls,
        solvent_mass_kg=1000,
        reagent_solvent_fractions={product['id']: 0.4},
        maximum_reagent_mass_g={product['id']: 6000},
    )


class JointWorkflowTests(unittest.TestCase):
    # Catalogue v0.0: re-enable in PR 4 (G5)
    def test_explicit_joint_rebuilds_actual_recipe_and_zero_reagent(self):
        self.enterContext(historical_catalogue())
        pool = nutrient_salts(LIBRARY['salts'])
        product = ACIDS[0]
        result = plan_fertilizer_workflow(
            LIBRARY['salts'],
            FORMULAS['Tomato Stage.2 - first cluster (Howard Resh)'],
            {},
            5.8,
            final_volume=VolumeLitres(1000),
            equilibrium=RO,
            ph_adjustment=dict(
                products=[product],
                maximum_reagent_volume_litres=5,
                joint=configuration(pool, product),
            ),
        )
        stage = result.stages['ph_adjustment']
        self.assertEqual(stage.status, 'blocked')
        self.assertIsNone(stage.value.selected)
        c = next(c for c in stage.value.candidates if c.target is not None)
        self.assertTrue(c.saturation['blocks'])
        self.assertEqual(c.reagent_mass_g, 0)
        self.assertAlmostEqual(amended_ph(c), 5.8, delta=0.001)
        self.assertFalse(c.joint_result['accepted'])
        self.assertFalse(c.joint_result['globalOptimalityProven'])
        self.assertEqual(c.recommendation['saltIds'], [s['id'] for s in c.recommendation['salts']])
        rows = {r['symbol']: r for r in c.recommendation['rows']}
        for missed in c.recommendation['unmetTargets']:
            self.assertEqual(missed['final'], rows[missed['symbol']]['final'])
            self.assertEqual(missed['deltaPct'], rows[missed['symbol']]['deltaPct'])

    def positive_case(self, config_change=None, controls_change=None, maxima=None, scale=1):
        pool = [next(p for p in load_library()['salts'] if p['formula'] == 'KNO3')]
        product = ACIDS[0]
        config = configuration(pool, product, **(controls_change or {}))
        config['solvent_mass_kg'] = 1000 * scale
        config.update(config_change or {})
        return plan_fertilizer_workflow(
            pool,
            {'K': 100},
            {'Na': 0.002 * 22.989769 * 1000},
            5.8,
            final_volume=VolumeLitres(1000 * scale),
            maximum_concentrations=maxima,
            equilibrium=RO
            | dict(water_totals={'Na+': 0.002, 'CO3-2': 0.002}, water_mass_kg=1000 * scale),
            ph_adjustment=dict(products=[product], maximum_reagent_volume_litres=5, joint=config),
        ).stages['ph_adjustment']

    # Catalogue v0.0: re-enable in PR 4 (G5)
    def test_positive_reagent_is_counted_once_and_quantity_units_agree(self):
        self.enterContext(historical_catalogue())
        stage = self.positive_case()
        c = stage.value.selected
        self.assertIsNotNone(c, stage)
        self.assertGreater(c.reagent_mass_g, 0)
        self.assertAlmostEqual(c.reagent_volume_litres * 1370, c.reagent_mass_g)
        self.assertAlmostEqual(c.target.ph, 5.8, delta=0.001)
        rows = {r['symbol']: r for r in c.recommendation['rows']}
        self.assertAlmostEqual(rows['K']['final'], 100, places=5)
        # One nitrate per potassium in KNO3, plus nitric-acid nitrogen.
        self.assertAlmostEqual(
            rows['N_NO3']['final'],
            100 * 14.0067 / 39.0983 + c.nutrient_contribution['N_NO3'],
            delta=0.01,
        )
        self.assertEqual(c.recommendation['limitViolations'], [])

    # Catalogue v0.0: re-enable in PR 4 (G5)
    def test_missing_solvent_and_mismatched_basis_do_not_select_a_candidate(self):
        self.enterContext(historical_catalogue())
        for change, expected in [
            ({'reagent_solvent_fractions': {}}, 'missing_field'),
            ({'solvent_mass_kg': 900}, 'inconsistent_basis'),
        ]:
            with self.subTest(change=change):
                stage = self.positive_case(change)
                self.assertEqual(stage.status, 'blocked')
                self.assertIsNone(stage.value.selected)
                self.assertEqual(stage.value.candidates[0].error_code, expected)

    # Catalogue v0.0: re-enable in PR 4 (G5)
    def test_exhaustion_and_hard_limits_cannot_be_accepted(self):
        self.enterContext(historical_catalogue())
        for changes in [
            dict(controls_change={'max_iterations': 1}),
            dict(maxima={'K': 50}),
            dict(config_change={'maximum_reagent_mass_g': {ACIDS[0]['id']: 0}}),
        ]:
            with self.subTest(changes=changes):
                stage = self.positive_case(**changes)
                self.assertEqual(stage.status, 'blocked')
                self.assertIsNone(stage.value.selected)

    # Catalogue v0.0: re-enable in PR 4 (G5)
    def test_proportional_volume_and_solvent_scale_actual_reagent_mass(self):
        self.enterContext(historical_catalogue())
        full = self.positive_case().value.selected
        half = self.positive_case(scale=0.5).value.selected
        self.assertIsNotNone(half)
        self.assertAlmostEqual(half.reagent_mass_g * 2, full.reagent_mass_g, places=8)
        self.assertAlmostEqual(
            half.reagent_volume_litres * 2, full.reagent_volume_litres, places=10
        )
        self.assertAlmostEqual(half.dose_molal, full.dose_molal, places=12)
        self.assertAlmostEqual(half.target.ph, full.target.ph, places=8)

    # Catalogue v0.0: re-enable in PR 4 (G5)
    def test_invalid_controls_and_starts_are_reported_without_fallback(self):
        self.enterContext(historical_catalogue())
        for change in [
            {'controls': []},
            {'controls': {ACIDS[0]['id']: []}},
            {'unexpected': 1},
            {'controls': {'unexpected': 1}},
            {'starting_points': []},
            {'starting_points': {ACIDS[0]['id']: {}}},
            {
                'starting_points': {
                    ACIDS[0]['id']: dict(fertilizer_doses={'unknown': 1}, reagent_dose=0)
                }
            },
        ]:
            with self.subTest(change=change):
                stage = self.positive_case(config_change=change)
                self.assertIsNone(stage.value.selected)
                self.assertEqual(stage.status, 'blocked')
                self.assertFalse(stage.value.candidates[0].joint_result['accepted'])

    # Catalogue v0.0: re-enable in PR 4 (G5)
    def test_per_reagent_controls_and_preferred_selection(self):
        self.enterContext(historical_catalogue())
        pool = [next(p for p in LIBRARY['salts'] if p['formula'] == 'KNO3')]
        products = [ACIDS[0], ACIDS[0] | {'id': 'second-grade'}]
        configs = {p['id']: configuration(pool, p) for p in products}
        config = dict(
            solvent_mass_kg=1000,
            controls={k: c['controls'] for k, c in configs.items()},
            reagent_solvent_fractions={p['id']: 0.4 for p in products},
            maximum_reagent_mass_g={p['id']: 6000 for p in products},
        )
        flow = plan_fertilizer_workflow(
            pool,
            {'K': 100},
            {'Na': 0.002 * 22.989769 * 1000},
            5.8,
            final_volume=VolumeLitres(1000),
            equilibrium=RO | dict(water_totals={'Na+': 0.002, 'CO3-2': 0.002}),
            ph_adjustment=dict(
                products=products,
                maximum_reagent_volume_litres=5,
                preferred_product_id='second-grade',
                joint=config,
            ),
        )
        plan = flow.stages['ph_adjustment'].value
        self.assertEqual(plan.selected_product_id, 'second-grade')
        self.assertEqual(len(plan.candidates), 2)
        for candidate in plan.candidates:
            self.assertIsNotNone(candidate.target)
            self.assertAlmostEqual(candidate.target.ph, 5.8, delta=0.001)

    # Catalogue v0.0: re-enable in PR 4 (G5)
    def test_fresh_charge_rejects_a_false_solver_certificate(self):
        self.enterContext(historical_catalogue())
        fake = dict(status='numerical_candidate', fertilizerDoses={}, reagentDose=0)
        with patch('flahax.joint_workflow.solve_joint_problem', return_value=fake):
            stage = self.positive_case()
        self.assertIsNone(stage.value.selected)
        self.assertEqual(stage.value.candidates[0].error_code, 'joint_verification_failed')

    # Catalogue v0.0: re-enable in PR 4 (G5)
    def test_fresh_public_ph_rejects_false_numerical_success(self):
        self.enterContext(historical_catalogue())
        from flahax.calculated_ph import calculate_equilibrium_ph
        from dataclasses import replace

        def wrong(*args, **kwargs):
            return replace(calculate_equilibrium_ph(*args, **kwargs), ph=7)

        with patch('flahax.joint_workflow.calculate_equilibrium_ph', wrong):
            stage = self.positive_case()
        self.assertEqual(stage.value.candidates[0].error_code, 'joint_verification_failed')
        self.assertIsNone(stage.value.selected)


if __name__ == '__main__':
    unittest.main()
