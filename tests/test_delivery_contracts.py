import copy
import unittest

from flahax import DeliveryError, make_audit_record, validate_delivery_request


def record(record_id, **fields):
    return {
        "schemaVersion": "0.1",
        "id": record_id,
        "source": "bench-validation",
        "revision": "1",
        "recordedAt": "2026-09-25T12:00:00+03:00",
        **fields,
    }


def request():
    return {
        "schemaVersion": "0.1",
        "mode": "batch",
        "waterAnalysis": record(
            "water-wc1",
            ions={"Ca": 20},
            temperatureC=22,
            pH=7.4,
            alkalinityMgLAsCaCO3=120,
        ),
        "products": [
            record(
                "calcium-nitrate",
                name="Calcium nitrate",
                kind="fertilizer",
                elements={"N_NO3": 15.5, "Ca": 19.0},
            )
        ],
        "compatibilityRules": [
            record(
                "ca-separate-phosphate",
                productIds=["calcium-nitrate", "phosphoric-acid"],
                constraint="separate",
                reason="Concentrated calcium and phosphate may precipitate.",
                temperatureMinC=10,
                temperatureMaxC=30,
            )
        ],
        "solubilityLimits": [
            record(
                "calcium-nitrate-limit",
                productId="calcium-nitrate",
                maxGramsPerLitre=500,
                temperatureMinC=10,
                temperatureMaxC=30,
            )
        ],
        "titrationCurves": [
            record(
                "wc1-nitric-acid",
                waterAnalysisId="water-wc1",
                reagentId="nitric-acid",
                points=[
                    {"demandMeqPerL": 0, "pH": 7.4},
                    {"demandMeqPerL": 1.2, "pH": 6.0},
                ],
            )
        ],
        "pumpCalibrations": [
            record(
                "pump-a-calibration",
                channelId="A",
                flowLitresPerMinute=0.12,
                standardDeviationLitresPerMinute=0.002,
                validMinLitres=0.02,
                validMaxLitres=20,
            )
        ],
    }


class DeliveryContracts(unittest.TestCase):
    def test_valid_batch_request_is_normalized(self):
        result = validate_delivery_request(request())
        self.assertEqual(result["mode"], "batch")
        self.assertEqual(result["waterAnalysis"]["ions"], {"Ca": 20.0})
        self.assertEqual(result["products"][0]["elements"]["Ca"], 19.0)
        self.assertEqual(result["titrationCurves"][0]["points"][1]["pH"], 6.0)

    def test_audit_record_is_deterministic_and_has_every_input_id(self):
        payload = request()
        first = make_audit_record(payload, model_version="delivery-contracts-0.1")
        second = make_audit_record(copy.deepcopy(payload), model_version="delivery-contracts-0.1")
        self.assertEqual(first, second)
        self.assertEqual(first["waterAnalysisId"], "water-wc1")
        self.assertEqual(first["productIds"], ["calcium-nitrate"])
        self.assertEqual(first["pumpCalibrationIds"], ["pump-a-calibration"])

    def test_unsupported_mode_is_rejected_before_any_planning(self):
        payload = request()
        payload["mode"] = "proportional"
        with self.assertRaises(DeliveryError) as caught:
            validate_delivery_request(payload)
        self.assertEqual(caught.exception.code, "unsupported_mode")

    def test_ambiguous_total_nitrogen_is_rejected(self):
        payload = request()
        payload["products"][0]["elements"] = {"N": 15}
        with self.assertRaises(DeliveryError) as caught:
            validate_delivery_request(payload)
        self.assertEqual(caught.exception.code, "ambiguous_unit")

    def test_incomplete_or_invalid_records_have_stable_errors(self):
        payload = request()
        del payload["waterAnalysis"]["temperatureC"]
        with self.assertRaises(DeliveryError) as caught:
            validate_delivery_request(payload)
        self.assertEqual(caught.exception.code, "missing_field")

        payload = request()
        payload["pumpCalibrations"][0]["validMaxLitres"] = 0.01
        with self.assertRaises(DeliveryError) as caught:
            validate_delivery_request(payload)
        self.assertEqual(caught.exception.code, "out_of_range")

    def test_titration_demand_requires_strict_order(self):
        payload = request()
        payload["titrationCurves"][0]["points"][1]["demandMeqPerL"] = 0
        with self.assertRaises(DeliveryError) as caught:
            validate_delivery_request(payload)
        self.assertEqual(caught.exception.code, "invalid_value")


if __name__ == "__main__":
    unittest.main()
