#!/usr/bin/env python3
"""@brief Database access for the CT6 dashboard.

   CT6DataSource defines the operations the dashboard needs.
   - MySQLDataSource reads the databases written by ct6_db_store
     (one MySQL database per CT6 device).
   - SQLiteDataSource reads the databases written by ct6_app
     (one <HW_ASSY>.db SQLite file per CT6 device, in its DB storage folder).

   Instances are NOT thread safe. Each worker thread should create its own
   instance via a factory (see create_data_source_factory()) and close it when
   done."""

import os
import re
import sqlite3
import threading
from abc import ABC, abstractmethod
from datetime import date, datetime, time, timedelta

from lib.base_constants import BaseConstants

from ct6.ct6_data import DeviceInfo, EnergyBucket, TIMESTAMP


class CT6DataSource(ABC):
    """@brief The database operations used by the CT6 dashboard."""

    @abstractmethod
    def list_devices(self):
        """@return A list of DeviceInfo instances, one per CT6 device found."""

    @abstractmethod
    def count_rows(self, device_id, start_dt, stop_dt, resolution):
        """@return The number of rows between start_dt and stop_dt (inclusive) at the given Resolution."""

    @abstractmethod
    def read_rows(self, device_id, start_dt, stop_dt, resolution):
        """@return A list of row dicts (TIMESTAMP as a datetime) ordered by time."""

    @abstractmethod
    def daily_averages(self, device_id, column, start_dt, stop_dt):
        """@brief Average a column per calendar day using the hour resolution table.
           @return A list of dicts with day (date), avg_w (float) and sample_count (int)."""

    @abstractmethod
    def half_hour_energy(self, device_id, column, start_dt, stop_dt):
        """@brief Total a power column per half-hour using the minute resolution table.
                  Each minute row is taken as one minute at that power. Used for costs.
           @return A list of dicts with slot (datetime, start of the half-hour),
                   minutes (minute rows with data in the half-hour),
                   pos_kwh (energy from positive readings, >= 0) and
                   neg_kwh (energy from negative readings, <= 0), ordered by slot."""

    @abstractmethod
    def period_energy(self, device_id, columns, start_dt, stop_dt, bucket):
        """@brief Total power columns per day or month using the minute resolution table.
                  Each minute row counts as one minute at that power.
           @param columns The power columns (e.g. CT1_ACT_WATTS).
           @param bucket EnergyBucket.DAY or EnergyBucket.MONTH.
           @return A list of dicts ordered by period: period (date, first day of the day/month)
                   plus <column>_pos (kWh from positive readings, >= 0) and
                   <column>_neg (kWh from negative readings, <= 0) for each column."""

    @abstractmethod
    def daily_run_time(self, device_id, column, threshold_w, start_dt, stop_dt):
        """@brief Per day heat pump figures from the minute resolution table (Heat pump tab).
                  The absolute value of the power is used, so a reversed CT clamp still works.
           @param threshold_w A minute counts as running when its average power is at or above this.
           @return A list of dicts ordered by day: day (date), on_minutes (running minutes),
                   minutes (minutes with data), peak_w (highest minute average) and kwh."""

    @abstractmethod
    def recent_rows(self, device_id, since_dt):
        """@brief Read the full resolution rows newer than since_dt (used by the Live tab).
           @return A list of row dicts ordered by time."""

    @abstractmethod
    def latest_timestamp(self, device_id):
        """@return The datetime of the newest full resolution row, or None if there is none."""

    @abstractmethod
    def close(self):
        """@brief Release the connection."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


_VALID_NAME = re.compile(r"^[A-Za-z0-9_$\-]+$")
_VALID_COLUMN = re.compile(r"^[A-Za-z0-9_]+$")


def _quote_name(name):
    """@brief Quote a database name, rejecting anything unexpected."""
    if not name or not _VALID_NAME.match(name):
        raise ValueError(f"Invalid database name: {name!r}")
    return f"`{name}`"


def _check_column(column):
    if not column or not _VALID_COLUMN.match(column):
        raise ValueError(f"Invalid column name: {column!r}")
    return column


class HalfHourEnergyCache:
    """@brief Keeps the half-hour energy of completed days, so repeat cost calculations
              (another tab, Update, a different range) don't re-read them from the database.
              Days before today don't change, so they are cached; today is always read.
              Shared by all browser clients and worker threads."""

    def __init__(self, max_days=20000):
        self._days = {}               # (backend, device_id, column, date) -> list of slot dicts
        self._lock = threading.Lock()
        self._max_days = max_days

    def clear(self):
        with self._lock:
            self._days.clear()

    def half_hour_energy(self, ds, device_id, column, start_dt, stop_dt, today=None):
        """@brief As CT6DataSource.half_hour_energy() but using cached days where possible.
                  Returns the half-hours that start within start_dt..stop_dt."""
        today = today or date.today()
        backend = type(ds).__name__
        first_day, last_day = start_dt.date(), stop_dt.date()
        last_cached_day = min(last_day, today - timedelta(days=1))
        days = [first_day + timedelta(days=i) for i in range((last_cached_day - first_day).days + 1)]
        with self._lock:
            missing = [d for d in days if (backend, device_id, column, d) not in self._days]
        if missing:
            rows = ds.half_hour_energy(device_id, column, datetime.combine(missing[0], time()),
                                       datetime.combine(missing[-1], time(23, 59, 59)))
            by_day = {d: [] for d in missing}
            for r in rows:
                if r["slot"].date() in by_day:
                    by_day[r["slot"].date()].append(r)
            with self._lock:
                if len(self._days) + len(by_day) > self._max_days:
                    self._days.clear()
                for d, day_rows in by_day.items():
                    self._days[(backend, device_id, column, d)] = day_rows
        result = []
        with self._lock:
            for d in days:
                result += self._days.get((backend, device_id, column, d), [])
        if last_day > last_cached_day:
            # Today (or later): always read, it is still changing.
            live_start = max(start_dt, datetime.combine(last_cached_day + timedelta(days=1), time()))
            result += ds.half_hour_energy(device_id, column, live_start, stop_dt)
        lo = start_dt.replace(minute=start_dt.minute - start_dt.minute % 30, second=0, microsecond=0)
        return [dict(r) for r in result if lo <= r["slot"] <= stop_dt]


class MySQLDataSource(CT6DataSource):
    """@brief Reads CT6 data from the MySQL databases written by ct6_db_store.
              Each CT6 device has its own database (named after the device)
              holding the CT6_META table and the CT6_SENSOR(_MINUTE/_HOUR/_DAY) tables."""

    def __init__(self, host, port, username, password, connect_timeout=10):
        import MySQLdb
        import MySQLdb.cursors
        self._conn = MySQLdb.connect(host=host,
                                     port=int(port),
                                     user=username,
                                     passwd=password,
                                     connect_timeout=connect_timeout,
                                     cursorclass=MySQLdb.cursors.DictCursor,
                                     autocommit=True)

    def _query(self, sql, params=None):
        cur = self._conn.cursor()
        try:
            cur.execute(sql, params)
            return list(cur.fetchall())
        finally:
            cur.close()

    def _tables(self, db_name):
        rows = self._query("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s", (db_name,))
        return {r["TABLE_NAME"] for r in rows}

    def list_devices(self):
        devices = []
        for rec in self._query("SHOW DATABASES"):
            db_name = rec.get("Database")
            if not db_name or not _VALID_NAME.match(db_name):
                continue
            tables = self._tables(db_name)
            if BaseConstants.CT6_META_TABLE_NAME in tables and BaseConstants.MAX_RES_DB_DATA_TABLE_NAME in tables:
                meta = self._query(f"SELECT * FROM {_quote_name(db_name)}.{BaseConstants.CT6_META_TABLE_NAME} LIMIT 1")
                if meta:
                    dev = DeviceInfo.from_meta_row(db_name, db_name, meta[0])
                    dev.first_date = self._first_date(db_name, tables)
                    devices.append(dev)
        return devices

    def _first_date(self, db_name, tables):
        """@return The date of the earliest row (indexed MIN, so fast), or None."""
        for table in (BaseConstants.DAY_RES_DB_DATA_TABLE_NAME, BaseConstants.MAX_RES_DB_DATA_TABLE_NAME):
            if table in tables:
                rows = self._query(f"SELECT MIN({TIMESTAMP}) AS t FROM {_quote_name(db_name)}.{table}")
                if rows and rows[0]["t"]:
                    return rows[0]["t"].date()
        return None

    def count_rows(self, device_id, start_dt, stop_dt, resolution):
        sql = f"SELECT COUNT(*) AS n FROM {_quote_name(device_id)}.{resolution.table_name} " \
              f"WHERE {TIMESTAMP} BETWEEN %s AND %s"
        return int(self._query(sql, (start_dt, stop_dt))[0]["n"])

    def read_rows(self, device_id, start_dt, stop_dt, resolution):
        sql = f"SELECT * FROM {_quote_name(device_id)}.{resolution.table_name} " \
              f"WHERE {TIMESTAMP} BETWEEN %s AND %s ORDER BY {TIMESTAMP}"
        return self._query(sql, (start_dt, stop_dt))

    def daily_averages(self, device_id, column, start_dt, stop_dt):
        column = _check_column(column)
        sql = f"SELECT DATE({TIMESTAMP}) AS day, AVG({column}) AS avg_w, COUNT(*) AS sample_count " \
              f"FROM {_quote_name(device_id)}.{BaseConstants.HOUR_RES_DB_DATA_TABLE_NAME} " \
              f"WHERE {TIMESTAMP} BETWEEN %s AND %s GROUP BY DATE({TIMESTAMP}) ORDER BY day"
        return self._query(sql, (start_dt, stop_dt))

    def half_hour_energy(self, device_id, column, start_dt, stop_dt):
        column = _check_column(column)
        slot = f"DATE_SUB({TIMESTAMP}, INTERVAL MOD(MINUTE({TIMESTAMP}), 30) * 60 + SECOND({TIMESTAMP}) SECOND)"
        sql = f"SELECT {slot} AS slot, " \
              f"SUM(GREATEST({column}, 0)) / 60000.0 AS pos_kwh, " \
              f"SUM(LEAST({column}, 0)) / 60000.0 AS neg_kwh, COUNT(*) AS minutes " \
              f"FROM {_quote_name(device_id)}.{BaseConstants.MINUTE_RES_DB_DATA_TABLE_NAME} " \
              f"WHERE {TIMESTAMP} BETWEEN %s AND %s GROUP BY slot ORDER BY slot"
        rows = self._query(sql, (start_dt, stop_dt))
        for r in rows:
            r["pos_kwh"] = float(r["pos_kwh"] or 0.0)
            r["minutes"] = int(r["minutes"] or 0)
            r["neg_kwh"] = float(r["neg_kwh"] or 0.0)
        return rows

    def period_energy(self, device_id, columns, start_dt, stop_dt, bucket):
        if bucket == EnergyBucket.MONTH:
            period = f"DATE_SUB(DATE({TIMESTAMP}), INTERVAL DAYOFMONTH({TIMESTAMP}) - 1 DAY)"
        else:
            period = f"DATE({TIMESTAMP})"
        sums = []
        for c in columns:
            c = _check_column(c)
            sums.append(f"SUM(GREATEST({c}, 0)) / 60000.0 AS {c}_pos")
            sums.append(f"SUM(LEAST({c}, 0)) / 60000.0 AS {c}_neg")
        sql = f"SELECT {period} AS period, {', '.join(sums)} " \
              f"FROM {_quote_name(device_id)}.{BaseConstants.MINUTE_RES_DB_DATA_TABLE_NAME} " \
              f"WHERE {TIMESTAMP} BETWEEN %s AND %s GROUP BY period ORDER BY period"
        rows = self._query(sql, (start_dt, stop_dt))
        for r in rows:
            for k, v in r.items():
                if k != "period":
                    r[k] = float(v or 0.0)
        return rows

    def daily_run_time(self, device_id, column, threshold_w, start_dt, stop_dt):
        c = _check_column(column)
        sql = f"SELECT DATE({TIMESTAMP}) AS day, SUM(ABS({c}) >= %s) AS on_minutes, COUNT(*) AS minutes, " \
              f"MAX(ABS({c})) AS peak_w, SUM(ABS({c})) / 60000.0 AS kwh " \
              f"FROM {_quote_name(device_id)}.{BaseConstants.MINUTE_RES_DB_DATA_TABLE_NAME} " \
              f"WHERE {TIMESTAMP} BETWEEN %s AND %s GROUP BY day ORDER BY day"
        rows = self._query(sql, (float(threshold_w), start_dt, stop_dt))
        return [{"day": r["day"], "on_minutes": int(r["on_minutes"] or 0), "minutes": int(r["minutes"]),
                 "peak_w": float(r["peak_w"] or 0.0), "kwh": float(r["kwh"] or 0.0)} for r in rows]

    def recent_rows(self, device_id, since_dt):
        sql = f"SELECT * FROM {_quote_name(device_id)}.{BaseConstants.MAX_RES_DB_DATA_TABLE_NAME} " \
              f"WHERE {TIMESTAMP} > %s ORDER BY {TIMESTAMP}"
        return self._query(sql, (since_dt,))

    def latest_timestamp(self, device_id):
        sql = f"SELECT MAX({TIMESTAMP}) AS t FROM {_quote_name(device_id)}.{BaseConstants.MAX_RES_DB_DATA_TABLE_NAME}"
        rows = self._query(sql)
        return rows[0]["t"] if rows else None

    def close(self):
        if self._conn:
            try:
                self._conn.close()
            finally:
                self._conn = None


class SQLiteDataSource(CT6DataSource):
    """@brief Reads CT6 data from the SQLite database files written by ct6_app.
              Each CT6 device has its own <HW_ASSY>.db file holding the CT6_META table
              (with a UNIT_NAME column) and the CT6_SENSOR(_MINUTE/_HOUR/_DAY) tables.
              ct6_app stores TIMESTAMP as text ('YYYY-MM-DD HH:MM:SS[.ffffff]'), so times are
              compared as text and parsed into datetimes when read.
              The device ID is the absolute path of the .db file. Files are opened read-only."""

    def __init__(self, folder, timeout=10):
        """@param folder The folder holding the .db files (ct6_app's DB_STORAGE_PATH).
           @param timeout Seconds to wait if ct6_app is writing to a file."""
        self._folder = os.path.abspath(os.path.expanduser(folder))
        self._timeout = timeout
        self._conns = {}

    @staticmethod
    def _ts_text(dt):
        """@return A datetime as text that compares correctly with ct6_app's stored timestamps."""
        return dt.isoformat(sep=" ")

    @staticmethod
    def _parse_ts(value):
        if value is None or isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value).strip()[:26])

    def _conn(self, device_id):
        conn = self._conns.get(device_id)
        if conn is None:
            if not os.path.isfile(device_id):
                raise FileNotFoundError(f"{device_id} not found.")
            uri = "file:" + os.path.abspath(device_id).replace("?", "%3f").replace("#", "%23") + "?mode=ro"
            conn = sqlite3.connect(uri, uri=True, timeout=self._timeout, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self._conns[device_id] = conn
        return conn

    def _query(self, device_id, sql, params=()):
        cur = self._conn(device_id).execute(sql, params)
        try:
            return [dict(r) for r in cur.fetchall()]
        finally:
            cur.close()

    def _rows(self, device_id, sql, params=()):
        rows = self._query(device_id, sql, params)
        for r in rows:
            r[TIMESTAMP] = self._parse_ts(r.get(TIMESTAMP))
        return rows

    def _tables(self, device_id):
        return {r["name"] for r in self._query(device_id, "SELECT name FROM sqlite_master WHERE type='table'")}

    def list_devices(self):
        if not os.path.isdir(self._folder):
            raise FileNotFoundError(f"The SQLite database folder ({self._folder}) was not found.")
        devices = []
        for entry in sorted(os.listdir(self._folder)):
            path = os.path.join(self._folder, entry)
            if not entry.endswith(".db") or not os.path.isfile(path):
                continue
            try:
                tables = self._tables(path)
                if BaseConstants.CT6_META_TABLE_NAME not in tables or BaseConstants.MAX_RES_DB_DATA_TABLE_NAME not in tables:
                    continue
                meta = self._query(path, f"SELECT * FROM {BaseConstants.CT6_META_TABLE_NAME} LIMIT 1")
            except sqlite3.DatabaseError:
                continue        # Not a CT6 database (or not an SQLite file)
            meta = meta[0] if meta else {}
            name = (meta.get(BaseConstants.UNIT_NAME) or "").strip() or os.path.splitext(entry)[0]
            dev = DeviceInfo.from_meta_row(path, name, meta)
            dev.first_date = self._first_date(path, tables)
            devices.append(dev)
        # Make tab names unique if two files have the same unit name.
        counts = {}
        for d in devices:
            counts[d.name] = counts.get(d.name, 0) + 1
        for d in devices:
            if counts[d.name] > 1:
                d.name = f"{d.name} ({os.path.splitext(os.path.basename(d.device_id))[0]})"
        return sorted(devices, key=lambda d: d.name)

    def _first_date(self, device_id, tables):
        """@return The date of the earliest row (indexed MIN, so fast), or None."""
        for table in (BaseConstants.DAY_RES_DB_DATA_TABLE_NAME, BaseConstants.MAX_RES_DB_DATA_TABLE_NAME):
            if table in tables:
                rows = self._query(device_id, f"SELECT MIN({TIMESTAMP}) AS t FROM {table}")
                if rows and rows[0]["t"]:
                    return self._parse_ts(rows[0]["t"]).date()
        return None

    def count_rows(self, device_id, start_dt, stop_dt, resolution):
        sql = f"SELECT COUNT(*) AS n FROM {resolution.table_name} WHERE {TIMESTAMP} BETWEEN ? AND ?"
        return int(self._query(device_id, sql, (self._ts_text(start_dt), self._ts_text(stop_dt)))[0]["n"])

    def read_rows(self, device_id, start_dt, stop_dt, resolution):
        sql = f"SELECT * FROM {resolution.table_name} WHERE {TIMESTAMP} BETWEEN ? AND ? ORDER BY {TIMESTAMP}"
        return self._rows(device_id, sql, (self._ts_text(start_dt), self._ts_text(stop_dt)))

    def daily_averages(self, device_id, column, start_dt, stop_dt):
        column = _check_column(column)
        sql = f"SELECT DATE({TIMESTAMP}) AS day, AVG({column}) AS avg_w, COUNT(*) AS sample_count " \
              f"FROM {BaseConstants.HOUR_RES_DB_DATA_TABLE_NAME} " \
              f"WHERE {TIMESTAMP} BETWEEN ? AND ? GROUP BY day ORDER BY day"
        rows = self._query(device_id, sql, (self._ts_text(start_dt), self._ts_text(stop_dt)))
        for r in rows:
            r["day"] = date.fromisoformat(r["day"]) if r["day"] else None
        return rows

    def half_hour_energy(self, device_id, column, start_dt, stop_dt):
        column = _check_column(column)
        # Text timestamps: the half-hour is the first 14 characters ('YYYY-MM-DD HH:') plus 00 or 30.
        slot = f"SUBSTR({TIMESTAMP}, 1, 14) || CASE WHEN CAST(SUBSTR({TIMESTAMP}, 15, 2) AS INTEGER) < 30 " \
               f"THEN '00:00' ELSE '30:00' END"
        sql = f"SELECT {slot} AS slot, SUM(MAX({column}, 0)) / 60000.0 AS pos_kwh, " \
              f"SUM(MIN({column}, 0)) / 60000.0 AS neg_kwh, COUNT(*) AS minutes " \
              f"FROM {BaseConstants.MINUTE_RES_DB_DATA_TABLE_NAME} " \
              f"WHERE {TIMESTAMP} BETWEEN ? AND ? GROUP BY slot ORDER BY slot"
        rows = self._query(device_id, sql, (self._ts_text(start_dt), self._ts_text(stop_dt)))
        for r in rows:
            r["slot"] = self._parse_ts(r["slot"])
            r["pos_kwh"] = float(r["pos_kwh"] or 0.0)
            r["minutes"] = int(r["minutes"] or 0)
            r["neg_kwh"] = float(r["neg_kwh"] or 0.0)
        return rows

    def period_energy(self, device_id, columns, start_dt, stop_dt, bucket):
        period = f"DATE({TIMESTAMP}, 'start of month')" if bucket == EnergyBucket.MONTH else f"DATE({TIMESTAMP})"
        sums = []
        for c in columns:
            c = _check_column(c)
            sums.append(f"SUM(MAX({c}, 0)) / 60000.0 AS {c}_pos")
            sums.append(f"SUM(MIN({c}, 0)) / 60000.0 AS {c}_neg")
        sql = f"SELECT {period} AS period, {', '.join(sums)} " \
              f"FROM {BaseConstants.MINUTE_RES_DB_DATA_TABLE_NAME} " \
              f"WHERE {TIMESTAMP} BETWEEN ? AND ? GROUP BY period ORDER BY period"
        rows = self._query(device_id, sql, (self._ts_text(start_dt), self._ts_text(stop_dt)))
        for r in rows:
            r["period"] = date.fromisoformat(r["period"])
            for k, v in r.items():
                if k != "period":
                    r[k] = float(v or 0.0)
        return rows

    def daily_run_time(self, device_id, column, threshold_w, start_dt, stop_dt):
        c = _check_column(column)
        sql = f"SELECT DATE({TIMESTAMP}) AS day, SUM(ABS({c}) >= ?) AS on_minutes, COUNT(*) AS minutes, " \
              f"MAX(ABS({c})) AS peak_w, SUM(ABS({c})) / 60000.0 AS kwh " \
              f"FROM {BaseConstants.MINUTE_RES_DB_DATA_TABLE_NAME} " \
              f"WHERE {TIMESTAMP} BETWEEN ? AND ? GROUP BY day ORDER BY day"
        rows = self._query(device_id, sql, (float(threshold_w), self._ts_text(start_dt), self._ts_text(stop_dt)))
        return [{"day": date.fromisoformat(r["day"]), "on_minutes": int(r["on_minutes"] or 0),
                 "minutes": int(r["minutes"]), "peak_w": float(r["peak_w"] or 0.0),
                 "kwh": float(r["kwh"] or 0.0)} for r in rows]

    def recent_rows(self, device_id, since_dt):
        sql = f"SELECT * FROM {BaseConstants.MAX_RES_DB_DATA_TABLE_NAME} WHERE {TIMESTAMP} > ? ORDER BY {TIMESTAMP}"
        return self._rows(device_id, sql, (self._ts_text(since_dt),))

    def latest_timestamp(self, device_id):
        rows = self._query(device_id, f"SELECT MAX({TIMESTAMP}) AS t FROM {BaseConstants.MAX_RES_DB_DATA_TABLE_NAME}")
        return self._parse_ts(rows[0]["t"]) if rows else None

    def close(self):
        for conn in self._conns.values():
            try:
                conn.close()
            except Exception:
                pass
        self._conns = {}


BACKEND_MYSQL = "mysql"
BACKEND_SQLITE = "sqlite"
DB_BACKEND = "DB_BACKEND"           # Config key: BACKEND_MYSQL or BACKEND_SQLITE
SQLITE_DB_PATH = "SQLITE_DB_PATH"   # Config key: folder holding ct6_app's .db files


def default_sqlite_path():
    """@return ct6_app's default DB storage folder (~/.config/ct6_app)."""
    return os.path.join(os.path.expanduser("~"), ".config", "ct6_app")


def create_data_source_factory(config, sqlite_path=None):
    """@brief Get a callable that creates a new CT6DataSource from the app config.
              Call it once per worker thread.
       @param config A ConfigBase instance holding the DB settings.
       @param sqlite_path If set, use the SQLite backend with this folder (overrides the config).
       @return A callable returning a CT6DataSource."""
    def _get(key):
        try:
            return config.getAttr(key)
        except KeyError:
            return None

    backend = BACKEND_SQLITE if sqlite_path else (_get(DB_BACKEND) or BACKEND_MYSQL)
    if backend == BACKEND_SQLITE:
        folder = sqlite_path or _get(SQLITE_DB_PATH) or default_sqlite_path()

        def sqlite_factory():
            return SQLiteDataSource(folder)
        return sqlite_factory

    return _mysql_factory(config)


def _mysql_factory(config):
    """@brief Get a callable that creates a new MySQLDataSource from the app config.
              Call it once per worker thread.
       @param config A ConfigBase instance holding the DB settings.
       @return A callable returning a CT6DataSource."""
    from lib.config import ConfigBase
    host = config.getAttr(ConfigBase.DB_HOST)
    port = config.getAttr(ConfigBase.DB_PORT)
    username = config.getAttr(ConfigBase.DB_USERNAME)
    password = config.getAttr(ConfigBase.DB_PASSWORD)

    def factory():
        return MySQLDataSource(host, port, username, password)
    return factory
