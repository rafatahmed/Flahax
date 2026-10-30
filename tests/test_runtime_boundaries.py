# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Outcome-based delivery guard checks for runtime coverage closure (#186)."""

from dataclasses import replace
import unittest

from flahax import DeliveryError, MassGrams, plan_equilibrium_delivery
from flahax.measured_water import balance_water_analysis
from tests.test_equilibrium_delivery import arguments
from tests.catalogue_history import historical_catalogue


class EquilibriumDeliveryBoundaryTests(unittest.TestCase):
    # Catalogue v0.0: re-enable in PR 4 (G5)
    @classmethod
    def setUpClass(cls):
        cls.enterClassContext(historical_catalogue())
        cls.args = arguments()

    def rejected(self, code, **changes):
        with self.assertRaises(DeliveryError) as caught:
            plan_equilibrium_delivery(**(self.args | changes))
        self.assertEqual(caught.exception.code, code)

    def test_incomplete_or_invalid_delivery_inventory(self):
        for recipe in (None, replace(self.args['recipe'], feasible=False)):
            self.rejected('infeasible_recipe', recipe=recipe)
        # An empty recipe is no longer rejected as such (G25): it is planned on the water alone,
        # and this synthetic water, balanced with the recipe's salts, is out of balance alone.
        self.rejected('charge_imbalance', recipe=replace(self.args['recipe'], salts=()))
        self.rejected('missing_field', reagent_channel_id=' ')
        self.rejected('missing_field', water_totals=None)
        self.rejected('invalid_type', analytical_water_totals=[])
        self.rejected('invalid_totals', analytical_water_totals={'unknown-component': 0.1})
        self.rejected('invalid_type', maximum_reagent_volume=0.1)

    def test_balanced_record_refuses_conflicting_analytical_inventory(self):
        balanced = balance_water_analysis({'Na+': 0.001, 'Cl-': 0.001, 'CO3-2': 0}, measured_ph=7)
        self.rejected(
            'contradictory_water_inputs',
            water_totals=balanced,
            analytical_water_totals={'Na+': 0.002},
        )

    def test_supplied_analytical_inventory_is_retained_separately(self):
        plan = plan_equilibrium_delivery(
            **(self.args | {'analytical_water_totals': dict(self.args['water_totals'])})
        )
        self.assertEqual(plan.audit['analyticalWaterTotalsMolal'], self.args['water_totals'])

    def test_inconsistent_batch_mass_is_rejected_before_chemistry(self):
        recipe = self.args['recipe']
        salt = recipe.salts[0]
        wrong = replace(salt, mass=MassGrams(salt.mass.value * 2))
        self.rejected(
            'inconsistent_recipe', recipe=replace(recipe, salts=(wrong, *recipe.salts[1:]))
        )

    def test_consistent_balanced_record_preserves_the_analytical_water(self):
        from tests.test_analytical_water import measured_at_own_ph

        water = self.args['water_totals'] | {'CO3-2': 0}
        balanced = balance_water_analysis(water, measured_ph=measured_at_own_ph(water))
        plan = plan_equilibrium_delivery(
            **(self.args | {'water_totals': balanced, 'analytical_water_totals': water})
        )
        self.assertEqual(plan.audit['analyticalWaterTotalsMolal'], water)
        self.assertEqual(plan.audit['waterTotalsMolal'], balanced.totals)

    def test_low_residual_bicarbonate_is_reported_without_crop_advice(self):
        from flahax.aqueous_model import solve
        from flahax.product_conversion import catalogue_dose_totals

        # Synthetic complete electrolyte; close its stated chloride against the
        # initial mixed state just as the existing delivery fixture does.
        water = self.args['water_totals'] | {'CO3-2': 0.001}
        totals = catalogue_dose_totals({'Potassium Carbonate': 0.01, 'Potassium Nitrate': 0.02})
        for _ in range(8):
            mixed = dict(totals)
            for key, value in water.items():
                mixed[key] = mixed.get(key, 0) + value
            water['Cl-'] += solve(mixed, self.args['initial_ph']).charge_balance
        self.assertGreater(water['Cl-'], 0)
        plan = plan_equilibrium_delivery(
            **(self.args | {'water_totals': water, 'maximum_concentrations': {'N_NO3': 100}})
        )
        self.assertLess(plan.audit['residualBicarbonateMmolPerKg'], 0.5)
        self.assertFalse(any('Residual bicarbonate' in warning for warning in plan.warnings))
        self.assertAlmostEqual(
            plan.audit['residualBicarbonateMmolPerKg'],
            1000 * plan.equilibrium.target.species.get('HCO3-', 0.0),
        )


