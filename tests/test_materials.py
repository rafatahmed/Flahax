import json
from pathlib import Path
import unittest

from flahax.delivery_contracts import DeliveryError
from flahax.engine import load_library
from flahax.composition import ATOMIC
from flahax.materials import (IDENTITIES_SHA256, IDENTITY_STATUSES, OXIDE_FACTORS, Grade, Lot,
                              identity_for_product, load_identities, make_grade, make_lot,
                              resolve_material)

FIXTURES = Path(__file__).parent / 'fixtures' / 'materials'

# Charge per dissolved component as declared in ion_forms. Neutral solutes are 0.
CHARGES = {
    'Na+': 1, 'K+': 1, 'NH4+': 1,
    'Ca+2': 2, 'Mg+2': 2, 'Fe+2': 2, 'Cu+2': 2, 'Zn+2': 2,
    'NO3-': -1, 'Cl-': -1, 'SO4-2': -2, 'H2PO4-': -1, 'HPO4-2': -2, 'CO3-2': -2, 'HCO3-': -1, 'OH-': -1,
    'MoO4-2': -2, 'B(OH)4-': -1, 'citrate': -3,
    'Fe(III)-EDTA': -1, 'Mn-EDTA': -2, 'Zn-EDTA': -2, 'Cu-EDTA': -2,
    'Fe(III)-DTPA': -2, 'Fe(III)-o,o-EDDHA': -1,
    'H3PO4': 0, 'B(OH)3': 0, 'CO(NH2)2': 0,
}

REQUIRED_KEYS = {'id', 'products', 'name', 'formula', 'hydration', 'molecular_weight', 'cas',
                 'ion_forms', 'theoretical_analysis', 'comparator', 'status', 'notes'}


class IdentityTests(unittest.TestCase):
    def test_every_catalogue_product_has_exactly_one_identity(self):
        names = [s['name'] for s in load_library()['salts']]
        covered = [p for i in load_identities().values() for p in i['products']]
        self.assertEqual(sorted(names), sorted(covered))

    def test_theoretical_analysis_matches_independent_audit_values(self):
        audit = json.loads((FIXTURES / 'audit_theory.json').read_text(encoding='utf-8'))
        compared = 0
        for name, ref in audit.items():
            ident = identity_for_product(name)
            if ident['formula'] == ref['formula']:
                compared += 1
                self.assertEqual(set(ident['theoretical_analysis']), set(ref['analysis']), name)
                for key, value in ref['analysis'].items():
                    self.assertAlmostEqual(ident['theoretical_analysis'][key], value, places=6,
                                           msg=(name, key))
        # Potassium Citrate is the only fixture row whose formula (monohydrate
        # comparator) differs from the shipped anhydrous identity.
        self.assertEqual(compared, len(audit) - 1)

    def test_calcium_nitrate_is_the_double_salt_and_exercised(self):
        ident = identity_for_product('Calcium Nitrate (ag grade)')
        self.assertEqual(ident['formula'], '5Ca(NO3)2.NH4NO3.10H2O')
        self.assertEqual(ident['status'], 'commercial_double_salt')

    def test_mg_nitrate_identity_is_hexahydrate(self):
        ident = identity_for_product('Mg Nitrate')
        self.assertEqual(ident['formula'], 'Mg(NO3)2.6H2O')
        self.assertAlmostEqual(ident['theoretical_analysis']['N_NO3'], 10.92564, places=4)
        self.assertAlmostEqual(ident['theoretical_analysis']['Mg'], 9.47931, places=4)

    def test_ion_forms_are_charge_neutral(self):
        for ident in load_identities().values():
            if ident['status'] == 'assumed_blend':
                continue
            self.assertEqual(sum(CHARGES[c] * n for c, n in ident['ion_forms'].items()), 0, ident['id'])

    def test_records_have_required_keys_and_known_status(self):
        for key, ident in load_identities().items():
            self.assertEqual(key, ident['id'])
            self.assertTrue(key.startswith('idn-'), key)
            self.assertTrue(REQUIRED_KEYS <= set(ident), (key, REQUIRED_KEYS - set(ident)))
            self.assertIn(ident['status'], IDENTITY_STATUSES, key)
            self.assertEqual(set(ident['comparator']), {'product', 'url', 'accessed'}, key)

    def test_chelates_are_defined_sodium_salts(self):
        expected = {
            'Iron EDTA': ('C10H12FeN2NaO8', {'Na+': 1, 'Fe(III)-EDTA': 1}),
            'Mn EDTA': ('C10H12MnN2Na2O8', {'Na+': 2, 'Mn-EDTA': 1}),
            'Zn EDTA': ('C10H12N2Na2O8Zn', {'Na+': 2, 'Zn-EDTA': 1}),
            'Copper EDTA': ('C10H12CuN2Na2O8', {'Na+': 2, 'Cu-EDTA': 1}),
            'Iron DTPA': ('C14H18FeN3Na2O10', {'Na+': 2, 'Fe(III)-DTPA': 1}),
            'Iron EDDHA': ('C18H16FeN2NaO6', {'Na+': 1, 'Fe(III)-o,o-EDDHA': 1}),
        }
        for name, (formula, ions) in expected.items():
            ident = identity_for_product(name)
            self.assertEqual(ident['status'], 'chelate_salt_defined', name)
            self.assertEqual(ident['formula'], formula, name)
            self.assertEqual(ident['ion_forms'], ions, name)
        self.assertAlmostEqual(identity_for_product('Iron EDTA')['theoretical_analysis']['Fe'],
                               15.2148, places=3)

    def test_special_statuses(self):
        self.assertEqual(identity_for_product('Phosphoric Acid (75%)')['status'], 'aqueous_solution')
        self.assertEqual(identity_for_product('Phosphoric Acid (75%)')['formula'], 'H3PO4')
        blend = identity_for_product('CH - micro')
        self.assertEqual(blend['status'], 'assumed_blend')
        for component in ('Fe(III)-EDTA', 'Mn-EDTA', 'Zn-EDTA', 'Cu-EDTA', 'B(OH)4-', 'MoO4-2'):
            self.assertIn(component, blend['ion_forms'])
        self.assertEqual(identity_for_product('Potassium Citrate')['formula'], 'C6H5K3O7')
        self.assertEqual(identity_for_product('Sodium Borate (Decahydrate) (borax)')['ion_forms'],
                         {'Na+': 2, 'B(OH)4-': 2, 'B(OH)3': 2})
        self.assertAlmostEqual(identity_for_product('Urea')['theoretical_analysis']['N_UREA'],
                               46.64642736062887, places=9)

    def test_unknown_product_fails_closed(self):
        with self.assertRaises(DeliveryError) as caught:
            identity_for_product('Unobtainium Nitrate')
        self.assertEqual(caught.exception.code, 'unknown_product')

    def test_identities_file_is_pinned(self):
        self.assertEqual(IDENTITIES_SHA256, '7c3526334f77e4fb9879b2aebbeebd6810aa354ed417c4d03059f373e9f85a22')


DOC = {'supplier': 'Example Supplier', 'title': 'Technical data sheet TDS-1', 'issued': '2026-01-15',
       'entered': '2026-10-18'}
COA = {'supplier': 'Example Supplier', 'title': 'Certificate of analysis L-77', 'issued': '2026-09-01',
       'entered': '2026-10-18', 'sha256': 'a' * 64}
MKP = 'idn-monopotassium-phosphate'
CAN = 'idn-ammonium-calcium-nitrate'


def grade(**overrides):
    record = {'grade_id': 'grd-test', 'identity_id': MKP, 'supplier': 'Example Supplier',
              'product': 'MKP 0-52-34', 'composition': 'single',
              'analysis': {'P2O5': {'minimum': 52.0}}, 'document': DOC}
    record.update(overrides)
    return make_grade(record)


def lot(**overrides):
    record = {'lot_id': 'L-77', 'grade_id': 'grd-test', 'measured': {'K': 28.5},
              'uncertainty': {'K': 0.3}, 'document': COA}
    record.update(overrides)
    return make_lot(record)


