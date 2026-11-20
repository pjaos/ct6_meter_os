#!/usr/bin/env python3
"""@brief Database access for the CT6 dashboard.

   CT6DataSource defines the operations the dashboard needs. MySQLDataSource
   reads the databases written by ct6_db_store. A SQLiteDataSource (for the
   databases written by ct6_app) can be added by implementing the same methods.

   Instances are NOT thread safe. Each worker thread should create its own
   instance via a factory (see create_data_source_factory()) and close it when
   done."""

import re
from abc import ABC, abstractmethod

from lib.base_constants import BaseConstants

from ct6.ct6_data import DeviceInfo, TIMESTAMP


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
                    devices.append(DeviceInfo.from_meta_row(db_name, db_name, meta[0]))
        return devices

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


def create_data_source_factory(config):
    """@brief Get a callable that creates a new CT6DataSource from the app config.
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
