"""Unit tests for ct6/ct6_tariff.py (ct6_dash2 cost estimates).

   Run from the software/server folder:  python3 -m pytest tests/test_ct6_tariff.py"""
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, time, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ct6 import ct6_tariff as ct  # noqa: E402
from ct6.ct6_tariff import RatePeriod, Tariff, CTRef, SiteRoles, Settings  # noqa: E402


def iog(standing=50.0):
    return Tariff(rates=[RatePeriod(date(2026, 1, 1), peak=28.0, offpeak=7.0, export=15.0, standing=standing)])


def slot(dt, pos=0.0, neg=0.0):
    return {"slot": dt, "pos_kwh": pos, "neg_kwh": neg}


class TestTariff(unittest.TestCase):

    def test_offpeak_window_crossing_midnight(self):
        t = Tariff()
        self.assertTrue(t.is_offpeak(time(23, 30)))
        self.assertTrue(t.is_offpeak(time(0, 0)))
        self.assertTrue(t.is_offpeak(time(5, 0)))
        self.assertFalse(t.is_offpeak(time(5, 30)))
        self.assertFalse(t.is_offpeak(time(23, 0)))
        self.assertFalse(t.is_offpeak(time(12, 0)))

    def test_offpeak_window_same_day(self):
        t = Tariff(offpeak_start="00:30", offpeak_end="05:30")
        self.assertFalse(t.is_offpeak(time(0, 0)))
        self.assertTrue(t.is_offpeak(datetime(2026, 1, 1, 0, 30)))
        self.assertFalse(t.is_offpeak(time(5, 30)))

    def test_rate_for(self):
        t = Tariff(rates=[RatePeriod(date(2026, 4, 1), 25, 7, 15), RatePeriod(date(2026, 1, 1), 28, 8, 15)])
        self.assertIsNone(t.rate_for(date(2025, 12, 31)))
        self.assertEqual(t.rate_for(date(2026, 3, 31)).peak, 28)
        self.assertEqual(t.rate_for(date(2026, 4, 1)).peak, 25)

    def test_validate(self):
        for bad in [Tariff(offpeak_start="23:15"), Tariff(offpeak_start="05:30"), Tariff(offpeak_end="x"),
                    Tariff(rates=[RatePeriod(date(2026, 1, 1), 1, 1, 1)] * 2),
                    Tariff(rates=[RatePeriod(date(2026, 1, 1), -1, 1, 1)])]:
            with self.assertRaises(ValueError):
                bad.validate()
        iog().validate()


