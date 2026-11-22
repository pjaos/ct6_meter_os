"""Unit tests for ct6_heatpump (the ct6_dash2 Heat pump tab logic)."""
import os
import sys
import tempfile
import unittest
from datetime import date, datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ct6 import ct6_heatpump as hp  # noqa: E402
from ct6 import ct6_tariff as tf  # noqa: E402


def rec(day, on_minutes, kwh, minutes=1440, peak=900.0):
    return {"day": day, "on_minutes": on_minutes, "minutes": minutes, "peak_w": peak, "kwh": kwh}


class TestHeatPump(unittest.TestCase):

    def setUp(self):
        self.settings = hp.HeatPumpSettings(ct_key="HOUSE:3", threshold_w=100, min_minutes=10)
        self.records = [rec(date(2025, 1, 10), 300, 4.0),     # heating day
                        rec(date(2025, 1, 11), 5, 0.3),       # below the minimum run-time
                        rec(date(2025, 7, 1), 120, 2.0),      # cooling day
                        rec(date(2025, 7, 2), 0, 0.1)]        # standby only

    def test_analyse(self):
        r = hp.analyse(self.records, self.settings)
        s = r.summary
        self.assertEqual((s["days_with_data"], s["on_days"], s["heating_days"], s["cooling_days"]), (4, 2, 1, 1))
        self.assertAlmostEqual(s["run_hours"], (300 + 5 + 120) / 60.0)
        self.assertAlmostEqual(s["heating_hours"], 5.0)
        self.assertAlmostEqual(s["cooling_hours"], 2.0)
        self.assertAlmostEqual(s["kwh"], 6.4)
        self.assertAlmostEqual(s["heating_kwh"], 4.0)
        self.assertAlmostEqual(s["cooling_kwh"], 2.0)
        self.assertEqual([d["mode"] for d in r.days], ["heating", "off", "cooling", "off"])
        self.assertEqual([(m["month"], m["on_days"], m["mode"]) for m in r.months],
                         [("2025-01", 1, "heating"), ("2025-07", 1, "cooling")])
        self.assertIn("2 on day(s) of 4 with data (heating 1 · cooling 1)", hp.summary_text(r))

    def test_cooling_months_setting(self):
        self.settings.cooling_months = [1]
        r = hp.analyse(self.records, self.settings)
        self.assertEqual((r.summary["heating_days"], r.summary["cooling_days"]), (1, 1))
        self.assertEqual(r.days[0]["mode"], "cooling")
        self.assertEqual(r.days[2]["mode"], "heating")

    def test_chart_data_fills_every_day(self):
        r = hp.analyse(self.records[:2], self.settings)
        c = hp.chart_data(r, datetime(2025, 1, 9), datetime(2025, 1, 12, 23, 59))
        self.assertEqual(c["labels"], ["2025-01-09", "2025-01-10", "2025-01-11", "2025-01-12"])
        self.assertEqual(c["heating"], [None, 5.0, None, None])
        self.assertEqual(c["off"], [None, None, 0.08, None])
        self.assertEqual(c["kwh"], [None, 4.0, 0.3, None])

    def test_csv_and_month_rows(self):
        r = hp.analyse(self.records, self.settings)
        lines = hp.to_csv(r).splitlines()
        self.assertEqual(lines[0], "date,on_minutes,peak_watts,samples,on,mode,kwh")
        self.assertEqual(lines[1], "2025-01-10,300.0,900.0,1440,True,heating,4.0")
        self.assertEqual(hp.month_table_rows(r)[0],
                         {"id": "2025-01", "month": "Jan 2025", "mode": "Heating", "data_days": 2,
                          "on_days": 1, "hours": "5.1", "kwh": "4.3"})
        self.assertEqual(hp.to_csv(hp.analyse([], self.settings)), "")
        self.assertEqual(hp.summary_text(hp.analyse([], self.settings)), "No heat pump data for the selected dates.")

    def test_validate(self):
        for bad in (hp.HeatPumpSettings(threshold_w=0), hp.HeatPumpSettings(min_minutes=0),
                    hp.HeatPumpSettings(cooling_months=[13])):
            with self.assertRaises(ValueError):
                bad.validate()

    def test_settings_saved_with_tariff(self):
        with tempfile.TemporaryDirectory() as folder:
            store = tf.SettingsStore(os.path.join(folder, "s.json"))
            s = store.load()
            self.assertEqual(s.heatpump, hp.HeatPumpSettings())
            s.heatpump = self.settings
            store.save(s)
            loaded = store.load()
            self.assertEqual(loaded.heatpump.ct_key, "HOUSE:3")
            self.assertEqual(loaded.heatpump.cooling_months, [5, 6, 7, 8, 9])
            # A version 3 file (no heatpump key) loads with the defaults.
            self.assertEqual(tf.Settings.from_dict({"version": 3}).heatpump, hp.HeatPumpSettings())


if __name__ == "__main__":
    unittest.main()
