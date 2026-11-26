# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Totals, dissolved species and precipitated amounts are reported apart (contract Q12).

Meeting a nutrient target is a statement about totals. The result also lists the dissolved
species and any predicted precipitate, and says that meeting targets does not establish
that nutrients stay dissolved or available.
"""

import json
from pathlib import Path
import tempfile
import unittest

from flahax import render_report
from flahax.canonical_result import seal_summary
from flahax.batch_request import BatchOptions, run_batch

TARGETS = {'N_NO3': 140, 'Ca': 100, 'K': 150, 'P': 30, 'Mg': 40}


def summary(targets=TARGETS):
    with tempfile.TemporaryDirectory() as folder:
        target_file = Path(folder, 'targets.json')
        target_file.write_text(json.dumps(targets))
        water = Path(folder, 'water.json')
        water.write_text(json.dumps({'mg_per_litre': {'HCO3': 0}, 'measured_ph': 6.0}))
        return run_batch(
            BatchOptions(water=str(water), targets=str(target_file), volume=1000, ratio=100)
        )


class DissolvedReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = summary()
        cls.chemistry = cls.result['chemistry']

    def test_dissolved_species_are_listed_largest_first(self):
        species = self.chemistry['species_mol_per_kg']
        self.assertGreater(len(species), 5)
        values = list(species.values())
        self.assertTrue(all(v > 0 for v in values))
        self.assertEqual(values, sorted(values, reverse=True))

    def test_dissolved_calcium_cannot_exceed_the_calcium_supplied(self):
        supplied = 100 / 40.078 / 1000  # mol/kg for 100 mg/L Ca in 1 kg of water per litre
        self.assertLessEqual(self.chemistry['species_mol_per_kg']['Ca+2'], supplied * 1.001)

    def test_precipitated_amounts_are_reported_apart_from_species(self):
        self.assertIsInstance(self.chemistry['precipitated_mol_per_kg'], dict)
        self.assertFalse(
            set(self.chemistry['precipitated_mol_per_kg'])
            & set(self.chemistry['species_mol_per_kg'])
        )

    def test_the_result_says_meeting_targets_does_not_establish_dissolution(self):
        text = ' '.join(self.result['assumptions'])
        self.assertIn('does not establish that nutrients remain dissolved or available', text)
        self.assertIn('dissolved-target calculation is not supported', text)

    def test_the_report_lists_the_dissolved_species(self):
        html = render_report(self.result)
        self.assertIn('Dissolved species', html)
        self.assertIn('Ca+2', html)

    def test_a_predicted_precipitate_is_listed_in_the_report(self):
        from copy import deepcopy

        shown = deepcopy(self.result)
        shown['chemistry']['precipitated_mol_per_kg'] = {'Hydroxylapatite': 1.25e-4}
        html = render_report(seal_summary(shown))
        self.assertIn('Predicted precipitate', html)
        self.assertIn('Hydroxylapatite', html)
        self.assertIn('No precipitate is predicted', render_report(self.result))


if __name__ == '__main__':
    unittest.main()