class GradeLotTests(unittest.TestCase):
    def test_oxide_factors(self):
        o = ATOMIC['O']
        derived = {
            'P2O5': 2 * ATOMIC['P'] / (2 * ATOMIC['P'] + 5 * o),
            'K2O': 2 * ATOMIC['K'] / (2 * ATOMIC['K'] + o),
            'CaO': ATOMIC['Ca'] / (ATOMIC['Ca'] + o),
            'MgO': ATOMIC['Mg'] / (ATOMIC['Mg'] + o),
            'SO3': ATOMIC['S'] / (ATOMIC['S'] + 3 * o),
        }
        elements = {'P2O5': 'P', 'K2O': 'K', 'CaO': 'Ca', 'MgO': 'Mg', 'SO3': 'S'}
        # Brief values (0.436421, 0.830148, 0.714701, 0.603036, 0.400496) come from older
        # atomic masses (O 15.9994, S 32.065, Ca 40.08). composition.ATOMIC (O 15.999,
        # S 32.06, Ca 40.078) gives the from_atomic values, which agree with the brief to 4
        # places only. Factors are computed from ATOMIC, never hard-coded.
        brief = {'P2O5': 0.436421, 'K2O': 0.830148, 'CaO': 0.714701, 'MgO': 0.603036, 'SO3': 0.400496}
        from_atomic = {'P2O5': 0.436427, 'K2O': 0.830151, 'CaO': 0.714696, 'MgO': 0.603042,
                       'SO3': 0.400465}
        self.assertEqual(set(OXIDE_FACTORS), set(derived))
        for oxide, (element, factor) in OXIDE_FACTORS.items():
            self.assertEqual(element, elements[oxide])
            self.assertEqual(factor, derived[oxide])
            self.assertAlmostEqual(factor, from_atomic[oxide], places=6)
            self.assertAlmostEqual(factor, brief[oxide], places=4)
        g = grade(analysis={'P2O5': {'typical': 52.0}, 'K2O': {'typical': 34.0}})
        self.assertEqual(g.oxide_conversions, {'P2O5': {'element': 'P', 'factor': derived['P2O5']},
                                               'K2O': {'element': 'K', 'factor': derived['K2O']}})
        self.assertAlmostEqual(g.typical['K'], 34.0 * derived['K2O'], places=12)
        with self.assertRaises(DeliveryError) as caught:
            grade(analysis={'P2O5': {'typical': 52.0}, 'P': {'typical': 22.7}})
        self.assertEqual(caught.exception.code, 'invalid_value')

    def test_grade_requires_document_reference(self):
        for document in (None, {}, {**DOC, 'issued': ''}, {k: v for k, v in DOC.items() if k != 'entered'}):
            record = {'grade_id': 'grd-test', 'identity_id': MKP, 'supplier': 'S', 'product': 'P',
                      'composition': 'single', 'analysis': {'P': {'typical': 22.7}}}
            if document is not None:
                record['document'] = document
            with self.assertRaises(DeliveryError) as caught:
                make_grade(record)
            self.assertEqual(caught.exception.code, 'missing_document_reference')
        with self.assertRaises(DeliveryError) as caught:
            make_lot({'lot_id': 'L', 'identity_id': MKP, 'measured': {'K': 28.0}})
        self.assertEqual(caught.exception.code, 'missing_document_reference')
        g = grade()
        self.assertEqual(g.document.supplier, 'Example Supplier')
        self.assertIsNone(g.document.url)

    def test_invalid_values_rejected(self):
        for bad in (float('nan'), float('inf'), -1.0, 100.5, 'x', True):
            with self.assertRaises(DeliveryError) as caught:
                grade(analysis={'P': {'typical': bad}})
            self.assertEqual(caught.exception.code, 'invalid_value', bad)
        for analysis in ({'Xx': {'typical': 1.0}}, {'P': {'typical': 22.0, 'minimum': 23.0}},
                         {'P': {'average': 22.0}}, {'P': {}}):
            with self.assertRaises(DeliveryError) as caught:
                grade(analysis=analysis)
            self.assertEqual(caught.exception.code, 'invalid_value', analysis)
        with self.assertRaises(DeliveryError) as caught:
            lot(measured={'K': -0.1})
        self.assertEqual(caught.exception.code, 'invalid_value')
        with self.assertRaises(DeliveryError) as caught:
            lot(uncertainty={'P': 0.1})
        self.assertEqual(caught.exception.code, 'invalid_value')
        with self.assertRaises(DeliveryError) as caught:
            grade(identity_id='idn-unobtainium')
        self.assertEqual(caught.exception.code, 'unknown_identity')
        with self.assertRaises(DeliveryError) as caught:
            lot(grade_id=None, identity_id='idn-unobtainium')
        self.assertEqual(caught.exception.code, 'unknown_identity')

    def test_minimum_only_grade_is_lower_bound(self):
        g = grade()
        self.assertIsInstance(g, Grade)
        resolved = resolve_material('Potassium Monobasic Phosphate', grade=g)
        self.assertEqual(resolved.basis['P'], 'grade_minimum')
        self.assertIn('lower_bound_grade_assay', resolved.flags)
        self.assertAlmostEqual(resolved.record['elements']['P'], 22.6939, places=3)
        self.assertEqual(resolved.record['elements']['P'], 52.0 * OXIDE_FACTORS['P2O5'][1])
        self.assertEqual(resolved.band_minimum['P'], resolved.record['elements']['P'])
        self.assertIn('P', resolved.band_maximum)
        self.assertIsNone(resolved.band_maximum['P'])
        # K is not stated by the grade: identity theoretical, no band.
        self.assertEqual(resolved.basis['K'], 'identity_theoretical')
        self.assertIsNone(resolved.band_minimum['K'])
        self.assertIsNone(resolved.band_maximum['K'])
        shipped = next(s for s in load_library()['salts'] if s['name'] == 'Potassium Monobasic Phosphate')
        # A grade is not the shipped product: own id, shipped name.
        self.assertEqual(resolved.record['id'], shipped['id'] + '+grd-test')
        self.assertEqual(resolved.record['name'], shipped['name'])
        self.assertEqual(resolved.record['formula'], 'KH2PO4')
        self.assertEqual(resolved.provenance['gradeId'], 'grd-test')
        self.assertEqual(resolved.provenance['identitiesSha256'], IDENTITIES_SHA256)

    def test_partial_lot_falls_back_per_nutrient(self):
        g = grade(grade_id='grd-can', identity_id=CAN, product='Calcium nitrate ag grade',
                  analysis={'N_NO3': {'typical': 14.4, 'minimum': 14.0, 'maximum': 14.8},
                            'N_NH4': {'typical': 1.1}, 'Ca': {'typical': 19.0, 'minimum': 18.5}})
        l = lot(grade_id='grd-can', measured={'N_NO3': 14.6}, uncertainty={'N_NO3': 0.2})
        self.assertIsInstance(l, Lot)
        resolved = resolve_material('Calcium Nitrate (ag grade)', grade=g, lot=l)
        self.assertEqual(resolved.basis, {'N_NO3': 'lot_measured', 'N_NH4': 'grade_typical',
                                          'Ca': 'grade_typical'})
        self.assertEqual(resolved.record['elements'], {'N_NO3': 14.6, 'N_NH4': 1.1, 'Ca': 19.0})
        self.assertAlmostEqual(resolved.band_minimum['N_NO3'], 14.4, places=12)
        self.assertAlmostEqual(resolved.band_maximum['N_NO3'], 14.8, places=12)
        self.assertEqual(resolved.band_minimum['Ca'], 18.5)
        self.assertIsNone(resolved.band_maximum['Ca'])
        self.assertIsNone(resolved.band_minimum['N_NH4'])
        self.assertNotIn('lower_bound_grade_assay', resolved.flags)
        self.assertEqual(resolved.provenance['lotId'], 'L-77')
        self.assertEqual(resolved.provenance['documents']['lot']['sha256'], 'a' * 64)
        shipped = next(s for s in load_library()['salts'] if s['name'] == 'Calcium Nitrate (ag grade)')
        self.assertEqual(resolved.record['id'], shipped['id'] + '+grd-can+L-77')
        self.assertNotIn('lot_outside_grade_range', resolved.flags)

    def test_lot_outside_grade_range_widens_band(self):
        kno3 = grade(grade_id='grd-kno3', identity_id=KNO3,
                     analysis={'N_NO3': {'typical': 13.7, 'minimum': 13.5, 'maximum': 13.9}})
        high = resolve_material('Potassium Nitrate', grade=kno3,
                                lot=lot(grade_id='grd-kno3', measured={'N_NO3': 14.3}, uncertainty={}))
        self.assertEqual(high.record['elements']['N_NO3'], 14.3)
        self.assertEqual((high.band_minimum['N_NO3'], high.band_maximum['N_NO3']), (13.5, 14.3))
        self.assertIn('lot_outside_grade_range', high.flags)
        low = resolve_material('Potassium Nitrate', grade=kno3,
                               lot=lot(grade_id='grd-kno3', measured={'N_NO3': 13.2}, uncertainty={}))
        self.assertEqual((low.band_minimum['N_NO3'], low.band_maximum['N_NO3']), (13.2, 13.9))
        self.assertIn('lot_outside_grade_range', low.flags)
        inside = resolve_material('Potassium Nitrate', grade=kno3,
                                  lot=lot(grade_id='grd-kno3', measured={'N_NO3': 13.8}, uncertainty={}))
        self.assertEqual((inside.band_minimum['N_NO3'], inside.band_maximum['N_NO3']), (13.5, 13.9))
        self.assertNotIn('lot_outside_grade_range', inside.flags)

    def test_lot_against_identity_without_grade(self):
        l = lot(grade_id=None, identity_id=MKP)
        resolved = resolve_material('Potassium Monobasic Phosphate', lot=l)
        self.assertEqual(resolved.basis, {'K': 'lot_measured', 'P': 'identity_theoretical'})
        self.assertEqual(resolved.record['elements']['K'], 28.5)
        self.assertEqual(resolved.record['elements']['P'],
                         identity_for_product('Potassium Monobasic Phosphate')['theoretical_analysis']['P'])
        self.assertAlmostEqual(resolved.band_minimum['K'], 28.2, places=12)
        self.assertAlmostEqual(resolved.band_maximum['K'], 28.8, places=12)
        self.assertIsNone(resolved.provenance['gradeId'])
        self.assertIsNone(resolved.provenance['documents']['grade'])
        shipped = next(s for s in load_library()['salts'] if s['name'] == 'Potassium Monobasic Phosphate')
        self.assertEqual(resolved.record['id'], shipped['id'] + '+lot:L-77')
        for linkage in ({'grade_id': 'grd-test', 'identity_id': MKP}, {'grade_id': None}):
            with self.assertRaises(DeliveryError) as caught:
                lot(**linkage)
            self.assertEqual(caught.exception.code, 'material_mismatch')
        with self.assertRaises(DeliveryError) as caught:
            resolve_material('Potassium Nitrate', lot=l)
        self.assertEqual(caught.exception.code, 'material_mismatch')
        with self.assertRaises(DeliveryError) as caught:
            resolve_material('Potassium Monobasic Phosphate', lot=lot())
        self.assertEqual(caught.exception.code, 'material_mismatch')

    def test_lot_grade_mismatch_raises(self):
        with self.assertRaises(DeliveryError) as caught:
            resolve_material('Potassium Monobasic Phosphate', grade=grade(), lot=lot(grade_id='grd-other'))
        self.assertEqual(caught.exception.code, 'material_mismatch')
        with self.assertRaises(DeliveryError) as caught:
            resolve_material('Potassium Monobasic Phosphate', grade=grade(),
                             lot=lot(grade_id=None, identity_id=MKP))
        self.assertEqual(caught.exception.code, 'material_mismatch')
        with self.assertRaises(DeliveryError) as caught:
            resolve_material('Potassium Nitrate', grade=grade())
        self.assertEqual(caught.exception.code, 'material_mismatch')

    def test_identity_inconsistent_flag_on_old_mg_nitrate_analysis(self):
        old = grade(identity_id='idn-magnesium-nitrate-hexahydrate', analysis={
            'N_NO3': {'typical': 11.0}, 'Mg': {'typical': 9.65}})
        self.assertIn('identity_inconsistent', old.flags)
        self.assertAlmostEqual(old.charge_residual_percent, 0.553, places=3)
        resolved = resolve_material('Mg Nitrate', grade=old)
        self.assertIn('identity_inconsistent', resolved.flags)
        theory = load_identities()['idn-magnesium-nitrate-hexahydrate']['theoretical_analysis']
        exact = grade(identity_id='idn-magnesium-nitrate-hexahydrate', analysis={
            'N_NO3': {'typical': theory['N_NO3']}, 'Mg': {'typical': theory['Mg']}})
        self.assertAlmostEqual(exact.charge_residual_percent, 0.0, places=9)
        self.assertNotIn('identity_inconsistent', exact.flags)

    def test_charge_residual_not_flagged_for_balanced_or_one_sided_grades(self):
        mkp = grade()
        self.assertIsNone(mkp.charge_residual_percent)  # P only: no cation stated
        self.assertNotIn('identity_inconsistent', mkp.flags)
        can = grade(identity_id=CAN, analysis={'N_NO3': {'typical': 14.4}, 'N_NH4': {'typical': 1.1},
                                               'Ca': {'typical': 19.0}})
        self.assertAlmostEqual(can.charge_residual_percent, -0.068, places=3)
        self.assertNotIn('identity_inconsistent', can.flags)
        # Minimum is used for a form with no typical.
        mkp_min = grade(analysis={'K': {'minimum': 28.0}, 'P': {'minimum': 22.7}})
        self.assertIsNotNone(mkp_min.charge_residual_percent)
        # Chelate metal is carried by the anionic complex; Fe alone has no cation.
        self.assertIsNone(grade(identity_id='idn-sodium-iron-edta',
                                analysis={'Fe': {'typical': 13.0}}).charge_residual_percent)

    def test_identity_inconsistent_when_range_excludes_theory(self):
        theory = load_identities()['idn-magnesium-nitrate-hexahydrate']['theoretical_analysis']
        excluded = grade(identity_id='idn-magnesium-nitrate-hexahydrate', analysis={
            'Mg': {'typical': theory['Mg'] * 1.03, 'minimum': theory['Mg'] * 1.02,
                   'maximum': theory['Mg'] * 1.04}})
        self.assertIsNone(excluded.charge_residual_percent)
        self.assertIn('identity_inconsistent', excluded.flags)
        # A minimum alone above theory is not a range: not flagged.
        open_ended = grade(identity_id='idn-magnesium-nitrate-hexahydrate', analysis={
            'Mg': {'minimum': theory['Mg'] * 1.02}})
        self.assertNotIn('identity_inconsistent', open_ended.flags)
        inside = grade(identity_id='idn-magnesium-nitrate-hexahydrate', analysis={
            'Mg': {'minimum': theory['Mg'] * 0.99, 'maximum': theory['Mg'] * 1.01}})
        self.assertNotIn('identity_inconsistent', inside.flags)

    def test_range_test_skipped_for_solution_and_chelate_identities(self):
        # Theory is the pure compound; a commercial 75 % acid or a chelate as sold sits below it.
        acid = grade(identity_id='idn-phosphoric-acid', analysis={
            'P2O5': {'typical': 54.3, 'minimum': 54.0, 'maximum': 54.6}})
        self.assertNotIn('identity_inconsistent', acid.flags)
        chelate = grade(identity_id='idn-sodium-iron-edta', analysis={
            'Fe': {'typical': 13.0, 'minimum': 12.8, 'maximum': 13.2}})
        self.assertNotIn('identity_inconsistent', chelate.flags)
        theory = load_identities()[KNO3]['theoretical_analysis']
        kno3 = grade(identity_id=KNO3, analysis={
            'N_NO3': {'typical': theory['N_NO3'] * 1.03, 'minimum': theory['N_NO3'] * 1.02,
                      'maximum': theory['N_NO3'] * 1.04}})
        self.assertIn('identity_inconsistent', kno3.flags)

    def test_total_n_split_by_identity_ratio(self):
        theory = load_identities()[CAN]['theoretical_analysis']
        total = theory['N_NO3'] + theory['N_NH4']
        g = grade(identity_id=CAN, analysis={'N': {'typical': 15.5}, 'Ca': {'typical': 19.0}})
        self.assertEqual(g.form_split, {'N': {'N_NO3': theory['N_NO3'] / total,
                                              'N_NH4': theory['N_NH4'] / total}})
        self.assertAlmostEqual(g.typical['N_NO3'], 15.5 * theory['N_NO3'] / total, places=12)
        self.assertAlmostEqual(g.typical['N_NH4'], 15.5 * theory['N_NH4'] / total, places=12)
        self.assertAlmostEqual(g.typical['N_NO3'] + g.typical['N_NH4'], 15.5, places=12)
        self.assertNotIn('N', g.typical)
        resolved = resolve_material('Calcium Nitrate (ag grade)', grade=g)
        self.assertEqual(resolved.basis, {'N_NO3': 'grade_typical', 'N_NH4': 'grade_typical',
                                          'Ca': 'grade_typical'})
        for analysis in ({'N': {'typical': 15.5}, 'N_NO3': {'typical': 14.4}},
                         {'N_UREA': {'typical': 1.0}, 'N': {'typical': 15.5}}):
            with self.assertRaises(DeliveryError) as caught:
                grade(identity_id=CAN, analysis=analysis)
            self.assertEqual(caught.exception.code, 'invalid_value')
        with self.assertRaises(DeliveryError) as caught:
            grade(analysis={'N': {'typical': 1.0}})  # MKP has no nitrogen
        self.assertEqual(caught.exception.code, 'invalid_value')

    def test_maximum_only_analysis_rejected(self):
        with self.assertRaises(DeliveryError) as caught:
            grade(analysis={'P': {'typical': 22.7}, 'K': {'maximum': 29.0}})
        self.assertEqual(caught.exception.code, 'invalid_value')

    def test_assumed_blend_is_labelled(self):
        shipped = resolve_material('CH - micro')
        self.assertIn('assumed_composition', shipped.flags)
        self.assertIs(shipped.provenance['assumed'], True)
        graded = resolve_material('CH - micro', grade=grade(
            grade_id='grd-ch', identity_id='idn-ch-micro-assumed-blend', composition='disclosed',
            components=[{'identity_id': 'idn-sodium-iron-edta', 'mass_fraction': 0.5}],
            analysis={'Fe': {'typical': 7.0}}))
        self.assertIn('assumed_composition', graded.flags)
        self.assertIs(graded.provenance['assumed'], True)
        plain = resolve_material('Potassium Nitrate')
        self.assertNotIn('assumed_composition', plain.flags)
        self.assertIs(plain.provenance['assumed'], False)

    def test_disclosed_blend_fractions_validated(self):
        components = [{'identity_id': 'idn-sodium-iron-edta', 'mass_fraction': 0.6},
                      {'identity_id': 'idn-borax-decahydrate', 'mass_fraction': 0.3}]
        g = grade(grade_id='grd-blend', identity_id=None, composition='disclosed', components=components,
                  analysis={'Fe': {'typical': 7.0}})
        self.assertEqual(g.components, (('idn-sodium-iron-edta', 0.6), ('idn-borax-decahydrate', 0.3)))
        resolved = resolve_material('CH - micro', grade=g)
        self.assertIsNone(resolved.provenance['identityId'])
        self.assertEqual(resolved.provenance['hostProduct'], 'CH - micro')
        self.assertIsNone(resolved.record['formula'])
        self.assertEqual(resolved.record['name'], 'CH - micro')
        self.assertTrue(resolved.record['id'].endswith('+grd-blend'))
        for bad in ([{**components[0], 'mass_fraction': 0.8}, components[1]], [],
                    [{**components[0], 'mass_fraction': 0.0}]):
            with self.assertRaises(DeliveryError) as caught:
                grade(identity_id=None, composition='disclosed', components=bad)
            self.assertEqual(caught.exception.code, 'invalid_composition')
        with self.assertRaises(DeliveryError) as caught:
            grade(identity_id=None, composition='disclosed',
                  components=[{'identity_id': 'idn-nope', 'mass_fraction': 0.5}])
        self.assertEqual(caught.exception.code, 'unknown_identity')
        with self.assertRaises(DeliveryError) as caught:
            grade(identity_id=None)
        self.assertEqual(caught.exception.code, 'invalid_composition')
        with self.assertRaises(DeliveryError) as caught:
            grade(composition='mystery')
        self.assertEqual(caught.exception.code, 'invalid_composition')

    def test_undisclosed_blend_has_composition_undisclosed(self):
        g = grade(grade_id='grd-secret', identity_id=None, composition='undisclosed',
                  analysis={'Fe': {'typical': 7.0}, 'Zn': {'typical': 0.4}})
        self.assertEqual(g.components, ())
        resolved = resolve_material('CH - micro', grade=g)
        self.assertEqual(resolved.composition, 'undisclosed')
        self.assertIsNone(resolved.provenance['identityId'])
        self.assertEqual(resolved.provenance['hostProduct'], 'CH - micro')
        self.assertIsNone(resolved.record['formula'])
        self.assertEqual(resolved.basis, {'Fe': 'grade_typical', 'Zn': 'grade_typical'})
        with self.assertRaises(DeliveryError) as caught:
            grade(identity_id=None, composition='undisclosed',
                  components=[{'identity_id': MKP, 'mass_fraction': 0.5}])
        self.assertEqual(caught.exception.code, 'invalid_composition')

    def test_undisclosed_blend_record_doses_in_recommend(self):
        # Mass balance works from the declared analysis; the record carries no host formula.
        from flahax.engine import recommend
        secret = resolve_material('CH - micro', grade=grade(
            grade_id='grd-secret', identity_id=None, composition='undisclosed',
            analysis={'Fe': {'typical': 7.0}, 'Zn': {'typical': 0.4}}))
        shipped = [s for s in load_library()['salts'] if s['name'] == 'Potassium Nitrate']
        fit = recommend([secret.record, *shipped], {'Fe': 0.7, 'Zn': 0.04})
        self.assertTrue(fit['feasible'])
        dosed = {s['id']: s for s in fit['salts']}
        self.assertEqual(dosed[secret.record['id']]['name'], 'CH - micro')
        self.assertAlmostEqual(dosed[secret.record['id']]['gramsPerLitre'], 0.01, places=4)
        self.assertEqual(fit['excluded'], [])

    def test_shipped_product_without_grade_or_lot(self):
        resolved = resolve_material('Mg Nitrate')
        # 2026-10-18 catalogue correction (Mg Nitrate D1 / phosphoric 75 %)
        self.assertEqual(resolved.record['elements'], {'N_NO3': 10.92564, 'Mg': 9.47931})
        self.assertEqual(resolved.basis, {'N_NO3': 'identity_theoretical', 'Mg': 'identity_theoretical'})
        self.assertEqual(resolved.band_minimum, {'N_NO3': None, 'Mg': None})
        self.assertEqual(resolved.band_maximum, {'N_NO3': None, 'Mg': None})
        self.assertEqual(resolved.record['formula'], 'Mg(NO3)2.6H2O')
        self.assertEqual(resolved.identity_id, 'idn-magnesium-nitrate-hexahydrate')
        self.assertIsNone(resolved.provenance['lotId'])

    def test_chelate_sodium_not_added_to_elements(self):
        resolved = resolve_material('Iron EDTA', grade=grade(
            identity_id='idn-sodium-iron-edta', analysis={'Fe': {'typical': 13.0}}))
        self.assertEqual(resolved.record['elements'], {'Fe': 13.0})


