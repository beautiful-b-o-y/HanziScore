import json
import tempfile
import unittest
from pathlib import Path

import app as app_module


class CaptureApiTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_paths = (
            app_module.DATA_DIR,
            app_module.SAMPLES_DIR,
            app_module.ANALYSES_DIR,
            app_module.AI_CACHE_PATH,
        )

        data_dir = Path(self.temp_dir.name) / "data"
        app_module.DATA_DIR = data_dir
        app_module.SAMPLES_DIR = data_dir / "samples"
        app_module.ANALYSES_DIR = data_dir / "analyses"
        app_module.AI_CACHE_PATH = data_dir / "ai_cache.json"

        self.client = app_module.create_app().test_client()

    def tearDown(self):
        (
            app_module.DATA_DIR,
            app_module.SAMPLES_DIR,
            app_module.ANALYSES_DIR,
            app_module.AI_CACHE_PATH,
        ) = self.old_paths
        self.temp_dir.cleanup()

    def test_capture_post_stores_sample_and_analysis_json(self):
        payload = {
            "version": 1,
            "targetCharacter": "永",
            "strokes": [
                {
                    "id": "stroke-1",
                    "pointerType": "mouse",
                    "points": [
                        {"x": 0, "y": 0, "t": 0, "pressure": 0.5},
                        {"x": 3, "y": 4, "t": 100, "pressure": 0.5},
                    ],
                }
            ],
        }

        response = self.client.post("/api/captures", json=payload)
        result = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(result["stored"])
        self.assertEqual(result["metrics"]["strokeCount"], 1)
        self.assertEqual(result["metrics"]["pointCount"], 2)
        self.assertEqual(result["metrics"]["pathLengthPx"], 5)

        sample_path = app_module.SAMPLES_DIR / f"{result['recordId']}.json"
        analysis_path = app_module.ANALYSES_DIR / f"{result['recordId']}.json"
        self.assertTrue(sample_path.exists())
        self.assertTrue(analysis_path.exists())

        sample = json.loads(sample_path.read_text(encoding="utf-8"))
        analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
        self.assertEqual(sample["payload"]["targetCharacter"], "永")
        self.assertEqual(analysis["metrics"]["pathLengthPx"], 5)

        list_response = self.client.get("/api/records")
        records = list_response.get_json()["records"]
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(records[0]["id"], result["recordId"])
        self.assertEqual(records[0]["strokeCount"], 1)

        detail_response = self.client.get(f"/api/records/{result['recordId']}")
        detail = detail_response.get_json()
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail["id"], result["recordId"])
        self.assertEqual(detail["sample"]["payload"]["targetCharacter"], "永")
        self.assertEqual(detail["analysis"]["metrics"]["pointCount"], 2)

    def test_record_detail_rejects_invalid_record_id(self):
        response = self.client.get("/api/records/not-a-record")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Invalid record id.")


if __name__ == "__main__":
    unittest.main()
