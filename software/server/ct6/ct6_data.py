#!/usr/bin/env python3
"""@brief Backend independent CT6 dashboard data logic.

   Nothing in this module touches a database or a GUI so that it can be shared
   by ct6_dash2 (NiceGUI) and any other front end, and unit tested on its own.
   The algorithms (date presets, kWh calculation, peak day search) mirror those
   in ct6_dash_gui.py / gui_base.py so results match ct6_dash."""

import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum

from dateutil.relativedelta import relativedelta

from lib.base_constants import BaseConstants

SENSOR_COUNT = 6
TIMESTAMP = BaseConstants.TIMESTAMP
X_FORMAT = "%Y-%m-%d %H:%M:%S"
HOURS_PER_DAY = 24


class Resolution(Enum):
    """@brief The plot resolutions. The value is the label shown to the user."""
    SEC = "Sec"
    MIN = "Min"
    HOUR = "Hour"
    DAY = "Day"

    @property
    def table_name(self):
        """@return The name of the database table holding data at this resolution."""
        return {Resolution.SEC: BaseConstants.MAX_RES_DB_DATA_TABLE_NAME,
                Resolution.MIN: BaseConstants.MINUTE_RES_DB_DATA_TABLE_NAME,
                Resolution.HOUR: BaseConstants.HOUR_RES_DB_DATA_TABLE_NAME,
                Resolution.DAY: BaseConstants.DAY_RES_DB_DATA_TABLE_NAME}[self]


class PowerType(Enum):
    ACTIVE = "Active"
    REACTIVE = "Reactive"
    APPARENT = "Apparent"


class Polarity(Enum):
    IMPORT_POSITIVE = "Import is positive"
    IMPORT_NEGATIVE = "Import is negative"


class PlotType(Enum):
    """@brief The things that can be plotted. The value is the label shown to the user."""
    POWER = "Power"
    POWER_FACTOR = "Power Factor"
    AC_VOLTS = "AC Voltage"
    AC_FREQ = "AC Frequency"
    TEMPERATURE = "Temperature"
    RSSI = "WiFi RSSI"

    @property
    def is_per_ct(self):
        """@return True if this plot has one trace per CT port."""
        return self in (PlotType.POWER, PlotType.POWER_FACTOR)

    @property
    def single_field(self):
        """@return The DB column for single trace plots, else None."""
        return {PlotType.AC_VOLTS: BaseConstants.VOLTAGE,
                PlotType.AC_FREQ: BaseConstants.FREQUENCY,
                PlotType.TEMPERATURE: BaseConstants.TEMPERATURE,
                PlotType.RSSI: BaseConstants.RSSI_DBM}.get(self)

    def y_axis_label(self, power_type=PowerType.ACTIVE):
        """@return The Y axis label for this plot."""
        if self == PlotType.POWER:
            return "kW" if power_type == PowerType.ACTIVE else "kVA"
        return {PlotType.POWER_FACTOR: "Power Factor",
                PlotType.AC_VOLTS: "Volts",
                PlotType.AC_FREQ: "Hz",
                PlotType.TEMPERATURE: "°C",
                PlotType.RSSI: "dBm"}[self]

    def single_trace_name(self):
        return {PlotType.AC_VOLTS: "AC Voltage",
                PlotType.AC_FREQ: "AC Frequency",
                PlotType.TEMPERATURE: "CT6 device Temperature",
                PlotType.RSSI: "WiFi RSSI"}.get(self)


def act_watts_field(ct_number):
    """@param ct_number 1-6
       @return The active power DB column for the CT port."""
    return f"CT{ct_number}_ACT_WATTS"