class CatalogueMigrationTests(unittest.TestCase):
    """Task 3: library.json references identities and carries the 2026-10-18 corrections."""

    BASES = {'declared_catalogue', 'identity_theoretical', 'grade_typical'}

    def salts(self):
        return {salt['name']: salt for salt in load_library()['salts']}

    def test_every_salt_links_to_identity(self):
        salts = self.salts()
        self.assertEqual(len(salts), 32)
        for name, salt in salts.items():
            with self.subTest(name=name):
                self.assertEqual(salt['identityId'], identity_for_product(name)['id'])
                self.assertIn(salt['analysisBasis'], self.BASES)
                self.assertIn('source', salt)
                if salt['source'] is not None:
                    self.assertEqual(set(salt['source']),
                                     {'supplier', 'title', 'issued', 'entered', 'url', 'sha256'})
        expected = {'Mg Nitrate': 'identity_theoretical', 'Calcium Nitrate (ag grade)': 'grade_typical',
                    'Calcium Chloride (Dihydrate)': 'identity_theoretical',
                    'Potassium Chloride': 'identity_theoretical',
                    # pH-up reagents (#75, owner decisions 2026-10-22)
                    'Potassium Carbonate': 'identity_theoretical', 'Potassium Bicarbonate': 'identity_theoretical',
                    'Potassium Hydroxide (45% solution)': 'grade_typical'}
        for name, salt in salts.items():
            self.assertEqual(salt['analysisBasis'], expected.get(name, 'declared_catalogue'), name)

    def test_ph_reagents_are_sourced_and_never_nutrient_salts(self):
        salts = self.salts()
        expected = {'Potassium Hydroxide (45% solution)': ('417661', 0.45 * 69.687554),
                    'Potassium Bicarbonate': ('237205', 39.053724),
                    'Potassium Carbonate': ('209619', 56.580316)}
        for name, (code, potassium) in expected.items():
            salt = salts[name]
            self.assertEqual(salt['role'], 'ph_reagent', name)
            self.assertAlmostEqual(salt['elements']['K'], potassium, places=5, msg=name)
            self.assertTrue(salt['source']['url'].endswith(code), name)
        self.assertEqual(salts['Potassium Hydroxide (45% solution)']['densityKgPerL'], 1.456)
        self.assertEqual([s['name'] for s in salts.values() if s.get('role') == 'ph_reagent'],
                         sorted(expected))

    def test_phosphoric_acid_is_75_percent_basis(self):
        salt = self.salts()['Phosphoric Acid (75%)']
        self.assertAlmostEqual(salt['elements']['P'], 31.608046 * 0.75, places=6)
        self.assertAlmostEqual(salt['elements']['P'], 23.706035, places=6)
        self.assertEqual(salt['formula'], 'H3PO4')
        self.assertEqual(salt['analysisBasis'], 'declared_catalogue')
        self.assertIsNone(salt['source'])
        self.assertEqual(salt['notes'], '75 % w/w aqueous solution; product-mass dosing')

    def test_mg_nitrate_uses_hexahydrate(self):
        salt = self.salts()['Mg Nitrate']
        theory = identity_for_product('Mg Nitrate')['theoretical_analysis']
        self.assertEqual(salt['formula'], 'Mg(NO3)2.6H2O')
        self.assertEqual(set(salt['elements']), {'N_NO3', 'Mg'})
        self.assertAlmostEqual(salt['elements']['N_NO3'], 10.92564, places=5)
        self.assertAlmostEqual(salt['elements']['Mg'], 9.47931, places=5)
        for key in ('N_NO3', 'Mg'):
            self.assertAlmostEqual(salt['elements'][key], theory[key], places=4)
        self.assertEqual(salt['analysisBasis'], 'identity_theoretical')

    def test_phosphoric_regression(self):
        from flahax.product_conversion import catalogue_dose_totals
        before = 0.010205411922516871  # PO4-3 mol/kg water for 1 g/kg, captured before the 75 % correction
        after = catalogue_dose_totals({'Phosphoric Acid (75%)': 1.0})['PO4-3']
        # The old row stored P 31.61 (rounded); the new one is 0.75 x the exact 31.608046,
        # so the ratio is 23.706035 / 31.61 = 0.749954, i.e. 0.75 to 1e-4 relative.
        self.assertAlmostEqual(after / before, 23.706035 / 31.61, places=12)
        self.assertAlmostEqual(after / before, 0.75, delta=1e-4)

    def test_calcium_nitrate_cites_haifa_cal_ng(self):
        salt = self.salts()['Calcium Nitrate (ag grade)']
        self.assertEqual(salt['elements'], {'N_NO3': 14.4, 'N_NH4': 1.1, 'Ca': 19})
        source = salt['source']
        self.assertEqual(source['supplier'], 'Haifa Group')
        self.assertEqual(source['issued'], '2018-10-01')
        self.assertEqual(source['entered'], '2026-10-18')
        self.assertTrue(source['url'].startswith('https://www.haifa-group.com/'))
        # The reference has the same shape materials.make_grade accepts.
        make_grade({'grade_id': 'grd-check', 'identity_id': salt['identityId'], 'supplier': source['supplier'],
                    'product': 'Haifa Cal NG', 'document': source,
                    'analysis': {key: {'typical': value} for key, value in salt['elements'].items()}})

    def test_metadata_fixes(self):
        salts = self.salts()
        self.assertEqual(salts['Urea']['formula'], 'CO(NH2)2')
        self.assertEqual(salts['Iron II Sulfate (Hepahydrate)']['displayName'], 'Iron(II) Sulfate (Heptahydrate)')
        self.assertEqual(salts['Potassium Citrate']['displayName'], 'Potassium Citrate (anhydrous)')

    def test_urea_formula_still_doses(self):
        from flahax.composition import assay_conflict, assay_drift
        urea = self.salts()['Urea']
        self.assertIsNone(assay_conflict(urea))
        self.assertIsNone(assay_drift(urea))

    def test_resolve_material_reports_catalogue_basis(self):
        for name, salt in self.salts().items():
            with self.subTest(name=name):
                resolved = resolve_material(name)
                self.assertEqual(set(resolved.basis.values()), {salt['analysisBasis']})
        self.assertEqual(resolve_material('Calcium Nitrate (ag grade)').basis,
                         {'N_NO3': 'grade_typical', 'N_NH4': 'grade_typical', 'Ca': 'grade_typical'})


