# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Workflow stages preserve missing-input and rejection outcomes (#186)."""

import unittest
from flahax import DeliveryError, VolumeLitres, load_library, plan_fertilizer_workflow
from tests.test_ph_planning import inputs
from tests.test_ph_adjustment import RO, ACIDS
from tests.catalogue_history import historical_catalogue


class WorkflowBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.salts = [p for p in load_library()['salts'] if p['formula'] == 'KNO3']

    def workflow(self, **kw):
        args = dict(final_volume=VolumeLitres(100))
        args.update(kw)
        return plan_fertilizer_workflow(self.salts, {'K': 10}, {}, 6.5, **args)

    def test_invalid_ph_stage_shapes_and_volume_are_explicit(self):
        for ph in (True, float('nan'), -1, '6'):
            with self.assertRaises(DeliveryError) as caught:
                plan_fertilizer_workflow(self.salts, {'K': 10}, {}, ph)
            self.assertEqual(caught.exception.code, 'out_of_range')
        for key in ('equilibrium', 'nitric', 'titration', 'stocks', 'acids', 'ph_adjustment'):
            with self.assertRaises(DeliveryError) as caught:
                self.workflow(**{key: []})
            self.assertEqual(caught.exception.code, 'invalid_type')
        with self.assertRaises(DeliveryError) as caught:
            self.workflow(final_volume=100)
        self.assertEqual(caught.exception.code, 'invalid_type')

    def test_stages_without_final_volume_request_it(self):
        water, curve, reagent = inputs()
        result = self.workflow(
            final_volume=None,
            equilibrium=RO,
            titration=dict(
                water_analysis=water,
                curve=curve,
                reagent=reagent,
                maximum_reagent_volume=VolumeLitres(1),
            ),
            stocks=dict(
                injection_ratio=100,
                tanks=[],
                compatibility_rules=[],
                solubility_limits=[],
                temperature=25,
            ),
        )
        for stage in ('chemistry', 'titration', 'stocks'):
            self.assertEqual(result.stages[stage].status, 'needs_input')
            self.assertEqual(result.stages[stage].required_inputs, ('final_volume',))

    def test_dependent_reagents_do_not_run_without_chemistry(self):
        result = self.workflow(
            nitric=dict(
                reagent={},
                reagent_channel_id='acid',
                maximum_reagent_volume=VolumeLitres(1),
                maximum_nutrient_error_percent=1,
            ),
            acids=dict(
                products=ACIDS, maximum_nutrient_error_percent=1, maximum_reagent_volume_litres=1
            ),
        )
        for stage in ('nitric', 'acid_selection'):
            self.assertEqual(result.stages[stage].status, 'blocked')
            self.assertEqual(result.stages[stage].error_code, 'chemistry_required')

    def test_invalid_water_basis_is_a_blocked_chemistry_stage(self):
        for change, code in [
            ({'water_analysis_id': ''}, 'missing_field'),
            ({'water_balance': {}}, 'invalid_type'),
            ({'measured_ph': 7, 'complete_analysis': False}, 'incomplete_water_analysis'),
            ({'measured_ph': 7, 'carbon_boundary': 'open'}, 'unsupported_carbon_boundary'),
        ]:
            result = self.workflow(equilibrium=RO | {'water_mass_kg': 100} | change)
            self.assertEqual(result.stages['chemistry'].status, 'blocked')
            self.assertEqual(result.stages['chemistry'].error_code, code)

    def test_titration_input_identity_and_infeasible_recipe_block(self):
        water, curve, reagent = inputs()
        config = dict(
            water_analysis=water,
            curve=curve,
            reagent=reagent,
            maximum_reagent_volume=VolumeLitres(1),
        )
        for supplied, code in [([], 'invalid_type'), (water, 'inconsistent_water_analysis')]:
            result = self.workflow(titration=config | {'water_analysis': supplied})
            self.assertEqual(result.stages['titration'].error_code, code)
        # G25: a K maximum of 0 forces a K shortfall, a reported deviation, not a block.
        result = self.workflow(titration=config, maximum_concentrations={'K': 0})
        self.assertEqual(result.stages['formulation'].status, 'requires_review')
        self.assertEqual(result.stages['formulation'].message, 'targets missed: K -100 %')
        self.assertEqual(result.stages['titration'].error_code, 'inconsistent_water_analysis')
        # Only a broken declared maximum blocks: water sodium 5 mg/L above a 1 mg/L maximum.
        result = plan_fertilizer_workflow(
            self.salts,
            {'K': 10},
            {'Na': 5},
            6.5,
            final_volume=VolumeLitres(100),
            titration=config,
            maximum_concentrations={'Na': 1},
        )
        self.assertEqual(result.stages['titration'].error_code, 'infeasible_recipe')
        self.assertEqual(
            result.stages['titration'].message,
            'Na would be 5 mg/L, above the declared maximum 1 mg/L',
        )

    def test_titration_nutrient_tolerance_and_maximum_are_checked_after_dosing(self):
        water, curve, reagent = inputs()
        config = dict(
            water_analysis=water,
            curve=curve,
            reagent=reagent,
            maximum_reagent_volume=VolumeLitres(1),
        )
        for targets, changes, expected in [
            (
                {'K': 10},
                {'titration': config | {'maximum_nutrient_error_percent': 0}},
                'invalid_value',
            ),
            ({'K': 10}, {'maximum_concentrations': {'N_NO3': 5}}, 'nutrient_limit_exceeded'),
            # The reagent's own nitrate moves N_NO3 by more than a declared 1 % (G25).
            (
                {'N_NO3': 10},
                {'titration': config | {'maximum_nutrient_error_percent': 1}},
                'nutrient_tolerance_exceeded',
            ),
            # No percent declared: no chosen-number gate, the reagent's nitrate is reported.
            ({'N_NO3': 10}, {}, None),
        ]:
            kwargs = dict(titration=config, final_volume=VolumeLitres(100)) | changes
            result = plan_fertilizer_workflow(self.salts, targets, water['ions'], 6.5, **kwargs)
            self.assertEqual(result.stages['titration'].error_code, expected)

    def test_titration_never_blocks_on_a_deviation_the_formulation_accepts(self):
        # G25: the titration stage judges only the change its reagent makes.
        water, curve, reagent = inputs()
        config = dict(
            water_analysis=water,
            curve=curve,
            reagent=reagent,
            maximum_reagent_volume=VolumeLitres(1),
        )
        library = load_library()
        lettuce = {f['name']: f['targets'] for f in library['formulas']}['Lettuce 2 (Howard Resh)']
        cases = [
            (self.salts, {'K': 10}, {'K': 0}, config),  # K -100 %
            (self.salts, {'K': 10}, {'K': 0}, config | {'maximum_nutrient_error_percent': 1}),
            (library['salts'], lettuce, None, config),  # N_NO3 -5.98 %, Ca +4.81 % ...
        ]
        for salts, targets, maxima, titration in cases:
            with self.subTest(targets=sorted(targets), maxima=maxima):
                result = plan_fertilizer_workflow(
                    salts,
                    targets,
                    water['ions'],
                    6.0,
                    final_volume=VolumeLitres(100),
                    titration=titration,
                    maximum_concentrations=maxima,
                )
                self.assertEqual(result.stages['formulation'].status, 'requires_review')
                stage = result.stages['titration']
                self.assertIn(stage.status, ('calculated', 'requires_review'), stage.message)
                self.assertIsNone(stage.error_code)


