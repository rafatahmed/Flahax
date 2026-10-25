# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Requirement traceability refuses omissions and premature numerical qualification."""

import copy
import unittest

from tools.check_requirements import validate


class RequirementContractTests(unittest.TestCase):
    def setUp(self):
        self.surface = {'exports': ['calculate'], 'runtime_files': ['src/flahax/model.py']}
        self.register = {
            'required_ids': ['R1'],
            'task_ids': ['verify'],
            'requirements': [
                {
                    'id': 'R1',
                    'contract': 'conserve mass',
                    'independent_evidence': 'rational sum',
                    'owner_tasks': ['verify'],
                }
            ],
            'findings': {'F1': ['R1']},
            'required_findings': ['F1'],
            'exports': {'calculate': ['R1']},
            'runtime_files': {'src/flahax/model.py': ['R1']},
            'physical_stage_blocks_math': False,
            'numerical_criteria': [
                {
                    'meaning': 'zero contribution',
                    'status': 'structural_exact',
                    'qualification_task': 'verify',
                }
            ],
        }

    def test_complete_inventory_is_not_a_claim_of_implemented_requirements(self):
        self.assertEqual(validate(self.register, self.surface), [])

    def test_missing_duplicate_unknown_requirements_and_owners_fail(self):
        for mutate in (
            lambda r: r['requirements'].clear(),
            lambda r: r['requirements'].append(r['requirements'][0]),
            lambda r: r['findings'].update(F1=['unknown']),
            lambda r: r['requirements'][0].update(owner_tasks=['unknown']),
            lambda r: r['requirements'][0].update(contract=''),
        ):
            data = copy.deepcopy(self.register)
            mutate(data)
            self.assertTrue(validate(data, self.surface))

    def test_new_api_or_module_requires_inventory_update(self):
        for field in self.surface:
            surface = copy.deepcopy(self.surface)
            surface[field].append('new')
            self.assertTrue(validate(self.register, surface))

    def test_physical_gate_and_unqualified_tolerance_adoption_fail(self):
        self.register['physical_stage_blocks_math'] = True
        self.assertTrue(validate(self.register, self.surface))
        self.register['physical_stage_blocks_math'] = False
        self.register['numerical_criteria'][0]['status'] = 'approved_without_evidence'
        self.assertTrue(validate(self.register, self.surface))

    def test_malformed_register_is_rejected(self):
        for value in (None, {}, {'requirements': None}):
            self.assertTrue(validate(value, self.surface))


if __name__ == '__main__':
    unittest.main()
