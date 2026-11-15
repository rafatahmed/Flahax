"""Above-label elemental assays are bounded inventories, not purity over 100%."""

import unittest

from flahax import plan_ratio_recipe
from flahax.delivery_contracts import DeliveryError
from flahax.ratio_analysis_uncertainty import validate_analysis_uncertainty
from tests.test_ratio_analysis_uncertainty import request, bounds
from tests.test_ratio_element_uncertainty import elemental_options
from tests.test_ratio_grade_uncertainty import with_grade


class UpperAssayBoundsTests(unittest.TestCase):
    def test_above_nominal_sodium_is_counted_and_can_fail_ceiling(self):
        req = request()
        nominal = plan_ratio_recipe(**req)
        req['maximum_concentrations']['Na'] = nominal['elemental_mg_l']['Na'] * 1.00001
        opts = elemental_options(req)
        name = req['products'][-1]['product']['name']
        opts['product_element_factors'][name]['Na'] = [1, 1.1]
        actual = plan_ratio_recipe(**dict(req, uncertainty=opts))
        check = actual['uncertainty_verification']
        self.assertIn('sodium_chloride_limits', check['failed_checks'])
        row = nominal['rounded_verification']['ingredients'][-1]
        expected_increment = row['grams'] * row['product']['elements']['Na'] * 10 * 0.1 / 10
        baseline = plan_ratio_recipe(**dict(req, uncertainty=elemental_options(req)))
        base_high = baseline['uncertainty_verification']['elemental_mg_l_ranges']['Na'][1]
        self.assertAlmostEqual(
            check['elemental_mg_l_ranges']['Na'][1], base_high + expected_increment
        )

    def test_two_sided_single_grade_bounds_are_accepted(self):
        req = with_grade(request())
        opts = elemental_options(req)
        name = req['products'][0]['product']['name']
        opts['product_element_factors'][name]['P'] = [0.995, 1.005]
        result = plan_ratio_recipe(**dict(req, uncertainty=opts))
        check = result['uncertainty_verification']
        self.assertEqual(check['status'], 'passed')
        self.assertGreater(
            check['ratio_percent_ranges'][4][1], check['ratio_percent_ranges'][4][0]
        )
        self.assertFalse(result['verified'])

    def test_all_high_assays_must_fit_declared_non_solvent_mass(self):
        req = request()
        opts = elemental_options(req)
        name = req['products'][0]['product']['name']
        opts['product_element_factors'][name] = {
            k: [1, 10] for k in req['products'][0]['product']['elements']
        }
        with self.assertRaises(DeliveryError) as caught:
            validate_analysis_uncertainty(opts, 10, req['products'], req['water'])
        self.assertEqual(caught.exception.code, 'invalid_elemental_mass_bounds')

    def test_whole_product_purity_mode_still_cannot_exceed_one(self):
        req = request()
        opts = bounds(req)
        name = req['products'][0]['product']['name']
        opts['product_assay_factors'][name] = [0.99, 1.01]
        with self.assertRaises(DeliveryError):
            validate_analysis_uncertainty(opts, 10, req['products'], req['water'])
