# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Independent equation, provenance and explicitly limited model-domain checks."""

from copy import deepcopy
from fractions import Fraction
import math
from pathlib import Path
import unittest
from unittest.mock import patch

from flahax import DeliveryError, calculate_equilibrium_ph
from flahax.aqueous_model import chemistry, model_qualification, solve
from tools.qualify_chemistry_model import audit_model, composition, equation

ROOT = Path(__file__).resolve().parents[1]


class ReactionQualificationTests(unittest.TestCase):
    def test_all_225_reactions_conserve_atoms_charge_and_basis(self):
        sources = {
            p.name: p.read_text()
            for p in (ROOT / 'tests/fixtures/phreeqc/database').glob('flahax-*.dat')
        }
        report = audit_model(chemistry(), sources)
        self.assertEqual(report['errors'], [])
        self.assertEqual(len(report['reactions']), 225)
        self.assertEqual(sum(r['kind'] == 'phases' for r in report['reactions']), 28)
        for row in report['reactions']:
            self.assertTrue(all(row['checks'].values()), row['name'])
            if row['source'] != 'minteq.v4.dat':
                self.assertTrue(row['source_verified'], row['name'])
            self.assertEqual(row['experimental_applicability'], 'not independently requalified')

    def test_independent_parser_handles_ligand_charge_and_hydrate(self):
        self.assertEqual(composition('FeDtp-2'), dict(Fe=1, C=14, H=18, N=3, O=10, charge=-2))
        self.assertEqual(composition('MgNH4PO4:6H2O'), dict(Mg=1, N=1, H=16, P=1, O=10))
        self.assertEqual(equation('2 H+ + SO4-2 = H2SO4'), {'H+': -2, 'SO4-2': -1, 'H2SO4': 1})
        self.assertEqual(equation('Ure = Ure'), {})
        self.assertEqual(equation('0.5 H2 = H'), {'H2': Fraction(-1, 2), 'H': 1})
        for invalid in ('H@', 'H)', '(H', 'H(2)'):
            with self.assertRaises(ValueError):
                composition(invalid)

    def test_changed_coefficients_charge_and_logk_are_detected(self):
        for field, value, check in (
            ('beta', 123.0, 'log_k_transform'),
            ('charge', 99, 'stored_charge'),
            ('powers', {'H+': 99}, 'transformed_atoms_and_charge'),
            ('equation', 'H2O = 2 OH-', 'original_atoms_and_charge'),
        ):
            model = deepcopy(chemistry())
            next(r for r in model['aqueous'] if r['name'] == 'OH-')[field] = value
            report = audit_model(model)
            self.assertEqual(report['status'], 'failed')
            self.assertTrue(any(check in e for e in report['errors']), report['errors'])
        model = deepcopy(chemistry())
        model['phases'][0]['beta'] += 0.01
        self.assertIn('phases/Zincite: log_k_transform', audit_model(model)['errors'])

    def test_source_line_and_constant_mismatches_are_detected(self):
        name = 'flahax-chelates-25c.dat'
        text = (ROOT / 'tests/fixtures/phreeqc/database' / name).read_text()
        wrong_k = audit_model(chemistry(), {name: text.replace('log_k 28.60', 'log_k 28.61')})
        self.assertIn('aqueous/FeDtp-2: source_log_k', wrong_k['errors'])
        wrong_eq = audit_model(chemistry(), {name: text.replace('Fe+3 + Dtp-5', 'Fe+2 + Dtp-5')})
        self.assertIn('aqueous/FeDtp-2: source_equation', wrong_eq['errors'])

    def test_fixed_activity_parameter_sensitivity_for_every_reaction(self):
        # At fixed activities, +log10(2) in a formation beta doubles a species
        # activity; in a dissolution beta it lowers SI by log10(2). This is a
        # derivative identity, not a bound on coupled composition uncertainty.
        logs = {b: -4.0 for b in chemistry()['bases']}
        logs.update({'H+': -6.0, 'H2O': math.log10(0.999)})
        delta = math.log10(2)
        for kind in ('aqueous', 'phases'):
            for r in chemistry()[kind]:
                action = sum(v * logs[b] for b, v in r['powers'].items())
                sign = 1 if kind == 'aqueous' else -1
                before = action + sign * r['beta']
                after = action + sign * (r['beta'] + delta)
                self.assertAlmostEqual(after - before, sign * delta, places=12, msg=r['name'])