class TestCost(unittest.TestCase):
    DAY = datetime(2026, 6, 10)

    def test_import_export_peak_offpeak(self):
        # CT6 default: import is negative.
        slots = [slot(self.DAY.replace(hour=0), neg=-2.0),                # 2 kWh off-peak
                 slot(self.DAY.replace(hour=12), pos=3.0, neg=-1.0),      # 1 kWh peak import, 3 kWh export
                 slot(self.DAY.replace(hour=23, minute=30), neg=-1.0)]    # 1 kWh off-peak
        r = ct.calc_cost(slots, iog(), self.DAY, self.DAY.replace(hour=23, minute=59), now=datetime(2026, 7, 1))
        self.assertAlmostEqual(r.import_offpeak_kwh, 3.0)
        self.assertAlmostEqual(r.import_peak_kwh, 1.0)
        self.assertAlmostEqual(r.export_kwh, 3.0)
        self.assertAlmostEqual(r.import_p, 3 * 7 + 28)
        self.assertAlmostEqual(r.export_p, 45)
        self.assertEqual(r.standing_days, 1)
        self.assertAlmostEqual(r.net_p, 49 + 50 - 45)
        self.assertEqual(ct.pounds(r.net_p), "£0.54")

    def test_import_positive_orientation(self):
        slots = [slot(self.DAY.replace(hour=12), pos=1.0, neg=-2.0)]
        r = ct.calc_cost(slots, iog(0), self.DAY, self.DAY, now=self.DAY, import_negative=False)
        self.assertAlmostEqual((r.import_peak_kwh, r.export_kwh), (1.0, 2.0))

    def test_standing_charge_not_added_for_future_days_or_before_rates(self):
        start = datetime(2025, 12, 30)
        stop = datetime(2026, 1, 31, 23, 59)
        r = ct.calc_cost([], iog(), start, stop, now=datetime(2026, 1, 10, 9, 0))
        self.assertEqual(r.standing_days, 10)    # 1-10 Jan only
        self.assertAlmostEqual(r.standing_p, 500)

    def test_unpriced_and_rate_change(self):
        t = Tariff(rates=[RatePeriod(date(2026, 6, 11), 30, 10, 20)])
        slots = [slot(self.DAY.replace(hour=12), neg=-1.0), slot(self.DAY.replace(day=11, hour=12), neg=-1.0)]
        r = ct.calc_cost(slots, t, self.DAY, self.DAY + timedelta(days=1), now=datetime(2026, 7, 1))
        self.assertEqual(r.unpriced_slots, 1)
        self.assertEqual((r.priced_days, r.unpriced_days), (1, 1))
        # kWh and £ cover the same (costed) days only.
        self.assertAlmostEqual(r.import_peak_kwh, 1.0)
        self.assertAlmostEqual(r.import_peak_p, 30)
        self.assertEqual(ct.uncosted_warning(r, t), "⚠ Only 1 of 2 days costed (no rate before 11 Jun 2026)")
        r0 = ct.calc_cost(slots[:1], t, self.DAY, self.DAY, now=datetime(2026, 7, 1))
        self.assertEqual(ct.uncosted_warning(r0, t), "⚠ No days costed (no rate before 11 Jun 2026)")
        self.assertIsNone(ct.uncosted_warning(ct.calc_cost(slots[1:], t, self.DAY, self.DAY, now=self.DAY), t))

    def test_ev_not_counted_before_first_rate(self):
        t = Tariff(rates=[RatePeriod(date(2026, 6, 11), 30, 10, 20)])
        ev = [slot(self.DAY.replace(hour=14), neg=-2.0), slot(self.DAY.replace(day=11, hour=14), neg=-3.0)]
        r = ct.calc_cost([], t, self.DAY, self.DAY + timedelta(days=1), now=datetime(2026, 7, 1), ev_slots=ev)
        self.assertAlmostEqual((r.ev.peak_kwh, r.ev.cost_p), (3.0, 90))

    def test_ev(self):
        ev = [slot(self.DAY.replace(hour=1), neg=-7.0), slot(self.DAY.replace(hour=14), neg=-2.0)]
        r = ct.calc_cost([], iog(0), self.DAY, self.DAY, now=self.DAY, ev_slots=ev)
        self.assertAlmostEqual((r.ev.offpeak_kwh, r.ev.peak_kwh, r.ev.cost_p), (7.0, 2.0, 49 + 56))
        self.assertIn("Zappi £1.05", ct.cost_summary_text(r, "Zappi"))
        self.assertEqual(ct.cost_table_rows(r, "Zappi")[-1]["kwh"], "2.00 / 7.00")


class TestSettings(unittest.TestCase):

    def test_round_trip_grid_and_ev_on_different_devices(self):
        roles = SiteRoles(grid=CTRef("HOUSE", 1), ev=CTRef("GARAGE", 1), grid_import_negative=False)
        s = Settings(iog(), roles)
        with tempfile.TemporaryDirectory() as d:
            store = ct.SettingsStore(os.path.join(d, "sub", "s.json"))
            self.assertEqual(store.load().roles, SiteRoles())
            store.save(s)
            loaded = store.load()
        self.assertEqual(loaded.tariff.rates, s.tariff.rates)
        self.assertEqual(loaded.roles, roles)

    def test_version1_per_device_settings_converted(self):
        v1 = {"version": 1, "tariff": {"rates": []},
              "devices": {"GARAGE": {"grid_ct": None, "ev_ct": 2, "grid_import_negative": True},
                          "HOUSE": {"grid_ct": 1, "ev_ct": None, "grid_import_negative": False}}}
        r = Settings.from_dict(v1).roles
        self.assertEqual((r.grid, r.ev, r.grid_import_negative), (CTRef("HOUSE", 1), CTRef("GARAGE", 2), False))

    def test_ctref_key(self):
        self.assertEqual(CTRef.from_key(CTRef("MY:DEV", 3).key()), CTRef("MY:DEV", 3))
        self.assertIsNone(CTRef.from_key(""))

    def test_save_rejects_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                ct.SettingsStore(os.path.join(d, "s.json")).save(Settings(Tariff(offpeak_start="bad")))