class GradeIdentityBoundaryTests(unittest.TestCase):
    def test_graded_records_cannot_replace_identity_or_assay(self):
        from flahax.fertilizer_workflow import _graded
        from tests import test_materials as fixtures

        library = {p['id']: p for p in load_library()['salts']}
        compound, _ = fixtures.DeclaredCompoundTests().product()
        single, _ = fixtures.WorkflowGradeTests().graded(0.97)
        for product in (
            compound | {'id': 'wrong'},
            single | {'name': 'unknown'},
            single | {'formula': 'KNO3'},
        ):
            with self.assertRaises(DeliveryError) as caught:
                _graded(product, library)
            self.assertEqual(caught.exception.code, 'product_chemistry_mismatch')

    def test_water_basis_review_applies_to_every_completed_stage(self):
        from types import SimpleNamespace
        from flahax.fertilizer_workflow import _review_water_basis, WorkflowStage
        from flahax.measured_water import balance_water_analysis
        from tests.test_measured_water import STATION_104

        balanced = balance_water_analysis(STATION_104, measured_ph=7.8)
        # Synthetic boundary case: balanced Na would cross a laboratory decision.
        row = dict(symbol='Na', target=None, final=1, deltaPct=None)
        value = SimpleNamespace(rows=[row])
        chemistry = dict(
            water_balance=balanced,
            analytical_water_totals={'Na+': 0.00001},
            water_totals={'Na+': 0.0001},
            water_analysis_id='synthetic',
        )
        selected = SimpleNamespace(recommendation={'rows': [row]})
        output = SimpleNamespace(
            recommendation={'rows': [row]},
            stages={
                'formulation': WorkflowStage('calculated'),
                'chemistry': WorkflowStage('calculated', value=chemistry),
                'nitric': WorkflowStage('calculated', value=value),
                'titration': WorkflowStage('blocked', value=value),
                'ph_adjustment': WorkflowStage(
                    'calculated', value=SimpleNamespace(selected=selected)
                ),
            },
        )
        _review_water_basis(output, 1, 1, {'Na': 1.5})
        self.assertEqual(output.water_basis['decisionBasis'], 'laboratory analysis')
        self.assertEqual(
            set(output.water_basis['findings']),
            {'formulation', 'nitric', 'titration', 'ph_adjustment'},
        )
        for name in ('formulation', 'nitric', 'ph_adjustment'):
            self.assertEqual(output.stages[name].status, 'requires_review')
        self.assertEqual(output.stages['titration'].status, 'blocked')


