# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The ``flahax mix`` results screen: the Tanks, Nutrients and Notes views of one batch.

Every value comes from the batch ``summary`` through the helpers the batch sheet uses, with
the sheet's rounding, so the screen and the sheet always agree.
"""

from . import __version__
from .grower_report import _reagent_line, grams, litres, millilitres, number
from .grower_sheet import LABEL, STATUS_WORDS, agronomist_rows, key_reasons, limited_by, readable
from .mix_tui import MIN_HEIGHT, MIN_WIDTH, SMALL, cut, paint, wrap

VIEWS = ('Tanks', 'Nutrients', 'Notes')
STATUS_STYLE = {'ready': 'ok', 'requires_review': 'warn', 'blocked': 'error'}
KEYS = 'Tab Next view   {up}{down} Scroll   Q Quit'
COLUMNS = (('Nutrient', 7), ('Target', 8), ('From water', 10), ('Required', 8))
COLUMNS += (('Achieved', 8), ('Final', 8), ('Diff', 18))


def first_view(summary):
    """The view the results open on: Notes for a blocked plan, else Tanks."""
    return 2 if summary['status'] == 'blocked' else 0


def handle_results(view, scroll, key):
    """(view, scroll, quit) after one key on the results screen."""
    if key in ('q', 'Q', 'ESC'):
        return view, scroll, True
    if key in ('TAB', 'RIGHT'):
        return (view + 1) % len(VIEWS), 0, False
    if key in ('SHIFT_TAB', 'LEFT'):
        return (view - 1) % len(VIEWS), 0, False
    if key == 'UP':
        return view, max(0, scroll - 1), False
    if key == 'DOWN':
        return view, scroll + 1, False
    return view, scroll, False


def _card(title, rows, width, g):
    inner = width - 4
    top = f'{g["tl"]}{g["h"]} {title} '
    out = [[(top + g['h'] * max(0, width - len(top) - 1) + g['tr'], 'accent')]]
    for row in rows:
        text = ''.join(t for t, _ in row)
        pad = ' ' * max(0, inner - len(text))
        out.append([(f'{g["v"]} ', 'accent')] + row + [(pad + f' {g["v"]}', 'accent')])
    out.append([(g['bl'] + g['h'] * (width - 2) + g['br'], 'accent')])
    return out


def _tank_rows(summary, width, g):
    volumes, blocked = summary['volumes'], summary['status'] == 'blocked'
    inner, rows = width - 4, []
    for tank in summary['tanks']['tanks']:
        name = tank['name']
        head = (
            'not to be prepared (do not mix)'
            if blocked
            else f'prepare {litres(volumes["prepared_litres"][name])} L in your '
            f'{litres(volumes["capacity_litres"][name])} L tank{limited_by(volumes)}'
        )
        body = [[(line, 'error' if blocked else None)] for line in wrap(head, inner, lines=4)]
        for product in tank['products']:
            weight = grams(product['gramsPerBatch'])
            label = cut(
                f'{"-" if blocked else "[ ]"} {product["name"]}', inner - len(weight) - 1, g
            )
            gap = max(1, inner - len(label) - len(weight))
            body.append([(label + ' ' * gap, None), (weight, 'accent')])
        if not tank['acid_allowed']:
            body.append([('no acid in this tank', 'dim')])
        rows += _card(f'Tank {name}', body, width, g)
    selected = summary['ph'] and summary['ph']['selected']
    if selected and not blocked:
        ph = summary['ph']
        body = [
            [
                (f'{millilitres(selected["volume_ml_per_batch"])} mL', 'accent'),
                (f' {selected["product"]}, added to water and made up to ', None),
                (f'{litres(volumes["prepared_litres"]["acid"])} L', 'accent'),
            ],
            [('Add acid to water, never water to acid.', 'warn')],
            [
                (
                    f'pH after fertilizers {number(ph["mixed_ph"], 2)}, after '
                    f'{selected["direction"]} {number(ph["target_ph"], 2)} (measure it)',
                    None,
                )
            ],
        ]
        rows += _card('Acid' if selected['direction'] == 'acid' else 'pH reagent', body, width, g)
    elif not blocked:
        rows += _card('pH reagent', [[(_reagent_line(summary), 'warn')]], width, g)
    checks = summary['solubility'] or []
    if any(c['status'] == 'exceeds' for c in checks):
        dissolves = 'a product exceeds its single-product limit (see Notes)'
    elif not checks or any(c['status'] != 'ok' for c in checks):
        dissolves = 'solubility not checked for every product'
    else:
        dissolves = f'single-product limits checked; mixture unqualified {g["tick"]}'
    ratio = summary['tanks']['injection_ratio']
    mode = 'prepared full' if volumes.get('mode') == 'fill' else 'one irrigation'
    temperature = summary['tanks'].get('temperature_c')
    footer = (
        f'1:{ratio:g} injection {g["dot"]} {mode}'
        + (f' {g["dot"]} {temperature:g} {g["deg"]}C' if temperature is not None else '')
        + f' {g["dot"]} {dissolves}'
    )
    rows.extend([[(line, 'dim')] for line in wrap(footer, width, lines=3)])
    return rows


def _nutrient_rows(summary):
    def cell(value):
        return '' if value is None else number(value, 2)

    rows = [
        [
            (
                ' '.join(
                    name.rjust(w) if i else name.ljust(w) for i, (name, w) in enumerate(COLUMNS)
                ),
                'accent',
            )
        ]
    ]
    for r in agronomist_rows(summary):
        diff = '' if r['target'] is None else f'{r["diff_mg_l"]:+.2f} ({r["diff_pct"]:+.1f} %)'
        cells = (
            LABEL.get(r['nutrient'], r['nutrient']),
            cell(r['target']),
            cell(r['water']),
            cell(r['required']),
            cell(r['achieved']),
            cell(r['final']),
            diff,
        )
        line = ' '.join(
            c.rjust(w) if i else c.ljust(w) for i, (c, (_, w)) in enumerate(zip(cells, COLUMNS))
        )
        style = 'dim' if r['target'] is None else 'warn' if abs(r['diff_pct']) > 1 else None
        rows.append([(line, style)])
    ph, chemistry = summary['ph'], summary.get('chemistry')
    path = [f'water {number(chemistry["water_ph"], 2)}'] if chemistry else []
    if ph and ph.get('mixed_ph') is not None:
        path.append(f'after fertilizers {number(ph["mixed_ph"], 2)}')
    if ph and ph['selected']:
        path.append(f'after {ph["selected"]["direction"]} {number(ph["target_ph"], 2)}')
    if path:
        rows += [[]] + [[('pH: ' + ', '.join(path) + ' (measure it)', None)]]
    return rows


def _note_rows(summary, width):
    blocking = key_reasons(summary) if summary['status'] == 'blocked' else []
    ordered = blocking + [w for w in summary['warnings'] if w not in blocking]
    rows = []
    for warning in ordered:
        style = 'error' if warning in blocking else None
        for i, line in enumerate(wrap(readable(warning), width - 4, lines=10**6)):
            rows.append([(('- ' if i == 0 else '  ') + line, style)])
    return rows or [[('No notes.', 'dim')]]


def results_lines(summary, view, width, height, scroll, g, output, message=None):
    """The lines to draw for one results view, scrolled by ``scroll`` rows.

    ``message`` (a question such as the leave confirmation) replaces the "Sheets:" line.
    """
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        return [SMALL]
    usable = width - 1
    title = f'  F L A H A X   /   MIX   {summary["title"]}'
    tabs = [('  ', None)]
    for i, name in enumerate(VIEWS):
        tabs.append((f' {name} ', 'selected' if i == view else 'dim'))
        tabs.append(('  ', None))
    status = STATUS_WORDS[summary['status']]
    used = sum(len(t) for t, _ in tabs)
    tabs.append((' ' * max(1, usable - used - len(status) - 2), None))
    tabs.append((status, STATUS_STYLE[summary['status']]))
    lines = [
        paint([(title + __version__.rjust(max(1, usable - len(title))), 'accent')], usable, g),
        paint([('  ' + g['h'] * (usable - 4), 'accent')], usable, g),
        paint(tabs, usable, g),
        '',
    ]
    card_width = min(usable - 2, 76)
    if view == 0:
        body = _tank_rows(summary, card_width, g)
    elif view == 1:
        body = _nutrient_rows(summary)
    else:
        body = _note_rows(summary, usable - 2)
    room = height - 1 - len(lines) - 2
    scroll = max(0, min(scroll, len(body) - room))
    shown = body[scroll : scroll + room]
    if scroll > 0:
        shown[0] = [(f'{g["up"]} more above', 'warn')]
    if scroll + room < len(body):
        shown[-1] = [(f'{g["down"]} more below ({g["up"]}{g["down"]} to scroll)', 'warn')]
    for row in shown:
        lines.append(paint([('  ', None)] + row, usable, g))
    lines += [''] * (height - 3 - len(lines))
    footer = [(f'  {message}', 'warn')] if message else [(f'  Sheets: {output}', 'dim')]
    lines.append(paint(footer, usable, g))
    lines.append(paint([('  ' + KEYS.format(**g), 'dim')], usable, g))
    return lines
