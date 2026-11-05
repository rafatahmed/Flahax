# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Bad input at every entry point gets a plain message and an exit code, never a traceback
(#117)."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from flahax.__main__ import main as flahax
from flahax.batch_cli import main as batch

TOMATO = ['--formula', 'Tomato (Howard Resh)']


def run(command, argv, stdin=''):
    out, err = io.StringIO(), io.StringIO()
    with (
        mock.patch('sys.argv', ['flahax', *argv]),
        mock.patch('sys.stdin', io.StringIO(stdin)),
        contextlib.redirect_stdout(out),
        contextlib.redirect_stderr(err),
    ):
        try:
            code = command(argv) if command is batch else command()
        except SystemExit as exc:
            code = exc.code
    return code, err.getvalue() + out.getvalue()


class EntryInputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        (self.dir / 'bad.json').write_text('{"bad json', encoding='utf-8')
        (self.dir / 'lots.json').write_text(
            json.dumps({'measured_ph': 7, 'mg_per_litre': {'Ca': 'lots'}}), encoding='utf-8'
        )

    def batch(self, *extra):
        return run(batch, [*TOMATO, '--water', 'ro', '--output', str(self.dir / 'out'), *extra])

    def test_numbers_are_checked_at_the_command_line(self):
        for option, value, said in (
            ('--ratio', '0', '--ratio must be above 0, not 0'),
            ('--volume', '-5', '--volume must be above 0'),
            ('--ph', '20', '--ph must be at least 0 and at most 14'),
            ('--ratio', 'abc', "--ratio 'abc' is not a number"),
            ('--max-reagent-litres', '0', '--max-reagent-litres must be above 0'),
        ):
            with self.subTest(option=option, value=value):
                code, text = self.batch(option, value)
                self.assertEqual(code, 2)
                self.assertIn(said, text)
                self.assertNotIn('Traceback', text)

    def test_files_are_named_with_the_line(self):
        code, text = run(
            batch,
            [*TOMATO, '--water', str(self.dir / 'bad.json'), '--output', str(self.dir / 'o')],
        )
        self.assertEqual(code, 1)
        self.assertIn('water file', text)
        self.assertRegex(text, r'bad\.json is not valid JSON: \w.* at line 1, column \d+')
        self.assertNotIn('at at', text)
        code, text = run(
            batch,
            [*TOMATO, '--water', str(self.dir / 'none.json'), '--output', str(self.dir / 'o')],
        )
        self.assertIn('none.json was not found', text)
        code, text = run(
            batch,
            [
                '--targets',
                str(self.dir / 'bad.json'),
                '--water',
                'ro',
                '--output',
                str(self.dir / 'o'),
            ],
        )
        self.assertIn('targets file', text)

    def test_water_values_and_acid_numbers_are_named(self):
        _, text = run(
            batch,
            [*TOMATO, '--water', str(self.dir / 'lots.json'), '--output', str(self.dir / 'o')],
        )
        self.assertIn("water value Ca = 'lots' is not a number of mg/L", text)
        _, text = self.batch('--acid', 'HNO3:abc:1.4')
        self.assertIn("the assay (mass fraction) 'abc' is not a number", text)

    def test_stdin_json_errors_give_the_position(self):
        code, text = run(flahax, ['workflow'], '{"bad json')
        self.assertEqual(code, 1)
        self.assertRegex(text, r'stdin is not valid JSON: \w.* at line 1, column \d+')
        code, text = run(flahax, [], '{bad')
        self.assertIn('Expected a JSON object on stdin: Expecting property name', text)

    def test_valid_input_returns_the_current_blocked_result(self):
        code, text = self.batch('--acid', 'HNO3:0.60:1.37:Nitric acid 60%')
        self.assertEqual(code, 3, text)
        self.assertIn(' - blocked', text)
        self.assertNotIn('mL Nitric acid 60%', text)
        summary = json.loads((self.dir / 'out/summary.json').read_text(encoding='utf-8'))
        self.assertEqual(summary['status'], 'blocked')
        self.assertIsNone(summary['ph']['selected'])
        self.assertTrue(any('precipitation risk' in note for note in summary['warnings']))


if __name__ == '__main__':
    unittest.main()
