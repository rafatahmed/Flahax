# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The precipitation screen (decisions G12-G14): risk by evidence, information otherwise.

A phase that forms readily marks the recipe with a precipitation risk. Every other
supersaturated phase is information with the basis of its constant. Nothing blocks.
"""

from types import SimpleNamespace
import unittest

from flahax.saturation_policy import (
    FERROUS_IRON_ADVISORY,
    RISK_PHASES,
    assess_saturation,
    describe,
    risk_warnings,
)

DATABASE_BASIS = 'database constant (minteq.v4), not individually reviewed'
MNHPO4_BASIS = 'unmeasured constant (Plummer et al. 1976 program data)'


def state(indices, precipitated=None, totals=None):
    return SimpleNamespace(
        saturation_indices=indices, precipitated=precipitated or {}, totals=totals or {}
    )


class PrecipitationScreenTests(unittest.TestCase):
    def test_the_phases_known_to_form_readily_are_the_risk_phases(self):
        self.assertEqual(RISK_PHASES, ('CaHPO4:2H2O', 'Gypsum', 'Calcite'))

    def test_a_readily_forming_phase_above_saturation_is_a_risk(self):
        result = assess_saturation(state({'CaHPO4:2H2O': 0.16, 'Calcite': 0.4, 'Gypsum': -0.5}))
        self.assertEqual(result['risk'], [('CaHPO4:2H2O', 0.16), ('Calcite', 0.4)])
        self.assertEqual(result['information'], [])

    def test_gypsum_forming_in_the_final_solution_is_a_risk_not_an_input(self):
        result = assess_saturation(state({'Gypsum': 0.05}))
        self.assertEqual(result['risk'], [('Gypsum', 0.05)])
        self.assertEqual(describe(result), ['precipitation risk: Gypsum SI 0.05'])

    def test_nothing_blocks_and_there_is_no_evidence_input(self):
        result = assess_saturation(state({'CaHPO4:2H2O': 2.0, 'MnHPO4': 3.1}))
        self.assertNotIn('blocks', result)
        self.assertNotIn('blocking', result)
        with self.assertRaises(TypeError):
            assess_saturation(state({}), evidence={})

    def test_slow_forming_phases_are_information_with_the_basis_of_their_constant(self):
        result = assess_saturation(
            state({'Hydroxylapatite': 4.0, 'MnHPO4': 3.3, 'Vivianite': 0.2, 'Goethite': 0.1})
        )
        self.assertEqual(result['risk'], [])
        self.assertEqual(
            result['information'],
            [
                ('Goethite', 0.1, DATABASE_BASIS),
                ('Hydroxylapatite', 4.0, DATABASE_BASIS),
                ('MnHPO4', 3.3, MNHPO4_BASIS),
                ('Vivianite', 0.2, DATABASE_BASIS),
            ],
        )

    def test_a_phase_that_is_not_supersaturated_is_not_reported(self):
        result = assess_saturation(
            state({'Gypsum': -0.5, 'Hydroxylapatite': 0.0, 'Struvite': float('-inf')})
        )
        self.assertEqual((result['risk'], result['information']), ([], []))

    def test_an_index_that_is_not_a_number_is_left_out(self):
        result = assess_saturation(
            state({'Calcite': float('nan'), 'Gypsum': 'x', 'Struvite': 0.3})
        )
        self.assertEqual(result['risk'], [])
        self.assertEqual([p for p, *_ in result['information']], ['Struvite'])

    def test_an_allocated_solid_is_a_risk_and_is_described(self):
        result = assess_saturation(state({}, precipitated={'Gypsum': 1e-4, 'Calcite': 0.0}))
        self.assertEqual(result['solids'], {'Gypsum': 1e-4})
        self.assertEqual(result['risk'], [('Gypsum', 0.0)])
        self.assertEqual(describe(result), ['precipitation risk: solid Gypsum allocated'])

    def test_an_invalid_solid_amount_is_left_out(self):
        for bad in (-1.0, float('nan'), True, 'x'):
            with self.subTest(bad=bad):
                self.assertEqual(
                    assess_saturation(state({}, precipitated={'Gypsum': bad}))['risk'], []
                )

    def test_a_risk_is_described_the_way_the_summary_label_reads(self):
        result = assess_saturation(state({'CaHPO4:2H2O': 0.1634}))
        self.assertEqual(describe(result), ['precipitation risk: CaHPO4:2H2O SI 0.16'])

    def test_each_risk_is_a_warning_sentence(self):
        result = assess_saturation(state({'CaHPO4:2H2O': 0.1634}, precipitated={'Gypsum': 1e-4}))
        self.assertEqual(
            risk_warnings(result),
            [
                'The recipe carries a precipitation risk: CaHPO4:2H2O SI 0.16.',
                'The recipe carries a precipitation risk: solid Gypsum allocated.',
            ],
        )

    def test_ferrous_iron_triggers_the_iron_advisory(self):
        self.assertEqual(
            FERROUS_IRON_ADVISORY,
            'Iron(II) is held at a fixed oxidation state; in an aerated tank it oxidizes.',
        )
        self.assertEqual(
            assess_saturation(state({'Vivianite': 0.2}, totals={'Fe+2': 1e-5}))['advisories'],
            [FERROUS_IRON_ADVISORY],
        )
        self.assertEqual(assess_saturation(state({}, totals={'Fe+3': 1e-5}))['advisories'], [])


if __name__ == '__main__':
    unittest.main()
