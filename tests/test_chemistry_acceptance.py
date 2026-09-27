"""Acceptance invariants independent of the PHREEQC output comparator."""
import math
import unittest
from flahax import load_library, DeliveryError, FertilizerTotals, solve_mixed_fertilizer_equilibrium
from flahax.aqueous_model import chemistry, solve, nitric_target
from flahax.product_conversion import catalogue_dose_totals, convert_catalogue_product_dose, solve_catalogue_product_doses

class ChemistryAcceptanceTests(unittest.TestCase):
    def test_every_product_assay_survives_the_analytical_boundary(self):
        for product in load_library()['salts']:
            name=product['name']
            with self.subTest(product=name):
                converted=convert_catalogue_product_dose(product,.01)
                basis=catalogue_dose_totals({name:.01})
                self.assertTrue(basis)
                for key,amount in converted.totals.items():
                    mapping={'Ca':'Ca+2','Mg':'Mg+2','K':'K+','Na':'Na+','Fe':'Fe+2' if 'Iron II' in name else 'Fe+3',
                             'Mn':'Mn+2','Zn':'Zn+2','Cu':'Cu+2','phosphate':'PO4-3','sulfate':'SO4-2',
                             'boron':'H3BO3','molybdate':'MoO4-2','ammonium':'NH4+','nitrate':'NO3-','urea':'Ure'}
                    self.assertAlmostEqual(basis[mapping[key]],amount,places=15)
                result=solve_catalogue_product_doses({name:.01},6.,allow_precipitation=False).aqueous
                for b,v in result.residuals.items():
                    self.assertLess(abs(v),1e-9*result.totals[b]+1e-15)

    def test_urea_and_potassium_carbonate_stoichiometry(self):
        urea=catalogue_dose_totals({'Urea':1.})
        self.assertAlmostEqual(2*urea['Ure'],.46646/14.0067)
        carbonate=catalogue_dose_totals({'Potassium Carbonate':1.})
        self.assertEqual(carbonate['K+'],2*carbonate['CO3-2'])

    def test_no_extra_dtpa_or_eddha_metal_families(self):
        for r in chemistry()['aqueous']:
            if set(r['powers']) & {'Dtp-5','Edd-4'}:
                self.assertFalse(set(r['powers']) & {'Ca+2','Mg+2','Mn+2','Zn+2','Cu+2','Fe+2'})

    def test_simultaneous_ligands_are_order_independent(self):
        totals={'Fe+3':3e-5,'Edta-4':1e-5,'Dtp-5':1e-5,'Edd-4':1e-5,'Ca+2':.001,'NO3-':.002}
        a=solve(totals,6.)
        b=solve(dict(reversed(list(totals.items()))),6.)
        for key,value in a.species.items():
            self.assertAlmostEqual(value,b.species[key],delta=1e-12+abs(value)*1e-8)
        for r in chemistry()['aqueous']:
            if r['name'] in a.species and set(r['powers']) <= (set(totals)|{'H+','H2O'}):
                expected=r['beta']+sum(v*math.log10(a.activities[k]) for k,v in r['powers'].items())
                self.assertAlmostEqual(math.log10(a.activities[r['name']]),expected,places=9)

    def test_zero_dilute_domain_and_temperature_boundaries(self):
        self.assertGreater(solve({},7.).species['H+'],0)
        self.assertLess(solve({'Na+':1e-12,'Cl-':1e-12},7.).ionic_strength,1e-6)
        for args in ({'totals':{'Na+':.2,'Cl-':.2},'ph':6.},
                     {'totals':{'Na+':.2,'Cl-':.2},'ph':6.,'ionic_strength':.01},
                     {'totals':{},'ph':6.,'ionic_strength':.10001},
                     {'totals':{},'ph':6.,'temperature_c':30}):
            with self.assertRaises(DeliveryError):
                solve(**args)

    def test_phase_complementarity_and_element_conservation(self):
        totals={'Ca+2':.001,'Mg+2':.001,'PO4-3':.001,'CO3-2':.001,'SO4-2':.001,
                'Fe+3':2e-5,'Zn+2':1e-5,'Cu+2':1e-5,'Mn+2':1e-5,'Na+':.005,'Cl-':.005}
        phases=[r['name'] for r in chemistry()['phases']]
        result=solve(totals,8.,phases=phases)
        self.assertTrue(result.precipitated)
        for p,si in result.saturation_indices.items():
            self.assertLessEqual(si,1e-7,p)
            if result.precipitated.get(p,0)>1e-12:
                self.assertAlmostEqual(si,0.,places=7,msg=p)
        for b,v in result.residuals.items():
            self.assertLess(abs(v),1e-9*totals[b]+1e-15,b)

    def test_macro_entry_point_honours_precipitation_flag(self):
        totals=FertilizerTotals(calcium=.001,carbonate=.002,sodium=.002)
        without=solve_mixed_fertilizer_equilibrium(totals,9.,allow_precipitation=False)
        with_phases=solve_mixed_fertilizer_equilibrium(totals,9.,allow_precipitation=True)
        self.assertGreater(without.macro.saturation_indices['Calcite'],0)
        self.assertFalse(without.macro.phase_allocations)
        self.assertGreater(with_phases.aqueous.precipitated['Calcite'],0)

    def test_nitric_plan_preserves_nitrate_and_protonation_demand(self):
        totals={'CO3-2':.001,'Na+':.002,'Cl-':.001,'H3BO3':1e-4,'Dtp-5':1e-5,'Fe+3':1e-5}
        result=nitric_target(totals,7.4,6.)
        self.assertGreater(result.nitric_acid_molal,0)
        self.assertAlmostEqual(result.target.totals['NO3-'],result.nitric_acid_molal,places=14)
        self.assertAlmostEqual(result.initial.charge_balance,result.target.charge_balance,places=12)
        self.assertEqual(result.target.totals['Dtp-5'],totals['Dtp-5'])
        self.assertTrue(result.post_mix_measurement_required)
        with self.assertRaises(DeliveryError):
            nitric_target(totals,6.,7.)
