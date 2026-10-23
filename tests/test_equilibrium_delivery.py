# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Tests for flahax.equilibrium_delivery."""

import copy
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest

from flahax import (
    DeliveryError,
    VolumeLitres,
    final_solution_recipe,
    load_library,
    plan_equilibrium_delivery,
    compose_delivery_plan,
    transition_plan,
    plan_stocks,
    StockTank,
    InjectionRatio,
    TemperatureCelsius,
    plan_pump_command,
)
from flahax.aqueous_model import solve
from flahax.product_conversion import catalogue_dose_totals
from tests.test_ph_planning import record
from tests.test_pump_planning import calibration


def recipe_for(doses, water_mass=95.0, volume=100.0):
    library = {p['name']: p for p in load_library()['salts']}
    return final_solution_recipe(
        {
            'feasible': True,
            'salts': [
                {'id': library[n]['id'], 'name': n, 'gramsPerLitre': g * water_mass / volume}
                for n, g in doses.items()
            ],
        },
        VolumeLitres(volume),
    )


def arguments():
    doses = {'Potassium Carbonate': 0.01, 'Potassium Nitrate': 0.02}
    water = {'Na+': 0.002, 'Cl-': 0.002}
    totals = catalogue_dose_totals(doses)
    # Deliberately specified complete synthetic water, not an automatic adapter
    # correction. The adapter must reject an unbalanced supplied inventory.
    for _ in range(8):
        water['Cl-'] += solve(totals | water, 7.4).charge_balance
    return dict(
        recipe=recipe_for(doses),
        water_mass_kg=95.0,
        water_totals=water,
        water_analysis_id='synthetic-complete-water-v1',
        initial_ph=7.4,
        target_ph=6.0,
        reagent_channel_id='acid',
        reagent=record(
            'nitric',
            name='Nitric acid',
            kind='acid',
            chemicalFormula='HNO3',
            elements={'N_NO3': 13.8},
            densityKgPerL=1.4,
        ),
        maximum_reagent_volume=VolumeLitres(0.1),
        targets={'K': 12.72},
        maximum_nutrient_error_percent=1.0,
        maximum_concentrations={'Na': 50, 'Cl': 100, 'N_NO3': 20},
    )


class EquilibriumDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.args = arguments()
        cls.plan = plan_equilibrium_delivery(**cls.args)

    def test_units_assay_nitrate_and_recipe_rescoring(self):
        p = self.plan
        moles = p.equilibrium.nitric_acid_molal * 95
        self.assertAlmostEqual(p.reagent_mass.value, moles * 14.0067 / 0.138, places=12)
        self.assertAlmostEqual(p.reagent_volume_litres, p.reagent_mass.value / 1400, places=14)
        self.assertAlmostEqual(
            p.nutrient_contribution['N_NO3'].value, moles * 14.0067 * 1000 / 100, places=12
        )
        self.assertAlmostEqual(p.audit['productDosesGPerKgWater']['Potassium Carbonate'], 0.01)
        before = (
            next(row['final'] for row in p.rows if row['symbol'] == 'N_NO3')
            - p.nutrient_contribution['N_NO3'].value
        )
        self.assertAlmostEqual(before, 0.02 * 0.95 * 13.856 * 10, places=10)
        self.assertTrue(p.post_mix_measurement_required)
        self.assertEqual(len(p.audit['chemistrySha256']), 64)
        self.assertEqual(p.audit['waterTotalsMolal'], self.args['water_totals'])

    def test_residual_bicarbonate_is_reported(self):
        p = self.plan
        self.assertAlmostEqual(
            p.audit['residualBicarbonateMmolPerKg'],
            1000 * p.equilibrium.target.species.get('HCO3-', 0.0),
            places=12,
        )
        carbon = 1000 * self.args['water_totals'].get('CO3-2', 0.0)
        flagged = any('Residual bicarbonate' in w for w in p.warnings)
        self.assertEqual(flagged, carbon > 0.5 and p.audit['residualBicarbonateMmolPerKg'] < 0.5)

    def compose(self, plan=None):
        p = plan or self.plan
        limits = [
            record(
                s.salt_id + '-limit',
                productId=s.salt_id,
                maxGramsPerLitre=50,
                temperatureMinC=20,
                temperatureMaxC=30,
            )
            for s in p.recipe.salts
        ]
        stocks = plan_stocks(
            p.recipe,
            InjectionRatio(100),
            [StockTank('A', VolumeLitres(2))],
            [],
            limits,
            TemperatureCelsius(25),
        )
        cal = calibration()
        cal['validMinLitres'] = 1e-6
        cal['channelId'] = 'acid'
        command = plan_pump_command(
            cal,
            VolumeLitres(p.reagent_volume_litres),
            VolumeLitres(1),
            as_of=datetime(2026, 9, 27, tzinfo=timezone.utc),
        )
        return compose_delivery_plan(
            p.recipe, stocks, p, [command], {'modelVersion': 'package-test'}
        )

    def test_complete_recipe_to_reviewed_delivery_path(self):
        plan = self.compose()
        self.assertEqual(plan.audit_record['equilibrium'], self.plan.audit)
        self.assertTrue(plan.warnings)
        for state in ('validated', 'operator-approved'):
            plan = transition_plan(plan, state)
        self.assertEqual(plan.state, 'operator-approved')
        self.assertTrue(plan.commands[0].requires_operator_verification)

    def test_missing_bad_units_assay_and_domain_fail_closed(self):
        mutations = [
            {'water_mass_kg': None},
            {'water_mass_kg': 0},
            {'water_mass_kg': True},
            {'reagent_channel_id': ''},
            {'water_totals': None},
            {'water_analysis_id': ''},
            {'initial_ph': None},
            {'temperature_c': 30},
            {'maximum_reagent_volume': 0.1},
            {'targets': {}},
            {'maximum_nutrient_error_percent': float('nan')},
            {'water_totals': {'Na+': 0.2, 'Cl-': 0.2}},
            {'target_ph': 8.0},
            {'water_totals': {'Na+': 0.01, 'Cl-': 0.001}},
            {'targets': {'K': 0.0}, 'maximum_concentrations': {'K': 0.0}},
            {'targets': {'K': 1.0}},
            {'maximum_reagent_volume': VolumeLitres(1e-9)},
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(DeliveryError):
                plan_equilibrium_delivery(**(self.args | mutation))
        for change in (
            {'chemicalFormula': 'H2SO4'},
            {'densityKgPerL': 0},
            {'elements': {'N_NO3': 30}},
            {'elements': {'N_NH4': 13.8}},
            {'normalityMeqPerL': 100},
        ):
            with self.subTest(change=change), self.assertRaises(DeliveryError):
                plan_equilibrium_delivery(
                    **(self.args | {'reagent': self.args['reagent'] | change})
                )
        reagent = copy.deepcopy(self.args['reagent'])
        del reagent['densityKgPerL']
        with self.assertRaises(DeliveryError):
            plan_equilibrium_delivery(**(self.args | {'reagent': reagent}))

    def test_identity_and_composition_mismatch_rejected(self):
        recipe = self.args['recipe']
        bad = replace(
            recipe, salts=(replace(recipe.salts[0], name='Iron DTPA'),) + recipe.salts[1:]
        )
        with self.assertRaises(DeliveryError):
            plan_equilibrium_delivery(**(self.args | {'recipe': bad}))
        plan = self.compose()
        with self.assertRaises(DeliveryError):
            compose_delivery_plan(
                bad, replace(plan.stocks, recipe=bad), self.plan, plan.commands, plan.audit_record
            )
        with self.assertRaises(DeliveryError):
            compose_delivery_plan(
                plan.recipe,
                plan.stocks,
                self.plan,
                [replace(plan.commands[0], requested_volume=VolumeLitres(0.1))],
                plan.audit_record,
            )

    def test_user_grade_record_fails_closed_not_shipped_assay(self):
        # A grade's record has its own id, so the plan cannot mistake it for the shipped product.
        from flahax import make_grade, recommend, resolve_material

        grade = make_grade(
            {
                'grade_id': 'grd-kno3',
                'identity_id': 'idn-potassium-nitrate',
                'supplier': 'S',
                'product': 'KNO3',
                'document': {
                    'supplier': 'S',
                    'title': 'TDS',
                    'issued': '2026-01-01',
                    'entered': '2026-10-18',
                },
                'analysis': {'K': {'typical': 38.0}, 'N_NO3': {'typical': 13.0}},
            }
        )
        record = resolve_material('Potassium Nitrate', grade=grade).record
        fit = recommend([record], {'K': 38.0 * 0.19, 'N_NO3': 13.0 * 0.19})
        self.assertTrue(fit['feasible'])
        recipe = final_solution_recipe(fit, VolumeLitres(100))
        self.assertEqual(recipe.salts[0].name, 'Potassium Nitrate')
        with self.assertRaises(DeliveryError) as caught:
            plan_equilibrium_delivery(**(self.args | {'recipe': recipe}))
        self.assertEqual(caught.exception.code, 'product_chemistry_mismatch')

    def test_equal_target_requires_no_reagent(self):
        p = plan_equilibrium_delivery(**(self.args | {'target_ph': 7.4}))
        self.assertEqual(p.reagent_mass.value, 0)
        self.assertEqual(p.reagent_volume_litres, 0)

    def test_real_mixed_golden_dose_and_precipitation_guard(self):
        fixture = (
            Path(__file__).parent
            / 'fixtures/phreeqc/products/mixed_target_ph_nitric/expected.json'
        )
        data = json.loads(fixture.read_text())
        doses = data['product_doses_g_per_kgw']
        converted = catalogue_dose_totals(doses)
        args = self.args | {
            'recipe': recipe_for(doses),
            'maximum_concentrations': {'N_NO3': 100},
            'water_totals': {
                'Na+': data['runtime_totals']['Na+'] - converted.get('Na+', 0.0),
                'Cl-': data['runtime_totals']['Cl-'],
            },
            'targets': {'K': converted['K+'] * 39.0983 * 0.95 * 1000},
        }
        p = plan_equilibrium_delivery(**args)
        self.assertAlmostEqual(
            p.equilibrium.nitric_acid_molal,
            data['nitric_acid_molal'],
            delta=2e-6 + 0.03 * data['nitric_acid_molal'],
        )
        # Only MnHPO4 and hydroxylapatite are supersaturated at the target: review-class phases
        # (#78) travel as cited warnings instead of blocking. Validation still stops, now at the
        # unreviewed incidental nutrients.
        review = [w for w in p.warnings if w.startswith('Review: ')]
        self.assertEqual(sorted(w.split()[1] for w in review), ['Hydroxylapatite', 'MnHPO4'])
        self.assertFalse(any(w.startswith('Precipitation risk') for w in p.warnings))
        with self.assertRaises(DeliveryError) as caught:
            transition_plan(self.compose(p), 'validated')
        self.assertEqual(caught.exception.code, 'incidental_review_required')
