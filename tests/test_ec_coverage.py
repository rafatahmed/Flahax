# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Incomplete conductivity, joint assay scenarios and uncertainty provenance."""

from dataclasses import asdict
import json
import unittest

from flahax.calculated_ec import estimate_manufacturer_ec
from flahax.delivery_contracts import DeliveryError
from flahax.irrigation_ec import (
    _end_material,
    calculate_ec_from_totals,
    calculate_irrigation_ec,
    calculate_irrigation_ec_band,
)
from tests import test_irrigation_ec as reference
from tests.catalogue_history import historical_catalogue


class CoverageTests(unittest.TestCase):
    def test_uncertainty_is_unknown_not_zero_for_complete_and_partial_cases(self):
        for totals, expected in (
            ({'K+': 0.01, 'Cl-': 0.01}, 'estimated'),
            ({'Mg+2': 0.004, 'SO4-2': 0.004}, 'partial'),
        ):
            result = calculate_ec_from_totals(
                totals, solution_id='coverage', ph_mode='calculated', phase_policy='dissolved'
            )
            self.assertEqual(result.status, expected)
            self.assertEqual(set(result.uncertainty_components), {'numerical', 'input', 'model'})
            self.assertTrue(
                all(c['bound_ms_cm'] is None for c in result.uncertainty_components.values())
            )
            self.assertIsNone(result.uncertainty_ms_cm)
            if expected == 'partial':
                self.assertIsNone(result.ec25_ms_cm)
                self.assertEqual(result.transport_numbers, {})
                self.assertGreater(result.known_species_subtotal_ms_cm, 0)
                self.assertTrue(result.missing_species)
            json.dumps(asdict(result), allow_nan=False)

    def test_manufacturer_unknown_product_has_no_zero_substitution(self):
        result = estimate_manufacturer_ec({'Unknown product': 0.1}, water_ec_ms_cm=0)
        self.assertEqual(result['status'], 'not_supported')
        self.assertEqual(result['missing_products'], ['Unknown product'])
        self.assertIsNone(result['ec_ms_cm'])
        self.assertIsNone(result['uncertainty_components']['model']['bound_ms_cm'])

    def test_joint_scenarios_preserve_opposing_assay_changes(self):
        helper = reference.BandChemistryTests()
        materials = helper._materials()
        names = list(materials)
        doses = {names[0]: 1.0, names[1]: 0.5}
        scenarios = {
            'opposing-a': {
                names[0]: _end_material(materials[names[0]], 'minimum'),
                names[1]: _end_material(materials[names[1]], 'maximum'),
            },
            'opposing-b': {
                names[0]: _end_material(materials[names[0]], 'maximum'),
                names[1]: _end_material(materials[names[1]], 'minimum'),
            },
        }
        result = calculate_irrigation_ec_band(
            doses, materials=materials, joint_scenarios=scenarios, **helper.PURE
        )
        values = []
        for name, joint in scenarios.items():
            point = result['scenarios'][name]
            direct = calculate_irrigation_ec(doses, materials=joint, **helper.PURE)
            self.assertEqual(point.ec25_ms_cm, direct.ec25_ms_cm)
            self.assertEqual(point.contributions_ms_cm, direct.contributions_ms_cm)
            self.assertEqual(point.audit['input_scenario'], name)
            self.assertEqual(
                point.uncertainty_components['input']['status'], 'joint_scenario_only'
            )
            self.assertIsNone(point.uncertainty_components['input']['bound_ms_cm'])
            values.append(point.ec25_ms_cm)
        self.assertNotEqual(*values)
        self.assertIn('not statistical bounds', result['note'])

    def test_scenario_failures_are_retained_and_incomplete_mappings_refused(self):
        helper = reference.BandChemistryTests()
        materials = helper._materials()
        doses = {'Potassium Nitrate': 4.4, 'Potassium Sulfate': 3.6}
        high = {name: _end_material(mat, 'maximum') for name, mat in materials.items()}
        result = calculate_irrigation_ec_band(
            doses, materials=materials, joint_scenarios={'high': high}, **helper.PURE
        )
        self.assertEqual(result['scenarios']['high'].reason, 'ionic_strength_outside_domain')
        self.assertIsNone(result['scenarios']['high'].ec25_ms_cm)
        for scenarios in (
            [],
            {'': high},
            {'incomplete': {}},
            {'bad': []},
            {'missing': dict.fromkeys(doses)},
        ):
            with self.subTest(scenarios=scenarios), self.assertRaises(DeliveryError) as caught:
                calculate_irrigation_ec_band(
                    doses, materials=materials, joint_scenarios=scenarios, **helper.PURE
                )
            self.assertEqual(caught.exception.code, 'invalid_ec_scenarios')

    # Catalogue v0.0: re-enable in PR 4 (G5)
    def test_grower_outputs_retain_qualifications(self):
        self.enterContext(historical_catalogue())
        from flahax.grower_report import summarize_batch, render_report, render_batch_sheet
        from tests.test_grower_outputs import workflow, PRODUCTS

        summary = summarize_batch(
            workflow('Tomato (Howard Resh)', products=[]),
            PRODUCTS,
            title='EC coverage',
            water_label='RO',
        )
        ec = summary['ec']
        self.assertIn('uncertainty_components', ec)
        self.assertIn('missing_species', ec)
        self.assertIn('audit', ec)
        json.dumps(summary, allow_nan=False)
        for render in (render_report, render_batch_sheet):
            html = render(summary)
            self.assertIn(ec['qualifier'], html)
            for warning in ec['warnings']:
                self.assertIn(warning, html)

    def test_measured_profile_error_does_not_become_input_uncertainty(self):
        from examples.ec_and_injection import inputs
        from flahax.conductivity import plan_ec_delivery

        stocks, profiles, _ = inputs()
        profiles[0]['validated_max_error_ms_cm'] = 0.02
        result = plan_ec_delivery(
            stocks, profiles=profiles, water_source_id='synthetic-water', water_ec_ms_cm=0.5
        ).predictions['irrigation']
        self.assertEqual(result.uncertainty_components['model']['bound_ms_cm'], 0.02)
        self.assertEqual(
            result.uncertainty_components['model']['status'], 'profile_declared_max_error'
        )
        self.assertIsNone(result.uncertainty_components['input']['bound_ms_cm'])
        self.assertIsNone(result.uncertainty_components['numerical']['bound_ms_cm'])

    def test_missing_reagent_quantity_does_not_hide_ec_qualifications(self):
        from flahax.grower_report import _reagent_amount

        self.assertEqual(
            _reagent_amount({'volume_ml_per_batch': None, 'mass_g_per_batch': None}),
            'Not available',
        )
        self.assertEqual(
            _reagent_amount({'volume_ml_per_batch': None, 'mass_g_per_batch': 5.0}), '5 g'
        )
