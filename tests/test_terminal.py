# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Tests for flahax.terminal: key decoding, glyph fallback and when the TUI can run."""

import io
import unittest

from flahax.terminal import Terminal, decode_posix, decode_windows, glyphs, supported


class NotATerminal(io.StringIO):
    def isatty(self):
        return False


class KeyDecodingTests(unittest.TestCase):
    def test_decode_windows(self):
        for chars, key in {
            '\xe0H': 'UP',
            '\x00P': 'DOWN',
            '\xe0K': 'LEFT',
            '\xe0M': 'RIGHT',
            '\xe0G': 'HOME',
            '\xe0O': 'END',
            '\x00\x0f': 'SHIFT_TAB',
            '\r': 'ENTER',
            '\x1b': 'ESC',
            '\t': 'TAB',
            '\x08': 'BACKSPACE',
            '\x15': 'CTRL_U',
            ' ': ' ',
            'م': 'م',
        }.items():
            with self.subTest(chars=chars):
                self.assertEqual(decode_windows(chars), key)
        with self.assertRaises(KeyboardInterrupt):
            decode_windows('\x03')

    def test_decode_posix(self):
        self.assertEqual(decode_posix(b'\x1b[A'), ['UP'])
        self.assertEqual(decode_posix(b'\x1bOB'), ['DOWN'])
        self.assertEqual(decode_posix(b'\x1b[Z'), ['SHIFT_TAB'])
        self.assertEqual(decode_posix(b'\x1b'), ['ESC'])
        self.assertEqual(decode_posix(b'ab\r'), ['a', 'b', 'ENTER'])
        self.assertEqual(decode_posix(b'\x7f\x15\t'), ['BACKSPACE', 'CTRL_U', 'TAB'])
        self.assertEqual(decode_posix('م°µ'.encode()), ['م', '°', 'µ'])
        with self.assertRaises(KeyboardInterrupt):
            decode_posix(b'\x03')


class GlyphTests(unittest.TestCase):
    def test_glyphs(self):
        self.assertEqual(glyphs('utf-8')['tick'], '✓')
        self.assertEqual(glyphs('utf-8')['h'], '─')
        ascii_ = glyphs('cp437')
        self.assertEqual((ascii_['tick'], ascii_['h'], ascii_['ellipsis']), ('+', '-', '...'))
        self.assertEqual(glyphs(None)['tick'], '+')


class RecordingTerminal(Terminal):
    """A Terminal writing to a string, with the console mode switch recorded instead of made."""

    def __init__(self):
        super().__init__(stream=io.StringIO())
        self.modes = []

    def _console_on(self):
        self.modes.append('on')
        return lambda: self.modes.append('off')


class TerminalTests(unittest.TestCase):
    def test_terminal_restores_on_exception(self):
        term = RecordingTerminal()
        with self.assertRaises(KeyboardInterrupt):
            with term:
                term.draw(['hello'])
                raise KeyboardInterrupt
        written = term.stream.getvalue()
        self.assertTrue(written.startswith('\x1b[?1049h'))
        self.assertTrue(written.endswith('\x1b[0m\x1b[?25h\x1b[?1049l'))
        self.assertEqual(term.modes, ['on', 'off'])

    def test_draw_clears_each_line(self):
        term = RecordingTerminal()
        term.draw(['a', 'b'])
        self.assertEqual(term.stream.getvalue(), '\x1b[H\x1b[2Ka\r\n\x1b[2Kb\r\n\x1b[J')


class SupportedTests(unittest.TestCase):
    def test_supported_false_for_pipes(self):
        self.assertFalse(supported(NotATerminal(), NotATerminal()))


if __name__ == '__main__':
    unittest.main()
