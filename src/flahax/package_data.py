# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Read the data files shipped inside the package.

``importlib.resources`` takes about 35 ms to import (tempfile, shutil,
zipfile and the path readers), which every first call paid only to open
a file beside the package (#342). The package is installed as plain
files, so they are opened directly.
"""

import os

_DIRECTORY = os.path.dirname(os.path.abspath(__file__))


def read_bytes(relative):
    """The bytes of ``relative`` (for example ``data/library.json``)."""
    with open(os.path.join(_DIRECTORY, *relative.split('/')), 'rb') as handle:
        return handle.read()


def read_text(relative, encoding='utf-8'):
    """The decoded text of ``relative``, with universal newlines."""
    with open(os.path.join(_DIRECTORY, *relative.split('/')), encoding=encoding) as handle:
        return handle.read()
