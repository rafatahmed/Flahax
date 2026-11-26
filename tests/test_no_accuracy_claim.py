# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""No real-mixture predictive accuracy is claimed (contract Q25, issue #41).

Q25 asks for measured evidence "for the claimed accuracy". FlahaX claims none: results
say so, and the documents that discuss accuracy say that no measured accuracy exists.
A future claim needs the physical validation that #41 designs.
"""

import json
from pathlib import Path
import tempfile
import unittest

from flahax import render_report
from flahax.batch_request import BatchOptions, run_batch

ROOT = Path(__file__).resolve().parents[1]
STATEMENT = 'No real-mixture predictive accuracy is claimed'


def summary():
    with tempfile.TemporaryDirectory() as folder:
        targets = Path(folder, 'targets.json')
        targets.write_text(json.dumps({'N_NO3': 100, 'Ca': 100}))
        water = Path(folder, 'water.json')
        water.write_text(json.dumps({'mg_per_litre': {'HCO3': 0}, 'measured_ph': 6.0}))
        return run_batch(
            BatchOptions(water=str(water), targets=str(targets), volume=1000, ratio=100)
        )


class NoAccuracyClaimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = summary()

    def test_every_result_says_no_predictive_accuracy_is_claimed(self):
        text = ' '.join(self.result['assumptions'])
        self.assertIn(STATEMENT, text)
        self.assertIn('measured evidence', text)
        self.assertIn('#41', text)

    def test_the_report_shows_the_statement(self):
        self.assertIn(STATEMENT, render_report(self.result))

    def test_the_documents_that_discuss_accuracy_state_that_none_is_claimed(self):
        conductivity = (ROOT / 'docs/site/developer/conductivity.md').read_text(encoding='utf-8')
        self.assertIn('No measured accuracy is claimed', conductivity)
        benchmark = (ROOT / 'docs/site/evidence/benchmark-results-windows.md').read_text(
            encoding='utf-8'
        )
        self.assertIn('No measured mixture/pH/titration/EC accuracy claim', benchmark)
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertIn('unknown accuracy', readme)

    def test_the_validation_protocol_exists_and_is_a_draft_for_review(self):
        protocol = ' '.join(
            (ROOT / 'docs/physical-validation-protocol.md').read_text(encoding='utf-8').split()
        )
        self.assertIn('Draft for independent review', protocol)
        self.assertIn('#41', protocol)
        self.assertIn('Nothing in this document authorizes', protocol)


if __name__ == '__main__':
    unittest.main()
