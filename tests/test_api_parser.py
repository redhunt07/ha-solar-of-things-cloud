"""Offline parser regressions using a sanitized real telemetry fixture."""

from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _pkg  # noqa: F401
from solar_of_things_cloud import api

FIXTURE = Path(__file__).parent / "fixtures" / "state.json"


class ParserTests(unittest.TestCase):
    """The parser must reject unusable samples instead of inventing zeros."""

    def setUp(self) -> None:
        self.payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.stamp = datetime.fromisoformat(
            self.payload["data"]["time"].replace("Z", "+00:00")
        )

    def parse(self, payload, **kwargs):
        return api.parse_state(payload, now=self.stamp, **kwargs)

    def test_real_fixture(self) -> None:
        result = self.parse(self.payload)
        self.assertEqual(result["values"]["batteryVoltage"], 26.4)
        self.assertEqual(result["values"]["pvGeneratedEnergyOfTotal"], 1282.3)
        self.assertEqual(len(result["values"]), 18)
        self.assertEqual(result["time"], self.stamp)

    def test_numeric_value(self) -> None:
        payload = self.single(26.4)
        self.assertEqual(self.parse(payload)["values"], {"batteryVoltage": 26.4})

    def test_unit_mismatch_is_skipped(self) -> None:
        self.assertEqual(self.parse(self.single(26.4, unit="mV"))["values"], {})

    def test_hidden_field_is_skipped(self) -> None:
        self.assertEqual(self.parse(self.single(26.4, isHidden=True))["values"], {})

    def test_non_numeric_values_are_skipped(self) -> None:
        for value in (None, True, "26.4", float("nan"), float("inf")):
            with self.subTest(value=value):
                self.assertEqual(self.parse(self.single(value))["values"], {})

    def test_missing_fields(self) -> None:
        payload = self.single(26.4)
        payload["data"]["fields"] = {}
        self.assertEqual(self.parse(payload)["values"], {})

    def test_stale_sample_is_rejected(self) -> None:
        with self.assertRaises(api.ApiError):
            api.parse_state(self.payload, now=self.stamp + timedelta(hours=1))

    def test_future_sample_is_rejected(self) -> None:
        with self.assertRaises(api.ApiError):
            api.parse_state(self.payload, now=self.stamp - timedelta(hours=1))

    def test_small_clock_skew_is_tolerated(self) -> None:
        result = api.parse_state(self.payload, now=self.stamp + timedelta(seconds=60))
        self.assertEqual(len(result["values"]), 18)

    def test_bad_timestamps_are_rejected(self) -> None:
        for value in (None, "bad", "2026-10-22T22:48:22", 123):
            with self.subTest(value=value):
                payload = self.single(26.4)
                payload["data"]["time"] = value
                with self.assertRaises(api.ApiError):
                    self.parse(payload)

    def test_unsuccessful_payloads_are_rejected(self) -> None:
        for payload in (None, {}, {"code": 70001}, {"code": 0, "data": None}):
            with self.subTest(payload=payload), self.assertRaises(api.ApiError):
                self.parse(payload)

    def test_device_id_validation(self) -> None:
        with self.assertRaises(ValueError):
            api.SolarApi(None, "1&other=1")
        api.SolarApi(None, "123456789")

    def single(self, value, **field):
        return {
            "code": 0,
            "data": {
                "time": self.payload["data"]["time"],
                "fields": {
                    "batteryVoltage": {
                        "unit": "V",
                        "value": value,
                        "isHidden": None,
                        **field,
                    }
                },
            },
        }


if __name__ == "__main__":
    unittest.main()
