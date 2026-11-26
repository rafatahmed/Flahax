# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Directive D4 acceptance: equipment fixed at two tanks (contract Q19, Q20, Q14).

A recipe that needs two tanks and the same targets made to need three, both run with
two declared tanks. Find mode keeps the declared equipment, either finds a fitting
recipe or keeps the candidate with the unmet requirement named, and says that it
searched only the supplied alternatives. Analyze mode on the same inputs preserves the
quantities and reports the mismatch.
"""

import json
import tempfile
import unittest
from pathlib import Path

from flahax.batch_request import BatchOptions, run_batch
from tests.test_batch_equipment_search import NITRIC, alternative_file, targets_file

CALCIUM = 'cmbpfudif00lkq8z99slfmci3'
MAGNESIUM_NITRATE = 'cmbpfudhl00kyq8z9j8u2rr14'
PHOSPHATE = 'cmbpfudkn00naq8z9kd4qsr60'


def rule(rule_id, first, second):
    return dict(
        schemaVersion='0.1',
        id=rule_id,
        source='test',
        revision='1',
        recordedAt='2026-11-25T00:00:00Z',
        productIds=[first, second],
        constraint='separate',
        reason='test separation',
        temperatureMinC=0,
        temperatureMaxC=50,
    )


def doses(result):
    return sorted(
        (p['id'], p['gramsPerLitre']) for t in result['tanks']['tanks'] for p in t['products']
    )


class TwoTankEquipmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        folder = Path(cls.directory.name)
        rules = folder / 'rules.json'
        rules.write_text(
            json.dumps(
                [
                    rule('ca-mg', CALCIUM, MAGNESIUM_NITRATE),
                    rule('mg-p', MAGNESIUM_NITRATE, PHOSPHATE),
                ]
            )
        )
        cls.base = dict(
            water='ro',
            targets=targets_file(cls.directory.name),
            acid=[NITRIC],
            volume=1000,
            ratio=100,
            available_tanks=2,
            alternative_products=alternative_file(cls.directory.name),
        )
        cls.three_rules = str(rules)

    def run_case(self, **changes):
        return run_batch(BatchOptions(**(self.base | changes)))

    def test_a_recipe_needing_two_tanks_fits_two_and_runs_no_search(self):
        result = self.run_case(fit_equipment=True)
        self.assertEqual(result['tanks']['required_tanks'], 2)
        self.assertEqual(result['remedies']['evaluations'], 0)

    def test_a_recipe_needing_three_tanks_is_not_fitted_by_adding_a_tank(self):
        result = self.run_case(fit_equipment=True, rules=self.three_rules)
        self.assertEqual(result['tanks']['required_tanks'], 3)
        self.assertEqual(result['tanks']['available_tanks'], 2)  # never substituted
        remedies = result['remedies']
        self.assertEqual(remedies['mode'], 'find_suitable_doses')
        self.assertEqual(remedies['declared_equipment']['available_tanks'], 2)
        self.assertIn('equipment:fit', {r['id'] for r in remedies['requirements']})

    def test_the_unmet_equipment_requirement_stays_named_on_every_option(self):
        remedies = self.run_case(fit_equipment=True, rules=self.three_rules)['remedies']
        for option in remedies['options']:
            if option['status'].startswith('evaluated'):
                with self.subTest(option=option['id']):
                    self.assertIn(
                        'equipment:fit',
                        set(option['resolved_requirements'])
                        | {r['id'] for r in option['remaining_requirements']},
                    )

    def test_the_search_says_it_covered_only_the_supplied_alternatives(self):
        remedies = self.run_case(fit_equipment=True, rules=self.three_rules)['remedies']
        self.assertIn('Supplied alternatives only', remedies['scope'])
        self.assertIn('no global proof', remedies['scope'])
        self.assertIn(remedies['status'], {'declared_options_evaluated', 'search_incomplete'})

    def test_the_original_quantities_are_kept_when_nothing_fits(self):
        analysed = self.run_case(rules=self.three_rules)
        searched = self.run_case(fit_equipment=True, rules=self.three_rules)
        self.assertEqual(doses(searched), doses(analysed))

    def test_analyze_mode_preserves_the_quantities_and_reports_the_mismatch(self):
        analysed = self.run_case(rules=self.three_rules)
        self.assertEqual(analysed['remedies']['mode'], 'analyze_supplied_doses')
        self.assertEqual(analysed['remedies']['evaluations'], 0)
        self.assertEqual(analysed['status'], 'blocked')
        self.assertTrue(any('needs a third tank' in w for w in analysed['warnings']))


if __name__ == '__main__':
    unittest.main()