if __name__ == "__main__":
    unittest.main()


class TestIOGEVSlots(unittest.TestCase):
    """The Intelligent Octopus Go rule: EV charging outside the off-peak window marks an off-peak slot."""
    DAY = datetime(2026, 11, 20)
    HOUSE = 0.2         # House load kWh per half-hour
    EV = 3.65           # 7.3 kW for half an hour

    def tariff(self, **kw):
        t = iog(standing=0)
        t.ev_slots_offpeak = True
        for k, v in kw.items():
            setattr(t, k, v)
        return t

    def charge(self, start, halfhours, ev=None, grid_extra=None):
        """Grid (import negative) and EV half-hours for a charge starting at 'start'."""
        ev = self.EV if ev is None else ev
        grid, evs = [], []
        for i in range(halfhours):
            t = start + timedelta(minutes=30 * i)
            imp = ev + self.HOUSE if grid_extra is None else grid_extra
            grid.append(slot(t, neg=-imp))
            evs.append(slot(t, neg=-ev))
        return grid, evs

    def cost(self, grid, evs, t):
        return ct.calc_cost(grid, t, self.DAY, self.DAY, now=self.DAY, ev_slots=evs)

    def test_charge_running_past_0530_is_all_offpeak(self):
        # 03:00-06:30: 7 half-hours, the last two outside 23:30-05:30.
        grid, evs = self.charge(self.DAY.replace(hour=3), 7)
        off = self.cost(grid, evs, iog(standing=0))
        self.assertAlmostEqual(off.import_peak_kwh, 2 * (self.EV + self.HOUSE))          # rule off: peak
        on = self.cost(grid, evs, self.tariff())
        self.assertAlmostEqual(on.import_peak_kwh, 0.0)
        self.assertAlmostEqual(on.import_offpeak_kwh, 7 * (self.EV + self.HOUSE))
        self.assertAlmostEqual(on.ev.peak_kwh, 0.0)
        self.assertAlmostEqual(on.ev.offpeak_kwh, 7 * self.EV)
        self.assertEqual(on.ev_slot_halfhours, 2)

    def test_daytime_slot_makes_whole_house_offpeak(self):
        grid, evs = self.charge(self.DAY.replace(hour=14), 1)
        grid.append(slot(self.DAY.replace(hour=15), neg=-1.0))      # no charging: stays peak
        r = self.cost(grid, evs, self.tariff())
        self.assertAlmostEqual(r.import_offpeak_kwh, self.EV + self.HOUSE)
        self.assertAlmostEqual(r.import_peak_kwh, 1.0)
        self.assertAlmostEqual(r.import_offpeak_p, (self.EV + self.HOUSE) * 7.0)

    def test_solar_charging_is_not_a_slot(self):
        # EV uses 2 kWh but only 0.2 kWh comes from the grid (< 50%).
        grid, evs = self.charge(self.DAY.replace(hour=13), 1, ev=2.0, grid_extra=0.2)
        r = self.cost(grid, evs, self.tariff())
        self.assertEqual(r.ev_slot_halfhours, 0)
        self.assertAlmostEqual(r.import_peak_kwh, 0.2)
        self.assertAlmostEqual(r.ev.peak_kwh, 2.0)
        r0 = self.cost(grid, evs, self.tariff(ev_slot_min_grid_share=0.0))    # check switched off
        self.assertEqual(r0.ev_slot_halfhours, 1)

    def test_tiny_ev_draw_is_not_a_slot(self):
        grid, evs = self.charge(self.DAY.replace(hour=13), 1, ev=0.05)
        self.assertEqual(self.cost(grid, evs, self.tariff()).ev_slot_halfhours, 0)
        self.assertEqual(self.cost(grid, evs, self.tariff(ev_slot_min_kwh=0.05)).ev_slot_halfhours, 1)

    def test_daily_cap_outside_window(self):
        # 23:30-06:30 = 14 charging half-hours in one charging day: the last 2 are over the 6 h cap.
        start = self.DAY.replace(hour=23, minute=30) - timedelta(days=1)
        grid, evs = self.charge(start, 14)
        r = ct.calc_cost(grid, self.tariff(), start, start + timedelta(hours=8), now=self.DAY, ev_slots=evs)
        self.assertEqual((r.ev_slot_halfhours, r.ev_over_cap_halfhours), (0, 2))
        self.assertAlmostEqual(r.import_peak_kwh, 2 * (self.EV + self.HOUSE))
        self.assertAlmostEqual(r.ev.peak_kwh, 2 * self.EV)

    def test_daily_cap_inside_window_costs_only_ev_at_peak(self):
        # 22:00-05:30 = 15 half-hours: 3 slots before 23:30 use the allowance first,
        # so the last 3 (04:00-05:30, inside the window) are over the cap.
        start = self.DAY.replace(hour=22) - timedelta(days=1)
        grid, evs = self.charge(start, 15)
        r = ct.calc_cost(grid, self.tariff(), start, start + timedelta(hours=8), now=self.DAY, ev_slots=evs)
        self.assertEqual((r.ev_slot_halfhours, r.ev_over_cap_halfhours), (3, 3))
        self.assertAlmostEqual(r.import_peak_kwh, 3 * self.EV)                 # EV part only
        self.assertAlmostEqual(r.import_offpeak_kwh, 15 * (self.EV + self.HOUSE) - 3 * self.EV)
        r0 = ct.calc_cost(grid, self.tariff(ev_daily_cap_hours=0), start, start + timedelta(hours=8),
                          now=self.DAY, ev_slots=evs)
        self.assertAlmostEqual(r0.import_peak_kwh, 0.0)                         # cap off

    def test_cap_resets_at_midday(self):
        # 12 half-hours ending at 12:00 and 2 starting at 12:00 are in different charging days.
        grid, evs = self.charge(self.DAY.replace(hour=6), 14)
        r = self.cost(grid, evs, self.tariff())
        self.assertEqual(r.ev_over_cap_halfhours, 0)
        self.assertEqual(r.ev_slot_halfhours, 14)

    def test_rule_needs_ev_data(self):
        grid, _ = self.charge(self.DAY.replace(hour=14), 1)
        r = ct.calc_cost(grid, self.tariff(), self.DAY, self.DAY, now=self.DAY)
        self.assertFalse(r.ev_rule)
        self.assertAlmostEqual(r.import_peak_kwh, self.EV + self.HOUSE)

    def test_table_rows_and_caveat(self):
        grid, evs = self.charge(self.DAY.replace(hour=14), 1)
        rows = ct.cost_table_rows(self.cost(grid, evs, self.tariff()), "ZAPPI")
        self.assertEqual(rows[-1]["item"], "EV slots costed off-peak (half-hours)")
        self.assertEqual(rows[-1]["kwh"], "1")
        self.assertIn("Intelligent Octopus Go", ct.cost_caveat(self.tariff()))
        self.assertIn("Only 23:30-05:30 is off-peak", ct.cost_caveat(iog()))

    def test_settings_round_trip_and_old_files(self):
        t = self.tariff(ev_slot_min_kwh=0.2, ev_slot_min_grid_share=0.25, ev_daily_cap_hours=5.5)
        with tempfile.TemporaryDirectory() as d:
            store = ct.SettingsStore(os.path.join(d, "s.json"))
            store.save(Settings(t, SiteRoles(grid=CTRef("HOUSE", 1), ev=CTRef("GARAGE", 1))))
            lt = store.load().tariff
        self.assertEqual((lt.ev_slots_offpeak, lt.ev_slot_min_kwh, lt.ev_slot_min_grid_share, lt.ev_daily_cap_hours),
                         (True, 0.2, 0.25, 5.5))
        old = Settings.from_dict({"version": 2, "tariff": {"rates": []}, "roles": {}}).tariff
        self.assertEqual((old.ev_slots_offpeak, old.ev_slot_min_kwh, old.ev_daily_cap_hours), (False, 0.1, 6.0))

    def test_validate_ev_settings(self):
        for bad in (dict(ev_slot_min_kwh=0), dict(ev_slot_min_grid_share=1.5), dict(ev_daily_cap_hours=-1),
                    dict(ev_daily_cap_hours=5.25)):
            with self.assertRaises(ValueError):
                self.tariff(**bad).validate()
        self.tariff().validate()
