"""
Tests for Value Tuning dashboard UI helper functions and gate history delta calculations.
"""

import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
from src.rag.learning_dashboard import (
    _build_gate_history_rows,
    _format_gate_history_rows,
    _delta_style
)


class TestLearningDashboardValueTuning(unittest.TestCase):
    def test_delta_style(self):
        """Test that _delta_style returns the correct CSS color code based on arrows."""
        self.assertEqual(_delta_style(None), "")
        self.assertEqual(_delta_style(123), "")
        self.assertIn("#e8f5e9", _delta_style("↑ +0.250"))  # Green for up
        self.assertIn("#ffebee", _delta_style("↓ -0.150"))  # Red for down
        self.assertIn("#f5f5f5", _delta_style("→ +0.00"))   # Gray for no change
        self.assertEqual(_delta_style("1.000"), "")

    def test_build_gate_history_rows_no_deltas(self):
        """Test _build_gate_history_rows with a single log entry (no delta possible)."""
        logs = [
            {
                "timestamp": "2026-06-01T12:00:00",
                "status": "ok",
                "source": "human_only",
                "summary": {
                    "total_entries": 10,
                    "csat_mean": 1.25,
                    "nps_mean": 1.0,
                    "adoption_rate": 1.15
                },
                "reasons": []
            }
        ]
        rows = _build_gate_history_rows(logs)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "ok")
        self.assertEqual(rows[0]["source"], "human_only")
        self.assertEqual(rows[0]["csat"], 1.25)
        self.assertEqual(rows[0]["nps"], 1.0)
        self.assertEqual(rows[0]["adoption"], 1.15)
        self.assertEqual(rows[0]["reasons"], "")

    def test_build_gate_history_rows_with_deltas(self):
        """Test _build_gate_history_rows with multiple logs to verify delta calculations."""
        # Chronological order: index 2 is oldest, index 0 is newest
        logs = [
            {
                "timestamp": "2026-06-01T14:00:00",
                "status": "ok",
                "source": "human_ai_blended",
                "summary": {
                    "total_entries": 15,
                    "csat_mean": 1.30,      # csat: 1.25 -> 1.30 (+0.05)
                    "nps_mean": 0.95,       # nps: 1.00 -> 0.95 (-0.05)
                    "adoption_rate": 1.15   # adoption: 1.15 -> 1.15 (no change)
                },
                "reasons": []
            },
            {
                "timestamp": "2026-06-01T13:00:00",
                "status": "ok",
                "source": "human_only",
                "summary": {
                    "total_entries": 10,
                    "csat_mean": 1.25,
                    "nps_mean": 1.00,
                    "adoption_rate": 1.15
                },
                "reasons": []
            },
            {
                "timestamp": "2026-06-01T12:00:00",
                "status": "skipped",
                "source": "human_only",
                "summary": {},
                "reasons": ["insufficient_entries"]
            }
        ]
        
        rows = _build_gate_history_rows(logs)
        self.assertEqual(len(rows), 3)
        
        # Test index 0 (latest log, compared to index 1)
        self.assertEqual(rows[0]["status"], "ok")
        self.assertEqual(rows[0]["source"], "human_ai_blended")
        self.assertEqual(rows[0]["csat"], 1.30)
        self.assertAlmostEqual(rows[0]["Δcsat"], 0.05)
        self.assertEqual(rows[0]["nps"], 0.95)
        self.assertAlmostEqual(rows[0]["Δnps"], -0.05)
        self.assertEqual(rows[0]["adoption"], 1.15)
        self.assertAlmostEqual(rows[0]["Δadoption"], 0.0)
        
        # Test index 1 (compared to index 2 which has no weights)
        self.assertEqual(rows[1]["status"], "ok")
        self.assertEqual(rows[1]["source"], "human_only")
        self.assertEqual(rows[1]["csat"], 1.25)
        self.assertIsNone(rows[1]["Δcsat"])
        
        # Test index 2 (oldest log, no previous log to compare to)
        self.assertEqual(rows[2]["status"], "skipped")
        self.assertEqual(rows[2]["reasons"], "insufficient_entries")

    def test_format_gate_history_rows(self):
        """Test that _format_gate_history_rows returns a styled or unstyled pandas object safely."""
        rows = [
            {
                "timestamp": "2026-06-01T14:00:00",
                "status": "ok",
                "source": "human_ai_blended",
                "reasons": "",
                "entries": 15,
                "csat": 1.30,
                "nps": 0.95,
                "adoption": 1.15,
                "Δentries": 5,
                "Δcsat": 0.05,
                "Δnps": -0.05,
                "Δadoption": 0.0
            }
        ]
        formatted = _format_gate_history_rows(rows)
        self.assertTrue(isinstance(formatted, pd.DataFrame))
        self.assertEqual(formatted.iloc[0]["csat"], "1.30")
        self.assertEqual(formatted.iloc[0]["Δcsat"], "↑ +0.05")
        self.assertEqual(formatted.iloc[0]["Δnps"], "↓ -0.05")
        self.assertEqual(formatted.iloc[0]["Δadoption"], "→ +0.00")


if __name__ == "__main__":
    unittest.main()