def ct_field(ct_number, plot_type, power_type=PowerType.ACTIVE):
    """@brief Get the DB column to plot for a CT port.
       @param ct_number 1-6
       @param plot_type PlotType.POWER or PlotType.POWER_FACTOR
       @param power_type The PowerType (POWER plots only).
       @return The column name."""
    if plot_type == PlotType.POWER_FACTOR:
        return f"CT{ct_number}_PF"
    return {PowerType.ACTIVE: f"CT{ct_number}_ACT_WATTS",
            PowerType.REACTIVE: f"CT{ct_number}_REACT_WATTS",
            PowerType.APPARENT: f"CT{ct_number}_APP_WATTS"}[power_type]


@dataclass
class DeviceInfo:
    """@brief Details of a single CT6 device (one MySQL database or one SQLite file)."""
    device_id: str          # Unique key used by the data source (DB name or file path)
    name: str               # Name shown on the tab
    ct_names: tuple = field(default_factory=lambda: ("",) * SENSOR_COUNT)
    hw_assy: str = ""

    def active_cts(self):
        """@return A list of (ct_number, name) for CT ports that have a name."""
        return [(i + 1, n) for i, n in enumerate(self.ct_names) if n]

    @staticmethod
    def from_meta_row(device_id, name, meta_row):
        """@brief Build from a CT6_META table row dict."""
        meta_row = meta_row or {}
        ct_names = tuple((meta_row.get(f"CT{i}_NAME") or "") for i in range(1, SENSOR_COUNT + 1))
        return DeviceInfo(device_id, name, ct_names, meta_row.get(BaseConstants.HW_ASSY) or "")


# ---------------------------------------------------------------- date/time

@dataclass
class DateRange:
    """@brief The values shown in the date/time controls."""
    start_date: date
    start_time: str
    stop_date: date
    stop_time: str
    resolution: Resolution


PRESETS = ("Today", "Yesterday", "This week", "Last week",
           "This month", "Last month", "This year", "Last year")


def preset_range(preset, now=None):
    """@brief Get the date range for one of the PRESETS (as ct6_dash's preset buttons).
       @param preset One of PRESETS.
       @param now The current local datetime (for testing).
       @return A DateRange."""
    now = now or datetime.now()
    today = now.date()
    if preset == "Today":
        return DateRange(today, "00:00", today, "23:59", Resolution.MIN)
    if preset == "Yesterday":
        y = today - timedelta(days=1)
        return DateRange(y, "00:00", y, "23:59", Resolution.MIN)
    if preset in ("This week", "Last week"):
        start = today - timedelta(days=today.weekday() + (7 if preset == "Last week" else 0))
        return DateRange(start, "00:00", start + timedelta(days=6), "23:59", Resolution.MIN)
    if preset == "This month":
        last = calendar.monthrange(today.year, today.month)[1]
        return DateRange(today.replace(day=1), "00:00", today.replace(day=last), "23:59", Resolution.HOUR)
    if preset == "Last month":
        first_this = today.replace(day=1)
        return DateRange(first_this - relativedelta(months=1), "00:00",
                         first_this - timedelta(days=1), "23:59", Resolution.HOUR)
    if preset in ("This year", "Last year"):
        year = today.year - (1 if preset == "Last year" else 0)
        return DateRange(date(year, 1, 1), "00:00", date(year, 12, 31), "23:59", Resolution.HOUR)
    raise ValueError(f"Unknown preset: {preset}")


def parse_start_stop(start_date, start_time, stop_date, stop_time):
    """@brief Convert the date/time control values to datetimes.
       @param start_date A date or ISO format date string.
       @param start_time HH:MM
       @param stop_date A date or ISO format date string.
       @param stop_time HH:MM
       @return (start_datetime, stop_datetime). The stop time includes the whole of the stop minute.
       @raise ValueError if the values are invalid or stop is not after start."""
    def _dt(d, t, label):
        try:
            d = d if isinstance(d, date) else date.fromisoformat(str(d).strip())
            hm = datetime.strptime(str(t).strip(), "%H:%M")
        except (ValueError, TypeError):
            raise ValueError(f"The {label} date/time is not correct.")
        return datetime(d.year, d.month, d.day, hm.hour, hm.minute)

    start_dt = _dt(start_date, start_time, "start")
    stop_dt = _dt(stop_date, stop_time, "stop").replace(second=59, microsecond=999999)
    if start_dt >= stop_dt:
        raise ValueError("Stop must be after the start date.")
    return start_dt, stop_dt