class BalancedConfigurationBoundaryTests(unittest.TestCase):
    def test_prepared_balance_cannot_be_relabelled_incomplete_or_open_carbon(self):
        from flahax.measured_water import balance_water_analysis
        from tests.test_measured_water import STATION_104

        balance = balance_water_analysis(STATION_104, measured_ph=7.8)
        pool = [p for p in load_library()['salts'] if p['formula'] == 'KNO3']
        for change in ({'complete_analysis': False}, {'carbon_boundary': 'open'}):
            config = RO | dict(water_balance=balance, water_totals=balance.analytical_totals)
            result = plan_fertilizer_workflow(
                pool,
                {'K': 10},
                {},
                6.5,
                final_volume=VolumeLitres(1000),
                equilibrium=config | change,
            )
            self.assertEqual(result.stages['chemistry'].error_code, 'contradictory_water_inputs')


class WorkflowAcceptanceBoundaryTests(unittest.TestCase):
    # Owner catalogue: re-enable in PR 4 (G5)
    def setUp(self):
        self.enterContext(historical_catalogue())
        self.pool = [p for p in load_library()['salts'] if p['formula'] == 'KNO3']
        self.config = RO | {'water_mass_kg': 100}

    # Owner catalogue: re-enable in PR 4 (G5)
    def test_no_acceptable_acid_and_infeasible_nutrients_stay_blocked(self):
        self.enterContext(historical_catalogue())
        config = dict(
            products=ACIDS, maximum_nutrient_error_percent=1, maximum_reagent_volume_litres=1e-20
        )
        # Only a broken declared maximum (water sodium 46 mg/L above 10 mg/L) blocks with
        # infeasible_recipe (G25).
        sodium = 0.002 * 22.98977 * 1000  # Na+ 0.002 mol/kg, as in the chemistry water
        salty = self.config | dict(water_totals={'Na+': 0.002, 'CO3-2': 0.001})
        for water, equilibrium, maxima, expected in [
            ({}, self.config, None, 'no_acceptable_acid'),
            ({'Na': sodium}, salty, {'Na': 10}, 'infeasible_recipe'),
        ]:
            flow = plan_fertilizer_workflow(
                self.pool,
                {'K': 10},
                water,
                6.5,
                final_volume=VolumeLitres(100),
                equilibrium=equilibrium,
                acids=config,
                maximum_concentrations=maxima,
            )
            self.assertEqual(flow.stages['acid_selection'].error_code, expected)

    def candidates(self, targets, percent, maxima=None):
        acids = dict(products=ACIDS, maximum_reagent_volume_litres=1)
        if percent is not None:
            acids['maximum_nutrient_error_percent'] = percent
        return plan_fertilizer_workflow(
            self.pool,
            targets,
            {},
            6.5,
            final_volume=VolumeLitres(100),
            equilibrium=self.config,
            acids=acids,
            maximum_concentrations=maxima,
        ).stages['acid_selection']

    def codes(self, stage):
        return {c.product_id: c.error_code for c in stage.value.candidates}

    def test_acid_selection_judges_only_the_change_the_acid_makes(self):
        # G25: K -100 % (forced by a K maximum of 0) is the recipe's deviation, not the acid's.
        for percent in (None, 1):
            stage = self.candidates({'K': 10}, percent, {'K': 0})
            self.assertEqual(self.codes(stage), {'HNO3-example': None, 'H3PO4-example': None})
        # K 10 with N_NO3 5 misses both by more than 1 %; with a declared 1 % the acids pass
        # (nitric adds 0.0033 mg/L N_NO3, 0.067 % of 5), with a declared 0.01 % nitric fails.
        stage = self.candidates({'K': 10, 'N_NO3': 5}, 1)
        self.assertEqual(self.codes(stage), {'HNO3-example': None, 'H3PO4-example': None})
        stage = self.candidates({'K': 10, 'N_NO3': 5}, 0.01)
        self.assertEqual(
            self.codes(stage),
            {'HNO3-example': 'nutrient_tolerance_exceeded', 'H3PO4-example': None},
        )
        # Nitric pushes N_NO3 from 3.5831 past a declared 3.5833 mg/L maximum.
        stage = self.candidates({'K': 10}, None, {'N_NO3': 3.5833})
        self.assertEqual(self.codes(stage)['HNO3-example'], 'nutrient_limit_exceeded')

    def nitric(self, targets, percent, maxima=None):
        from tests.test_ph_planning import record

        config = dict(
            reagent=record(
                'nitric',
                kind='acid',
                name='Nitric',
                chemicalFormula='HNO3',
                elements={'N_NO3': 13.8},
                densityKgPerL=1.4,
            ),
            reagent_channel_id='acid',
            maximum_reagent_volume=VolumeLitres(1),
        )
        if percent is not None:
            config['maximum_nutrient_error_percent'] = percent
        return plan_fertilizer_workflow(
            self.pool,
            targets,
            {},
            6.5,
            final_volume=VolumeLitres(100),
            equilibrium=self.config,
            nitric=config,
            maximum_concentrations=maxima,
        ).stages['nitric']

    def test_nitric_judges_only_the_change_the_acid_makes(self):
        # K 10 with N_NO3 5 misses both by more than 1 % (G25): not the nitric acid's doing.
        for percent in (None, 1):
            stage = self.nitric({'K': 10, 'N_NO3': 5}, percent)
            self.assertIn(stage.status, ('calculated', 'requires_review'), stage.message)
            self.assertIsNone(stage.error_code)
        stage = self.nitric({'K': 10, 'N_NO3': 5}, 0.01)
        self.assertEqual(
            (stage.status, stage.error_code), ('blocked', 'nutrient_tolerance_exceeded')
        )
        stage = self.nitric({'K': 10}, None, {'N_NO3': 3.5833})
        self.assertEqual((stage.status, stage.error_code), ('blocked', 'nutrient_limit_exceeded'))

    def test_nitric_plans_on_water_alone_when_the_accepted_recipe_is_empty(self):
        # K maximum 0: no product may be dosed, the formulation stage accepts the empty recipe
        # with K -100 % reported, and the nitric stage plans on the water alone (G25).
        stage = self.nitric({'K': 10}, None, {'K': 0})
        self.assertIn(stage.status, ('calculated', 'requires_review'), stage.message)
        self.assertIsNone(stage.error_code)
        self.assertEqual(stage.value.audit['productDosesGPerKgWater'], {})
        self.assertGreater(stage.value.reagent_mass.value, 0)
        self.assertLessEqual(abs(stage.value.equilibrium.target.ph - 6.5), 1e-4)

    def test_a_declared_error_percent_must_be_positive_in_every_stage(self):
        for percent in (0, -1, float('nan'), True):
            with self.subTest(percent=percent):
                for stage in (
                    self.candidates({'K': 10}, percent),
                    self.nitric({'K': 10}, percent),
                ):
                    self.assertEqual(
                        (stage.status, stage.error_code), ('blocked', 'invalid_value')
                    )
                    self.assertEqual(
                        stage.message, 'maximum_nutrient_error_percent must be finite and positive'
                    )

    # Owner catalogue: re-enable in PR 4 (G5)
    def test_nitric_incidental_nutrients_are_not_automatically_accepted(self):
        self.enterContext(historical_catalogue())
        from tests.test_ph_planning import record

        config = dict(
            reagent=record(
                'nitric',
                kind='acid',
                name='Nitric',
                chemicalFormula='HNO3',
                elements={'N_NO3': 13.8},
                densityKgPerL=1.4,
            ),
            reagent_channel_id='acid',
            maximum_reagent_volume=VolumeLitres(1),
            maximum_nutrient_error_percent=1,
        )
        flow = plan_fertilizer_workflow(
            self.pool,
            {'K': 10},
            {},
            6.5,
            final_volume=VolumeLitres(100),
            equilibrium=self.config,
            nitric=config,
        )
        self.assertEqual(flow.stages['nitric'].status, 'requires_review')
        self.assertTrue(flow.stages['nitric'].value.incidental_assessment['requiresReview'])

    # Owner catalogue: re-enable in PR 4 (G5)
    def test_coupled_solver_failure_remains_blocked(self):
        self.enterContext(historical_catalogue())
        from unittest.mock import patch

        with patch(
            'flahax.fertilizer_workflow.plan_coupled_ph',
            side_effect=DeliveryError('nonconvergent', 'Injected coupled failure'),
        ):
            flow = plan_fertilizer_workflow(
                self.pool,
                {'K': 10},
                {},
                6.5,
                final_volume=VolumeLitres(100),
                equilibrium=self.config,
                ph_adjustment=dict(products=ACIDS, maximum_reagent_volume_litres=1),
            )
        self.assertEqual(flow.stages['ph_adjustment'].status, 'blocked')
        self.assertEqual(flow.stages['ph_adjustment'].error_code, 'nonconvergent')


