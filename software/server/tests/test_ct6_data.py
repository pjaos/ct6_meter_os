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


class TestGaps(unittest.TestCase):

    def rows(self, minutes):
        t0 = datetime(2026, 11, 20)
        return [{cd.TIMESTAMP: t0 + timedelta(minutes=m), "CT1_ACT_WATTS": 1000.0} for m in minutes]

    def test_threshold(self):
        rows = self.rows(range(0, 60))                       # 1 min data
        self.assertEqual(cd.gap_threshold(rows, Resolution.MIN), 300)
        rows = self.rows([0, 10, 20, 30, 40])                # 10 min data: 5 x median wins
        self.assertEqual(cd.gap_threshold(rows, Resolution.MIN), 3000)
        self.assertEqual(cd.gap_threshold(self.rows([0]), Resolution.SEC), 60)

    def test_build_series_breaks(self):
        rows = self.rows([0, 1, 2, 30, 31])                  # 28 min gap
        pts = cd.build_series(rows, "CT1_ACT_WATTS", Resolution.MIN, gap_secs=300)
        self.assertEqual(len(pts), 6)
        self.assertIsNone(pts[3][1])
        self.assertEqual(pts[3][0], "2026-11-20 00:16:00")    # Middle of the gap
        self.assertEqual(cd.count_gaps(rows, 300), 1)
        # No breaks without gap_secs (as before).
        self.assertEqual(len(cd.build_series(rows, "CT1_ACT_WATTS", Resolution.MIN)), 5)

    def test_hour_steps_and_breaks(self):
        t0 = datetime(2026, 11, 20)
        rows = [{cd.TIMESTAMP: t0 + timedelta(hours=h), "CT1_ACT_WATTS": 500.0} for h in (0, 1, 2, 10)]
        pts = cd.build_series(rows, "CT1_ACT_WATTS", Resolution.HOUR, gap_secs=3 * 3600)
        xs = [p[0] for p in pts]
        self.assertEqual(xs, sorted(xs))                     # The marker stays in time order
        self.assertEqual([p[1] for p in pts].count(None), 1)

    def test_downsample_keeps_markers(self):
        pts = [[f"x{i:04d}", float(i % 7)] for i in range(1000)]
        pts.insert(500, ["x0499b", None])
        out = cd.downsample_minmax(pts, 100)
        self.assertIn(["x0499b", None], out)
        self.assertLessEqual(len(out), 101)

    def test_format_duration(self):
        self.assertEqual([cd.format_duration(s) for s in (30, 300, 10800, 259200)],
                         ["30 s", "5 min", "3 h", "3 days"])


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


class TestEnergy(unittest.TestCase):

    def test_choose_bucket_and_labels(self):
        s = datetime(2026, 1, 1)
        self.assertEqual(cd.choose_bucket(cd.EnergyBucket.AUTO, s, s + timedelta(days=61)), cd.EnergyBucket.DAY)
        self.assertEqual(cd.choose_bucket(cd.EnergyBucket.AUTO, s, s + timedelta(days=62)), cd.EnergyBucket.MONTH)
        self.assertEqual(cd.choose_bucket(cd.EnergyBucket.DAY, s, s + timedelta(days=365)), cd.EnergyBucket.DAY)
        self.assertEqual(cd.period_label(date(2026, 11, 1), cd.EnergyBucket.MONTH), "Nov 2026")
        self.assertEqual(cd.period_label(date(2026, 11, 20), cd.EnergyBucket.DAY), "2026-11-20")

    def test_bars_and_totals_match_kwh_table_conventions(self):
        dev = cd.DeviceInfo("HOUSE", "HOUSE", ("Grid", "", "", "", "", ""))
        recs = [{"period": date(2026, 11, 19), "CT1_ACT_WATTS_pos": 3.0, "CT1_ACT_WATTS_neg": -1.0},
                {"period": date(2026, 11, 20), "CT1_ACT_WATTS_pos": 1.0, "CT1_ACT_WATTS_neg": -4.0}]
        labels, bars, totals = cd.build_energy_bars(recs, dev, cd.EnergyBucket.DAY)
        self.assertEqual(labels, ["2026-11-19", "2026-11-20"])
        self.assertEqual((bars[0]["pos"], bars[0]["neg"]), ([3.0, 1.0], [-1.0, -4.0]))
        self.assertEqual(cd.summary_row(1, "Grid", totals[1]),
                         {"ct": 1, "sensor": "Grid", "total": "-1.00", "positive": "4.00", "negative": "-5.00"})
        # Inverted: bars flip sign, and the summary row matches what calc_kwh(invert=True) would give.
        _, bars_i, totals_i = cd.build_energy_bars(recs, dev, cd.EnergyBucket.DAY, invert=True)
        self.assertEqual((bars_i[0]["pos"], bars_i[0]["neg"]), ([1.0, 4.0], [-3.0, -1.0]))
        rows = [{TS: datetime(2026, 1, 1, 0, 0), "CT1_ACT_WATTS": 0.0},
                {TS: datetime(2026, 1, 1, 1, 0), "CT1_ACT_WATTS": 4000.0},
                {TS: datetime(2026, 1, 1, 2, 0), "CT1_ACT_WATTS": -5000.0}]
        ref = cd.calc_kwh(rows, "CT1_ACT_WATTS", invert=True)
        got = cd.energy_kwh(4.0, -5.0, invert=True)
        self.assertEqual((got.total, got.positive, got.negative), (ref.total, ref.positive, ref.negative))


