import math
import unittest

from app import PAUSE_THRESHOLD_MS, calculate_metrics
from analysis import build_analysis


class MetricsTest(unittest.TestCase):
    def test_calculate_metrics_counts_length_speed_and_pauses(self):
        strokes = [
            {
                "id": "stroke-1",
                "pointerType": "mouse",
                "points": [
                    {"x": 0, "y": 0, "t": 0, "pressure": 0.5},
                    {"x": 3, "y": 4, "t": 100, "pressure": 0.5},
                ],
            },
            {
                "id": "stroke-2",
                "pointerType": "mouse",
                "points": [
                    {"x": 3, "y": 4, "t": PAUSE_THRESHOLD_MS + 100, "pressure": 0.5},
                    {"x": 6, "y": 8, "t": PAUSE_THRESHOLD_MS + 200, "pressure": 0.5},
                ],
            },
        ]

        metrics = calculate_metrics(strokes)

        self.assertEqual(metrics["strokeCount"], 2)
        self.assertEqual(metrics["pointCount"], 4)
        self.assertEqual(metrics["durationMs"], PAUSE_THRESHOLD_MS + 200)
        self.assertEqual(metrics["pathLengthPx"], 10)
        self.assertTrue(
            math.isclose(
                metrics["averageSpeedPxPerSecond"],
                10 / ((PAUSE_THRESHOLD_MS + 200) / 1000),
                abs_tol=0.01,
            )
        )
        self.assertEqual(metrics["pauseCount"], 1)
        self.assertEqual(metrics["pauses"][0]["durationMs"], PAUSE_THRESHOLD_MS)

    def test_build_analysis_adds_stroke_events_without_losing_raw_points(self):
        strokes = [
            {
                "id": "stroke-1",
                "pointerType": "mouse",
                "points": [
                    {"x": 0, "y": 0, "t": 0, "pressure": 0.5},
                    {"x": 80, "y": 0, "t": 100, "pressure": 0.5},
                    {"x": 80, "y": 80, "t": 200, "pressure": 0.5},
                    {"x": 82, "y": 82, "t": 1500, "pressure": 0.5},
                ],
            }
        ]

        analysis = build_analysis(strokes, PAUSE_THRESHOLD_MS)
        stroke_event = analysis["strokes"][0]

        self.assertEqual(stroke_event["raw_points"], strokes[0]["points"])
        self.assertIn("normalized_points", stroke_event["geometry"])
        self.assertIn("resampled_points", stroke_event["geometry"])
        self.assertEqual(stroke_event["geometry"]["bbox"]["width"], 82)
        self.assertGreater(stroke_event["geometry"]["path_length"], 160)
        self.assertGreaterEqual(len(stroke_event["geometry"]["turning_points"]), 1)
        self.assertIn("speed_profile", stroke_event["dynamics"])
        self.assertIn("acceleration_profile", stroke_event["dynamics"])
        self.assertIn("mean_speed", stroke_event["dynamics"])
        self.assertIn("max_speed", stroke_event["dynamics"])
        self.assertIn("speed_variance", stroke_event["dynamics"])
        self.assertTrue(any(segment["type"] == "turn" for segment in stroke_event["segments"]))
        self.assertEqual(
            stroke_event["visual_proxy"]["width_profile_source"],
            "simulated_from_speed",
        )
        self.assertTrue(
            any(event["type"] == "sharp_turn" for event in analysis["event_summary"]["data_events"])
        )


if __name__ == "__main__":
    unittest.main()
