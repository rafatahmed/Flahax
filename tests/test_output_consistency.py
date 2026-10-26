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
        with mock.patch.dict(os.environ, {'FLAHAX_HOME': str(Path(cls.tmp.name) / 'home')}):
            code = main(
                ['--output', str(out)],
                ask=lambda prompt: answers.pop(0),
                say=lambda *a: lines.append(' '.join(map(str, a))),
            )
        assert code == 0, lines
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

    def test_selected_reagent_quantity_reads_the_same_everywhere(self):
        selected = self.selected
        # Keep the original owner inputs: accuracy-first fitting now selects a base.
        self.assertEqual(selected['direction'], 'base')
        self.assertIsNone(selected['volume_ml_per_batch'])
        per_batch = grams(selected['mass_g_per_batch'])
        self.assertGreater(selected['mass_g_per_batch'], 0)
        for name, page in self.outputs().items():
            with self.subTest(output=name):
                self.assertIn(per_batch, page)
                self.assertIn(selected['product'], page)
                self.assertNotIn('None mL', page)

    def test_one_ph_after_fertilizers_the_weighed_recipe(self):
        mixed = number(self.summary['chemistry']['mixed_ph'], 2)
        self.assertEqual(number(self.summary['ph']['mixed_ph'], 2), mixed)
        self.assertNotEqual(
            mixed, number(self.summary['ph']['unadjusted_ph'], 2)
        )  # the case that hid the bug
        for d in (2, 3):
            self.assertIn(f'after fertilizers {mixed}', self.sheets[d])
        self.assertIn(f'mixed {mixed}', self.report)
        self.assertIn(f'from pH {mixed} to', self.report)

    def test_each_warning_once(self):
        for name, page in (('report', self.report), ('sheet 2', self.sheets[2])):
            for phrase in (
                'Hydroxylapatite does not form directly',
                'Iron supplied as iron(II) oxidizes',
            ):
                with self.subTest(output=name, phrase=phrase):
                    reasons = (
                        page.split('Why review')[-1]
                        if name.startswith('sheet')
                        else page.split('Recipe')[0]
                    )
                    self.assertEqual(reasons.count(phrase), 1, reasons)

    def test_report_formatting(self):
        self.assertNotIn('1:100.0', self.report)
        self.assertNotIn('ready / requires review / blocked', self.report)
        self.assertIn('review notes before mixing', self.report)


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
