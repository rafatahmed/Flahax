# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Tests for flahax.mix_tui: the wizard widgets, the frame and the full-screen prompts."""

import re
import unittest

from flahax.mix_cli import number_answer
from flahax.mix_tui import Question, Wizard, frame, handle, visible
from flahax.terminal import glyphs

UTF8 = glyphs('utf-8')
ANSI = re.compile(r'\x1b\[[0-9;?]*[A-Za-z]')


def plain(lines):
    """The frame as the reader sees it, without colour codes."""
    return [ANSI.sub('', line) for line in lines]


def press(question, keys, validate=None):
    for key in keys:
        question = handle(question, key, validate)
    return question


def typed(text):
    return list(text)


class WidgetTests(unittest.TestCase):
    def test_choice_keys(self):
        q = press(Question('choice', 'Pick', ['a', 'b', 'c']), ['DOWN'] * 3 + ['ENTER'])
        self.assertTrue(q.done)
        self.assertEqual(q.answer, 2)
        q = press(Question('choice', 'Pick', ['a', 'b', 'c']), ['UP'])
        self.assertEqual(q.selected, 0)

    def test_filter(self):
        options = ['Calcium Nitrate', 'Potassium Nitrate', 'MKP']
        q = press(Question('filter', 'Formula', options), typed('nitr'))
        self.assertEqual(visible(q), [0, 1])
        q = press(q, ['DOWN', 'ENTER'])
        self.assertEqual(q.answer, 1)
        q = press(Question('filter', 'Formula', options), typed('zz') + ['ENTER'])
        self.assertFalse(q.done)
        self.assertEqual(q.error, 'Nothing matches; change the filter.')
        q = press(q, ['BACKSPACE', 'BACKSPACE', 'ENTER'])
        self.assertEqual(q.answer, 0)

    def test_ticks(self):
        q = press(Question('ticks', 'Have', ['a', 'b', 'c']), [' ', 'DOWN', ' ', 'ENTER'])
        self.assertEqual(q.answer, [0, 1])
        q = press(Question('ticks', 'Have', ['a', 'b', 'c']), ['DOWN', ' ', 'UP', ' ', 'ENTER'])
        self.assertEqual(q.answer, [1, 0])
        q = press(Question('ticks', 'Have', ['a', 'b']), ['ENTER'])
        self.assertFalse(q.done)
        self.assertEqual(q.error, 'Tick at least one with Space.')

    def test_field_validation(self):
        def check(text):
            return number_answer(text, 25, high=60)

        q = press(Question('field', 'Temperature'), typed('70') + ['ENTER'], check)
        self.assertFalse(q.done)
        self.assertEqual(q.error, '  Enter a number from 0 up to 60.')
        self.assertEqual(q.text, '70')
        q = press(q, ['CTRL_U'] + typed('30') + ['ENTER'], check)
        self.assertEqual(q.answer, 30.0)
        q = press(Question('field', 'Temperature'), ['ENTER'], check)
        self.assertEqual(q.answer, 25)

    def test_unicode_typing(self):
        q = press(Question('field', 'Name'), ['م', '°', 'BACKSPACE', 'µ'])
        self.assertEqual(q.text, 'مµ')


class FrameTests(unittest.TestCase):
    def wizard(self):
        return Wizard(step=4, answers=[('Tanks', 'A 1000 L'), ('Water', 'RO'), ('Formula', 'T')])

    def question(self):
        return Question('ticks', 'Fertilizers you have', ['Calcium Nitrate', 'MKP'])

    def test_frame_two_panes_and_one_column(self):
        wide = '\n'.join(plain(frame(self.wizard(), self.question(), 120, 30, UTF8)))
        self.assertIn('Your batch', wide)
        self.assertIn('A 1000 L', wide)
        narrow = '\n'.join(plain(frame(self.wizard(), self.question(), 90, 30, UTF8)))
        self.assertNotIn('Your batch', narrow)
        self.assertIn('✓ Spec', narrow)
        self.assertIn('▸ 4 Fertilizers', narrow)

    def test_frame_fits_the_window(self):
        for width, height in ((80, 24), (120, 30)):
            lines = plain(frame(self.wizard(), self.question(), width, height, UTF8))
            self.assertLessEqual(len(lines), height - 1)
            self.assertTrue(all(len(line) <= width - 1 for line in lines))

    def test_frame_small_window(self):
        for size in ((79, 24), (80, 23)):
            self.assertEqual(
                plain(frame(self.wizard(), self.question(), *size, UTF8)),
                ['Enlarge the window to at least 80 x 24. Q quits.'],
            )

    def test_frame_cuts_long_lines(self):
        wizard = Wizard(step=1, messages=['x ' * 150])
        lines = plain(frame(wizard, Question('field', 'Name ' * 40), 80, 24, UTF8))
        self.assertTrue(all(len(line) <= 79 for line in lines))
        self.assertTrue(any(line.endswith('…') for line in lines))

    def test_frame_ascii_fallback(self):
        text = '\n'.join(frame(self.wizard(), self.question(), 90, 30, glyphs('cp437')))
        self.assertNotIn('─', text)
        self.assertNotIn('✓', text)
        self.assertIn('+ Spec', ANSI.sub('', text))


if __name__ == '__main__':
    unittest.main()