class AssumedWaterReviewBoundaryTests(unittest.TestCase):
    # Owner catalogue: re-enable in PR 4 (G5)
    def test_accepted_reagent_on_assumed_water_closure_still_requires_review(self):
        self.enterContext(historical_catalogue())
        from flahax.measured_water import nutrient_mg_per_litre
        from tests.test_ph_planning import record

        totals = {'Na+': 0.001, 'Cl-': 0.00095, 'CO3-2': 0}
        pool = [p for p in load_library()['salts'] if p['formula'] == 'KNO3']
        config = RO | dict(water_totals=totals, measured_ph=7.8, water_mass_kg=100)
        nitric = dict(
            reagent=record(
                'nitric',
                kind='acid',
                name='Nitric',
                chemicalFormula='HNO3',
                elements={'N_NO3': 13.8},
                densityKgPerL=1.4,
            ),
            reagent_channel_id='acid',
            maximum_reagent_volume=VolumeLitres(1),
            maximum_nutrient_error_percent=1,
        )
        flow = plan_fertilizer_workflow(
            pool,
            {'K': 10},
            nutrient_mg_per_litre(totals, 100, 100),
            6.5,
            final_volume=VolumeLitres(100),
            equilibrium=config,
            nitric=nitric,
            acids=dict(
                products=ACIDS, maximum_nutrient_error_percent=1, maximum_reagent_volume_litres=1
            ),
            maximum_concentrations={'N_NO3': 20, 'Na': 50, 'Cl': 50, 'P': 1},
        )
        self.assertEqual(
            flow.stages['chemistry'].status, 'requires_review', flow.stages['chemistry']
        )
        for name in ('nitric', 'acid_selection'):
            self.assertEqual(flow.stages[name].status, 'requires_review')
            self.assertIsNotNone(flow.stages[name].value)


