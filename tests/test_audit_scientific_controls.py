# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Audit controls for unit bases, domain/qualification propagation and published claims.

These are minimum counterexamples, not complete scientific closure tests. An assertion
about lost metadata or an unsupported statement does not establish physical accuracy.
"""

from fractions import Fraction
import json
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from flahax import calculate_equilibrium_ph, load_library, recommend, summarize_batch
from flahax.batch_cli import read_water
from flahax.delivery_contracts import DeliveryError
from flahax.irrigation_ec import calculate_ec_from_totals
from flahax.measured_water import _carbon_for_alkalinity
from flahax.saturation_policy import assess_saturation
from flahax.tank_grouping import group_tanks
from tests.audit_oracles import competition_is_explicitly_qualified

ROOT = Path(__file__).resolve().parents[1]


class ScientificOracleTests(unittest.TestCase):
    def test_solvent_mass_changes_molality_not_analytical_mg_per_litre(self):
        c, volume, molar_mass = Fraction(20), Fraction(1), Fraction(40)
        first = c * volume / (1000 * molar_mass * 1)
        second = c * volume / (1000 * molar_mass * 2)
        self.assertEqual(first / second, 2)

    def test_reference_agreement_does_not_determine_si_sign(self):
        si, agreement_allowance = Fraction('0.1'), Fraction('0.25')
        self.assertLess(si - agreement_allowance, 0)
        self.assertGreater(si + agreement_allowance, 0)

    def test_restricted_cucumber_source_bound(self):
        calcium, nitrate_target = Fraction(200), Fraction(140)
        ratio = Fraction('14.4') / 19
        self.assertGreater(calcium * ratio, nitrate_target)
        k = calcium * ratio / nitrate_target
        u = (1 + k) / (1 + k * k)
        self.assertEqual((u - 1) + k * (k * u - 1), 0)
        self.assertGreater((u - 1) ** 2 + (k * u - 1) ** 2, 0)


class ScientificAuditRegressionTests(unittest.TestCase):
    def test_f06_explicit_solvent_basis_is_not_silently_ignored(self):
        configurations = []
        with tempfile.TemporaryDirectory() as directory:
            for mass in (1, 2):
                path = Path(directory) / f'water-{mass}.json'
                path.write_text(
                    json.dumps(
                        {
                            'mg_per_litre': {'Ca': 20},
                            'measured_ph': 7,
                            'water_mass_kg': mass,
                            'final_volume_litres': 1,
                        }
                    ),
                    encoding='utf-8',
                )
                try:
                    configurations.append(read_water(str(path))[2])
                except DeliveryError as error:
                    # Explicit rejection is honest until the input contract supports this basis.
                    self.assertTrue(
                        any(
                            word in str(error).lower()
                            for word in ('mass', 'volume', 'basis', 'unknown')
                        )
                    )
                    return
        self.assertLess(
            configurations[1]['water_totals']['Ca+2'], configurations[0]['water_totals']['Ca+2']
        )

    def test_f07_known_zero_carbon_cannot_be_overwritten_by_total_alkalinity(self):
        # The scalar is a declared synthetic assay, not a verified equilibrium state.
        # A contradictory or unsupported analysis may be rejected; known zero carbon
        # must not silently change. The independent proton-inventory witness is in
        # test_audit_oracles; it does not assert this helper input is charge-balanced.
        try:
            inferred = _carbon_for_alkalinity(
                {'PO4-3': 0.001, 'CO3-2': 0.0}, 8, 0.0008859033379310278, []
            )
        except DeliveryError as error:
            self.assertTrue(
                any(
                    word in error.code
                    for word in ('unsupported', 'inconsistent', 'alkalinity', 'carbon')
                )
            )
            return
        self.assertEqual(inferred, 0, 'known zero carbon cannot become inferred positive carbon')

    def test_f08_phosphate_fit_extrapolation_is_reported(self):
        result = calculate_ec_from_totals(
            {'Na+': 0.02, 'PO4-3': 0.02},
            solution_id='audit-phosphate',
            ph_mode='calculated',
            phase_policy='dissolved',
        )
        self.assertGreater(result.ionic_strength, result.audit['phosphate_fit_max_ionic_strength'])
        self.assertTrue(
            result.warnings or result.status == 'not_supported',
            'the empirical-fit domain is narrower than the speciation domain',
        )

    def test_f09_grower_summary_preserves_ec_qualification(self):
        from tests.test_grower_outputs import PRODUCTS, workflow

        result = workflow('Tomato (Howard Resh)', products=[])
        captured = []

        def capture(*args, **kwargs):
            computed = calculate_ec_from_totals(*args, **kwargs)
            captured.append(computed)
            return computed

        # Observe the actual calculation; do not replace its chemistry or its result.
        with patch('flahax.grower_report.calculate_ec_from_totals', side_effect=capture):
            summary = summarize_batch(result, PRODUCTS, title='Audit', water_label='RO')
        self.assertIsNotNone(summary['ec'])
        self.assertEqual(len(captured), 1)
        self.assertTrue(
            'ec25_range_ms_cm' in summary['ec'] and 'warnings' in summary['ec'],
            'a midpoint/status alone loses the EC interval and qualifications',
        )
        self.assertEqual(summary['ec']['ec25_range_ms_cm'], captured[0].ec25_range_ms_cm)
        self.assertEqual(tuple(summary['ec']['warnings']), captured[0].warnings)

    def test_f10_two_tank_preference_cannot_waive_a_separation(self):
        names = [
            'Calcium Nitrate (ag grade)',
            'Magnesium Sulfate (Heptahydrate)',
            'Potassium Monobasic Phosphate',
        ]
        products = [p for p in load_library()['salts'] if p['name'] in names]
        rows = [dict(id=p['id'], name=p['name'], gramsPerLitre=1) for p in products]
        try:
            grouping = group_tanks(rows, products)
        except DeliveryError as error:
            self.assertTrue(
                error.code == 'too_many_tanks'
                or any(word in error.code for word in ('unsupported', 'incompatible'))
            )
            return
        self.assertFalse(grouping.waived, 'equipment preference is not compatibility evidence')
        self.assertNotEqual(grouping.tank_of(names[1]), grouping.tank_of(names[2]))

    def test_f11_unverified_source_chain_is_not_reported_as_proven_absence(self):
        state = SimpleNamespace(saturation_indices={'MnHPO4': 1.0}, precipitated={}, totals={})
        assessment = assess_saturation(state)
        reasons = ' '.join(row[2] for row in assessment['review'])
        self.assertNotIn('no measurement behind it', reasons)

    def test_f12_omitted_ammonium_uses_disclosed_dutch_default(self):
        # Owner decision 2026-10-28 / #54: Dutch min(10% of N, 1.5 mmol/L) when N_NH4
        # is omitted; disclosed on ammoniumLimit (not a silent invented ceiling).
        products = [
            dict(
                id='synthetic',
                name='Synthetic audit product',
                elements={'K': 10, 'N_NO3': 10, 'N_NH4': 1},
            )
        ]
        result = recommend(products, {'K': 100, 'N_NO3': 100}, {})
        limit = result['ammoniumLimit']
        self.assertEqual(limit['fractionOfTotalN'], 0.10)
        self.assertAlmostEqual(limit['mgPerL'], 10.0)
        self.assertAlmostEqual(limit['absoluteCapMgPerL'], 1.5 * 14.0067)
        self.assertIn('Dutch', limit['basis'])
        self.assertIn('achievedMgPerL', limit)
        opted_out = recommend(products, {'K': 100, 'N_NO3': 100}, {}, max_ammonium_fraction=None)
        self.assertIsNone(opted_out.get('ammoniumLimit'))

    def test_f13_omitted_ligand_competition_is_not_silently_qualified(self):
        # The pinned model has DTPA protonation and Fe-DTPA, but no Cu-DTPA reaction.
        # This is an admission/diagnosis control, not a predicted Cu-DTPA concentration.
        # Expanding the reaction set requires separately reviewed parameters and tests.
        try:
            result = calculate_equilibrium_ph(
                {'Dtp-5': 0.001, 'Cu+2': 0.001, 'Na+': 0.003},
                complete_analysis=True,
                carbon_boundary='closed',
                phases=[],
            )
        except DeliveryError as error:
            self.assertTrue(any(word in error.code for word in ('unsupported', 'incomplete')))
            return
        self.assertTrue(
            competition_is_explicitly_qualified(result, ('Dtp-5', 'Cu+2')),
            'return an explicit omitted-competition limitation or refuse the calculation',
        )

    def test_f14_release_banner_agrees_with_its_own_publication_records(self):
        text = (ROOT / 'docs/site/evidence/release-evidence.md').read_text(encoding='utf-8')
        current = re.search(r'Current release: ([0-9]+\.[0-9]+\.[0-9]+)', text)
        publications = re.findall(r'^## ([0-9]+\.[0-9]+\.[0-9]+) publication', text, re.M)
        self.assertIsNotNone(current)
        self.assertTrue(publications)
        latest = max(publications, key=lambda v: tuple(int(n) for n in v.split('.')))
        self.assertEqual(current.group(1), latest)


if __name__ == '__main__':
    unittest.main()
