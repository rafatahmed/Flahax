# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Sonneveld et al. (1999), Appendix I, DOI 10.17660/ActaHortic.1999.481.38.

The printed EC is a design target. Some cells in the available transcription
were reconstructed using equations 2–5. The acid-to-pH cases are model
regressions. They use closed carbon, 25 C, aqueous-only equilibrium and
1000 kg solvent for 1000 L of dilute finished solution.
"""

import json
import unittest

from flahax import VolumeLitres, plan_fertilizer_workflow
from flahax.engine import recommend
from flahax.irrigation_ec import calculate_ec_from_totals
from flahax.nutrient_acceptance import assess_incidental


# Concentrations in mmol/L, including the trace elements.
COLUMN_D = {
    'Ca': 2.84,
    'Mg': 1.03,
    'K': 8.76,
    'N_NO3': 13.10,
    'N_NH4': 1.50,
    'P': 1.25,
    'S': 1.83,
    'Fe': 0.015,
    'Mn': 0.010,
    'Zn': 0.004,
    'B': 0.030,
    'Cu': 0.00075,
    'Mo': 0.00050,
}
COLUMN_E = {'Ca': 1.00, 'Mg': 0.40, 'S': 0.30}
BICARBONATE = 2.20
ATOMIC_MASS = {
    'Ca': 40.078,
    'Mg': 24.305,
    'K': 39.0983,
    'N_NO3': 14.007,
    'N_NH4': 14.007,
    'P': 30.974,
    'S': 32.06,
    'Fe': 55.845,
    'Mn': 54.938,
    'Zn': 65.38,
    'B': 10.81,
    'Cu': 63.546,
    'Mo': 95.95,
    'Na': 22.98977,
}
BASIS = dict(
    zip(
        ATOMIC_MASS,
        (
            'Ca+2',
            'Mg+2',
            'K+',
            'NO3-',
            'NH4+',
            'PO4-3',
            'SO4-2',
            'Fe+3',
            'Mn+2',
            'Zn+2',
            'H3BO3',
            'Cu+2',
            'MoO4-2',
            'Na+',
        ),
        strict=True,
    )
)
# Defined grades for the replay. Fe-DTPA is the disodium form, assayed at 11% Fe.
GRADES = (
    ('calcium nitrate tetrahydrate', 236.15, {'Ca': 1, 'N_NO3': 2}),
    ('ammonium nitrate', 80.043, {'N_NH4': 1, 'N_NO3': 1}),
    ('magnesium sulfate heptahydrate', 246.47, {'Mg': 1, 'S': 1}),
    ('monopotassium phosphate', 136.086, {'K': 1, 'P': 1}),
    ('potassium nitrate', 101.103, {'K': 1, 'N_NO3': 1}),
    ('potassium sulfate', 174.259, {'K': 2, 'S': 1}),
    ('iron DTPA', 55.845 / 0.11, {'Fe': 1, 'Na': 2}),
    ('manganese sulfate monohydrate', 169.02, {'Mn': 1, 'S': 1}),
    ('zinc sulfate heptahydrate', 287.54, {'Zn': 1, 'S': 1}),
    ('boric acid', 61.83, {'B': 1}),
    ('copper sulfate pentahydrate', 249.68, {'Cu': 1, 'S': 1}),
    ('sodium molybdate dihydrate', 241.95, {'Mo': 1, 'Na': 2}),
)
SODIUM_NITRATE = ('sodium nitrate', 84.995, {'Na': 1, 'N_NO3': 1})


def ppm(concentrations):
    return {key: amount * ATOMIC_MASS[key] for key, amount in concentrations.items()}


def fit_recipe(acid_mmol_l, *, sodium_target=None):
    # Treat the independently fixed HNO3 dose as a nitrate credit in the fit.
    credited_water = dict(COLUMN_E, N_NO3=acid_mmol_l)
    targets = dict(COLUMN_D)
    grades = GRADES
    if sodium_target is not None:
        grades += (SODIUM_NITRATE,)
        targets['Na'] = sodium_target
    library = [
        {
            'id': name,
            'name': name,
            'formula': '',
            'elements': ppm({key: 100 * count / mass for key, count in ions.items()}),
        }
        for name, mass, ions in grades
    ]
    fit = recommend(library, ppm(targets), ppm(credited_water), allow_ions={'Na'})
    return fit, grades


def reconstruct(fit, grades, acid_mmol_l, *, mass_decimals=None):
    """Calculate finished analytical totals independently from returned product weights."""
    concentrations = dict(COLUMN_E, N_NO3=acid_mmol_l)
    if mass_decimals is not None:
        # Round the actual delivered volume (mL), then recover the acid inventory.
        acid_ml = acid_mmol_l * 63.01 / (0.65 * 1.39)
        concentrations['N_NO3'] = round(acid_ml, 2) * 0.65 * 1.39 / 63.01
    grade_by_name = {name: (mass, ions) for name, mass, ions in grades}
    for salt in fit['salts']:
        mass, ions = grade_by_name[salt['id']]
        grams = 1000 * salt['gramsPerLitre']
        if mass_decimals is not None:
            grams = round(grams, mass_decimals)
        for key, count in ions.items():
            concentrations[key] = concentrations.get(key, 0) + grams / mass * count
    inventory = {BASIS[key]: amount / 1000 for key, amount in concentrations.items()}
    inventory.update({'CO3-2': BICARBONATE / 1000, 'Dtp-5': inventory['Fe+3']})
    return concentrations, calculate_ec_from_totals(
        inventory,
        solution_id='sonneveld-appendix-i',
        ph_mode='calculated',
        phase_policy='dissolved',
    )


class SonneveldAppendixI(unittest.TestCase):
    def replay(self, acid, *, sodium_target=None):
        fit, grades = fit_recipe(acid, sodium_target=sodium_target)
        concentrations, chemistry = reconstruct(fit, grades, acid)
        rows = {row['symbol']: row['final'] for row in fit['rows']}
        for key, amount in ppm(concentrations).items():
            self.assertAlmostEqual(rows[key], amount, delta=1e-8, msg=key)
        self.assertEqual(chemistry.status, 'range')
        return fit, grades, concentrations, chemistry

    def test_fixed_bicarbonate_equivalent_dose(self):
        fit, _, totals, chemistry = self.replay(BICARBONATE)
        self.assertAlmostEqual(BICARBONATE * 63.01 / (0.65 * 1.39), 153.43, places=2)
        self.assertFalse(fit['feasible'])
        self.assertLess(max(abs(totals[k] / v - 1) for k, v in COLUMN_D.items()), 0.001)
        self.assertAlmostEqual(chemistry.ph, 4.5097, places=4)
        self.assertAlmostEqual(chemistry.ec25_range_ms_cm[0], 2.0794, places=4)
        self.assertAlmostEqual(chemistry.ec25_range_ms_cm[1], 2.1874, places=4)

    def test_ph_target_original_inventory_is_a_near_fit(self):
        # Dose from the retained-carbon pH 5.5 replay with this product inventory.
        acid = 1.8319650066
        fit, _, totals, chemistry = self.replay(acid)
        self.assertFalse(fit['feasible'])
        self.assertAlmostEqual(chemistry.ph, 5.5, places=6)
        self.assertAlmostEqual(totals['N_NO3'], 12.90199, places=4)
        self.assertAlmostEqual(totals['K'], 8.84854, places=4)
        self.assertAlmostEqual(totals['Na'] * ATOMIC_MASS['Na'], 0.71268, places=4)
        self.assertAlmostEqual(chemistry.ec25_range_ms_cm[0], 2.07118, places=4)
        self.assertAlmostEqual(chemistry.ec25_range_ms_cm[1], 2.18113, places=4)

    def test_ph_target_with_sodium_nitrate_discloses_sodium(self):
        acid = 1.8317694626
        fit, grades, totals, chemistry = self.replay(acid, sodium_target=0.3797305374)
        self.assertTrue(fit['feasible'])
        self.assertAlmostEqual(chemistry.ph, 5.5, places=6)
        for key, target in COLUMN_D.items():
            self.assertAlmostEqual(totals[key], target, delta=target * 1e-5, msg=key)
        self.assertAlmostEqual(totals['Na'] * ATOMIC_MASS['Na'], 8.730, places=3)
        dose = next(
            salt['gramsPerLitre'] * 1000
            for salt in fit['salts']
            if salt['id'] == SODIUM_NITRATE[0]
        )
        self.assertAlmostEqual(dose, 29.640, places=3)
        self.assertAlmostEqual(chemistry.ec25_range_ms_cm[0], 2.09162, places=4)
        self.assertAlmostEqual(chemistry.ec25_range_ms_cm[1], 2.20175, places=4)
        # Illustrative 1 mg/L sodium ceiling, not a crop recommendation.
        limits = assess_incidental(fit['rows'], {'Na': 1.0})
        self.assertEqual([row['symbol'] for row in limits['limitViolations']], ['Na'])
        coarse, _ = reconstruct(fit, grades, acid, mass_decimals=3)
        self.assertGreater(abs(coarse["Cu"] / COLUMN_D["Cu"] - 1), 0.001)
        rounded, rounded_chemistry = reconstruct(fit, grades, acid, mass_decimals=4)
        self.assertAlmostEqual(rounded_chemistry.ph, 5.5, delta=0.001)
        for key, target in COLUMN_D.items():
            self.assertAlmostEqual(rounded[key], target, delta=target * 0.001, msg=key)

    def batch_at_ph_5_5(self, extra_grade, extra_formula, targets, *, maxima=None, search=False):
        formulas = (
            'Ca(NO3)2.4H2O',
            'NH4NO3',
            'MgSO4.7H2O',
            'KH2PO4',
            'KNO3',
            'K2SO4',
            '',
            'MnSO4.H2O',
            'ZnSO4.7H2O',
            'H3BO3',
            'CuSO4.5H2O',
            'Na2MoO4.2H2O',
            extra_formula,
        )
        grades = GRADES + (extra_grade,)
        products = [
            {
                'id': name,
                'name': name,
                'formula': formula,
                'elements': ppm({key: 100 * count / mass for key, count in ions.items()}),
            }
            for (name, mass, ions), formula in zip(grades, formulas, strict=True)
        ]
        products[6]['identityId'] = 'idn-disodium-iron-dtpa'
        alternatives = ()
        if search:
            from flahax.evaluated_remedies import available_product_search

            alternatives = (available_product_search(products[-1:]),)
            products = products[:-1]
        result = plan_fertilizer_workflow(
            products,
            ppm(targets),
            ppm(COLUMN_E),
            5.5,
            final_volume=VolumeLitres(1000),
            maximum_concentrations=maxima,
            remedy_options=alternatives,
            equilibrium={
                'water_totals': {'Ca+2': 0.001, 'Mg+2': 0.0004, 'SO4-2': 0.0003, 'CO3-2': 0.0022},
                'water_mass_kg': 1000,
                'water_analysis_id': 'Sonneveld Appendix I',
                'temperature_c': 25,
                'carbon_boundary': 'closed',
                'phases': [],
            },
            ph_adjustment={
                'products': [
                    {
                        'id': 'appendix-nitric-acid',
                        'chemicalFormula': 'HNO3',
                        'massFraction': 0.65,
                        'densityKgPerL': 1.39,
                        'source': 'Example grade',
                        'revision': '1',
                        'recordedAt': '2026-11-17T00:00:00Z',
                    }
                ],
                'maximum_reagent_volume_litres': 1,
            },
        )
        if search:
            return result
        stage = result.stages['ph_adjustment']
        self.assertIsNotNone(stage.value, result.stages)
        candidate = stage.value.selected
        self.assertIsNotNone(candidate, stage.value.candidates)
        self.assertEqual(candidate.formula, 'HNO3')
        return candidate, grades

    def test_batch_workflow_finds_acid_for_ph_5_5(self):
        candidate, grades = self.batch_at_ph_5_5(
            SODIUM_NITRATE, 'NaNO3', dict(COLUMN_D, Na=0.3797305374)
        )
        self.assertAlmostEqual(candidate.reagent_volume_litres * 1000, 127.75, delta=0.1)
        self.assertAlmostEqual(candidate.target.ph, 5.5, delta=0.001)
        acid = candidate.reagent_mass_g * 0.65 / 63.01
        self.assertAlmostEqual(candidate.reagent_volume_litres * 1390, candidate.reagent_mass_g)
        totals, chemistry = reconstruct(candidate.recommendation, grades, acid)
        self.assertAlmostEqual(chemistry.ph, 5.5, delta=0.001)
        self.assertEqual(chemistry.status, 'range')
        low, high = chemistry.ec25_range_ms_cm
        self.assertAlmostEqual(low, 2.0916, delta=0.002)
        self.assertAlmostEqual(high, 2.2017, delta=0.002)
        for key, target in COLUMN_D.items():
            self.assertAlmostEqual(totals[key], target, delta=target * 0.001, msg=key)

    def test_batch_selects_sodium_sulfate_without_sodium_nitrate_or_target(self):
        sulfate = ('sodium sulfate anhydrous', 142.04, {'Na': 2, 'S': 1})
        # An illustrative replay ceiling, not an agronomic recommendation.
        sodium_ceiling = 9.0
        candidate, grades = self.batch_at_ph_5_5(
            sulfate, 'Na2SO4', COLUMN_D, maxima={'Na': sodium_ceiling}
        )
        self.assertEqual(candidate.status, 'accepted')
        self.assertTrue(candidate.recommendation['feasible'])
        doses = {
            salt['id']: 1000 * salt['gramsPerLitre'] for salt in candidate.recommendation['salts']
        }
        self.assertNotIn(SODIUM_NITRATE[0], doses)
        self.assertAlmostEqual(doses[sulfate[0]], 24.77, delta=0.05)
        self.assertAlmostEqual(doses['potassium nitrate'], 615.54, delta=0.05)
        self.assertAlmostEqual(doses['potassium sulfate'], 123.88, delta=0.05)
        self.assertAlmostEqual(candidate.reagent_volume_litres * 1000, 127.75, delta=0.1)

        acid = candidate.reagent_mass_g * 0.65 / 63.01
        totals, chemistry = reconstruct(candidate.recommendation, grades, acid)
        for key, target in COLUMN_D.items():
            self.assertAlmostEqual(totals[key], target, delta=target * 1e-5, msg=key)
        sodium = totals['Na'] * ATOMIC_MASS['Na']
        self.assertAlmostEqual(sodium, 8.73, delta=0.01)
        self.assertLessEqual(sodium, sodium_ceiling)
        self.assertAlmostEqual(chemistry.ph, 5.5, delta=0.001)

    def test_batch_search_recovers_sodium_nitrate_free_recipe_after_first_fit_misses(self):
        sulfate = ('sodium sulfate anhydrous', 142.04, {'Na': 2, 'S': 1})
        result = self.batch_at_ph_5_5(sulfate, 'Na2SO4', COLUMN_D, maxima={'Na': 9.0}, search=True)
        baseline = result.stages['ph_adjustment'].value.selected
        self.assertFalse(baseline.recommendation['feasible'])
        self.assertEqual(result.remedies['evaluations'], 1)
        trial = result.remedies['options'][0]
        self.assertEqual(trial['status'], 'evaluated_candidate')
        self.assertIn('nutrient:N_NO3', trial['resolved_requirements'])
        snapshot = json.loads(trial['snapshot'])
        self.assertEqual(snapshot['inputs']['maximum_concentrations'], {'Na': 9.0})
        self.assertEqual(snapshot['inputs']['targets'], ppm(COLUMN_D))
        candidate = snapshot['workflow']['stages']['ph_adjustment']['value']
        chosen = next(item for item in candidate['candidates'] if item['status'] == 'accepted')
        fit = chosen['recommendation']
        self.assertTrue(fit['feasible'])
        self.assertIn(sulfate[0], fit['saltIds'])
        self.assertNotIn(SODIUM_NITRATE[0], fit['saltIds'])
        self.assertAlmostEqual(chosen['reagent_volume_litres'] * 1000, 127.75, delta=0.1)
        acid = chosen['reagent_mass_g'] * 0.65 / 63.01
        totals, chemistry = reconstruct(fit, GRADES + (sulfate,), acid)
        for key, target in COLUMN_D.items():
            self.assertAlmostEqual(totals[key], target, delta=target * 1e-5, msg=key)
        self.assertAlmostEqual(chemistry.ph, 5.5, delta=0.001)
        self.assertLessEqual(totals['Na'] * ATOMIC_MASS['Na'], 9.0)
