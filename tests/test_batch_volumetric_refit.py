# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Rounded batch preparation, uncertainty and dose search regressions."""

import unittest
from types import SimpleNamespace

from flahax.batch_volumetric_stocks import verify_batch_stock_delivery
from flahax.delivery_contracts import DeliveryError


KNO3 = dict(id='KNO3', name='KNO3', formula='KNO3', elements={'K': 38.67, 'N_NO3': 13.85})
MGSO4 = dict(id='MgSO4', name='MgSO4', formula='MgSO4', elements={'Mg': 20.19, 'S': 26.64})


class RoundedBatchRefitTests(unittest.TestCase):
    def setUp(self):
        self.config = dict(
            stock=dict(
                basis='product_mass',
                carrier='demineralized_water',
                concentrations_g_l={'KNO3': 40},
                density_kg_l={'KNO3': [0.998, 1.1]},
                concentration_relative_error=0,
                dose_error_ml=0,
                dose_decimals=0,
            ),
            dry_mass_decimals=2,
            reagent_volume_decimals=1,
            nutrient_tolerance_percent=0.1,
            ph_tolerance=7,
        )
        self.reagent = dict(
            formula='KOH',
            product_record={'massFraction': 1},
            reagent_mass_g=0,
            reagent_volume_litres=None,
        )

    def verify(self, grams, targets, maxima=None, *, ph=7, **kwargs):
        chosen = SimpleNamespace(
            recommendation={
                'salts': [dict(name=name, gramsPerLitre=g) for name, g in grams.items()],
            },
            **self.reagent,
        )
        chemistry = dict(
            materials={},
            products={p['name']: p for p in (KNO3, MGSO4)},
            analytical_water_totals={},
            water_totals={},
            residual_charge_eq=0,
        )
        return verify_batch_stock_delivery(
            chosen, chemistry, {'water_mass_kg': 1}, 1, targets, ph, maxima, self.config, **kwargs
        )

    def test_refits_stock_and_dry_product_in_same_candidate(self):
        # Nearest solutions deliver .12 g KNO3 and .10 g MgSO4.
        # The only passing combination needs 3 mL at 37.5 g/L and .11 g dry.
        self.config['alternative_stock_concentrations_g_l'] = {'KNO3': [37.5]}
        result = self.verify(
            {'KNO3': 0.1125, 'MgSO4': 0.104},
            {'K': 0.1125 * 386.7, 'Mg': 0.11 * 201.9},
        )
        self.assertEqual(result['rounding_search']['status'], 'refitted')
        self.assertFalse(result['missed_targets'])
        self.assertEqual(result['stocks'][0]['concentration_g_l'], 37.5)
        self.assertEqual(result['stocks'][0]['dose_ml'], 3)
        self.assertEqual(result['dry_product_grams'], {'MgSO4': 0.11})

    def test_declared_bounds_include_dry_scale_and_liquid_reagent(self):
        self.reagent = dict(
            formula='HNO3',
            product_record={'massFraction': 0.1, 'densityKgPerL': 1},
            reagent_mass_g=0.3,
            reagent_volume_litres=0.0003,
        )
        self.config['uncertainty'] = dict(
            dry_product_error_g={'MgSO4': 0.001},
            dry_product_assay_relative_error={'MgSO4': 0.02},
            reagent_volume_error_ml=0.02,
            reagent_mass_fraction_bounds=(0.09, 0.11),
            reagent_density_kg_l_bounds=(0.99, 1.01),
        )
        # The reagent limit is tested against the upper bounded volume. Reducing
        # one reagent increment would miss the nitrate target.
        self.config['nutrient_tolerance_percent'] = 5
        result = self.verify(
            {'KNO3': 0.12, 'MgSO4': 0.1},
            {'K': 0.12 * 386.7, 'N_NO3': 23.3},
            reagent_maximum=0.31,
        )
        self.assertEqual(result['rounding_search']['status'], 'no_passing_candidate')
        self.assertAlmostEqual(result['reagent']['volume_ml_bounds'][1], 0.32)
        self.assertAlmostEqual(result['reagent']['active_grams_bounds'][1], 0.32 * 1.01 * 0.11)
        self.assertTrue(result['reagent_limit_exceeded'])
        self.assertAlmostEqual(
            result['nutrient_bounds_mg_l']['Mg'][0], 0.099 * 0.98 * 201.9, places=2
        )
        self.assertAlmostEqual(
            result['nutrient_bounds_mg_l']['Mg'][1], 0.101 * 1.02 * 201.9, places=2
        )

    def test_reserve_rejects_nominal_delivery_below_unreserved_ceiling(self):
        self.config['nutrient_ceiling_reserve'] = 0.1
        result = self.verify({'KNO3': 0.12}, {'K': 0.12 * 386.7}, {'K': 50})
        self.assertEqual(result['effective_maximum_concentrations']['K'], 45)
        self.assertLess(result['nutrient_mg_l']['K'], 50)
        self.assertEqual(result['limit_violations'], ['K'])
        self.assertEqual(result['rounding_search']['status'], 'no_passing_candidate')

    def test_declared_stock_strengths_and_reagent_assay_are_validated(self):
        self.config['alternative_stock_concentrations_g_l'] = {'KNO3': [1100]}
        with self.assertRaises(DeliveryError) as caught:
            self.verify({'KNO3': 0.12}, {})
        self.assertEqual(caught.exception.code, 'invalid_product_stock_dosing')
        self.config.pop('alternative_stock_concentrations_g_l')
        self.config['uncertainty'] = {'reagent_mass_fraction_bounds': [0.5, 0.9]}
        with self.assertRaises(DeliveryError) as caught:
            self.verify({'KNO3': 0.12}, {})
        self.assertEqual(caught.exception.code, 'invalid_stock_dosing')

    def test_reagent_refit_checks_ph_and_measurement_error(self):
        self.reagent['reagent_mass_g'] = 0.004
        self.config['ph_tolerance'] = 0.2
        result = self.verify({'KNO3': 0.12}, {}, ph=10.2)
        self.assertEqual(result['rounding_search']['status'], 'refitted')
        self.assertEqual(result['reagent']['grams'], 0.01)
        self.assertTrue(result['ph_within_tolerance'])

        self.config['uncertainty'] = {'reagent_mass_error_g': 0.02}
        result = self.verify({'KNO3': 0.12}, {}, ph=10.2)
        self.assertEqual(result['rounding_search']['status'], 'no_passing_candidate')
        self.assertFalse(result['ph_within_tolerance'])

    def test_search_ignores_alternatives_when_nearest_passes(self):
        self.config['alternative_stock_concentrations_g_l'] = {'KNO3': [37.5]}
        result = self.verify({'KNO3': 0.12}, {'K': 0.12 * 386.7})
        self.assertEqual(result['rounding_search'], dict(attempts=1, status='nearest_passed'))
        self.assertEqual(result['stocks'][0]['concentration_g_l'], 40)

    def test_invalid_optional_settings_and_uncertainty(self):
        for field, invalid in (
            ('uncertainty', []),
            ('uncertainty', {'dry_product_error_g': {'KNO3': 0.1}}),
            ('uncertainty', {'reagent_mass_error_g': -1}),
            ('uncertainty', {'reagent_mass_fraction_bounds': [1]}),
            ('alternative_stock_concentrations_g_l', {'not stocked': [10]}),
            ('alternative_stock_concentrations_g_l', {'KNO3': []}),
            ('nutrient_ceiling_reserve', 0.1),
        ):
            with self.subTest(field=field, invalid=invalid), self.assertRaises(DeliveryError):
                self.config[field] = invalid
                try:
                    self.verify({'KNO3': 0.12}, {})
                finally:
                    del self.config[field]

        self.reagent = dict(
            formula='HNO3',
            product_record={'massFraction': 0.1, 'densityKgPerL': 1},
            reagent_mass_g=0.3,
            reagent_volume_litres=0.0003,
        )
        self.config['uncertainty'] = {'reagent_density_kg_l_bounds': [0, 1.1]}
        with self.assertRaisesRegex(DeliveryError, 'density must be positive'):
            self.verify({'KNO3': 0.12}, {})