PURE_WATER_ID = 'ro-test'
HAIFA = {'N_NO3': {'typical': 14.4}, 'N_NH4': {'typical': 1.1}, 'Ca': {'typical': 19.0}}


def _old_totals(doses):
    """Pre-Task-5 catalogue_dose_totals: shipped records through their own chemistry."""
    from flahax.product_conversion import convert_catalogue_product_dose
    library = {s['name']: s for s in load_library()['salts']}
    mapping = {'Ca': 'Ca+2', 'Mg': 'Mg+2', 'K': 'K+', 'Na': 'Na+', 'sodium': 'Na+',
               'Fe': 'Fe+3', 'Mn': 'Mn+2', 'Zn': 'Zn+2', 'Cu': 'Cu+2', 'boron': 'H3BO3',
               'molybdate': 'MoO4-2', 'phosphate': 'PO4-3', 'sulfate': 'SO4-2',
               'nitrate': 'NO3-', 'ammonium': 'NH4+', 'carbonate': 'CO3-2', 'urea': 'Ure',
               'EDTA': 'Edta-4', 'DTPA': 'Dtp-5', 'o,o-EDDHA': 'Edd-4', 'citrate': 'Citrate-3'}
    out = {}
    for name, dose in doses.items():
        c = convert_catalogue_product_dose(library[name], dose)
        for source in (c.totals, c.counterions, c.ligands):
            for key, amount in source.items():
                basis = 'Fe+2' if key == 'Fe' and name == 'Iron II Sulfate (Hepahydrate)' else mapping[key]
                out[basis] = out.get(basis, 0.0) + amount
    return out


