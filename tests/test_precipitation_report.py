# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Precipitation in a batch run (decisions G12-G14): reported by evidence, never a refusal."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from flahax.batch_cli import main as batch
from flahax.saturation_policy import FERROUS_IRON_ADVISORY

FORMULA = 'Lettuce 2 (Howard Resh)'
NITRIC = ('--acid', 'HNO3:0.6:1.37')


def run(*extra):
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder) / 'out'
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            batch(['--formula', FORMULA, '--water', 'ro', *NITRIC, *extra, '--output', str(out)])
        return json.loads((out / 'summary.json').read_text(encoding='utf-8'))


class PrecipitationReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.default = run()
        cls.neutral = run('--ph', '6.5')

    def test_slow_forming_phases_are_information_and_the_recipe_is_produced(self):
        chemistry = self.default['chemistry']
        information = {row['phase']: row for row in chemistry['information']}
        self.assertEqual(
            information['MnHPO4']['basis'],
            'unmeasured constant (Plummer et al. 1976 program data)',
        )
        self.assertEqual(
            information['Hydroxylapatite']['basis'],
            'database constant (minteq.v4), not individually reviewed',
        )
        self.assertEqual(chemistry['risk'], [])
        self.assertTrue(self.default['formulation']['salts'])

    def test_a_supersaturated_phase_no_longer_rejects_every_reagent(self):
        stage = self.default['stages']['ph_adjustment']
        self.assertNotEqual(stage['status'], 'blocked')
        self.assertNotEqual(stage['error_code'], 'no_acceptable_reagent')
        self.assertTrue(self.default['ph']['candidates'])
        self.assertNotIn('precipitation_risk', json.dumps(self.default['ph']['candidates']))

    def test_vivianite_is_information_with_the_iron_advisory(self):
        chemistry = self.default['chemistry']
        self.assertIn('Vivianite', [row['phase'] for row in chemistry['information']])
        self.assertIn(FERROUS_IRON_ADVISORY, chemistry['advisories'])
        self.assertIn(FERROUS_IRON_ADVISORY, self.default['warnings'])

    def test_brushite_above_saturation_labels_the_recipe_without_refusing_it(self):
        chemistry = self.neutral['chemistry']
        self.assertEqual([row['phase'] for row in chemistry['risk']], ['CaHPO4:2H2O'])
        self.assertAlmostEqual(chemistry['risk'][0]['si'], 0.16, places=2)
        self.assertIn(
            'The recipe carries a precipitation risk: CaHPO4:2H2O SI 0.16.',
            self.neutral['warnings'],
        )
        self.assertNotEqual(self.neutral['stages']['ph_adjustment']['status'], 'blocked')
        self.assertEqual(self.neutral['statuses']['phase'], 'requires_review')

    def test_a_recipe_with_only_information_phases_is_assessed(self):
        self.assertEqual(self.default['statuses']['phase'], 'assessed')


if __name__ == '__main__':
    unittest.main()
