# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Independent arithmetic witnesses for one joint nutrient/chemistry problem."""

from fractions import Fraction
import unittest

from flahax.joint_problem import JointSource, JointProblem
from flahax import DeliveryError


class JointContractTests(unittest.TestCase):
    def problem(self, **overrides):
        args = dict(
            fertilizers=(JointSource('salt', {'K': 0.1}, {'K+': 0.1 / 39.0983}),),
            reagent=JointSource(
                'acid',
                {'N_NO3': 0.2},
                {'NO3-': 0.2 / 14.0067},
                solvent_fraction=0.5,
                density_kg_per_litre=1.2,
            ),
            targets={'K': 100, 'N_NO3': 30},
            water={'N_NO3': 10},
            water_components={},
            final_volume_litres=10,
            solvent_mass_kg=8,
            target_ph=5.8,
            reference_charge_mol_per_kg=0,
            maximum_reagent_mass_g=2,
            maximum_concentrations={'Na': 0},
        )
        return JointProblem(**(args | overrides))

    def test_joint_mass_and_basis_conversion(self):
        result = self.problem().evaluate({'salt': 1}, 0.1)
        self.assertEqual(result['concentrations']['K'], 100)
        self.assertEqual(result['concentrations']['N_NO3'], 30)
        self.assertEqual(result['loss'], 0)
        self.assertEqual(result['reagentMassGrams'], 1)
        self.assertEqual(result['reagentSolventKg'], float(Fraction(1, 2000)))
        self.assertAlmostEqual(result['componentsMolPerKg']['K+'], 1 / 39.0983 / 8)
        self.assertAlmostEqual(result['componentsMolPerKg']['NO3-'], 0.2 / 14.0067 / 8)
        self.assertEqual(result['reagentVolumeLitres'], 1 / 1200)
        self.assertEqual(result['status'], 'requires_joint_acceptance')

    def test_zero_dose_and_scale(self):
        for volume, mass in ((10, 8), (100, 80)):
            result = self.problem(final_volume_litres=volume, solvent_mass_kg=mass).evaluate({}, 0)
            self.assertEqual(result['reagentMassGrams'], 0)
            self.assertEqual(result['reagentVolumeLitres'], 0)
            self.assertAlmostEqual(result['loss'], 1 + float(Fraction(2, 3) ** 2), places=14)
            self.assertTrue(all(v == 0 for v in result['componentsMolPerKg'].values()))

    def test_hard_constraints_are_not_objective_penalties(self):
        problem = self.problem(targets={'K': 0}, maximum_concentrations={'N_NO3': 20})
        result = problem.evaluate({'salt': 1}, 0.3)
        self.assertEqual(result['loss'], 0)
        self.assertEqual(
            {v['kind'] for v in result['violations']}, {'zero_target', 'maximum', 'reagent_mass'}
        )

    def test_missing_chemistry_is_explicit(self):
        result = self.problem(water_components=None).evaluate({}, 0)
        self.assertEqual(result['status'], 'missing_chemistry')
        self.assertIsNone(result['equilibrium'])

    def test_inputs_are_snapshotted(self):
        targets = {'K': 100}
        problem = self.problem(targets=targets)
        targets['K'] = 200
        self.assertEqual(problem.evaluate({'salt': 1}, 0)['loss'], 0)
        with self.assertRaises(TypeError):
            problem.targets['K'] = 2

    def test_chemistry_boundary_uses_explicit_reference_charge(self):
        p = self.problem(
            water={}, targets={'K': 0}, target_ph=7, reference_charge_mol_per_kg=0.002
        )
        r = p.evaluate({}, 0)
        # The explicit closure offset is subtracted once, independently of the
        # pinned water dissociation constant (pH 7 is not assumed exactly neutral).
        self.assertEqual(r['chargeResidual'], r['equilibrium'].charge_balance - 0.002)
        self.assertEqual(r['equilibrium'].ph, 7)
        self.assertEqual(r['status'], 'requires_joint_acceptance')

    def test_caps_missing_density_and_missing_source_components(self):
        bare = JointSource('bare', {}, None)
        r = self.problem(reagent=bare).evaluate({}, 0)
        self.assertIsNone(r['reagentVolumeLitres'])
        self.assertEqual(r['status'], 'requires_joint_acceptance')
        r = self.problem(reagent=bare).evaluate({}, 0.1)
        self.assertEqual(r['status'], 'missing_chemistry')
        wet = JointSource('wet', {}, {}, solvent_fraction=1, density_kg_per_litre=0.001)
        r = self.problem(
            reagent=wet,
            maximum_reagent_volume_litres=0.1,
            solvent_mass_kg=0.001,
            water_components=None,
            maximum_concentrations={'K': 50},
        ).evaluate({'salt': 1}, 2)
        self.assertTrue(
            {'solvent_inventory', 'reagent_volume', 'final_volume', 'contradictory_target'}
            <= {v['kind'] for v in r['violations']}
        )

    def test_reject_invalid_problem_inputs(self):
        bad = [
            dict(targets={}),
            dict(fertilizers=None),
            dict(phases=[1]),
            dict(targets=[]),
            dict(final_volume_litres=0),
            dict(solvent_mass_kg=-1),
            dict(target_ph=15),
            dict(target_ph=float('nan')),
            dict(reference_charge_mol_per_kg=True),
            dict(maximum_reagent_mass_g=-1),
            dict(water_components={'unknown': 1}),
            dict(phases='Calcite'),
            dict(phases=('unknown',)),
            dict(fertilizers=(None,)),
            dict(fertilizers=(JointSource('acid', {}, {}),)),
            dict(reagent=JointSource('bare', {}, {}), maximum_reagent_volume_litres=1),
        ]
        for kwargs in bad:
            with self.subTest(kwargs=kwargs), self.assertRaises((DeliveryError, ValueError)):
                self.problem(**kwargs)
        for args in (
            ('', {}, {}),
            ('x', {'K': 2}, {}),
            ('x', {}, {'unknown': 1}),
            ('x', {}, {'K+': -1}),
        ):
            with self.assertRaises(DeliveryError):
                JointSource(*args)
        with self.assertRaises(DeliveryError):
            JointSource('x', {}, {}, density_kg_per_litre=0)
        for doses, q in (
            ([], 0),
            ({'absent': 1}, 0),
            ({'salt': -1}, 0),
            ({}, -1),
            ({}, True),
            ({}, float('inf')),
            ({'salt': 1e308}, 0),
        ):
            with self.assertRaises(DeliveryError):
                self.problem().evaluate(doses, q)

    def test_nonrepresentable_derived_quantities_fail_explicitly(self):
        with self.assertRaises(DeliveryError):
            self.problem(targets={'K': 1e-300}).evaluate({'salt': 1}, 0)
        with self.assertRaises(DeliveryError):
            self.problem(
                reagent=JointSource('tiny', {}, {}, density_kg_per_litre=1e-320)
            ).evaluate({}, 0.1)

    def test_nonconvergence_is_not_a_success(self):
        from unittest.mock import patch

        with patch(
            'flahax.joint_problem.solve', side_effect=DeliveryError('nonconvergent', 'test')
        ):
            with self.assertRaises(DeliveryError):
                self.problem().evaluate({}, 0)

    def test_inventory_adapter_preserves_assay_and_solvent_basis(self):
        from flahax import make_joint_problem

        reagent = dict(
            id='nitric',
            chemicalFormula='HNO3',
            massFraction=0.65,
            densityKgPerL=1.3,
            source='test',
            revision='1',
            recordedAt='2026-10-26',
        )
        inputs = dict(
            water_components={},
            final_volume_litres=100,
            solvent_mass_kg=80,
            target_ph=7,
            reference_charge_mol_per_kg=0,
            maximum_reagent_mass_g=20,
        )
        p = make_joint_problem(
            [], reagent, {'N_NO3': 1}, {}, reagent_solvent_fraction=0.35, **inputs
        )
        r = p.evaluate({}, 0.1)
        expected = (
            Fraction(10) * Fraction('0.65') / Fraction('63.01284') * Fraction('14.0067') * 10
        )
        self.assertAlmostEqual(r['concentrations']['N_NO3'], float(expected), places=12)
        self.assertAlmostEqual(
            r['componentsMolPerKg']['NO3-'],
            float(Fraction('6.5') / Fraction('63.01284') / 80),
            places=15,
        )
        self.assertEqual(r['reagentVolumeLitres'], 10 / 1300)
        for salt in (dict(id='a', name='a', role='ph_reagent', elements={'K': 10}),):
            with self.assertRaises(DeliveryError):
                make_joint_problem(
                    [salt], reagent, {'K': 1}, {}, reagent_solvent_fraction=0.35, **inputs
                )
        with self.assertRaises(DeliveryError):
            make_joint_problem([], reagent, {'K': 1}, {}, reagent_solvent_fraction=0.5, **inputs)
        p = make_joint_problem(
            [dict(id='a', name='a', elements={'K': 10})],
            reagent,
            {'K': 1},
            {},
            reagent_solvent_fraction=0.35,
            **inputs,
        )
        self.assertEqual(p.evaluate({'a': 0.01}, 0)['status'], 'missing_chemistry')

    def test_nonzero_basis_scaling_and_pinned_reference(self):
        import json
        from pathlib import Path
        from flahax import make_joint_problem

        data = json.loads(
            (
                Path(__file__).parent / 'fixtures/phreeqc/acid_selection/HNO3/expected.json'
            ).read_text()
        )
        reagent = dict(
            id='nitric',
            chemicalFormula='HNO3',
            massFraction=0.5,
            densityKgPerL=1.2,
            source='pinned synthetic reference',
            revision='1',
            recordedAt='2026-10-26',
        )
        doses = []
        for v, w in ((10, 8), (100, 80)):
            problem = make_joint_problem(
                [],
                reagent,
                {'Na': 36.783632},
                {'Na': 36.783632, 'Cl': 56.7248},
                reagent_solvent_fraction=0.5,
                water_components=data['totals'],
                final_volume_litres=v,
                solvent_mass_kg=w,
                target_ph=data['target_ph'],
                reference_charge_mol_per_kg=0,
                maximum_reagent_mass_g=1,
            )
            q = data['acid_molal'] * w * 63.01284 / 0.5 / v
            r = problem.evaluate({}, q)
            doses.append(r['componentsMolPerKg']['NO3-'])
            self.assertAlmostEqual(doses[-1], data['acid_molal'], places=18)
            state = r['equilibrium']
            # Existing product-reference ionic-strength and conservation criteria.
            reference = data['selected_rows'][-1]['mu']
            self.assertAlmostEqual(state.ionic_strength, reference, delta=0.03 * reference + 1e-9)
            for component, residual in state.residuals.items():
                self.assertLess(abs(residual), 1e-9 * state.totals[component] + 1e-15)
            self.assertEqual(r['violations'], [])
        self.assertEqual(doses[0], doses[1])
