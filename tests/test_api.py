import json
import os
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
        self.old_zhipu_api_key = os.environ.pop("ZHIPU_API_KEY", None)

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
        if self.old_zhipu_api_key is not None:
            os.environ["ZHIPU_API_KEY"] = self.old_zhipu_api_key
        else:
            os.environ.pop("ZHIPU_API_KEY", None)
        self.temp_dir.cleanup()

    def test_capture_post_stores_sample_and_analysis_json(self):
        payload = {
            "version": 1,
            "targetCharacter": "永",
            "strokes": [
                {
                    "id": "stroke-1",
                    "pointerType": "mouse",
                    "brushSize": 9,
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
        self.assertEqual(sample["payload"]["strokes"][0]["brushSize"], 9)
        self.assertEqual(analysis["metrics"]["pathLengthPx"], 5)
        self.assertEqual(analysis["strokes"][0]["id"], "stroke-1")
        self.assertIn("raw_points", analysis["strokes"][0])
        self.assertIn("geometry", analysis["strokes"][0])
        self.assertIn("dynamics", analysis["strokes"][0])
        self.assertIn("segments", analysis["strokes"][0])
        self.assertIn("visual_proxy", analysis["strokes"][0])
        self.assertIn("labels", analysis["strokes"][0])
        self.assertEqual(
            analysis["strokes"][0]["visual_proxy"]["width_profile_source"],
            "simulated_from_speed",
        )

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
        self.assertIn("event_summary", detail["analysis"])

    def test_record_detail_rejects_invalid_record_id(self):
        response = self.client.get("/api/records/not-a-record")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Invalid record id.")

    def test_explanation_returns_source_and_uses_cache(self):
        payload = {
            "version": 1,
            "targetCharacter": "",
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
        capture_response = self.client.post("/api/captures", json=payload)
        record_id = capture_response.get_json()["recordId"]

        first_response = self.client.get(f"/api/records/{record_id}/explanation")
        first = first_response.get_json()

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(first["source"], "local_rules")
        self.assertEqual(first["sourceLabel"], "本地规则")
        self.assertIn("text", first)
        self.assertIn("这次书写", first["text"])
        self.assertIn("不是汉字识别", first["text"])

        second_response = self.client.get(f"/api/records/{record_id}/explanation")
        second = second_response.get_json()

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second["source"], "cache")
        self.assertEqual(second["sourceLabel"], "本地 cache")
        self.assertEqual(second["cachedSource"], "local_rules")

    def test_explanation_prompt_uses_metrics_not_raw_points(self):
        analysis = {
            "targetCharacter": "永",
            "metrics": {
                "strokeCount": 1,
                "pointCount": 2,
                "durationMs": 100,
                "durationSeconds": 0.1,
                "pathLengthPx": 5,
                "averageSpeedPxPerSecond": 50,
                "pauseThresholdMs": 700,
                "pauseCount": 0,
                "pauses": [],
            },
        }

        prompt = app_module.build_explanation_prompt(analysis)

        self.assertIn("strokeCount", prompt)
        self.assertIn("pathLengthPx", prompt)
        self.assertIn("candidate_labels", prompt)
        self.assertIn("observation_questions", prompt)
        self.assertIn("请使用中文解释", prompt)
        self.assertNotIn("targetCharacter", prompt)
        self.assertNotIn("strokes", prompt)
        self.assertNotIn("points", prompt)

    def test_local_explanation_uses_research_protocol_fields(self):
        analysis = {
            "metrics": {
                "strokeCount": 1,
                "pointCount": 4,
                "durationMs": 1500,
                "durationSeconds": 1.5,
                "pathLengthPx": 162,
                "averageSpeedPxPerSecond": 108,
                "pauseThresholdMs": 700,
                "pauseCount": 1,
                "pauses": [],
            },
            "strokes": [
                {
                    "id": "stroke-1",
                    "index": 1,
                    "geometry": {
                        "path_length": 162,
                        "turning_points": [{"pointIndex": 1}],
                    },
                    "dynamics": {
                        "duration_ms": 1500,
                        "mean_speed": 108,
                        "max_speed": 800,
                        "speed_variance": 20000,
                        "pause_before_ms": 0,
                        "pause_after_ms": 900,
                    },
                    "labels": [
                        {
                            "type": "sharp_turn",
                            "value": 90,
                            "threshold": 65,
                            "unit": "deg",
                        }
                    ],
                }
            ],
            "event_summary": {
                "data_events": [
                    {
                        "strokeIndex": 1,
                        "strokeId": "stroke-1",
                        "type": "sharp_turn",
                        "value": 90,
                        "threshold": 65,
                        "unit": "deg",
                    }
                ]
            },
        }

        text, explanation_json = app_module.generate_local_explanation(analysis)

        self.assertIn("evidence", explanation_json)
        self.assertIn("candidate_labels", explanation_json)
        self.assertIn("observation_questions", explanation_json)
        self.assertIn("uncertainty", explanation_json)
        self.assertTrue(explanation_json["candidate_labels"][0]["label"].startswith("\u5019\u9009\uff1a"))
        self.assertIn("转折", explanation_json["candidate_labels"][0]["evidence"])
        self.assertIn("\u5019\u9009\u6807\u6ce8", text)

    def test_zhipu_request_uses_chat_messages_and_metrics_only(self):
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return json.dumps(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": json.dumps(
                                        {
                                            "summary": "summary",
                                            "rhythm": "rhythm",
                                            "pauses": "pauses",
                                            "caution": "caution",
                                        }
                                    )
                                }
                            }
                        ]
                    }
                ).encode("utf-8")

        def fake_urlopen(request, timeout):
            captured["timeout"] = timeout
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["headers"] = dict(request.header_items())
            return FakeResponse()

        old_urlopen = app_module.urllib.request.urlopen
        os.environ["ZHIPU_API_KEY"] = "test-key"
        app_module.urllib.request.urlopen = fake_urlopen
        try:
            text, explanation_json, error = app_module.generate_zhipu_explanation(
                {
                    "metrics": {
                        "strokeCount": 1,
                        "pointCount": 2,
                        "durationMs": 100,
                        "durationSeconds": 0.1,
                        "pathLengthPx": 5,
                        "averageSpeedPxPerSecond": 50,
                        "pauseThresholdMs": 700,
                        "pauseCount": 0,
                        "pauses": [],
                    }
                }
            )
        finally:
            app_module.urllib.request.urlopen = old_urlopen

        self.assertIsNone(error)
        self.assertIn("summary", text)
        self.assertEqual(explanation_json["rhythm"], "rhythm")
        self.assertEqual(captured["timeout"], app_module.ZHIPU_TIMEOUT_SECONDS)
        self.assertEqual(captured["body"]["model"], app_module.ZHIPU_MODEL)
        self.assertFalse(captured["body"]["stream"])
        self.assertEqual(captured["body"]["response_format"]["type"], "json_object")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(captured["headers"]["User-agent"], "HanziScore/0.1")
        user_message = captured["body"]["messages"][1]["content"]
        self.assertIn("strokeCount", user_message)
        self.assertNotIn("strokes", user_message)
        self.assertNotIn("points", user_message)

    def test_zhipu_request_retries_connection_failures(self):
        attempts = {"count": 0}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return json.dumps(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": json.dumps(
                                        {
                                            "summary": "summary",
                                            "rhythm": "rhythm",
                                            "pauses": "pauses",
                                            "caution": "caution",
                                        }
                                    )
                                }
                            }
                        ]
                    }
                ).encode("utf-8")

        def fake_urlopen(request, timeout):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise ConnectionResetError("Remote end closed connection without response")
            return FakeResponse()

        old_urlopen = app_module.urllib.request.urlopen
        old_sleep = app_module.time.sleep
        os.environ["ZHIPU_API_KEY"] = "test-key"
        app_module.urllib.request.urlopen = fake_urlopen
        app_module.time.sleep = lambda _seconds: None
        try:
            text, explanation_json, error = app_module.generate_zhipu_explanation(
                {
                    "metrics": {
                        "strokeCount": 1,
                        "pointCount": 2,
                        "durationMs": 100,
                        "durationSeconds": 0.1,
                        "pathLengthPx": 5,
                        "averageSpeedPxPerSecond": 50,
                        "pauseThresholdMs": 700,
                        "pauseCount": 0,
                        "pauses": [],
                    }
                }
            )
        finally:
            app_module.urllib.request.urlopen = old_urlopen
            app_module.time.sleep = old_sleep

        self.assertIsNone(error)
        self.assertIn("summary", text)
        self.assertEqual(explanation_json["summary"], "summary")
        self.assertEqual(attempts["count"], 2)

    def test_format_explanation_json_falls_back_to_nested_text(self):
        text = app_module.format_explanation_json(
            {
                "analysis": {
                    "overview": "nested summary",
                    "detail": ["nested rhythm", "nested pause"],
                }
            }
        )

        self.assertIn("nested summary", text)
        self.assertIn("nested rhythm", text)
        self.assertIn("nested pause", text)


if __name__ == "__main__":
    unittest.main()
