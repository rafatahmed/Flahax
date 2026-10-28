# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Independent material arithmetic and explicit evidence status, without lot claims."""

from fractions import Fraction
from decimal import Decimal
from copy import deepcopy
import json
from pathlib import Path
import unittest

from flahax import load_library, recommend
from flahax.composition import ATOMIC, ATOMIC_CONVENTION, InputError, theoretical_assay
from flahax.delivery_contracts import DeliveryError
from flahax.materials import OXIDE_FACTORS, _check, load_identities, resolve_material
from flahax.product_conversion import MOLAR_MASS
from tests.test_materials import grade, lot


class MaterialConventionTests(unittest.TestCase):
    def test_malformed_mass_and_stoichiometry_have_stable_diagnostics(self):
        original = next(iter(load_identities().values()))
        for value in (float('nan'), float('inf'), True, False, 0, -1, '12'):
            for field in ('molecular_weight', 'ion_forms'):
                candidate = deepcopy(original)
                if field == 'ion_forms':
                    candidate[field][next(iter(candidate[field]))] = value
                else:
                    candidate[field] = value
                with (
                    self.subTest(field=field, value=value),
                    self.assertRaises(DeliveryError) as err,
                ):
                    _check(candidate)
                self.assertEqual(err.exception.code, 'invalid_identity_record')
        candidate = deepcopy(original)
        candidate['molecular_weight'] = None
        _check(candidate)  # explicitly unavailable is distinct from a fabricated number

    def test_frozen_atomic_convention_and_conversion_tables_agree(self):
        self.assertEqual(ATOMIC_CONVENTION, 'flahax-atomic-legacy-1')
        for element, value in MOLAR_MASS.items():
            self.assertEqual(value, ATOMIC[element], element)

    def test_all_retained_values_have_a_versioned_reference_comparison(self):
        path = Path(__file__).parent / 'fixtures/materials/atomic_convention.json'
        fixture = json.loads(path.read_text())
        self.assertEqual(fixture['convention'], ATOMIC_CONVENTION)
        self.assertEqual(set(fixture['elements']), set(ATOMIC))
        for element, (retained, low, high) in fixture['elements'].items():
            with self.subTest(element=element):
                value = Decimal(retained)
                self.assertEqual(Decimal(str(ATOMIC[element])), value)
                self.assertLessEqual(Decimal(low).quantize(value), value)
                self.assertGreaterEqual(Decimal(high).quantize(value), value)

    def test_hydrate_and_nitrogen_forms_from_independent_atom_counts(self):
        # Literal, exact decimal compatibility masses; no production parser/oracle reuse.
        h, n, o, mg = map(Fraction, ('1.00784', '14.0067', '15.999', '24.305'))
        mass = mg + 2 * n + 12 * o + 12 * h  # Mg(NO3)2.6H2O
        assay = theoretical_assay('Mg(NO3)2.6H2O')
        self.assertAlmostEqual(assay['Mg'], float(100 * mg / mass), places=12)
        self.assertAlmostEqual(assay['N_NO3'], float(200 * n / mass), places=12)
        ammonium_nitrate = theoretical_assay('NH4NO3')
        expected = float(100 * n / (2 * n + 4 * h + 3 * o))
        self.assertAlmostEqual(ammonium_nitrate['N_NO3'], expected, places=12)
        self.assertAlmostEqual(ammonium_nitrate['N_NH4'], expected, places=12)

    def test_oxide_mass_fraction_from_independent_rational_arithmetic(self):
        p, oxygen = Fraction('30.973762'), Fraction('15.999')
        element, factor = OXIDE_FACTORS['P2O5']
        self.assertEqual(element, 'P')
        self.assertAlmostEqual(factor, float(2 * p / (2 * p + 5 * oxygen)), places=15)

    def test_every_catalogue_product_has_explicit_source_and_assumption_status(self):
        for salt in load_library()['salts']:
            with self.subTest(product=salt['name']):
                material = resolve_material(salt['name'])
                provenance = material.provenance
                self.assertEqual(provenance['atomicMassConvention'], ATOMIC_CONVENTION)
                self.assertEqual(
                    provenance['sourceStatus'],
                    'catalogue_documented'
                    if salt['source'] is not None
                    else 'catalogue_unattributed',
                )
                self.assertIn(
                    provenance['assumptionStatus'],
                    ('assumed_composition', 'declared_composition_not_independently_verified'),
                )

    def test_grade_and_lot_documents_do_not_become_catalogue_source(self):
        supplier_grade = grade()
        measured_lot = lot()
        graded = resolve_material('Potassium Monobasic Phosphate', grade=supplier_grade)
        measured = resolve_material(
            'Potassium Monobasic Phosphate', grade=supplier_grade, lot=measured_lot
        )
        self.assertEqual(graded.provenance['sourceStatus'], 'grade_documented')
        self.assertEqual(measured.provenance['sourceStatus'], 'lot_documented')
        self.assertIsNone(graded.provenance['source'])
        self.assertIsNone(measured.provenance['source'])

    def test_unattributed_product_is_not_reported_as_documented(self):
        result = recommend([dict(id='x', name='Synthetic', elements={'K': 10})], {'K': 100})
        provenance = result['salts'][0]['provenance']
        self.assertEqual(provenance['sourceStatus'], 'declared_unattributed')
        self.assertEqual(provenance['atomicMassConvention'], ATOMIC_CONVENTION)

    def test_total_nitrogen_is_not_silently_split(self):
        with self.assertRaises(InputError):
            recommend(load_library()['salts'], {'N': 100})


if __name__ == '__main__':
    unittest.main()
