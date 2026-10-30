# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Material record and chemistry guard checks for runtime coverage closure (#186)."""

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from flahax import DeliveryError
from flahax import materials as m
from flahax.material_chemistry import material_chemistry, chemistry_ions, chelate
from flahax.catalogue_chemistry import ProductChemistry
from tests.test_materials import grade, lot, DOC, MKP
from tests import test_materials as fixtures
from tests.catalogue_history import historical_catalogue


class MaterialRecordBoundaryTests(unittest.TestCase):
    def assert_code(self, code, function, *args, **kwargs):
        with self.assertRaises(DeliveryError) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_identity_structure_and_duplicate_inventory(self):
        valid = deepcopy(m.load_identities()[MKP])
        for field, value in [
            ('id', 'other'),
            ('status', 'unknown'),
            ('products', []),
            ('ion_forms', {}),
            ('comparator', {}),
            ('theoretical_analysis', {}),
        ]:
            with self.subTest(field=field):
                self.assert_code(
                    'invalid_identity_record', m._check, dict(valid, **{field: value})
                )
        missing = dict(valid)
        del missing['notes']
        self.assert_code('invalid_identity_record', m._check, missing)
        for second in (valid, dict(valid, id='idn-another')):
            raw = json.dumps({'identities': [valid, second]}).encode()
            with patch.object(m, '_RAW', raw):
                self.assert_code('invalid_identity_record', m._load.__wrapped__)

    def test_grade_and_lot_field_contracts(self):
        self.assert_code('invalid_value', m.make_grade, [])
        self.assert_code('invalid_value', m.make_lot, [])
        self.assert_code('invalid_value', lot, measured={})
        self.assert_code('invalid_value', lot, measured=[])
        self.assert_code('invalid_value', lot, measured={'K': 1, 'K2O': 1})
        for change in [
            dict(grade_id=''),
            dict(analysis={}),
            dict(chelating_agent='unknown'),
            dict(impurity_limits=[1]),
        ]:
            self.assert_code('invalid_value', grade, **change)
        for change in [dict(issued='not a date'), dict(url=1), dict(sha256='g' * 64)]:
            self.assert_code('invalid_value', grade, document=DOC | change)
        self.assert_code('invalid_composition', grade, composition='declared_ions')
        self.assert_code('invalid_composition', grade, components='bad')
        for components in ([None], [(MKP, 0.5), (MKP, 0.5)]):
            self.assert_code(
                'invalid_composition',
                grade,
                composition='disclosed',
                identity_id=None,
                components=components,
            )
        disclosed = grade(composition='disclosed', identity_id=None, components=[(MKP, 1)])
        self.assertEqual(disclosed.components, ((MKP, 1.0),))

    def test_declared_chemistry_checks_missing_forms_and_qualified_ligands(self):
        template = dict(
            grade_id='grd-synthetic',
            supplier='Example',
            product='Synthetic',
            composition='declared_ions',
            document=DOC,
        )

        def made(analysis, **kwargs):
            return m.make_grade(
                template | dict(analysis={k: {'typical': v} for k, v in analysis.items()}) | kwargs
            )

        self.assertFalse(m.declared_ions_check(made({'K': 1})).modellable)
        zero_n = dict(N_NO3=0, N_NH4=0, N_UREA=0)
        check = m.declared_ions_check(made(zero_n | {'Fe': 1}))
        self.assertFalse(check.modellable)
        self.assertIn('chelating_agent', check.reason)
        check = m.declared_ions_check(made(zero_n | {'Mn': 1}, chelating_agent='DTPA'))
        self.assertFalse(check.modellable)
        self.assertIn('iron only', check.reason)
        check = m.declared_ions_check(made(zero_n | {'K': 1}, chelating_agent=None))
        self.assertFalse(check.modellable)
        self.assertIn('charge balance', check.reason)
        balanced = made(zero_n, chelating_agent=None)
        check = m.declared_ions_check(balanced)
        self.assertTrue(check.modellable)
        self.assertEqual(check.residual_percent, 0)
        product, _ = fixtures.DeclaredCompoundTests().product()
        actual = material_chemistry(product)
        self.assertEqual(actual.family, 'declared_ions')
        bad = deepcopy(product)
        del bad['grade']['analysis']['N_UREA']
        self.assert_code('ph_not_planned_for_product', material_chemistry, bad)
        declared, _ = fixtures.DeclaredCompoundTests().grade()
        self.assert_code(
            'material_mismatch', m.resolve_material, 'Synthetic', grade=declared, lot=lot()
        )

    def test_material_mapping_ions_and_provenance_boundaries(self):
        self.assert_code('invalid_type', material_chemistry, [])
        self.assert_code('missing_field', material_chemistry, {'name': ' '})
        self.assert_code('invalid_value', material_chemistry, {'name': 'Salt', 'ions': object()})
        self.assert_code(
            'unknown_identity', material_chemistry, {'name': 'Salt', 'identityId': 'missing'}
        )
        for ions in ({}, {'Xx': 1}, {'Na+': True}, {'Na+': 0}, {'Na+': float('inf')}):
            self.assert_code(
                'invalid_composition', material_chemistry, dict(name='Salt', ions=ions)
            )
        self.assert_code('invalid_value', chelate, {'Fe+3': 1}, 'unknown')
        self.assert_code('invalid_composition', chelate, {'Na+': 1}, 'EDTA')
        self.assert_code(
            'identity_inconsistent',
            material_chemistry,
            dict(name='KNO3', formula='KNO3', elements={'Ca': 1}),
        )
        profile = ProductChemistry('Legacy', 'salt', 'Na+', 'synthetic')
        self.assertEqual(chemistry_ions(profile), {'Na+': 1})
        self.assert_code(
            'unsupported_product_chemistry',
            chemistry_ions,
            ProductChemistry('Legacy', 'salt', ('Xx',), 'synthetic'),
        )


