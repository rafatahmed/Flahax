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
    'NO3-': -1, 'SO4-2': -2, 'H2PO4-': -1, 'HPO4-2': -2, 'CO3-2': -2,
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
        self.assertEqual(IDENTITIES_SHA256, '7713f20cc7e8eb83ea4fa9e90bf36b875c81599c2965f9ddf96818e4c372c891')


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
        self.assertEqual(resolved.record['id'], shipped['id'])
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
        self.assertEqual(resolved.basis, {'Fe': 'grade_typical', 'Zn': 'grade_typical'})
        with self.assertRaises(DeliveryError) as caught:
            grade(identity_id=None, composition='undisclosed',
                  components=[{'identity_id': MKP, 'mass_fraction': 0.5}])
        self.assertEqual(caught.exception.code, 'invalid_composition')

    def test_shipped_product_without_grade_or_lot(self):
        resolved = resolve_material('Mg Nitrate')
        self.assertEqual(resolved.record['elements'], {'N_NO3': 11, 'Mg': 9.65})
        self.assertEqual(resolved.basis, {'N_NO3': 'declared_catalogue', 'Mg': 'declared_catalogue'})
        self.assertEqual(resolved.band_minimum, {'N_NO3': None, 'Mg': None})
        self.assertEqual(resolved.band_maximum, {'N_NO3': None, 'Mg': None})
        self.assertEqual(resolved.record['formula'], 'Mg(NO3)2.6H2O')
        self.assertEqual(resolved.identity_id, 'idn-magnesium-nitrate-hexahydrate')
        self.assertIsNone(resolved.provenance['lotId'])

    def test_chelate_sodium_not_added_to_elements(self):
        resolved = resolve_material('Iron EDTA', grade=grade(
            identity_id='idn-sodium-iron-edta', analysis={'Fe': {'typical': 13.0}}))
        self.assertEqual(resolved.record['elements'], {'Fe': 13.0})


if __name__ == '__main__':
    unittest.main()
