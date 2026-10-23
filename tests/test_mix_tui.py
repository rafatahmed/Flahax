# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Tests for flahax.mix_tui: the wizard widgets, the frame and the full-screen prompts."""

import copy
import json
import os
from pathlib import Path
import re
import tempfile
import time
import unittest
from unittest import mock

from flahax.delivery_contracts import DeliveryError
from flahax.mix_cli import Prompts, interview, main, number_answer
from flahax.mix_store import Store
from flahax.mix_tui import Question, TuiPrompts, Wizard, frame, handle, run_tui, visible
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
        self.keys, self.sizes, self.frames, self.cursors = list(keys), list(sizes), [], []

    def read_key(self, timeout=0.1):
        if not self.keys:
            raise AssertionError('ran out of keys')
        return self.keys.pop(0)

    def size(self):
        return self.sizes.pop(0) if len(self.sizes) > 1 else self.sizes[0]

    def draw(self, lines, cursor=None):
        self.frames.append(plain(lines))
        self.cursors.append(cursor)

    def show_cursor(self, on):
        pass


class IdleTerm(FakeTerm):
    """A FakeTerm that waits (returns None) once its keys run out, as an idle keyboard does.

    The key 'CTRL_C' raises KeyboardInterrupt, as the terminal layer does for Ctrl+C.
    """

    def __init__(self, keys, **kwargs):
        super().__init__(keys, **kwargs)
        self.idle, self.exited = 0, False

    def read_key(self, timeout=0.1):
        if self.keys:
            key = self.keys.pop(0)
            if key == 'CTRL_C':
                raise KeyboardInterrupt
            return key
        self.idle += 1
        if self.idle > 6000:
            raise AssertionError('waited too long for a screen to finish')
        time.sleep(0.01)
        return None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.exited = True


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

    def test_no_faint_text(self):
        # Owner's trial 2026-10-23: faint text (SGR 2) vanished on a translucent grey theme,
        # hiding the key help, the inactive steps and the "Filter:" label.
        for width in (90, 120):
            for kind in ('choice', 'filter', 'ticks', 'field'):
                lines = frame(self.wizard(), Question(kind, 'Q', ['a', 'b']), width, 30, UTF8)
                self.assertFalse(any('\x1b[2m' in line for line in lines), (width, kind))

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


class UnavailableTerm(IdleTerm):
    def __enter__(self):
        from flahax.terminal import TerminalUnavailable

        raise TerminalUnavailable('cannot switch on ANSI output in this console')


class IssueTests(unittest.TestCase):
    def test_two_pane_message_that_fits_is_not_cut(self):  # 125
        message = 'A' * 30 + ' ' + 'B' * 31
        text = '\n'.join(
            plain(frame(Wizard(messages=[message]), Question('field', 'Q'), 100, 30, UTF8))
        )
        self.assertIn('B' * 31, text)
        self.assertNotIn('…', text)

    def test_long_prompt_wraps(self):  # 126
        prompt = 'Na (Enter = not measured, 0 = measured zero, <DL = below detection, e.g. <0.02)'
        for width in (80, 100):
            text = '\n'.join(plain(frame(Wizard(), Question('field', prompt), width, 30, UTF8)))
            self.assertIn('<0.02)', text)

    def test_quit_prompt_ignores_y_in_a_small_window(self):  # 131
        term = FakeTerm(
            ['ESC', 'y', 'n', 'a', 'ENTER'], sizes=[(100, 30), (70, 20), (100, 30), (100, 30)]
        )
        self.assertEqual(TuiPrompts(term, UTF8).text('Name'), 'a')

    def test_quit_prompt_redraws_on_resize(self):  # 131
        term = FakeTerm(['ESC', None, 'n', 'a', 'ENTER'], sizes=[(100, 30), (100, 30), (90, 30)])
        TuiPrompts(term, UTF8).text('Name')
        asked = [f for f in term.frames if 'Quit without saving? Y/N' in '\n'.join(f)]
        self.assertEqual(sorted(len(f[0]) for f in asked), [89, 99])

    def test_quit_prompt_after_saving(self):  # 129
        term = FakeTerm(['ESC', 'n', 'a', 'ENTER'])
        prompts = TuiPrompts(term, UTF8)
        prompts.saved = True
        prompts.text('Name')
        self.assertTrue(
            any(
                'Quit now? The sheets will not be written. Y/N' in '\n'.join(f)
                for f in term.frames
            )
        )

    def test_unchanged_screen_is_not_redrawn(self):  # 132
        term = FakeTerm([None, None, 'a', None, 'ENTER'])
        TuiPrompts(term, UTF8).text('Name')
        self.assertEqual(len(term.frames), 2)

    def test_cursor_shows_in_a_text_field(self):  # 132
        term = FakeTerm(['a', 'b', 'ENTER'])
        TuiPrompts(term, UTF8).text('Name')
        row, column = term.cursors[-1]
        self.assertTrue(term.frames[-1][row - 1].rstrip().endswith('ab_'))
        self.assertEqual(term.frames[-1][row - 1][column - 1], '_')
        choice = FakeTerm(['ENTER'])
        TuiPrompts(choice, UTF8).choose('Pick', ['a', 'b'])
        self.assertEqual(choice.cursors, [None])


