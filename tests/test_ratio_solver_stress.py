# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""N3 bounded supported-domain stress through the public recipe workflow."""

import unittest

from flahax import plan_ratio_recipe
from flahax.aqueous_model import solve
from flahax.delivery_contracts import DeliveryError
from tests.ratio_allocation_cases import base_request, independent_witness
from tests.test_ratio_allocation_reliability import exercise


def stress_cases():
    result = []
    for cations in ([50, 30, 20], [51, 29, 20], [49, 31, 20]):
        for strength in (1.0, 1.1, 1.2):
            for water_factor in (0.5, 1.0, 1.5):
                req = base_request(strength)
                req['cation_shares'] = cations
                req['water']['totals_mol_kg'] = {
                    k: v * water_factor for k, v in req['water']['totals_mol_kg'].items()
                }
                name = f'c{cations[0]}_{cations[1]}_s{strength}_w{water_factor}'
                result.append(
                    (
                        name,
                        'feasible',
                        req,
                        'Independent nominal allocation witness; '
                        'uncertainty acceptance assessed separately',
                    )
                )
    return result


def sulfate_counterexample(request, grams):
    """Explicit admissible interval corner, independent of uncertainty-bound code.

    High source-water quantity/sulfate and sulfate-product mass; low nitrate/
    phosphate assays, source concentrations and other product masses. All blend
    ingredient fractions share their declared 0.99 low multiplier in this anchor.
    """
    from flahax.product_conversion import material_inventory

    masses = {'N_NO3': 14.0067, 'P': 30.973762, 'S': 32.06}
    bases = {'N_NO3': 'NO3-', 'P': 'PO4-3', 'S': 'SO4-2'}
    amount = {
        k: request['water']['totals_mol_kg'][b] * 0.101 * 1000 * (1.01 if k == 'S' else 0.99)
        for k, b in bases.items()
    }
    for index, (product, dose) in enumerate(zip(request['products'], grams)):
        percent = material_inventory(product['product'])['nutrient_percent']
        for k in amount:
            amount[k] += (
                (round(dose, 5) + (0.001 if index == 2 else -0.001))
                * 10
                * percent.get(k, 0)
                * (1 if k == 'S' else 0.99)
                / masses[k]
            )
    sulfate = 2 * amount['S'] / (amount['N_NO3'] + amount['P'] + 2 * amount['S'])
    target = request['anion_shares'][2] / sum(request['anion_shares'])
    return dict(
        analytical_batch_mmol=amount,
        sulfate_share=sulfate,
        target=target,
        relative_error=abs(sulfate / target - 1),
    )


