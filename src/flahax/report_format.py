# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Number and text formatters shared by every grower report and sheet."""

from html import escape
import math


DISPLAY_ZERO = 1e-9  # Existing display rounding only; never a solver or acceptance tolerance.


def litres(value):
    """A volume a grower can measure: one decimal from 10 L, three below
    (never '0 L' for a small batch).
    """
    return dose_number(value, 1 if value >= 10 else 3)


def display_residue(value):
    """Whether a positive displayed quantity falls below the existing
    display-zero precision.
    """
    return 0 < value < DISPLAY_ZERO


def grams(value):
    """A weight a grower can read on a scale: never '0 g' for a product
    that is in the recipe.
    """
    if display_residue(value):
        return f'numerical residue: {value:.6g} g'
    digits = 1 if value >= 10 else 2 if value >= 0.1 else 3
    shown = number(value, digits)
    return f'{shown} g' if float(shown.replace(',', '')) > 0 else 'less than 0.001 g'


def below_checklist_precision(value):
    """Detect a positive mass below the dry checklist's 0.001 g
    reporting increment.
    """
    return 0 < value < 0.001


def checklist_grams(value):
    """Show an unresolved small dose as a diagnostic on preparation
    checklists.
    """
    if below_checklist_precision(value) and not display_residue(value):
        return f'{value:.6g} g (below 0.001 g)'
    return grams(value)


def millilitres(value):
    """A reagent volume, one decimal, the same on every output."""
    return dose_number(value, 1)


def text(value):
    """The value as HTML-escaped text."""
    return escape(str(value), quote=True)


def number(value, digits=4):
    """A readable number: "Not available" for None, scientific notation
    below 0.0001, otherwise grouped with trailing zeros removed.
    """
    if value is None:
        return 'Not available'
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        return text(value)
    if abs(value) < DISPLAY_ZERO:
        value = 0.0  # floating-point noise such as 7e-15 mg/L
    if value != 0 and abs(value) < 0.0001:
        return f'{value:.3e}'
    return f'{value:,.{digits}f}'.rstrip('0').rstrip('.') if digits else f'{value:,.0f}'


def table(headers, rows, caption):
    """An HTML table with a caption, header row and escaped cells, in a
    scrolling wrapper.
    """
    return (
        '<div class="table-scroll"><table><caption>'
        + text(caption)
        + '</caption><thead><tr>'
        + ''.join('<th scope="col">' + text(h) + '</th>' for h in headers)
        + '</tr></thead><tbody>'
        + ''.join(
            '<tr>' + ''.join('<td>' + text(cell) + '</td>' for cell in row) + '</tr>'
            for row in rows
        )
        + '</tbody></table></div>'
    )


def bars(title, labels, series, unit):
    """Zero-based grouped bars with direct value labels and a visible
    axis.
    """
    colors = ['#116c73', '#879bb0', '#e3a128']
    values = [
        v
        for _, samples in series
        for v in samples
        if isinstance(v, (int, float)) and math.isfinite(v)
    ]
    maximum = max(values, default=0)
    maximum = maximum * 1.15 if maximum > 0 else 1
    group = max(56, len(series) * 21 + 12)
    height = 94 + group * len(labels)
    left, width = 265, 545
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 940 {height}" role="img" '
        f'aria-label="{text(title)}">',
        '<title>' + text(title) + '</title>',
        '<desc>Zero-based horizontal bars. Exact values and units also appear in the '
        'accompanying table. '
        'Missing values are not plotted.</desc>',
    ]
    for i in range(5):
        x = left + width * i / 4
        svg.append(f'<path d="M{x} 38 V{height - 38}" stroke="#dbe4e8"/>')
        svg.append(
            f'<text x="{x}" y="{height - 16}" '
            f'text-anchor="middle">{number(maximum * i / 4, 2)}</text>'
        )
    for index, (name, _) in enumerate(series):
        x = left + index * 170
        svg.append(f'<rect x="{x}" y="9" width="11" height="11" fill="{colors[index % 3]}"/>')
        svg.append(f'<text x="{x + 17}" y="19">{text(name)}</text>')
    for row, label in enumerate(labels):
        y = 45 + group * row
        # Long product labels wrap into separate SVG text elements.
        words, lines, line = str(label).split(), [], ''
        for word in words:
            if len(line + ' ' + word) > 31 and line:
                lines.append(line)
                line = word
            else:
                line = (line + ' ' + word).strip()
        lines.append(line)
        for j, line in enumerate(lines):
            svg.append(f'<text x="12" y="{y + 14 + j * 17}">{text(line)}</text>')
        for j, (_, samples) in enumerate(series):
            value = samples[row]
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                continue
            size = width * value / maximum
            by = y + j * 21
            svg.append(
                f'<rect x="{left}" y="{by}" width="{size}" height="14" rx="3" '
                f'fill="{colors[j % 3]}"/>'
            )
            svg.append(f'<text x="{left + size + 7}" y="{by + 12}">{number(value, 3)}</text>')
    svg.append('</svg>')
    return (
        '<figure><figcaption>'
        + text(title)
        + ' <small>('
        + text(unit)
        + ')</small></figcaption>'
        + ''.join(svg)
        + '</figure>'
    )


def percentage(value, digits=2, suffix="%"):
    """Format a relative difference without inventing a percentage for
    zero targets.
    """
    return 'undefined (zero target)' if value is None else f'{value:+.{digits}f}{suffix}'


def dose_number(value, digits=2):
    """Preserve a positive dose when fixed-point display would round it
    to zero.
    """
    shown = number(value, digits)
    if value is not None and value > 0 and float(shown.replace(',', '')) == 0:
        return f'{value:.6g}'
    return shown


def ec_text(ec, *, about=False):
    """The EC a result can state: one value for an estimate, 'low-high'
    for a range, else None.
    """
    if not ec or ec.get('status') not in ('estimated', 'range') or not ec.get('ec25_range_ms_cm'):
        return None
    low, high = ec['ec25_range_ms_cm']
    if ec['status'] == 'estimated':
        return ('about ' if about else '') + number(low, 2)
    return (
        f'{number(low, 2)} to {number(high, 2)}'
        if about
        else f'{number(low, 2)}\u2013{number(high, 2)}'
    )