# ---------------------------------------------------------------- plotting

def _x(ts):
    return ts.strftime(X_FORMAT)


def build_series(rows, column, resolution, invert=False, is_power=True):
    """@brief Build the [x, y] points for one trace (as ct6_dash's _addToPlot()).
       @param rows The DB rows (dicts with a TIMESTAMP datetime).
       @param column The DB column to plot.
       @param resolution The Resolution. HOUR/DAY data gets a second point at the
              end of each period so the plot is stepped.
       @param invert If True negate the values (power plots only).
       @param is_power True for power columns (W → kW, may be inverted).
              False for PF (abs value) and single field plots (raw value).
       @return A list of [x_string, y] points."""
    points = []
    for row in rows:
        ts = row[TIMESTAMP]
        value = row.get(column)
        if value is None:
            continue
        if is_power:
            value = (-value if invert else value) / 1000.0
        y = round(value, 4)
        points.append([_x(ts), y])
        if resolution == Resolution.HOUR:
            points.append([_x(ts.replace(minute=59, second=59)), y])
        elif resolution == Resolution.DAY:
            points.append([_x(ts.replace(hour=23, minute=59, second=59)), y])
    return points


def downsample_minmax(points, max_points):
    """@brief Reduce the number of points sent to the browser while keeping peaks.
              The points are split into buckets and the min and max of each bucket
              are kept (in time order).
       @param points A list of [x, y] points.
       @param max_points The maximum number of points to return (>= 4).
       @return The (possibly reduced) list of points."""
    n = len(points)
    if max_points is None or max_points <= 0 or n <= max_points:
        return points
    max_points = max(4, max_points)
    bucket_count = max_points // 2
    out = []
    for b in range(bucket_count):
        lo = b * n // bucket_count
        hi = (b + 1) * n // bucket_count
        if hi <= lo:
            continue
        bucket = points[lo:hi]
        i_min = min(range(len(bucket)), key=lambda i: bucket[i][1])
        i_max = max(range(len(bucket)), key=lambda i: bucket[i][1])
        for i in sorted({i_min, i_max}):
            out.append(bucket[i])
    return out


# ---------------------------------------------------------------- live

LIVE_WINDOW = timedelta(minutes=15)
LIVE_OK_SECS = 10
LIVE_STALE_SECS = 60
LIVE_FIELDS = (BaseConstants.VOLTAGE, BaseConstants.FREQUENCY, BaseConstants.TEMPERATURE, BaseConstants.RSSI_DBM)


def live_status(age_secs):
    """@brief Classify how fresh a device's data is.
       @param age_secs Seconds since the newest row, or None if there is no data.
       @return "ok" (< 10 s), "stale" (< 60 s) or "offline"."""
    if age_secs is None or age_secs >= LIVE_STALE_SECS:
        return "offline"
    return "ok" if age_secs < LIVE_OK_SECS else "stale"


def format_age(age_secs):
    """@return A short 'time since' string, e.g. '3 s ago', '5 min ago', '2 h ago', '4 days ago'."""
    if age_secs is None:
        return "no data"
    age_secs = max(0, int(age_secs))
    if age_secs < 60:
        return f"{age_secs} s ago"
    if age_secs < 3600:
        return f"{age_secs // 60} min ago"
    if age_secs < 86400:
        return f"{age_secs // 3600} h ago"
    days = age_secs // 86400
    return f"{days} day{'s' if days != 1 else ''} ago"


def live_columns(device):
    """@return The DB columns the Live tab needs for a device (keeps worker messages small)."""
    return [TIMESTAMP] + [act_watts_field(n) for n, _ in device.active_cts()] + list(LIVE_FIELDS)


