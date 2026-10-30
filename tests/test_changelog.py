# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The changelog follows Keep a Changelog 1.1.0 (decision 2026-10-23, every release).

Headings ``## [X.Y.Z] - YYYY-MM-DD`` (``[YANKED]`` for a yanked release), ``## [Unreleased]``
first, only the six change types, short bullets, and a comparison link for every version. The
full text of a change belongs in docs/releases/<version>.md (CONTRIBUTING, Changelog).
"""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
HEADINGS = {'Added', 'Changed', 'Deprecated', 'Removed', 'Fixed', 'Security'}
LONGEST_BULLET = 400
VERSION_HEADING = re.compile(
    r'^\[(?P<version>\d+\.\d+\.\d+)\] - (?:\d{4}-\d{2}-\d{2}(?: \[YANKED\])?|not yet released)$'
)


def sections(text):
    """(title, body) of every ``## `` section."""
    for match in re.finditer(r'(?ms)^## (.+?)\n(.*?)(?=^## |\Z)', text):
        yield match.group(1).strip(), match.group(2)


def problems(text=None):
    """Every way the changelog breaks Keep a Changelog, as readable strings."""
    if text is None:
        text = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
    found, titles = [], [title for title, _ in sections(text)]
    if not titles or titles[0] != '[Unreleased]':
        found.append('the first section must be ## [Unreleased]')
    links = set(re.findall(r'(?m)^\[([^\]]+)\]: https://', text))
    for title, body in sections(text):
        version = VERSION_HEADING.match(title)
        if title != '[Unreleased]' and not version:
            found.append(f'{title}: heading is not "[X.Y.Z] - YYYY-MM-DD"')
        key = 'unreleased' if title == '[Unreleased]' else version and version.group('version')
        if key and key not in links:
            found.append(f'{title}: no comparison link [{key}]')
        for heading in re.findall(r'(?m)^### (.+)$', body):
            if heading.strip() not in HEADINGS:
                found.append(f'{title}: heading {heading.strip()!r}')
        for bullet in re.findall(r'(?m)^- .*$', body):
            if len(bullet) > LONGEST_BULLET:
                found.append(f'{title}: bullet of {len(bullet)} characters')
        if re.search(r'(?m)^- ', body) and not re.search(r'(?m)^### ', body):
            found.append(f'{title}: bullets without headings')
    return found


class ChangelogStructureTests(unittest.TestCase):
    def test_the_changelog_keeps_the_structure(self):
        self.assertEqual(problems(), [])

    def test_the_old_style_is_refused(self):
        merged = 'A long merged paragraph. ' * 20
        old_style = f'# Changelog\n\n## Unreleased\n\n## 0.7.0 - 2027-01-01\n\n- {merged}\n'
        self.assertEqual(
            problems(old_style),
            [
                'the first section must be ## [Unreleased]',
                'Unreleased: heading is not "[X.Y.Z] - YYYY-MM-DD"',
                '0.7.0 - 2027-01-01: heading is not "[X.Y.Z] - YYYY-MM-DD"',
                '0.7.0 - 2027-01-01: bullet of 502 characters',
                '0.7.0 - 2027-01-01: bullets without headings',
            ],
        )

    def test_headings_links_and_types(self):
        text = (
            '## [Unreleased]\n\n## [0.7.0] - 2027-01-01\n\n### News\n\n- short\n\n'
            '[unreleased]: https://example.org/a\n'
        )
        self.assertEqual(
            problems(text),
            [
                '[0.7.0] - 2027-01-01: no comparison link [0.7.0]',
                "[0.7.0] - 2027-01-01: heading 'News'",
            ],
        )


if __name__ == '__main__':
    unittest.main()
