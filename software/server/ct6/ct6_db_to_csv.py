#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""
ct6_db_to_csv.py

Read CT6 sensor data from the MySQL database populated by ct6_db_store and
write selected fields to a CSV file.

The ct6_db_store application stores one MySQL *database* per CT6 unit (named
after the unit). Each database contains the tables:

    CT6_SENSOR          - full resolution sensor data (default)
    CT6_SENSOR_MINUTE   - 1 minute averaged data
    CT6_SENSOR_HOUR     - 1 hour averaged data
    CT6_SENSOR_DAY      - 1 day averaged data
    CT6_META            - unit / port name meta data

The sensor tables share these columns:

    TIMESTAMP
    CT1_ACT_WATTS   .. CT6_ACT_WATTS      (active power)
    CT1_REACT_WATTS .. CT6_REACT_WATTS    (reactive power)
    CT1_APP_WATTS   .. CT6_APP_WATTS      (apparent power)
    CT1_PF          .. CT6_PF             (power factor)
    VOLTAGE
    FREQUENCY
    BOARD_TEMPERATURE
    RSSI_DBM

Examples
--------
List the CT6 databases on a server:
    ct6_db_to_csv.py -H 192.168.0.10 -u root -p secret --list-dbs

List the columns available in a table:
    ct6_db_to_csv.py -H 192.168.0.10 -u root -p secret -d MY_CT6 --list-fields

Export the whole CT6_SENSOR table to a CSV file:
    ct6_db_to_csv.py -H 192.168.0.10 -u root -p secret -d MY_CT6 -o out.csv

Export selected fields for a date range to a CSV file:
    ct6_db_to_csv.py -H 192.168.0.10 -u root -p secret -d MY_CT6 \\
        -f TIMESTAMP,CT1_ACT_WATTS,VOLTAGE \\
        --from "2024-01-01 00:00:00" --to "2024-02-01 00:00:00" -o jan.csv