class DeliveryRecordBoundaryTests(unittest.TestCase):
    """Malformed saved inputs must fail with stable public error codes."""

    def test_record_field_failures(self):
        from flahax import validate_delivery_request
        from tests.test_delivery_contracts import request

        cases = [
            (('schemaVersion',), '9', 'unsupported_schema'),
            (('waterAnalysis',), None, 'missing_field'),
            (('waterAnalysis',), [], 'invalid_type'),
            (('waterAnalysis', 'schemaVersion'), '9', 'unsupported_schema'),
            (('waterAnalysis', 'id'), None, 'missing_field'),
            (('waterAnalysis', 'source'), ' ', 'invalid_value'),
            (('waterAnalysis', 'recordedAt'), 'yesterday', 'invalid_value'),
            (('waterAnalysis', 'temperatureC'), None, 'missing_field'),
            (('waterAnalysis', 'temperatureC'), True, 'invalid_type'),
            (('waterAnalysis', 'temperatureC'), [], 'invalid_type'),
            (('waterAnalysis', 'temperatureC'), float('nan'), 'invalid_value'),
            (('waterAnalysis', 'pH'), -1, 'out_of_range'),
            (('waterAnalysis', 'pH'), 15, 'out_of_range'),
            (('waterAnalysis', 'ions'), {'unknown': 1}, 'invalid_ions'),
            (('products',), None, 'missing_field'),
            (('products', 0, 'kind'), 'unknown', 'invalid_value'),
            (('products', 0, 'elements'), {}, 'missing_field'),
            (('products', 0, 'elements'), {'unknown': 1}, 'unknown_ion'),
            (('products', 0, 'elements'), {'K': 101}, 'out_of_range'),
            (('products', 0, 'elements'), {'K': 60, 'Ca': 50}, 'out_of_range'),
            (('products', 0, 'densityKgPerL'), 0, 'out_of_range'),
            (('products', 0, 'normalityMeqPerL'), 0, 'out_of_range'),
            (('compatibilityRules', 0, 'productIds'), ['a'], 'invalid_value'),
            (('compatibilityRules', 0, 'productIds'), ['a', 'a'], 'invalid_value'),
            (('compatibilityRules', 0, 'constraint'), 'mix', 'invalid_value'),
            (('solubilityLimits', 0, 'temperatureMaxC'), 0, 'out_of_range'),
            (('solubilityLimits', 0, 'maxGramsPerLitre'), 0, 'out_of_range'),
            (('titrationCurves', 0, 'points'), [], 'invalid_value'),
            (('titrationCurves', 0, 'points', 1, 'pH'), 15, 'out_of_range'),
            (('titrationCurves', 0, 'points', 1, 'pH'), 7.4, 'invalid_value'),
            (('pumpCalibrations', 0, 'flowLitresPerMinute'), 0, 'out_of_range'),
            (('pumpCalibrations', 0, 'stockDensityKgPerL'), 0, 'out_of_range'),
        ]
        for path, value, code in cases:
            with self.subTest(path=path, value=value):
                payload = request()
                target = payload
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                with self.assertRaises(DeliveryError) as caught:
                    validate_delivery_request(payload)
                self.assertEqual(caught.exception.code, code)

    def test_optional_water_measurements_remain_absent(self):
        from flahax import validate_delivery_request
        from tests.test_delivery_contracts import request

        payload = request()
        del payload['waterAnalysis']['pH']
        del payload['waterAnalysis']['alkalinityMgLAsCaCO3']
        result = validate_delivery_request(payload)['waterAnalysis']
        self.assertNotIn('pH', result)
        self.assertNotIn('alkalinityMgLAsCaCO3', result)
        self.assertEqual(result['ions'], {'Ca': 20})

    def test_titration_direction_is_consistent_for_acid_and_base(self):
        from flahax import validate_delivery_request
        from tests.test_delivery_contracts import request

        for ph_values in ((8, 7, 6), (6, 7, 8)):
            payload = request()
            points = [dict(demandMeqPerL=i, pH=ph) for i, ph in enumerate(ph_values)]
            payload['titrationCurves'][0]['points'] = points
            result = validate_delivery_request(payload)
            self.assertEqual(result['titrationCurves'][0]['points'], points)
            points[2]['pH'] = ph_values[0]
            with self.assertRaises(DeliveryError) as caught:
                validate_delivery_request(payload)
            self.assertEqual(caught.exception.code, 'invalid_value')


