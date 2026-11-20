"""Unit tests for SQLiteDataSource (ct6_dash2 reading the SQLite files written by ct6_app).

   Run from the software/server folder:  python3 -m pytest tests/test_ct6_data_source_sqlite.py"""
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from lib.base_constants import BaseConstants as B  # noqa: E402
from ct6 import ct6_data as cd  # noqa: E402
from ct6.ct6_data import Resolution, EnergyBucket  # noqa: E402
from ct6.ct6_data_source import SQLiteDataSource, create_data_source_factory  # noqa: E402

FIELDS = list(B.FIELD_LIST_A)


def make_ct6_db(path, unit_name, ct_names, rows_by_table):
    """Create a CT6 SQLite file laid out as ct6_app does (text TIMESTAMP, META with UNIT_NAME).
       rows_by_table: table -> list of (timestamp_text, {column: value})."""
    conn = sqlite3.connect(path)
    cols = ", ".join(f"{e.split(':')[0]} {'TEXT' if e.split(':')[0] == B.TIMESTAMP else 'REAL'}"
                     for e in B.CT6_DB_TABLE_SCHEMA.split())
    conn.execute(f"CREATE TABLE {B.CT6_META_TABLE_NAME} ({B.CT6_DB_META_TABLE_SCHEMA_SQLITE})")
    conn.execute(f"INSERT INTO {B.CT6_META_TABLE_NAME} (ID, HW_ASSY, UNIT_NAME, CT1_NAME, CT2_NAME, CT3_NAME, "
                 "CT4_NAME, CT5_NAME, CT6_NAME) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)",
                 ["ASY0398_V01.6000_SN0001", unit_name] + list(ct_names))
    for table in (B.CT6_TABLE_NAME, B.MINUTE_RES_DB_DATA_TABLE_NAME, B.HOUR_RES_DB_DATA_TABLE_NAME,
                  B.DAY_RES_DB_DATA_TABLE_NAME):
        conn.execute(f"CREATE TABLE {table} ({cols})")
        for ts, values in rows_by_table.get(table, []):
            row = {f: 0.0 for f in FIELDS}
            row.update(values)
            conn.execute(f"INSERT INTO {table} (TIMESTAMP, {', '.join(FIELDS)}) VALUES (?{', ?' * len(FIELDS)})",
                         [ts] + [row[f] for f in FIELDS])
    conn.commit()
    conn.close()


