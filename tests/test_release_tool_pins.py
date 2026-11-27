# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The tools that build and check the release are pinned (#348, roadmap H8).

The release job installs ``tools/requirements-release.txt`` with ``--require-hashes`` and builds
without isolation, so the build tool, its backend (setuptools) and twine are exactly the reviewed
versions. Every other job that installs ``build`` uses the same version. Dependabot proposes
updates monthly.
"""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / '.github' / 'workflows'
REQUIREMENTS = ROOT / 'tools' / 'requirements-release.txt'
SOURCES = ROOT / 'tools' / 'requirements-release.in'


def requirements():
    """name -> (version, hash count) for every pinned requirement line."""
    found, current = {}, None
    for line in REQUIREMENTS.read_text(encoding='utf-8').splitlines():
        match = re.match(r'^([A-Za-z0-9_.-]+)==([^\s;\\]+)', line)
        if match:
            current = match.group(1).lower()
            found[current] = [match.group(2), 0]
        elif line.strip().startswith('--hash=sha256:') and current:
            found[current][1] += 1
    return found


def install_lines():
    for path in sorted(WORKFLOWS.glob('*.yml')):
        for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            if 'pip install' in line:
                yield path.name, number, line.strip()


class ReleaseToolPinTests(unittest.TestCase):
    def test_every_requirement_is_an_exact_version_with_hashes(self):
        pins = requirements()
        self.assertTrue(pins)
        for name, (version, hashes) in pins.items():
            with self.subTest(name):
                self.assertRegex(version, r'^\d')
                self.assertGreaterEqual(hashes, 1)
        text = REQUIREMENTS.read_text(encoding='utf-8')
        loose = [
            line
            for line in text.splitlines()
            if line
            and not line.startswith((' ', '#'))
            and not re.match(r'^[A-Za-z0-9_.-]+==', line)
        ]
        self.assertEqual(loose, [])

    def test_the_release_tools_and_their_backend_are_pinned(self):
        pins = requirements()
        for name in ('build', 'twine', 'setuptools'):
            self.assertIn(name, pins)
        sources = SOURCES.read_text(encoding='utf-8')
        for name in ('build', 'twine', 'setuptools'):
            self.assertRegex(sources, rf'(?m)^{name}\b')
        pyproject = (ROOT / 'pyproject.toml').read_text(encoding='utf-8')
        minimum = re.search(r'requires = \["setuptools>=([0-9.]+)"\]', pyproject).group(1)
        self.assertRegex(sources, rf'setuptools>={re.escape(minimum)}')
        self.assertGreaterEqual(_parts(pins['setuptools'][0]), _parts(minimum))

    def test_the_release_job_installs_with_hashes_and_builds_without_isolation(self):
        text = (WORKFLOWS / 'publish.yml').read_text(encoding='utf-8')
        self.assertIn('pip install --require-hashes -r tools/requirements-release.txt', text)
        self.assertIn('python -m build --no-isolation', text)
        self.assertNotIn('--upgrade', text)
        self.assertNotIn('python -m build\n', text)

    def test_no_workflow_installs_build_or_twine_unpinned(self):
        pinned = requirements()['build'][0]
        for name, number, line in install_lines():
            with self.subTest(f'{name}:{number}'):
                self.assertNotIn('--upgrade', line)
                for tool in re.findall(r'(?<![\w/.-])(build|twine)(==\S+)?(?=\s|$)', line):
                    self.assertEqual(
                        tool,
                        ('build', f'=={pinned}'),
                        'install build with the version pinned in requirements-release.txt',
                    )

    def test_dependabot_proposes_updates_to_the_pinned_tools(self):
        text = (ROOT / '.github' / 'dependabot.yml').read_text(encoding='utf-8')
        self.assertRegex(text, r'package-ecosystem: pip\s+directory: /tools')
        self.assertIn('package-ecosystem: github-actions', text)


def _parts(version):
    return tuple(int(part) for part in version.split('.'))


if __name__ == '__main__':
    unittest.main()
