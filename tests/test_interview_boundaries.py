# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Input preservation and terminal boundary checks for #186."""

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from flahax import DeliveryError, load_library
from flahax import mix_cli as cli
from flahax.mix_store import Store
from tests.test_mix_cli import Script


class InterviewBoundaryTests(unittest.TestCase):
    def test_required_text_number_date_and_name_retry(self):
        lines = []
        p = cli.Prompts(
            Script(['', 'value', '-1', '2', 'bad', '2026-10-27', 'Sheet', 'taken', '1', 'fresh']),
            lines.append,
        )
        self.assertEqual(p.text('Required'), 'value')
        self.assertEqual(p.number('Nonnegative'), 2)
        self.assertEqual(p.document('Supplier')['issued'], '2026-10-27')
        store = Mock()
        store.list.return_value = ['taken']
        self.assertEqual(p.new_name(store, 'stores', 'Name'), 'fresh')
        self.assertTrue(any('needed' in line for line in lines))
        self.assertTrue(any('2025-03-28' in line for line in lines))

    def test_saved_water_and_invalid_limit_retry(self):
        p, store, pending = Mock(), Mock(), []
        store.list.return_value = ['lab']
        p.choose.return_value = 1
        p.number.return_value = 25
        p.text.side_effect = ['Na', 'Na=0 Cl=10']
        self.assertEqual(cli.ask_water(p, store, pending), ('lab', 25, {'Na': 0, 'Cl': 10}))
        self.assertEqual(pending, [])
        self.assertEqual(p.text.call_count, 2)

    def test_saved_and_new_formula_preserve_explicit_zero(self):
        library = load_library()
        store = Mock()
        store.list.return_value = ['existing']
        store.load.return_value = {'K': 0}
        p = Mock()
        p.choose.return_value = 2
        pending = []
        self.assertEqual(
            cli.ask_formula(p, store, pending, library), ('existing', {'K': 0}, 'existing')
        )
        self.assertEqual(pending, [])
        p.choose.return_value = 3
        p.new_name.return_value = 'new'
        p.typed = 'New'
        p.number.side_effect = lambda label, **kw: 0 if label.startswith('K,') else None
        self.assertEqual(cli.ask_formula(p, store, pending, library), ('new', {'K': 0}, 'New'))
        self.assertEqual(pending, [('formulas', 'new', {'K': 0})])

    def test_product_selection_and_failed_add_do_not_replace_saved_records(self):
        catalogue = load_library()
        store = Mock()
        store.list.return_value = ['saved']
        store.load.return_value = catalogue['salts'][:1]
        p = Mock()
        p.choose.side_effect = [1, 2, 0]
        pending = []
        with patch.object(cli, 'add_compound', return_value=None):
            ref, products = cli.ask_products(p, store, pending, catalogue)
        self.assertEqual((ref, products), ('saved', catalogue['salts'][:1]))
        self.assertEqual(pending, [])
        p.choose.side_effect = [2, 0]
        p.pick_many.return_value = [0]
        p.new_name.return_value = 'chosen'
        self.assertEqual(
            cli.ask_products(p, store, pending, catalogue), ('chosen', catalogue['salts'][:1])
        )
        self.assertEqual(pending, [('stores', 'chosen', catalogue['salts'][:1])])

    def test_saved_acid_and_invalid_new_name(self):
        store, p = Mock(), Mock()
        store.list.return_value = ['saved']
        p.choose.side_effect = [0, 1]
        self.assertEqual(cli.ask_acids(p, store, []), ['saved'])
        p.choose.side_effect = [1, 2]
        p.text.side_effect = ['HNO3', 'bad:name', 'New acid']
        p.number.side_effect = [60, 1.37]
        pending = []
        self.assertEqual(cli.ask_acids(p, store, pending), ['new-acid'])
        self.assertEqual(pending[0][2]['name'], 'New acid')
        self.assertTrue(any('cannot contain' in str(c) for c in p.say.call_args_list))

    def test_single_grade_disagreement_and_invalid_compound_are_rejected(self):
        library = load_library()
        p = Mock()
        p.search.side_effect = lambda prompt, labels: labels[0]
        p.choose.return_value = 0
        p.text.side_effect = ['Brand', 'Supplier', '']
        p.document.return_value = dict(
            supplier='Supplier', title='Sheet', issued='2026-10-27', entered='2026-10-27'
        )
        p.number.side_effect = lambda label, *a, **k: 100 if label.startswith('Ca,') else 0
        self.assertIsNone(cli.add_single(p, library['salts']))
        self.assertTrue(any('identity_inconsistent' in str(c) for c in p.say.call_args_list))
        p.text.side_effect = ['Compound', 'Supplier', '']
        p.number.side_effect = None
        p.number.return_value = None
        self.assertIsNone(cli.add_compound(p))
        self.assertTrue(any('Not added' in str(c) for c in p.say.call_args_list))


