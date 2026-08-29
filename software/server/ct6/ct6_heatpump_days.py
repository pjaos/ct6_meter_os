#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""
ct6_heatpump_days.py

Count the number of days in a year that an air-to-air heat pump (aircon),
measured on one CT port of a CT6 device, was running - split into heating and
cooling days.

How it works
------------
The heat pump is measured on one CT port, i.e. the active power column
CT<port>_ACT_WATTS in the CT6_SENSOR table written by ct6_db_store.

A day is counted as an "on" day when the pump ran for at least a minimum amount
of time that day (default 10 minutes). "Running" means the measured active
power was at or above a threshold (in watts). The absolute value of the power is
used so a reversed CT clamp still works.

On-time is measured properly (not just "seen once"): for every sample at/above
the threshold, the tool credits the time gap since the previous sample and sums
those gaps for the day. Gaps larger than --max-gap-seconds (e.g. the device was
offline) are capped so an outage is not mistaken for run-time. A day is an "on"
day when this total reaches --min-minutes.

A CT port cannot tell heating from cooling electrically, so each on-day is
labelled by the calendar: cooling from May to September inclusive, heating in
every other month. The cooling months can be changed with --cooling-months.

The per-day aggregation is done in the database, so only ~365 rows come back
even though CT6_SENSOR holds roughly one sample per second.

Requires MySQL 8.0+ (uses the LAG window function).

Examples
--------
Port 3 is the heat pump, "on" means >= 150 W for at least 10 minutes in a day:
    ct6_heatpump_days.py -H 192.168.0.10 -u root -p secret -d MY_CT6 \\
        --port 3 --threshold 150 --year 2024

Same, but require 30 minutes of run-time and dump per-day detail to a CSV:
    ct6_heatpump_days.py -H 192.168.0.10 -u root -p secret -d MY_CT6 \\
        --port 3 --threshold 150 --min-minutes 30 --year 2024 --csv 2024_days.csv