class PublicCalculationBoundaryTests(unittest.TestCase):
    def assert_code(self, code, function, *args, **kwargs):
        with self.assertRaises(DeliveryError) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_calculated_ph_rejects_malformed_analytical_values(self):
        from flahax.calculated_ph import calculate_equilibrium_ph

        defaults = dict(totals={}, complete_analysis=True, carbon_boundary='closed', phases=[])
        cases = [(dict(totals=[]), 'invalid_totals')]
        cases += [(dict(temperature_c=x), 'temperature_out_of_range') for x in (True, 24)]
        cases += [
            (dict(totals={'Na+': x}), 'invalid_totals') for x in (True, '1', -1, float('nan'))
        ]
        for override, code in cases:
            with self.subTest(override=override):
                self.assert_code(code, calculate_equilibrium_ph, **(defaults | override))

    def test_manufacturer_ec_requires_named_product_mapping(self):
        from flahax.calculated_ec import estimate_manufacturer_ec

        self.assert_code('invalid_type', estimate_manufacturer_ec, [])
        for key in (' ', 1):
            self.assert_code('invalid_value', estimate_manufacturer_ec, {key: 1})

    # Catalogue v0.0: re-enable in PR 4 (G5)
    def test_catalogue_chemistry_identity_and_inventory_boundaries(self):
        self.enterContext(historical_catalogue())
        from flahax import load_library
        from flahax.catalogue_chemistry import (
            PRODUCT_CHEMISTRY,
            ProductChemistry,
            assert_catalogue_coverage,
            chemistry_for_product,
        )

        products = load_library()['salts']
        self.assertEqual(len(PRODUCT_CHEMISTRY), len(products))
        self.assert_code('unsupported_product_chemistry', chemistry_for_product, 'not a product')
        self.assert_code('catalogue_chemistry_mismatch', assert_catalogue_coverage, products[:-1])
        for field in ('name', 'family', 'components', 'source_profile'):
            fields = dict(name='salt', family='salt', components=('Na+',), source_profile='test')
            fields[field] = () if field == 'components' else ''
            self.assert_code('missing_field', ProductChemistry, **fields)

    def test_incidental_sources_do_not_invent_unavailable_product_data(self):
        from flahax.nutrient_acceptance import assessed_limits, name_sources

        limits = assessed_limits({'Cl': 0}, {'ammoniumLimit': {'mgPerL': 2}})
        self.assertEqual(limits, {'Cl': 0, 'N_NH4': 2})
        assessment = {'incidentalContributions': [{'symbol': 'Na'}]}
        result = name_sources(assessment, [{'id': 'missing'}], [], {'Na': 1})
        self.assertEqual(result['incidentalContributions'][0]['source'], ['water'])

    def test_batch_recipe_requires_complete_typed_salt_records(self):
        from flahax import final_solution_recipe, VolumeLitres

        valid = dict(feasible=True, salts=[dict(id='k', name='salt', gramsPerLitre=1)])
        cases = [
            (None, 'invalid_type'),
            ({}, 'missing_field'),
            (dict(valid, salts=[None]), 'invalid_type'),
            (dict(valid, salts=valid['salts'] * 2), 'invalid_value'),
            (dict(valid, feasible=1), 'missing_field'),
        ]
        for field in ('id', 'name'):
            for value in (None, ' '):
                cases.append(
                    (
                        dict(valid, salts=[dict(valid['salts'][0], **{field: value})]),
                        'missing_field',
                    )
                )
        for payload, code in cases:
            with self.subTest(payload=payload):
                self.assert_code(code, final_solution_recipe, payload, VolumeLitres(1))
        self.assert_code('invalid_type', final_solution_recipe, valid, 1)

    def test_reagent_accounting_rejects_wrong_units_and_unknown_ions(self):
        from flahax import VolumeLitres, elemental_contribution, rescore_with_reagent

        for args, code in [
            ((1, {'K': 0.1}, VolumeLitres(1)), 'invalid_type'),
            ((MassGrams(1), {'K': 0.1}, 1), 'invalid_type'),
            ((MassGrams(1), {}, VolumeLitres(1)), 'missing_field'),
            ((MassGrams(1), {'unknown': 0.1}, VolumeLitres(1)), 'unknown_ion'),
        ]:
            self.assert_code(code, elemental_contribution, *args)
        for args, code in [
            ((None, {}, {}), 'invalid_ions'),
            (({}, {}, []), 'invalid_type'),
            (({}, {}, {'unknown': 1}), 'unknown_ion'),
            (({}, {}, {'K': 1}), 'invalid_type'),
        ]:
            self.assert_code(code, rescore_with_reagent, *args)

    def test_measured_titration_input_boundaries(self):
        from flahax import VolumeLitres, plan_ph, alkalinity_meq_per_litre
        from tests.test_ph_planning import inputs

        self.assert_code('invalid_type', alkalinity_meq_per_litre, 50)
        for target, code in [
            (True, 'invalid_type'),
            ([], 'invalid_type'),
            (-1, 'out_of_range'),
            (float('nan'), 'invalid_value'),
        ]:
            self.assert_code(
                code, plan_ph, *inputs(), target, VolumeLitres(100), VolumeLitres(1), {}, {}
            )
        for index in (4, 5):
            args = [*inputs(), 6.7, VolumeLitres(100), VolumeLitres(1), {}, {}]
            args[index] = 1
            self.assert_code('invalid_type', plan_ph, *args)
        for field, value, code in [
            ('id', 'other', 'mismatched_record'),
            ('kind', 'fertilizer', 'invalid_value'),
            ('densityKgPerL', None, 'missing_measurement'),
        ]:
            water, curve, reagent = inputs()
            if value is None:
                del reagent[field]
            else:
                reagent[field] = value
            self.assert_code(
                code,
                plan_ph,
                water,
                curve,
                reagent,
                6.7,
                VolumeLitres(100),
                VolumeLitres(1),
                {},
                {},
            )
        water, curve, reagent = inputs()
        endpoint = plan_ph(water, curve, reagent, 7.4, VolumeLitres(100), VolumeLitres(1), {}, {})
        self.assertEqual(endpoint.demand.value, 0)
        curve['points'].append(dict(demandMeqPerL=2, pH=5))
        later = plan_ph(water, curve, reagent, 5.5, VolumeLitres(100), VolumeLitres(1), {}, {})
        self.assertAlmostEqual(later.demand.value, 1.6)