class ModelDomainTests(unittest.TestCase):
    def test_every_selected_ligand_metal_pair_is_classified(self):
        metals = ('Ca+2', 'Mg+2', 'Fe+2', 'Fe+3', 'Mn+2', 'Zn+2', 'Cu+2')
        for ligand in ('Edta-4', 'Citrate-3', 'Dtp-5', 'Edd-4'):
            for metal in metals:
                limitations, _ = model_qualification({ligand: 1e-6, metal: 1e-6})
                omitted = [
                    r['components'] for r in limitations if r['code'] == 'omitted_competition'
                ]
                expected = (
                    [(ligand, metal)] if ligand in ('Dtp-5', 'Edd-4') and metal != 'Fe+3' else []
                )
                self.assertEqual(omitted, expected)

    def test_zero_inputs_do_not_activate_omitted_competition(self):
        for totals in ({}, {'Dtp-5': 0, 'Cu+2': 1}, {'Dtp-5': 1, 'Cu+2': 0}):
            limitations, _ = model_qualification(totals)
            self.assertFalse(any(r['code'] == 'omitted_competition' for r in limitations))

    def test_calculated_and_fixed_ph_keep_exact_pair_limitations(self):
        totals = {'Dtp-5': 0.001, 'Cu+2': 0.001, 'Na+': 0.003}
        for result in (
            solve(totals, 7),
            calculate_equilibrium_ph(
                totals, complete_analysis=True, carbon_boundary='closed', phases=[]
            ),
        ):
            self.assertIn(
                ('Dtp-5', 'Cu+2'), [r.get('components') for r in result.model_limitations]
            )
            self.assertIn('not experimental', result.model_domain['qualification'])
            self.assertEqual(
                result.model_domain['database_sha256'], chemistry()['database_sha256']
            )

    def test_returned_domain_records_are_independent(self):
        first = solve({}, 7)
        first.model_domain['temperature_c'] = 99
        self.assertEqual(solve({}, 7).model_domain['temperature_c'], 25)

    def test_no_new_constants_are_needed_for_qualifications(self):
        totals = {'Dtp-5': 1e-5, 'Cu+2': 1e-5, 'Na+': 3e-5}
        current = solve(totals, 6)
        with patch('flahax.aqueous_model.model_qualification', return_value=((), {})):
            without_metadata = solve(totals, 6)
        for field in ('species', 'activities', 'residuals', 'precipitated', 'ionic_strength'):
            self.assertEqual(getattr(current, field), getattr(without_metadata, field))

    def test_numerical_domain_edges_reject_extrapolation(self):
        for kwargs, code in (
            ({'ph': -1e-6}, 'out_of_range'),
            ({'ph': 14.000001}, 'out_of_range'),
            ({'temperature_c': 24.999}, 'temperature_out_of_range'),
            ({'temperature_c': 25.001}, 'temperature_out_of_range'),
            ({'ionic_strength': 0.100001}, 'activity_model_out_of_range'),
            ({'ionic_strength': -1e-6}, 'activity_model_out_of_range'),
        ):
            with self.assertRaises(DeliveryError) as caught:
                solve({}, **({'ph': 7} | kwargs))
            self.assertEqual(caught.exception.code, code)
        # The numerical pH interval does not override the ionic-strength boundary.
        for ph in (0, 14):
            with self.assertRaises(DeliveryError) as caught:
                solve({}, ph)
            self.assertEqual(caught.exception.code, 'activity_model_out_of_range')
        for strength in (0, 0.1):
            result = solve({'Na+': 1e-5, 'Cl-': 1e-5}, 7, ionic_strength=strength)
            self.assertEqual(result.ionic_strength, strength)

    def test_fixed_valence_urea_and_water_conventions_are_observable(self):
        result = solve({'Fe+2': 1e-6, 'Fe+3': 2e-6, 'Ure': 1e-5}, 6)
        for component in ('Fe+2', 'Fe+3', 'Ure'):
            self.assertLess(
                abs(result.residuals[component]), 1e-9 * result.totals[component] + 1e-15
            )
        self.assertAlmostEqual(result.species['Ure'], 1e-5, places=14)
        self.assertNotIn('NH4+', result.species)
        self.assertAlmostEqual(
            result.water_activity, max(0.9, 1 - sum(result.species.values()) / 55.5084), places=12
        )