class CompositionBoundaryTests(unittest.TestCase):
    def test_formula_syntax_and_zero_mass_fail_without_an_assay(self):
        from flahax.composition import (
            parse_formula,
            theoretical_assay,
            validate_profile,
            InputError,
        )

        for formula in ('K)', '(K', 'K?', '123', '()', 'K()2)', '.'):
            with self.subTest(formula=formula):
                self.assertIsNone(parse_formula(formula))
        self.assertIsNone(theoretical_assay('K0'))
        with self.assertRaises(InputError):
            validate_profile({'K': []}, 'target')

    def test_bad_assays_have_actionable_conflicts_and_missing_elements_have_drift(self):
        from flahax.composition import assay_conflict, assay_drift

        for record, reason in [
            ({}, 'no element assay'),
            ({'elements': {'Xx': 1}}, 'not a balance ion'),
            ({'elements': {'K': []}}, 'non-numeric'),
            ({'elements': {'K': 60, 'Ca': 50}}, 'more than 100'),
            ({'name': 'test_placeholder', 'elements': {'K': 1}}, 'placeholder'),
            ({'formula': 'KNO3', 'elements': {'Ca': 1}}, 'contains 0.00'),
        ]:
            with self.subTest(record=record):
                self.assertIn(reason, assay_conflict(record))
                self.assertIsNone(assay_drift(record))
        self.assertIn('N_NO3 missing', assay_drift({'formula': 'KNO3', 'elements': {'K': 38.67}}))
        # Oxygen and hydrogen do not create missing nutrient-assay alarms.
        self.assertIsNone(assay_drift({'formula': 'H2O', 'elements': {'K': 0}}))

    # Owner catalogue: re-enable in PR 4 (G5)
    def test_product_conversion_rejects_bad_doses_and_preserves_declared_sodium(self):
        self.enterContext(historical_catalogue())
        from flahax import load_library
        from flahax.product_conversion import (
            convert_material_dose,
            convert_product_dose,
            catalogue_dose_totals,
            declared_ion_totals,
            counterion_sodium_mg_per_l,
        )

        product = next(p for p in load_library()['salts'] if p['name'] == 'Potassium Nitrate')
        chemistry = material_chemistry(product)
        converted = convert_material_dose(product, 1)
        self.assertEqual(converted.chemistry, chemistry)
        for dose in (-1, float('inf'), 'one'):
            with self.assertRaises(DeliveryError) as caught:
                convert_product_dose(product, chemistry, dose)
            self.assertEqual(caught.exception.code, 'out_of_range')
        for function, args, kwargs, code in [
            (
                convert_product_dose,
                (dict(product, elements=None), chemistry, 1),
                {},
                'missing_field',
            ),
            (catalogue_dose_totals, ({'missing': 1},), {}, 'unknown_product'),
            (catalogue_dose_totals, ({},), {'materials': []}, 'material_mismatch'),
            (declared_ion_totals, ({'unknown': 1}, None, 1), {}, 'unsupported_product_chemistry'),
        ]:
            with self.assertRaises(DeliveryError) as caught:
                function(*args, **kwargs)
            self.assertEqual(caught.exception.code, code)
        declared = declared_ion_totals({'Fe': 1, 'Na': 2}, 'EDTA', 100)
        self.assertAlmostEqual(declared['Na+'], 2 / 22.989769, delta=1e-8)
        self.assertEqual(counterion_sodium_mg_per_l([(product, 0)]), 0)


