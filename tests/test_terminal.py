# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Tests for flahax.terminal: key decoding, glyph fallback and when the TUI can run."""

import io
import unittest

from flahax.terminal import (
    Terminal,
    TerminalUnavailable,
    decode_posix,
    decode_windows,
    glyphs,
    read_windows_key,
    supported,
)


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

    def test_windows_arrows_without_kbhit(self):
        # Field trial in Windows Terminal (2026-10-23): after the prefix, kbhit() is False
        # although the second code follows; reading it only when kbhit() was True typed letters.
        for first, second, key in (
            ('\xe0', 'H', 'UP'),
            ('\xe0', 'P', 'DOWN'),
            ('\x00', 'K', 'LEFT'),
        ):
            reads = iter([first, second])
            self.assertEqual(read_windows_key(lambda: next(reads)), key)

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

    def test_draw_places_the_cursor(self):  # 132
        term = RecordingTerminal()
        term.draw(['ab_'], cursor=(1, 3))
        self.assertTrue(term.stream.getvalue().endswith('\x1b[J\x1b[1;3H\x1b[?25h'))
        term = RecordingTerminal()
        term.draw(['ab'])
        self.assertTrue(term.stream.getvalue().endswith('\x1b[J\x1b[?25l'))

    def test_draw_clears_each_line(self):
        term = RecordingTerminal()
        term.draw(['a', 'b'])
        self.assertEqual(term.stream.getvalue(), '\x1b[H\x1b[2Ka\r\n\x1b[2Kb\r\n\x1b[J\x1b[?25l')


class Latin1Stream(io.StringIO):
    encoding = 'latin-1'


class FailingConsole(RecordingTerminal):
    def _console_on(self):
        raise TerminalUnavailable('cannot switch on ANSI output in this console')


class EncodingAndFallbackTests(unittest.TestCase):
    def test_draw_replaces_what_the_console_cannot_print(self):
        term = Terminal(stream=Latin1Stream())
        term.draw(['\u2191 \u0645 \u00b0'])
        self.assertIn('? ? \u00b0', term.stream.getvalue())

    def test_new_glyphs_fall_back(self):
        utf8, latin = glyphs('utf-8'), glyphs('latin-1')
        self.assertEqual((utf8['up'], utf8['down'], utf8['dot']), ('\u2191', '\u2193', '\u00b7'))
        self.assertEqual((latin['up'], latin['down'], latin['dot']), ('^', 'v', '-'))

    def test_console_failure_is_terminal_unavailable(self):
        term = FailingConsole()
        with self.assertRaises(TerminalUnavailable):
            with term:
                pass
        self.assertEqual(term.stream.getvalue(), '')

    def test_enter_restores_mode_when_the_first_write_fails(self):
        class BrokenStream(io.StringIO):
            def write(self, text):
                raise OSError('closed')

        term = RecordingTerminal()
        term.stream = BrokenStream()
        with self.assertRaises(OSError):
            term.__enter__()
        self.assertEqual(term.modes, ['on', 'off'])


class SupportedTests(unittest.TestCase):
    def test_supported_false_for_pipes(self):
        self.assertFalse(supported(NotATerminal(), NotATerminal()))


if __name__ == '__main__':
    unittest.main()
