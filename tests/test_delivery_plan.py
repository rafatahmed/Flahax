import unittest
from flahax import DeliveryError, VolumeLitres
from flahax.delivery_plan import compose_delivery_plan, delivery_report, transition_plan
from flahax.delivery_quantities import final_solution_recipe, InjectionRatio, TemperatureCelsius
from flahax.pump_planning import plan_pump_command
from flahax.stock_planning import StockTank, plan_stocks
from flahax.ph_planning import plan_ph
from tests.test_ph_planning import inputs
from tests.test_pump_planning import calibration

class DeliveryPlanTests(unittest.TestCase):
 def make_plan(self):
  recipe=final_solution_recipe({"feasible":True,"salts":[{"id":"a","name":"A","gramsPerLitre":.1}]},VolumeLitres(10))
  stocks=plan_stocks(recipe,InjectionRatio(100),[StockTank("A",VolumeLitres(1))],[],[{"schemaVersion":"0.1","id":"l","source":"s","revision":"1","recordedAt":"2026-01-01T00:00:00Z","productId":"a","maxGramsPerLitre":20,"temperatureMinC":0,"temperatureMaxC":30}],TemperatureCelsius(20))
  command=plan_pump_command(calibration(),VolumeLitres(.1),VolumeLitres(1))
  return compose_delivery_plan(recipe,stocks,None,[command],{"modelVersion":"test"})
 def test_state_machine_blocks_partial_validation(self):
  plan=self.make_plan()
  with self.assertRaises(DeliveryError): transition_plan(plan,"validated")
 def test_report_and_matching_recipe(self):
  plan=self.make_plan(); self.assertIn("draft",delivery_report(plan))
 def test_complete_plan_transitions_to_verified(self):
  recipe=final_solution_recipe({"feasible":True,"salts":[{"id":"a","name":"A","gramsPerLitre":.1}]},VolumeLitres(100))
  stocks=plan_stocks(recipe,InjectionRatio(100),[StockTank("A",VolumeLitres(2))],[],[{"schemaVersion":"0.1","id":"l","source":"s","revision":"1","recordedAt":"2026-01-01T00:00:00Z","productId":"a","maxGramsPerLitre":20,"temperatureMinC":0,"temperatureMaxC":30}],TemperatureCelsius(20))
  water, curve, reagent=inputs()
  ph_plan=plan_ph(water,curve,reagent,6.7,VolumeLitres(100),VolumeLitres(1),{"N_NO3":100},{"N_NO3":111.592})
  command=plan_pump_command(calibration(),VolumeLitres(1),stocks.tanks[0].stock_volume)
  plan=compose_delivery_plan(recipe,stocks,ph_plan,[command],{"modelVersion":"0.2.0","waterAnalysisId":water["id"]})
  for state in ("validated","operator-approved","executed","verified"): plan=transition_plan(plan,state)
  self.assertEqual(plan.state,"verified")
  self.assertIn("post-mix measurement required",delivery_report(plan))