class RemainingMaterialPaths(unittest.TestCase):
    def test_ambiguous_and_fractional_formula_requires_explicit_ions(self):
        from flahax.material_chemistry import ions_from_formula, formula_problem, _pair_ligands

        self.assertIsNone(ions_from_formula('K2H4P2O8'))
        self.assertIn('more than one way', formula_problem('K2H4P2O8'))
        # A future parser accepting fractional stoichiometry must still stop this adapter.
        with patch('flahax.material_chemistry.parse_formula', return_value={'atoms': {'K': 0.5}}):
            self.assertIn('fractional atoms', formula_problem('K'))
        self.assertIsNone(_pair_ligands({'EDTA': 2, 'Fe+3': 1}))

    def test_missing_counterion_information_is_not_invented(self):
        from flahax.material_chemistry import unstated_amounts

        for function, args in [
            (
                material_chemistry,
                ({'name': 'Salt', 'ions': {'K+': 1, 'Na+': 1, 'SO4-2': 1}, 'elements': {'S': 1}},),
            ),
            (unstated_amounts, ({'K+': 1, 'Na+': 1, 'SO4-2': 1}, {'sulfate': 1})),
        ]:
            with self.assertRaises(DeliveryError) as caught:
                function(*args)
            self.assertEqual(caught.exception.code, 'material_undefined')
        counterions, ligands = unstated_amounts({'Fe(III)-EDTA': 1}, {})
        self.assertEqual(counterions, {})
        self.assertEqual(ligands, {'EDTA': 0})

    def test_missing_catalogue_and_unknown_theory_remain_explicit(self):
        from flahax.product_conversion import (
            catalogue_dose_contributions,
            counterion_sodium_mg_per_l,
        )

        for function, args in [
            (catalogue_dose_contributions, ({'missing': 1},)),
            (m._shipped_salt, ('missing',)),
        ]:
            with self.assertRaises(DeliveryError) as caught:
                function(*args)
            self.assertEqual(caught.exception.code, 'unknown_product')
        self.assertFalse(
            m._range_excludes_theory({'theoretical_analysis': None}, {'K': 1}, {'K': 2})
        )
        self.assertEqual(counterion_sodium_mg_per_l([({'name': 'Incomplete'}, 1)]), 0)

    def test_parser_helper_rejects_unbalanced_group_and_tiny_element_is_not_missing(self):
        from flahax.composition import _parse_group, parse_formula, assay_drift

        with self.assertRaises(ValueError):
            _parse_group(['(', 'K'], 0)
        self.assertIsNone(parse_formula('abc'))
        self.assertIsNone(assay_drift({'formula': 'K1000Cl', 'elements': {'K': 99.9}}))


class MaterialBandBoundaryTests(unittest.TestCase):
    def test_open_bound_stays_unknown_after_another_contributor(self):
        result = m.nutrient_band({'Potassium Nitrate': 1, 'Potassium Monobasic Phosphate': 1})
        self.assertGreater(result['nutrients']['K']['nominal_mg_per_l'], 0)
        self.assertIsNone(result['nutrients']['K']['maximum_mg_per_l'])

    def test_explicit_sodium_is_not_added_again_as_a_counterion(self):
        from flahax.product_conversion import counterion_sodium_mg_per_l

        product = dict(
            name='Synthetic', elements={'Na': 1}, grade={'composition': 'declared_ions'}
        )
        self.assertEqual(counterion_sodium_mg_per_l([(product, 1)]), 0)


class CompositionAdapterBoundaryTests(unittest.TestCase):
    def test_partial_parser_output_is_not_accepted_as_a_complete_formula(self):
        from flahax import composition

        # Fault injection checks the parser adapter, not a valid chemical formula.
        with patch.object(composition, '_parse_group', return_value=({}, 0)):
            self.assertIsNone(composition.parse_formula('KNO3'))

    def test_assay_that_changes_between_validation_reads_cannot_produce_drift(self):
        from flahax import composition

        with patch.object(
            composition, '_cleaned_assay', side_effect=[({'K': 38}, None), (None, 'invalid')]
        ):
            self.assertIsNone(composition.assay_drift({'formula': 'KNO3'}))
