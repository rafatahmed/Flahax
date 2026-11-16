# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Disclosed ingredients carry their assays and counterions together."""

import copy
import unittest

from flahax import plan_ratio_recipe
from flahax.delivery_contracts import DeliveryError
from flahax.engine import load_library
from flahax.materials import make_grade, resolve_material
from flahax.product_conversion import material_inventory
from tests.test_ratio_analysis_uncertainty import request
from tests.test_ratio_element_uncertainty import elemental_options


def blend_request():
    req = request()
    catalogue = {p['identityId']: p for p in load_library()['salts']}
    fractions = {'idn-potassium-nitrate': 0.49, 'idn-monopotassium-phosphate': 0.01}
    analysis = {
        k: {
            'typical': sum(
                f * material_inventory(catalogue[i])['nutrient_percent'].get(k, 0)
                for i, f in fractions.items()
            )
        }
        for k in ('K', 'N_NO3')
    }
    grade = dict(
        grade_id='synthetic-blend',
        supplier='Illustrative only',
        product='Nitrate/MKP',
        composition='disclosed',
        components=[dict(identity_id=i, mass_fraction=f) for i, f in fractions.items()],
        analysis=analysis,
        document=dict(
            supplier='Illustrative only',
            title='Synthetic composition',
            issued='2026-11-01',
            entered='2026-11-15',
        ),
    )
    material = resolve_material('Potassium Nitrate', grade=make_grade(grade))
    req['products'][4] = dict(
        product=dict(material.record, grade=grade), role='fertilizer', solvent_fraction=0.5
    )
    opts = elemental_options(req)
    opts['product_element_factors']['Potassium Nitrate'] = dict(
        source='blend_ingredients', mass_fraction_bounds={i: [f, f] for i, f in fractions.items()}
    )
    req['uncertainty'] = opts
    return req


class BlendUncertaintyTests(unittest.TestCase):
    def test_inferred_chelate_sodium_can_fail_limit_when_ingredient_increases(self):
        req = blend_request()
        product = req['products'][4]['product']
        grade = product['grade']
        grade['components'][0]['mass_fraction'] = 0.4899
        grade['components'].append(dict(identity_id='idn-sodium-iron-edta', mass_fraction=0.0001))
        catalogue = {p['identityId']: p for p in load_library()['salts']}
        for key in grade['analysis']:
            grade['analysis'][key]['typical'] = sum(
                p['mass_fraction']
                * material_inventory(catalogue[p['identity_id']])['nutrient_percent'].get(key, 0)
                for p in grade['components']
            )
        product['elements'] = resolve_material(
            'Potassium Nitrate', grade=make_grade(grade)
        ).record['elements']
        req['products'][4]['solvent_fraction'] = 0.499
        bounds = req['uncertainty']['product_element_factors']['Potassium Nitrate'][
            'mass_fraction_bounds'
        ]
        bounds.update(
            {'idn-potassium-nitrate': [0.4899, 0.4899], 'idn-sodium-iron-edta': [0.0001, 0.0002]}
        )
        nominal = plan_ratio_recipe(**dict(req, uncertainty=None))
        req['maximum_concentrations']['Na'] = (
            nominal['rounded_verification']['elemental_mg_l']['Na'] * 1.00001
        )
        c = plan_ratio_recipe(**req)['uncertainty_verification']
        self.assertIn('Na', c['blend_bound_sources']['Potassium Nitrate']['inferred_nutrients'])
        self.assertIn('sodium_chloride_limits', c['failed_checks'])
        self.assertGreater(
            c['elemental_mg_l_ranges']['Na'][1], req['maximum_concentrations']['Na']
        )

    def test_fixed_ingredients_reproduce_rounded_recipe_and_inferred_phosphate(self):
        req = blend_request()
        original = copy.deepcopy(req)
        nominal = plan_ratio_recipe(**dict(req, uncertainty=None))
        result = plan_ratio_recipe(**req)
        c = result['uncertainty_verification']
        self.assertEqual(req, original)
        self.assertEqual(c['status'], 'passed')
        self.assertAlmostEqual(
            c['counted_mmol_l_range'][0], nominal['rounded_verification']['counted_mmol_l']
        )
        for phase, row in c['phase_maxima'].items():
            self.assertAlmostEqual(
                row['si'], nominal['rounded_verification']['phase_maxima'][phase]['si']
            )

    def test_variable_ingredient_bounds_inferred_phosphate_without_label_zero(self):
        req = blend_request()
        entry = req['uncertainty']['product_element_factors']['Potassium Nitrate']
        entry['mass_fraction_bounds']['idn-monopotassium-phosphate'] = [0, 0.01]
        result = plan_ratio_recipe(**req)
        c = result['uncertainty_verification']
        self.assertGreater(c['ratio_percent_ranges'][4][1], c['ratio_percent_ranges'][4][0])
        self.assertIn('ingredient.Potassium Nitrate.idn-monopotassium-phosphate', c['dimensions'])
        self.assertNotIn('assay.Potassium Nitrate.P', c['dimensions'])
        self.assertIn('P', c['blend_bound_sources']['Potassium Nitrate']['inferred_nutrients'])

    def test_mass_excess_and_assay_mismatch_are_refused(self):
        for problem in ('mass', 'assay'):
            req = blend_request()
            if problem == 'mass':
                req['uncertainty']['product_element_factors']['Potassium Nitrate'][
                    'mass_fraction_bounds'
                ]['idn-monopotassium-phosphate'] = [0.01, 0.02]
            else:
                product = req['products'][4]['product']
                product['grade']['analysis']['K']['typical'] *= 0.99
                product['elements']['K'] *= 0.99
            with self.subTest(problem=problem), self.assertRaises(DeliveryError) as caught:
                plan_ratio_recipe(**req)
            self.assertEqual(
                caught.exception.code,
                'invalid_blend_mass_bounds' if problem == 'mass' else 'blend_assay_mismatch',
            )