class FinalWorkflowVerificationTests(unittest.TestCase):
    def test_recipe_identity_is_rechecked_at_chemistry_boundary(self):
        from dataclasses import replace
        from unittest.mock import patch
        from flahax import fertilizer_workflow as workflow

        original = workflow.final_solution_recipe
        pool = [p for p in load_library()['salts'] if p['formula'] == 'KNO3']

        def changed(*args):
            recipe = original(*args)
            return replace(recipe, salts=(replace(recipe.salts[0], salt_id='missing'),))

        with patch.object(workflow, 'final_solution_recipe', changed):
            result = plan_fertilizer_workflow(
                pool,
                {'K': 10},
                {},
                6.5,
                final_volume=VolumeLitres(100),
                equilibrium=RO | {'water_mass_kg': 100},
            )
        self.assertEqual(result.stages['chemistry'].error_code, 'product_chemistry_mismatch')

    # Owner catalogue: re-enable in PR 4 (G5)
    def test_selected_plan_is_rechecked_for_hard_limits(self):
        self.enterContext(historical_catalogue())
        from copy import deepcopy
        from dataclasses import replace
        from unittest.mock import patch
        from tests import test_joint_workflow as fixtures

        plan = fixtures.JointWorkflowTests().positive_case().value
        candidate = plan.selected
        pool = [p for p in load_library()['salts'] if p['formula'] == 'KNO3']
        for exceeds in (False, True):
            recipe = deepcopy(candidate.recommendation)
            recipe['feasible'] = True
            for row in recipe['rows']:
                if row['symbol'] == 'Na' and exceeds:
                    row['final'] = 100
            selected = replace(candidate, status='accepted', recommendation=recipe)
            supplied = replace(plan, candidates=(selected,))
            with patch('flahax.fertilizer_workflow.plan_coupled_ph', return_value=supplied):
                flow = plan_fertilizer_workflow(
                    pool,
                    {'K': 100},
                    {'Na': 0.002 * 22.989769 * 1000},
                    5.8,
                    final_volume=VolumeLitres(1000),
                    equilibrium=RO | {'water_totals': {'Na+': 0.002, 'CO3-2': 0.002}},
                    maximum_concentrations={'Na': 50, 'N_NO3': 200},
                    ph_adjustment=dict(products=ACIDS, maximum_reagent_volume_litres=5),
                )
            stage = flow.stages['ph_adjustment']
            self.assertEqual(stage.status, 'blocked' if exceeds else 'calculated')
            if exceeds:
                self.assertEqual(stage.error_code, 'nutrient_limit_exceeded')
