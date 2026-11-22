"""Unit tests for ct6_selfuse (solar and battery self-consumption figures)."""
import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ct6 import ct6_selfuse as su  # noqa: E402
from ct6 import ct6_tariff as tf  # noqa: E402

T0, T1, T2 = datetime(2025, 6, 1, 2), datetime(2025, 6, 1, 12), datetime(2025, 6, 1, 19)


def slot(t, pos=0.0, neg=0.0):
    return {"slot": t, "pos_kwh": pos, "neg_kwh": -neg}


class TestSelfUse(unittest.TestCase):
    """CT6 default signs: grid import negative, solar generation negative, battery charge positive."""

    def setUp(self):
        # 02:00 night: import 2.0 (house 0.5 + battery charge 1.5).
        # 12:00 midday: solar 3.0, house 1.0, battery charges 1.5, export 0.5.
        # 19:00 evening: house 1.2 from battery 1.0 + import 0.2.
        self.grid = [slot(T0, neg=2.0), slot(T1, pos=0.5), slot(T2, neg=0.2)]
        self.solar = [slot(T0, pos=0.01), slot(T1, neg=3.0)]
        self.battery = [slot(T0, pos=1.5), slot(T1, pos=1.5), slot(T2, neg=1.0)]

    def test_solar_and_battery(self):
        r = su.calc_self_use(self.grid, self.solar, self.battery)
        self.assertAlmostEqual(r.import_kwh, 2.2)
        self.assertAlmostEqual(r.export_kwh, 0.5)
        self.assertAlmostEqual(r.solar_kwh, 3.0)
        self.assertAlmostEqual(r.solar_reverse_kwh, 0.01)
        self.assertAlmostEqual(r.home_kwh, 0.5 + 1.0 + 1.2)   # Inverter standby is part of the home import
        self.assertAlmostEqual(r.solar_battery_kwh, 1.5)
        self.assertAlmostEqual(r.solar_home_kwh, 1.0)
        self.assertAlmostEqual(r.grid_battery_kwh, 1.5)
        self.assertAlmostEqual(r.charge_kwh, 3.0)
        self.assertAlmostEqual(r.discharge_kwh, 1.0)
        self.assertAlmostEqual(r.self_consumption, 2.5 / 3.0)
        self.assertAlmostEqual(r.battery_efficiency, 1.0 / 3.0)
        self.assertAlmostEqual(r.home_grid_kwh, 0.5 + 0.2)
        # Home supply adds up.
        self.assertAlmostEqual(r.solar_home_kwh + r.discharge_kwh + r.home_grid_kwh, 0.5 + 1.0 + 1.2)
        # Half the battery's charge came from solar, so half its discharge counts as solar.
        self.assertAlmostEqual(r.battery_solar_share, 0.5)
        self.assertAlmostEqual(r.self_sufficiency, (1.0 + 0.5) / r.home_kwh)
        self.assertFalse(r.solar_sign_suspect)

    def test_signs_flipped(self):
        def flip(slots):
            return [{"slot": s["slot"], "pos_kwh": -s["neg_kwh"], "neg_kwh": -s["pos_kwh"]} for s in slots]
        a = su.calc_self_use(self.grid, self.solar, self.battery)
        b = su.calc_self_use(flip(self.grid), flip(self.solar), flip(self.battery), grid_import_negative=False,
                             solar_gen_negative=False, battery_charge_negative=True)
        self.assertEqual(a, b)

    def test_wrong_solar_sign_is_flagged(self):
        r = su.calc_self_use(self.grid, self.solar, self.battery, solar_gen_negative=False)
        self.assertTrue(r.solar_sign_suspect)
        self.assertTrue(su.summary_text(r).startswith("⚠ Check the solar CT sign"))

    def test_battery_only(self):
        r = su.calc_self_use(self.grid, None, self.battery)
        self.assertFalse(r.has_solar)
        self.assertEqual(r.solar_kwh, 0.0)
        # Without a solar CT, midday charging looks like grid charging and the export is unexplained.
        self.assertAlmostEqual(r.grid_battery_kwh, 3.0)
        text = su.summary_text(r)
        self.assertIn("Battery in 3.00 · out 1.00 kWh", text)
        self.assertIn("from battery", text)
        self.assertAlmostEqual(r.self_sufficiency, 1.0 / r.home_kwh)
        items = [row["item"] for row in su.table_rows(r)]
        self.assertFalse(any(i.startswith("Solar generated") for i in items))
        self.assertIn("  from the grid", items)

    def test_solar_only(self):
        r = su.calc_self_use(self.grid[:2], self.solar)
        self.assertAlmostEqual(r.solar_home_kwh, 2.5)
        self.assertAlmostEqual(r.self_consumption, 2.5 / 3.0)
        rows = {row["item"]: row for row in su.table_rows(r)}
        self.assertEqual(rows["Solar generated (% used)"]["pc"], "83%")
        self.assertEqual(rows["  exported"]["kwh"], "0.50")
        self.assertNotIn("Battery charged", rows)

    def test_empty(self):
        r = su.calc_self_use([], [], [])
        self.assertIsNone(r.self_consumption)
        self.assertIsNone(r.self_sufficiency)
        self.assertIn("Solar 0.00 kWh, – used on site", su.summary_text(r))

    def test_grid_charged_battery_is_not_solar(self):
        # Battery charged only overnight from the grid, solar all exported or used directly.
        battery = [slot(T0, pos=1.5), slot(T2, neg=1.0)]
        grid = [slot(T0, neg=2.0), slot(T1, pos=2.0), slot(T2, neg=0.2)]
        r = su.calc_self_use(grid, self.solar, battery)
        self.assertAlmostEqual(r.solar_battery_kwh, 0.0)
        self.assertAlmostEqual(r.grid_battery_kwh, 1.5)
        self.assertAlmostEqual(r.solar_home_kwh, 1.0)
        self.assertAlmostEqual(r.self_sufficiency, 1.0 / r.home_kwh)   # The battery adds nothing

    def test_detect_gen_negative(self):
        self.assertTrue(su.detect_gen_negative(self.solar))            # Generation read negative
        flipped = [{"slot": x["slot"], "pos_kwh": -x["neg_kwh"], "neg_kwh": -x["pos_kwh"]} for x in self.solar]
        self.assertFalse(su.detect_gen_negative(flipped))
        self.assertIsNone(su.detect_gen_negative([slot(T0, pos=0.01)]))  # Night only: can't tell
        self.assertIsNone(su.detect_gen_negative([]))

    def test_detected_sign_suppresses_warning(self):
        r = su.calc_self_use(self.grid, self.solar, self.battery, solar_gen_negative=False)
        r.solar_sign_detected = True
        self.assertFalse(r.solar_sign_suspect)

    def test_battery_sign_check_needs_a_week(self):
        def week(slots):
            out = []
            for d in range(8):
                for x in slots:
                    out.append({**x, "slot": x["slot"].replace(day=1 + d)})
            return out
        # Right way round: no warning.
        r = su.calc_self_use(week(self.grid), week(self.solar), week(self.battery))
        self.assertEqual(r.days, 8)
        self.assertFalse(r.battery_sign_suspect)
        # Wrong way round over a week: out (3.0/day) > in (1.0/day) is flagged.
        r = su.calc_self_use(week(self.grid), week(self.solar), week(self.battery), battery_charge_negative=True)
        self.assertTrue(r.battery_sign_suspect)
        self.assertIn("⚠ Check the battery CT sign", su.summary_text(r))
        # Same over one day: not flagged (an evening can be all discharge).
        r = su.calc_self_use(self.grid, self.solar, self.battery, battery_charge_negative=True)
        self.assertFalse(r.battery_sign_suspect)

    def test_data_coverage(self):
        a = datetime(2025, 6, 1)
        slots = [{"slot": a, "pos_kwh": 0, "neg_kwh": 0, "minutes": 30},
                 {"slot": a.replace(minute=30), "pos_kwh": 0, "neg_kwh": 0, "minutes": 24}]
        self.assertAlmostEqual(su.data_coverage(slots, a, a.replace(hour=1)), 54 / 60)
        self.assertIsNone(su.data_coverage(slots, a, a))
        self.assertEqual(su.data_coverage(slots, a, a.replace(minute=40)), 1.0)    # Capped
        r = su.calc_self_use(self.grid, self.solar, self.battery)
        r.coverage = {"grid": 0.998, "solar": 0.964, "battery": None}
        self.assertIn("data 96.4% complete", su.summary_text(r))
        rows = {row["item"]: row["pc"] for row in su.table_rows(r)}
        self.assertEqual((rows["  grid CT"], rows["  solar CT"]), ("99.8%", "96.4%"))
        self.assertNotIn("  battery CT", rows)
        self.assertIn("Minutes with data: grid 99.8%, solar 96.4%", su.caveat_text(r))
        r.coverage = {"grid": 0.995}
        self.assertNotIn("complete", su.summary_text(r))
        r.coverage = None
        self.assertEqual(su.caveat_text(r), su.CAVEAT)

    def test_roles_round_trip_and_check(self):
        roles = tf.SiteRoles(grid=tf.CTRef("A", 1), solar=tf.CTRef("A", 2), solar_gen_negative=False,
                             solar_sign_auto=False,
                             battery=tf.CTRef("B", 3), battery_charge_negative=True)
        self.assertEqual(tf.SiteRoles.from_dict(roles.to_dict()), roles)
        old = tf.SiteRoles.from_dict({"grid": {"device_id": "A", "ct": 1}})
        self.assertIsNone(old.solar)
        self.assertTrue(old.solar_gen_negative)
        self.assertTrue(old.solar_sign_auto)
        self.assertFalse(old.battery_charge_negative)
        roles.check()
        roles.battery = tf.CTRef("A", 2)
        with self.assertRaises(ValueError):
            roles.check()


if __name__ == "__main__":
    unittest.main()
