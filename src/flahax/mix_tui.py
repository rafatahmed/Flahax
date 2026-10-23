# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The ``flahax mix`` full-screen wizard: widgets, the screen frame and the prompts.

Widgets and the frame are pure: ``handle`` turns (question, key) into the next question and
``frame`` turns the wizard state into the lines to draw. Only ``flahax.terminal`` touches the
console.
"""

from dataclasses import dataclass, field
import re
import sys
import threading

from . import __version__
from .batch_cli import read_json, run_batch
from .delivery_contracts import DeliveryError
from .mix_cli import (
    Prompts,
    find_session,
    interview,
    number_answer,
    options_for,
    output_folder,
    saved_line,
    summarize,
    write_sheets,
)
from .terminal import Terminal, TerminalUnavailable, glyphs

STEPS = ('Spec', 'Water', 'Formula', 'Fertilizers', 'Acid and pH')
MIN_WIDTH, MIN_HEIGHT, TWO_PANES = 80, 24, 100
PANE = 30
SMALL = 'Enlarge the window to at least 80 x 24. Q quits.'
SPINNER = '|/-\\'
ANSI = re.compile(r'\x1b\[[0-9;?]*[A-Za-z]')
STYLE = {
    'accent': '\x1b[1;96m',
    'ok': '\x1b[92m',
    'warn': '\x1b[93m',
    'error': '\x1b[91m',
    'dim': '',  # the terminal's normal colour: faint text vanished on some themes
    'selected': '\x1b[7m',
    None: '',
}
HELP = {
    'choice': '{up}{down} Move   Enter Choose   Esc Quit',
    'filter': '{up}{down} Move   Type to filter   Enter Choose   Esc Quit',
    'ticks': '{up}{down} Move   Space Tick   Type to filter   Enter Next   Esc Quit',
    'ticks-filtered': '{up}{down} Move   Tab Tick   Type to filter   Enter Next   Esc Quit',
    'field': 'Type   Backspace Edit   Enter Next   Esc Quit',
}


@dataclass
class Question:
    """One question on screen: its kind, the options or text, and the answer once done."""

    kind: str  # 'choice', 'filter', 'ticks' or 'field'
    prompt: str
    options: list = field(default_factory=list)
    selected: int = 0  # position in the visible options
    query: str = ''
    ticked: list = field(default_factory=list)
    text: str = ''
    hint: str = ''
    error: str = ''
    done: bool = False
    answer: object = None


@dataclass
class Wizard:
    """The wizard so far: the current step, the finished answers and the messages to show."""

    step: int = 1
    answers: list = field(default_factory=list)
    messages: list = field(default_factory=list)
    progress: str | None = None  # e.g. the lab values typed so far in this step


def visible(question):
    """Indices of the options shown: those containing the filter text, ignoring case."""
    if question.kind == 'choice' or not question.query:
        return list(range(len(question.options)))
    query = question.query.lower()
    return [i for i, option in enumerate(question.options) if query in option.lower()]


def handle(question, key, validate=None):
    """The question after one key; ENTER finishes it when the answer is acceptable."""
    if key is None or question.done:
        return question
    shown = visible(question)
    if question.kind == 'field':
        if key == 'ENTER':
            answer, error = validate(question.text) if validate else (question.text, None)
            if error is None:
                question.answer, question.done, question.error = answer, True, ''
            else:
                question.error = error
        elif key == 'BACKSPACE':
            question.text = question.text[:-1]
        elif key == 'CTRL_U':
            question.text = ''
        elif len(key) == 1 and key.isprintable():
            question.text += key
        return question
    if key in ('UP', 'DOWN'):
        step = -1 if key == 'UP' else 1
        question.selected = max(0, min(question.selected + step, len(shown) - 1))
    elif key == 'HOME':
        question.selected = 0
    elif key == 'END':
        question.selected = max(0, len(shown) - 1)
    elif question.kind == 'ticks' and (key == 'TAB' or (key == ' ' and not question.query)):
        if shown:
            index = shown[question.selected]
            if index in question.ticked:
                question.ticked.remove(index)
            else:
                question.ticked.append(index)
            question.error = ''
    elif key == 'ENTER':
        if question.kind == 'ticks':
            if question.ticked:
                question.answer, question.done = list(question.ticked), True
            else:
                question.error = 'Tick at least one with Space.'
        elif shown:
            question.answer, question.done = shown[question.selected], True
        else:
            question.error = 'Nothing matches; change the filter.'
    elif question.kind in ('filter', 'ticks') and key in ('BACKSPACE', 'CTRL_U'):
        question.query = question.query[:-1] if key == 'BACKSPACE' else ''
        question.selected, question.error = 0, ''
    elif question.kind in ('filter', 'ticks') and len(key) == 1 and key.isprintable():
        question.query += key
        question.selected, question.error = 0, ''
    return question


def help_for(question):
    """The key-help template for a question: in a filtered tick list Tab ticks, not Space."""
    if question.kind == 'ticks' and question.query:
        return HELP['ticks-filtered']
    return HELP[question.kind]


def cut(text, width, g):
    """``text`` shortened to ``width`` characters, ending with the ellipsis when cut."""
    if len(text) <= width:
        return text
    mark = g['ellipsis']
    return text[: max(0, width - len(mark))] + mark


def wrap(text, width, lines=3):
    """``text`` broken at spaces into at most ``lines`` lines (the last may still be long)."""
    words, out = text.split(), ['']
    for word in words:
        if out[-1] and len(out[-1]) + 1 + len(word) > width and len(out) < lines:
            out.append(word)
        else:
            out[-1] = f'{out[-1]} {word}' if out[-1] else word
    return out


def paint(segments, width, g):
    """One screen line from (text, style) segments, cut to ``width`` visible characters."""
    out, room = [], width
    for text, style in segments:
        if room <= 0:
            break
        piece = cut(text, room, g) if len(text) > room else text
        if len(text) > room:
            room = 0
        else:
            room -= len(piece)
        out.append(f'{STYLE[style]}{piece}\x1b[0m' if style else piece)
    return ''.join(out)


def steps_pane(wizard, g):
    """The left pane: "Your batch" with each finished answer, the current step and the rest."""
    rows = [[('Your batch', 'accent')]]
    for label, value in wizard.answers:
        rows.append([(f'{g["tick"]} {label}', 'ok')])
        rows.extend([[(f'  {line}', None)] for line in str(value).split('\n')])
    rows.append([(f'{g["here"]} {STEPS[wizard.step - 1]}', 'accent')])
    rows.extend([[(f'  {name}', 'dim')] for name in STEPS[wizard.step :]])
    return rows


def step_bar(wizard, g):
    """The one-column step bar: ticks for finished steps, the marker on the current one."""
    segments = [('  ', None)]
    for number, name in enumerate(STEPS, 1):
        if number < wizard.step:
            segments.append((f'{g["tick"]} {name}  ', 'ok'))
        elif number == wizard.step:
            segments.append((f'{g["here"]} {number} {name}  ', 'accent'))
        else:
            segments.append((f'{number} {name}  ', 'dim'))
    return segments


def question_rows(wizard, question, width, height, g):
    """The question area: messages, prompt, filter or field, options and the error line."""
    rows = []
    if wizard.progress:
        rows.extend([[(line, 'ok')] for line in wrap(wizard.progress, width)])
    for message in wizard.messages:
        rows.extend([[(line, 'warn')] for line in wrap(message.strip(), width)])
    if question is None:
        return rows
    prompt = f'{question.prompt} {question.hint}'.rstrip()
    rows.extend([[(line, 'accent')] for line in wrap(prompt, width)])
    if question.kind == 'field':
        rows.append([('> ', 'accent'), (question.text + '_', None)])
    if question.kind in ('filter', 'ticks'):
        rows.append([('Filter: ', 'dim'), (question.query + '_', 'warn')])
    shown = visible(question)
    tail = []
    if question.kind == 'ticks' and question.ticked:
        names = ', '.join(question.options[i] for i in question.ticked)
        tail.append([(f'{len(question.ticked)} ticked: {names}', 'dim')])
    if question.error:
        tail.append([(question.error.strip(), 'error')])
    room = max(1, height - len(rows) - len(tail))
    start = min(max(0, question.selected - room + 1), max(0, len(shown) - room))
    for position in range(start, min(len(shown), start + room)):
        index = shown[position]
        label = question.options[index]
        if question.kind == 'ticks':
            label = f'[{"x" if index in question.ticked else " "}] {label}'
        here = position == question.selected
        rows.append([(f'{g["here"] if here else " "} {label}', 'selected' if here else None)])
    return rows + tail


def frame(wizard, question, width, height, g):
    """The lines to draw for this wizard state in a ``width`` x ``height`` window."""
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        return [SMALL]
    usable = width - 1
    title = '  F L A H A X   /   MIX'
    lines = [
        paint([(title + __version__.rjust(usable - len(title)), 'accent')], usable, g),
        paint([('  ' + g['h'] * (usable - 4), 'accent')], usable, g),
    ]
    body_height = height - 1 - len(lines) - 1
    if width >= TWO_PANES:
        right_width = usable - PANE - 3
        left = steps_pane(wizard, g)
        right = question_rows(wizard, question, right_width - 2, body_height, g)
        for i in range(min(body_height, max(len(left), len(right)))):
            row = left[i] if i < len(left) else []
            text = ''.join(t for t, _ in row)
            padded = row + [(' ' * (PANE - len(text)), None)] if len(text) < PANE else row
            right_row = right[i] if i < len(right) else []
            lines.append(
                paint([('  ', None)], 2, g)
                + paint(padded, PANE, g)
                + paint([(f' {g["v"]} ', 'dim')], 3, g)
                + paint(right_row, right_width - 2, g)
            )
    else:
        lines.append(paint(step_bar(wizard, g), usable, g))
        lines.append('')
        for row in question_rows(wizard, question, usable - 2, body_height - 2, g):
            lines.append(paint([('  ', None)] + row, usable, g))
    lines = lines[: height - 2]
    lines += [''] * (height - 2 - len(lines))
    lines.append(
        paint(
            [('  ' + help_for(question).format(**g) if question else 'Esc Quit', 'dim')],
            usable,
            g,
        )
    )
    return lines


class TuiPrompts(Prompts):
    """The ``flahax mix`` questions on the full screen; the five steps call it like ``Prompts``.

    ``term`` reads keys and draws (``flahax.terminal.Terminal`` or a test double); ``g`` is the
    glyph set from ``flahax.terminal.glyphs``.
    """

    def __init__(self, term, g):
        # Not Prompts.__init__: it stores ask and say on the instance, hiding the methods below.
        self.term, self.g, self.wizard = term, g, Wizard()
        self.saved = False  # True once the answers are saved: quitting then only skips the sheets
        self._shown = None

    def current_frame(self, question=None):
        """The lines for the current state at the current window size."""
        width, height = self.term.size()
        return frame(self.wizard, question, width, height, self.g)

    def _draw(self, question):
        """Draw the current frame unless it is already on screen; returns its lines."""
        lines = self.current_frame(question)
        cursor = None
        if question is not None and question.kind == 'field' and lines != [SMALL]:
            mark = question.text + '_'
            for row, line in enumerate(lines, 1):
                visible = ANSI.sub('', line).rstrip()
                if visible.endswith(mark):
                    cursor = (row, len(visible))
        if (lines, cursor) != self._shown:
            self.term.draw(lines, cursor=cursor)
            self._shown = (lines, cursor)
        return lines

    def _confirm_quit(self, question):
        ask = (
            'Quit now? The sheets will not be written. Y/N'
            if self.saved
            else 'Quit without saving? Y/N'
        )
        while True:
            self.wizard.messages.append(ask)
            try:
                lines = self._draw(question)
            finally:
                self.wizard.messages.pop()
            key = self.term.read_key()
            if key is None:
                continue
            if lines == [SMALL]:
                if key in ('q', 'Q'):
                    raise KeyboardInterrupt
                continue
            if key in ('y', 'Y'):
                raise KeyboardInterrupt
            return

    def _run(self, question, validate=None):
        while True:
            lines = self._draw(question)
            key = self.term.read_key()
            if lines == [SMALL]:
                if key in ('q', 'Q'):
                    raise KeyboardInterrupt
                continue
            if key == 'ESC':
                self._confirm_quit(question)
                continue
            question = handle(question, key, validate)
            if question.done:
                self.wizard.messages.clear()
                return question.answer

    def say(self, *parts):
        """Show a message above the next question (kept until it is answered)."""
        text = ' '.join(str(part) for part in parts).strip()
        if text:
            self.wizard.messages = (self.wizard.messages + [text])[-6:]

    def ask(self, prompt):
        """A raw typed answer (empty allowed), as ``input`` would give it."""
        return self._run(Question('field', prompt.rstrip().rstrip(':')))

    def text(self, prompt, default=None):
        """A non-empty answer, or the default on Enter when there is one."""

        def check(text):
            if text.strip():
                return text.strip(), None
            if default is not None:
                return default, None
            return None, 'This one is needed.'

        hint = '' if default is None else f'[{default or "none"}]'
        return self._run(Question('field', prompt, hint=hint), check)

    def number(self, prompt, default=None, *, blank=False, low=0.0, high=None, positive=False):
        """A number within the limits; the message shows under the field until it is valid."""

        def check(text):
            return number_answer(text, default, blank=blank, low=low, high=high, positive=positive)

        hint = f'[{default:g}]' if default is not None else '(Enter if blank)' if blank else ''
        return self._run(Question('field', prompt, hint=hint), check)

    def choose(self, prompt, options, default=1):
        """0-based index of the chosen option; the default starts highlighted."""
        start = 0 if default is None else max(0, min(default - 1, len(options) - 1))
        return self._run(Question('choice', prompt or 'Choose', list(options), selected=start))

    def search(self, prompt, names):
        """A name chosen from a list that narrows as you type."""
        return names[self._run(Question('filter', prompt, list(names)))]

    def pick_many(self, prompt, names):
        """0-based indices ticked with Space, in the order ticked."""
        return self._run(Question('ticks', prompt, list(names)))

    def step(self, index, heading=None):
        """Move the step bar to step ``index``."""
        self.wizard.step, self.wizard.progress = index, None

    def progress(self, text):
        """Show ``text`` above the questions of this step until it changes (None hides it)."""
        self.wizard.progress = text

    def answered(self, label, value):
        """Add a finished step's short answer to "Your batch"."""
        self.wizard.answers.append((label, value))