"""

import sys
import csv
import time
import argparse
import getpass
import re
from datetime import date

# ---------------------------------------------------------------------------
# Database driver abstraction (same approach as ct6_db_to_csv.py): use whichever
# MySQL driver is installed and talk to it through the DB-API 2.0 interface.
# ---------------------------------------------------------------------------

_IDENTIFIER_RE = re.compile(r'^[0-9A-Za-z_$]+$')

SENSOR_TABLE = "CT6_SENSOR"
TIMESTAMP_COL = "TIMESTAMP"

# Default cooling season: May(5) .. September(9) inclusive.
DEFAULT_COOLING_MONTHS = (5, 6, 7, 8, 9)


def _connect(host, port, user, password, database=None):
    """@brief Connect to a MySQL server using whatever driver is installed.
       @return A tuple of (connection, driver_name)."""
    lastError = None

    try:
        import mysql.connector as mysql_connector
        conn = mysql_connector.connect(host=host, port=int(port), user=user,
                                       password=password, database=database)
        return conn, "mysql.connector"
    except ImportError:
        pass
    except Exception as ex:
        lastError = ex

    try:
        import MySQLdb
        kwargs = dict(host=host, port=int(port), user=user, passwd=password)
        if database:
            kwargs["db"] = database
        return MySQLdb.connect(**kwargs), "MySQLdb"
    except ImportError:
        pass
    except Exception as ex:
        lastError = ex

    try:
        import pymysql
        conn = pymysql.connect(host=host, port=int(port), user=user,
                               password=password, database=database)
        return conn, "pymysql"
    except ImportError:
        pass
    except Exception as ex:
        lastError = ex

    if lastError is not None:
        raise lastError
    raise RuntimeError(
        "No MySQL driver found. Install one of: mysql-connector-python, "
        "mysqlclient or pymysql."
    )


def _validateIdentifier(name, what):
    """@brief Ensure a name is a safe SQL identifier."""
    if not name or not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid {what}: '{name}'.")
    return name


def portToColumn(port):
    """@brief Map a CT port number (1-6) to its active power column name."""
    if port not in (1, 2, 3, 4, 5, 6):
        raise ValueError(f"--port must be 1..6, not {port}.")
    return f"CT{port}_ACT_WATTS"


def parseCoolingMonths(text):
    """@brief Parse a comma separated list of month numbers into a set.
       @param text e.g. "5,6,7,8,9".
       @return A set of ints in 1..12."""
    months = set()
    for raw in text.split(","):
        raw = raw.strip()
        if not raw:
            continue
        m = int(raw)
        if m < 1 or m > 12:
            raise ValueError(f"Month out of range (1..12): {m}.")
        months.add(m)
    if not months:
        raise ValueError("No cooling months given.")
    return months


def yearRange(year):
    """@brief Return the [start, end) datetime strings bounding a calendar year."""
    return f"{year:04d}-01-01 00:00:00", f"{year + 1:04d}-01-01 00:00:00"


def iterMonthRanges(year):
    """@brief Yield (start, end, label) [start, end) datetime bounds for each
              month of a year, so the analysis can be run in progress-reporting
              chunks instead of one long query.
       @param year The calendar year.
       @return A generator of (start_str, end_str, label) tuples."""
    for month in range(1, 13):
        start = f"{year:04d}-{month:02d}-01 00:00:00"
        if month == 12:
            end = f"{year + 1:04d}-01-01 00:00:00"
        else:
            end = f"{year:04d}-{month + 1:02d}-01 00:00:00"
        yield start, end, f"{year:04d}-{month:02d}"


def _progress(msg):
    """@brief Write a progress line to stderr and flush immediately so the user
              sees it while the server is still working."""
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()


def serverVersion(cursor):
    """@brief Read and assess the database server version.

       Window functions (LAG), used by this tool, need MySQL 8.0+ or, for
       MariaDB, 10.2+.

       @param cursor A DB-API cursor.
       @return A tuple of (version_string, ok, requirement_text)."""
    cursor.execute("SELECT VERSION();")
    verStr = str(cursor.fetchone()[0])
    isMariaDB = "mariadb" in verStr.lower()

    match = re.match(r'(\d+)\.(\d+)', verStr)
    if not match:
        # Could not parse - do not block the user, just report what we saw.
        return verStr, True, "MySQL 8.0+ / MariaDB 10.2+"

    major, minor = int(match.group(1)), int(match.group(2))
    if isMariaDB:
        ok = (major, minor) >= (10, 2)
        requirement = "MariaDB 10.2+"
    else:
        ok = major >= 8
        requirement = "MySQL 8.0+"
    return verStr, ok, requirement


def buildDailyOnTimeSQL(database, table, column, maxGapSeconds):
    """@brief Build the per-day aggregation query.

       For each sample the time gap to the previous sample is computed with LAG,
       clamped to [0, maxGapSeconds]. Per day we sum those gaps for samples
       at/above the threshold (on_seconds), and also report the peak power and
       the number of samples so the result can be sanity checked.

       @return A tuple of (sql, placeholder_order) where placeholder_order names
               the parameters in the order the %s placeholders appear."""
    database = _validateIdentifier(database, "database name")
    table = _validateIdentifier(table, "table name")
    column = _validateIdentifier(column, "column name")

    sql = f"""
SELECT
    DATE(sub.ts)                                        AS day,
    SUM(CASE WHEN sub.on_sample = 1 THEN sub.gap END)   AS on_seconds,
    MAX(sub.w)                                          AS peak_watts,
    COUNT(*)                                            AS sample_count
