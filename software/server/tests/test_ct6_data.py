"""Unit tests for ct6/ct6_data.py (the backend independent ct6_dash2 logic).

   Run from the software/server folder:  python3 -m pytest tests/test_ct6_data.py"""
import os
import sys
import unittest
from datetime import date, datetime, timedelta

# Use the server packages (lib, ct6) rather than tests/lib.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ct6 import ct6_data as cd  # noqa: E402
from ct6.ct6_data import PlotType, PowerType, Resolution  # noqa: E402

TS = cd.TIMESTAMP


def rows_every(start, step_s, watts_list, column="CT1_ACT_WATTS"):
    return [{TS: start + timedelta(seconds=i * step_s), column: w} for i, w in enumerate(watts_list)]


class TestPresets(unittest.TestCase):
    NOW = datetime(2026, 11, 20, 14, 30)   # A Friday

    def check(self, preset, start, stop, res):
        r = cd.preset_range(preset, self.NOW)
        self.assertEqual((r.start_date, r.start_time, r.stop_date, r.stop_time, r.resolution),
                         (start, "00:00", stop, "23:59", res))

    def test_presets(self):
        self.check("Today", date(2026, 11, 20), date(2026, 11, 20), Resolution.MIN)
        self.check("Yesterday", date(2026, 11, 19), date(2026, 11, 19), Resolution.MIN)
        self.check("This week", date(2026, 11, 16), date(2026, 11, 22), Resolution.MIN)
        self.check("Last week", date(2026, 11, 9), date(2026, 11, 15), Resolution.MIN)
        self.check("This month", date(2026, 11, 1), date(2026, 11, 30), Resolution.HOUR)
        self.check("Last month", date(2026, 10, 1), date(2026, 10, 31), Resolution.HOUR)
        self.check("This year", date(2026, 1, 1), date(2026, 12, 31), Resolution.HOUR)
        self.check("Last year", date(2025, 1, 1), date(2025, 12, 31), Resolution.HOUR)

    def test_last_month_in_january_and_leap_february(self):
        r = cd.preset_range("Last month", datetime(2026, 1, 15))
        self.assertEqual((r.start_date, r.stop_date), (date(2025, 12, 1), date(2025, 12, 31)))
        r = cd.preset_range("This month", datetime(2028, 2, 3))
        self.assertEqual(r.stop_date, date(2028, 2, 29))

    def test_unknown(self):
        with self.assertRaises(ValueError):
            cd.preset_range("Next week")


class TestParseStartStop(unittest.TestCase):

    def test_ok(self):
        start, stop = cd.parse_start_stop("2026-11-20", "00:00", date(2026, 11, 20), "23:59")
        self.assertEqual(start, datetime(2026, 11, 20, 0, 0))
        self.assertEqual(stop, datetime(2026, 11, 20, 23, 59, 59, 999999))

    def test_bad_values(self):
        for args in [("2026-13-01", "00:00", "2026-11-20", "23:59"),
                     ("2026-11-20", "25:00", "2026-11-20", "23:59"),
                     ("", "00:00", "2026-11-20", "23:59"),
                     ("2026-11-21", "00:00", "2026-11-20", "23:59")]:
            with self.assertRaises(ValueError):
                cd.parse_start_stop(*args)


class TestSeries(unittest.TestCase):
    START = datetime(2026, 11, 20, 10, 0)

    def test_power_kw_and_invert(self):
        rows = rows_every(self.START, 60, [1000.0, -500.0])
        self.assertEqual(cd.build_series(rows, "CT1_ACT_WATTS", Resolution.MIN),
                         [["2026-11-20 10:00:00", 1.0], ["2026-11-20 10:01:00", -0.5]])
        self.assertEqual([p[1] for p in cd.build_series(rows, "CT1_ACT_WATTS", Resolution.MIN, invert=True)],
                         [-1.0, 0.5])

    def test_hour_and_day_steps(self):
        rows = rows_every(self.START, 3600, [2000.0])
        self.assertEqual(cd.build_series(rows, "CT1_ACT_WATTS", Resolution.HOUR),
                         [["2026-11-20 10:00:00", 2.0], ["2026-11-20 10:59:59", 2.0]])
        rows = [{TS: datetime(2026, 11, 20), "CT1_ACT_WATTS": 2000.0}]
        self.assertEqual(cd.build_series(rows, "CT1_ACT_WATTS", Resolution.DAY)[1],
                         ["2026-11-20 23:59:59", 2.0])

    def test_non_power_and_missing(self):
        rows = [{TS: self.START, "VOLTAGE": 241.5}, {TS: self.START, "VOLTAGE": None}]
        self.assertEqual(cd.build_series(rows, "VOLTAGE", Resolution.MIN, invert=True, is_power=False),
                         [["2026-11-20 10:00:00", 241.5]])

    def test_downsample_keeps_peaks(self):
        pts = [[str(i), 0.0] for i in range(10000)]
        pts[1234][1] = 99.0
        pts[8765][1] = -99.0
        out = cd.downsample_minmax(pts, 100)
        self.assertLessEqual(len(out), 100)
        ys = [p[1] for p in out]
        self.assertIn(99.0, ys)
        self.assertIn(-99.0, ys)
        self.assertEqual([p[0] for p in out], sorted((p[0] for p in out), key=int))
        self.assertEqual(len(cd.downsample_minmax(pts[:50], 100)), 50)


