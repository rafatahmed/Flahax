# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Grade documents remain evidence, never rewritten as sampled
measurements.
"""

import copy
import unittest

from flahax import plan_ratio_recipe
from flahax.materials import make_grade, resolve_material
from flahax.ratio_element_uncertainty import perturb_sources, validate_element_factors
from flahax.ratio_products import _sources
from flahax.delivery_contracts import DeliveryError
from tests.test_ratio_analysis_uncertainty import request
from tests.test_ratio_element_uncertainty import elemental_options


def with_grade(req):
    row = req['products'][0]
    record = dict(
        grade_id='illustrative-mkp',
        identity_id='idn-monopotassium-phosphate',
        supplier='Illustrative supplier',
        product='Illustrative dilute MKP',
        composition='single',
        document=dict(
            supplier='Illustrative supplier',
            title='Synthetic test only',
            issued='2026-01-15',
            entered='2026-11-15',
        ),
        analysis={k: {'typical': v} for k, v in row['product']['elements'].items()},
    )
    name = 'Potassium Monobasic Phosphate'
    resolved = resolve_material(name, grade=make_grade(record))
    row['product'] = dict(resolved.record, grade=record)
    return req


class GradeUncertaintyTests(unittest.TestCase):
    def test_grade_and_flat_case_have_identical_fixed_chemistry(self):
        req = request()
        flat = plan_ratio_recipe(**dict(req, uncertainty=elemental_options(req)))
        with_grade(req)
        original = copy.deepcopy(req)
        result = plan_ratio_recipe(**dict(req, uncertainty=elemental_options(req)))
        self.assertEqual(req, original)
        c = result['uncertainty_verification']
        self.assertEqual(c['status'], 'passed')
        for phase, row in c['phase_maxima'].items():
            self.assertAlmostEqual(
                row['si'], flat['uncertainty_verification']['phase_maxima'][phase]['si']
            )
        self.assertEqual(
            result['ingredients'][0]['product']['grade'], req['products'][0]['product']['grade']
        )

    def test_sampled_grade_is_separate_hypothesis_with_identity(self):
        req = with_grade(request())
        sources = _sources(req['products'])
        for row in sources:
            row['grams'] = 1.0
        original = copy.deepcopy(sources)
        opts = elemental_options(req, 0.99)
        validate_element_factors(sources, opts['product_element_factors'])
        name = sources[0]['name']
        changed, _ = perturb_sources(sources, opts, {'assay.' + name + '.P': 0.99})
        self.assertEqual(sources, original)
        self.assertNotIn('grade', changed[0]['product'])
        self.assertEqual(changed[0]['product']['identityId'], 'idn-monopotassium-phosphate')
        self.assertAlmostEqual(
            changed[0]['product']['elements']['P'], original[0]['product']['elements']['P'] * 0.99
        )

    def test_blend_grade_remains_refused(self):
        req = with_grade(request())
        sources = _sources(req['products'])
        sources[0]['product']['grade']['composition'] = 'disclosed'
        with self.assertRaises(DeliveryError) as caught:
            validate_element_factors(sources, elemental_options(req)['product_element_factors'])
        self.assertEqual(caught.exception.code, 'unsupported_elemental_grade')

    def test_independent_grade_assays_recompute_chemistry(self):
        req = request()
        opts = elemental_options(req)
        opts['product_element_factors'][req['products'][0]['product']['name']]['P'] = [0.9, 1]
        flat = plan_ratio_recipe(**dict(req, uncertainty=opts))['uncertainty_verification']
        with_grade(req)
        opts = elemental_options(req)
        opts['product_element_factors'][req['products'][0]['product']['name']]['P'] = [0.9, 1]
        actual = plan_ratio_recipe(**dict(req, uncertainty=opts))['uncertainty_verification']
        self.assertEqual(actual['status'], flat['status'])
        self.assertEqual(actual['ratio_percent_ranges'], flat['ratio_percent_ranges'])
        for phase, row in actual['phase_maxima'].items():
            self.assertAlmostEqual(row['si'], flat['phase_maxima'][phase]['si'])
        self.assertGreater(actual['maximum_abs_assay_chemistry_difference_mg_l']['K'], 0)

    def test_adapter_must_preserve_nominal_inventory(self):
        req = with_grade(request())
        sources = _sources(req['products'])
        sources[0]['inventory']['components_moles_per_gram']['K+'] *= 0.9
        with self.assertRaises(DeliveryError) as caught:
            validate_element_factors(sources, elemental_options(req)['product_element_factors'])
        self.assertEqual(caught.exception.code, 'unsupported_elemental_grade')