class TestCSV(unittest.TestCase):
    DEV = cd.DeviceInfo("HOUSE", "HOUSE", ("Grid", "", "", "", "", ""))

    def test_rows_to_csv_keeps_stored_values_and_names_cts(self):
        rows = [{TS: datetime(2026, 11, 20, 10, 0), "CT1_ACT_WATTS": -512.5, "CT2_ACT_WATTS": 0.0, "VOLTAGE": 241.2}]
        text = cd.rows_to_csv(rows, self.DEV)
        self.assertEqual(text.splitlines(), ["TIMESTAMP,CT1_ACT_WATTS (Grid),CT2_ACT_WATTS,VOLTAGE",
                                             "2026-11-20 10:00:00,-512.5,0.0,241.2"])
        self.assertEqual(cd.rows_to_csv([], self.DEV), "")

    def test_energy_csv(self):
        recs = [{"period": date(2026, 11, 1), "CT1_ACT_WATTS_pos": 3.0, "CT1_ACT_WATTS_neg": -1.25}]
        lines = cd.energy_to_csv(recs, self.DEV, cd.EnergyBucket.MONTH).splitlines()
        self.assertEqual(lines, ["PERIOD,CT1_ACT_WATTS_POS_KWH (Grid),CT1_ACT_WATTS_NEG_KWH (Grid),CT1_ACT_WATTS_NET_KWH (Grid)",
                                 "2026-11,3.0000,-1.2500,1.7500"])

    def test_filename(self):
        self.assertEqual(cd.csv_filename("MY DEV", datetime(2026, 11, 20), datetime(2026, 11, 20, 23, 59), "Min"),
                         "MY_DEV_20261120-0000_20261120-2359_Min.csv")


class TestLive(unittest.TestCase):

    def test_status_and_age(self):
        self.assertEqual([cd.live_status(a) for a in (None, 0, 9.9, 10, 59, 60)],
                         ["offline", "ok", "ok", "stale", "stale", "offline"])
        self.assertEqual([cd.format_age(a) for a in (None, 3.7, 125, 7300, 86400, 200000)],
                         ["no data", "3 s ago", "2 min ago", "2 h ago", "1 day ago", "2 days ago"])

    def test_merge_trims_to_window(self):
        now = datetime(2026, 11, 20, 12, 0)
        old = [{TS: now - timedelta(minutes=m)} for m in (20, 16, 14)]
        new = [{TS: now - timedelta(seconds=1)}]
        merged = cd.merge_live_rows(old, new, now)
        self.assertEqual([r[TS] for r in merged], [now - timedelta(minutes=14), now - timedelta(seconds=1)])

    def test_live_columns(self):
        d = cd.DeviceInfo("HOUSE", "HOUSE", ("Grid", "", "Solar", "", "", ""))
        self.assertEqual(cd.live_columns(d), [TS, "CT1_ACT_WATTS", "CT3_ACT_WATTS",
                                              "VOLTAGE", "FREQUENCY", "BOARD_TEMPERATURE", "RSSI_DBM"])


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
