"""Tests for HalfHourEnergyCache (no database needed)."""
import unittest
from datetime import date, datetime, timedelta

from ct6.ct6_data_source import HalfHourEnergyCache


class FakeSource:
    """Every half-hour holds 1 kWh import (pos) per slot; counts the queries made."""

    def __init__(self):
        self.calls = []

    def half_hour_energy(self, device_id, column, start_dt, stop_dt):
        self.calls.append((start_dt, stop_dt))
        t = start_dt.replace(minute=start_dt.minute - start_dt.minute % 30, second=0, microsecond=0)
        rows = []
        while t <= stop_dt:
            rows.append({"slot": t, "pos_kwh": 1.0, "neg_kwh": 0.0})
            t += timedelta(minutes=30)
        return rows


class TestHalfHourEnergyCache(unittest.TestCase):
    TODAY = date(2025, 6, 10)

    def test_past_days_read_once(self):
        cache, ds = HalfHourEnergyCache(), FakeSource()
        a, b = datetime(2025, 6, 1), datetime(2025, 6, 7, 23, 59, 59)
        first = cache.half_hour_energy(ds, "D", "C", a, b, today=self.TODAY)
        self.assertEqual(len(first), 7 * 48)
        second = cache.half_hour_energy(ds, "D", "C", a, b, today=self.TODAY)
        self.assertEqual(first, second)
        self.assertEqual(len(ds.calls), 1)

    def test_today_always_read(self):
        cache, ds = HalfHourEnergyCache(), FakeSource()
        a, b = datetime(2025, 6, 9), datetime(2025, 6, 10, 23, 59, 59)
        rows = cache.half_hour_energy(ds, "D", "C", a, b, today=self.TODAY)
        self.assertEqual(len(rows), 2 * 48)
        cache.half_hour_energy(ds, "D", "C", a, b, today=self.TODAY)
        # 1st call: yesterday + today. 2nd call: today only.
        self.assertEqual(len(ds.calls), 3)
        self.assertEqual(ds.calls[-1][0], datetime(2025, 6, 10))

    def test_only_missing_days_read(self):
        cache, ds = HalfHourEnergyCache(), FakeSource()
        cache.half_hour_energy(ds, "D", "C", datetime(2025, 6, 3), datetime(2025, 6, 4, 23, 59, 59), today=self.TODAY)
        cache.half_hour_energy(ds, "D", "C", datetime(2025, 6, 1), datetime(2025, 6, 2, 23, 59, 59), today=self.TODAY)
        rows = cache.half_hour_energy(ds, "D", "C", datetime(2025, 6, 1), datetime(2025, 6, 4, 23, 59, 59),
                                      today=self.TODAY)
        self.assertEqual(len(rows), 4 * 48)
        self.assertEqual(len(ds.calls), 2)

    def test_partial_day_range(self):
        cache, ds = HalfHourEnergyCache(), FakeSource()
        rows = cache.half_hour_energy(ds, "D", "C", datetime(2025, 6, 1, 10, 0), datetime(2025, 6, 1, 11, 59, 59),
                                      today=self.TODAY)
        self.assertEqual([r["slot"].strftime("%H:%M") for r in rows], ["10:00", "10:30", "11:00", "11:30"])

    def test_keys_separate(self):
        cache, ds = HalfHourEnergyCache(), FakeSource()
        a, b = datetime(2025, 6, 1), datetime(2025, 6, 1, 23, 59, 59)
        cache.half_hour_energy(ds, "D", "C1", a, b, today=self.TODAY)
        cache.half_hour_energy(ds, "D", "C2", a, b, today=self.TODAY)
        cache.half_hour_energy(ds, "E", "C1", a, b, today=self.TODAY)
        self.assertEqual(len(ds.calls), 3)


if __name__ == "__main__":
    unittest.main()
