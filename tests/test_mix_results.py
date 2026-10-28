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
from flahax.grower_sheet import agronomist_rows, readable, render_mix_sheet
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


def unbound_summary(actual):
    """Detach an explicitly synthetic mutable display fixture from calculation identity."""
    result = copy.deepcopy(actual)
    result.pop('export_identity', None)
    result.pop('calculation_identity', None)
    return result


def presentation_summary(actual):
    """Synthetic renderer state, never a chemistry result or mixing approval."""
    summary = copy.deepcopy(actual)
    summary.pop('export_identity', None)  # Synthetic presentation, no calculation claim.
    summary.pop('calculation_identity', None)
    summary['status'] = 'requires_review'
    for tank in summary['tanks']['tanks']:
        for key in ('prepared_litres', 'capacity_litres'):
            summary['volumes'][key].setdefault(tank['name'], summary['volumes'][key]['A'])
    summary['ph']['selected'] = dict(
        direction='acid',
        product='Synthetic rendering reagent',
        formula='HNO3',
        volume_ml_per_batch=123.0,
    )
    return summary


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
        cls.blocked = unbound_summary(cls.summary)
        cls.blocked['status'] = 'blocked'
        cls.blocked['stages']['chemistry']['status'] = 'blocked'
        cls.blocked['warnings'].insert(0, 'chemistry: a phase forms; do not mix this recipe.')

    def test_solubility_footer_never_claims_mixture_dissolution(self):
        for statuses, expected in [
            ([], 'not checked'),
            (['screening_only'], 'not checked'),
            (['inconclusive'], 'not checked'),
            (['ok'], 'mixture unqualified'),
            (['exceeds'], 'single-product limit'),
        ]:
            summary = unbound_summary(self.summary)
            summary['solubility'] = [dict(status=status) for status in statuses]
            text = ' '.join(screen(summary, 0, width=160, height=100))
            self.assertIn(expected, text)
            self.assertNotIn('all dissolve', text)

    def test_real_workflow_remains_phase_blocked_without_reagent(self):
        self.assertEqual(self.summary['status'], 'blocked')
        self.assertTrue(self.summary['chemistry']['phase_assessment']['blocks'])
        self.assertIsNone(self.summary['ph']['selected'])
        self.assertEqual(first_view(self.summary), 2)
        tanks = '\n'.join(screen(self.summary, 0))
        self.assertIn('not to be prepared', tanks)
        self.assertNotIn('sets the batch', tanks)
        self.assertNotIn('Synthetic rendering reagent', tanks)

    def test_tanks_match_sheet(self):
        summary = presentation_summary(self.summary)
        tanks, sheet = '\n'.join(screen(summary, 0)), sheet_text(summary, 1)
        for tank in summary['tanks']['tanks']:
            self.assertIn(f'Tank {tank["name"]}', tanks)
            for product in tank['products']:
                self.assertIn(product['name'], tanks)
                self.assertIn(grams(product['gramsPerBatch']), tanks)
                self.assertIn(grams(product['gramsPerBatch']), sheet)
        acid = millilitres(summary['ph']['selected']['volume_ml_per_batch'])
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
            shown = ' '.join(readable(warning).split())
            self.assertEqual(notes.count(shown), 1, warning[:60])

    def test_blocked_opens_notes(self):
        self.assertEqual(first_view(self.summary), 2)
        self.assertEqual(first_view(presentation_summary(self.summary)), 0)
        self.assertEqual(first_view(self.blocked), 2)
        self.assertIn('do not mix', '\n'.join(screen(self.blocked, 0)))
        notes = screen(self.blocked, 2)
        first = next(i for i, line in enumerate(notes) if 'a phase forms' in line)
        self.assertLess(
            first, next(i for i, line in enumerate(notes) if 'Hydroxylapatite' in line)
        )

    def test_long_product_name_keeps_its_weight(self):
        summary = unbound_summary(self.summary)
        product = summary['tanks']['tanks'][0]['products'][0]
        product['name'] = (
            'Compound NPK 20-20-20 plus trace elements, chelated, from data sheet 2025-03'
        )
        tanks = screen(summary, 0, 80, 60)
        row = next(line for line in tanks if 'Compound NPK' in line)
        self.assertIn(grams(product['gramsPerBatch']), row)
        self.assertLessEqual(len(row), 79)

    def test_base_reagent_is_not_called_acid(self):
        summary = presentation_summary(self.summary)
        summary['ph']['selected']['direction'] = 'base'
        tanks = '\n'.join(screen(summary, 0))
        self.assertIn('pH reagent', tanks)
        # Product names such as Boric Acid are legitimate; check the reagent heading.
        self.assertNotRegex(tanks, r'\u250c[^\n]* Acid ')

    def test_results_encode_on_a_latin1_console(self):
        for view in range(3):
            for line in results_lines(self.summary, view, 100, 40, 0, glyphs('latin-1'), 'out'):
                line.encode('latin-1')

    def test_no_ph_path_no_ph_line(self):  # 130
        summary = unbound_summary(self.summary)
        summary['chemistry'] = None
        summary['ph'] = None
        self.assertFalse(any(line.strip().startswith('pH:') for line in screen(summary, 1)))

    def test_status_colour_follows_the_status(self):  # 132
        def status_line(summary):
            lines = results_lines(summary, 0, 100, 40, 0, UTF8, 'out')
            return lines[2]

        ready = presentation_summary(self.summary)
        ready['status'] = 'ready'
        self.assertIn('\x1b[92m', status_line(ready))
        self.assertIn('\x1b[91m', status_line(self.blocked))
        self.assertIn('\x1b[93m', status_line(presentation_summary(self.summary)))

    def test_no_faint_text(self):
        # The key help ("Q Quit") and the inactive tab names must stay readable (owner's trial).
        for view in range(3):
            lines = results_lines(self.summary, view, 100, 40, 0, UTF8, 'out')
            self.assertFalse(any('\x1b[2m' in line for line in lines), view)

    def test_results_message_replaces_the_sheets_line(self):  # 138
        lines = results_lines(self.summary, 0, 100, 40, 0, UTF8, 'out', message='Leave? Y/N')
        text = [ANSI.sub('', line) for line in lines]
        self.assertEqual(text[-2].strip(), 'Leave? Y/N')
        self.assertNotIn('Sheets: out', ' '.join(text))

    def test_rounding_noise_is_zero_and_columns_stay_apart(self):  # 140
        self.assertEqual(number(7.105e-15, 2), '0')
        self.assertEqual(number(-3e-12, 2), '0')
        summary = unbound_summary(self.summary)
        for row in summary['formulation']['rows']:
            if row['symbol'] == 'K':
                row['final'] = 0.0
            if row['symbol'] == 'Ca':
                row['final'] = row['target'] + 7.105e-15
        lines = screen(summary, 1, 80, 40)
        table = lines[next(i for i, row in enumerate(lines) if 'Nutrient' in row) + 1 :]
        table = table[: next(i for i, row in enumerate(table) if not row.strip())]
        self.assertFalse(any('e-1' in line for line in table))
        self.assertFalse(any(re.search(r'[0-9][-+][0-9]', line) for line in table), table)
        self.assertTrue(any(' -200.00 (-100.0 %)' in line for line in lines))

    def test_tank_cards_keep_their_border_at_80_columns(self):  # 141
        lines = screen(presentation_summary(self.summary), 0, 80, 60)
        cards = [line for line in lines if line.strip().startswith('│')]
        self.assertTrue(cards)
        self.assertTrue(all(line.rstrip().endswith('│') for line in cards), cards)
        self.assertFalse(any(line.rstrip().endswith('…') for line in lines), lines)
        joined = ' '.join(' '.join(line.replace('│', ' ') for line in lines).split())
        self.assertIn('sets the batch', joined)

    def test_notes_use_grower_words(self):  # 142
        summary = unbound_summary(self.summary)
        summary['warnings'] = [
            'None of the available products supplies N_NO3.',
            'ph_adjustment: targets missed: N_NO3 -65.5% (no_source), '
            'P -44.7% (conflicting_targets)',
            'formulation: targets missed by more than 1 %: N_NH4 -86.0 %',
        ]
        notes = ' '.join(' '.join(screen(summary, 2)).split())
        self.assertIn('None of the available products supplies NO3-N.', notes)
        self.assertIn(
            'pH adjustment: targets missed: NO3-N -65.5% (no product supplies it)', notes
        )
        self.assertIn('(conflicts with other targets)', notes)
        self.assertIn('Formulation: targets missed by more than 1 %: NH4-N -86.0 %', notes)
        sheet = sheet_text(summary, 2)
        self.assertIn('None of the available products supplies NO3-N.', sheet)
        self.assertNotIn('N_NO3', sheet.split('Nutrients')[0] + notes)

    def test_hidden_rows_are_announced(self):  # 146
        short = screen(self.summary, 0, 80, 24)
        self.assertTrue(any('more below' in line for line in short), short)
        self.assertFalse(any('more above' in line for line in short))
        scrolled = screen(self.summary, 0, 80, 24, scroll=3)
        self.assertTrue(any('more above' in line for line in scrolled), scrolled)
        tall = screen(self.summary, 0, 100, 60)
        self.assertFalse(any('more below' in line or 'more above' in line for line in tall))

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
