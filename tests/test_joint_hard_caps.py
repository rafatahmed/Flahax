# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Provably unusable sources must not dominate the public joint search."""

import json
from pathlib import Path
import tempfile
import unittest

from flahax import (
    catalogue_ph_reagents,
    load_library,
    make_joint_problem,
    recommend,
    solve_joint_problem,
)
from flahax.batch_cli import JOINT_CONTROLS


def capped_problem(include_forbidden):
    pool = [
        p
        for p in load_library()['salts']
        if p['formula'] == 'KH2PO4' or include_forbidden and p['formula'] == '(NH4)2SO4'
    ]
    reagent = next(p for p in catalogue_ph_reagents() if p['chemicalFormula'] == 'KOH')
    targets = {'K': 100, 'P': 50, 'S': 50}
    problem = make_joint_problem(
        pool,
        reagent,
        targets,
        {},
        reagent_solvent_fraction=0.55,
        water_components={},
        final_volume_litres=1000,
        solvent_mass_kg=1000,
        target_ph=6,
        reference_charge_mol_per_kg=0,
        maximum_reagent_mass_g=7280,
        maximum_reagent_volume_litres=5,
        maximum_concentrations={'N_NH4': 0},
    )
    recipe = recommend(pool, targets, {}, maximum_concentrations={'N_NH4': 0})
    doses = {s['id']: s['gramsPerLitre'] for s in recipe['salts']}
    controls = dict(
        JOINT_CONTROLS,
        dose_steps={s.product_id: 1e-4 for s in (*problem.fertilizers, problem.reagent)},
    )
    return problem, doses, controls


class JointHardCapTests(unittest.TestCase):
    def test_batch_converges_with_explicit_zero_ammonium_maximum(self):
        from flahax.batch_cli import BatchOptions, run_batch

        targets = {
            'N_NO3': 140,
            'N_NH4': 0,
            'P': 50,
            'K': 340,
            'Ca': 200,
            'Mg': 50,
            'S': 150,
            'Fe': 2.8,
            'Mn': 0.8,
            'B': 0.7,
            'Zn': 0.1,
            'Cu': 0.07,
            'Mo': 0.05,
        }
        reagents = [p for p in catalogue_ph_reagents() if p['chemicalFormula'] == 'KOH']
        with tempfile.TemporaryDirectory() as directory:
            target_file = Path(directory) / 'targets.json'
            reagent_file = Path(directory) / 'reagents.json'
            target_file.write_text(json.dumps(targets))
            reagent_file.write_text(json.dumps(reagents))
            summary = run_batch(
                BatchOptions(
                    water='ro',
                    targets=str(target_file),
                    reagents=str(reagent_file),
                    ph=6,
                    ratio=10,
                    tank_litres={'A': 100, 'B': 100, 'acid': 10},
                    mode='fill',
                    limit=[['N_NH4', 0]],
                )
            )
        chosen = summary['ph']['selected']
        self.assertIsNotNone(chosen, summary['ph']['message'])
        self.assertEqual(chosen['joint']['status'], 'stationary_point')
        products = {p['id']: p for p in load_library()['salts']}
        self.assertEqual(chosen['formula'], 'KOH')
        ammonium = sum(
            salt['gramsPerLitre'] * products[salt['id']]['elements'].get('N_NH4', 0) * 10
            for salt in summary['formulation']['salts']
        )
        self.assertEqual(ammonium, 0)
        limit = next(item for item in summary['limits'] if item['symbol'] == 'N_NH4')
        self.assertEqual(limit['maximumPpm'], 0)
        self.assertLessEqual(
            abs(chosen['joint']['chargeResidual']), chosen['joint']['chargeTolerance']
        )
        self.assertAlmostEqual(chosen['joint']['finalPh'], 6, delta=1e-4)

    def test_unusable_ammonium_source_does_not_explode_search_work(self):
        results = []
        for include_forbidden in (False, True):
            problem, doses, controls = capped_problem(include_forbidden)
            result = solve_joint_problem(problem, doses, 0, **controls)
            self.assertEqual(result['status'], 'stationary_point')
            self.assertEqual(result['evaluation']['violations'], [])
            self.assertLessEqual(abs(result['evaluation']['chargeResidual']), 2e-12)
            for source in problem.fertilizers:
                if source.nutrients.get('N_NH4', 0) > 0:
                    self.assertEqual(result['fertilizerDoses'][source.product_id], 0)
            results.append(result)
        self.assertAlmostEqual(
            results[0]['evaluation']['loss'], results[1]['evaluation']['loss'], delta=1e-8
        )
        # A loose relative work guard, not an iteration or numerical tolerance change.
        self.assertLessEqual(
            results[1]['diagnostics']['evaluations'],
            5 * results[0]['diagnostics']['evaluations'],
        )


if __name__ == '__main__':
    unittest.main()