class MeasuredWaterBoundaryTests(unittest.TestCase):
    def test_invalid_measurements_are_rejected_before_reconciliation(self):
        from tests.test_measured_water import STATION_104, WITHOUT_CARBON

        cases = [
            (dict(totals=[]), 'invalid_totals'),
            (dict(phases='Calcite'), 'invalid_type'),
            (dict(below_detection={'Na+': 0}), 'invalid_value'),
            (dict(below_detection={'unknown': 1}), 'invalid_value'),
            (dict(totals=WITHOUT_CARBON, alkalinity_eq_per_kg=float('nan')), 'invalid_value'),
            (dict(balance_ion_uncertainty_percent=0), 'invalid_value'),
            (dict(balance_ion='NO3-'), 'unsupported_balance_ion'),
        ]
        cases += [
            (dict(totals={'Na+': x}), 'invalid_totals') for x in (True, [], -1, float('inf'))
        ]
        for override, code in cases:
            with self.subTest(override=override):
                with self.assertRaises(DeliveryError) as caught:
                    balance_water_analysis(
                        **(dict(totals=STATION_104, measured_ph=7.8) | override)
                    )
                self.assertEqual(caught.exception.code, code)


class TerminalWidgetBoundaryTests(unittest.TestCase):
    def test_list_endpoints_toggle_and_empty_filter(self):
        from flahax.mix_tui import Question, handle, frame, Wizard
        from tests.test_mix_tui import UTF8, plain

        q = Question('ticks', 'Products', ['First', 'Last'])
        q = handle(q, 'END')
        self.assertEqual(q.selected, 1)
        q = handle(q, ' ')
        self.assertEqual(q.ticked, [1])
        self.assertIn('1 ticked: Last', '\n'.join(plain(frame(Wizard(), q, 100, 30, UTF8))))
        q = handle(q, ' ')
        self.assertEqual(q.ticked, [])
        q = handle(q, 'HOME')
        self.assertEqual(q.selected, 0)
        q.query = 'missing'
        q = handle(q, 'TAB')
        self.assertEqual(q.ticked, [])
        q = handle(q, 'F1')
        self.assertFalse(q.done)
        field = Question('field', 'Name')
        self.assertEqual(handle(field, 'F1').text, '')
        choice = Question('choice', 'Name', ['First'])
        self.assertFalse(handle(choice, 'F1').done)

    def test_tick_selection_and_small_screen_quit(self):
        from flahax.mix_tui import TuiPrompts, Question
        from tests.test_mix_tui import FakeTerm, UTF8

        prompt = TuiPrompts(FakeTerm([' ', 'ENTER']), UTF8)
        self.assertEqual(prompt.pick_many('Products', ['First']), [0])
        for confirm in (False, True):
            prompt = TuiPrompts(FakeTerm(['q'], sizes=((10, 5),)), UTF8)
            with self.assertRaises(KeyboardInterrupt):
                if confirm:
                    prompt._confirm_quit(None)
                else:
                    prompt._run(Question('field', 'Name'))

    def test_rows_clip_excess_segments_and_unknown_result_keys_are_ignored(self):
        from flahax.mix_tui import paint
        from flahax.mix_results import handle_results
        from tests.test_mix_tui import UTF8, plain

        self.assertEqual(plain([paint([('abc', None), ('hidden', None)], 3, UTF8)])[0], 'abc')
        self.assertEqual(handle_results(1, 2, 'F1'), (1, 2, False))