class FallbackTests(unittest.TestCase):
    def test_run_tui_reports_an_unusable_console(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, lines = run_tui(Store(tmp), None, None, term_factory=lambda: UnavailableTerm([]))
        self.assertEqual((code, lines), (None, []))

    def test_main_falls_back_to_line_mode(self):
        lines = []
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch('flahax.mix_cli.use_tui', return_value=True),
            mock.patch('flahax.mix_tui.run_tui', return_value=(None, [])),
        ):
            code = main(
                [],
                ask=lambda prompt: (_ for _ in ()).throw(EOFError),
                say=lines.append,
                store=Store(tmp),
            )
        self.assertEqual(code, 1)
        self.assertIn('1/5 Specification', lines)
        self.assertEqual(lines[-1], 'Stopped; nothing saved.')

    def test_frame_encodes_on_a_latin1_console(self):
        g = glyphs('latin-1')
        wizard = Wizard(step=2, answers=[('Tanks', 'A 1 L; 25 \u00b0C')])
        for width in (90, 120):
            for kind in ('choice', 'filter', 'ticks', 'field'):
                for line in frame(wizard, Question(kind, 'Q', ['a']), width, 30, g):
                    line.encode('latin-1')


class RunTuiTests(unittest.TestCase):
    """The whole ``flahax mix`` run on the full screen, against the line mode's files."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        answers = list(ANSWERS)
        with mock.patch.dict(os.environ, {'FLAHAX_HOME': str(cls.root / 'plain-home')}):
            cls.plain_code = main(
                ['--output', str(cls.root / 'plain-out')],
                ask=lambda prompt: answers.pop(0),
                say=lambda *a: None,
            )
        cls.summary = json.loads((cls.root / 'plain-out' / 'summary.json').read_text('utf-8'))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_tui(self, keys, home, session=None, output='out'):
        term = IdleTerm(keys)
        code, lines = run_tui(
            Store(self.root / home), session, str(self.root / output), term_factory=lambda: term
        )
        return term, code, lines

    def test_run_tui_end_to_end(self):
        term, code, lines = self.run_tui(OWNER_KEYS + ['TAB', 'TAB', 'q'], 'tui-home')
        self.assertEqual((code, self.plain_code), (0, 0))
        self.assertTrue(term.exited)
        for name in ('batch-sheet.html', 'summary.json', 'report.html'):
            self.assertEqual(
                (self.root / 'out' / name).read_bytes(),
                (self.root / 'plain-out' / name).read_bytes(),
                name,
            )
        self.assertTrue(lines[0].startswith('Saved the answers as '), lines)
        self.assertTrue(lines[-1].startswith('Wrote batch-sheet.html, summary.json'), lines)
        shown = ['\n'.join(f) for f in term.frames]
        self.assertTrue(any('Calculating the recipe, pH and tanks' in f for f in shown))
        self.assertTrue(any('From water' in f for f in shown))

    def test_run_tui_saved_session(self):
        term, code, _ = self.run_tui(['q'], 'plain-home', 'tomato stage 1', 'again')
        self.assertEqual(code, 0)
        shown = ['\n'.join(f) for f in term.frames]
        self.assertFalse(any('Enter Choose' in f or 'Enter Next' in f for f in shown))
        self.assertIn('Tank A', shown[-1])

    def test_run_tui_restores_on_interrupt(self):
        term, code, lines = self.run_tui(entry('100') + ['CTRL_C'], 'stopped-home')
        self.assertTrue(term.exited)
        self.assertEqual((code, lines), (1, ['Stopped; nothing saved.']))
        self.assertFalse((self.root / 'stopped-home').exists())

    def test_run_tui_restores_on_error(self):
        with mock.patch('flahax.mix_tui.run_batch', side_effect=DeliveryError('x', 'boom')):
            term, code, lines = self.run_tui(['q'], 'plain-home', 'tomato stage 1', 'error')
        self.assertTrue(term.exited)
        self.assertEqual((code, lines[-1]), (1, 'flahax mix: boom'))

    def test_ctrl_c_on_results_keeps_the_result(self):  # 128
        # The batch is ready at once, so Ctrl+C arrives on the results screen.
        with mock.patch('flahax.mix_tui.calculate', return_value=(self.summary, [])):
            term, code, lines = self.run_tui(['CTRL_C'], 'plain-home', 'tomato stage 1', 'ctrl-c')
        self.assertTrue(term.exited)
        self.assertEqual(code, 0)
        self.assertTrue(lines[-1].startswith('Wrote batch-sheet.html'), lines)

    def test_run_tui_blocked_exit_code(self):
        blocked = copy.deepcopy(self.summary)
        blocked['status'] = 'blocked'
        blocked['stages']['chemistry']['status'] = 'blocked'
        with mock.patch('flahax.mix_tui.run_batch', return_value=blocked):
            term, code, _ = self.run_tui(['q'], 'plain-home', 'tomato stage 1', 'blocked')
        self.assertEqual(code, 3)
        self.assertIn('do not mix', term.frames[-1][2])
        self.assertTrue(any(line.lstrip().startswith('- ') for line in term.frames[-1]))


if __name__ == '__main__':
    unittest.main()
