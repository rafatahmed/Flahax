# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Tests for flahax.mix_tui: the wizard widgets, the frame and the full-screen prompts."""

import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

from flahax.mix_cli import Prompts, interview, number_answer
from flahax.mix_store import Store
from flahax.mix_tui import Question, TuiPrompts, Wizard, frame, handle, visible
from tests.test_output_consistency import ANSWERS
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


def entry(text):
    return typed(text) + ['ENTER']


# The owner's session (tests/test_output_consistency.py ANSWERS) as keys on the wizard.
OWNER_KEYS = (
    entry('100')
    + entry('100')
    + entry('10')
    + entry('100')
    + entry('25')
    + ['ENTER', 'ENTER', 'ENTER', 'ENTER']  # fill the tanks; RO; no limits; a packaged formula
    + typed('tomato')
    + ['DOWN', 'ENTER']  # the second formula matching "tomato"
    + ['ENTER', 'ENTER', 'ENTER']  # whole catalogue; add nothing; a new acid
    + entry('HNO3')
    + entry('65')
    + entry('1.3')
    + entry('HNO3 65%')
    + ['ENTER']  # done with acids
    + entry('6')
    + ['DOWN', 'DOWN', 'ENTER']
    + entry('tomato stage 1')
)


class FakeTerm:
    """The terminal methods TuiPrompts uses, from a key script; it keeps every frame drawn."""

    def __init__(self, keys, sizes=((100, 30),)):
        self.keys, self.sizes, self.frames = list(keys), list(sizes), []

    def read_key(self, timeout=0.1):
        if not self.keys:
            raise AssertionError('ran out of keys')
        return self.keys.pop(0)

    def size(self):
        return self.sizes.pop(0) if len(self.sizes) > 1 else self.sizes[0]

    def draw(self, lines):
        self.frames.append(plain(lines))

    def show_cursor(self, on):
        pass


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


class TuiPromptsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patch = mock.patch.dict(os.environ, {'FLAHAX_HOME': self.tmp.name})
        patch.start()
        self.addCleanup(patch.stop)

    def test_interview_same_session_as_plain(self):
        answers = list(ANSWERS)
        plain_run = interview(
            Prompts(lambda prompt: answers.pop(0), lambda *a: None),
            Store(Path(self.tmp.name) / 'plain'),
        )
        term = FakeTerm(OWNER_KEYS)
        tui_run = interview(TuiPrompts(term, UTF8), Store(Path(self.tmp.name) / 'tui'))
        self.assertEqual(term.keys, [])
        self.assertEqual(tui_run[:2], plain_run[:2])
        self.assertEqual(tui_run[2], plain_run[2])

    def test_say_shows_until_next_answer(self):
        term = FakeTerm(entry('x'))
        p = TuiPrompts(term, UTF8)
        p.say('Added X as Y.')
        self.assertEqual(p.text('Name'), 'x')
        self.assertIn('Added X as Y.', '\n'.join(term.frames[0]))
        self.assertNotIn('Added X as Y.', '\n'.join(p.current_frame()))

    def test_escape_confirms(self):
        term = FakeTerm(['a', 'ESC', 'n', 'b', 'ENTER'])
        self.assertEqual(TuiPrompts(term, UTF8).text('Name'), 'ab')
        self.assertTrue(any('Quit without saving? Y/N' in '\n'.join(f) for f in term.frames))
        with self.assertRaises(KeyboardInterrupt):
            TuiPrompts(FakeTerm(['ESC', 'y']), UTF8).text('Name')

    def test_resize_mid_question(self):
        term = FakeTerm(['a', None, 'b', 'ENTER'], sizes=[(100, 30), (70, 20), (100, 30)])
        self.assertEqual(TuiPrompts(term, UTF8).text('Name'), 'ab')
        self.assertIn(['Enlarge the window to at least 80 x 24. Q quits.'], term.frames)

    def test_ask_gives_raw_text_for_lab_values(self):
        from flahax.mix_water import ask_ion

        p = TuiPrompts(FakeTerm(entry('<0.02') + ['ENTER']), UTF8)
        self.assertEqual(p.ask('Na: '), '<0.02')
        self.assertEqual(ask_ion(p, 'Cl'), (None, None))

    def test_text_needs_an_answer(self):
        term = FakeTerm(['ENTER', 'z', 'ENTER'])
        self.assertEqual(TuiPrompts(term, UTF8).text('Name'), 'z')
        self.assertTrue(any('This one is needed.' in '\n'.join(f) for f in term.frames))


if __name__ == '__main__':
    unittest.main()
