# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Optional source-byte retrieval, independent of PHREEQC execution or installation."""

import hashlib
import json
import os
from pathlib import Path
import unittest
from urllib.error import URLError
from urllib.request import urlopen


@unittest.skipUnless(
    os.environ.get('FLAHAX_VERIFY_SOURCE_DOWNLOADS') == '1',
    'source downloads are opt-in; offline integrity checks remain mandatory',
)
class SourceDownloadTests(unittest.TestCase):
    def test_versioned_downloads_match_recorded_bytes(self):
        sources = json.loads(
            (Path(__file__).resolve().parents[1] / 'tools/chemistry_sources.json').read_bytes()
        )
        for source in sources:
            record = source.get('archive', source)
            with self.subTest(source=source['filename']):
                try:
                    with urlopen(record['url'], timeout=60) as response:
                        raw = response.read()
                except (URLError, TimeoutError) as exc:
                    self.fail(f'source retrieval unavailable: {exc}')
                self.assertEqual(len(raw), record['bytes'], 'download byte-count mismatch')
                self.assertEqual(
                    hashlib.sha256(raw).hexdigest(),
                    record['sha256'],
                    'download content hash mismatch',
                )
