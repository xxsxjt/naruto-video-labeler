import unittest

import numpy as np

from naruto_video_analyzer.analysis import TimelineAnalyzer
from naruto_video_analyzer.regions import parse_regions


class TimelineAnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.regions = parse_regions({
            "arena": [0, 0, 1, 1], "joystick": [0, 0, 0.25, 0.25],
            "attack": [0.75, 0.75, 0.25, 0.25], "skill_1": [0.5, 0.5, 0.2, 0.2],
            "impact_area": [0.25, 0.25, 0.5, 0.5], "self_health": [0, 0, 0.2, 0.05], "enemy_health": [0.8, 0, 0.2, 0.05],
        })

    def test_detects_button_motion(self):
        analyzer = TimelineAnalyzer(self.regions, visual_change_threshold=10)
        first = np.zeros((100, 100, 3), dtype=np.uint8)
        second = first.copy()
        second[75:100, 75:100] = 255
        analyzer.process(0.0, first)
        analyzer.process(0.1, second)
        analyzer.process(0.2, first)
        events = analyzer.process(0.6, first)
        self.assertIn("attack_visual_change", [event.event for event in events])

    def test_merges_sustained_visual_change_into_one_segment(self):
        analyzer = TimelineAnalyzer(self.regions, visual_change_threshold=10, merge_gap_s=0.2)
        first = np.zeros((100, 100, 3), dtype=np.uint8)
        bright = first.copy()
        bright[75:100, 75:100] = 255
        analyzer.process(0.0, first)
        analyzer.process(0.1, bright)
        analyzer.process(0.2, first)
        events = analyzer.process(0.5, first)
        attack_events = [event for event in events if event.event == "attack_visual_change"]
        self.assertEqual(1, len(attack_events))
        self.assertEqual(2.0, attack_events[0].evidence["observations"])

    def test_detects_blue_ring_candidate(self):
        analyzer = TimelineAnalyzer(self.regions)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[40:50, 40:50] = [20, 100, 240]
        events = analyzer.process(0.0, frame)
        self.assertIn("blue_ring_state", [event.event for event in events])
