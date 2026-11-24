# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Final nutrient accounting uses emitted fertilizer and selected reagent quantities."""

from decimal import Decimal
import unittest

from flahax import (
    VolumeLitres,
    catalogue_ph_reagents,
    load_library,
    plan_fertilizer_workflow,
    summarize_batch,
)


class SelectedReagentAccountingTests(unittest.TestCase):
    def test_reported_potassium_reconstructs_from_selected_base_and_fertilizer(self):
        products = [p for p in load_library()['salts'] if p['formula'] == 'KH2PO4']
        reagents = [p for p in catalogue_ph_reagents() if p['chemicalFormula'] == 'KOH']
        workflow = plan_fertilizer_workflow(
            products,
            {'K': 150, 'N_NO3': 40, 'P': 25},
            {},
            5.8,
            final_volume=VolumeLitres(1000),
            equilibrium=dict(
                water_totals={},
                water_mass_kg=1000,
                water_analysis_id='declared-ion-free',
                carbon_boundary='closed',
                temperature_c=25,
                phases=[],
            ),
            ph_adjustment=dict(
                products=reagents,
                maximum_reagent_volume_litres=5,
                correct_mixed_ph=True,
            ),
        )
        summary = summarize_batch(
            workflow,
            products,
            title='Accounting',
            water_label='Declared ion-free water',
            available_tanks=2,
            injection_ratio=100,
        )
        selected = summary['ph']['selected']
        self.assertIsNotNone(selected)
        # Independent label arithmetic: g/L * weight-percent * 10 = mg/L.
        fertilizer = sum(
            Decimal(str(dose['gramsPerLitre'])) * Decimal(str(products[0]['elements']['K'])) * 10
            for dose in summary['formulation']['salts']
        )
        # 1000 L batch: reagent grams equal mg/L before the mass-fraction conversion.
        # KOH formula mass follows the disclosed atomic-mass convention (g/mol).
        reagent = (
            Decimal(str(selected['mass_g_per_batch']))
            * Decimal(str(reagents[0]['massFraction']))
            * Decimal('39.0983')
            / (Decimal('39.0983') + Decimal('15.999') + Decimal('1.00784'))
        )
        reported = next(r['final'] for r in summary['formulation']['rows'] if r['symbol'] == 'K')
        self.assertAlmostEqual(float(fertilizer + reagent), reported, delta=1e-10)


if __name__ == '__main__':
    unittest.main()