"""

import sys
import csv
import argparse
import getpass
import re

# ---------------------------------------------------------------------------
# Database driver abstraction.
#
# ct6_db_store depends on both mysql-connector-python and mysqlclient (MySQLdb),
# so at least one of these is normally available. We use whichever we find and
# talk to it purely through the DB-API 2.0 interface, taking column headers from
# cursor.description so we do not depend on any driver specific dict cursor.
# ---------------------------------------------------------------------------

# Valid MySQL identifier (table / column / database name). Used to reject
# anything that could be an injection attempt before we backtick-quote it.
_IDENTIFIER_RE = re.compile(r'^[0-9A-Za-z_$]+$')

DEFAULT_TABLE = "CT6_SENSOR"
TIMESTAMP_COL = "TIMESTAMP"


def _connect(host, port, user, password, database=None):
    """@brief Connect to a MySQL server using whatever driver is installed.
       @param host The server address.
       @param port The server TCP port.
       @param user The database user name.
       @param password The database password (may be an empty string).
       @param database Optional database (schema) to select on connect.
       @return A tuple of (connection, driver_name)."""
    lastError = None

    # 1. mysql-connector-python (pure python, import name mysql.connector).
    try:
        import mysql.connector as mysql_connector
        conn = mysql_connector.connect(
            host=host,
            port=int(port),
            user=user,
            password=password,
            database=database,
        )
        return conn, "mysql.connector"
    except ImportError:
        pass
    except Exception as ex:                      # connection / auth error
        lastError = ex

    # 2. mysqlclient (MySQLdb) - the driver ct6_db_store itself uses.
    try:
        import MySQLdb
        kwargs = dict(host=host, port=int(port), user=user, passwd=password)
        if database:
            kwargs["db"] = database
        conn = MySQLdb.connect(**kwargs)
        return conn, "MySQLdb"
    except ImportError:
        pass
    except Exception as ex:
        lastError = ex

    # 3. PyMySQL as a last resort.
    try:
        import pymysql
        conn = pymysql.connect(
            host=host,
            port=int(port),
            user=user,
            password=password,
            database=database,
        )
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
    """@brief Ensure a name is a safe SQL identifier.
       @param name The identifier to check.
       @param what A human readable description used in any error message.
       @return The validated identifier."""
    if not name or not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid {what}: '{name}'.")
    return name


def _fetchOne(cursor, sql, params=None):
    cursor.execute(sql, params or ())
    return cursor.fetchall()


def listDatabases(cursor, ct6Only=True):
    """@brief Return a list of database names on the server.
       @param cursor A DB-API cursor.
       @param ct6Only If True only return databases that contain a CT6_SENSOR table.
       @return A list of database names."""
    rows = _fetchOne(cursor, "SHOW DATABASES;")
    allDbs = [r[0] for r in rows]
    if not ct6Only:
        return allDbs

    ct6Dbs = []
    for dbName in allDbs:
        try:
            cursor.execute(f"SHOW TABLES IN `{dbName}`;")
            tables = [r[0] for r in cursor.fetchall()]
            if DEFAULT_TABLE in tables:
                ct6Dbs.append(dbName)
        except Exception:
            # System databases we cannot read - just skip them.
            continue
    return ct6Dbs


def listTables(cursor, database):
    """@brief Return a list of table names in a database."""
    database = _validateIdentifier(database, "database name")
    rows = _fetchOne(cursor, f"SHOW TABLES IN `{database}`;")
    return [r[0] for r in rows]


def getColumns(cursor, database, table):
    """@brief Return the ordered list of column names for a table.
       @return A list of (column_name, column_type) tuples."""
    database = _validateIdentifier(database, "database name")
    table = _validateIdentifier(table, "table name")
    rows = _fetchOne(cursor, f"DESCRIBE `{database}`.`{table}`;")
    # DESCRIBE returns: Field, Type, Null, Key, Default, Extra
    return [(r[0], r[1]) for r in rows]


def buildSelectSQL(database, table, fields, fromTS, toTS, order, maxRows):
    """@brief Build the parameterised SELECT statement and its parameters.
       @return A tuple of (sql, params)."""
    database = _validateIdentifier(database, "database name")
    table = _validateIdentifier(table, "table name")

    colExpr = ", ".join(f"`{c}`" for c in fields)

    sql = f"SELECT {colExpr} FROM `{database}`.`{table}`"

    where = []
    params = []
    if fromTS:
        where.append(f"`{TIMESTAMP_COL}` >= %s")
        params.append(fromTS)
    if toTS:
        where.append(f"`{TIMESTAMP_COL}` <= %s")
        params.append(toTS)
    if where:
        sql += " WHERE " + " AND ".join(where)

    sql += f" ORDER BY `{TIMESTAMP_COL}` {order}"

    if maxRows and maxRows > 0:
        sql += " LIMIT %s"
        params.append(int(maxRows))

    return sql, tuple(params)


def exportToCSV(cursor, sql, params, outFile, batchSize, delimiter):
    """@brief Run the query and stream the result to a CSV file object.
       @param cursor A DB-API cursor.
       @param sql The SELECT statement.
       @param params Query parameters.
       @param outFile An open, writable text file object.
       @param batchSize Rows to fetch per round trip.
       @param delimiter CSV field delimiter.
       @return The number of data rows written."""
    cursor.execute(sql, params)

    header = [d[0] for d in cursor.description]
    writer = csv.writer(outFile, delimiter=delimiter, lineterminator="\n")
    writer.writerow(header)

    rowCount = 0
    while True:
        rows = cursor.fetchmany(batchSize)
        if not rows:
            break
        writer.writerows(rows)
        rowCount += len(rows)
    return rowCount


def _unbufferedCursor(conn, driver):
    """@brief Try to obtain a server side / unbuffered cursor so that large
              tables are streamed rather than fully buffered in memory.
       @return A cursor (unbuffered where the driver supports it)."""
    try:
        if driver == "MySQLdb":
            import MySQLdb.cursors
            return conn.cursor(MySQLdb.cursors.SSCursor)
        if driver == "pymysql":
            import pymysql.cursors
            return conn.cursor(pymysql.cursors.SSCursor)
        if driver == "mysql.connector":
            # buffered=False streams rows from the server for this cursor.
            return conn.cursor(buffered=False)
    except Exception:
        pass
    return conn.cursor()


def _resolveFields(requested, availableCols):
    """@brief Resolve and validate the user requested fields against the table.
       @param requested Comma separated field string, or None for all fields.
       @param availableCols Ordered list of (name, type) tuples from the table.
       @return The ordered list of column names to export."""
    available = [c[0] for c in availableCols]
    if not requested:
        return available

    # Case-insensitive lookup so the user need not match the exact case.
    lowerMap = {c.lower(): c for c in available}
    resolved = []
    unknown = []
    for raw in requested.split(","):
        name = raw.strip()
        if not name:
            continue
        actual = lowerMap.get(name.lower())
        if actual is None:
            unknown.append(name)
        elif actual not in resolved:
            resolved.append(actual)

    if unknown:
        raise ValueError(
            "Unknown field(s): {}. Available fields: {}".format(
                ", ".join(unknown), ", ".join(available)
            )
        )
    if not resolved:
        raise ValueError("No valid fields selected.")
    return resolved


def main():
    """@brief Program entry point."""
    parser = argparse.ArgumentParser(
        description="Read CT6 sensor data from the MySQL database written by "
                    "ct6_db_store and export selected fields to a CSV file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Examples")[-1] if "Examples" in __doc__ else None,
    )

    # Connection / credentials.
    parser.add_argument("-H", "--host", default="127.0.0.1",
                        help="MySQL server address (default=127.0.0.1).")
    parser.add_argument("-P", "--port", type=int, default=3306,
                        help="MySQL server TCP port (default=3306).")
    parser.add_argument("-u", "--user", default="root",
                        help="MySQL user name (default=root).")
    parser.add_argument("-p", "--password", default=None,
                        help="MySQL password. Omit for no password, or use "
                             "--ask-password to be prompted.")
    parser.add_argument("--ask-password", action="store_true",
                        help="Prompt for the MySQL password (hidden input).")

    # What to read.
    parser.add_argument("-d", "--database", default=None,
                        help="The database to read (one CT6 unit per database).")
    parser.add_argument("-t", "--table", default=DEFAULT_TABLE,
                        help=f"The table to read (default={DEFAULT_TABLE}). "
                             "Low res tables: CT6_SENSOR_MINUTE, CT6_SENSOR_HOUR, "
                             "CT6_SENSOR_DAY.")
    parser.add_argument("-f", "--fields", default=None,
                        help="Comma separated list of fields (columns) to export. "
                             "Default is all fields. Use --list-fields to see them.")

    # Filtering.
    parser.add_argument("--from", dest="from_ts", default=None,
                        help="Only export rows on/after this timestamp, "
                             "e.g. \"2024-01-01 00:00:00\".")
    parser.add_argument("--to", dest="to_ts", default=None,
                        help="Only export rows on/before this timestamp, "
                             "e.g. \"2024-02-01 00:00:00\".")
    parser.add_argument("-n", "--max-rows", type=int, default=0,
                        help="Limit the number of rows exported (0 = no limit).")
    parser.add_argument("--order", choices=("asc", "desc"), default="asc",
                        help="Row order by TIMESTAMP (default=asc).")

    # Output.
    parser.add_argument("-o", "--out", default=None,
                        help="Output CSV file (default: write to stdout).")
    parser.add_argument("--delimiter", default=",",
                        help="CSV field delimiter (default=',').")
    parser.add_argument("--batch-size", type=int, default=5000,
                        help="Rows fetched per DB round trip (default=5000).")

    # Discovery helpers.
    parser.add_argument("--list-dbs", action="store_true",
                        help="List CT6 databases on the server and exit.")
    parser.add_argument("--all-dbs", action="store_true",
                        help="With --list-dbs, list every database, not just CT6 ones.")
    parser.add_argument("--list-tables", action="store_true",
                        help="List tables in --database and exit.")
    parser.add_argument("--list-fields", action="store_true",
                        help="List the fields (columns) of --table and exit.")

    parser.add_argument("--debug", action="store_true",
                        help="Print full tracebacks on error.")

    options = parser.parse_args()

    # Resolve the password.
    password = options.password
    if options.ask_password:
        password = getpass.getpass("MySQL password: ")
    if password is None:
        password = ""   # matches ct6_db_store default of an empty password.

    conn = None
    try:
        needDB = not options.list_dbs
        conn, driver = _connect(
            options.host, options.port, options.user, password,
            database=options.database if needDB and options.database else None,
        )

        # ---- Discovery helpers -------------------------------------------
        if options.list_dbs:
            cur = conn.cursor()
            for dbName in listDatabases(cur, ct6Only=not options.all_dbs):
                print(dbName)
            cur.close()
            return

        if options.list_tables:
            if not options.database:
                raise ValueError("--database is required with --list-tables.")
            cur = conn.cursor()
            for tableName in listTables(cur, options.database):
                print(tableName)
            cur.close()
            return

        if options.list_fields:
            if not options.database:
                raise ValueError("--database is required with --list-fields.")
            cur = conn.cursor()
            for name, colType in getColumns(cur, options.database, options.table):
                print(f"{name}\t{colType}")
            cur.close()
            return

        # ---- Export ------------------------------------------------------
        if not options.database:
            raise ValueError("--database is required (use --list-dbs to find it).")

        # Validate table and resolve the requested fields against the real schema.
        cur = conn.cursor()
        cols = getColumns(cur, options.database, options.table)
        if not cols:
            raise ValueError(
                f"Table '{options.table}' has no columns / does not exist in "
                f"database '{options.database}'."
            )
        fields = _resolveFields(options.fields, cols)
        cur.close()

        sql, params = buildSelectSQL(
            options.database, options.table, fields,
            options.from_ts, options.to_ts, options.order.upper(),
            options.max_rows,
        )
        if options.debug:
            sys.stderr.write(f"Driver: {driver}\nSQL: {sql}\nParams: {params}\n")

        exportCur = _unbufferedCursor(conn, driver)

        if options.out:
            with open(options.out, "w", newline="", encoding="utf-8") as fh:
                rowCount = exportToCSV(exportCur, sql, params, fh,
                                       options.batch_size, options.delimiter)
            sys.stderr.write(
                f"Wrote {rowCount} rows ({len(fields)} fields) to {options.out}\n"
            )
        else:
            rowCount = exportToCSV(exportCur, sql, params, sys.stdout,
                                   options.batch_size, options.delimiter)
            sys.stderr.write(f"Wrote {rowCount} rows ({len(fields)} fields).\n")

        exportCur.close()

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