class TestKWh(unittest.TestCase):
    START = datetime(2026, 11, 20, 0, 0)

    def test_constant_power(self):
        # 1 kW for 1 hour (61 one minute samples) = 1 kWh.
        rows = rows_every(self.START, 60, [1000.0] * 61)
        k = cd.calc_kwh(rows, "CT1_ACT_WATTS")
        self.assertAlmostEqual(k.total, 1.0)
        self.assertAlmostEqual(k.positive, 1.0)
        self.assertAlmostEqual(k.negative, 0.0)

    def test_mixed_and_invert(self):
        # The first sample has no elapsed time. Then +2 kW for 30 min and -1 kW for 30 min.
        rows = rows_every(self.START, 1800, [0.0, 2000.0, -1000.0])
        k = cd.calc_kwh(rows, "CT1_ACT_WATTS")
        self.assertAlmostEqual(k.total, 0.5)
        self.assertAlmostEqual(k.positive, 1.0)
        self.assertAlmostEqual(k.negative, -0.5)
        ki = cd.calc_kwh(rows, "CT1_ACT_WATTS", invert=True)
        self.assertAlmostEqual(ki.positive, 0.5)
        self.assertAlmostEqual(ki.negative, -1.0)

    def test_summary_row_columns_follow_power_direction(self):
        rows = rows_every(self.START, 1800, [0.0, 2000.0, -1000.0])
        normal = cd.summary_row(1, "Grid", cd.calc_kwh(rows, "CT1_ACT_WATTS"), invert=False)
        inverted = cd.summary_row(1, "Grid", cd.calc_kwh(rows, "CT1_ACT_WATTS", invert=True), invert=True)
        self.assertEqual(normal, {"ct": 1, "sensor": "Grid", "total": "0.50", "positive": "1.00", "negative": "-0.50"})
        self.assertEqual(inverted["total"], "-0.50")
        self.assertEqual((inverted["positive"], inverted["negative"]), ("-1.00", "0.50"))


class TestPeakDay(unittest.TestCase):

    def test_peak_and_incomplete(self):
        recs = [{"day": date(2026, 6, 1), "avg_w": 500.0, "sample_count": 24},
                {"day": date(2026, 6, 2), "avg_w": -900.0, "sample_count": 24},
                {"day": date(2026, 6, 3), "avg_w": 5000.0, "sample_count": 20},
                {"day": None, "avg_w": 1.0, "sample_count": 24}]
        r = cd.peak_daily_kwh(recs)
        self.assertEqual(r.peak_day, date(2026, 6, 2))
        self.assertAlmostEqual(r.peak_kwh, -21.6)
        self.assertEqual((r.total_days, r.incomplete_days), (3, 1))
        text = cd.peak_result_text("Solar", datetime(2026, 6, 1), datetime(2026, 6, 3), r)
        self.assertEqual(text, "Solar: Peak daily kWh = 21.60 kWh on 2026-06-02. "
                               "(1 of 3 day(s) ignored due to incomplete data)")

    def test_none(self):
        r = cd.peak_daily_kwh([])
        self.assertIsNone(r.peak_day)
        self.assertIn("No complete days", cd.peak_result_text("X", datetime(2026, 1, 1), datetime(2026, 1, 2), r))


class TestPlotTypesAndDevices(unittest.TestCase):

    def test_fields_and_labels(self):
        self.assertEqual(cd.ct_field(3, PlotType.POWER, PowerType.REACTIVE), "CT3_REACT_WATTS")
        self.assertEqual(cd.ct_field(6, PlotType.POWER_FACTOR), "CT6_PF")
        self.assertEqual(PlotType.POWER.y_axis_label(PowerType.APPARENT), "kVA")
        self.assertEqual(PlotType.AC_VOLTS.single_field, "VOLTAGE")
        self.assertEqual(Resolution.HOUR.table_name, "CT6_SENSOR_HOUR")

    def test_device_from_meta(self):
        meta = {"HW_ASSY": "ASY1", "CT1_NAME": "Grid", "CT2_NAME": "", "CT3_NAME": None,
                "CT4_NAME": "Solar", "CT5_NAME": "", "CT6_NAME": ""}
        d = cd.DeviceInfo.from_meta_row("HOUSE", "HOUSE", meta)
        self.assertEqual(d.active_cts(), [(1, "Grid"), (4, "Solar")])
        self.assertEqual(d.hw_assy, "ASY1")


if __name__ == "__main__":
    unittest.main()
