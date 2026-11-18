# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The changelog follows Keep a Changelog 1.1.0 (decision 2026-10-23,
every release).

Headings ``## [X.Y.Z] - YYYY-MM-DD`` (``[YANKED]`` for a yanked
release), ``## [Unreleased]`` first, only the six change types, short
bullets, and a comparison link for every version. The full text of a
change belongs in docs/releases/<version>.md (CONTRIBUTING, Changelog).
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
    """Every way the changelog breaks Keep a Changelog, as readable
    strings.
    """
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
        seen, category, orphan, bullet = set(), None, False, []

        def finish_bullet():
            if bullet:
                length = len(' '.join(bullet))
                if length > LONGEST_BULLET:
                    found.append(f'{title}: bullet of {length} characters')
                bullet.clear()

        for line in body.splitlines():
            if line.startswith('### '):
                finish_bullet()
                category = line[4:].strip()
                if category not in HEADINGS:
                    found.append(f'{title}: heading {category!r}')
                if category in seen:
                    found.append(f'{title}: duplicate category {category}')
                seen.add(category)
            elif line.startswith('- '):
                finish_bullet()
                orphan |= category is None
                bullet.append(line.strip())
            elif bullet and line.startswith('  '):
                bullet.append(line.strip())
            elif line.strip():
                finish_bullet()
        finish_bullet()
        if orphan:
            found.append(f'{title}: bullets without headings')
    return found


class ChangelogStructureTests(unittest.TestCase):
    def test_the_changelog_keeps_the_structure(self):
        self.assertEqual(problems(), [])

    def test_duplicate_categories_are_reported_per_release(self):
        text = (
            '## [Unreleased]\n\n### Added\n\n- first\n\n### Added\n\n- second\n'
            '[unreleased]: https://example.org/compare\n'
        )
        self.assertEqual(problems(text), ['[Unreleased]: duplicate category Added'])

    def test_uncategorized_bullet_before_a_category_is_reported(self):
        text = (
            '## [Unreleased]\n\n- orphan\n\n### Fixed\n\n- categorized\n'
            '[unreleased]: https://example.org/compare\n'
        )
        self.assertEqual(problems(text), ['[Unreleased]: bullets without headings'])

    def test_wrapped_bullet_uses_its_complete_length(self):
        text = (
            '## [Unreleased]\n\n### Changed\n\n- '
            + 'x' * 200
            + '\n  '
            + 'y' * 200
            + '\n[unreleased]: https://example.org/compare\n'
        )
        self.assertEqual(problems(text), ['[Unreleased]: bullet of 403 characters'])

    def test_four_hundred_character_bullet_and_reused_release_category_are_valid(self):
        text = (
            '## [Unreleased]\n\n### Added\n\n- '
            + 'x' * 398
            + '\n\n## [1.2.3] - not yet released\n\n### Added\n\n- released feature\n'
            '[unreleased]: https://example.org/compare\n'
            '[1.2.3]: https://example.org/release\n'
        )
        self.assertEqual(problems(text), [])

    def test_the_old_style_is_refused(self):
        merged = 'A long merged paragraph. ' * 20
        old_style = f'# Changelog\n\n## Unreleased\n\n## 1.2.3 - 2027-01-01\n\n- {merged}\n'
        self.assertEqual(
            problems(old_style),
            [
                'the first section must be ## [Unreleased]',
                'Unreleased: heading is not "[X.Y.Z] - YYYY-MM-DD"',
                '1.2.3 - 2027-01-01: heading is not "[X.Y.Z] - YYYY-MM-DD"',
                '1.2.3 - 2027-01-01: bullet of 501 characters',
                '1.2.3 - 2027-01-01: bullets without headings',
            ],
        )

    def test_headings_links_and_types(self):
        text = (
            '## [Unreleased]\n\n## [1.2.3] - 2027-01-01\n\n### News\n\n- short\n\n'
            '[unreleased]: https://example.org/a\n'
        )
        self.assertEqual(
            problems(text),
            [
                '[1.2.3] - 2027-01-01: no comparison link [1.2.3]',
                "[1.2.3] - 2027-01-01: heading 'News'",
            ],
        )


if __name__ == '__main__':
    unittest.main()