def stress_case(case):
    req = case[2]
    witness = independent_witness(req)
    counterexample = sulfate_counterexample(req, witness['grams'])
    if counterexample['relative_error'] <= 0.01:
        result = exercise(case, witness=witness)
        result['expected_disposition'] = 'accepted_under_declared_bounds'
    else:
        actual = plan_ratio_recipe(**req)
        rounded, check = actual['rounded_verification'], actual['uncertainty_verification']
        assert rounded['status'] == 'passed'
        assert check['status'] == 'failed' and check['failed_checks'] == ['nutrient_ratios']
        assert actual['nutrient_ceiling_reserve']['fraction'] == 0.05
        assert check['scenario_count'] == 128
        assert all(s['complete'] for s in check['ph_refinement']['scenarios'])
        assert check['all_scenario_ph_in_range']
        assert all(p['si'] < -0.3000001 for p in check['phase_maxima'].values())
        assert check['worst_concentration_relative_error'] <= 0.02
        for k, value in check['elemental_mg_l_ranges'].items():
            assert value[1] <= 0.95 * req['maximum_concentrations'][k]
        actual_witness = sulfate_counterexample(req, [r['grams'] for r in rounded['ingredients']])
        assert actual_witness['relative_error'] > 0.01
        assert (
            abs(actual_witness['sulfate_share'] * 100 - check['ratio_percent_ranges'][5][1])
            < 1e-10
        )
        assert not actual['verified'] and not actual['stable']
        assert abs(actual['charge_closure_error_mol_kg']) <= 1e-10
        result = dict(
            case=case[0],
            status='passed',
            expected_disposition='reject_uncertain_ratio',
            independent_witness=witness,
            uncertainty_counterexample=actual_witness,
            rounded_grams={r['name']: r['grams'] for r in rounded['ingredients']},
            phase_maxima=check['phase_maxima'],
            request=req,
            allocation_evidence=actual['allocation_evidence'],
            ratio_error=check['worst_ratio_relative_error'],
            count_error=check['worst_concentration_relative_error'],
            scenario_count=check['scenario_count'],
            ph_evaluations=check['ph_refinement']['total_ph_evaluations'],
            nutrient_ranges=check['elemental_mg_l_ranges'],
            charge_closure_error=actual['charge_closure_error_mol_kg'],
        )
    # Independent direct components from the witness give an additional chemistry
    # check without rerunning or weakening the public uncertainty calculation.
    from flahax.product_conversion import material_inventory

    req = case[2]
    totals = {
        k: v * req['water']['source_water_mass_kg'] / req['water_mass_kg']
        for k, v in req['water']['totals_mol_kg'].items()
    }
    for product in req['products']:
        name = product['product']['name']
        for k, v in material_inventory(product['product'])['components_moles_per_gram'].items():
            totals[k] = totals.get(k, 0) + result['rounded_grams'][name] * v / req['water_mass_kg']
    maximum = dict(si=0.0, ionic_strength=0.0, residual_fraction=0.0, iterations=0)
    for ph in (6.28, 6.30, 6.32):
        cold = solve(totals, ph)
        repeated = solve(totals, ph)
        warm = solve(totals, ph, start=solve(totals, ph + 0.03))
        assert cold.species == repeated.species
        for phase in result['phase_maxima']:
            delta = abs(cold.saturation_indices[phase] - warm.saturation_indices[phase])
            assert delta < 1e-8
            maximum['si'] = max(maximum['si'], delta)
        delta = abs(cold.ionic_strength - warm.ionic_strength)
        assert delta < 1e-11
        maximum['ionic_strength'] = max(maximum['ionic_strength'], delta)
        for state in (cold, warm):
            maximum['iterations'] = max(maximum['iterations'], state.iterations)
            assert state.iterations < 1500
            for key, residual in state.residuals.items():
                fraction = abs(residual) / (1e-9 * state.totals[key] + 1e-15)
                assert fraction < 1
                maximum['residual_fraction'] = max(maximum['residual_fraction'], fraction)
    result['cold_warm_repeatability'] = maximum
    return result


class SolverStressTests(unittest.TestCase):
    """Each generated method runs one complete uncertainty-preserving recipe."""


def install(case):
    def test(self):
        stress_case(case)

    setattr(SolverStressTests, 'test_' + case[0].replace('.', '_'), test)


for _case in stress_cases():
    install(_case)


class SolverBoundaryTests(unittest.TestCase):
    def test_nonfinite_negative_and_boolean_inputs_are_rejected(self):
        for key, value in (
            ('ph', float('nan')),
            ('counted_mmol_l', float('inf')),
            ('counted_mmol_l', -1),
            ('volume_litres', True),
            ('cation_shares', [50, -1, 20]),
            ('anion_shares', [0, 0, 0]),
        ):
            with self.subTest(field=key, value=value):
                req = base_request()
                req[key] = value
                with self.assertRaises(DeliveryError) as caught:
                    plan_ratio_recipe(**req)
                expected = (
                    'invalid_analysis_uncertainty'
                    if key == 'volume_litres'
                    else 'invalid_ratio_input'
                )
                self.assertEqual(caught.exception.code, expected)

    def test_required_assays_and_unsupported_inputs_are_rejected(self):
        for change in (
            'missing_assay',
            'missing_counterion_bound',
            'unknown_water_ion',
            'unknown_phase',
            'reactive_impurity',
        ):
            req = base_request()
            expected = None
            if change == 'missing_assay':
                req['uncertainty']['product_element_factors'].pop('Synthetic KH2PO4')
                expected = 'invalid_analysis_uncertainty'
            elif change == 'missing_counterion_bound':
                req['products'][-1]['product']['elements'].pop('Na')
                req['uncertainty']['product_element_factors']['Synthetic sodium-bearing base'].pop(
                    'Na'
                )
                expected = 'invalid_totals'
            elif change == 'unknown_water_ion':
                req['water']['totals_mol_kg']['NO2-'] = 0.001
                expected = 'invalid_ratio_water'
            elif change == 'unknown_phase':
                req['selected_phases'] = ['Invented mineral']
                expected = 'invalid_phases'
            else:
                req['uncertainty']['impurity_model'] = 'carbonate'
                expected = 'invalid_analysis_uncertainty'
            with self.subTest(change=change), self.assertRaises(DeliveryError) as caught:
                plan_ratio_recipe(**req)
            self.assertEqual(caught.exception.code, expected)

    def test_insufficient_uncertainty_budget_is_incomplete(self):
        req = base_request()
        req['uncertainty']['max_scenarios'] = 1
        result = plan_ratio_recipe(**req)
        self.assertEqual(result['nutrient_ceiling_reserve']['fraction'], 0.05)
        self.assertEqual(result['rounded_verification']['status'], 'passed')
        check = result['uncertainty_verification']
        self.assertEqual(check['status'], 'incomplete')
        self.assertIn('insufficient_sampling_budget', check['failed_checks'])
        self.assertEqual(check['scenario_count'], 0)
        self.assertFalse(result['verified'])
        self.assertFalse(result['stable'])


