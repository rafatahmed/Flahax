import unittest
from flahax.struvite_mixture import solve_charge_balanced_struvite_mixture, struvite_mixture_speciation
class StruviteMixtureTests(unittest.TestCase):
 def test_phreeqc_probe_direction(self):
  r=struvite_mixture_speciation(.001,.001,.001,.001,8.5,.005168)
  self.assertAlmostEqual(r.ammonium_molal,.0008575,places=5); self.assertLess(r.struvite_si,0); self.assertAlmostEqual(r.struvite_si,-.30,places=1)
 def test_reduced_system_solves_charge_balance(self):
  r=solve_charge_balanced_struvite_mixture(.001,.001,.001,.001,.003)
  self.assertAlmostEqual(r.charge_residual,0,places=9); self.assertGreaterEqual(r.ph,0); self.assertLessEqual(r.ph,14)
