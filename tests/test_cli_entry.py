# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The bare ``flahax`` command: start screen, --version, program name, Ctrl+C (field test 2026-10-23)."""

import contextlib
import io
import unittest
from unittest import mock

import flahax
from flahax.__main__ import main


class Terminal(io.StringIO):
    def isatty(self):
        return True


def run(*argv, stdin=None):
    out, err = io.StringIO(), io.StringIO()
    with (
        mock.patch('sys.argv', ['flahax', *argv]),
        mock.patch('sys.stdin', stdin or Terminal()),
        contextlib.redirect_stdout(out),
        contextlib.redirect_stderr(err),
    ):
        try:
            code = main()
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class EntryTests(unittest.TestCase):
    def test_bare_flahax_at_a_terminal_shows_where_to_start(self):
        code, out, _ = run()
        self.assertEqual(code, 0)
        self.assertIn(f'FlahaX {flahax.__version__}', out)
        self.assertIn('flahax mix', out)

    def test_version_and_program_name(self):
        code, out, _ = run('--version')
        self.assertEqual((code, out.strip()), (0, f'FlahaX {flahax.__version__}'))
        _, out, _ = run('--help')
        self.assertTrue(out.startswith('usage: flahax '), out[:80])

    def test_ctrl_c_stops_without_a_traceback(self):
        with mock.patch('flahax.__main__._main', side_effect=KeyboardInterrupt):
            code, _, err = run('recommend')
        self.assertEqual((code, err.strip()), (130, 'Stopped.'))

    def test_piped_json_still_gives_a_recommendation(self):
        request = io.StringIO(
            '{"targets": {"K": 100}, "salts": %s}'
            % __import__('json').dumps(
                [s for s in flahax.load_library()['salts'] if s['name'] == 'Potassium Sulfate']
            )
        )
        code, out, _ = run(stdin=request)
        self.assertEqual(code, 0)
        self.assertIn('Potassium Sulfate', out)


if __name__ == '__main__':
    unittest.main()
