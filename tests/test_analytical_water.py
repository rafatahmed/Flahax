# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""#84: targets and limits use the laboratory analysis; the charge-balanced water is chemistry
only."""

import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest

from flahax import (
    DeliveryError,
    VolumeLitres,
    balance_water_analysis,
    calculate_equilibrium_ph,
    catalogue_ph_reagents,
    load_library,
    plan_equilibrium_delivery,
    plan_fertilizer_workflow,
    render_batch_sheet,
    render_report,
    summarize_batch,
)
from flahax.batch_cli import main as batch
from flahax.measured_water import nutrient_mg_per_litre
from flahax.nutrient_acceptance import assess_water_basis
from flahax.planning_cli import serializable
from tests.catalogue_history import historical_catalogue
from tests.test_equilibrium_delivery import arguments
from tests.test_measured_water import STATION_104

# The pre-owner products and formulas these workflow tests were written against.
with historical_catalogue():
    LIBRARY = load_library()
PRODUCTS = LIBRARY['salts']
FORMULAS = {f['name']: f['targets'] for f in LIBRARY['formulas']}
CLOSED = dict(complete_analysis=True, carbon_boundary='closed', phases=[])


def measured_at_own_ph(totals):
    """A composition and the pH it actually has, as a laboratory would report it."""
    return calculate_equilibrium_ph(totals, **CLOSED).ph


def equilibrium(**water):
    return dict(
        water_mass_kg=1000, water_analysis_id='test-water', temperature_c=25, **CLOSED, **water
    )


class RecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = dict(STATION_104)
        cls.balanced = balance_water_analysis(
            cls.source, measured_ph=7.8, analysis_id='station-104'
        )

    def test_the_laboratory_analysis_is_kept_unchanged(self):
        b = self.balanced
        self.assertEqual(b.analytical_totals, STATION_104)
        self.assertNotEqual(b.totals['Cl-'], STATION_104['Cl-'])
        self.source['Cl-'] = 0.0  # a later edit of the caller's dict
        self.assertEqual(b.analytical_totals['Cl-'], STATION_104['Cl-'])
        self.assertEqual(serializable(b)['analytical_totals'], STATION_104)
        self.assertEqual(b.analytical_mg_per_litre()['Cl'], STATION_104['Cl-'] * 35.45e3)
        self.assertEqual(
            (b.analysis_id, b.units, b.reconciliation), ('station-104', 'mol/kg water', 'assumed')
        )

    def test_dilution_scales_both_inventories_and_recomputes_chemistry(self):
        d = self.balanced.diluted(0.08)
        for name, value in STATION_104.items():
            self.assertAlmostEqual(d.analytical_totals[name], value * 0.08, delta=1e-18)
            self.assertAlmostEqual(d.totals[name], self.balanced.totals[name] * 0.08, delta=1e-18)
        self.assertEqual(d.measured_ph, 7.8)  # source metadata
        self.assertNotAlmostEqual(d.state.ph, 7.8, places=2)  # recomputed, not carried over
        self.assertEqual(d.dilution_fraction, 0.08)
        self.assertEqual(self.balanced.analytical_totals, STATION_104)
        with self.assertRaises(DeliveryError):
            self.balanced.diluted(0)

    def test_mass_and_volume_scale_the_concentration(self):
        ppm = nutrient_mg_per_litre({'Cl-': 0.001}, 95, 100)
        self.assertAlmostEqual(ppm['Cl'], 0.001 * 35.45 * 1000 * 0.95, places=12)
        self.assertNotIn('Na', ppm)  # not measured stays absent


class BalanceBeforeAdjustingTests(unittest.TestCase):
    def test_already_balanced_chloride_free_waters_need_no_balance_ion(self):
        for name, totals in (
            ('pure water', {'CO3-2': 0.0}),
            ('potassium nitrate', {'K+': 0.005, 'NO3-': 0.005, 'CO3-2': 0.0, 'Cl-': 0.0}),
            ('potassium bicarbonate', {'K+': 0.002, 'CO3-2': 0.002, 'Cl-': 0.0}),
        ):
            with self.subTest(name):
                b = balance_water_analysis(totals, measured_ph=measured_at_own_ph(totals))
                self.assertEqual(b.reconciliation, 'unchanged')
                self.assertIsNone(b.balance_ion)
                self.assertEqual(b.balance_adjustment_molal, 0)
                self.assertEqual(b.totals, totals)
                self.assertEqual(b.totals.get('Cl-', 0.0), 0.0)

    def test_explicit_zero_carbon_is_not_missing_carbon(self):
        kno3 = {'K+': 0.005, 'NO3-': 0.005}
        with self.assertRaises(DeliveryError) as raised:
            balance_water_analysis(kno3, measured_ph=7)
        self.assertEqual(raised.exception.code, 'missing_carbon')
        b = balance_water_analysis(
            kno3 | {'CO3-2': 0.0}, measured_ph=measured_at_own_ph(kno3 | {'CO3-2': 0.0})
        )
        self.assertEqual(b.carbon_source, 'none')

    def test_fixed_zero_chloride_is_never_adjusted_and_closes_on_the_alkalinity(self):
        # 1% more potassium than nitrate: out of balance, chloride measured zero (#100, owner
        # 2026-10-23).
        water = {'K+': 0.00505, 'NO3-': 0.005, 'CO3-2': 0.0002, 'Cl-': 0.0}
        closed = balance_water_analysis(water, measured_ph=7)
        self.assertEqual(
            (closed.balance_ion, closed.reconciliation), ('CO3-2', 'closed_on_alkalinity')
        )
        self.assertEqual(closed.totals['Cl-'], 0.0)
        with self.assertRaises(DeliveryError) as raised:
            balance_water_analysis(water, measured_ph=7, balance_ion='Na+')
        self.assertEqual(raised.exception.code, 'missing_balance_ion')

    def test_reconciliation_only_within_the_stated_uncertainty(self):
        with self.assertRaises(DeliveryError) as raised:  # station 104 needs -9.5 % chloride
            balance_water_analysis(STATION_104, measured_ph=7.8, balance_ion_uncertainty_percent=5)
        self.assertEqual(raised.exception.code, 'reconciliation_out_of_bounds')
        b = balance_water_analysis(
            STATION_104, measured_ph=7.8, balance_ion_uncertainty_percent=10
        )
        self.assertEqual(b.reconciliation, 'reconciled')
        self.assertEqual(b.analytical_totals, STATION_104)

    def test_below_detection_is_recorded_and_held(self):
        water = dict(STATION_104, **{'Mn+2': 0.0})
        b = balance_water_analysis(water, measured_ph=7.8, below_detection={'Mn+2': 1e-7})
        self.assertEqual(b.below_detection, {'Mn+2': 1e-7})
        self.assertIn('Mn+2', b.fixed)
        self.assertEqual(b.totals['Mn+2'], 0.0)
        self.assertEqual(b.diluted(0.5).below_detection, {'Mn+2': 5e-8})
        with self.assertRaises(DeliveryError):
            balance_water_analysis(
                dict(STATION_104, **{'Mn+2': 1e-6}),
                measured_ph=7.8,
                below_detection={'Mn+2': 1e-7},
            )


class WorkflowLimitTests(unittest.TestCase):
    def plan(self, water, maxima, **extra):
        return plan_fertilizer_workflow(
            PRODUCTS,
            FORMULAS['Tomato (Howard Resh)'],
            water.analytical_mg_per_litre(),
            5.8,
            final_volume=VolumeLitres(1000),
            maximum_concentrations=maxima,
            equilibrium=equilibrium(water_balance=water),
            **extra,
        )

    # Owner catalogue: re-enable in PR 4 (G5)
    def test_a_laboratory_exceedance_blocks_even_when_the_model_passes(self):
        self.enterContext(historical_catalogue())
        nine = balance_water_analysis(STATION_104, measured_ph=7.8).diluted(
            0.09
        )  # Cl 115.2 lab, 104.3 model
        workflow = self.plan(nine, {'Cl': 110})
        self.assertEqual(workflow.stages['formulation'].status, 'blocked')
        self.assertEqual(workflow.recommendation['limitViolations'][0]['symbol'], 'Cl')
        summary = summarize_batch(workflow, PRODUCTS, title='t', water_label='w')
        self.assertEqual(summary['status'], 'blocked')
        self.assertEqual(summary['limits'][0]['decision'], 'exceeds_limit')
        self.assertTrue(summary['limits'][0]['balancingChangesDecision'])

    # Owner catalogue: re-enable in PR 4 (G5)
    def test_a_laboratory_pass_is_not_rejected_by_the_model_but_asks_for_review(self):
        # Balanced on sodium: the model raises Na from 54.4 to 60.7 mg/L at 8%.
        self.enterContext(historical_catalogue())
        eight = balance_water_analysis(STATION_104, measured_ph=7.8, balance_ion='Na+').diluted(
            0.08
        )
        workflow = self.plan(eight, {'Na': 58})
        self.assertTrue(workflow.recommendation['feasible'])
        self.assertFalse(workflow.recommendation['limitViolations'])
        self.assertEqual(workflow.stages['formulation'].status, 'requires_review')
        finding = workflow.water_basis['findings']['formulation'][0]
        self.assertEqual((finding['symbol'], finding['decision']), ('Na', 'within_limit'))
        self.assertGreater(finding['modelledPpm'], 58)

    def test_contradictory_water_inputs_are_rejected(self):
        eight = balance_water_analysis(STATION_104, measured_ph=7.8).diluted(0.08)
        for extra in ({'measured_ph': 7.8}, {'water_totals': eight.totals}):
            with self.subTest(extra=list(extra)):
                workflow = plan_fertilizer_workflow(
                    PRODUCTS,
                    FORMULAS['Tomato (Howard Resh)'],
                    eight.analytical_mg_per_litre(),
                    5.8,
                    final_volume=VolumeLitres(1000),
                    equilibrium=equilibrium(water_balance=eight, **extra),
                )
                self.assertEqual(
                    workflow.stages['chemistry'].error_code, 'contradictory_water_inputs'
                )
        # The model's mg/L in place of the laboratory's is caught by the consistency check.
        workflow = plan_fertilizer_workflow(
            PRODUCTS,
            FORMULAS['Tomato (Howard Resh)'],
            eight.modelled_mg_per_litre(),
            5.8,
            final_volume=VolumeLitres(1000),
            equilibrium=equilibrium(water_balance=eight),
        )
        self.assertEqual(workflow.stages['chemistry'].error_code, 'inconsistent_water_analysis')

    # Owner catalogue: re-enable in PR 4 (G5)
    def test_a_chloride_free_recipe_keeps_chloride_zero_throughout(self):
        self.enterContext(historical_catalogue())
        water = {'K+': 0.0005, 'NO3-': 0.0005, 'Cl-': 0.0, 'CO3-2': 0.0}
        b = balance_water_analysis(water, measured_ph=measured_at_own_ph(water)).diluted(0.5)
        workflow = self.plan(
            b,
            {'Cl': 0},  # A zero source analysis alone does not prohibit fertilizer chloride.
            ph_adjustment=dict(products=catalogue_ph_reagents(), maximum_reagent_volume_litres=5),
        )
        chemistry = workflow.stages['chemistry']
        self.assertEqual(chemistry.status, 'calculated', chemistry.message)
        self.assertEqual(chemistry.value['water_totals']['Cl-'], 0.0)
        self.assertEqual(chemistry.value['mixed'].totals.get('Cl-', 0.0), 0.0)
        self.assertEqual(workflow.water_basis['reconciliation'], 'unchanged')
        summary = summarize_batch(workflow, PRODUCTS, title='t', water_label='w')
        self.assertEqual(summary['water']['analysis_mg_per_litre']['Cl'], 0.0)
        self.assertIn('no adjustment was needed', render_report(summary))
        self.assertEqual([row['analyticalPpm'] for row in summary['limits']], [0.0])

    # Owner catalogue: re-enable in PR 4 (G5)
    def test_no_reagent_needed_still_gets_the_final_limit_check(self):
        # Salty water already over its own declared chloride maximum; target pH = the mix's own pH.
        self.enterContext(historical_catalogue())
        water = {'Cl': 50.0, 'Na': 50 * 22.98977 / 35.45}
        totals = {'Cl-': 50 / 35.45e3, 'Na+': 50 / 35.45e3}

        def run(target_ph):
            return plan_fertilizer_workflow(
                PRODUCTS,
                FORMULAS['Lettuce General (Howard Resh)'],
                water,
                target_ph,
                final_volume=VolumeLitres(1000),
                equilibrium=equilibrium(water_totals=totals),
                ph_adjustment=dict(
                    products=catalogue_ph_reagents(), maximum_reagent_volume_litres=5
                ),
                maximum_concentrations={'Cl': 10},
            )

        ph = run(5.8).stages['ph_adjustment'].value.unadjusted_ph
        stage = run(ph).stages['ph_adjustment']
        self.assertEqual(stage.value.direction, 'none')
        self.assertEqual(stage.status, 'blocked')
        self.assertTrue(
            all(c.error_code == 'nutrient_limit_exceeded' for c in stage.value.candidates)
        )


class NitricDeliveryTests(unittest.TestCase):
    # Owner catalogue: re-enable in PR 4 (G5)
    def test_rows_and_limits_use_the_analysis_and_the_dose_uses_the_chemistry(self):
        self.enterContext(historical_catalogue())
        args = arguments()
        plain = plan_equilibrium_delivery(**args)
        self.assertEqual(plain.audit['nutrientBasis'], 'supplied water totals')  # legacy meaning
        analysis = dict(args['water_totals'], **{'Cl-': args['water_totals']['Cl-'] * 1.1})
        split = plan_equilibrium_delivery(**args, analytical_water_totals=analysis)
        self.assertEqual(split.equilibrium.nitric_acid_molal, plain.equilibrium.nitric_acid_molal)
        cl = {
            p: next(r['final'] for r in plan.rows if r['symbol'] == 'Cl')
            for p, plan in (('plain', plain), ('split', split))
        }
        self.assertAlmostEqual(cl['split'] / cl['plain'], 1.1, places=9)
        self.assertEqual(split.audit['analyticalWaterTotalsMolal'], analysis)
        with self.assertRaises(DeliveryError) as raised:
            plan_equilibrium_delivery(
                **args
                | {'maximum_concentrations': {'Na': 50, 'Cl': cl['plain'] * 1.05, 'N_NO3': 20}},
                analytical_water_totals=analysis,
            )
        self.assertEqual(raised.exception.code, 'nutrient_limit_exceeded')

    # Owner catalogue: re-enable in PR 4 (G5)
    def test_a_balanced_record_brings_its_own_analysis(self):
        self.enterContext(historical_catalogue())
        args = arguments()
        source = copy.deepcopy(args['water_totals'])
        record = balance_water_analysis(
            source | {'CO3-2': 1e-4}, measured_ph=7.4, maximum_imbalance_percent=100
        )
        with self.assertRaises(DeliveryError) as raised:
            plan_equilibrium_delivery(
                **args | {'water_totals': record},
                analytical_water_totals=dict(record.analytical_totals, **{'Cl-': 1.0}),
            )
        self.assertEqual(raised.exception.code, 'contradictory_water_inputs')


class AssessmentBoundaryTests(unittest.TestCase):
    def test_exactly_at_the_limit_is_within(self):
        rows = [dict(symbol='Cl', final=106.35, target=None)]
        self.assertEqual(assess_water_basis(rows, {'Cl': 106.35}, {'Cl': 100}, {'Cl': 100}), [])
        found = assess_water_basis(rows, {'Cl': 106.35}, {'Cl': 100}, {'Cl': 100.5})
        self.assertEqual(found[0]['decision'], 'within_limit')


class BatchCommandTests(unittest.TestCase):
    def run_batch(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = batch(list(argv))
        return code, out.getvalue(), err.getvalue()

    def write(self, tmp, name, data):
        path = Path(tmp) / name
        path.write_text(json.dumps(data), encoding='utf-8')
        return str(path)

    def test_status_html_json_sheet_and_exit_code_agree(self):
        with tempfile.TemporaryDirectory() as tmp:
            water = self.write(
                tmp,
                'well.json',
                dict(
                    id='station-104',
                    measured_ph=7.8,
                    mg_per_litre=dict(
                        Ca=244,
                        Mg=100.8,
                        K=44.2,
                        Na=680,
                        Cl=1280.4,
                        S=241.43,
                        N_NO3=3.474,
                        HCO3=196.9,
                    ),
                ),
            )
            out = Path(tmp) / 'out'
            code, _, err = self.run_batch(
                '--formula',
                'Lettuce General (Howard Resh)',
                '--water',
                water,
                '--limit',
                'Cl=106.35',
                '--output',
                str(out),
            )
            self.assertEqual(code, 3, err)
            summary = json.loads((out / 'summary.json').read_text(encoding='utf-8'))
            self.assertEqual(summary['status'], 'blocked')
            self.assertEqual(summary['limits'][0]['analyticalPpm'], 1280.4)
            self.assertIn('Do not mix.', (out / 'batch-sheet.html').read_text(encoding='utf-8'))
            report = (out / 'report.html').read_text(encoding='utf-8')
            self.assertIn('Laboratory mg/L', report)
            self.assertIn('exceeds', report)
            with self.assertRaises(SystemExit):
                self.run_batch(
                    '--crop',
                    'tomato (howard',
                    '--water',
                    'ro',
                    '--limit',
                    'Cl',
                    '--output',
                    str(out) + '2',
                )

    # Owner catalogue: re-enable in PR 4 (G5)
    def test_water_share_blends_the_analysis_with_ion_free_water(self):
        # The grower walkthrough (#80): the station 104 well as 8% and 9% of the batch water.
        self.enterContext(historical_catalogue())
        with tempfile.TemporaryDirectory() as tmp:
            water = self.write(
                tmp,
                'well.json',
                dict(
                    id='station-104',
                    measured_ph=7.8,
                    mg_per_litre=dict(
                        Ca=244,
                        Mg=100.8,
                        K=44.2,
                        Na=680,
                        Cl=1280.4,
                        S=241.43,
                        N_NO3=3.474,
                        HCO3=196.9,
                    ),
                ),
            )
            limits = (
                '--limit',
                'Na=68.97',
                '--limit',
                'Cl=106.35',
                '--limit',
                'N_NH4=14',
                '--acid',
                'HNO3:0.60:1.37',
            )
            runs = {}
            for share in ('8', '9'):
                out = Path(tmp) / share
                code, _, err = self.run_batch(
                    '--formula',
                    'Tomato (Howard Resh)',
                    '--water',
                    water,
                    '--water-share',
                    share,
                    *limits,
                    '--output',
                    str(out),
                )
                runs[share] = code, json.loads((out / 'summary.json').read_text(encoding='utf-8'))
            code, eight = runs['8']
            self.assertEqual((code, eight['status']), (3, 'blocked'))
            self.assertEqual(eight['stages']['ph_adjustment']['status'], 'blocked')
            self.assertAlmostEqual(
                eight['water']['analysis_mg_per_litre']['Cl'], 1280.4 * 0.08, places=9
            )
            self.assertEqual(eight['water']['dilution_fraction'], 0.08)
            self.assertTrue(all(row['decision'] == 'within_limit' for row in eight['limits']))
            self.assertFalse(eight['formulation']['unmet'])
            self.assertEqual(
                eight['stages']['formulation']['status'], 'calculated'
            )  # the weighed recipe has no unreviewed incidentals
            self.assertIn('Hydroxylapatite', eight['stages']['ph_adjustment']['message'])
            code, nine = runs['9']
            self.assertEqual((code, nine['status']), (3, 'blocked'))
            self.assertEqual(
                [r['symbol'] for r in nine['limits'] if r['decision'] == 'exceeds_limit'], ['Cl']
            )
            code, _, err = self.run_batch(
                '--formula',
                'Tomato (Howard Resh)',
                '--water',
                'ro',
                '--water-share',
                '8',
                '--output',
                str(Path(tmp) / 'ro'),
            )
            self.assertEqual(code, 1)
            self.assertIn('--water-share needs a measured water analysis', err)

    # Owner catalogue: re-enable in PR 4 (G5)
    def test_chloride_free_water_does_not_fail_on_the_default_balance_ion(self):
        self.enterContext(historical_catalogue())
        water_totals = {'K+': 0.0005, 'NO3-': 0.0005, 'CO3-2': 0.0, 'Cl-': 0.0}
        ph = measured_at_own_ph(water_totals)
        with tempfile.TemporaryDirectory() as tmp:
            water = self.write(
                tmp,
                'ro-kno3.json',
                dict(
                    id='ro-kno3',
                    measured_ph=ph,
                    mg_per_litre=dict(
                        K=0.0005 * 39.0983e3, N_NO3=0.0005 * 14.0067e3, Cl=0, HCO3=0
                    ),
                ),
            )
            code, _, err = self.run_batch(
                '--formula',
                'Tomato (Howard Resh)',
                '--water',
                water,
                '--output',
                str(Path(tmp) / 'out'),
            )
            self.assertIn(code, (0, 3), err)
            summary = json.loads((Path(tmp) / 'out/summary.json').read_text(encoding='utf-8'))
            self.assertEqual(summary['stages']['chemistry']['status'], 'calculated')
            self.assertEqual(summary['water']['reconciliation'], 'unchanged')
            self.assertEqual(summary['water']['analysis_mg_per_litre']['Cl'], 0)
            self.assertIn('No maximum concentrations were declared', render_batch_sheet(summary))
