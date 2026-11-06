# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The EC range in a batch run and a requested EC compared with it (decisions G6-G9)."""

import contextlib
import io
import json
from pathlib import Path
import re
import tempfile
import unittest

from flahax import DeliveryError
from flahax.batch_cli import main as batch
from flahax.grower_report import ec_text, requested_ec_note
from flahax.irrigation_ec import QUALIFIER

RANGE = {'status': 'range', 'ec25_range_ms_cm': (1.5, 2.5)}
INSIDE = 'compatible with the estimated range; target attainment unverified'


class RequestedEcNoteTests(unittest.TestCase):
    def test_a_request_inside_the_range_is_compatible_and_unverified(self):
        for requested in (1.5, 2.0, 2.5):  # both ends are inside
            with self.subTest(requested=requested):
                self.assertEqual(requested_ec_note(requested, RANGE), INSIDE)

    def test_a_request_outside_the_range_names_its_distance(self):
        self.assertEqual(
            requested_ec_note(1.0, RANGE),
            'requested 1.00 mS/cm is 0.50 mS/cm from the estimated range',
        )
        self.assertEqual(
            requested_ec_note(3.25, RANGE),
            'requested 3.25 mS/cm is 0.75 mS/cm from the estimated range',
        )

    def test_without_a_request_or_a_range_there_is_no_note(self):
        self.assertIsNone(requested_ec_note(None, RANGE))
        self.assertIsNone(requested_ec_note(2.0, None))
        self.assertIsNone(requested_ec_note(2.0, {'status': 'not_supported'}))

    def test_the_model_note_is_always_the_qualifier(self):
        self.assertEqual(
            QUALIFIER,
            'Model: McCleskey et al. (2012); its reported accuracy (-0.7 ± 5 %) is for '
            'natural waters, not fertilizer solutions. Measure EC after mixing.',
        )

    def test_the_display_text_is_one_value_or_a_range_never_a_midpoint(self):
        self.assertEqual(ec_text(RANGE), '1.5–2.5')
        self.assertEqual(ec_text(RANGE, about=True), '1.5 to 2.5')
        estimate = {'status': 'estimated', 'ec25_range_ms_cm': (1.42, 1.42)}
        self.assertEqual(ec_text(estimate), '1.42')
        self.assertEqual(ec_text(estimate, about=True), 'about 1.42')
        self.assertIsNone(ec_text({'status': 'not_supported'}))
        self.assertIsNone(ec_text(None))


class BatchEcTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name) / 'out'
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            batch(
                [
                    '--formula',
                    'Lettuce 2 (Howard Resh)',
                    '--water',
                    'ro',
                    '--acid',
                    'HNO3:0.6:1.37',
                    '--ec',
                    '2.00',
                    '--output',
                    str(out),
                ]
            )
        cls.summary = json.loads((out / 'summary.json').read_text(encoding='utf-8'))
        cls.report = (out / 'report.html').read_text(encoding='utf-8')
        cls.sheet = (out / 'batch-sheet.html').read_text(encoding='utf-8')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_ec_is_a_range_not_a_refusal(self):
        ec = self.summary['ec']
        low, high = ec['ec25_range_ms_cm']
        self.assertEqual(ec['status'], 'range')
        self.assertLess(low, high)
        self.assertIsNone(ec['ec25_ms_cm'])
        self.assertNotEqual(ec['status'], 'not_supported')

    def test_the_report_and_sheet_show_the_range(self):
        low, high = self.summary['ec']['ec25_range_ms_cm']
        self.assertIn(f'{low:.2f}–{high:.2f} mS/cm', self.report)
        self.assertIn(f'{low:.2f} to {high:.2f}', self.sheet)

    def test_no_output_carries_a_midpoint(self):
        for name, text in (
            ('report', self.report),
            ('sheet', self.sheet),
            ('summary', json.dumps(self.summary)),
        ):
            with self.subTest(output=name):
                self.assertNotIn('midpoint', text.lower())

    def test_the_requested_ec_is_compared_and_the_model_note_always_shows(self):
        request = self.summary['requested_ec']
        self.assertEqual(request['requested_ms_cm'], 2.0)
        self.assertRegex(
            request['note'],
            re.escape(INSIDE)
            + r'|requested 2\.00 mS/cm is \d+\.\d\d mS/cm from the estimated range',
        )
        self.assertIn(request['note'], self.summary['warnings'])
        self.assertIn(QUALIFIER, self.summary['warnings'])

    def test_a_request_that_is_not_a_positive_number_is_refused(self):
        from flahax.grower_report import summarize_batch

        for bad in (0, -1.0, float('nan'), True, '2'):
            with self.subTest(bad=bad), self.assertRaises(DeliveryError) as raised:
                summarize_batch(None, [], title='t', water_label='w', requested_ec_ms_cm=bad)
            self.assertEqual(raised.exception.code, 'invalid_value')


if __name__ == '__main__':
    unittest.main()