class ChemistryUseTests(unittest.TestCase):
    """Task 5: resolved materials in chemistry, undisclosed blends and provenance."""

    def ec(self, doses, **kw):
        from flahax.irrigation_ec import DeclaredPureWater, calculate_irrigation_ec
        return calculate_irrigation_ec(doses, recipe_id='r', water=DeclaredPureWater(PURE_WATER_ID),
                                       ph_mode='calculated', phase_policy='dissolved', **kw)

    def test_user_lot_changes_chemistry_totals(self):
        from flahax.product_conversion import catalogue_dose_totals
        name = 'Calcium Nitrate (ag grade)'
        g = grade(grade_id='grd-can', identity_id=CAN, analysis=HAIFA)
        material = resolve_material(name, grade=g, lot=lot(grade_id='grd-can', measured={'Ca': 18.5},
                                                           uncertainty={}))
        self.assertEqual(material.basis['Ca'], 'lot_measured')
        shipped = catalogue_dose_totals({name: 1.0})
        user = catalogue_dose_totals({name: 1.0}, materials={name: material})
        self.assertAlmostEqual(user['Ca+2'], shipped['Ca+2'] * 18.5 / 19.0, places=15)
        self.assertNotEqual(user['Ca+2'], shipped['Ca+2'])
        for basis in ('NO3-', 'NH4+'):
            self.assertAlmostEqual(user[basis], shipped[basis], places=15)

    def test_undisclosed_blend_refuses_chemistry(self):
        from flahax.irrigation_ec import assay_charge_residual
        from flahax.product_conversion import catalogue_dose_totals
        secret = resolve_material('CH - micro', grade=grade(
            grade_id='grd-secret', identity_id=None, composition='undisclosed',
            analysis={'Fe': {'typical': 7.0}}))
        doses = {'CH - micro': 0.05, 'Potassium Nitrate': 1.0}
        materials = {'CH - micro': secret}
        for call in (lambda: catalogue_dose_totals(doses, materials=materials),
                     lambda: assay_charge_residual(doses, materials=materials)):
            with self.assertRaises(DeliveryError) as caught:
                call()
            self.assertEqual(caught.exception.code, 'composition_undisclosed')
        r = self.ec(doses, materials=materials)
        self.assertEqual((r.status, r.reason), ('not_supported', 'composition_undisclosed'))
        self.assertIsNone(r.ec25_ms_cm)
        self.assertEqual(r.contributions_ms_cm, {})
        self.assertEqual(r.audit['materials']['CH - micro']['composition'], 'undisclosed')
        # Invalid mode input still raises before the refusal.
        with self.assertRaises(DeliveryError) as caught:
            self.ec(doses, materials=materials, ph=6.0)
        self.assertEqual(caught.exception.code, 'invalid_ph_input')

    def test_disclosed_blend_converts_components(self):
        from flahax.product_conversion import catalogue_dose_totals
        blend = resolve_material('CH - micro', grade=grade(
            grade_id='grd-blend', identity_id='idn-ch-micro-assumed-blend', composition='disclosed',
            components=[{'identity_id': 'idn-sodium-iron-edta', 'mass_fraction': 0.6},
                        {'identity_id': 'idn-borax-decahydrate', 'mass_fraction': 0.3}],
            analysis={'Fe': {'typical': 7.0}}))
        got = catalogue_dose_totals({'CH - micro': 2.0}, materials={'CH - micro': blend})
        # Declared Fe 7 vs 0.6 x 13 = 7.8 implied by the components: reported, not rejected.
        self.assertIn('blend_analysis_unreconciled', blend.flags)
        self.assertAlmostEqual(blend.provenance['blendImpliedAnalysis']['Fe'], 7.8, places=12)
        r = self.ec({'CH - micro': 0.05}, materials={'CH - micro': blend})
        entry = r.audit['materials']['CH - micro']
        self.assertIn('blend_analysis_unreconciled', entry['flags'])
        self.assertAlmostEqual(entry['blendImpliedAnalysis']['Fe'], 7.8, places=12)
        reconciled = resolve_material('CH - micro', grade=grade(
            grade_id='grd-blend', identity_id=None, composition='disclosed',
            components=[{'identity_id': 'idn-sodium-iron-edta', 'mass_fraction': 0.6}],
            analysis={'Fe': {'typical': 7.6}}))
        self.assertNotIn('blend_analysis_unreconciled', reconciled.flags)
        expected = _old_totals({'Iron EDTA': 1.2, 'Sodium Borate (Decahydrate) (borax)': 0.6})
        self.assertEqual(set(got), set(expected))
        for basis, amount in expected.items():
            self.assertAlmostEqual(got[basis], amount, places=15, msg=basis)
        # The shipped assumed blend (no listed components) keeps its own chemistry profile.
        shipped = resolve_material('CH - micro')
        self.assertEqual(catalogue_dose_totals({'CH - micro': 2.0}, materials={'CH - micro': shipped}),
                         _old_totals({'CH - micro': 2.0}))

    def test_irrigation_ec_reports_material_provenance(self):
        from flahax.materials import IDENTITIES_SHA256 as SHA
        name = 'Calcium Nitrate (ag grade)'
        material = resolve_material(name, grade=grade(grade_id='grd-can', identity_id=CAN, analysis=HAIFA))
        r = self.ec({name: 1.0, 'Potassium Nitrate': 0.5}, materials={name: material})
        self.assertEqual(set(r.audit['materials']), {name, 'Potassium Nitrate'})
        user = r.audit['materials'][name]
        self.assertEqual(user['identityId'], CAN)
        self.assertEqual(user['gradeId'], 'grd-can')
        self.assertEqual(user['documents']['grade']['title'], DOC['title'])
        self.assertEqual(user['basis'], {'N_NO3': 'grade_typical', 'N_NH4': 'grade_typical',
                                         'Ca': 'grade_typical'})
        shipped = r.audit['materials']['Potassium Nitrate']
        self.assertEqual(shipped['identityId'], 'idn-potassium-nitrate')
        self.assertIsNone(shipped['gradeId'])
        self.assertEqual(set(shipped['basis'].values()), {'declared_catalogue'})
        self.assertEqual(shipped['analysisBasis'], 'declared_catalogue')
        self.assertEqual(r.audit['identitiesSha256'], SHA)
        # A shipped product dosed without materials carries its library basis and source document.
        plain = self.ec({name: 1.0})
        entry = plain.audit['materials'][name]
        self.assertEqual(entry['analysisBasis'], 'grade_typical')
        self.assertEqual(entry['source']['supplier'], 'Haifa Group')

    def test_shipped_provenance_carries_source_document(self):
        can = resolve_material('Calcium Nitrate (ag grade)')
        salt = {s['name']: s for s in load_library()['salts']}['Calcium Nitrate (ag grade)']
        self.assertEqual(can.provenance['source'], salt['source'])
        self.assertIsNone(resolve_material('Potassium Nitrate').provenance['source'])
        graded = resolve_material('Calcium Nitrate (ag grade)',
                                  grade=grade(grade_id='grd-can', identity_id=CAN, analysis=HAIFA))
        self.assertIsNone(graded.provenance['source'])

    def test_materials_key_mismatch(self):
        from flahax.product_conversion import catalogue_dose_totals
        kno3 = resolve_material('Potassium Nitrate')
        doses = {'Potassium Nitrate': 1.0, 'Potassium Sulfate': 1.0}
        for materials in ({'Mg Nitrate': resolve_material('Mg Nitrate')},  # not dosed
                          {'Potassium Sulfate': kno3},  # name differs from key
                          {'Potassium Nitrate': 'not a material'}):
            with self.subTest(materials=materials):
                with self.assertRaises(DeliveryError) as caught:
                    catalogue_dose_totals(doses, materials=materials)
                self.assertEqual(caught.exception.code, 'material_mismatch')
                with self.assertRaises(DeliveryError) as caught:
                    self.ec(doses, materials=materials)
                self.assertEqual(caught.exception.code, 'material_mismatch')

    def test_no_materials_is_unchanged(self):
        from flahax.irrigation_ec import assay_charge_residual
        from flahax.product_conversion import catalogue_dose_totals
        doses = {'Calcium Nitrate (ag grade)': 0.9, 'Potassium Nitrate': 0.4, 'Iron EDTA': 0.02,
                 'Iron II Sulfate (Hepahydrate)': 0.01, 'CH - micro': 0.03,
                 'Ammonium Monobasic Phosphate': 0.15, 'Magnesium Sulfate (Heptahydrate)': 0.5}
        before = _old_totals(doses)
        self.assertEqual(catalogue_dose_totals(doses), before)
        self.assertEqual(catalogue_dose_totals(doses, materials={}), before)
        self.assertEqual(catalogue_dose_totals(doses, materials=None), before)
        shipped = {name: resolve_material(name) for name in doses}
        self.assertEqual(catalogue_dose_totals(doses, materials=shipped), before)
        self.assertEqual(assay_charge_residual(doses, materials=shipped), assay_charge_residual(doses))
        plain, explicit = self.ec(doses), self.ec(doses, materials=shipped)
        self.assertEqual((plain.status, plain.ec25_ms_cm), (explicit.status, explicit.ec25_ms_cm))
        self.assertEqual(plain.audit['materials'], explicit.audit['materials'])

    def test_user_grade_drives_o5_gate(self):
        # Controller ruling (Task 3): the retired Mg Nitrate analysis as a user grade.
        from flahax.irrigation_ec import assay_charge_residual
        retired = resolve_material('Mg Nitrate', grade=grade(
            grade_id='grd-old-mgn', identity_id='idn-magnesium-nitrate-hexahydrate',
            analysis={'N_NO3': {'typical': 11.0}, 'Mg': {'typical': 9.65}}))
        residual = assay_charge_residual({'Mg Nitrate': 1.0}, materials={'Mg Nitrate': retired})
        self.assertAlmostEqual(residual['percent'], 0.5532, places=3)
        r = self.ec({'Mg Nitrate': 1.0}, materials={'Mg Nitrate': retired})
        self.assertEqual((r.status, r.reason), ('not_supported', 'assay_charge_residual_too_large'))
        self.assertIn('identity_inconsistent', r.audit['materials']['Mg Nitrate']['flags'])
        shipped = self.ec({'Mg Nitrate': 1.0})
        self.assertNotEqual(shipped.reason, 'assay_charge_residual_too_large')

    def test_equilibrium_plan_audits_materials(self):
        from flahax import plan_equilibrium_delivery
        from flahax.materials import IDENTITIES_SHA256 as SHA
        from tests.test_equilibrium_delivery import arguments
        plan = plan_equilibrium_delivery(**arguments())
        self.assertEqual(plan.audit['identitiesSha256'], SHA)
        self.assertEqual(set(plan.audit['materials']), set(plan.audit['productDosesGPerKgWater']))
        salts = {s['name']: s for s in load_library()['salts']}
        for name, entry in plan.audit['materials'].items():
            self.assertEqual(entry['identityId'], salts[name]['identityId'])
            self.assertEqual(entry['analysisBasis'], salts[name]['analysisBasis'])
            self.assertEqual(entry['source'], salts[name]['source'])