class AcidOptionBoundaryTests(unittest.TestCase):
    def test_invalid_requests_and_unbalanced_inputs_fail_closed(self):
        from flahax import plan_acid_options
        from tests.test_water_workflow import AcidSelectionTests

        defaults = AcidSelectionTests().arguments()
        cases = [
            (dict(initial_ph=float('nan')), 'out_of_range'),
            (dict(targets={}), 'missing_field'),
            (dict(products=[]), 'missing_field'),
            (dict(products=[None]), 'invalid_value'),
            (dict(products=defaults['products'] * 2), 'invalid_value'),
            (dict(phases='Calcite'), 'invalid_type'),
            (dict(totals={'Na+': 0.002}), 'charge_imbalance'),
        ]
        for override, code in cases:
            with self.subTest(override=override):
                with self.assertRaises(DeliveryError) as caught:
                    plan_acid_options(**(defaults | override))
                self.assertEqual(caught.exception.code, code)

    def test_unsupported_reagent_and_explicit_dose_cap_return_rejected_candidates(self):
        from flahax import plan_acid_options
        from tests.test_water_workflow import AcidSelectionTests

        args = AcidSelectionTests().arguments()
        bad = dict(args['products'][0], chemicalFormula='HCl')
        unsupported = plan_acid_options(**(args | dict(products=[bad])))
        self.assertIsNone(unsupported.selected_product_id)
        self.assertEqual(unsupported.candidates[0].error_code, 'unsupported_reagent')
        limited = plan_acid_options(**(args | dict(maximum_reagent_volume_litres=1e-20)))
        self.assertIsNone(limited.selected_product_id)
        self.assertTrue(all(c.error_code == 'dose_limit_exceeded' for c in limited.candidates))


