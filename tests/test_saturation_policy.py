# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""#78: positive saturation indices that block a plan, and those that need review only."""

import unittest
from types import SimpleNamespace

from flahax.saturation_policy import FERROUS_IRON_ADVISORY, REVIEW, assess_saturation, describe


def state(indices, precipitated=None, totals=None):
    return SimpleNamespace(
        saturation_indices=indices, precipitated=precipitated or {}, totals=totals or {}
    )


class SaturationPolicyTests(unittest.TestCase):
    def test_review_phases_carry_a_reason_and_sources(self):
        self.assertEqual(set(REVIEW), {'Hydroxylapatite', 'Goethite', 'MnHPO4', 'Vivianite'})
        for phase, (reason, sources) in REVIEW.items():
            self.assertTrue(reason and sources, phase)

    def test_phase_names_do_not_exempt_missing_evidence(self):
        result = assess_saturation(
            state({'Hydroxylapatite': 2.0, 'MnHPO4': 3.1, 'Goethite': 0.1, 'Gypsum': -0.5})
        )
        self.assertTrue(result['blocks'])
        self.assertEqual(
            [p for p, *_ in result['review']], ['Goethite', 'Hydroxylapatite', 'MnHPO4']
        )

    def test_readily_forming_phases_and_solids_still_block(self):
        for indices in (
            {'CaHPO4:2H2O': 0.2},
            {'CaHPO4': 0.1},
            {'Gypsum': 0.05},
            {'Struvite': 0.3},
            {'Ferrihydrite': 0.1},
            {'Calcite': 0.4},
        ):
            with self.subTest(indices):
                self.assertTrue(
                    assess_saturation(state(indices | {'Hydroxylapatite': 1.0}))['blocks']
                )
        solid = assess_saturation(state({'Hydroxylapatite': 1.0}, precipitated={'Gypsum': 1e-4}))
        self.assertTrue(solid['blocks'])
        self.assertIn('solid Gypsum allocated', describe(solid))

    def test_ferrous_iron_triggers_the_iron_advisory(self):
        self.assertEqual(
            assess_saturation(state({}, totals={'Fe+2': 1e-5}))['advisories'],
            [FERROUS_IRON_ADVISORY],
        )
        self.assertEqual(assess_saturation(state({}, totals={'Fe+3': 1e-5}))['advisories'], [])


if __name__ == '__main__':
    unittest.main()