class ReactionEvaluationTests(unittest.TestCase):
    def test_every_selected_reaction_is_evaluated_in_one_complete_inventory(self):
        result = solve({b: 1e-6 for b in chemistry()['bases']}, 6)
        for r in chemistry()['aqueous']:
            expected = r['beta'] + sum(
                v * math.log10(result.activities[b]) for b, v in r['powers'].items()
            )
            self.assertAlmostEqual(
                math.log10(result.activities[r['name']]), expected, places=9, msg=r['name']
            )
        for r in chemistry()['phases']:
            expected = (
                sum(v * math.log10(result.activities[b]) for b, v in r['powers'].items())
                - r['beta']
            )
            self.assertAlmostEqual(
                result.saturation_indices[r['name']], expected, places=9, msg=r['name']
            )

    def test_isolated_parameter_perturbation_has_predicted_response(self):
        totals = {'H3BO3': 1e-5}
        baseline = solve(totals, 9, ionic_strength=0.01)
        altered = deepcopy(chemistry())
        row = next(r for r in altered['aqueous'] if r['name'] == 'H2BO3-')
        row['beta'] += math.log10(2)
        with patch('flahax.aqueous_model.chemistry', return_value=altered):
            perturbed = solve(totals, 9, ionic_strength=0.01)

        def ratio(r):
            return r.activities['H2BO3-'] / r.activities['H3BO3']

        self.assertAlmostEqual(ratio(perturbed) / ratio(baseline), 2, places=9)
        # A phase-constant perturbation affects its SI without changing an
        # aqueous-only calculation. Copies exist only in memory for this test.
        totals = {'Ca+2': 1e-4, 'CO3-2': 1e-4}
        baseline = solve(totals, 7)
        altered = deepcopy(chemistry())
        next(r for r in altered['phases'] if r['name'] == 'Calcite')['beta'] += 1
        with patch('flahax.aqueous_model.chemistry', return_value=altered):
            perturbed = solve(totals, 7)
        self.assertEqual(perturbed.species, baseline.species)
        self.assertAlmostEqual(
            perturbed.saturation_indices['Calcite'] - baseline.saturation_indices['Calcite'],
            -1,
            places=12,
        )


class QualificationCommandTests(unittest.TestCase):
    def test_missing_source_constant_is_not_assumed(self):
        name = 'flahax-chelates-25c.dat'
        text = (ROOT / 'tests/fixtures/phreeqc/database' / name).read_text()
        for changed in (text.replace('    log_k 28.60', '# missing constant'), ''):
            report = audit_model(chemistry(), {name: changed})
            self.assertIn('aqueous/FeDtp-2: source_log_k', report['errors'])
            self.assertFalse(
                next(r for r in report['reactions'] if r['name'] == 'FeDtp-2')['source_verified']
            )

    def test_command_checks_base_hash_and_only_writes_report(self):
        import contextlib
        import hashlib
        import io
        import json
        import tempfile
        from tools import qualify_chemistry_model as checker

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data_dir = root / 'src/flahax/data'
            extension_dir = root / 'tests/fixtures/phreeqc/database'
            data_dir.mkdir(parents=True)
            extension_dir.mkdir(parents=True)
            base = root / 'minteq.v4.dat'
            base.write_text('H2O = H2O\n    log_k 0\n')
            for name in ('flahax-chelates-25c.dat', 'flahax-phases-25c.dat'):
                (extension_dir / name).write_text('')
            model = dict(
                bases=['H2O'],
                phases=[],
                aqueous=[
                    dict(
                        name='H2O',
                        source='minteq.v4.dat',
                        line=1,
                        equation='H2O = H2O',
                        powers={'H2O': 1},
                        charge=0,
                        beta=0,
                        log_k=0,
                    )
                ],
                database_sha256=hashlib.sha256(base.read_bytes()).hexdigest(),
            )
            path = data_dir / 'chemistry_25c.json'
            path.write_text(json.dumps(model))
            report = root / 'report.json'
            argv = ['checker', '--database', str(base), '--report', str(report)]
            for expected in (0, 1):
                before = base.read_bytes()
                with patch.object(checker, 'ROOT', root), patch('sys.argv', argv):
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(checker.main(), expected)
                self.assertEqual(base.read_bytes(), before)
                self.assertEqual(
                    json.loads(report.read_text())['status'],
                    'passed' if expected == 0 else 'failed',
                )
                base.write_text(base.read_text() + '# changes the hash only\n')