def merge_live_rows(existing, new_rows, now, window=LIVE_WINDOW):
    """@brief Append new rows to a device's rolling Live window and drop rows older than the window.
       @param existing The current list of rows (oldest first).
       @param new_rows Newer rows (oldest first).
       @param now The current datetime.
       @return The new list of rows."""
    cutoff = now - window
    rows = existing + list(new_rows)
    i = 0
    while i < len(rows) and rows[i][TIMESTAMP] < cutoff:
        i += 1
    return rows[i:]


# ---------------------------------------------------------------- kWh

@dataclass
class KWhResult:
    total: float
    positive: float
    negative: float


def calc_kwh(rows, column, invert=False):
    """@brief Calculate kWh from active power readings (as ct6_dash's _calcKWH()).
              Each reading is multiplied by the time since the previous reading.
       @param rows The DB rows (dicts with a TIMESTAMP datetime).
       @param column The xxx_ACT_WATTS column.
       @param invert If True negate the values first.
       @return A KWhResult."""
    total = pos = neg = 0.0
    last_time = None
    for row in rows:
        this_time = row[TIMESTAMP]
        watts = row.get(column)
        if watts is None:
            continue
        if invert:
            watts = -watts
        if last_time is not None:
            wh = (this_time - last_time).total_seconds() / 3600.0 * watts
            if wh >= 0.0:
                pos += wh
            else:
                neg += wh
            total += wh
        last_time = this_time
    return KWhResult(total / 1000.0, pos / 1000.0, neg / 1000.0)


def summary_row(ct_number, sensor_name, kwh, invert=False):
    """@brief Build a kWh summary table row (as ct6_dash's _updateSummaryTable()).
              The positive/negative columns are swapped back when inverted so
              that they always refer to the same direction of power flow.
       @return A dict with ct, sensor, total, positive, negative (strings)."""
    pos, neg = (kwh.negative, kwh.positive) if invert else (kwh.positive, kwh.negative)
    return {"ct": ct_number,
            "sensor": sensor_name,
            "total": f"{kwh.total:.2f}",
            "positive": f"{pos:.2f}",
            "negative": f"{neg:.2f}"}


# ---------------------------------------------------------------- peak day

@dataclass
class PeakDayResult:
    peak_day: object        # date or None
    peak_kwh: float         # None if no complete days
    total_days: int
    incomplete_days: int


def peak_daily_kwh(day_records):
    """@brief Find the day with the largest absolute daily kWh (as ct6_dash's _findPeakDailyKWh()).
              Days without a full set of 24 hourly samples are ignored.
       @param day_records Iterable of dicts with day, avg_w and sample_count keys
              (from the hour resolution table grouped by day).
       @return A PeakDayResult."""
    peak_day = None
    peak_kwh = None
    total = incomplete = 0
    for rec in day_records:
        avg_w = rec.get("avg_w")
        day = rec.get("day")
        count = rec.get("sample_count")
        if avg_w is None or day is None:
            continue
        total += 1
        if count is None or count < HOURS_PER_DAY:
            incomplete += 1
            continue
        daily = float(avg_w) * 24.0 / 1000.0
        if peak_kwh is None or abs(daily) > abs(peak_kwh):
            peak_kwh = daily
            peak_day = day
    return PeakDayResult(peak_day, peak_kwh, total, incomplete)


def peak_result_text(ct_name, start_dt, stop_dt, result):
    """@return The peak day message shown to the user (same text as ct6_dash)."""
    start_s = start_dt.strftime("%Y-%m-%d")
    stop_s = stop_dt.strftime("%Y-%m-%d")
    if result.peak_day is None:
        return f"{ct_name}: No complete days (24 hours of data) found between {start_s} and {stop_s}."
    text = f"{ct_name}: Peak daily kWh = {abs(result.peak_kwh):.2f} kWh on {result.peak_day}."
    if result.incomplete_days > 0:
        text += f" ({result.incomplete_days} of {result.total_days} day(s) ignored due to incomplete data)"
    return text
