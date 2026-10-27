# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""One batch, every output: terminal, batch sheet (each depth), full report and summary must agree
(#107-#110).

The owner's session of 2026-10-23: RO water, Tomato Stage.1, 100 L tanks with a 10 L acid
container,
nitric 65 % (1.3 kg/L), pH 6, answered once and written at the full depth.
"""

import html
import copy
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

from flahax.grower_report import grams, number
from flahax.grower_sheet import render_mix_sheet
from flahax.mix_cli import main

ANSWERS = [
    '100',
    '100',
    '10',
    '100',
    '25',
    '1',
    '1',
    '',
    '1',
    'tomato',
    '2',
    '1',
    '1',
    '1',
    'HNO3',
    '65',
    '1.3',
    'HNO3 65%',
    '2',
    '6',
    '3',
    'tomato stage 1',
]


def text_of(page):
    return html.unescape(re.sub(r'<[^>]+>', ' ', page))


class OwnerSessionConsistency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        out, answers, lines = Path(cls.tmp.name) / 'out', list(ANSWERS), []
        from flahax import batch_cli

        actual_workflow = batch_cli.plan_fertilizer_workflow

        def capture(*args, **kwargs):
            cls.workflow = actual_workflow(*args, **kwargs)
            return cls.workflow

        with (
            mock.patch.dict(os.environ, {'FLAHAX_HOME': str(Path(cls.tmp.name) / 'home')}),
            mock.patch.object(batch_cli, 'plan_fertilizer_workflow', side_effect=capture),
        ):
            code = main(
                ['--output', str(out)],
                ask=lambda prompt: answers.pop(0),
                say=lambda *a: lines.append(' '.join(map(str, a))),
            )
        assert code == 3, lines
        cls.terminal = '\n'.join(lines)
        cls.summary = json.loads((out / 'summary.json').read_text(encoding='utf-8'))
        cls.report = text_of((out / 'report.html').read_text(encoding='utf-8'))
        cls.sheets = {d: text_of(render_mix_sheet(cls.summary, d)) for d in (1, 2, 3)}
        cls.selected = cls.summary['ph']['selected']

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def outputs(self):
        return {
            'terminal': self.terminal,
            'report': self.report,
            **{f'sheet {d}': s for d, s in self.sheets.items()},
        }

    def test_every_weight_reads_the_same_everywhere_and_never_zero(self):
        for tank in self.summary['tanks']['tanks']:
            for product in tank['products']:
                shown = grams(product['gramsPerBatch'])
                self.assertNotIn(shown, ('0 g', '0.0 g'))
                for name, page in self.outputs().items():
                    with self.subTest(product=product['name'], output=name):
                        self.assertIn(f'{product["name"]}', page)
                        self.assertIn(shown.replace(' g', ''), page)
        self.assertNotRegex(
            self.report, r'\(Monohydrate\)\s+[\d.e-]+\s+0\s'
        )  # no '0' weight in the report

    def test_blocked_workflow_has_no_selected_reagent(self):
        self.assertIsNone(self.selected)
        self.assertEqual(self.summary['status'], 'blocked')
        self.assertEqual(self.summary['chemistry']['state_basis'], 'unadjusted_recipe')
        rejected = self.summary['chemistry']['rejected_candidate_diagnostics']
        self.assertEqual(rejected['state_basis'], 'rejected_candidate_not_weighed')
        self.assertTrue(rejected['phase_assessment']['blocks'])
        self.assertFalse(self.summary['tanks']['mixture_approved'])
        self.assertFalse(self.summary['tanks']['waived'])
        self.assertEqual(self.summary['tanks']['required_tanks'], 3)
        for name, page in self.outputs().items():
            with self.subTest(output=name):
                self.assertIn('do not mix', page.lower())
                self.assertNotIn('None mL', page)

    def test_one_ph_after_fertilizers_the_weighed_recipe(self):
        mixed = number(self.summary['chemistry']['mixed_ph'], 2)
        self.assertEqual(number(self.summary['ph']['mixed_ph'], 2), mixed)
        # A rejected reagent leaves the unadjusted weighed recipe.
        self.assertEqual(mixed, number(self.summary['ph']['unadjusted_ph'], 2))
        for d in (2, 3):
            self.assertIn(f'after fertilizers {mixed}', self.sheets[d])
        self.assertIn(f'mixed {mixed}', self.report)

    def test_no_retired_phase_exemption_and_equipment_warning_once(self):
        for page in (self.report, self.sheets[2]):
            self.assertNotIn('Hydroxylapatite does not form directly', page)
            self.assertNotIn('with calcium their small doses are harmless', page)
            self.assertEqual(page.count('Stock assignment needs 3 tanks'), 1)

    def test_ec_uses_the_unadjusted_state_and_rejected_state_stays_separate(self):
        from flahax.irrigation_ec import calculate_ec_from_totals

        plan = self.workflow.stages['ph_adjustment'].value
        state = plan.unadjusted_state
        self.assertIsNotNone(state)
        self.assertEqual(state.ph, plan.unadjusted_ph)
        expected = calculate_ec_from_totals(
            state.totals,
            solution_id='batch',
            ph_mode='supplied',
            ph=state.ph,
            phase_policy='dissolved',
        )
        self.assertEqual(self.summary['ec'], json.loads(json.dumps(asdict(expected))))
        self.assertEqual(self.summary['chemistry']['ionic_strength'], state.ionic_strength)
        rejected = self.summary['chemistry']['rejected_candidate_diagnostics']
        self.assertNotEqual(rejected['mixed_ph'], state.ph)

    def test_legacy_missing_state_does_not_substitute_rejected_chemistry(self):
        from flahax import summarize_batch, load_library

        workflow = copy.copy(self.workflow)
        workflow.stages = dict(workflow.stages)
        stage = copy.copy(workflow.stages['ph_adjustment'])
        stage.value = replace(stage.value, unadjusted_state=None)
        workflow.stages['ph_adjustment'] = stage
        summary = summarize_batch(
            workflow, load_library()['salts'], title='Legacy', water_label='RO'
        )
        self.assertIsNone(summary['chemistry'])
        self.assertEqual(summary['ec']['status'], 'not_supported')
        self.assertEqual(summary['ec']['reason'], 'weighed_recipe_state_unavailable')
        self.assertNotEqual(summary['status'], 'ready')

    def test_report_formatting(self):
        self.assertNotIn('1:100.0', self.report)
        self.assertNotIn('ready / requires review / blocked', self.report)
        self.assertIn('do not mix', self.report.lower())


if __name__ == '__main__':
    unittest.main()


class ReagentQuantityRendering(unittest.TestCase):
    def test_liquid_volume_and_mass_have_distinct_units(self):
        from flahax.grower_report import _reagent_amount

        self.assertEqual(
            _reagent_amount(dict(volume_ml_per_batch=12.34, mass_g_per_batch=16.042)), '12.3 mL'
        )
        self.assertEqual(
            _reagent_amount(dict(volume_ml_per_batch=None, mass_g_per_batch=16.042)), '16 g'
        )


class SelectedStateIdentity(unittest.TestCase):
    def test_selected_recipe_uses_its_own_mixed_and_target_states(self):
        from flahax import load_library, plan_fertilizer_workflow, VolumeLitres, summarize_batch
        from flahax.irrigation_ec import calculate_ec_from_totals
        from tests.test_joint_workflow import configuration
        from tests.test_ph_adjustment import ACIDS, RO

        pool = [next(p for p in load_library()['salts'] if p['formula'] == 'KNO3')]
        reagent = ACIDS[0]
        workflow = plan_fertilizer_workflow(
            pool,
            {'K': 100},
            {'Na': 0.002 * 22.989769 * 1000},
            5.8,
            final_volume=VolumeLitres(1000),
            equilibrium=RO | dict(water_totals={'Na+': 0.002, 'CO3-2': 0.002}),
            ph_adjustment=dict(
                products=[reagent],
                maximum_reagent_volume_litres=5,
                joint=configuration(pool, reagent),
            ),
        )
        chosen = workflow.stages['ph_adjustment'].value.selected
        self.assertIsNotNone(chosen)
        summary = summarize_batch(workflow, pool, title='Selected', water_label='Synthetic')
        self.assertEqual(summary['chemistry']['state_basis'], 'selected_recipe')
        self.assertIsNone(summary['chemistry']['rejected_candidate_diagnostics'])
        self.assertEqual(summary['ph']['mixed_ph'], chosen.mixed.ph)
        self.assertEqual(summary['chemistry']['mixed_ph'], chosen.mixed.ph)
        self.assertEqual(summary['chemistry']['final_ph'], chosen.target.ph)
        expected = calculate_ec_from_totals(
            chosen.target.totals,
            solution_id='batch',
            ph_mode='supplied',
            ph=chosen.target.ph,
            phase_policy='dissolved',
        )
        self.assertEqual(summary['ec'], asdict(expected))
