# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Edge-case corpus for the public entry points (#348, roadmap H2).

Every malformed number gets a documented error (an ``InputError``, which is a ``ValueError``,
or a ``DeliveryError`` with a stable code), never a traceback, an overflow or a plausible-looking
plan with a non-finite value.
"""

import itertools
import json
import math
from pathlib import Path
import tempfile
import unittest

from flahax import DeliveryError, InputError, load_library, recommend
from flahax.aqueous_model import nitric_target, solve
from flahax.batch_cli import main as batch
from flahax.composition import MAX_MG_PER_L
from flahax.water_input import read_water

from tests.test_entry_inputs import TOMATO, run

NOT_NUMBERS = ['abc', None, True, [1], {'a': 1}]
NUMBERS_OUT_OF_RANGE = [float('nan'), float('inf'), float('-inf'), -1.0, 1e308]
TARGETS = {'Ca': 100.0, 'K': 150.0, 'Mg': 40.0, 'P': 40.0, 'S': 60.0, 'N': 150.0}
WATER = {'Ca': 20.0, 'Mg': 5.0, 'N_NO3': 2.0}
TOTALS = {'CO3-2': 0.001, 'Na+': 0.002, 'Cl-': 0.001}


def finite(value):
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(finite(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(finite(item) for item in value)
    return True


class RecommendInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.salts = load_library()['salts']

    def test_a_bad_target_or_water_number_is_an_input_error(self):
        bad = NUMBERS_OUT_OF_RANGE + NOT_NUMBERS
        for ion in TARGETS:
            for value in bad:
                if ion == 'N' and value is None:
                    continue  # a total-N target of None means no total-N target
                with self.subTest(target=ion, value=repr(value)):
                    with self.assertRaises(InputError):
                        recommend(self.salts, {**TARGETS, ion: value}, WATER)
        for ion in ('Ca', 'Mg', 'N_NO3', 'Na', 'Cl'):
            for value in bad:
                with self.subTest(water=ion, value=repr(value)):
                    with self.assertRaises(InputError):
                        recommend(self.salts, TARGETS, {**WATER, ion: value})

    def test_an_unknown_ion_is_an_input_error(self):
        with self.assertRaises(InputError):
            recommend(self.salts, TARGETS, {**WATER, 'Zz': 1.0})
        with self.assertRaises(InputError):
            recommend(self.salts, {**TARGETS, 'Zz': 1.0}, WATER)

    def test_the_largest_concentration_is_accepted_and_finite(self):
        for value in (0.0, 1e-308, 1.0):
            with self.subTest(value=value):
                result = recommend(self.salts, TARGETS, {**WATER, 'Na': value})
                self.assertTrue(finite(result['grams']))
        with self.assertRaises(InputError) as raised:
            recommend(self.salts, TARGETS, {**WATER, 'Na': MAX_MG_PER_L * 1.0000001})
        self.assertIn('more than a litre of solution can hold', str(raised.exception))


class AqueousInputTests(unittest.TestCase):
    def code(self, call):
        with self.assertRaises(DeliveryError) as raised:
            call()
        return raised.exception.code

    def test_a_non_number_pH_or_total_is_a_delivery_error_not_a_type_error(self):
        for value in NOT_NUMBERS:
            with self.subTest(value=repr(value)):
                self.assertEqual(self.code(lambda: solve(TOTALS, value)), 'out_of_range')
                self.assertEqual(
                    self.code(lambda: nitric_target(TOTALS, value, 6.0)), 'out_of_range'
                )
                self.assertEqual(
                    self.code(lambda: nitric_target(TOTALS, 7.4, value)), 'out_of_range'
                )
                self.assertEqual(
                    self.code(lambda: solve({**TOTALS, 'Na+': value}, 7.0)), 'invalid_totals'
                )
                if value is not None:  # None means: solve the ionic strength
                    self.assertEqual(
                        self.code(lambda: solve(TOTALS, 7.0, ionic_strength=value)),
                        'activity_model_out_of_range',
                    )

    def test_a_valid_pH_keeps_the_type_it_was_given(self):
        self.assertIs(type(solve(TOTALS, 7).ph), int)
        self.assertIs(type(solve(TOTALS, 7.0).ph), float)

    def test_totals_must_be_a_map_of_known_components(self):
        self.assertEqual(self.code(lambda: solve([1], 7.0)), 'invalid_totals')
        self.assertEqual(self.code(lambda: solve({'Zz+': 0.001}, 7.0)), 'invalid_totals')
        for value in (float('nan'), float('inf'), -1.0):
            with self.subTest(value=value):
                self.assertEqual(
                    self.code(lambda: solve({**TOTALS, 'Na+': value}, 7.0)), 'invalid_totals'
                )

    def test_pH_beyond_the_scale_is_rejected_and_its_ends_report_the_model_limit(self):
        for ph in (2, 12, 2.0, 12.0):
            with self.subTest(ph=ph):
                self.assertTrue(math.isfinite(solve(TOTALS, ph).ionic_strength))
        for ph in (-0.1, 14.1, float('nan'), float('inf')):
            with self.subTest(ph=ph):
                self.assertEqual(self.code(lambda: solve(TOTALS, ph)), 'out_of_range')
        # At pH 0 and 14 one mol/kg of H+ or OH- is itself above the Davies limit of 0.1.
        for ph in (0, 14):
            with self.subTest(ph=ph):
                self.assertEqual(
                    self.code(lambda: solve(TOTALS, ph)), 'activity_model_out_of_range'
                )

    def test_ionic_strength_is_limited_to_the_activity_model(self):
        self.assertTrue(math.isfinite(solve(TOTALS, 7.0, ionic_strength=0.1).ph))
        self.assertTrue(math.isfinite(solve(TOTALS, 7.0, ionic_strength=0).ph))
        for value in (0.1000001, -0.1, float('nan')):
            with self.subTest(value=value):
                self.assertEqual(
                    self.code(lambda: solve(TOTALS, 7.0, ionic_strength=value)),
                    'activity_model_out_of_range',
                )

    def test_only_25_degrees_is_modelled(self):
        for value in (20.0, float('nan')):
            with self.subTest(value=value):
                self.assertEqual(
                    self.code(lambda: solve(TOTALS, 7.0, temperature_c=value)),
                    'temperature_out_of_range',
                )


class WaterFileTests(unittest.TestCase):
    def water(self, measured_ph):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / 'water.json'
        text = '{"id": "x", "measured_ph": %s, "mg_per_litre": {"Ca": 10, "HCO3": 50}}' % (
            measured_ph
        )
        path.write_text(text, encoding='utf-8')
        return str(path)

    def test_a_measured_pH_that_is_not_a_finite_number_is_rejected(self):
        for text in ('NaN', 'Infinity', '-Infinity', '"7"', 'null', 'true'):
            with self.subTest(measured_ph=text):
                with self.assertRaises(DeliveryError) as raised:
                    read_water(self.water(text))
                self.assertEqual(raised.exception.code, 'invalid_value')

    def test_a_finite_measured_pH_is_read(self):
        self.assertEqual(read_water(self.water('7.8'))[2]['measured_ph'], 7.8)

    def test_a_nan_measured_pH_stops_the_command_with_a_message(self):
        with tempfile.TemporaryDirectory() as folder:
            code, text = run(
                batch,
                [*TOMATO, '--water', self.water('NaN'), '--ph', '5.8', '--output', folder + '/o'],
            )
        self.assertEqual(code, 1)
        self.assertIn('measured_ph', text)
        self.assertNotIn('Traceback', text)


class CommandNumberTests(unittest.TestCase):
    FLAGS = (
        '--volume',
        '--ph',
        '--ph-min',
        '--ph-max',
        '--ratio',
        '--ec',
        '--water-share',
        '--range-percent',
        '--max-reagent-litres',
        '--tank-capacity',
        '--available-tanks',
        '--alternative-search-budget',
        '--max-solid-reagent-grams',
    )
    VALUES = ('nan', 'inf', '-inf', '-1', 'abc', '')
    # Zero is a valid input for several flags (a strict range, no solid reagent, pH 0 as a
    # blocked report), and the search budget is ignored without --alternative-products, so the
    # rejection matrix covers values that are never meaningful.
    IGNORED = {('--alternative-search-budget', '-1')}

    def test_a_bad_number_stops_the_command_with_a_message_and_a_nonzero_code(self):
        accepted = []
        with tempfile.TemporaryDirectory() as folder:
            for number, (flag, value) in enumerate(itertools.product(self.FLAGS, self.VALUES)):
                if (flag, value) in self.IGNORED:
                    continue
                with self.subTest(flag=flag, value=value):
                    target = f'{folder}/out{number}'
                    argv = [*TOMATO, '--water', 'ro', flag, value, '--output', target]
                    if flag in ('--ph-min', '--ph-max'):
                        argv += ['--ph-max' if flag == '--ph-min' else '--ph-min', '7']
                    code, text = run(batch, argv)
                    if code == 0 or Path(target).exists():
                        accepted.append((flag, value, code))
                    self.assertNotIn('Traceback', text)
                    self.assertTrue(text.strip())
        self.assertEqual(accepted, [])

    def test_an_overflowing_volume_stops_the_command_without_a_traceback(self):
        with tempfile.TemporaryDirectory() as folder:
            code, text = run(
                batch, [*TOMATO, '--water', 'ro', '--volume', '1e308', '--output', folder + '/out']
            )
        self.assertNotEqual(code, 0)
        self.assertNotIn('Traceback', text)
        self.assertIn('not a finite', text)

    def test_a_good_run_still_writes_its_files(self):
        with tempfile.TemporaryDirectory() as folder:
            code, _ = run(
                batch,
                [
                    *TOMATO,
                    '--water',
                    'ro',
                    '--ph',
                    '5.8',
                    '--volume',
                    '100',
                    '--output',
                    folder + '/out',
                ],
            )
            self.assertIn(code, (0, 3))
            summary = json.loads(
                (Path(folder) / 'out' / 'summary.json').read_text(encoding='utf-8')
            )
            self.assertTrue(finite(summary))


if __name__ == '__main__':
    unittest.main()
