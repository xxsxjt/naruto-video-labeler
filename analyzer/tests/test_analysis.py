import unittest

import numpy as np

from naruto_video_analyzer.analysis import TimelineAnalyzer
from naruto_video_analyzer.coach import build_coaching_report
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

    def test_urashiki_coach_turns_visual_candidates_into_review_advice(self):
        report = {"video": {"filename": "sample.mp4"}, "character_id": "urashiki_astro_fisher", "character_assignment": "human_confirmed", "events": [
            {"timestamp_s": 0.0, "event": "red_ring_state", "source": "arena", "score": 0.8},
            {"timestamp_s": 1.0, "event": "skill_1_visual_change", "source": "skill_1", "score": 55},
            {"timestamp_s": 1.3, "event": "attack_visual_change", "source": "attack", "score": 44},
            {"timestamp_s": 1.4, "event": "impact_or_damage_flash", "source": "impact_area", "score": 60},
            {"timestamp_s": 2.0, "event": "health_bar_change", "source": "enemy_health", "score": 22},
        ]}
        coaching = build_coaching_report(report)
        self.assertEqual("offline_tactical_coach", coaching["mode"])
        self.assertGreaterEqual(coaching["recommendation_count"], 4)
        advice = " ".join(item["advice"] for item in coaching["recommendations"])
        self.assertIn("下拉摇杆", advice)
        self.assertIn("血条", advice)

    def test_kakashi_coach_distinguishes_invulnerability_and_special_attacks(self):
        report = {"video": {"filename": "sample.mp4"}, "character_id": "kakashi_susanoo", "character_assignment": "human_confirmed", "events": [
            {"timestamp_s": 0.0, "event": "red_ring_state", "source": "arena", "score": 0.8},
            {"timestamp_s": 0.7, "event": "attack_visual_change", "source": "attack", "score": 44},
            {"timestamp_s": 1.2, "event": "skill_2_visual_change", "source": "skill_2", "score": 60},
            {"timestamp_s": 1.8, "event": "impact_or_damage_flash", "source": "impact_area", "score": 70},
            {"timestamp_s": 2.5, "event": "health_bar_change", "source": "enemy_health", "score": 24},
        ]}
        coaching = build_coaching_report(report, character="kakashi_susanoo")
        self.assertEqual("kakashi_susanoo", coaching["character"]["id"])
        advice = " ".join(item["advice"] for item in coaching["recommendations"])
        self.assertIn("虚化", advice)
        self.assertIn("奥义", advice)

    def test_unconfirmed_character_cannot_generate_coaching_report(self):
        with self.assertRaises(ValueError):
            build_coaching_report({"events": []}, character="urashiki_astro_fisher")