KNO3 = 'idn-potassium-nitrate'


class BandTests(unittest.TestCase):
    """Task 6: delivered-nutrient band re-evaluates the same doses at band-end assays."""

    def banded(self):
        mkp = resolve_material('Potassium Monobasic Phosphate', grade=grade(
            grade_id='grd-mkp', analysis={'K': {'typical': 28.0, 'minimum': 27.0, 'maximum': 29.0},
                                          'P': {'typical': 22.5, 'minimum': 22.0, 'maximum': 23.0}}))
        kno3 = resolve_material('Potassium Nitrate', grade=grade(
            grade_id='grd-kno3', identity_id=KNO3,
            analysis={'K': {'typical': 38.0, 'minimum': 37.0, 'maximum': 38.5},
                      'N_NO3': {'typical': 13.0, 'minimum': 12.5, 'maximum': 13.5}}))
        return {'Potassium Monobasic Phosphate': mkp, 'Potassium Nitrate': kno3}

    def test_band_is_linear_reevaluation(self):
        from flahax.materials import nutrient_band
        doses = {'Potassium Monobasic Phosphate': 1.0, 'Potassium Nitrate': 2.0}
        result = nutrient_band(doses, materials=self.banded())
        k = result['nutrients']['K']
        self.assertAlmostEqual(k['nominal_mg_per_l'], (1.0 * 28.0 + 2.0 * 38.0) * 10)
        self.assertAlmostEqual(k['minimum_mg_per_l'], (1.0 * 27.0 + 2.0 * 37.0) * 10)
        self.assertAlmostEqual(k['maximum_mg_per_l'], (1.0 * 29.0 + 2.0 * 38.5) * 10)
        p = result['nutrients']['P']
        self.assertAlmostEqual(p['minimum_mg_per_l'], 220.0)
        self.assertAlmostEqual(p['maximum_mg_per_l'], 230.0)
        self.assertEqual(result['basis']['Potassium Nitrate']['K'], 'grade_typical')
        self.assertIn('nutrient amounts only', result['note'])

    def test_open_bound_propagates(self):
        from flahax.materials import nutrient_band
        doses = {'Potassium Monobasic Phosphate': 1.0, 'Potassium Nitrate': 2.0}
        materials = self.banded()
        del materials['Potassium Nitrate']  # shipped record: K has no band
        k = nutrient_band(doses, materials=materials)['nutrients']['K']
        self.assertIsNone(k['minimum_mg_per_l'])
        self.assertIsNone(k['maximum_mg_per_l'])
        self.assertIsNotNone(k['nominal_mg_per_l'])
        # a nutrient only the banded product supplies keeps its band
        p = nutrient_band(doses, materials=materials)['nutrients']['P']
        self.assertAlmostEqual(p['minimum_mg_per_l'], 220.0)

    def test_shipped_only_has_no_band(self):
        from flahax.materials import nutrient_band
        library = {s['name']: s for s in load_library()['salts']}
        result = nutrient_band({'Potassium Nitrate': 1.5})
        for symbol, entry in result['nutrients'].items():
            self.assertIsNone(entry['minimum_mg_per_l'])
            self.assertIsNone(entry['maximum_mg_per_l'])
            nominal = 1.5 * library['Potassium Nitrate']['elements'][symbol] * 10
            self.assertAlmostEqual(entry['nominal_mg_per_l'], nominal)
        self.assertEqual(set(result['basis']), {'Potassium Nitrate'})

    def test_band_does_not_call_solver(self):
        from unittest import mock
        from flahax.materials import nutrient_band
        with mock.patch('flahax.engine.recommend', side_effect=AssertionError('solver called')):
            nutrient_band({'Potassium Monobasic Phosphate': 1.0, 'Potassium Nitrate': 2.0},
                          materials=self.banded())

    def test_band_accepts_undisclosed_blend_chemistry_refuses_it(self):
        from flahax.materials import nutrient_band
        from flahax.product_conversion import catalogue_dose_totals
        secret = resolve_material('CH - micro', grade=grade(
            grade_id='grd-secret', identity_id=None, composition='undisclosed',
            analysis={'Fe': {'typical': 7.0, 'minimum': 6.5, 'maximum': 7.5}}))
        doses = {'CH - micro': 0.1}
        band = nutrient_band(doses, materials={'CH - micro': secret})
        self.assertAlmostEqual(band['nutrients']['Fe']['nominal_mg_per_l'], 7.0)
        self.assertAlmostEqual(band['nutrients']['Fe']['minimum_mg_per_l'], 6.5)
        with self.assertRaises(DeliveryError) as caught:
            catalogue_dose_totals(doses, materials={'CH - micro': secret})
        self.assertEqual(caught.exception.code, 'composition_undisclosed')

    def test_material_mismatch(self):
        from flahax.materials import nutrient_band
        materials = self.banded()
        with self.assertRaises(DeliveryError) as caught:
            nutrient_band({'Potassium Nitrate': 1.0}, materials=materials)
        self.assertEqual(caught.exception.code, 'material_mismatch')
        with self.assertRaises(DeliveryError) as caught:
            nutrient_band({'Potassium Nitrate': 1.0},
                          materials={'Potassium Nitrate': materials['Potassium Monobasic Phosphate']})
        self.assertEqual(caught.exception.code, 'material_mismatch')


