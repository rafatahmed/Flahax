# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Coupled recipe and pH reagent planning (#74, #75, #76, #77)."""

import math
import unittest

from flahax import (
    VolumeLitres,
    calculate_equilibrium_ph,
    catalogue_dose_totals,
    catalogue_ph_reagents,
    load_library,
    plan_fertilizer_workflow,
    reagent_dose,
    recommend,
)
from flahax.delivery_contracts import DeliveryError
from flahax.ph_adjustment import REAGENTS
from tests.catalogue_history import historical_catalogue

# Pre-owner products and formulas (Chilli (maximumyield) is not in the owner catalogue).
with historical_catalogue():
    LIBRARY = load_library()
FORMULAS = {f['name']: f['targets'] for f in LIBRARY['formulas']}
ACIDS = [
    dict(
        id=f'{f}-example',
        source='EXAMPLE GRADE',
        revision='1',
        recordedAt='2026-10-22T00:00:00Z',
        chemicalFormula=f,
        massFraction=m,
        densityKgPerL=d,
    )
    for f, m, d in (('HNO3', 0.60, 1.37), ('H3PO4', 0.75, 1.58))
]
RO = dict(
    water_totals={},
    water_mass_kg=1000,
    water_analysis_id='RO',
    complete_analysis=True,
    carbon_boundary='closed',
    temperature_c=25,
    phases=[],
)
CLOSED = dict(complete_analysis=True, carbon_boundary='closed', phases=[])


def coupled(formula, target_ph=5.8, maxima=None):
    return plan_fertilizer_workflow(
        LIBRARY['salts'],
        FORMULAS[formula],
        {},
        target_ph,
        maximum_concentrations=maxima,
        final_volume=VolumeLitres(1000),
        equilibrium=RO,
        ph_adjustment=dict(
            products=ACIDS + catalogue_ph_reagents(), maximum_reagent_volume_litres=5
        ),
    )


def amended_ph(candidate):
    """pH recalculated from scratch: the candidate's recipe in RO water plus its reagent."""
    doses = {s['name']: s['gramsPerLitre'] for s in candidate.recommendation['salts']}
    totals = catalogue_dose_totals(doses)
    for basis, n in REAGENTS[candidate.formula][1].items():
        totals[basis] = totals.get(basis, 0) + n * candidate.dose_molal
    return calculate_equilibrium_ph(totals, **CLOSED).ph


class ReagentDoseTests(unittest.TestCase):
    def setUp(self):
        self.acidic = calculate_equilibrium_ph(
            {'K+': 0.004, 'PO4-3': 0.004}, **CLOSED
        )  # KH2PO4-like, pH ~4.6

    def test_bases_raise_the_ph_to_exactly_the_target(self):
        for formula in ('KOH', 'KHCO3', 'K2CO3'):
            with self.subTest(formula):
                dose, _ = reagent_dose(
                    self.acidic.totals, self.acidic.ph, 5.8, formula, initial=self.acidic
                )
                self.assertGreater(dose, 0)
                totals = dict(self.acidic.totals)
                for basis, n in REAGENTS[formula][1].items():
                    totals[basis] = totals.get(basis, 0) + n * dose
                self.assertAlmostEqual(
                    calculate_equilibrium_ph(totals, **CLOSED).ph, 5.8, places=5
                )

    def test_wrong_direction_is_refused(self):
        with self.assertRaises(DeliveryError) as raised:
            reagent_dose(self.acidic.totals, self.acidic.ph, 5.8, 'HNO3', initial=self.acidic)
        self.assertEqual(raised.exception.code, 'wrong_reagent_direction')
        with self.assertRaises(DeliveryError):
            reagent_dose(self.acidic.totals, self.acidic.ph, 4.0, 'KOH', initial=self.acidic)


class CatalogueTests(unittest.TestCase):
    def test_catalogue_offers_three_sourced_bases(self):
        records = {r['chemicalFormula']: r for r in catalogue_ph_reagents()}
        # The owner catalogue adds phosphoric and nitric acid as pH reagents.
        self.assertEqual(set(records), {'KOH', 'KHCO3', 'K2CO3', 'H3PO4', 'HNO3'})
        self.assertEqual(
            (records['KOH']['massFraction'], records['KOH']['densityKgPerL']), (0.45, 1.456)
        )

    def test_recommend_never_selects_a_ph_reagent(self):
        result = recommend(LIBRARY['salts'], {'K': 300}, {}, allow_carbonates=True)
        self.assertFalse(
            {s['name'] for s in result['salts']}
            & {
                'Potassium Hydroxide (45% solution)',
                'Potassium Bicarbonate',
                'Potassium Carbonate',
            }
        )


class CoupledWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Preserve this reaction-accounting fixture's historical, now explicit allowance.
        cls.enterClassContext(historical_catalogue())
        cls.alkaline = coupled('Tomato (Howard Resh)', maxima={'N_NH4': 14})
        cls.acidic = coupled(
            'Chilli (maximumyield)'
        )  # mixed at pH 3 when phosphoric acid was a P source
        cls.unbalanced = coupled('Pepper (Howard Resh)')  # formula 39% out of ion balance

    def test_alkaline_feed_gets_acids_with_their_nutrients_counted(self):
        plan = self.alkaline.stages['ph_adjustment'].value
        self.assertEqual(plan.direction, 'acid')
        acids = [c for c in plan.candidates if c.direction == 'acid']
        self.assertEqual({c.formula for c in acids}, {'HNO3', 'H3PO4'})
        for c in acids:
            self.assertGreater(c.dose_molal, 0)
            self.assertAlmostEqual(c.target.ph, 5.8, places=9)
            self.assertAlmostEqual(amended_ph(c), 5.8, places=4)
        by_formula = {c.formula: c for c in acids}
        # Phosphoric acid's P is counted as supply: every target is met.
        self.assertTrue(by_formula['H3PO4'].recommendation['feasible'])
        # Nitric acid adds nitrate-N; calcium comes only from calcium nitrate, so N and Ca conflict
        # and the miss is explained, not hidden. No upper error bound follows
        # from primary-only fitting: joint optimality remains a separate contract.
        nitric = by_formula['HNO3'].recommendation
        self.assertFalse(nitric['feasible'])
        self.assertEqual({u['symbol'] for u in nitric['unmetTargets']}, {'N_NO3', 'Ca'})
        self.assertTrue(
            all(
                u['reason'] == 'conflicting_targets' and abs(u['deltaPct']) > 1
                for u in nitric['unmetTargets']
            )
        )
        for c in plan.candidates:
            if c.direction == 'base':
                self.assertEqual(c.status, 'not_applicable')

    def test_acidic_feed_gets_a_base_and_phosphoric_acid_is_not_a_p_source(self):
        plan = self.acidic.stages['ph_adjustment'].value
        self.assertEqual(plan.direction, 'base')
        self.assertGreater(
            plan.unadjusted_ph, 4.0
        )  # was 2.99 with phosphoric acid as a P source (#76)
        self.assertNotIn(
            'Phosphoric Acid (75%)', [s['name'] for s in plan.unadjusted_recommendation['salts']]
        )
        bases = [c for c in plan.candidates if c.direction == 'base']
        self.assertEqual({c.formula for c in bases}, {'KOH', 'KHCO3', 'K2CO3'})
        for c in bases:
            self.assertAlmostEqual(amended_ph(c), 5.8, places=4)
            self.assertGreater(c.nutrient_contribution['K'], 0)

    def test_a_missed_target_still_gets_a_ph_plan(self):
        plan = self.unbalanced.stages['ph_adjustment'].value
        self.assertIsNotNone(plan)
        computed = [c for c in plan.candidates if c.dose_molal]
        self.assertTrue(computed)
        self.assertTrue(
            all(not c.recommendation['feasible'] for c in computed)
        )  # reported, not hidden

    def test_phase_names_cannot_authorize_a_plan_without_applicable_evidence(self):
        stage = self.alkaline.stages['ph_adjustment']
        self.assertEqual(stage.status, 'blocked')
        self.assertIsNone(stage.value.selected)
        calculated = [c for c in stage.value.candidates if c.target is not None]
        self.assertTrue(calculated)
        for candidate in calculated:
            self.assertTrue(candidate.saturation['blocks'])
            self.assertFalse(candidate.saturation['mixing_approved'])
            self.assertIn('Hydroxylapatite', candidate.message)
            self.assertTrue(math.isfinite(candidate.reagent_mass_g))

    def test_readily_forming_phases_still_block_and_keep_the_dose(self):
        # Chilli with a base: monetite (CaHPO4) is supersaturated, a hard phase.
        stage = self.acidic.stages['ph_adjustment']
        self.assertEqual(stage.status, 'blocked')
        for c in stage.value.candidates:
            if c.direction == 'base':
                self.assertEqual(c.error_code, 'precipitation_risk')
                self.assertIn('CaHPO4', [p for p, _ in c.saturation['blocking']])
                self.assertTrue(math.isfinite(c.reagent_mass_g))


if __name__ == '__main__':
    unittest.main()
