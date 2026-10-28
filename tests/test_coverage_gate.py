# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Coverage acceptance uses raw gaps and source identities, never rounded percentages."""

import copy
import unittest

from tools.check_coverage import validate


class CoverageGateTests(unittest.TestCase):
    def setUp(self):
        self.current = {'src/flahax/model.py': 'hash'}
        self.manifest = {
            'files': dict(self.current),
            'source_revision': 'head',
            'configuration_sha256': 'config',
        }
        self.report = {
            'meta': {'branch_coverage': True},
            'files': {
                'src/flahax/model.py': {
                    'summary': {
                        'num_statements': 2,
                        'num_branches': 2,
                        'missing_lines': 0,
                        'missing_branches': 0,
                    },
                    'executed_lines': [1, 2],
                    'missing_lines': [],
                    'executed_branches': [[1, 2], [1, -1]],
                    'missing_branches': [],
                    'excluded_lines': [],
                }
            },
        }

    def result(self):
        return validate(self.report, self.manifest, self.current, 'head', 'config')

    def test_complete_raw_measurement_passes(self):
        self.assertTrue(self.result()['passed'])

    def test_missing_unimported_module_and_empty_report_fail(self):
        self.current['src/flahax/unimported.py'] = 'new'
        self.assertFalse(self.result()['passed'])
        self.report['files'].clear()
        self.assertFalse(self.result()['passed'])

    def test_stale_commit_source_and_configuration_fail(self):
        for field, value in [
            ('source_revision', 'old'),
            ('files', {}),
            ('configuration_sha256', 'old'),
        ]:
            saved = copy.deepcopy(self.manifest)
            self.manifest[field] = value
            self.assertFalse(self.result()['passed'])
            self.manifest = saved

    def test_one_gap_cannot_hide_behind_rounded_100_percent(self):
        data = self.report['files']['src/flahax/model.py']
        data['summary']['percent_covered_display'] = '100.00'
        data['executed_branches'].pop()
        data['missing_branches'] = [[1, -1]]
        data['summary']['missing_branches'] = 1
        self.assertFalse(self.result()['passed'])

    def test_statement_gap_exclusion_and_inconsistent_counts_fail(self):
        data = self.report['files']['src/flahax/model.py']
        for field, value in [
            ('missing_lines', [2]),
            ('excluded_lines', [3]),
            ('executed_lines', [1]),
        ]:
            saved = copy.deepcopy(data)
            data[field] = value
            self.assertFalse(self.result()['passed'])
            data.clear()
            data.update(saved)

    def test_statement_only_and_malformed_reports_fail(self):
        self.report['meta']['branch_coverage'] = False
        self.assertFalse(self.result()['passed'])
        self.report = {}
        self.assertFalse(self.result()['passed'])


if __name__ == '__main__':
    unittest.main()