class RefinementBudgetTests(unittest.TestCase):
    def test_below_limit_samples_do_not_hide_exhausted_refinement(self):
        import math
        from types import SimpleNamespace
        from flahax.ratio_ph_refinement import refine_ph

        phases = ('CaHPO4:2H2O', 'CaHPO4', 'Hydroxylapatite')
        grid = [6.28 + i * 0.001 for i in range(41)]

        def curve(ph):
            # Deliberately oscillatory numerical fixture, not a chemical prediction.
            value = -1 + 0.01 * math.cos(1000 * math.pi * (ph - 6.28))
            return SimpleNamespace(saturation_indices=dict.fromkeys(phases, value))

        states, report = refine_ph(curve, grid, phases, -0.3000001)
        self.assertTrue(
            all(s.saturation_indices[p] < -0.3000001 for s in states.values() for p in phases)
        )
        self.assertFalse(report['complete'])
        self.assertTrue(report['unresolved_intervals'])
        self.assertLessEqual(report['added_points'], report['max_additional_points'])
        self.assertLessEqual(report['rounds'], report['max_rounds'])
        self.assertFalse(report['continuous_extrema_proved'])


class RoundedBoundaryTests(unittest.TestCase):
    def test_coarse_rounding_cannot_inherit_the_unrounded_pass(self):
        req = base_request(1.2680127620697021)
        req['mass_decimals'] = 0
        result = plan_ratio_recipe(**req)
        self.assertTrue(result['limit_assessment']['passed'])
        self.assertEqual(result['rounded_verification']['status'], 'failed')
        self.assertNotEqual(result['uncertainty_verification']['status'], 'passed')
        self.assertFalse(result['verified'])
        self.assertFalse(result['stable'])

    def test_adjacent_rounded_candidates_respect_nitrate_reserve(self):
        reserve_boundary()


def reserve_boundary():
    results = []
    for strength, expected in (
        (1.2680127620697021, 'passed'),
        (1.268019676208496, 'failed'),
    ):
        result = plan_ratio_recipe(**base_request(strength))
        rounded, check = result['rounded_verification'], result['uncertainty_verification']
        assert result['nutrient_ceiling_reserve']['fraction'] == 0.05
        assert rounded['status'] == 'passed'
        assert check['status'] == expected
        assert check['scenario_count'] == 128
        assert all(x['complete'] for x in check['ph_refinement']['scenarios'])
        assert all(x['si'] < -0.3000001 for x in check['phase_maxima'].values())
        assert check['worst_ratio_relative_error'] <= 0.01
        assert check['worst_concentration_relative_error'] <= 0.02
        if expected == 'failed':
            assert check['failed_checks'] == ['nutrient_limits']
            assert check['elemental_mg_l_ranges']['N_NO3'][1] > 5.7
        else:
            assert check['elemental_mg_l_ranges']['N_NO3'][1] <= 5.7
        assert not result['verified'] and not result['stable']
        results.append(result)
    return results
