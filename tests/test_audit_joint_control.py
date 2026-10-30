# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Real released joint-fit fallback must diagnose its actual final recipe.

No chemistry is mocked. The original packaged formula and full inventory are used.
This consistency test does not certify global optimality or physical mixability.
"""

import unittest

from flahax import VolumeLitres, load_library, plan_fertilizer_workflow
from tests.catalogue_history import historical_catalogue


class JointAuditRegressionTests(unittest.TestCase):
    # Catalogue v0.0: re-enable in PR 4 (G5)
    def test_product_switch_diagnosis_matches_final_nutrient_rows(self):
        self.enterContext(historical_catalogue())
        library = load_library()
        formula = next(
            row
            for row in library['formulas']
            if row['name'] == 'Tomato Stage.2 - first cluster (Howard Resh)'
        )
        acid = dict(
            id='audit-hno3',
            name='Synthetic nitric grade',
            chemicalFormula='HNO3',
            massFraction=0.60,
            densityKgPerL=1.37,
            source='synthetic audit input',
            revision='1',
            recordedAt='2026-10-25T00:00:00Z',
        )
        result = plan_fertilizer_workflow(
            library['salts'],
            formula['targets'],
            {},
            5.8,
            final_volume=VolumeLitres(1000),
            equilibrium=dict(
                water_totals={},
                water_mass_kg=1000,
                water_analysis_id='RO',
                complete_analysis=True,
                carbon_boundary='closed',
                temperature_c=25,
                phases=[],
            ),
            ph_adjustment=dict(products=[acid], maximum_reagent_volume_litres=5),
        )
        candidates = result.stages['ph_adjustment'].value.candidates
        assessed = [candidate for candidate in candidates if candidate.target is not None]
        self.assertTrue(assessed, 'a setup failure is not a reproduced bookkeeping defect')
        for candidate in assessed:
            recommendation = candidate.recommendation
            rows = {row['symbol']: row for row in recommendation['rows']}
            for miss in recommendation['unmetTargets']:
                with self.subTest(reagent=candidate.product_id, nutrient=miss['symbol']):
                    self.assertEqual(miss['final'], rows[miss['symbol']]['final'])
                    self.assertEqual(miss['deltaPct'], rows[miss['symbol']]['deltaPct'])


if __name__ == '__main__':
    unittest.main()
