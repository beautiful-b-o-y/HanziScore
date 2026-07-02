import math
import unittest

from app import PAUSE_THRESHOLD_MS, calculate_metrics


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


if __name__ == "__main__":
    unittest.main()