class SavedInputBoundaryTests(unittest.TestCase):
    def session(self):
        return dict(
            spec=dict(
                tank_litres={'A': 20, 'B': 20, 'acid': 20},
                ratio=100,
                temperature_c=25,
                mode='fill',
                irrigation_litres=None,
            ),
            water='ro',
            water_share=100,
            limits={},
            formula='Tomato (Howard Resh)',
            store='catalogue',
            acids=[],
            ph=5.8,
        )

    def test_session_wrong_types_are_named(self):
        cases = [
            ('spec', [], None),
            ('ratio', None, 'spec'),
            ('temperature_c', True, 'spec'),
            ('irrigation_litres', '100', 'spec'),
            ('mode', [], 'spec'),
            ('water', [], None),
            ('formula_title', None, None),
        ]
        for key, value, parent in cases:
            data = deepcopy(self.session())
            (data[parent] if parent else data)[key] = value
            with self.subTest(key=key), self.assertRaises(DeliveryError) as caught:
                cli.check_session(data, 'example.json')
            self.assertEqual(caught.exception.code, 'invalid_session')
            self.assertIn(key, str(caught.exception))
        data = self.session()
        del data['spec']['ratio']
        with self.assertRaises(DeliveryError) as caught:
            cli.check_session(data, 'example.json')
        self.assertIn('ratio', str(caught.exception))

    def test_missing_session_and_output_collision_have_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'home')
            with self.assertRaises(DeliveryError) as caught:
                cli.find_session(store, '!!!')
            self.assertEqual(caught.exception.code, 'unknown_item')
            path = Path(tmp) / 'out'
            path.mkdir()
            (Path(tmp) / 'out-2').mkdir()
            self.assertEqual(cli.output_folder(str(path), 'ignored').name, 'out-3')
            lines = []
            self.assertEqual(cli.main(['--output', str(path)], say=lines.append, store=store), 1)
            self.assertIn('already exists', lines[0])

    def test_file_disappearance_after_session_validation_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(tmp)
            session = self.session() | {'water': 'missing'}
            # Simulates the file disappearing after the prior verification read.
            with patch.object(cli, 'verify_session'):
                with self.assertRaises(DeliveryError) as caught:
                    cli.options_for(store, session)
            self.assertEqual(caught.exception.code, 'unknown_item')

    def test_tui_exit_lines_are_forwarded(self):
        lines = []
        with patch.object(cli, 'use_tui', return_value=True):
            with patch('flahax.mix_tui.run_tui', return_value=(3, ['Do not mix.'])):
                self.assertEqual(cli.main([], say=lines.append, store=Mock()), 3)
        self.assertEqual(lines, ['Do not mix.'])


class TerminalSummaryBoundaryTests(unittest.TestCase):
    def summary(self):
        # Unbound legacy rendering fixture, never a scientific acceptance certificate.
        return dict(
            status='requires_review',
            title='Synthetic rendering fixture',
            ph=None,
            batch_litres=100,
            warnings=[],
            stages={},
            volumes={'irrigation_litres': 100, 'prepared_litres': {'acid': 1}},
            tanks=dict(tanks=[], injection_ratio=100),
        )

    def test_no_reagent_mass_only_and_liquid_are_distinct(self):
        s = self.summary()
        lines = []
        cli.summarize(s, lines.append)
        self.assertTrue(any('none planned' in line for line in lines))
        chosen = dict(
            product='Synthetic reagent',
            formula='HNO3',
            volume_ml_per_batch=None,
            mass_g_per_batch=2,
        )
        s['ph'] = dict(selected=chosen, mixed_ph=7, target_ph=6)
        lines.clear()
        cli.summarize(s, lines.append)
        self.assertTrue(any('2 g' in line for line in lines))
        self.assertFalse(any('None mL' in line for line in lines))
        chosen['volume_ml_per_batch'] = 5
        lines.clear()
        cli.summarize(s, lines.append)
        self.assertTrue(any('5 mL' in line for line in lines))

    def test_unavailable_and_unselected_ph_report_reasons(self):
        from flahax.grower_report import _reagent_line, number, _water_section

        s = self.summary()
        s['ph'] = dict(selected=None, unadjusted_ph=None, message='Missing chemistry')
        self.assertIn('Missing chemistry', _reagent_line(s))
        s['ph'].update(unadjusted_ph=7, target_ph=6, direction='acid')
        self.assertIn('needs an acid', _reagent_line(s))
        self.assertEqual(number('<missing>'), '&lt;missing&gt;')
        s['water'] = dict(
            analysis_mg_per_litre={},
            modelled_mg_per_litre={},
            adjustment_mg_per_litre={},
            reconciliation='closed_on_alkalinity',
            imbalance_percent=1,
            measured_ph=7,
            below_detection=['Fe'],
        )
        s['limits'] = []
        rendered = _water_section(s)
        self.assertIn('positive, nonfixed directly supplied carbon', rendered)
        self.assertIn('not confirmed zero', rendered)
        self.assertIn('Fe', rendered)


class InterviewFailureRecoveryTests(unittest.TestCase):
    def test_once_only_volume_retries_after_capacity_failure(self):
        p = cli.Prompts(
            Script(['20', '20', '20', '100', '25', '2', '10000', '100']), lambda line: None
        )
        result = cli.ask_spec(p)
        self.assertEqual(result['irrigation_litres'], 100)
        self.assertEqual(result['mode'], 'once')

    def test_invalid_single_assay_and_unstated_chelate_do_not_invent_information(self):
        p = Mock()
        p.search.side_effect = lambda prompt, labels: labels[0]
        p.choose.return_value = 0
        p.text.side_effect = ['Brand', 'Supplier', '']
        p.document.return_value = dict(
            supplier='Supplier', title='Sheet', issued='2026-10-27', entered='2026-10-27'
        )
        p.number.return_value = True
        self.assertIsNone(cli.add_single(p, load_library()['salts']))
        self.assertTrue(any('Not added' in str(c) for c in p.say.call_args_list))
        p.text.side_effect = ['Compound', 'Supplier', '']
        p.number.side_effect = lambda label, **kw: 1 if label.startswith('Fe') else None
        p.choose.return_value = 4
        result = cli.add_compound(p)
        self.assertNotIn('chelating_agent', result['grade'])