class CommandBoundaryTests(unittest.TestCase):
    def test_interactive_read_failure_and_wrong_command_have_clear_diagnostics(self):
        from contextlib import redirect_stderr
        from io import StringIO
        from unittest.mock import patch
        from flahax.__main__ import main

        error = StringIO()
        with patch('sys.argv', ['flahax', 'workflow', '--interactive']), redirect_stderr(error):
            with patch('flahax.planning_cli.interactive', side_effect=EOFError('input ended')):
                self.assertEqual(main(), 1)
        self.assertIn('Invalid planning input: input ended', error.getvalue())
        with patch('sys.argv', ['flahax', '--interactive']), redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit) as caught:
                main()
        self.assertEqual(caught.exception.code, 2)

    def test_keyboard_json_reader_identifies_end_of_input_keys(self):
        from contextlib import redirect_stderr
        from io import StringIO
        from unittest.mock import patch
        from flahax.__main__ import main

        stream = StringIO('invalid json')
        stream.isatty = lambda: True
        error = StringIO()
        with (
            patch('sys.argv', ['flahax', 'recommend']),
            patch('sys.stdin', stream),
            redirect_stderr(error),
        ):
            self.assertEqual(main(), 1)
        self.assertIn('Ctrl+Z', error.getvalue())
        self.assertIn('Ctrl+D', error.getvalue())
        self.assertIn('Expected a JSON object', error.getvalue())


class RenderedResultBoundaryTests(unittest.TestCase):
    def test_unplanned_and_mass_only_reagents_remain_distinct(self):
        from flahax.grower_sheet import _reagent_card, _agronomist_section
        from flahax.mix_results import _tank_rows, _nutrient_rows
        from tests.test_mix_tui import UTF8

        # Synthetic rendering fixture; these values do not claim a qualified chemical solution.
        summary = dict(
            status='requires_review',
            ph=None,
            batch_litres=100,
            volumes={},
            tanks=dict(tanks=[], injection_ratio=100),
            solubility=[],
            formulation=dict(rows=[]),
            limits=[],
            warnings=[],
            water={'analysis_mg_per_litre': {}},
        )
        self.assertIn('pH was not planned', _reagent_card(summary, None))
        self.assertIn('pH was not planned', str(_tank_rows(summary, 100, UTF8)))
        chosen = dict(
            direction='acid',
            product='Synthetic reagent',
            formula='HNO3',
            volume_ml_per_batch=None,
            mass_g_per_batch=2,
            nutrient_contribution={'N_NO3': 1},
        )
        summary['ph'] = dict(selected=chosen, mixed_ph=7, target_ph=6)
        card = _reagent_card(summary, None)
        self.assertIn('2 g', card)
        self.assertNotIn('None mL', card)
        self.assertIn('after acid 6', _agronomist_section(summary))
        self.assertIn('1 mg/L', _agronomist_section(summary))
        self.assertIn('after acid 6', str(_nutrient_rows(summary)))


class TerminalNavigationRegressionTests(unittest.TestCase):
    def test_overscroll_then_up_moves_immediately_and_idle_input_is_harmless(self):
        from unittest.mock import patch
        from flahax.mix_tui import show_results
        from tests.test_mix_tui import FakeTerm, UTF8

        term = FakeTerm(['DOWN'] * 8 + [None, 'UP', 'q', 'n', 'q', 'y'])

        def bounded_view(s, view, width, height, scroll, g, output, message=None):
            return [str(min(scroll, 2)) if message is None else 'confirm']

        with patch('flahax.mix_results.first_view', return_value=0):
            with patch('flahax.mix_results.results_lines', side_effect=bounded_view):
                show_results(term, UTF8, {}, 'out')
        self.assertEqual(term.frames[-4:], [['1'], ['confirm'], ['1'], ['confirm']])

    def test_escape_while_calculating_can_decline_quit(self):
        from threading import Event
        from unittest.mock import patch
        from flahax.mix_tui import calculate, TuiPrompts
        from tests.test_mix_tui import FakeTerm, UTF8

        done = Event()
        term = FakeTerm(['ESC'])
        prompts = TuiPrompts(term, UTF8)
        prompts.say('')
        self.assertEqual(prompts.wizard.messages, [])

        def work():
            if not done.wait(2):
                raise AssertionError('confirmation did not release calculation')
            return 42

        with patch.object(prompts, '_confirm_quit', side_effect=lambda _: done.set()) as confirm:
            result, ahead = calculate(prompts, work)
        confirm.assert_called_once_with(None)
        self.assertEqual((result, ahead), (42, []))


