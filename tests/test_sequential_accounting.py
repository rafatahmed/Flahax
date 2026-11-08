# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Sequential pH plans report the nutrients in their actual returned doses."""

import math
import json
from pathlib import Path
import tempfile
import unittest

from flahax import (
    calculate_equilibrium_ph,
    catalogue_dose_totals,
    catalogue_ph_reagents,
    load_library,
    plan_coupled_ph,
)


def acid_plan(maxima=None):
    pool = [p for p in load_library()['salts'] if p['formula'] in ('KNO3', 'KH2PO4')]
    acid = next(p for p in catalogue_ph_reagents() if p['chemicalFormula'] == 'HNO3')

    def mix(recipe):
        return calculate_equilibrium_ph(
            catalogue_dose_totals({s['name']: s['gramsPerLitre'] for s in recipe['salts']}),
            carbon_boundary='closed',
            phases=[],
        )

    plan = plan_coupled_ph(
        pool,
        {'N_NO3': 140, 'K': 100, 'P': 20},
        {},
        4,
        products=[acid],
        mix=mix,
        water_mass_kg=1000,
        final_volume_litres=1000,
        maximum_reagent_volume_litres=5,
        maximum_concentrations=maxima,
    )
    return plan.candidates[0], pool


class SequentialAccountingTests(unittest.TestCase):
    def test_report_counts_the_actual_nitric_dose(self):
        candidate, pool = acid_plan()
        by_id = {p['id']: p for p in pool}
        # g/batch / 1000 L * 1000 mg/g; nitric acid carries one nitrogen per molecule.
        nitrogen = candidate.reagent_mass_g * 0.65 * 14.0067 / 63.01284
        nitrogen += math.fsum(
            s['gramsPerLitre'] * by_id[s['id']]['elements'].get('N_NO3', 0) * 10
            for s in candidate.recommendation['salts']
        )
        row = next(r for r in candidate.recommendation['rows'] if r['symbol'] == 'N_NO3')
        self.assertAlmostEqual(row['final'], nitrogen, delta=1e-10)

    def test_tight_maximum_and_total_n_use_the_actual_recipe(self):
        candidate, pool = acid_plan({'N_NO3': 2})
        by_id = {p['id']: p for p in pool}
        nitrogen = candidate.reagent_mass_g * 0.65 * 14.0067 / 63.01284
        nitrogen += math.fsum(
            s['gramsPerLitre'] * by_id[s['id']]['elements'].get('N_NO3', 0) * 10
            for s in candidate.recommendation['salts']
        )
        self.assertLess(nitrogen, 2)
        self.assertLess(2 - nitrogen, 2e-6)
        self.assertAlmostEqual(candidate.recommendation['totalN']['final'], nitrogen, delta=1e-10)
        row = next(r for r in candidate.recommendation['rows'] if r['symbol'] == 'N_NO3')
        self.assertAlmostEqual(2 - row['final'], 2 - nitrogen, delta=1e-10)
        self.assertEqual(candidate.recommendation['limitViolations'], [])
        self.assertNotIn('convex blend', candidate.recommendation['substitutionSearch']['method'])

    def test_batch_reports_the_final_sequential_reagent_contribution(self):
        from flahax.batch_cli import BatchOptions, run_batch

        acid = next(p for p in catalogue_ph_reagents() if p['chemicalFormula'] == 'HNO3')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'reagents.json'
            path.write_text(json.dumps([acid]))
            summary = run_batch(
                BatchOptions(
                    water='ro', formula='Cucumber (Howard Resh)', ph=4, reagents=str(path)
                )
            )
        chosen = summary['ph']['selected']
        self.assertEqual(chosen['joint']['status'], 'sequential')
        products = {p['id']: p for p in load_library()['salts']}
        nitrate = chosen['mass_g_per_batch'] * 0.65 * 14.0067 / 63.01284
        nitrate += math.fsum(
            salt['gramsPerLitre'] * products[salt['id']]['elements'].get('N_NO3', 0) * 10
            for salt in summary['formulation']['salts']
        )
        row = next(r for r in summary['formulation']['rows'] if r['symbol'] == 'N_NO3')
        self.assertAlmostEqual(row['final'], nitrate, delta=1e-10)


if __name__ == '__main__':
    unittest.main()