class TestSQLiteDataSource(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = self.tmp.name
        self.house = os.path.join(self.folder, "ASY0398_SN0001.db")
        # ct6_app writes str(datetime)[:26]: no fraction when microseconds are 0, else 6 digits.
        minute = [("2026-11-19 23:59:00", {"CT1_ACT_WATTS": 600.0}),
                  ("2026-11-20 00:00:00", {"CT1_ACT_WATTS": 1200.0}),
                  ("2026-11-20 12:00:00.250000", {"CT1_ACT_WATTS": -600.0}),
                  ("2026-11-20 23:59:59.500000", {"CT1_ACT_WATTS": 60.0}),
                  ("2026-12-01 10:00:00", {"CT1_ACT_WATTS": 6000.0})]
        hour = [(f"2026-11-20 {h:02d}:00:00", {"CT1_ACT_WATTS": 1000.0}) for h in range(24)] + \
               [("2026-11-21 00:00:00", {"CT1_ACT_WATTS": 5000.0})]
        sensor = [("2026-11-20 10:00:00", {"CT1_ACT_WATTS": 100.0}),
                  ("2026-11-20 10:00:01.123456", {"CT1_ACT_WATTS": 200.0}),
                  ("2026-11-20 10:00:02.654321", {"CT1_ACT_WATTS": 300.0})]
        make_ct6_db(self.house, "HOUSE", ("Grid", "", "", "", "", ""),
                    {B.MINUTE_RES_DB_DATA_TABLE_NAME: minute, B.HOUR_RES_DB_DATA_TABLE_NAME: hour,
                     B.CT6_TABLE_NAME: sensor})
        self.ds = SQLiteDataSource(self.folder)

    def tearDown(self):
        self.ds.close()
        self.tmp.cleanup()

    def test_list_devices_skips_other_files_and_names_duplicates(self):
        make_ct6_db(os.path.join(self.folder, "B_SN0002.db"), "HOUSE", ("EV", "", "", "", "", ""), {})
        make_ct6_db(os.path.join(self.folder, "C_SN0003.db"), "", ("Zappi", "", "", "", "", ""), {})
        sqlite3.connect(os.path.join(self.folder, "other.db")).execute("CREATE TABLE x (a)").connection.close()
        with open(os.path.join(self.folder, "junk.db"), "w") as fd:
            fd.write("not an sqlite file")
        with open(os.path.join(self.folder, "notes.txt"), "w") as fd:
            fd.write("x")
        devices = self.ds.list_devices()
        names = [d.name for d in devices]
        self.assertEqual(names, ["C_SN0003", "HOUSE (ASY0398_SN0001)", "HOUSE (B_SN0002)"])
        house = [d for d in devices if d.device_id == self.house][0]
        self.assertEqual(house.active_cts(), [(1, "Grid")])

    def test_missing_folder(self):
        with self.assertRaises(FileNotFoundError):
            SQLiteDataSource(os.path.join(self.folder, "nope")).list_devices()

    def test_count_and_read_include_whole_stop_minute(self):
        start, stop = cd.parse_start_stop("2026-11-20", "00:00", "2026-11-20", "23:59")
        self.assertEqual(self.ds.count_rows(self.house, start, stop, Resolution.MIN), 3)
        rows = self.ds.read_rows(self.house, start, stop, Resolution.MIN)
        self.assertEqual([r[cd.TIMESTAMP] for r in rows],
                         [datetime(2026, 11, 20, 0, 0), datetime(2026, 11, 20, 12, 0, 0, 250000),
                          datetime(2026, 11, 20, 23, 59, 59, 500000)])
        self.assertEqual(rows[0]["CT1_ACT_WATTS"], 1200.0)

    def test_daily_averages(self):
        start, stop = cd.parse_start_stop("2026-11-20", "00:00", "2026-11-21", "23:59")
        recs = self.ds.daily_averages(self.house, "CT1_ACT_WATTS", start, stop)
        self.assertEqual([(r["day"], r["avg_w"], r["sample_count"]) for r in recs],
                         [(date(2026, 11, 20), 1000.0, 24), (date(2026, 11, 21), 5000.0, 1)])
        self.assertEqual(cd.peak_daily_kwh(recs).peak_kwh, 24.0)

    def test_period_energy_day_and_month(self):
        start, stop = cd.parse_start_stop("2026-11-19", "00:00", "2026-12-31", "23:59")
        days = self.ds.period_energy(self.house, ["CT1_ACT_WATTS"], start, stop, EnergyBucket.DAY)
        self.assertEqual([r["period"] for r in days], [date(2026, 11, 19), date(2026, 11, 20), date(2026, 12, 1)])
        self.assertAlmostEqual(days[1]["CT1_ACT_WATTS_pos"], (1200 + 60) / 60000)
        self.assertAlmostEqual(days[1]["CT1_ACT_WATTS_neg"], -600 / 60000)
        months = self.ds.period_energy(self.house, ["CT1_ACT_WATTS"], start, stop, EnergyBucket.MONTH)
        self.assertEqual([r["period"] for r in months], [date(2026, 11, 1), date(2026, 12, 1)])
        self.assertAlmostEqual(months[0]["CT1_ACT_WATTS_pos"], (600 + 1200 + 60) / 60000)

    def test_recent_rows_and_latest(self):
        rows = self.ds.recent_rows(self.house, datetime(2026, 11, 20, 10, 0, 1, 123456))
        self.assertEqual([r["CT1_ACT_WATTS"] for r in rows], [300.0])     # strictly newer
        self.assertEqual(len(self.ds.recent_rows(self.house, datetime(2026, 11, 20, 9, 0))), 3)
        self.assertEqual(self.ds.latest_timestamp(self.house), datetime(2026, 11, 20, 10, 0, 2, 654321))

    def test_files_are_opened_read_only(self):
        start, stop = cd.parse_start_stop("2026-11-20", "00:00", "2026-11-20", "23:59")
        self.ds.count_rows(self.house, start, stop, Resolution.MIN)
        with self.assertRaises(sqlite3.OperationalError):
            self.ds._conn(self.house).execute("DELETE FROM CT6_SENSOR")

    def test_factory_sqlite_override(self):
        class NoKeys:
            def getAttr(self, key):
                raise KeyError(key)
        factory = create_data_source_factory(NoKeys(), sqlite_path=self.folder)
        with factory() as ds:
            self.assertIsInstance(ds, SQLiteDataSource)
            self.assertEqual([d.name for d in ds.list_devices()], ["HOUSE"])


if __name__ == "__main__":
    unittest.main()