class EngineInputBoundaryTests(unittest.TestCase):
    def test_empty_linear_system_and_zero_rank(self):
        from flahax.engine import _lstsq, nnls

        self.assertEqual(_lstsq([], [1]), [])
        self.assertEqual(nnls([], []), [])
        with self.assertRaisesRegex(ValueError, 'rank deficient'):
            _lstsq([[0]], [1])

    def test_conflicting_assay_is_rejected_or_excluded_and_targets_are_required(self):
        from flahax.engine import InputError, solve_weights, recommend

        bad = dict(id='bad', name='Bad assay', formula='KNO3', elements={'Ca': 1})
        with self.assertRaises(InputError):
            solve_weights([bad], {'Ca': 1})
        good = dict(id='good', name='Declared calcium', elements={'Ca': 10})
        result = recommend([bad, good], {'Ca': 1})
        self.assertTrue(result['feasible'])
        self.assertTrue(any(r['id'] == 'bad' for r in result['excluded']))
        with self.assertRaisesRegex(InputError, 'targets are required'):
            recommend([], {})


class WarmStartBoundaryTests(unittest.TestCase):
    def test_nonnegative_warm_start_can_drop_every_column(self):
        from flahax.engine import nnls

        self.assertEqual(nnls([[1]], [-1], x0=[1]), [0])
        self.assertEqual(nnls([[1]], [2], x0=[0]), [2])


class MultipleCeilingBoundaryTests(unittest.TestCase):
    def test_repeated_dual_bracket_updates_preserve_mass_and_hard_limits(self):
        import json
        from pathlib import Path
        from flahax import engine

        cases = json.loads(
            (Path(__file__).parent / 'fixtures/runtime/ceiling_inputs.json').read_text()
        )['cases']
        for case in cases:
            result = engine._fit_within(case['salts'], case['targets'], {}, 0, case['maxima'])
            self.assertTrue(all(g >= 0 for g in result['grams']))
            rows = {r['symbol']: r['final'] for r in result['rows']}
            for symbol in ('K', 'N_NO3', 'Na', 'Cl'):
                # Independent mass accounting: g/L * assay percent * 10 = mg/L.
                expected = sum(
                    g * salt['elements'][symbol] * 10
                    for g, salt in zip(result['grams'], case['salts'])
                )
                self.assertAlmostEqual(rows[symbol], expected, places=10)
            for symbol, cap in case['maxima'].items():
                self.assertLessEqual(rows[symbol], cap)

    def test_exhausted_ceiling_budget_does_not_hide_remaining_violations(self):
        from unittest.mock import patch
        import json
        from pathlib import Path
        from flahax import engine

        case = json.loads(
            (Path(__file__).parent / 'fixtures/runtime/ceiling_inputs.json').read_text()
        )['cases'][0]
        # Fault injection of a shortened internal budget tests the incomplete-result contract.
        with patch.object(engine, 'CEILING_STEPS', 1):
            result = engine._fit_within(case['salts'], case['targets'], {}, 0, case['maxima'])
        verdict = engine._report(result['rows'], result['grams'], [], case['maxima'])
        self.assertFalse(verdict['feasible'])
        self.assertTrue(verdict['limitViolations'])


class CeilingOverflowBoundaryTests(unittest.TestCase):
    def test_overflowing_interpolation_uses_a_finite_bracket_midpoint(self):
        import math
        from unittest.mock import patch
        from flahax import engine

        seen = []
        values = iter([1e308, 1e308, 0, 1 - engine.CEILING_MARGIN])

        def fitted(*args, **kwargs):
            if len(args) > 5:
                seen.append(args[5]['Na'][1])
            return dict(grams=[0], rows=[dict(symbol='Na', final=next(values))], loss=1)

        # Inject finite fit responses whose secant products overflow; preserve the safeguard.
        with patch.object(engine, '_fit', fitted):
            result = engine._fit_within([{}], {'K': 1}, {}, 0, {'Na': 1})
        self.assertTrue(all(math.isfinite(v) for v in seen))
        self.assertAlmostEqual(seen[-1] / -1e308, 0.5)
        self.assertEqual(result['rows'][0]['final'], 1 - engine.CEILING_MARGIN)