class FormulationProvenanceTests(unittest.TestCase):
    """F1: every salt on a formulation result carries the provenance of its own record."""
    TARGETS = {'N_NO3': 150.0, 'K': 200.0, 'Ca': 120.0, 'P': 40.0, 'Mg': 40.0}

    def entries(self, library):
        from flahax.engine import recommend
        result = recommend(library, self.TARGETS)
        return result, {item['id']: item for item in result['salts']}

    def test_shipped_recommend_has_catalogue_provenance(self):
        result, entries = self.entries(load_library()['salts'])
        self.assertTrue(entries)
        for item in entries.values():
            self.assertTrue(item['provenance']['identityId'].startswith('idn-'), item['name'])
            self.assertEqual(item['provenance']['recordId'], item['id'])
        can = next(i for i in entries.values() if i['name'] == 'Calcium Nitrate (ag grade)')
        self.assertEqual(can['provenance']['analysisBasis'], 'grade_typical')
        self.assertEqual(can['provenance']['documents'][0]['supplier'], 'Haifa Group')
        self.assertIsInstance(can['provenance']['flags'], list)

    def test_resolved_record_provenance_flows(self):
        g = grade(grade_id='grd-kno3', identity_id='idn-potassium-nitrate',
                  analysis={'K': {'typical': 38.0}, 'N_NO3': {'typical': 13.0}})
        material = resolve_material('Potassium Nitrate', grade=g)
        library = [material.record if s['name'] == 'Potassium Nitrate' else s
                   for s in load_library()['salts']]
        _, entries = self.entries(library)
        resolved = entries[material.record['id']]
        self.assertEqual(resolved['provenance']['recordId'], f"{material.record['id']}")
        self.assertIn('+grd-kno3', resolved['provenance']['recordId'])
        self.assertEqual(resolved['provenance']['analysisBasis'], material.basis)
        self.assertEqual(resolved['provenance']['analysisBasis']['K'], 'grade_typical')
        self.assertEqual(resolved['provenance']['documents'][0]['title'], DOC['title'])
        for key, item in entries.items():
            if key != material.record['id']:
                self.assertTrue(item['provenance']['identityId'].startswith('idn-'))
                self.assertNotIsInstance(item['provenance']['analysisBasis'], dict)

    def test_gradeless_resolved_record_keeps_catalogue_document(self):
        material = resolve_material('Calcium Nitrate (ag grade)')
        library = [material.record if s['name'] == 'Calcium Nitrate (ag grade)' else s
                   for s in load_library()['salts']]
        _, entries = self.entries(library)
        resolved = entries[material.record['id']]
        _, shipped = self.entries(load_library()['salts'])
        self.assertEqual(resolved['provenance']['documents'],
                         shipped[material.record['id']]['provenance']['documents'])
        self.assertEqual(resolved['provenance']['documents'][0]['supplier'], 'Haifa Group')

    def test_unattributed_record(self):
        from flahax.engine import recommend
        record = {'id': 'hand', 'name': 'Hand KNO3', 'formula': 'KNO3',
                  'elements': {'K': 38.67, 'N_NO3': 13.85}}
        result = recommend([record], {'K': 38.0, 'N_NO3': 13.0})
        provenance = result['salts'][0]['provenance']
        self.assertEqual(provenance['analysisBasis'], 'unattributed')
        self.assertIsNone(provenance['identityId'])
        self.assertEqual(provenance['documents'], [])
        self.assertEqual(provenance['recordId'], 'hand')

    def test_identities_hash_on_result(self):
        result, _ = self.entries(load_library()['salts'])
        self.assertEqual(result['identitiesSha256'], IDENTITIES_SHA256)


