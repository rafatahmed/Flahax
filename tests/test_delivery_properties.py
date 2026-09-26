import unittest
from flahax import VolumeLitres
from flahax.delivery_quantities import final_solution_recipe, InjectionRatio, TemperatureCelsius
from flahax.stock_planning import StockTank, plan_stocks

class DeliveryProperties(unittest.TestCase):
 def test_stock_planning_is_deterministic_and_conserves_recipe_volume(self):
  recipe=final_solution_recipe({"feasible":True,"salts":[{"id":"a","name":"A","gramsPerLitre":.1},{"id":"b","name":"B","gramsPerLitre":.2}]},VolumeLitres(20))
  limits=[{"schemaVersion":"0.1","id":f"{i}-l","source":"s","revision":"1","recordedAt":"2026-01-01T00:00:00Z","productId":i,"maxGramsPerLitre":30,"temperatureMinC":0,"temperatureMaxC":30} for i in ("a","b")]
  args=(recipe,InjectionRatio(100),[StockTank("A",VolumeLitres(1)),StockTank("B",VolumeLitres(1))],[],limits,TemperatureCelsius(20))
  first=plan_stocks(*args); second=plan_stocks(*args)
  self.assertEqual(first,second)
  self.assertTrue(all(t.stock_volume.value==.2 for t in first.tanks))