FROM (
    SELECT
        `{TIMESTAMP_COL}`                               AS ts,
        ABS(`{column}`)                                 AS w,
        (ABS(`{column}`) >= %s)                         AS on_sample,
        LEAST(
            GREATEST(
                COALESCE(
                    TIMESTAMPDIFF(
                        SECOND,
                        LAG(`{TIMESTAMP_COL}`) OVER (ORDER BY `{TIMESTAMP_COL}`),
                        `{TIMESTAMP_COL}`
                    ),
                    0
                ),
                0
            ),
            %s
        )                                               AS gap
    FROM `{database}`.`{table}`
    WHERE `{TIMESTAMP_COL}` >= %s AND `{TIMESTAMP_COL}` < %s
) AS sub
GROUP BY DATE(sub.ts)
ORDER BY day ASC;
"""
    placeholderOrder = ("threshold", "max_gap", "start", "end")
    return sql, placeholderOrder


def classifyDays(rows, minMinutes, coolingMonths):
    """@brief Turn per-day rows into a classification and summary.
       @param rows Iterable of (day, on_seconds, peak_watts, sample_count).
                   'day' may be a datetime.date or an ISO date string.
       @param minMinutes Minimum on-minutes for a day to count as "on".
       @param coolingMonths A set of month numbers treated as cooling.
       @return A tuple of (detailRows, summary) where detailRows is a list of
               dicts (one per day with data) and summary is a dict of counts."""
    minSeconds = minMinutes * 60.0

    detail = []
    heatingDays = 0
    coolingDays = 0

    for row in rows:
        day, onSeconds, peakWatts, sampleCount = row[0], row[1], row[2], row[3]

        # Normalise the day into a datetime.date.
        if isinstance(day, date):
            dayDate = day
        else:
            dayDate = date.fromisoformat(str(day)[:10])

        onSeconds = float(onSeconds) if onSeconds is not None else 0.0
        onMinutes = onSeconds / 60.0
        isOn = onSeconds >= minSeconds

        if isOn:
            if dayDate.month in coolingMonths:
                mode = "cooling"
                coolingDays += 1
            else:
                mode = "heating"
                heatingDays += 1
        else:
            mode = "off"

        detail.append({
            "date": dayDate.isoformat(),
            "on_minutes": round(onMinutes, 1),
            "peak_watts": round(float(peakWatts), 1) if peakWatts is not None else 0.0,
            "samples": int(sampleCount),
            "on": isOn,
            "mode": mode,
        })

    summary = {
        "days_with_data": len(detail),
        "on_days": heatingDays + coolingDays,
        "heating_days": heatingDays,
        "cooling_days": coolingDays,
    }
    return detail, summary


def writeDetailCSV(path, detail):
    """@brief Write the per-day detail rows to a CSV file."""
    fields = ["date", "on_minutes", "peak_watts", "samples", "on", "mode"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in detail:
            writer.writerow(row)


def main():
    """@brief Program entry point."""
    parser = argparse.ArgumentParser(
        description="Count heating and cooling days in a year for a heat pump "
                    "measured on one CT port of a CT6 device.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Examples")[-1] if "Examples" in __doc__ else None,
    )

    # Connection / credentials (same options as ct6_db_to_csv.py).
    parser.add_argument("-H", "--host", default="127.0.0.1",
                        help="MySQL server address (default=127.0.0.1).")
    parser.add_argument("-P", "--port-number", type=int, default=3306, dest="db_port",
                        help="MySQL server TCP port (default=3306).")
    parser.add_argument("-u", "--user", default="root",
                        help="MySQL user name (default=root).")
    parser.add_argument("-p", "--password", default=None,
                        help="MySQL password. Omit for no password, or use "
                             "--ask-password to be prompted.")
    parser.add_argument("--ask-password", action="store_true",
                        help="Prompt for the MySQL password (hidden input).")
    parser.add_argument("-d", "--database", required=True,
                        help="The database to read (one CT6 unit per database).")
    parser.add_argument("-t", "--table", default=SENSOR_TABLE,
                        help=f"The sensor table to read (default={SENSOR_TABLE}).")

    # Analysis parameters.
    parser.add_argument("--port", type=int, required=True,
                        help="CT port the heat pump is on (1..6). Uses the "
                             "CT<port>_ACT_WATTS active power column.")
    parser.add_argument("--threshold", type=float, required=True,
                        help="Power (watts) at/above which the heat pump is "
                             "considered to be running.")
    parser.add_argument("--year", type=int, required=True,
                        help="Calendar year to analyse, e.g. 2024.")
    parser.add_argument("--min-minutes", type=float, default=10.0,
                        help="Minimum run-time (minutes) in a day for it to "
                             "count as an on day (default=10).")
    parser.add_argument("--max-gap-seconds", type=float, default=300.0,
                        help="Cap applied to the gap between samples when "
                             "summing run-time, so an offline device is not "
                             "counted as running (default=300).")
    parser.add_argument("--cooling-months", default=None,
                        help="Comma separated month numbers treated as cooling "
                             "(default=5,6,7,8,9). All other months are heating.")

    # Output.
    parser.add_argument("--csv", default=None,
                        help="Optional path to write per-day detail as CSV "
                             "(date, on_minutes, peak_watts, samples, on, mode).")
    parser.add_argument("--debug", action="store_true",
                        help="Print the SQL and full tracebacks on error.")

    options = parser.parse_args()

    # Resolve password.
    password = options.password
    if options.ask_password:
        password = getpass.getpass("MySQL password: ")
    if password is None:
        password = ""

    conn = None
    try:
        column = portToColumn(options.port)

        if options.cooling_months:
            coolingMonths = parseCoolingMonths(options.cooling_months)
        else:
            coolingMonths = set(DEFAULT_COOLING_MONTHS)

        _progress(f"Connecting to {options.host}:{options.db_port} "
                  f"(database '{options.database}') ...")
        conn, driver = _connect(options.host, options.db_port, options.user,
                                password, database=options.database)
        _progress(f"Connected using the {driver} driver.")

        cur = conn.cursor()

        # Check the server supports the window functions this tool relies on.
        _progress("Checking server version ...")
        versionStr, versionOk, requirement = serverVersion(cur)
        _progress(f"Server version: {versionStr}")
        if not versionOk:
            raise Exception(
                f"This tool needs {requirement} because it uses the LAG window "
                f"function. The server reports version '{versionStr}'."
            )

        sql, order = buildDailyOnTimeSQL(options.database, options.table,
                                         column, options.max_gap_seconds)
        if options.debug:
            sys.stderr.write(f"SQL:{sql}\n")

        # Run the analysis a month at a time so progress can be shown and each
        # query is smaller for the server to process. The result is ~365 daily
        # rows regardless.
        _progress(f"Analysing {options.year} month by month "
                  f"(this can take a while on large tables) ...")
        rows = []
        overallStart = time.time()
        for monthStart, monthEnd, label in iterMonthRanges(options.year):
            paramValues = {
                "threshold": options.threshold,
                "max_gap": options.max_gap_seconds,
                "start": monthStart,
                "end": monthEnd,
            }
            params = tuple(paramValues[name] for name in order)

            monthT0 = time.time()
            cur.execute(sql, params)
            monthRows = cur.fetchall()
            rows.extend(monthRows)
            _progress(f"  {label}: {len(monthRows):>2} day(s) with data "
                      f"({time.time() - monthT0:.1f}s)")

        cur.close()
        _progress(f"Query complete in {time.time() - overallStart:.1f}s. "
                  f"Classifying days ...")

        detail, summary = classifyDays(rows, options.min_minutes, coolingMonths)

        if options.csv:
            writeDetailCSV(options.csv, detail)

        # Report.
        seasonStr = ",".join(str(m) for m in sorted(coolingMonths))
        print( "CT6 heat pump run-time analysis")
        print(f"  Database / table : {options.database}.{options.table}")
        print(f"  Port / column    : {options.port} ({column})")
        print(f"  Year             : {options.year}")
        print(f"  Threshold        : {options.threshold:g} W")
        print(f"  Min run-time/day : {options.min_minutes:g} min")
        print(f"  Cooling months   : {seasonStr}")
        print( "  ---")
        print(f"  Days with data   : {summary['days_with_data']}")
        print(f"  On days (total)  : {summary['on_days']}")
        print(f"    Heating days   : {summary['heating_days']}")
        print(f"    Cooling days   : {summary['cooling_days']}")
        if options.csv:
            sys.stderr.write(f"Per-day detail written to {options.csv}\n")

    except KeyboardInterrupt:
        pass
    except Exception as ex:
        if options.debug:
            raise
        sys.stderr.write(f"ERROR: {ex}\n")
        sys.exit(1)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
