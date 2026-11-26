# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""A saved result keeps what was supplied, not only a hash of it (C6, contract Q27).

The inputs and product assays are saved with the result and bound to its input
fingerprint. A changed copy is rejected, and a recalculation with other inputs
names what differs.
"""

from copy import deepcopy
import unittest

from flahax import VolumeLitres, load_library, plan_fertilizer_workflow, summarize_batch
from flahax.canonical_result import digest, seal_summary
from flahax.delivery_contracts import DeliveryError
from flahax.result_acceptance import (
    load_result,
    save_result,
    saved_input_differences,
)

LIBRARY = load_library()
SALTS = LIBRARY['salts']
TOMATO = {f['name']: f['targets'] for f in LIBRARY['formulas']}['Tomato (Howard Resh)']


def summary(targets=TOMATO, water=None):
    flow = plan_fertilizer_workflow(
        SALTS, targets, water or {}, 5.8, final_volume=VolumeLitres(1000)
    )
    return summarize_batch(flow, SALTS, title='T', water_label='RO')


def legacy(result):
    """A result as an older version sealed it: no saved inputs."""
    return seal_summary({k: v for k, v in result.items() if k != 'supplied_inputs'})


class SavedInputsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = summary()

    def test_the_summary_keeps_the_supplied_inputs_and_product_assays(self):
        supplied = self.summary['supplied_inputs']
        self.assertEqual(supplied['targets'], TOMATO)
        self.assertEqual(supplied['target_ph'], 5.8)
        self.assertEqual(supplied['final_volume'], {'value': 1000.0})
        self.assertEqual([p['id'] for p in supplied['salts']], [p['id'] for p in SALTS])
        by_id = {p['id']: p for p in supplied['salts']}
        for product in SALTS:
            with self.subTest(product=product['name']):
                self.assertEqual(by_id[product['id']]['elements'], product['elements'])

    def test_the_supplied_inputs_are_the_ones_the_input_fingerprint_binds(self):
        identity = self.summary['calculation_identity']
        self.assertEqual(digest(self.summary['supplied_inputs']), identity['input_sha256'])

    def test_save_and_load_keep_the_inputs_and_assays(self):
        loaded = load_result(save_result(self.summary))
        first = SALTS[0]
        saved = next(
            p for p in loaded['summary']['supplied_inputs']['salts'] if p['id'] == first['id']
        )
        self.assertEqual(saved['elements'], first['elements'])

    def test_inputs_changed_after_saving_are_rejected(self):
        record = save_result(self.summary)
        tampered = deepcopy(record['payload'])
        tampered['summary']['supplied_inputs']['targets']['K'] += 1
        forged = dict(record, payload=tampered, sha256=digest(tampered))
        with self.assertRaises(DeliveryError) as raised:
            load_result(forged)
        self.assertEqual(raised.exception.code, 'invalid_saved_result')

    def test_an_older_result_without_saved_inputs_still_loads(self):
        loaded = load_result(save_result(legacy(self.summary)))
        self.assertNotIn('supplied_inputs', loaded['summary'])


class RecalculationDifferenceTests(unittest.TestCase):
    def test_recalculating_with_changes_names_what_changed(self):
        before = summary()
        after = summary(targets=dict(TOMATO, K=TOMATO['K'] + 10), water={'Na': 5.0})
        differences = saved_input_differences(before, after)
        self.assertEqual(sorted(d['path'] for d in differences), ['targets.K', 'water.Na'])
        k = next(d for d in differences if d['path'] == 'targets.K')
        self.assertEqual((k['saved'], k['recalculated']), (TOMATO['K'], TOMATO['K'] + 10))

    def test_identical_inputs_have_no_differences(self):
        self.assertEqual(saved_input_differences(summary(), summary()), [])

    def test_a_result_without_saved_inputs_cannot_be_compared(self):
        with self.assertRaises(DeliveryError) as raised:
            saved_input_differences(legacy(summary()), summary())
        self.assertEqual(raised.exception.code, 'missing_field')


if __name__ == '__main__':
    unittest.main()