class ChelateSodiumReportTests(unittest.TestCase):
    """F2: chelate counterion sodium (D2) is reported in rows, never fitted."""
    NO_CHELATE_TARGETS = {'N_NO3': 150.0, 'K': 200.0, 'Ca': 120.0, 'P': 40.0, 'Mg': 40.0}
    # Captured from recommend() before F2 (no chelate chosen).
    NO_CHELATE_ROWS = [
        {'symbol': 'N_NO3', 'target': 150.0, 'final': 150.00426635374635, 'deltaPct': 0.0028442358308969538},
        {'symbol': 'K', 'target': 200.0, 'final': 199.9932778479975, 'deltaPct': -0.0033610760012550145},
        {'symbol': 'Ca', 'target': 120.0, 'final': 119.40257151155895, 'deltaPct': -0.497857073700878},
        {'symbol': 'P', 'target': 40.0, 'final': 39.99986923316647, 'deltaPct': -0.00032691708382159845},
        {'symbol': 'Mg', 'target': 40.0, 'final': 39.996801591822894, 'deltaPct': -0.007996020442764262},
        {'symbol': 'N_NH4', 'target': None, 'final': 6.91278045593236, 'deltaPct': None},
    ]
    NO_CHELATE_INCIDENTAL = [
        {'symbol': 'N_NH4', 'ppm': 6.91278045593236, 'target': None, 'maximumPpm': None,
         'assessment': 'requires_review'},
    ]

    def chilli(self):
        library = load_library()
        formula = next(f for f in library['formulas'] if f['name'].startswith('Chilli'))
        return library['salts'], formula['targets']

    def test_chelate_sodium_reported_not_fitted(self):
        from unittest import mock
        from flahax import engine
        salts, targets = self.chilli()
        base = engine.recommend(salts, targets)
        with mock.patch.object(engine, 'counterion_sodium_mg_per_l', return_value=0.0):
            off = engine.recommend(salts, targets)
        names = {s['name'] for s in base['salts']}
        self.assertIn('Mn EDTA', names)
        self.assertEqual(base['grams'], off['grams'])
        self.assertEqual(names, {s['name'] for s in off['salts']})
        doses = {s['name']: s['gramsPerLitre'] for s in base['salts']}
        from flahax.product_conversion import counterion_sodium_mg_per_l
        extra = counterion_sodium_mg_per_l([(next(r for r in salts if r['name'] == n), g)
                                         for n, g in doses.items()])
        self.assertGreater(extra, 0)
        na = lambda res: next(r for r in res['rows'] if r['symbol'] == 'Na')
        self.assertAlmostEqual(na(base)['final'] - na(off)['final'], extra, places=9)
        self.assertIsNone(na(base)['target'])
        entry = next(i for i in base['incidentalContributions'] if i['symbol'] == 'Na')
        self.assertAlmostEqual(entry['ppm'], na(base)['final'], places=9)
        self.assertEqual(entry['assessment'], 'requires_review')
        self.assertIn('Incidental Na includes formula counterion sodium (chelates D2, '
                      f'CH - micro borax/molybdate): {extra:.4f} mg/L.', base['warnings'])
        self.assertFalse(any('counterion sodium' in w for w in off['warnings']))

    def test_na_row_created_when_absent(self):
        from flahax.engine import recommend
        library = load_library()['salts']
        chosen = {'Mn EDTA'}
        pool = [s for s in library if s['name'] in chosen]
        result = recommend(pool, {'Mn': 2.0})
        row = next(r for r in result['rows'] if r['symbol'] == 'Na')
        self.assertIsNone(row['target'])
        self.assertGreater(row['final'], 0)

    def test_no_chelate_recipe_unchanged(self):
        from flahax.engine import recommend
        # Pinned to the penalty-only fit: the #54 ammonium allowance changes this recipe
        # independently of chelate sodium reporting (Ca 119.40 -> 119.98 mg/L).
        result = recommend(load_library()['salts'], self.NO_CHELATE_TARGETS, max_ammonium_fraction=None)
        self.assertNotIn('Mn EDTA', {s['name'] for s in result['salts']})
        self.assertEqual(len(result['rows']), len(self.NO_CHELATE_ROWS))
        for got, want in zip(result['rows'], self.NO_CHELATE_ROWS):
            self.assertEqual(got['symbol'], want['symbol'])
            self.assertEqual(got['target'], want['target'])
            self.assertAlmostEqual(got['final'], want['final'], places=9)
        self.assertEqual(result['incidentalContributions'][0]['symbol'], 'N_NH4')
        self.assertEqual(len(result['incidentalContributions']), 1)
        self.assertAlmostEqual(result['incidentalContributions'][0]['ppm'],
                               self.NO_CHELATE_INCIDENTAL[0]['ppm'], places=9)
        # The synthetic targets omit S, so the formula is unbalanced (+16.6%) and says so;
        # no other warning, in particular no chelate-sodium note, may appear.
        self.assertEqual([w for w in result['warnings'] if 'not electrically balanced' not in w], [])

    def test_helper_matches_chemistry(self):
        from flahax.product_conversion import catalogue_dose_totals, counterion_sodium_mg_per_l
        by_name = {s['name']: s for s in load_library()['salts']}
        doses = {'Iron EDTA': 0.05, 'Mn EDTA': 0.02, 'Zn EDTA': 0.01, 'Copper EDTA': 0.004,
                 'Iron DTPA': 0.03, 'Iron EDDHA': 0.04}
        expected = catalogue_dose_totals(doses)['Na+'] * 22.98977 * 1000.0
        got = counterion_sodium_mg_per_l([(by_name[n], d) for n, d in doses.items()])
        self.assertGreater(got, 0)
        self.assertAlmostEqual(got, expected, places=6)

    def test_helper_counts_all_counterion_sodium_of_micro_blend(self):
        from flahax.product_conversion import catalogue_dose_totals, counterion_sodium_mg_per_l
        by_name = {s['name']: s for s in load_library()['salts']}
        got = counterion_sodium_mg_per_l([(by_name['CH - micro'], 1.0)])
        full = catalogue_dose_totals({'CH - micro': 1.0})['Na+'] * 22.98977 * 1000.0
        self.assertAlmostEqual(got, full, places=9)  # chelate share plus borax/molybdate sodium
        self.assertAlmostEqual(got, 63.23, places=2)
        # Standalone borax and sodium molybdate assay Na as an element: no counterion sodium.
        self.assertEqual(counterion_sodium_mg_per_l([(by_name['Boric Acid'], 1.0),
                                                     (by_name['Sodium Molybdate (Dihydrate)'], 1.0),
                                                     (by_name['Sodium Borate (Decahydrate) (borax)'], 1.0)]),
                         0.0)

    def test_na_target_delta_recomputed(self):
        from unittest import mock
        from flahax import engine
        pool = [s for s in load_library()['salts'] if s['name'] == 'Mn EDTA']
        targets = {'Mn': 2.0, 'Na': 5.0}
        base = engine.recommend(pool, targets)
        with mock.patch.object(engine, 'counterion_sodium_mg_per_l', return_value=0.0):
            off = engine.recommend(pool, targets)
        row = next(r for r in base['rows'] if r['symbol'] == 'Na')
        off_row = next(r for r in off['rows'] if r['symbol'] == 'Na')
        self.assertGreater(row['final'], off_row['final'])
        self.assertAlmostEqual(row['deltaPct'], 100.0 * (row['final'] - 5.0) / 5.0, places=9)
        self.assertNotAlmostEqual(row['deltaPct'], off_row['deltaPct'], places=6)


class WorkflowGradeTests(unittest.TestCase):
    """Interactive mix Task 3: a supplier label grade passes the chemistry and pH stages."""
    # The only Fe source in Tomato (Howard Resh); magnesium sulfate shares Mg with Mg Nitrate.
    NAME = 'Iron II Sulfate (Hepahydrate)'
    NITRIC = dict(id='HNO3-example', source='EXAMPLE GRADE', revision='1', recordedAt='2026-10-22T00:00:00Z',
                  chemicalFormula='HNO3', massFraction=.60, densityKgPerL=1.37)
    RO = dict(water_totals={}, water_mass_kg=1000, water_analysis_id='RO', complete_analysis=True,
              carbon_boundary='closed', temperature_c=25, phases=[])

    def graded(self, scale, fe=1.0):
        shipped = {s['name']: s for s in load_library()['salts']}[self.NAME]
        record = {'grade_id': 'grd-feso4-97', 'identity_id': shipped['identityId'], 'supplier': 'Example Supplier',
                  'product': 'Ferrous sulfate 97 %', 'composition': 'single', 'document': DOC,
                  'analysis': {k: {'typical': v * scale * (fe if k == 'Fe' else 1.0)}
                               for k, v in shipped['elements'].items()}}
        material = resolve_material(self.NAME, grade=make_grade(record))
        return dict(shipped, grade=record, elements=material.record['elements']), material

    def workflow(self, product=None):
        from flahax import VolumeLitres, plan_fertilizer_workflow
        library = load_library()
        salts = [product if product is not None and s['name'] == product['name'] else s for s in library['salts']]
        targets = {f['name']: f['targets'] for f in library['formulas']}['Tomato (Howard Resh)']
        return plan_fertilizer_workflow(salts, targets, {}, 5.8, final_volume=VolumeLitres(1000), equilibrium=self.RO,
                                        ph_adjustment=dict(products=[self.NITRIC], maximum_reagent_volume_litres=5))

    @staticmethod
    def doses(recommendation):
        return {s['name']: s['gramsPerLitre'] for s in recommendation['salts']}

    def test_label_grade_enters_chemistry_and_ph(self):
        from flahax.product_conversion import catalogue_dose_totals
        product, material = self.graded(0.97)
        self.assertEqual(material.flags, ())
        shipped, graded = self.workflow(), self.workflow(product)
        for stage in ('chemistry', 'ph_adjustment'):
            self.assertIn(graded.stages[stage].status, ('calculated', 'requires_review'), stage)
        self.assertEqual(graded.stages['chemistry'].status, 'calculated')
        fe_sources = [s['name'] for s in graded.recommendation['salts']
                      if 'Fe' in {x['name']: x for x in load_library()['salts']}[s['name']]['elements']]
        self.assertEqual(fe_sources, [self.NAME])
        # Weighed doses are recorded to 1e-6 g/L; both rounding errors bound the ratio check.
        self.assertAlmostEqual(self.doses(graded.recommendation)[self.NAME],
                               self.doses(shipped.recommendation)[self.NAME] / 0.97, delta=0.5e-6 * (1 + 1 / 0.97))
        # The conversion used the resolved label assay, not the catalogue assay.
        chemistry = graded.stages['chemistry'].value
        doses = chemistry['product_doses_g_per_kg_water']
        self.assertEqual(chemistry['materials'][self.NAME], material)
        label = catalogue_dose_totals(doses, materials={self.NAME: material})
        catalogue = catalogue_dose_totals(doses)
        self.assertAlmostEqual(chemistry['mixed'].totals['Fe+2'], label['Fe+2'], delta=1e-15)
        self.assertAlmostEqual(label['Fe+2'], 0.97 * catalogue['Fe+2'], delta=1e-15)
        selected = graded.stages['ph_adjustment'].value.selected
        mixed_doses = self.doses(selected.recommendation)  # g/L x 1000 L / 1000 kg water
        self.assertAlmostEqual(selected.mixed.totals['Fe+2'],
                               catalogue_dose_totals(mixed_doses, materials={self.NAME: material})['Fe+2'], delta=1e-15)
        # The graded record id (<catalogue id>+<grade id>) is found as well.
        resolved_id = self.workflow(dict(product, id=material.record['id']))
        self.assertEqual(resolved_id.stages['chemistry'].status, 'calculated')

    def test_inconsistent_label_is_refused(self):
        product, material = self.graded(0.97, fe=1.10)
        self.assertIn('identity_inconsistent', material.flags)
        stage = self.workflow(product).stages['chemistry']
        self.assertEqual((stage.status, stage.error_code), ('blocked', 'identity_inconsistent'))
        self.assertIn(self.NAME, stage.message)

    def test_changed_assay_without_grade_is_still_refused(self):
        product, _ = self.graded(0.97)
        del product['grade']
        stage = self.workflow(product).stages['chemistry']
        self.assertEqual(stage.error_code, 'product_chemistry_mismatch')

if __name__ == '__main__':
    unittest.main()
