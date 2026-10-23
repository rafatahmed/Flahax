# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Tests for flahax.mix_results: the Tanks, Nutrients and Notes views agree with the sheet."""

import copy
import html
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

from flahax.grower_report import grams, millilitres, number
from flahax.grower_sheet import agronomist_rows, render_mix_sheet
from flahax.mix_cli import main
from flahax.mix_results import first_view, handle_results, results_lines
from flahax.terminal import glyphs
from tests.test_output_consistency import ANSWERS

UTF8 = glyphs('utf-8')
ANSI = re.compile(r'\x1b\[[0-9;?]*[A-Za-z]')


def screen(summary, view, width=100, height=60, scroll=0):
    lines = results_lines(summary, view, width, height, scroll, UTF8, '/tmp/out')
    return [ANSI.sub('', line) for line in lines]


def sheet_text(summary, depth):
    return ' '.join(
        html.unescape(re.sub(r'<[^>]+>', ' ', render_mix_sheet(summary, depth))).split()
    )


class ResultViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            answers = list(ANSWERS)
            with mock.patch.dict(os.environ, {'FLAHAX_HOME': str(Path(tmp) / 'home')}):
                main(
                    ['--output', str(Path(tmp) / 'out')],
                    ask=lambda prompt: answers.pop(0),
                    say=lambda *a: None,
                )
            cls.summary = json.loads((Path(tmp) / 'out' / 'summary.json').read_text('utf-8'))
        cls.blocked = copy.deepcopy(cls.summary)
        cls.blocked['status'] = 'blocked'
        cls.blocked['stages']['chemistry']['status'] = 'blocked'
        cls.blocked['warnings'].insert(0, 'chemistry: a phase forms; do not mix this recipe.')

    def test_tanks_match_sheet(self):
        tanks, sheet = '\n'.join(screen(self.summary, 0)), sheet_text(self.summary, 1)
        for tank in self.summary['tanks']['tanks']:
            self.assertIn(f'Tank {tank["name"]}', tanks)
            for product in tank['products']:
                self.assertIn(product['name'], tanks)
                self.assertIn(grams(product['gramsPerBatch']), tanks)
                self.assertIn(grams(product['gramsPerBatch']), sheet)
        acid = millilitres(self.summary['ph']['selected']['volume_ml_per_batch'])
        self.assertIn(f'{acid} mL', tanks)
        self.assertIn(f'{acid} mL', sheet)
        self.assertIn('no acid in this tank', tanks)

    def test_nutrients_match_sheet(self):
        nutrients, sheet = '\n'.join(screen(self.summary, 1)), sheet_text(self.summary, 2)
        self.assertIn('From water', nutrients)
        for row in agronomist_rows(self.summary):
            if row['target'] is None:
                continue
            for cell in (
                number(row['target'], 2),
                number(row['final'], 2),
                f"{row['diff_mg_l']:+.2f} ({row['diff_pct']:+.1f} %)",
            ):
                self.assertIn(cell, nutrients, row['nutrient'])
                self.assertIn(cell, sheet, row['nutrient'])
        mixed = f'{self.summary["ph"]["mixed_ph"]:.2f}'.rstrip('0').rstrip('.')
        self.assertIn(f'after fertilizers {mixed}', nutrients)

    def test_notes_once(self):
        notes = ' '.join(' '.join(line.strip(' -') for line in screen(self.summary, 2)).split())
        for warning in self.summary['warnings']:
            self.assertEqual(notes.count(' '.join(warning.split())), 1, warning[:60])

    def test_blocked_opens_notes(self):
        self.assertEqual(first_view(self.summary), 0)
        self.assertEqual(first_view(self.blocked), 2)
        self.assertIn('do not mix', '\n'.join(screen(self.blocked, 0)))
        notes = screen(self.blocked, 2)
        first = next(i for i, line in enumerate(notes) if 'a phase forms' in line)
        self.assertLess(
            first, next(i for i, line in enumerate(notes) if 'Hydroxylapatite' in line)
        )

    def test_long_product_name_keeps_its_weight(self):
        summary = copy.deepcopy(self.summary)
        product = summary['tanks']['tanks'][0]['products'][0]
        product['name'] = (
            'Compound NPK 20-20-20 plus trace elements, chelated, from data sheet 2025-03'
        )
        tanks = screen(summary, 0, 80, 60)
        row = next(line for line in tanks if 'Compound NPK' in line)
        self.assertIn(grams(product['gramsPerBatch']), row)
        self.assertLessEqual(len(row), 79)

    def test_base_reagent_is_not_called_acid(self):
        summary = copy.deepcopy(self.summary)
        summary['ph']['selected']['direction'] = 'base'
        tanks = '\n'.join(screen(summary, 0))
        self.assertIn('pH reagent', tanks)
        self.assertNotIn(' Acid ', tanks)

    def test_results_encode_on_a_latin1_console(self):
        for view in range(3):
            for line in results_lines(self.summary, view, 100, 40, 0, glyphs('latin-1'), 'out'):
                line.encode('latin-1')

    def test_results_keys(self):
        self.assertEqual(handle_results(2, 0, 'TAB'), (0, 0, False))
        self.assertEqual(handle_results(0, 0, 'SHIFT_TAB'), (2, 0, False))
        self.assertEqual(handle_results(1, 5, 'RIGHT'), (2, 0, False))
        self.assertEqual(handle_results(0, 0, 'UP'), (0, 0, False))
        self.assertEqual(handle_results(0, 0, 'DOWN'), (0, 1, False))
        self.assertTrue(handle_results(0, 0, 'q')[2])
        self.assertTrue(handle_results(0, 0, 'ESC')[2])

    def test_results_width_and_height(self):
        for view in range(3):
            lines = screen(self.summary, view, 80, 24)
            self.assertLessEqual(len(lines), 23)
            self.assertTrue(all(len(line) <= 79 for line in lines), view)
            self.assertIn('Tab Next view', lines[-1])
        self.assertEqual(
            screen(self.summary, 0, 79, 24), ['Enlarge the window to at least 80 x 24. Q quits.']
        )


if __name__ == '__main__':
    unittest.main()
