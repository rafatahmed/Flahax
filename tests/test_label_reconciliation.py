# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Label reconciliation (decision G5, option a, 2026-10-31): only unbalanced charge is set aside.

Chemistry uses the label amounts as declared, except the charge the compound's ions cannot
balance: it is taken from the excess side's declared ions in proportion to their charge and
reported as not assigned to an ion. The nutrient fit keeps the label.
"""

import unittest

from flahax.composition import ATOMIC
from flahax.delivery_contracts import DeliveryError
from flahax.engine import load_library
from flahax.irrigation_ec import assay_charge_residual
from flahax.label_reconciliation import (
    LabelReconciliation,
    chemistry_elements,
    label_note,
    reconcile_label,
)
from flahax.material_chemistry import material_chemistry
from flahax.materials import load_identities, make_grade, resolve_material
from flahax.mix_cli import Prompts, add_single
from flahax.product_conversion import MOLAR_MASS, convert_material_dose, material_inventory

IDENTITIES = load_identities()
KNO3 = IDENTITIES['idn-potassium-nitrate']
# The identity's theory, from composition.theoretical_assay('KNO3') with O 15.999.
THEORY_N = KNO3['theoretical_analysis']['N_NO3']  # 13.854028604775376
THEORY_K = KNO3['theoretical_analysis']['K']  # 38.67213309331171
LABEL = {'N_NO3': 13.0, 'K': 38.2}
# KNO3 label: K+ and NO3- equivalents per 100 g; the cation surplus comes off K.
K_EQ, N_EQ = 38.2 / ATOMIC['K'], 13.0 / ATOMIC['N']
KNO3_SURPLUS_K = (K_EQ - N_EQ) / K_EQ * 38.2  # 1.9118022089428666
KNO3_IMBALANCE = 100 * (K_EQ - N_EQ) / (K_EQ + N_EQ)  # 2.5665840571221237


class ReconcileLabelTests(unittest.TestCase):
    def test_potassium_nitrate_label_leaves_its_potassium_surplus_unassigned(self):
        result = reconcile_label(KNO3, LABEL)
        self.assertIsInstance(result, LabelReconciliation)
        self.assertEqual(result.unassigned_percent, {'K': KNO3_SURPLUS_K})
        self.assertAlmostEqual(result.unassigned_percent['K'], 1.9118022089428666, places=12)
        self.assertEqual(result.imbalance_percent, KNO3_IMBALANCE)
        self.assertAlmostEqual(result.imbalance_percent, 2.5665840571221237, places=12)
        self.assertEqual(
            result.basis, "charge surplus of the label's cations, taken in proportion to charge"
        )

    def test_pure_compound_label_balances_exactly(self):
        # 38.672.../39.0983 and 13.854.../14.0067 are both 100 / formula mass: the net charge
        # is exactly 0.0 in floating point, so nothing is unassigned and no note is shown.
        pure = {'N_NO3': THEORY_N, 'K': THEORY_K}
        self.assertEqual(
            reconcile_label(KNO3, pure),
            LabelReconciliation({}, 0.0, 'the declared charges balance'),
        )
        self.assertIsNone(label_note(KNO3, pure))

    def test_calcium_nitrate_anion_surplus_comes_off_its_nitrate(self):
        double_salt = IDENTITIES['idn-ammonium-calcium-nitrate']
        label = {'N_NO3': 14.4, 'N_NH4': 1.1, 'Ca': 19.0}
        result = reconcile_label(double_salt, label)
        self.assertEqual(set(result.unassigned_percent), {'N_NO3'})
        self.assertAlmostEqual(result.unassigned_percent['N_NO3'], 0.01953191277009945, places=10)
        self.assertAlmostEqual(result.imbalance_percent, -0.06786516713661755, places=10)
        self.assertEqual(
            label_note(double_salt, label),
            'label analysis differs from 5Ca(NO₃)₂·NH₄NO₃·10H₂O: '
            '0.02 % N_NO3 not assigned to an ion',
        )

    def test_the_surplus_is_shared_by_charge_across_the_excess_side(self):
        double_salt = IDENTITIES['idn-ammonium-calcium-nitrate']
        label = {'N_NO3': 14.0, 'N_NH4': 1.4, 'Ca': 19.0}
        ca, nh4, no3 = 2 * 19.0 / ATOMIC['Ca'], 1.4 / ATOMIC['N'], 14.0 / ATOMIC['N']
        share = (ca + nh4 - no3) / (ca + nh4)
        result = reconcile_label(double_salt, label)
        self.assertEqual(set(result.unassigned_percent), {'Ca', 'N_NH4'})
        self.assertAlmostEqual(result.unassigned_percent['Ca'], share * 19.0, places=10)
        self.assertAlmostEqual(result.unassigned_percent['N_NH4'], share * 1.4, places=10)

    def test_a_label_closed_by_an_unstated_or_undeclared_ion_assigns_everything(self):
        self.assertEqual(
            reconcile_label(IDENTITIES['idn-disodium-manganese-edta'], {'Mn': 13}),
            LabelReconciliation({}, 0.0, 'an unstated ion closes the charge balance'),
        )
        self.assertEqual(
            reconcile_label(IDENTITIES['idn-potassium-carbonate'], {'K': 56.0}),
            LabelReconciliation({}, 0.0, 'an unstated ion closes the charge balance'),
        )
        for identity, label in (
            ('idn-potassium-hydroxide', {'K': 31.36}),
            ('idn-nitric-acid', {'N_NO3': 14.45}),
            ('idn-urea', {'N_UREA': 46.0}),
        ):
            with self.subTest(identity=identity):
                self.assertEqual(
                    reconcile_label(IDENTITIES[identity], label),
                    LabelReconciliation({}, 0.0, 'one side of the charge is not declared'),
                )

    def test_a_chelate_label_stating_its_sodium_is_balanced_against_the_complex(self):
        # NaFe(III)EDTA: one Na+ per Fe(III)-EDTA- complex; a label stating both balances.
        iron = IDENTITIES['idn-sodium-iron-edta']
        sodium = 13.0 / ATOMIC['Fe'] * ATOMIC['Na']
        self.assertEqual(reconcile_label(iron, {'Fe': 13.0, 'Na': sodium}).unassigned_percent, {})
        excess = reconcile_label(iron, {'Fe': 13.0, 'Na': 2 * sodium})
        self.assertEqual(set(excess.unassigned_percent), {'Na'})
        self.assertAlmostEqual(excess.unassigned_percent['Na'], sodium, places=12)

    def test_blends_have_no_defined_compound(self):
        mix = IDENTITIES['idn-micro-combi-mix-2-declared-blend']
        elements = {'Fe': 3.7, 'Cu': 0.2, 'Mn': 2.4, 'Zn': 1.5, 'Mo': 0.2, 'B': 1.4}
        self.assertIsNone(reconcile_label(mix, elements))
        self.assertEqual(
            label_note(mix, elements),
            'Micro Combi Mix 2 declared micronutrient blend has no defined compound: '
            'its label analysis is used as declared',
        )
        record = {'identityId': mix['id'], 'elements': elements}
        self.assertEqual(chemistry_elements(record, mix['ion_forms']), elements)

    def test_note_names_the_compound_the_elements_and_the_percent(self):
        self.assertEqual(
            label_note(KNO3, LABEL),
            'label analysis differs from KNO₃: 1.91 % K not assigned to an ion',
        )
        # A surplus that rounds to 0.00 % shows no note; the value stays in the result.
        copper = IDENTITIES['idn-copper-sulfate-pentahydrate']
        label = {'S': 12.84, 'Cu': 25.45}
        self.assertIsNone(label_note(copper, label))
        self.assertGreater(reconcile_label(copper, label).unassigned_percent['S'], 0)


class ChemistryUsesTheBalancedLabelTests(unittest.TestCase):
    def setUp(self):
        self.product = next(s for s in load_library()['salts'] if s['name'] == 'Potassium Nitrate')

    def test_chemistry_elements_are_the_label_without_its_surplus(self):
        ions = {'K+': 1, 'NO3-': 1}
        balanced = {'N_NO3': 13, 'K': 38.2 - KNO3_SURPLUS_K}
        self.assertEqual(chemistry_elements(self.product, ions), balanced)
        # A record without an identity is balanced against its own ions; so is a single grade.
        self.assertEqual(chemistry_elements({'elements': LABEL}, ions), balanced)
        graded = {'elements': LABEL, 'grade': {'identity_id': KNO3['id']}}
        self.assertEqual(chemistry_elements(graded, ions), balanced)
        # A disclosed blend's grade names no compound identity: its own ions decide.
        disclosed = {
            'elements': LABEL,
            'grade': {'composition': 'disclosed', 'identity_id': KNO3['id']},
        }
        self.assertEqual(chemistry_elements(disclosed, ions), balanced)

    def test_conversion_balances_the_charge_and_keeps_the_label_for_nutrients(self):
        converted = convert_material_dose(self.product, 1.0)
        nitrate = converted.totals['nitrate']
        self.assertAlmostEqual(nitrate, 13.0 / 100 / MOLAR_MASS['N'], delta=1e-15)
        self.assertAlmostEqual(converted.totals['K'], nitrate, delta=1e-15)
        self.assertLess(abs(assay_charge_residual({'Potassium Nitrate': 1.0})['percent']), 1e-9)
        inventory = material_inventory(self.product)
        self.assertEqual(inventory['nutrient_percent'], {'N_NO3': 13, 'K': 38.2})
        self.assertAlmostEqual(
            inventory['assay_component_difference_percent']['K'], KNO3_SURPLUS_K, places=12
        )


class PackagedCatalogueTests(unittest.TestCase):
    """The packaged catalogue (Flaha Agri Tech Analysis Ver 0.0) has no identity_inconsistent."""

    def test_every_product_resolves_with_chemistry_and_no_flag(self):
        for product in load_library()['salts']:
            with self.subTest(product=product['name']):
                self.assertEqual(resolve_material(product['name']).flags, ())
                material_chemistry(product)

    def test_a_label_grade_off_its_compound_is_not_flagged(self):
        grade = make_grade(
            {
                'grade_id': 'grd-kno3-13-0-46',
                'identity_id': KNO3['id'],
                'supplier': 'Example Supplier',
                'product': 'Potassium nitrate 13-0-46',
                'composition': 'single',
                'document': {
                    'supplier': 'Example Supplier',
                    'title': 'TDS-1',
                    'issued': '2026-01-15',
                    'entered': '2026-10-31',
                },
                'analysis': {'N_NO3': {'typical': 13.0}, 'K': {'typical': 38.2}},
            }
        )
        self.assertEqual(grade.flags, ())
        self.assertAlmostEqual(grade.charge_residual_percent, 2.57, places=2)


class MixAddsTheProductWithItsNoteTests(unittest.TestCase):
    def test_potassium_nitrate_label_is_added_with_the_note(self):
        answers = iter(
            [
                'potassium nitrate',
                'Potassium nitrate 13-0-46',
                'Example Supplier',
                '2026-01-15',
                'TDS-1',
                '',
                '',
                '',
            ]
        )
        lines = []
        added = add_single(
            Prompts(lambda prompt: next(answers), lines.append), load_library()['salts']
        )
        self.assertEqual(added['elements'], {'N_NO3': 13.0, 'K': 38.2})
        self.assertIn('Added Potassium nitrate 13-0-46 as Potassium Nitrate.', lines)
        self.assertIn('label analysis differs from KNO₃: 1.91 % K not assigned to an ion', lines)

    def test_a_label_matching_its_compound_is_added_without_a_note(self):
        answers = iter(
            [
                'potassium nitrate',
                'Pure KNO3',
                'Example Supplier',
                '2026-01-15',
                'TDS-1',
                repr(THEORY_N),
                repr(THEORY_K),
                '',
            ]
        )
        lines = []
        add_single(Prompts(lambda prompt: next(answers), lines.append), load_library()['salts'])
        self.assertEqual(lines[-1], 'Added Pure KNO3 as Potassium Nitrate.')


class MaterialRecordsTests(unittest.TestCase):
    def test_a_material_off_its_ions_resolves_and_converts_balanced(self):
        record = {'name': 'KNO3 label', 'formula': 'KNO3', 'elements': LABEL}
        self.assertEqual(dict(material_chemistry(record).ions), {'K+': 1, 'NO3-': 1})
        converted = convert_material_dose(record, 1.0)
        self.assertAlmostEqual(converted.totals['K'], converted.totals['nitrate'], delta=1e-15)

    def test_a_nutrient_the_ions_do_not_carry_is_still_refused(self):
        with self.assertRaises(DeliveryError) as caught:
            material_chemistry(
                {'name': 'KNO3 with P', 'formula': 'KNO3', 'elements': {**LABEL, 'P': 1.0}}
            )
        self.assertEqual(caught.exception.code, 'identity_inconsistent')


if __name__ == '__main__':
    unittest.main()
