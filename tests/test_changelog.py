# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The changelog keeps the release structure (owner decision 2026-10-23, from 0.6.0 on).

Each section from 0.6.0 on, and Unreleased, groups short bullets under fixed headings; the
full text of a change belongs in docs/releases/<version>.md (CONTRIBUTING, Changelog).
"""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
HEADINGS = {
    'Added',
    'Changed',
    'Fixed',
    'Deprecated',
    'Removed',
    'Security',
    'Compatibility and limits',
}
LONGEST_BULLET = 400


def checked_sections(text=None):
    """(title, body) of Unreleased and of every version from 0.6.0 on."""
    if text is None:
        text = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
    for match in re.finditer(r'(?ms)^## (.+?)\n(.*?)(?=^## |\Z)', text):
        title, body = match.group(1).strip(), match.group(2)
        version = re.match(r'(\d+)\.(\d+)\.(\d+)', title)
        if title == 'Unreleased' or (version and tuple(map(int, version.groups())) >= (0, 6, 0)):
            yield title, body


def problems(text=None):
    """Every way the sections break the release structure, as readable strings."""
    found = []
    for title, body in checked_sections(text):
        for heading in re.findall(r'(?m)^### (.+)$', body):
            if heading.strip() not in HEADINGS:
                found.append(f'{title}: heading {heading.strip()!r}')
        for bullet in re.findall(r'(?m)^- .*$', body):
            if len(bullet) > LONGEST_BULLET:
                found.append(f'{title}: bullet of {len(bullet)} characters')
        grouped = re.search(r'(?m)^### ', body)
        if title != 'Unreleased' and re.search(r'(?m)^- ', body) and not grouped:
            found.append(f'{title}: bullets without headings')
    return found


class ChangelogStructureTests(unittest.TestCase):
    def test_the_changelog_keeps_the_structure(self):
        self.assertEqual(problems(), [])

    def test_the_old_style_is_refused(self):
        merged = 'A long merged paragraph. ' * 20
        old_style = f'# Changelog\n\n## 0.7.0 - 2027-01-01\n\n- {merged}\n'
        self.assertEqual(
            problems(old_style),
            [
                '0.7.0 - 2027-01-01: bullet of 502 characters',
                '0.7.0 - 2027-01-01: bullets without headings',
            ],
        )
        self.assertEqual(problems('## 0.7.0\n\n### News\n\n- short\n'), ["0.7.0: heading 'News'"])

    def test_older_releases_are_not_checked(self):
        merged = 'A long merged paragraph. ' * 20
        self.assertEqual(problems(f'## 0.5.0 - 2026-10-20\n\n- {merged}\n'), [])


if __name__ == '__main__':
    unittest.main()