def calculate(prompts, work):
    """Run ``work`` on a thread while a spinner shows; Esc asks to quit. Returns its result."""
    outcome = {}

    def run():
        try:
            outcome['value'] = work()
        except BaseException as exc:  # handed to the screen thread below
            outcome['error'] = exc

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    turn, ahead = 0, []
    while worker.is_alive():
        prompts.wizard.messages = [f'{SPINNER[turn % 4]} Calculating the recipe, pH and tanks']
        prompts._draw(None)
        turn += 1
        key = prompts.term.read_key()
        if key == 'ESC':
            prompts._confirm_quit(None)
        elif key is not None:
            ahead.append(key)  # typed while waiting: for the results screen
        worker.join(0.05)
    prompts.wizard.messages = []
    if 'error' in outcome:
        raise outcome['error']
    return outcome['value'], ahead


def show_results(term, g, summary, output, ahead=()):
    """The results screen until Q or Esc, then Y; ``ahead``: keys typed during the calculation."""
    from .mix_results import first_view, handle_results, results_lines  # imports this module

    view, scroll, shown, key, ahead = first_view(summary), 0, None, None, list(ahead)
    leave = f'Leave the results? The sheets are saved in {output}. Y/N'
    while True:
        width, height = term.size()
        lines = results_lines(summary, view, width, height, scroll, g, str(output))
        if lines == shown and key == 'DOWN':
            scroll -= 1  # already at the end
        term.draw(lines)
        shown, key = lines, ahead.pop(0) if ahead else term.read_key()
        if key is None:
            continue
        view, scroll, done = handle_results(view, scroll, key)
        while done:  # a stray Q or Esc must not close the screen: ask first
            width, height = term.size()
            term.draw(results_lines(summary, view, width, height, scroll, g, str(output), leave))
            answer = ahead.pop(0) if ahead else term.read_key()
            if answer in ('y', 'Y'):
                return
            done = answer is None
        shown = None


