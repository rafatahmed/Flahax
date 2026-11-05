#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Say whether a pull request changes more than documentation (docs/adr/0002).

A comparison that cannot be made fails; it is never read as "documentation only".
"""

from pathlib import Path
import re
import subprocess
import sys

DOCUMENTATION = re.compile(r'docs/|[^/]+\.md$')


def changed_files(base, candidate, root):
    result = subprocess.run(
        ['git', 'diff', '--name-only', f'{base}...{candidate}'],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.splitlines()


def code_changed(paths):
    """True unless there is at least one changed file and every one is documentation."""
    return not paths or any(not DOCUMENTATION.match(path) for path in paths)


def main(argv=None, root=None):
    base, candidate = sys.argv[1:] if argv is None else argv
    root = Path.cwd() if root is None else root
    print(f'code={str(code_changed(changed_files(base, candidate, root))).lower()}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
