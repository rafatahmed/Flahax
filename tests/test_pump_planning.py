import unittest
from datetime import datetime, timezone
from flahax import DeliveryError, VolumeLitres
from flahax.pump_planning import plan_pump_command
def calibration(): return {"schemaVersion":"0.1","id":"pump-1","source":"bench","revision":"1","recordedAt":"2026-09-25T12:00:00+03:00","channelId":"A","stockDensityKgPerL":1.1,"testTemperatureC":22,"flowLitresPerMinute":.12,"standardDeviationLitresPerMinute":.002,"validMinLitres":.02,"validMaxLitres":2}
class PumpPlanningTests(unittest.TestCase):
 def test_volume_runtime_and_uncertainty(self):
  p=plan_pump_command(calibration(),VolumeLitres(.12),VolumeLitres(1),.01)
  self.assertAlmostEqual(p.runtime.value,1); self.assertGreater(p.volume_uncertainty.value,0); self.assertTrue(p.requires_operator_verification)
 def test_rejects_dry_tank_and_outside_calibration(self):
  with self.assertRaises(DeliveryError) as c: plan_pump_command(calibration(),VolumeLitres(.01),VolumeLitres(1))
  self.assertEqual(c.exception.code,"out_of_calibration_range")
  with self.assertRaises(DeliveryError) as c: plan_pump_command(calibration(),VolumeLitres(.12),VolumeLitres(.1))
  self.assertEqual(c.exception.code,"dry_tank_risk")
 def test_rejects_stale_calibration(self):
  with self.assertRaises(DeliveryError) as c: plan_pump_command(calibration(),VolumeLitres(.12),VolumeLitres(1),as_of=datetime(2026,11,1,tzinfo=timezone.utc))
  self.assertEqual(c.exception.code,"stale_calibration")
 def test_rejects_zero_stock_density(self):
  item=calibration(); item["stockDensityKgPerL"]=0
  with self.assertRaises(DeliveryError) as c: plan_pump_command(item,VolumeLitres(.12),VolumeLitres(1))
  self.assertEqual(c.exception.code,"out_of_range")