def run_tui(store, session_name, output_arg, term_factory=Terminal, encoding=None):
    """``flahax mix`` on the full screen; returns the exit code and the lines to print after it.

    The exit code is None when the console cannot show the full screen: ask line by line.

    The answers are saved and the sheets written exactly as in the line mode. The terminal is
    restored before this returns, also after Ctrl+C or an error.
    """
    lines = []
    try:
        with term_factory() as term:
            g = glyphs(encoding or getattr(sys.stdout, 'encoding', None))
            prompts = TuiPrompts(term, g)
            if session_name:
                path = find_session(store, session_name)
                name, session = path.stem, read_json(path, 'session')
            else:
                name, session, pending = interview(prompts, store)
                for kind, item, data in pending:
                    store.save(kind, item, data)
                lines.append(saved_line(store, name))
            prompts.saved = True
            prompts.wizard.step = len(STEPS)
            summary, ahead = calculate(prompts, lambda: run_batch(options_for(store, session)))
            output = output_folder(output_arg, name)
            files = write_sheets(summary, session, output)
            summarize(summary, lines.append)  # the recipe stays in the terminal after the screen
            lines.append(f'Wrote {", ".join(files)} to {output}')
            try:
                show_results(term, g, summary, output, ahead)
            except KeyboardInterrupt:
                pass  # the sheets are written: Ctrl+C here is the same as Q
    except TerminalUnavailable:
        return None, []  # the caller asks line by line instead
    except (KeyboardInterrupt, EOFError):
        return 1, lines + ['Stopped.'] if lines else ['Stopped; nothing saved.']
    except (DeliveryError, ValueError, OSError, KeyError) as exc:
        return 1, lines + [f'flahax mix: {exc}']
    return (3 if summary['status'] == 'blocked' else 0), lines
