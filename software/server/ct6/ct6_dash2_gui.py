#!/usr/bin/env python3
"""@brief NiceGUI dashboard for viewing CT6 data (ct6_dash2).

   Threading model
   - Every action that touches the database runs in a worker thread.
   - Workers never touch widgets. They post dicts onto a queue.Queue.
   - Each browser client has its own queue and its own 100 ms ui.timer that
     drains the queue and updates that client's widgets.
   - Each request carries an incrementing job ID. Messages from older jobs are
     dropped so the newest request always wins."""

import asyncio
import os
import queue
import threading
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from time import time
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import RedirectResponse
from nicegui import app, run, ui
from nicegui.storage import Storage
from starlette.middleware.base import BaseHTTPMiddleware

from ct6 import ct6_dash2_auth as auth
from ct6 import ct6_dash2_prefs as up

from ct6 import ct6_data as cd
from ct6.ct6_data import PlotType, PowerType, Polarity, Resolution, EnergyBucket, Compare
from ct6 import ct6_tariff as tf
from ct6 import ct6_heatpump as hp
from ct6 import ct6_selfuse as su
from ct6.ct6_data_source import HalfHourEnergyCache

# Message types posted by worker threads.
MSG_STATUS = "status"
MSG_DEVICES = "devices"
MSG_PLOT_DATA = "plot_data"
MSG_SUMMARY_ROW = "summary_row"
MSG_PEAK_RESULT = "peak_result"
MSG_COST = "cost"
MSG_ENABLE_CONTROLS = "enable_controls"
MSG_ERROR = "error"
MSG_DONE = "done"
MSG_DOWNLOAD = "download"
MSG_LIVE = "live"           # Live tab update (has its own request counter, see _start_live_job())
MSG_HEATPUMP = "heatpump"   # Heat pump tab results
MSG_SELFUSE = "selfuse"     # Solar / battery self-consumption figures
MSG_ZOOM = "zoom"           # Finer data for a zoomed-in plot (has its own request counter)
ZOOM_DELAY_SECS = 0.7       # Wait this long after the last zoom/pan before re-reading
ZOOM_PAD = 0.1              # Read this fraction of the visible span extra on each side (for panning)

LIVE_TAB = "__live__"       # Tab name of the Live tab
HP_TAB = "__heatpump__"     # Tab name of the Heat pump tab
HP_COLOURS = {hp.HEATING: "#ee6666", hp.COOLING: "#5470c6", hp.OFF: "#777777"}
HP_KWH_COLOUR = "#fac858"
HP_SETTINGS_PX = 58         # Height of the Heat pump tab settings row (instead of the plot type row)
HP_MONTH_COLUMNS = [
    {"name": "month", "label": "Month", "field": "month", "align": "left"},
    {"name": "mode", "label": "Mode", "field": "mode", "align": "left"},
    {"name": "data_days", "label": "Days with data", "field": "data_days", "align": "right"},
    {"name": "on_days", "label": "On days", "field": "on_days", "align": "right"},
    {"name": "hours", "label": "Run h", "field": "hours", "align": "right"},
    {"name": "kwh", "label": "kWh", "field": "kwh", "align": "right"},
]
HELP_HEATPUMP = "A day is an on day when the heat pump CT's one minute average power was at or above the " \
                "threshold for at least the minimum run-time that day. On days in the cooling months count as " \
                "cooling, other months as heating. Uses the minute data, so it covers the full history."
LIVE_SECONDS = 2.0          # Live tab refresh period
LIVE_STATUS_COLOURS = {"ok": "text-positive", "stale": "text-warning", "offline": "text-negative"}

# The ECharts default palette. Energy bars set colours explicitly (two series per CT)
# using the same order, so a CT keeps its colour in every view.
PALETTE = ["#5470c6", "#91cc75", "#fac858", "#ee6666", "#73c0de", "#3ba272", "#fc8452", "#9a60b4", "#ea7ccc"]
HELP_ENERGY_BUCKET = "Energy per bar. Auto = one bar per day for ranges up to " \
                     f"{cd.ENERGY_AUTO_MAX_DAYS} days, else one bar per month."

# Chart height = viewport height minus the space used by the header, tabs,
# plot type selector and the collapsed kWh bar.
CHART_OFFSET_PX = 221

SELFUSE_COLUMNS = [
    {"name": "item", "label": "Solar & battery", "field": "item", "align": "left",
     "style": "white-space: pre"},
    {"name": "kwh", "label": "kWh", "field": "kwh", "align": "right"},
    {"name": "pc", "label": "%", "field": "pc", "align": "right"},
]
KWH_TABLES_MAX_PX = 300     # The open kWh bar's tables scroll beyond this height
SELFUSE_LINE_PX = 20        # Height of the solar & battery line in the kWh bar header
COST_COLUMNS = [
    {"name": "item", "label": "Cost", "field": "item", "align": "left"},
    {"name": "kwh", "label": "kWh", "field": "kwh", "align": "right"},
    {"name": "cost", "label": "£", "field": "cost", "align": "right"},
]
KWH_ROW_PX = 29
KWH_TABLE_HEADER_PX = 36

POLL_SECONDS = 0.1
MAX_MSGS_PER_POLL = 200

HELP_RESOLUTION = "Select the plot resolution."
HELP_POWER_TYPE = "Select the power type. Active = Power normally charged by electricity supplier."
HELP_POLARITY = "Select imported electrical power to be plotted as negative or positive values."
HELP_GAPS = "Break the plot lines where readings are missing (e.g. the CT6 was offline) instead of " \
            "joining the readings either side with a straight line. A gap is longer than 5 times the " \
            "usual time between readings, and at least 1 min (Sec), 5 min (Min), 3 h (Hour) or 3 days (Day). " \
            "kWh figures are not affected."
HELP_COMPARE = "Draw an earlier period over the plot as dashed lines in the same colours, lined up with " \
               "the selected dates: the previous period of the same length (Today vs yesterday, " \
               "This week vs last week), the week before, or the same dates a year before. The kWh table " \
               "adds the earlier period's totals. Not shown on the Energy view."
HELP_ZOOM = "When you zoom in on a plot (mouse wheel, slider or box zoom), re-read the visible part " \
            "at a finer resolution: Sec for up to 6 hours, Min for up to 14 days, Hour beyond that. " \
            "It runs shortly after you stop zooming and doesn't block the controls. kWh figures still " \
            "cover the whole selected period."
HELP_PEAK = "Find the day with the largest daily kWh value (+ve or -ve) for the selected CT port " \
            "between the selected start and stop dates/times. This can be used to gauge solar " \
            "panel performance/degradation over time."

SUMMARY_COLUMNS = [
    {"name": "sensor", "label": "Sensor", "field": "sensor", "align": "left"},
    {"name": "total", "label": "kWh", "field": "total", "align": "right"},
    {"name": "positive", "label": "kWh", "field": "positive", "align": "right",
     "classes": "bg-green-8 text-white", "headerClasses": "bg-green-8 text-white"},
    {"name": "negative", "label": "kWh", "field": "negative", "align": "right",
     "classes": "bg-orange-8 text-white", "headerClasses": "bg-orange-8 text-white"},
    {"name": "compare", "label": "Compare kWh", "field": "compare", "align": "right"},
]


USER_PREFS_FILENAME = "ct6Dash2UserPrefs.json"     # Per-user remembered settings (login enabled)
THEME_CSS = """
.ct6-sub { color: #9e9e9e; }
.ct6-sum { color: #bdbdbd; }
body.body--light .ct6-sub { color: #616161; }
body.body--light .ct6-sum { color: #424242; }
body.body--light .text-warning { color: #b26a00 !important; }
"""


def _chart_colours(dark):
    return {"text": "#cccccc" if dark else "#333333", "grid": "#3a3a3a" if dark else "#e0e0e0"}


def _apply_chart_theme(opts, dark):
    """@brief Set the theme colours in ECharts options (in place) without touching the data.
       @return opts."""
    c = _chart_colours(dark)
    opts.setdefault("textStyle", {})["color"] = c["text"]
    if "legend" in opts:
        opts["legend"].setdefault("textStyle", {})["color"] = c["text"]
    if "toolbox" in opts:
        opts["toolbox"].setdefault("iconStyle", {})["borderColor"] = c["text"]
    for key in ("xAxis", "yAxis"):
        axes = opts.get(key)
        for axis in (axes if isinstance(axes, list) else [axes] if axes else []):
            axis.setdefault("axisLabel", {})["color"] = c["text"]
            if "nameTextStyle" in axis or key == "yAxis":
                axis.setdefault("nameTextStyle", {})["color"] = c["text"]
            split = axis.get("splitLine")
            if split is not None and split.get("show", True):
                split.setdefault("lineStyle", {})["color"] = c["grid"]
    for zoom in opts.get("dataZoom", []):
        if zoom.get("type") == "slider":
            zoom.setdefault("textStyle", {})["color"] = c["text"]
    return opts


def _base_chart_options(dark=True):
    c = _chart_colours(dark)
    text, grid_line = c["text"], c["grid"]
    axis_line = {"lineStyle": {"color": "#777777"}}
    return {
        "animation": False,
        "backgroundColor": "transparent",
        "textStyle": {"color": text},
        "tooltip": {"trigger": "axis"},
        # Keep the (scrolling) legend clear of the toolbox icons on the right.
        "legend": {"type": "scroll", "top": 0, "left": 60, "width": "78%", "textStyle": {"color": text}},
        "grid": {"left": 70, "right": 30, "top": 40, "bottom": 70},
        "toolbox": {"right": 10, "top": 0, "iconStyle": {"borderColor": text},
                    "feature": {"dataZoom": {"yAxisIndex": "none"}, "restore": {}, "saveAsImage": {}}},
        "xAxis": {"type": "time", "axisLine": axis_line, "axisLabel": {"color": text},
                  "splitLine": {"show": False}},
        "yAxis": {"type": "value", "name": "kW", "nameLocation": "middle", "nameGap": 50,
                  "nameTextStyle": {"color": text}, "axisLabel": {"color": text},
                  "axisLine": axis_line, "splitLine": {"lineStyle": {"color": grid_line}}},
        "dataZoom": [{"type": "inside"}, {"type": "slider", "bottom": 15, "height": 20,
                                          "textStyle": {"color": text}}],
        "series": [],
    }


@dataclass
class _DeviceTab:
    device: cd.DeviceInfo
    tab: object = None
    plot_toggle: object = None
    chart: object = None
    table: object = None
    status: object = None
    kwh_bar: object = None      # ui.expansion holding the kWh table
    kwh_summary: object = None  # One line kWh totals shown in the collapsed header
    cost_summary: object = None # One line cost summary shown in the collapsed header
    cost_tip: object = None     # Tooltip explaining how off-peak was decided
    cost_table: object = None
    self_row: object = None     # Solar & battery line in the collapsed header (hidden if no solar/battery CT)
    self_summary: object = None
    self_tip: object = None
    self_table: object = None
    bucket_toggle: object = None  # Auto/Day/Month (Energy plot only)
    bucket_row: object = None
    mode: str = "line"          # Current chart layout: "line" or "bar"
    chart_box: object = None    # Container the chart is (re)built in
    read_params: dict = None    # Parameters of the last plot read (for zoom refinement)
    base_series: list = None    # The plotted series as read (before any zoom refinement)
    x_min: object = None        # datetime extent of the plotted data
    x_max: object = None
    zoom_timer: object = None


@dataclass
class _HeatPumpPanel:
    """@brief The Heat pump tab widgets."""
    ct_select: object = None
    threshold: object = None
    min_minutes: object = None
    months: object = None
    apply_btn: object = None
    status: object = None
    bar: object = None          # ui.expansion holding the monthly table
    summary: object = None
    month_table: object = None
    chart: object = None


@dataclass
class _LiveCard:
    """@brief The Live tab widgets for one device."""
    device: cd.DeviceInfo
    dot: object = None
    age: object = None
    stats: object = None
    ct_values: dict = None      # ct_number -> ui.label
    chart: object = None


class _ClientSession:
    """@brief The state and widgets for one browser client (one page load)."""

    def __init__(self, gui, address="?"):
        self._gui = gui
        self._address = address
        self._uio = gui.uio
        self._options = gui.options
        self._queue = queue.Queue()
        self._job_id = 0
        self._zoom_id = 0
        self._job_lock = threading.Lock()
        self._suppress_events = False
        self._tabs = {}            # device_id -> _DeviceTab
        self._kwh_expanded = False # The kWh table open/closed state (shared by all tabs)
        self._controls = []        # Widgets disabled while a job runs
        self._peak_ct_fields = {}  # CT name -> ACT_WATTS column
        self._job_start = None
        self._devices = {}         # device_id -> DeviceInfo (set once, read by workers)
        # Live tab state (GUI thread only)
        self._live_cards = {}      # device_id -> _LiveCard
        self._live_rows = {}       # device_id -> rows in the rolling window (oldest first)
        self._live_last_ts = {}    # device_id -> newest row timestamp seen
        self._live_id = 0
        self._live_busy = False
        self._hp = None            # _HeatPumpPanel
        self._dark = gui.dark      # This browser's theme (set from app.storage.user in build())
        self._dark_mode = None
        self._theme_btn = None
        self._hp_expanded = False

    # ------------------------------------------------------------ jobs

    def _start_job(self, target, *args):
        """@brief Run target(job_id, post, *args) in a worker thread.
           @return The job ID."""
        with self._job_lock:
            self._job_id += 1
            job_id = self._job_id
        self._set_controls_enabled(False)
        self._job_start = time()

        def post(msg_type, **payload):
            payload["type"] = msg_type
            payload["job_id"] = job_id
            self._queue.put(payload)

        def run():
            try:
                target(post, *args)
            except Exception as ex:
                self._uio.errorException()
                post(MSG_ERROR, message=str(ex) or ex.__class__.__name__)
            finally:
                post(MSG_DONE)

        threading.Thread(target=run, daemon=True, name=f"ct6_dash2_job_{job_id}").start()
        return job_id

    def _poll(self):
        """@brief Called every POLL_SECONDS in the GUI thread to process worker messages."""
        for _ in range(MAX_MSGS_PER_POLL):
            try:
                msg = self._queue.get_nowait()
            except queue.Empty:
                return
            if msg["type"] == MSG_ZOOM:
                if msg.get("zoom_id") == self._zoom_id and msg.get("job_id") == self._job_id:
                    try:
                        self._apply_zoom(msg)
                    except Exception:
                        self._uio.errorException()
                continue
            if msg["type"] == MSG_LIVE:
                if msg.get("live_id") == self._live_id:
                    self._live_busy = False
                    try:
                        self._update_live(msg)
                    except Exception:
                        self._uio.errorException()
                continue
            if msg.get("job_id") != self._job_id:
                continue    # From a superseded job
            try:
                self._handle_msg(msg)
            except Exception:
                self._uio.errorException()

    def _handle_msg(self, msg):
        t = msg["type"]
        if t == MSG_STATUS:
            self._show_status(msg.get("device_id"), msg["message"])
        elif t == MSG_ERROR:
            self._show_status(msg.get("device_id"), msg["message"], error=True)
        elif t == MSG_DEVICES:
            self._build_device_tabs(msg["devices"])
        elif t == MSG_PLOT_DATA:
            self._update_plot(msg)
        elif t == MSG_SUMMARY_ROW:
            self._update_summary_row(msg["device_id"], msg["row"], msg.get("compare_label", ""))
        elif t == MSG_COST:
            self._update_cost(msg)
        elif t == MSG_SELFUSE:
            self._update_self_use(msg)
        elif t == MSG_PEAK_RESULT:
            self._peak_label.set_text(msg["message"])
        elif t == MSG_ENABLE_CONTROLS:
            self._set_controls_enabled(msg["enabled"])
        elif t == MSG_DOWNLOAD:
            ui.download.content(msg["content"], msg["filename"], media_type="text/csv")
            self._show_status(msg["device_id"], msg["message"])
        elif t == MSG_HEATPUMP:
            self._update_heatpump(msg)
        elif t == MSG_DONE:
            self._set_controls_enabled(True)

    # ------------------------------------------------------------ workers (run outside the GUI thread)

    def _worker_list_devices(self, post):
        post(MSG_STATUS, message="Connecting to database...")
        try:
            with self._gui.data_source_factory() as ds:
                devices = ds.list_devices()
        except Exception as ex:
            self._uio.errorException()
            post(MSG_ERROR, message=f"Failed to connect to the database: {ex}. Check the database settings (ct6_dash2 -c).")
            return
        post(MSG_DEVICES, devices=devices)

    def _worker_energy(self, post, p):
        """@brief Read daily/monthly energy totals and post them as bar chart data."""
        device = p["device"]
        dev_id = device.device_id
        start_t = time()
        post(MSG_STATUS, device_id=dev_id, message="Reading Data...")
        bucket = cd.choose_bucket(p["bucket"], p["start"], p["stop"])
        columns = [cd.act_watts_field(n) for n, _ in device.active_cts()]
        with self._gui.data_source_factory() as ds:
            records = ds.period_energy(dev_id, columns, p["start"], p["stop"], bucket)
        labels, bars, totals = cd.build_energy_bars(records, device, bucket, p["invert"])
        post(MSG_PLOT_DATA, device_id=dev_id, kind="bar", labels=labels, bars=bars,
             y_label=PlotType.ENERGY.y_axis_label(), scale=False, has_kwh=True)
        for ct_number, name in device.active_cts():
            post(MSG_SUMMARY_ROW, device_id=dev_id, row=cd.summary_row(ct_number, name, totals[ct_number], p["invert"]))
        cost_secs = self._post_cost(post, dev_id, p["start"], p["stop"])
        self._post_self_use(post, dev_id, p["start"], p["stop"])
        post(MSG_STATUS, device_id=dev_id,
             message=f"Energy per {bucket.value.lower()} from minute data: {len(labels)} bar(s) "
                     f"in {time() - start_t:.1f} seconds (costs {cost_secs:.1f} s)." +
                     (" The period comparison isn't shown on the Energy view."
                      if p.get("compare", Compare.OFF) != Compare.OFF else ""))

    def _worker_read(self, post, p):
        if p["plot_type"] == PlotType.ENERGY:
            return self._worker_energy(post, p)
        device = p["device"]
        dev_id = device.device_id
        start_t = time()
        post(MSG_STATUS, device_id=dev_id, message="Reading Data...")
        with self._gui.data_source_factory() as ds:
            count = ds.count_rows(dev_id, p["start"], p["stop"], p["resolution"])
            if count > p["maxpp"]:
                post(MSG_ERROR, device_id=dev_id,
                     message=f"Reduce plot resolution ({count} values read, max = {p['maxpp']}).")
                return
            rows = ds.read_rows(dev_id, p["start"], p["stop"], p["resolution"])
        read_secs = time() - start_t

        plot_type = p["plot_type"]
        series = []
        downsampled = False
        gap_secs = cd.gap_threshold(rows, p["resolution"]) if p["gaps"] else None

        # Period overlay: read the earlier period and move it forward so it lines up.
        offset, cmp_label = cd.compare_offset(p["compare"], p["start"], p["stop"])
        cmp_rows = []
        if offset is not None:
            cmp_start, cmp_stop = p["start"] - offset, p["stop"] - offset
            with self._gui.data_source_factory() as ds:
                cmp_count = ds.count_rows(dev_id, cmp_start, cmp_stop, p["resolution"])
                if cmp_count > p["maxpp"]:
                    post(MSG_ERROR, device_id=dev_id, message=f"Reduce plot resolution ({cmp_count} values "
                         f"read for the comparison period, max = {p['maxpp']}).")
                    return
                cmp_rows = cd.shift_rows(ds.read_rows(dev_id, cmp_start, cmp_stop, p["resolution"]), offset)
        cmp_gap_secs = cd.gap_threshold(cmp_rows, p["resolution"]) if p["gaps"] and cmp_rows else None
        if plot_type.is_per_ct:
            is_power = plot_type == PlotType.POWER
            for ct_number, name in device.active_cts():
                column = cd.ct_field(ct_number, plot_type, p["power_type"])
                points = cd.build_series(rows, column, p["resolution"], p["invert"], is_power=is_power,
                                         gap_secs=gap_secs)
                if not is_power:
                    points = [[x, None if y is None else abs(y)] for x, y in points]
                reduced = cd.downsample_minmax(points, p["maxdp"])
                downsampled |= len(reduced) < len(points)
                series.append({"name": name, "data": reduced, "colour": len(series)})
            for i, (ct_number, name) in enumerate(device.active_cts() if cmp_rows else []):
                column = cd.ct_field(ct_number, plot_type, p["power_type"])
                points = cd.build_series(cmp_rows, column, p["resolution"], p["invert"], is_power=is_power,
                                         gap_secs=cmp_gap_secs)
                if not is_power:
                    points = [[x, None if y is None else abs(y)] for x, y in points]
                series.append({"name": f"{name} ({cmp_label})", "data": cd.downsample_minmax(points, p["maxdp"]),
                               "colour": i, "compare": True})
        else:
            points = cd.build_series(rows, plot_type.single_field, p["resolution"], is_power=False,
                                     gap_secs=gap_secs)
            reduced = cd.downsample_minmax(points, p["maxdp"])
            downsampled = len(reduced) < len(points)
            series.append({"name": plot_type.single_trace_name(), "data": reduced, "colour": 0})
            if cmp_rows:
                points = cd.build_series(cmp_rows, plot_type.single_field, p["resolution"], is_power=False,
                                         gap_secs=cmp_gap_secs)
                series.append({"name": f"{plot_type.single_trace_name()} ({cmp_label})",
                               "data": cd.downsample_minmax(points, p["maxdp"]), "colour": 0, "compare": True})

        post(MSG_PLOT_DATA, device_id=dev_id, series=series,
             y_label=plot_type.y_axis_label(p["power_type"]), scale=plot_type != PlotType.POWER,
             has_kwh=plot_type.is_per_ct)

        if plot_type.is_per_ct:
            for ct_number, name in device.active_cts():
                kwh = cd.calc_kwh(rows, cd.act_watts_field(ct_number), p["invert"])
                row = cd.summary_row(ct_number, name, kwh, p["invert"])
                if offset is not None:
                    cmp_kwh = cd.calc_kwh(cmp_rows, cd.act_watts_field(ct_number), p["invert"])
                    row["compare"] = cd.summary_row(ct_number, name, cmp_kwh, p["invert"])["total"]
                post(MSG_SUMMARY_ROW, device_id=dev_id, row=row, compare_label=cmp_label)

        cost_text = ""
        if plot_type.is_per_ct:
            cost_text = f", costs {self._post_cost(post, dev_id, p['start'], p['stop']):.1f} s"
            self._post_self_use(post, dev_id, p["start"], p["stop"])

        msg = f"Took {time() - start_t:.1f} seconds to read and plot the data " \
              f"({len(rows)} rows, DB read {read_secs:.1f} s{cost_text})."
        if offset is not None:
            first = (p["start"] - offset).strftime("%d %b %Y")
            last = (p["stop"] - offset).strftime("%d %b %Y")
            msg += f" Compared with {first}" + (f" – {last}" if last != first else "") + \
                   ("" if cmp_rows else " (no data)") + "."
        if gap_secs is not None:
            gaps = cd.count_gaps(rows, gap_secs)
            if gaps:
                msg += f" {gaps} data gap(s) over {cd.format_duration(gap_secs)} shown as breaks."
        if downsampled:
            msg += f" Display reduced to {p['maxdp']} points per trace."
        post(MSG_STATUS, device_id=dev_id, message=msg)

    def _worker_csv(self, post, p):
        """@brief Build a CSV of the current view in the worker thread and post it for download."""
        device = p["device"]
        dev_id = device.device_id
        post(MSG_STATUS, device_id=dev_id, message="Creating CSV file...")
        with self._gui.data_source_factory() as ds:
            if p["plot_type"] == PlotType.ENERGY:
                bucket = cd.choose_bucket(p["bucket"], p["start"], p["stop"])
                columns = [cd.act_watts_field(n) for n, _ in device.active_cts()]
                records = ds.period_energy(dev_id, columns, p["start"], p["stop"], bucket)
                text = cd.energy_to_csv(records, device, bucket)
                count, label = len(records), f"Energy_{bucket.value}"
            else:
                count = ds.count_rows(dev_id, p["start"], p["stop"], p["resolution"])
                if count > p["maxpp"]:
                    post(MSG_ERROR, device_id=dev_id,
                         message=f"Reduce the resolution to export ({count} rows, max = {p['maxpp']}).")
                    return
                rows = ds.read_rows(dev_id, p["start"], p["stop"], p["resolution"])
                text = cd.rows_to_csv(rows, device)
                label = p["resolution"].value
        if not text:
            post(MSG_ERROR, device_id=dev_id, message="No data to export for the selected dates.")
            return
        data = text.encode("utf-8")
        post(MSG_DOWNLOAD, device_id=dev_id, content=data,
             filename=cd.csv_filename(device.name, p["start"], p["stop"], label),
             message=f"Exported {count} row(s) to CSV ({len(data) / 1024:.0f} KiB).")

    def _on_csv(self):
        if self._tab_panels.value == HP_TAB:
            self._read_heatpump(csv=True)
            return
        dt = self._selected_tab()
        if dt is None:
            ui.notify("Select a device or Heat pump tab to export its data.", type="info")
            return
        try:
            start, stop = self._get_start_stop()
        except ValueError as ex:
            self._show_status(dt.device.device_id, str(ex), error=True)
            return
        self._start_job(self._worker_csv, {"device": dt.device,
                                           "plot_type": PlotType(dt.plot_toggle.value),
                                           "resolution": Resolution(self._resolution.value),
                                           "bucket": EnergyBucket(dt.bucket_toggle.value),
                                           "start": start, "stop": stop,
                                           "maxpp": self._options.maxpp})

    def _start_live_job(self):
        """@brief Fetch new Live tab rows in a worker thread.
                  Live requests don't use the main job ID, so they never cancel a plot
                  read or disable the controls, and plot reads never cancel them."""
        self._live_id += 1
        live_id = self._live_id
        self._live_busy = True
        now = datetime.now()
        since = {dev_id: self._live_last_ts.get(dev_id) or (now - cd.LIVE_WINDOW) for dev_id in self._devices}
        devices = dict(self._devices)
        need_latest = {dev_id for dev_id in self._devices if dev_id not in self._live_last_ts}

        def run():
            msg = {"type": MSG_LIVE, "live_id": live_id, "rows": {}, "latest": {}, "error": None}
            try:
                with self._gui.data_source_factory() as ds:
                    for dev_id, dev in devices.items():
                        cols = cd.live_columns(dev)
                        rows = [{c: r.get(c) for c in cols} for r in ds.recent_rows(dev_id, since[dev_id])]
                        msg["rows"][dev_id] = rows
                        if not rows and dev_id in need_latest:
                            msg["latest"][dev_id] = ds.latest_timestamp(dev_id)
            except Exception as ex:
                self._uio.errorException()
                msg["error"] = f"Live update failed: {ex}"
            msg["now"] = datetime.now()
            self._queue.put(msg)

        threading.Thread(target=run, daemon=True, name=f"ct6_dash2_live_{live_id}").start()

    def _live_tick(self):
        """@brief Called every LIVE_SECONDS. Only reads the database while the Live tab is shown."""
        if self._tab_panels is None or self._tab_panels.value != LIVE_TAB or not self._devices or self._live_busy:
            return
        self._start_live_job()

    def _post_cost(self, post, dev_id, start, stop):
        """@brief Calculate the costs and post them (worker thread). The plot is already shown.
           @return The seconds taken."""
        cost_t = time()
        post(MSG_COST, device_id=dev_id, ok=True, warn=False, summary="Calculating costs...", caveat="", rows=[])
        post(MSG_COST, device_id=dev_id, **self._calc_cost(start, stop))
        return time() - cost_t

    def _post_self_use(self, post, dev_id, start, stop):
        """@brief Work out and post the solar / battery self-consumption figures (worker thread)."""
        try:
            post(MSG_SELFUSE, device_id=dev_id, **self._calc_self_use(start, stop))
        except Exception as ex:
            self._uio.errorException()
            post(MSG_SELFUSE, device_id=dev_id, visible=True, warn=True, summary=f"Failed: {ex}",
                 caveat=su.CAVEAT, rows=[])

    def _calc_self_use(self, start, stop):
        """@return A dict with visible, warn, summary, caveat and rows for the self-consumption line."""
        roles = self._gui.settings_store.load().roles
        if roles.solar is None and roles.battery is None:
            return {"visible": False, "warn": False, "summary": "", "caveat": "", "rows": []}

        def problem(text):
            return {"visible": True, "warn": True, "summary": text, "caveat": su.CAVEAT, "rows": []}

        if roles.grid is None:
            return problem("Set the grid CT in 'Tariff & CT roles' to see solar and battery figures.")
        for ref, what in ((roles.grid, "grid"), (roles.solar, "solar"), (roles.battery, "battery")):
            if ref is not None and ref.device_id not in self._devices:
                return problem(f"The {what} CT's device ({ref.device_id}) was not found in the database.")
        with self._gui.data_source_factory() as ds:
            cache = self._gui.half_hour_cache

            def slots(ref, a=start, b=stop):
                if ref is None:
                    return None
                return cache.half_hour_energy(ds, ref.device_id, cd.act_watts_field(ref.ct), a, b)
            solar = slots(roles.solar)
            gen_negative, detected = roles.solar_gen_negative, False
            if roles.solar is not None and roles.solar_sign_auto:
                found = su.detect_gen_negative(solar)
                if found is None:
                    # Not enough solar in the range (e.g. at night): look at the 14 days before it.
                    day0 = datetime.combine(start.date(), datetime.min.time())
                    found = su.detect_gen_negative(slots(roles.solar, day0 - timedelta(days=14),
                                                         day0 - timedelta(seconds=1)))
                if found is not None:
                    gen_negative, detected = found, True
            grid, battery = slots(roles.grid), slots(roles.battery)
            res = su.calc_self_use(grid, solar, battery,
                                   grid_import_negative=roles.grid_import_negative,
                                   solar_gen_negative=gen_negative,
                                   battery_charge_negative=roles.battery_charge_negative)
            res.solar_sign_detected = detected
            res.coverage = {name: self._coverage(ref, data, start, stop)
                            for name, ref, data in (("grid", roles.grid, grid), ("solar", roles.solar, solar),
                                                    ("battery", roles.battery, battery)) if ref is not None}
        return {"visible": True, "warn": res.solar_sign_suspect or res.battery_sign_suspect,
                "summary": su.summary_text(res), "caveat": su.caveat_text(res), "rows": su.table_rows(res)}

    def _coverage(self, ref, slots, start, stop):
        """@return The share of minutes with data for a CT over start..stop, from the device's first
                   data and up to now."""
        dev = self._devices.get(ref.device_id)
        begin = start
        if dev is not None and dev.first_date:
            begin = max(start, datetime.combine(dev.first_date, datetime.min.time()))
        end = min(stop + timedelta(seconds=1), datetime.now().replace(second=0, microsecond=0))
        return su.data_coverage(slots, begin, end)

    def _calc_cost(self, start, stop):
        """@brief Calculate the whole-site cost for the period (runs in the worker thread).
                  The grid CT and EV CT may be on different CT6 devices, so the result
                  is the same whichever device tab is selected.
           @return A dict with summary, caveat, rows, ok and warn."""
        settings = self._gui.settings_store.load()
        roles, tariff = settings.roles, settings.tariff
        caveat = tf.cost_caveat(tariff)

        def problem(text):
            return {"ok": False, "summary": text, "caveat": caveat, "rows": []}

        if roles.grid is None:
            return problem("Set the grid CT in 'Tariff & CT roles' to see costs.")
        if not tariff.rates:
            return problem("Add your rates in 'Tariff & CT roles' to see costs.")
        devices = self._devices
        for ref, what in ((roles.grid, "grid"), (roles.ev, "EV")):
            if ref is not None and ref.device_id not in devices:
                return problem(f"The {what} CT's device ({ref.device_id}) was not found in the database.")
        if tariff.ev_slots_offpeak and roles.ev is None:
            return problem("The EV charging rule needs an EV CT ('Tariff & CT roles').")
        with self._gui.data_source_factory() as ds:
            cache = self._gui.half_hour_cache
            grid = cache.half_hour_energy(ds, roles.grid.device_id, cd.act_watts_field(roles.grid.ct), start, stop)
            ev = None
            if roles.ev is not None:
                ev = cache.half_hour_energy(ds, roles.ev.device_id, cd.act_watts_field(roles.ev.ct), start, stop)
        res = tf.calc_cost(grid, tariff, start, stop, import_negative=roles.grid_import_negative, ev_slots=ev)
        ev_name = (devices[roles.ev.device_id].ct_names[roles.ev.ct - 1] or f"CT{roles.ev.ct}") if roles.ev else None
        summary = tf.cost_summary_text(res, ev_name)
        cov = self._coverage(roles.grid, grid, start, stop)
        if cov is not None:
            caveat += f" Grid CT minutes with data: {cov * 100:.1f}% (missing minutes count as zero)."
        warning = tf.uncosted_warning(res, tariff)
        if warning:
            summary = f"{warning} · {summary}"
        return {"ok": True, "warn": bool(warning), "summary": summary, "caveat": caveat,
                "rows": tf.cost_table_rows(res, ev_name)}

    def _worker_peak(self, post, p):
        try:
            with self._gui.data_source_factory() as ds:
                records = ds.daily_averages(p["device"].device_id, p["column"], p["start"], p["stop"])
            result = cd.peak_daily_kwh(records)
            post(MSG_PEAK_RESULT, message=cd.peak_result_text(p["ct_name"], p["start"], p["stop"], result))
        except Exception:
            self._uio.errorException()
            post(MSG_PEAK_RESULT, message="An error occurred while searching for the peak daily kWh value.")

    # ------------------------------------------------------------ GUI actions

    def _selected_tab(self):
        dev_id = self._tab_panels.value if self._tab_panels else None
        return self._tabs.get(dev_id)

    def _get_start_stop(self):
        return cd.parse_start_stop(self._start_date.value, self._start_time.value,
                                   self._stop_date.value, self._stop_time.value)

    def _read_selected(self):
        """@brief Read and plot data for the selected device using the current settings."""
        if self._tab_panels is not None and self._tab_panels.value == HP_TAB:
            self._read_heatpump()
            return
        dt = self._selected_tab()
        if dt is None:
            return
        try:
            start, stop = self._get_start_stop()
        except ValueError as ex:
            self._show_status(dt.device.device_id, str(ex), error=True)
            return
        self._clear_summary(dt)
        params = {"device": dt.device,
                  "plot_type": PlotType(dt.plot_toggle.value),
                  "power_type": PowerType(self._power_type.value),
                  "resolution": Resolution(self._resolution.value),
                  "invert": self._invert_kw(),
                  "start": start,
                  "stop": stop,
                  "maxpp": self._options.maxpp,
                  "maxdp": self._options.maxdp,
                  "gaps": bool(self._gaps.value),
                  "compare": Compare(self._compare.value or Compare.OFF.value),
                  "bucket": EnergyBucket(dt.bucket_toggle.value)}
        dt.read_params = params
        dt.base_series = None
        self._zoom_id += 1          # Drop any zoom refinement still running for the old plot
        self._start_job(self._worker_read, params)

    # ------------------------------------------------------------ remembered settings

    def _remember(self, key, value):
        """@brief Remember a setting the user changed (ignored while the code itself sets widgets)."""
        if not self._suppress_events:
            self._prefs.set(key, value)

    def _valid_pref(self, key, allowed, default):
        value = self._prefs.get(key)
        return value if value in allowed else default

    def _reset_prefs(self):
        self._prefs.clear()
        app.storage.user.pop(up.STORAGE_PREFIX + up.DARK_THEME, None)
        ui.navigate.reload()

    def _on_compare_change(self, e):
        self._remember(up.COMPARE, e.value)
        if not self._suppress_events and self._tab_panels is not None and self._selected_tab() is not None:
            self._read_selected()

    def _on_gaps_change(self, e):
        self._prefs.set(up.SHOW_GAPS, bool(e.value))
        if self._tab_panels is not None and self._selected_tab() is not None:
            self._read_selected()

    def _invert_kw(self):
        """@return True if imported power should be plotted as positive values (as ct6_dash)."""
        return self._polarity.value == Polarity.IMPORT_POSITIVE.value

    def _on_update(self):
        if self._tab_panels.value == LIVE_TAB:
            self._live_tick()
            return
        dt = self._selected_tab()
        if dt is not None and not dt.plot_toggle.value:
            dt.plot_toggle.value = PlotType.POWER.value
        self._read_selected()

    def _on_preset(self, preset, startup=False):
        """@param startup True when restoring the remembered preset on page load: the remembered
                  resolution and plot types are kept."""
        r = cd.preset_range(preset)
        dt = self._selected_tab()
        self._suppress_events = True
        try:
            self._resolution.value = r.resolution.value
            if startup:
                self._resolution.value = self._valid_pref(up.RESOLUTION, [x.value for x in Resolution],
                                                          r.resolution.value)
            self._start_date.value = r.start_date.isoformat()
            self._start_time.value = r.start_time
            self._stop_date.value = r.stop_date.isoformat()
            self._stop_time.value = r.stop_time
            if not startup and dt is not None and dt.plot_toggle.value != PlotType.ENERGY.value:
                dt.plot_toggle.value = PlotType.POWER.value
        finally:
            self._suppress_events = False
        if not startup:
            self._prefs.set(up.PRESET, preset)
            self._prefs.set(up.RESOLUTION, None)
            if dt is not None:
                self._prefs.set(up.PLOT_TYPE, dt.plot_toggle.value)
        self._read_selected()

    def _step_date(self, date_input, days):
        try:
            d = date.fromisoformat(str(date_input.value)) + timedelta(days=days)
        except ValueError:
            d = date.today()
        date_input.value = d.isoformat()

    def _on_plot_type_change(self, device_id):
        tab = self._tabs.get(device_id)
        if tab is not None:
            tab.bucket_row.set_visibility(tab.plot_toggle.value == PlotType.ENERGY.value)
        if self._suppress_events:
            return
        if tab is not None and tab.plot_toggle.value:
            self._prefs.set(up.PLOT_TYPE, tab.plot_toggle.value)
        dt = self._selected_tab()
        if dt is not None and dt.device.device_id == device_id and dt.plot_toggle.value:
            self._read_selected()

    def _on_bucket_change(self, device_id):
        if self._suppress_events:
            return
        tab = self._tabs.get(device_id)
        if tab is not None and tab.bucket_toggle.value:
            self._prefs.set(up.BUCKET, tab.bucket_toggle.value)
        dt = self._selected_tab()
        if dt is not None and dt.device.device_id == device_id and dt.plot_toggle.value == PlotType.ENERGY.value:
            self._read_selected()

    def _on_tab_change(self):
        if self._suppress_events:
            return
        self._prefs.set(up.TAB, self._tab_panels.value)
        if self._tab_panels.value == LIVE_TAB:
            self._live_tick()
            return
        self._update_peak_options()
        self._read_selected()

    def _on_find_peak(self):
        dt = self._selected_tab()
        if dt is None:
            return
        ct_name = self._peak_ct.value
        column = self._peak_ct_fields.get(ct_name)
        if column is None:
            self._peak_label.set_text("No CT sensor is available to search.")
            return
        try:
            start, stop = self._get_start_stop()
        except ValueError as ex:
            self._peak_label.set_text(str(ex))
            return
        self._peak_label.set_text("Searching...")
        self._start_job(self._worker_peak, {"device": dt.device, "ct_name": ct_name,
                                            "column": column, "start": start, "stop": stop})

    # ------------------------------------------------------------ widget updates

    def _set_controls_enabled(self, enabled):
        for w in self._controls:
            w.enable() if enabled else w.disable()
        for dt in self._tabs.values():
            for w in (dt.plot_toggle, dt.bucket_toggle):
                w.enable() if enabled else w.disable()
        if self._hp is not None:
            self._hp.apply_btn.enable() if enabled else self._hp.apply_btn.disable()

    def _show_status(self, device_id, message, error=False):
        if device_id == HP_TAB or (device_id is None and self._hp is not None
                                   and self._tab_panels.value == HP_TAB):
            label = self._hp.status
        else:
            dt = self._tabs.get(device_id) if device_id else self._selected_tab()
            label = dt.status if dt else self._global_status
        label.set_text(message)
        label.classes(replace="text-sm " + ("text-negative" if error else "ct6-sub"))

    def _update_plot(self, msg):
        dt = self._tabs.get(msg["device_id"])
        if dt is None:
            return
        kind = msg.get("kind", "line")
        self._set_chart_mode(dt, kind)
        opts = dt.chart.options
        opts["yAxis"]["name"] = msg["y_label"]
        opts["yAxis"]["scale"] = msg["scale"]
        if kind == "bar":
            # Two series per CT (positive above zero, negative below) sharing a name, stack and
            # colour, so the legend shows each CT once and toggles both.
            opts["xAxis"]["data"] = msg["labels"]
            series = []
            for i, b in enumerate(msg["bars"]):
                colour = PALETTE[i % len(PALETTE)]
                for key in ("pos", "neg"):
                    series.append({"name": b["name"], "type": "bar", "stack": f"ct{b['ct']}",
                                   "itemStyle": {"color": colour}, "emphasis": {"focus": "series"},
                                   "data": b[key]})
            opts["series"] = series
            opts["legend"]["data"] = [b["name"] for b in msg["bars"]]
        else:
            def line(s):
                colour = PALETTE[s.get("colour", 0) % len(PALETTE)]
                cmp = s.get("compare", False)
                return {"name": s["name"], "type": "line", "showSymbol": False, "sampling": "lttb",
                        "itemStyle": {"color": colour},
                        "lineStyle": {"width": 1.5 if cmp else 2, "color": colour, "type": "dashed" if cmp else "solid",
                                      "opacity": 0.6 if cmp else 1},
                        "z": 1 if cmp else 2, "emphasis": {"disabled": True}, "data": s["data"]}
            opts["series"] = [line(s) for s in msg["series"]]
            dt.base_series = msg["series"]
            xs = [pt[0] for s_ in msg["series"] for pt in (s_["data"][:1] + s_["data"][-1:])]
            dt.x_min = datetime.strptime(min(xs), "%Y-%m-%d %H:%M:%S") if xs else None
            dt.x_max = datetime.strptime(max(xs), "%Y-%m-%d %H:%M:%S") if xs else None
            for zoom in opts.get("dataZoom", []):
                zoom.pop("start", None)
                zoom.pop("end", None)
            opts["legend"]["data"] = [s["name"] for s in msg["series"]]
        dt.chart.update()
        dt.kwh_bar.set_visibility(msg["has_kwh"])
        self._set_chart_height(dt)

    # ------------------------------------------------------------ zoom refinement

    def _hook_zoom(self, dt):
        dt.chart.on("chart:datazoom", lambda _e, d=dt: self._on_zoom(d))

    def _on_zoom(self, dt):
        """@brief Called on every zoom/pan: re-read finer data once the user has stopped."""
        if not self._zoom_refine.value or dt.mode != "line" or not dt.base_series or dt.read_params is None:
            return
        if dt.zoom_timer is not None:
            dt.zoom_timer.cancel()
        dt.zoom_timer = ui.timer(ZOOM_DELAY_SECS, lambda d=dt: self._refine_zoom(d), once=True)

    async def _refine_zoom(self, dt):
        dt.zoom_timer = None
        if dt.x_min is None or dt.x_max is None or dt.x_max <= dt.x_min or dt.base_series is None:
            return
        try:
            # Ask the browser for just the zoom percentages. (getOption() would send every data
            # point back, which can exceed NiceGUI's 1 MB message limit on a big plot.)
            zoom = await ui.run_javascript(
                f"const z = getElement({dt.chart.id}).chart.getOption().dataZoom[0];"
                f"return [z.start, z.end];", timeout=2)
            start_pc, end_pc = float(zoom[0]), float(zoom[1])
        except Exception:
            return
        if end_pc - start_pc >= 99.5:
            return                  # Not zoomed in
        extent = (dt.x_max - dt.x_min).total_seconds()
        view0 = dt.x_min + timedelta(seconds=extent * start_pc / 100.0)
        view1 = dt.x_min + timedelta(seconds=extent * end_pc / 100.0)
        p = dt.read_params
        res = cd.zoom_resolution((view1 - view0).total_seconds(), p["resolution"])
        if res is None:
            return
        pad = (view1 - view0) * ZOOM_PAD
        w0 = max(dt.x_min, view0 - pad).replace(microsecond=0)
        w1 = min(dt.x_max, view1 + pad).replace(microsecond=0)
        self._zoom_id += 1
        zoom_id, job_id = self._zoom_id, self._job_id
        self._show_status(dt.device.device_id, f"Loading {res.value} data for the zoomed-in part...")

        def run():
            msg = {"type": MSG_ZOOM, "zoom_id": zoom_id, "job_id": job_id, "device_id": dt.device.device_id,
                   "start_pc": start_pc, "end_pc": end_pc, "res": res.value}
            t0 = time()
            try:
                with self._gui.data_source_factory() as ds:
                    count = ds.count_rows(p["device"].device_id, w0, w1, res)
                    if count > p["maxpp"]:
                        msg["error"] = f"Zoom in further for {res.value} data ({count} values, max = {p['maxpp']})."
                        self._queue.put(msg)
                        return
                    rows = ds.read_rows(p["device"].device_id, w0, w1, res)
                if not rows:
                    # e.g. per-second data no longer kept for these dates: keep what's plotted.
                    msg["error"] = f"No {res.value} data for the zoomed-in part; showing " \
                                   f"{p['resolution'].value} data."
                    self._queue.put(msg)
                    return
                msg["series"] = self._series_data(rows, p, res)
                msg["x0"], msg["x1"] = cd._x(w0), cd._x(w1)
            except Exception as ex:
                self._uio.errorException()
                msg["error"] = f"Zoom read failed: {ex}"
            msg["secs"] = time() - t0
            self._queue.put(msg)

        threading.Thread(target=run, daemon=True, name=f"ct6_dash2_zoom_{zoom_id}").start()

    def _series_data(self, rows, p, resolution):
        """@return The point lists of the main (not comparison) traces, in plot order."""
        plot_type, device = p["plot_type"], p["device"]
        gap_secs = cd.gap_threshold(rows, resolution) if p["gaps"] else None
        out = []
        if plot_type.is_per_ct:
            is_power = plot_type == PlotType.POWER
            for ct_number, _name in device.active_cts():
                column = cd.ct_field(ct_number, plot_type, p["power_type"])
                points = cd.build_series(rows, column, resolution, p["invert"], is_power=is_power, gap_secs=gap_secs)
                if not is_power:
                    points = [[x, None if y is None else abs(y)] for x, y in points]
                out.append(cd.downsample_minmax(points, p["maxdp"]))
        else:
            points = cd.build_series(rows, plot_type.single_field, resolution, is_power=False, gap_secs=gap_secs)
            out.append(cd.downsample_minmax(points, p["maxdp"]))
        return out

    def _apply_zoom(self, msg):
        dt = self._tabs.get(msg["device_id"])
        if dt is None or dt.base_series is None or dt.mode != "line":
            return
        if msg.get("error"):
            self._show_status(dt.device.device_id, msg["error"])
            return
        opts = dt.chart.options
        fine = iter(msg["series"])
        for i, s in enumerate(dt.base_series):
            if not s.get("compare"):
                opts["series"][i]["data"] = cd.merge_points(s["data"], next(fine, []), msg["x0"], msg["x1"])
        # Keep the user's zoom (the data extent is unchanged, so the percentages still apply).
        for zoom in opts.get("dataZoom", []):
            zoom["start"], zoom["end"] = msg["start_pc"], msg["end_pc"]
        dt.chart.update()
        self._show_status(dt.device.device_id,
                          f"Zoomed in: showing {msg['res']} data for {msg['x0'][:16]} – {msg['x1'][:16]} "
                          f"(read in {msg['secs']:.1f} s).")

    # ------------------------------------------------------------ theme

    def _show_theme_button(self):
        """@brief The header button shows the theme it switches to."""
        self._theme_btn.props(f"icon={'light_mode' if self._dark else 'dark_mode'}")
        self._theme_tip.set_text("Light theme" if self._dark else "Dark theme")

    def _toggle_theme(self):
        """@brief Switch between the dark and light themes, remembered for this browser."""
        self._dark = not self._dark
        self._prefs.set(up.DARK_THEME, self._dark)
        app.storage.user[up.STORAGE_PREFIX + up.DARK_THEME] = self._dark    # For the login page
        self._dark_mode.set_value(self._dark)
        self._show_theme_button()
        charts = [dt.chart for dt in self._tabs.values()] + [c.chart for c in self._live_cards.values()]
        if self._hp is not None:
            charts.append(self._hp.chart)
        for chart in charts:
            if chart is not None:
                _apply_chart_theme(chart.options, self._dark)
                chart.update()

    def _set_chart_mode(self, dt, mode):
        """@brief Switch a device chart between the time series ("line") and Energy ("bar") layouts."""
        if dt.mode == mode:
            return
        dt.mode = mode
        opts = _base_chart_options(self._dark)
        if mode == "bar":
            opts["xAxis"] = {**opts["xAxis"], "type": "category", "data": []}
            opts["tooltip"] = {"trigger": "axis", "axisPointer": {"type": "shadow"}}
            opts["toolbox"]["feature"] = {"saveAsImage": {}}
        # Rebuild the chart element: ECharts doesn't reliably switch axis types in place.
        dt.chart_box.clear()
        with dt.chart_box:
            dt.chart = ui.echart(opts).classes("w-full")
        self._hook_zoom(dt)
        self._set_chart_height(dt)

    def _update_summary_row(self, device_id, row, compare_label=""):
        dt = self._tabs.get(device_id)
        if dt is None:
            return
        rows = [r for r in dt.table.rows if r["ct"] != row["ct"]] + [row]
        dt.table.rows = sorted(rows, key=lambda r: r["ct"])
        self._show_compare_column(dt, compare_label)
        dt.table.update()
        dt.kwh_summary.set_text(" · ".join(
            f"{r['sensor']} {r['total']}" + (f" ({r['compare']})" if "compare" in r else "") for r in dt.table.rows))

    def _show_compare_column(self, dt, compare_label):
        """@brief Show the kWh table's Compare column only with a period overlay."""
        names = [c["name"] for c in SUMMARY_COLUMNS if compare_label or c["name"] != "compare"]
        for c in dt.table.columns:
            if c["name"] == "compare":
                c["label"] = f"kWh ({compare_label})" if compare_label else "Compare kWh"
        dt.table.props(f":visible-columns={names!r}".replace("'", '"'))

    def _clear_summary(self, dt):
        dt.table.rows = []
        dt.table.update()
        dt.kwh_summary.set_text("")
        dt.cost_summary.set_text("")
        dt.cost_table.rows = []
        dt.cost_table.update()
        dt.self_summary.set_text("")
        dt.self_table.rows = []
        dt.self_table.update()

    def _update_self_use(self, msg):
        dt = self._tabs.get(msg["device_id"])
        if dt is None:
            return
        dt.self_row.set_visibility(msg["visible"])
        dt.self_summary.set_text(msg["summary"])
        dt.self_summary.classes(replace="text-sm ellipsis " + ("text-warning" if msg["warn"] else "ct6-sum"))
        dt.self_tip.set_text(msg["caveat"])
        dt.self_table.rows = msg["rows"]
        dt.self_table.update()
        dt.self_table.set_visibility(bool(msg["rows"]))
        self._set_chart_height(dt)

    def _update_cost(self, msg):
        dt = self._tabs.get(msg["device_id"])
        if dt is None:
            return
        dt.cost_summary.set_text(msg["summary"])
        normal = msg["ok"] and not msg.get("warn")
        dt.cost_summary.classes(replace="text-sm ellipsis " + ("ct6-sum" if normal else "text-warning"))
        dt.cost_tip.set_text(msg["caveat"])
        dt.cost_table.rows = msg["rows"]
        dt.cost_table.update()
        dt.cost_table.set_visibility(bool(msg["rows"]))
        self._set_chart_height(dt)

    def _kwh_table_px(self, dt):
        """@return The height the open kWh table adds below its header."""
        rows = max(1, len(dt.device.active_cts()),
                   len(dt.cost_table.rows) if dt.cost_table.visible else 0,
                   len(dt.self_table.rows) if dt.self_table.visible else 0)
        # + room for a horizontal scroll bar when the tables are wider than the window
        return min(KWH_TABLES_MAX_PX, KWH_TABLE_HEADER_PX + KWH_ROW_PX * rows + 2) + 22

    def _set_chart_height(self, dt):
        """@brief Size the chart so the page fits the window with the kWh table open or closed."""
        offset = CHART_OFFSET_PX
        if dt.kwh_bar.visible and dt.self_row.visible:
            offset += SELFUSE_LINE_PX
        if self._kwh_expanded and dt.kwh_bar.visible:
            offset += self._kwh_table_px(dt)
        dt.chart.style(f"height: calc(100vh - {offset}px); min-height: 300px")

    def _on_kwh_toggle(self, value):
        """@brief Keep the kWh table open/closed state the same on every tab."""
        if self._suppress_events or value == self._kwh_expanded:
            return
        self._kwh_expanded = value
        self._prefs.set(up.KWH_BAR_OPEN, bool(value))
        self._suppress_events = True
        try:
            for dt in self._tabs.values():
                if dt.kwh_bar.value != value:
                    dt.kwh_bar.value = value
                self._set_chart_height(dt)
        finally:
            self._suppress_events = False

    def _update_live(self, msg):
        """@brief Show a Live tab update (GUI thread)."""
        self._live_status.set_text(msg["error"] or "")
        now = msg["now"]
        invert = self._invert_kw()
        for dev_id, card in self._live_cards.items():
            new_rows = msg["rows"].get(dev_id, [])
            rows = cd.merge_live_rows(self._live_rows.get(dev_id, []), new_rows, now)
            self._live_rows[dev_id] = rows
            if new_rows:
                self._live_last_ts[dev_id] = new_rows[-1][cd.TIMESTAMP]
            last_ts = self._live_last_ts.get(dev_id) or msg["latest"].get(dev_id)
            age = (now - last_ts).total_seconds() if last_ts else None
            state = cd.live_status(age)
            card.dot.classes(replace=LIVE_STATUS_COLOURS[state])
            card.age.set_text(f"Last data {cd.format_age(age)}" if last_ts else "No data")

            latest = rows[-1] if rows else None
            for ct_number, label in card.ct_values.items():
                w = latest.get(cd.act_watts_field(ct_number)) if latest and state != "offline" else None
                label.set_text("–" if w is None else _kw_text((-w if invert else w) / 1000.0))
            if latest and state != "offline":
                b = cd.BaseConstants
                card.stats.set_text(f"{latest[b.VOLTAGE]:.1f} V · {latest[b.FREQUENCY]:.2f} Hz · "
                                    f"{latest[b.TEMPERATURE]:.1f} °C · {latest[b.RSSI_DBM]:.0f} dBm")
            else:
                card.stats.set_text("")

            series = []
            for ct_number, name in card.device.active_cts():
                col = cd.act_watts_field(ct_number)
                data = [[r[cd.TIMESTAMP].strftime(cd.X_FORMAT), round((-r[col] if invert else r[col]) / 1000.0, 3)]
                        for r in rows if r.get(col) is not None]
                series.append({"name": name, "type": "line", "showSymbol": False,
                               "lineStyle": {"width": 2}, "emphasis": {"disabled": True}, "data": data})
            card.chart.options["series"] = series
            card.chart.options["legend"]["data"] = [s["name"] for s in series]
            card.chart.update()

    def _update_peak_options(self):
        dt = self._selected_tab()
        if dt is None:
            return
        names = [n for _, n in dt.device.active_cts()]
        self._peak_ct_fields = {n: cd.act_watts_field(i) for i, n in dt.device.active_cts()}
        current = self._peak_ct.value
        self._peak_ct.set_options(names, value=current if current in names else (names[0] if names else None))

    def _build_device_tabs(self, devices):
        self._global_status.set_text("")
        if not devices:
            self._show_status(None, "No CT6 databases found. Check the database settings (ct6_dash2 -c).", error=True)
            return
        self._suppress_events = True
        try:
            self._devices = {dev.device_id: dev for dev in devices}
            with self._tabs_bar:
                live_tab = ui.tab(LIVE_TAB, label="Live", icon="sensors")
                for dev in devices:
                    self._tabs[dev.device_id] = _DeviceTab(device=dev, tab=ui.tab(dev.device_id, label=dev.name))
                hp_tab = ui.tab(HP_TAB, label="Heat pump", icon="thermostat")
            with self._tab_panels:
                self._build_live_panel(live_tab, devices)
                for dev in devices:
                    self._build_device_panel(self._tabs[dev.device_id])
                self._build_heatpump_panel(hp_tab)
            # Restore the remembered tab, plot type and Energy bucket.
            valid_tabs = [LIVE_TAB, HP_TAB] + [d.device_id for d in devices]
            self._tab_panels.value = self._valid_pref(up.TAB, valid_tabs, devices[0].device_id)
            plot_type = self._valid_pref(up.PLOT_TYPE, [p.value for p in PlotType], PlotType.POWER.value)
            bucket = self._valid_pref(up.BUCKET, [b.value for b in EnergyBucket], EnergyBucket.AUTO.value)
            for dt in self._tabs.values():
                dt.plot_toggle.value = plot_type
                dt.bucket_toggle.value = bucket
                dt.bucket_row.set_visibility(plot_type == PlotType.ENERGY.value)
        finally:
            self._suppress_events = False
        self._update_peak_options()
        # On startup show the remembered date preset (Today by default, as ct6_dash).
        self._on_preset(self._valid_pref(up.PRESET, cd.PRESETS, "Today"), startup=True)
        if self._tab_panels.value == LIVE_TAB:
            self._live_tick()

    def _build_live_panel(self, live_tab, devices):
        """@brief Build the Live tab: one card per device with its latest readings and a rolling chart."""
        with ui.tab_panel(live_tab).classes("p-0 w-full"):
            with ui.column().classes("w-full gap-2"):
                self._live_status = ui.label("").classes("text-sm text-negative")
                for dev in devices:
                    card = _LiveCard(device=dev, ct_values={})
                    with ui.card().classes("w-full q-pa-sm"):
                        with ui.row().classes("w-full items-center gap-2"):
                            card.dot = ui.icon("circle", size="xs").classes("text-grey-6")
                            ui.label(dev.name).classes("text-subtitle1 text-weight-bold")
                            card.age = ui.label("").classes("text-sm ct6-sub")
                            ui.space()
                            card.stats = ui.label("").classes("text-sm ct6-sum")
                        with ui.row().classes("w-full gap-6"):
                            for ct_number, name in dev.active_cts():
                                with ui.column().classes("gap-0"):
                                    ui.label(name).classes("text-xs ct6-sub")
                                    card.ct_values[ct_number] = ui.label("–").classes("text-h6")
                        opts = _base_chart_options(self._dark)
                        opts.pop("dataZoom")
                        opts.pop("toolbox")
                        opts["grid"] = {"left": 60, "right": 20, "top": 30, "bottom": 25}
                        card.chart = ui.echart(opts).classes("w-full").style("height: 200px")
                    self._live_cards[dev.device_id] = card

    def _build_device_panel(self, dt):
        dev_id = dt.device.device_id
        with ui.tab_panel(dt.tab).classes("p-0 w-full"):
            with ui.column().classes("w-full gap-1"):
                with ui.row().classes("w-full items-center gap-x-4 gap-y-1"):
                    dt.plot_toggle = ui.toggle([p.value for p in PlotType], value=PlotType.POWER.value,
                                               on_change=lambda _e, d=dev_id: self._on_plot_type_change(d)) \
                                       .props("no-caps dense")
                    with ui.row().classes("items-center gap-1 no-wrap") as dt.bucket_row:
                        dt.bucket_toggle = ui.toggle([b.value for b in EnergyBucket], value=EnergyBucket.AUTO.value,
                                                     on_change=lambda _e, d=dev_id: self._on_bucket_change(d)) \
                                             .props("no-caps dense")
                        self._help(HELP_ENERGY_BUCKET)
                    dt.bucket_row.set_visibility(False)
                    dt.status = ui.label("").classes("text-sm ct6-sub")
                # kWh table above the plot, collapsed by default. The header shows the totals.
                dt.kwh_bar = ui.expansion(value=self._kwh_expanded,
                                          on_value_change=lambda e: self._on_kwh_toggle(e.value)) \
                               .props("dense dense-toggle header-class=q-px-sm").classes("w-full")
                with dt.kwh_bar.add_slot("header"):
                    with ui.column().classes("w-full gap-0"):
                        with ui.row().classes("w-full items-center gap-3 no-wrap"):
                            ui.label("kWh").classes("text-sm text-weight-bold w-6")
                            dt.kwh_summary = ui.label("").classes("text-sm ct6-sum ellipsis")
                        with ui.row().classes("w-full items-center gap-3 no-wrap"):
                            ui.label("£").classes("text-sm text-weight-bold w-6")
                            dt.cost_summary = ui.label("").classes("text-sm ct6-sum ellipsis")
                            with ui.icon("info_outline", size="xs").classes("ct6-sub"):
                                dt.cost_tip = ui.tooltip("").classes("text-body2").style("max-width: 420px")
                        with ui.row().classes("w-full items-center gap-3 no-wrap") as dt.self_row:
                            ui.icon("wb_sunny", size="xs").classes("text-weight-bold w-6")
                            dt.self_summary = ui.label("").classes("text-sm ct6-sum ellipsis")
                            with ui.icon("info_outline", size="xs").classes("ct6-sub"):
                                dt.self_tip = ui.tooltip("").classes("text-body2").style("max-width: 420px")
                        dt.self_row.set_visibility(False)
                with dt.kwh_bar:
                    # One row of tables; it scrolls (rather than wraps or grows) so the chart keeps its space.
                    with ui.row().classes("w-full items-start gap-4 no-wrap overflow-auto") \
                                 .style(f"max-height: {KWH_TABLES_MAX_PX}px"):
                        dt.table = ui.table(columns=[dict(c) for c in SUMMARY_COLUMNS], rows=[], row_key="ct") \
                                     .props("dense flat bordered hide-bottom").classes("min-w-[340px] shrink-0")
                        self._show_compare_column(dt, "")
                        dt.cost_table = ui.table(columns=COST_COLUMNS, rows=[], row_key="id") \
                                          .props("dense flat bordered hide-bottom").classes("min-w-[340px] shrink-0")
                        dt.cost_table.set_visibility(False)
                        dt.self_table = ui.table(columns=SELFUSE_COLUMNS, rows=[], row_key="id") \
                                          .props("dense flat bordered hide-bottom").classes("min-w-[280px] shrink-0")
                        dt.self_table.set_visibility(False)
                with ui.element("div").classes("w-full") as dt.chart_box:
                    dt.chart = ui.echart(_base_chart_options(self._dark)).classes("w-full")
                    self._hook_zoom(dt)
                self._set_chart_height(dt)

    # ------------------------------------------------------------ Heat pump tab

    def _hp_ct_options(self, saved_key=""):
        opts = {"": "Select the heat pump CT"}
        for dev_id, dev in self._devices.items():
            for n, name in dev.active_cts():
                opts[tf.CTRef(dev_id, n).key()] = f"{dev.name} · CT{n} {name}"
        if saved_key and saved_key not in opts:
            opts[saved_key] = f"{saved_key} (not found)"
        return opts

    def _build_heatpump_panel(self, hp_tab):
        """@brief Build the Heat pump tab: settings row, summary bar with a monthly table, daily chart."""
        try:
            settings = self._gui.settings_store.load().heatpump
        except Exception:
            settings = hp.HeatPumpSettings()
        p = self._hp = _HeatPumpPanel()
        month_opts = {i + 1: name for i, name in enumerate(hp.MONTH_NAMES)}
        with ui.tab_panel(hp_tab).classes("p-0 w-full"):
            with ui.column().classes("w-full gap-1"):
                with ui.row().classes("w-full items-center gap-x-3 gap-y-1"):
                    p.ct_select = ui.select(self._hp_ct_options(settings.ct_key), value=settings.ct_key,
                                            label="Heat pump CT").props("dense").classes("w-56")
                    p.threshold = ui.number("On at (W)", value=settings.threshold_w, min=1, step=10,
                                            format="%.0f").props("dense").classes("w-24")
                    p.min_minutes = ui.number("Min run/day (min)", value=settings.min_minutes, min=1, max=1440,
                                              step=5, format="%.0f").props("dense").classes("w-32")
                    p.months = ui.select(month_opts, value=list(settings.cooling_months), multiple=True,
                                         label="Cooling months").props("dense").classes("w-48")
                    p.apply_btn = ui.button("Apply", on_click=self._on_hp_apply).props("no-caps dense")
                    self._help(HELP_HEATPUMP)
                    p.status = ui.label("").classes("text-sm ct6-sub")
                p.bar = ui.expansion(value=self._hp_expanded, on_value_change=self._on_hp_bar_toggle) \
                          .props("dense dense-toggle header-class=q-px-sm").classes("w-full")
                with p.bar.add_slot("header"):
                    with ui.row().classes("w-full items-center gap-3 no-wrap"):
                        ui.label("Days").classes("text-sm text-weight-bold w-10")
                        p.summary = ui.label("").classes("text-sm ct6-sum ellipsis")
                with p.bar:
                    p.month_table = ui.table(columns=HP_MONTH_COLUMNS, rows=[], row_key="id") \
                                      .props("dense flat bordered hide-bottom virtual-scroll") \
                                      .classes("min-w-[480px]").style("max-height: 260px")
                opts = _base_chart_options(self._dark)
                text = opts["textStyle"]["color"]
                opts["xAxis"] = {**opts["xAxis"], "type": "category", "data": []}
                opts["tooltip"] = {"trigger": "axis", "axisPointer": {"type": "shadow"}}
                opts["toolbox"]["feature"] = {"saveAsImage": {}}
                opts["yAxis"] = [{**opts["yAxis"], "name": "Run hours"},
                                 {**opts["yAxis"], "name": "kWh", "position": "right", "nameGap": 40,
                                  "splitLine": {"show": False}}]
                opts["grid"]["right"] = 60
                opts["legend"]["textStyle"] = {"color": text}
                p.chart = ui.echart(opts).classes("w-full")
                self._set_hp_chart_height()

    def _hp_settings_from_widgets(self):
        p = self._hp
        if p.threshold.value is None or p.min_minutes.value is None:
            raise ValueError("Enter the on threshold and the minimum run-time.")
        s = hp.HeatPumpSettings(ct_key=p.ct_select.value or "", threshold_w=float(p.threshold.value),
                                min_minutes=float(p.min_minutes.value),
                                cooling_months=sorted(int(m) for m in (p.months.value or [])))
        s.validate()
        return s

    def _on_hp_apply(self):
        """@brief Save the Heat pump tab settings (shared by all clients) and re-read."""
        try:
            s = self._hp_settings_from_widgets()
            current = self._gui.settings_store.load()
            current.heatpump = s
            self._gui.settings_store.save(current)
        except (ValueError, OSError) as ex:
            self._show_status(HP_TAB, str(ex), error=True)
            return
        self._read_heatpump()

    def _read_heatpump(self, csv=False):
        """@brief Analyse the heat pump CT for the selected dates (or export the per-day CSV)."""
        try:
            s = self._hp_settings_from_widgets()
            start, stop = self._get_start_stop()
        except ValueError as ex:
            self._show_status(HP_TAB, str(ex), error=True)
            return
        ref = tf.CTRef.from_key(s.ct_key)
        if ref is None:
            self._show_status(HP_TAB, "Select the heat pump CT, then click Apply.", error=True)
            return
        device = self._devices.get(ref.device_id)
        if device is None:
            self._show_status(HP_TAB, "The heat pump CT's device was not found.", error=True)
            return
        if not csv:
            self._hp.summary.set_text("")
        self._start_job(self._worker_heatpump, {"settings": s, "device": device, "ct": ref.ct,
                                                "start": start, "stop": stop, "csv": csv})

    def _worker_heatpump(self, post, p):
        start_t = time()
        post(MSG_STATUS, device_id=HP_TAB, message="Reading Data...")
        s, device = p["settings"], p["device"]
        with self._gui.data_source_factory() as ds:
            records = ds.daily_run_time(device.device_id, cd.act_watts_field(p["ct"]), s.threshold_w,
                                        p["start"], p["stop"])
        result = hp.analyse(records, s)
        if p["csv"]:
            text = hp.to_csv(result)
            if not text:
                post(MSG_ERROR, device_id=HP_TAB, message="No heat pump data to export for the selected dates.")
                return
            data = text.encode("utf-8")
            ct_name = dict(device.active_cts()).get(p["ct"], f"CT{p['ct']}")
            post(MSG_DOWNLOAD, device_id=HP_TAB, content=data,
                 filename=cd.csv_filename(f"{device.name}_{ct_name}", p["start"], p["stop"], "HeatPumpDays"),
                 message=f"Exported {len(result.days)} day(s) to CSV.")
            return
        post(MSG_HEATPUMP, summary=hp.summary_text(result), months=hp.month_table_rows(result),
             chart=hp.chart_data(result, p["start"], p["stop"]))
        post(MSG_STATUS, device_id=HP_TAB,
             message=f"{len(result.days)} day(s) from minute data in {time() - start_t:.1f} seconds.")

    def _update_heatpump(self, msg):
        p = self._hp
        p.summary.set_text(msg["summary"])
        p.month_table.rows = msg["months"]
        p.month_table.update()
        c = msg["chart"]
        opts = p.chart.options
        opts["xAxis"]["data"] = c["labels"]
        names = {hp.HEATING: "Heating", hp.COOLING: "Cooling", hp.OFF: "Below min run"}
        series = [{"name": names[m], "type": "bar", "stack": "run", "barMaxWidth": 30,
                   "itemStyle": {"color": HP_COLOURS[m]}, "data": c[m]} for m in (hp.HEATING, hp.COOLING, hp.OFF)]
        series.append({"name": "kWh", "type": "line", "yAxisIndex": 1, "showSymbol": False, "connectNulls": False,
                       "lineStyle": {"width": 1.5, "color": HP_KWH_COLOUR}, "itemStyle": {"color": HP_KWH_COLOUR},
                       "data": c["kwh"]})
        opts["series"] = series
        opts["legend"]["data"] = [s["name"] for s in series]
        p.chart.update()
        self._set_hp_chart_height()

    def _on_hp_bar_toggle(self, e):
        self._hp_expanded = e.value
        self._prefs.set(up.HP_BAR_OPEN, bool(e.value))
        self._set_hp_chart_height()

    def _set_hp_chart_height(self):
        p = self._hp
        offset = CHART_OFFSET_PX - 37 + HP_SETTINGS_PX     # The kWh bar has 2 lines, this summary 1
        if self._hp_expanded:
            # The table scrolls beyond 260 px; 32 px is the expansion's padding around it.
            offset += min(260, KWH_TABLE_HEADER_PX + KWH_ROW_PX * max(1, len(p.month_table.rows)) + 8) + 32
        p.chart.style(f"height: calc(100vh - {offset}px); min-height: 300px")

    # ------------------------------------------------------------ page

    def build(self):
        """@brief Build the page for this client."""
        self._peak_label = None
        self._tab_panels = None
        username = app.storage.user.get(auth.USERNAME) if self._gui.login_manager is not None else None
        self._prefs = up.Prefs(app.storage.user, self._gui.user_prefs_file, username)
        self._dark = bool(self._prefs.get(up.DARK_THEME, self._gui.dark))
        self._kwh_expanded = bool(self._prefs.get(up.KWH_BAR_OPEN))
        self._hp_expanded = bool(self._prefs.get(up.HP_BAR_OPEN))
        ui.add_css(THEME_CSS)
        self._dark_mode = ui.dark_mode(self._dark)
        with ui.header().classes("items-center py-1"):
            ui.button(icon="menu", on_click=lambda: drawer.toggle()).props("flat round color=white")
            ui.label(self._gui.PAGE_TITLE).classes("text-lg")
            ui.space()
            ui.label(f"Software Version: {self._gui.version}").classes("text-xs")
            with ui.button(on_click=self._toggle_theme).props("flat round dense color=white") as self._theme_btn:
                self._theme_tip = ui.tooltip("")
            self._show_theme_button()
            if self._gui.login_manager is not None:
                username = app.storage.user.get(auth.USERNAME, "")
                ui.icon("person").classes("q-ml-md")
                ui.label(username).classes("text-sm")
                ui.button("Log out", icon="logout", on_click=self._logout).props("flat dense no-caps color=white")

        with ui.left_drawer(value=None, bordered=True).props("width=370").classes("q-pa-sm") as drawer:
            self._build_controls()

        with ui.column().classes("w-full gap-1"):
            self._tabs_bar = ui.tabs(on_change=None).classes("w-full").props("align=left no-caps dense inline-label")
            self._tab_panels = ui.tab_panels(self._tabs_bar, on_change=self._on_tab_change).classes("w-full")
            self._global_status = ui.label("").classes("text-sm ct6-sub")

        ui.timer(POLL_SECONDS, self._poll)
        ui.timer(LIVE_SECONDS, self._live_tick)
        self._start_job(self._worker_list_devices)

    # ------------------------------------------------------------ Tariff & CT roles dialog

    def _open_settings(self):
        """@brief Show the dialog to edit the tariff, the EV charging rule and the site CT roles."""
        try:
            settings = self._gui.settings_store.load()
        except Exception as ex:
            ui.notify(f"Failed to read {self._gui.settings_store.filename}: {ex}", type="negative")
            return
        t = settings.tariff
        rates = [r.to_dict() for r in sorted(t.rates, key=lambda r: r.valid_from)]
        if not rates:
            # Start the first rate period before the earliest data so the whole history is costed.
            first_dates = [d.first_date for d in self._devices.values() if d.first_date]
            first = min(first_dates) if first_dates else date(2000, 1, 1)
            rates = [{"valid_from": first.isoformat(), "peak": None, "offpeak": None,
                      "export": None, "standing": None}]
        r = settings.roles
        invert = self._invert_kw()      # Plotted value = -stored value
        polarity_name = self._polarity.value
        roles = {"grid": r.grid.key() if r.grid else "",
                 "ev": r.ev.key() if r.ev else "",
                 "grid_import_negative": r.grid_import_negative,
                 "solar": r.solar.key() if r.solar else "",
                 # Solar and battery signs are shown as they plot with the sidebar's current polarity.
                 "solar_sign": "auto" if r.solar_sign_auto else
                               ("below" if r.solar_gen_negative != invert else "above"),
                 "battery": r.battery.key() if r.battery else "",
                 "battery_sign": "below" if r.battery_charge_negative != invert else "above"}
        ev_rule = {"on": t.ev_slots_offpeak, "min_kwh": t.ev_slot_min_kwh,
                   "share_pc": round(t.ev_slot_min_grid_share * 100), "cap": t.ev_daily_cap_hours}

        with ui.dialog() as dialog, ui.card().classes("w-[840px] max-w-full"):
            ui.label("Tariff & CT roles").classes("text-h6")
            ui.label("Costs are for the whole site, so they are the same on every device tab.") \
              .classes("text-sm ct6-sub")
            ui.label("Off-peak window (local time). Import inside it uses the off-peak rate.").classes("text-sm ct6-sub")
            with ui.row().classes("items-center gap-4"):
                op_start = self._time_input("Off-peak start")
                op_start.value = t.offpeak_start
                op_end = self._time_input("Off-peak end")
                op_end.value = t.offpeak_end

            ui.label("Rates. Each applies from its date until the next one starts.").classes("text-sm ct6-sub q-mt-sm")

            @ui.refreshable
            def rate_rows():
                for i, rr in enumerate(rates):
                    with ui.row().classes("items-center gap-2 no-wrap"):
                        d = self._date_input("Valid from")
                        d.bind_value(rr, "valid_from")
                        for key, label in (("peak", "Peak p/kWh"), ("offpeak", "Off-peak p/kWh"),
                                           ("export", "Export p/kWh"), ("standing", "Standing p/day")):
                            ui.number(label, format="%.2f", min=0).props("dense").classes("w-28") \
                              .bind_value(rr, key)
                        ui.button(icon="delete", on_click=lambda _e, i=i: (rates.pop(i), rate_rows.refresh())) \
                          .props("flat dense round").tooltip("Remove this rate period")
            rate_rows()

            def add_rate():
                last = rates[-1] if rates else {}
                rates.append({**last, "valid_from": date.today().isoformat()})
                rate_rows.refresh()
            ui.button("Add rate period", icon="add", on_click=add_rate).props("flat dense no-caps")

            ui.separator()
            ui.checkbox("All EV charging is at the off-peak rate, and the whole house is off-peak in any half-hour "
                        "where the EV charges").bind_value(ev_rule, "on")
            with ui.row().classes("items-center gap-3") as ev_row:
                ui.number("Min EV kWh per half-hour", format="%.2f", min=0.01, step=0.05) \
                  .props("dense").classes("w-44").bind_value(ev_rule, "min_kwh")
                ui.number("Min share from grid %", format="%.0f", min=0, max=100, step=5) \
                  .props("dense").classes("w-40").bind_value(ev_rule, "share_pc") \
                  .tooltip("Stops solar-only EV charging counting as a slot. 0 = no check.")
                ui.number("Daily EV cap (hours)", format="%.1f", min=0, step=0.5) \
                  .props("dense").classes("w-36").bind_value(ev_rule, "cap") \
                  .tooltip("Off-peak EV charging allowed per day (midday to midday), "
                           "e.g. 6 h on Intelligent Octopus Go. Beyond it EV charging is costed at peak. 0 = no cap.")
            ev_row.bind_visibility_from(ev_rule, "on")

            ui.separator()
            ui.label("CT roles. Each can be on any CT6 device. Solar and battery CTs are optional "
                     "(for the self-consumption figures).").classes("text-sm ct6-sub")
            sign_opts = {True: "Import is negative (CT6 default)", False: "Import is positive"}
            ct_opts = {"": "None"}
            for dev_id, dev in self._devices.items():
                for n, name in dev.active_cts():
                    ct_opts[tf.CTRef(dev_id, n).key()] = f"{dev.name} · CT{n} {name}"
            # Keep a saved CT that isn't currently listed (e.g. device offline) selectable.
            for key in (roles["grid"], roles["ev"], roles["solar"], roles["battery"]):
                if key and key not in ct_opts:
                    ct_opts[key] = f"{key} (not found)"
            with ui.row().classes("items-center gap-3"):
                ui.select(ct_opts, label="Grid CT").props("dense").classes("w-60").bind_value(roles, "grid")
                ui.select(sign_opts, label="Grid CT sign").props("dense").classes("w-60") \
                  .bind_value(roles, "grid_import_negative")
            with ui.row().classes("items-center gap-3"):
                ui.select(ct_opts, label="EV CT").props("dense").classes("w-60").bind_value(roles, "ev")
            with ui.row().classes("items-center gap-3"):
                ui.select(ct_opts, label="Solar CT").props("dense").classes("w-60").bind_value(roles, "solar")
                ui.select({"auto": "Detect automatically", "above": "Generation plots above 0",
                           "below": "Generation plots below 0"},
                          label="Solar generation").props("dense").classes("w-60").bind_value(roles, "solar_sign")
            with ui.row().classes("items-center gap-3"):
                ui.select(ct_opts, label="Battery CT").props("dense").classes("w-60").bind_value(roles, "battery")
                ui.select({"above": "Charging plots above 0", "below": "Charging plots below 0"},
                          label="Battery charging").props("dense").classes("w-60") \
                  .bind_value(roles, "battery_sign")
            ui.label(f"Above/below 0 are as the plot shows them with the polarity set to '{polarity_name}'.") \
              .classes("text-xs ct6-sub")

            error = ui.label("").classes("text-negative text-sm")

            def save():
                try:
                    new_rates = []
                    for rr in rates:
                        if any(rr.get(k) is None for k in ("peak", "offpeak", "export")):
                            raise ValueError("Enter the peak, off-peak and export rates for every rate period.")
                        new_rates.append(tf.RatePeriod.from_dict({**rr, "standing": rr.get("standing") or 0.0}))
                    if any(ev_rule[k] is None for k in ("min_kwh", "share_pc", "cap")):
                        raise ValueError("Enter all the EV slot settings.")
                    tariff = tf.Tariff(str(op_start.value or ""), str(op_end.value or ""), new_rates,
                                       ev_slots_offpeak=bool(ev_rule["on"]),
                                       ev_slot_min_kwh=float(ev_rule["min_kwh"]),
                                       ev_slot_min_grid_share=float(ev_rule["share_pc"]) / 100.0,
                                       ev_daily_cap_hours=float(ev_rule["cap"]))
                    site_roles = tf.SiteRoles(grid=tf.CTRef.from_key(roles["grid"]),
                                              ev=tf.CTRef.from_key(roles["ev"]),
                                              grid_import_negative=bool(roles["grid_import_negative"]),
                                              solar=tf.CTRef.from_key(roles["solar"]),
                                              solar_sign_auto=roles["solar_sign"] == "auto",
                                              solar_gen_negative=r.solar_gen_negative
                                              if roles["solar_sign"] == "auto"
                                              else (roles["solar_sign"] == "below") != invert,
                                              battery=tf.CTRef.from_key(roles["battery"]),
                                              battery_charge_negative=(roles["battery_sign"] == "below") != invert)
                    site_roles.check()
                    if tariff.ev_slots_offpeak and site_roles.ev is None:
                        raise ValueError("Select the EV CT to use the EV charging rule.")
                    current = self._gui.settings_store.load()   # Keep the Heat pump tab settings
                    current.tariff, current.roles = tariff, site_roles
                    self._gui.settings_store.save(current)
                except (ValueError, KeyError) as ex:
                    error.set_text(str(ex))
                    return
                except OSError as ex:
                    error.set_text(f"Failed to save the settings: {ex}")
                    return
                dialog.close()
                ui.notify("Tariff & CT roles saved.", type="positive")
                self._read_selected()

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat no-caps")
                ui.button("Save", on_click=save).props("no-caps")
        dialog.open()

    def _logout(self):
        self._gui.log_event(f"logout {app.storage.user.get(auth.USERNAME, '')}", self._address)
        app.storage.user.clear()
        ui.navigate.to("/login")

    def _date_input(self, label):
        with ui.input(label).props("dense").classes("w-32") as inp:
            with ui.menu().props("no-parent-event") as menu:
                ui.date(mask="YYYY-MM-DD").bind_value(inp)
            with inp.add_slot("append"):
                ui.icon("edit_calendar").on("click", menu.open).classes("cursor-pointer")
        return inp

    def _time_input(self, label):
        with ui.input(label, validation={"HH:MM": lambda v: _valid_hhmm(v)}).props("dense").classes("w-24") as inp:
            with ui.menu().props("no-parent-event") as menu:
                ui.time(mask="HH:mm").props("format24h").bind_value(inp)
            with inp.add_slot("append"):
                ui.icon("schedule").on("click", menu.open).classes("cursor-pointer")
        return inp

    def _date_row(self, label, time_label):
        with ui.row().classes("items-center gap-1 no-wrap"):
            back = ui.button("<").props("dense flat")
            date_input = self._date_input(label)
            fwd = ui.button(">").props("dense flat")
            time_input = self._time_input(time_label)
        back.on_click(lambda: self._step_date(date_input, -1))
        fwd.on_click(lambda: self._step_date(date_input, 1))
        self._controls += [back, fwd]
        return date_input, time_input

    def _help(self, text):
        ui.icon("help_outline").classes("ct6-sub cursor-help").tooltip(text)

    def _build_controls(self):
        with ui.column().classes("w-full gap-3"):
            update_btn = ui.button("Update", icon="refresh", on_click=self._on_update).classes("w-full")
            csv_btn = ui.button("Download CSV", icon="download", on_click=self._on_csv) \
                        .props("outline no-caps dense").classes("w-full") \
                        .tooltip("Save the selected device's data for the selected dates and resolution "
                                 "(every column, values as stored). On the Energy view, saves the bar figures.")
            ui.button("Tariff & CT roles", icon="payments", on_click=self._open_settings) \
              .props("outline no-caps dense").classes("w-full")
            self._controls += [update_btn, csv_btn]

            with ui.grid(columns=2).classes("w-full gap-1"):
                for preset in cd.PRESETS:
                    b = ui.button(preset, on_click=lambda _e, p=preset: self._on_preset(p)) \
                          .props("outline no-caps dense")
                    self._controls.append(b)

            self._start_date, self._start_time = self._date_row("Start Date", "Start Time")
            self._stop_date, self._stop_time = self._date_row("Stop Date", "Stop Time")

            with ui.row().classes("items-center gap-1 no-wrap"):
                self._resolution = ui.toggle([r.value for r in Resolution], value=Resolution.MIN.value,
                                             on_change=lambda e: self._remember(up.RESOLUTION, e.value)) \
                                     .props("no-caps dense")
                self._help(HELP_RESOLUTION)
            with ui.row().classes("items-center gap-1 no-wrap"):
                power_types = [p.value for p in PowerType]
                self._power_type = ui.toggle(power_types,
                                             value=self._valid_pref(up.POWER_TYPE, power_types, PowerType.ACTIVE.value),
                                             on_change=lambda e: self._remember(up.POWER_TYPE, e.value)) \
                                     .props("no-caps dense")
                self._help(HELP_POWER_TYPE)
            with ui.row().classes("items-center gap-1 no-wrap"):
                default_pol = Polarity.IMPORT_NEGATIVE if self._options.negative else Polarity.IMPORT_POSITIVE
                polarities = [p.value for p in Polarity]
                self._polarity = ui.toggle(polarities, value=self._valid_pref(up.POLARITY, polarities, default_pol.value),
                                           on_change=lambda e: self._remember(up.POLARITY, e.value)) \
                                   .props("no-caps dense")
                self._help(HELP_POLARITY)
            with ui.row().classes("items-center gap-1 no-wrap"):
                self._gaps = ui.checkbox("Show data gaps as breaks",
                                         value=bool(self._prefs.get(up.SHOW_GAPS)),
                                         on_change=self._on_gaps_change).props("dense")
                self._help(HELP_GAPS)
            with ui.row().classes("items-center gap-1 no-wrap"):
                compares = [c.value for c in Compare]
                self._compare = ui.select(compares, label="Compare with",
                                          value=self._valid_pref(up.COMPARE, compares, Compare.OFF.value),
                                          on_change=self._on_compare_change).props("dense").classes("w-44")
                self._help(HELP_COMPARE)
            with ui.row().classes("items-center gap-1 no-wrap"):
                self._zoom_refine = ui.checkbox("Load finer data when zoomed in",
                                                value=bool(self._prefs.get(up.ZOOM_REFINE)),
                                                on_change=lambda e: self._remember(up.ZOOM_REFINE, bool(e.value))) \
                                      .props("dense")
                self._help(HELP_ZOOM)
            self._controls += [self._resolution, self._power_type, self._polarity, self._gaps, self._compare]

            ui.separator()
            ui.label("Peak daily kWh").classes("text-sm ct6-sub")
            with ui.row().classes("items-center gap-2 no-wrap"):
                self._peak_ct = ui.select([], label="CT Port").props("dense").classes("w-36")
                peak_btn = ui.button("Find Peak Day", on_click=self._on_find_peak).props("no-caps dense")
                self._help(HELP_PEAK)
            self._peak_label = ui.label("").classes("text-sm whitespace-normal")
            self._controls += [peak_btn]

            ui.separator()
            where = "for your login" if self._prefs.per_user else "in this browser"
            ui.label(f"Display settings (tab, dates preset, resolution, plot type, polarity, theme and so on) "
                     f"are remembered {where}.").classes("text-xs ct6-sub whitespace-normal")
            ui.button("Reset display settings", icon="restart_alt", on_click=self._reset_prefs) \
              .props("flat dense no-caps size=sm").classes("self-start")


def _kw_text(kw):
    """@return kW formatted to 2 decimal places, without a '-0.00'."""
    return f"{0.0 if abs(kw) < 0.005 else kw:.2f} kW"


def _valid_hhmm(value):
    try:
        datetime.strptime(str(value).strip(), "%H:%M")
        return True
    except ValueError:
        return False


class CT6Dash2GUI:
    """@brief Serves the ct6_dash2 NiceGUI dashboard."""

    PAGE_TITLE = "CT6 Dashboard 2"          # Header and browser tab title (tells it apart from ct6_dash)

    def __init__(self, uio, options, data_source_factory, address, port, access_log_file=None,
                 version="", dark=True, login_manager=None, storage_path=None, storage_secret=None,
                 settings_store=None):
        """@param uio A UIO instance.
           @param options The argparse options (uses maxpp, maxdp, negative, no_gui).
           @param data_source_factory A callable returning a new CT6DataSource (called once per job).
           @param address The address to serve on ("" = all interfaces).
           @param port The TCP port to serve on.
           @param access_log_file If set, page accesses are appended to this file.
           @param version The software version shown in the GUI.
           @param dark If True use the dark theme.
           @param login_manager A ct6_dash2_auth.LoginManager to require a login, or None for no login.
           @param storage_path The folder NiceGUI keeps per-browser session data in.
           @param storage_secret The secret used to sign session cookies (required for login).
           @param settings_store A ct6_tariff.SettingsStore holding the tariff and CT roles."""
        self.uio = uio
        self.options = options
        self.data_source_factory = data_source_factory
        self.half_hour_cache = HalfHourEnergyCache()
        self.address = address
        self.port = int(port)
        self.access_log_file = access_log_file
        self.version = version
        self.dark = dark
        self.login_manager = login_manager
        self.storage_path = storage_path
        self.storage_secret = storage_secret
        self.settings_store = settings_store or tf.SettingsStore("ct6Dash2Settings.json")
        # With login, display settings are remembered per user in a file next to the settings file.
        self.user_prefs_file = up.UserPrefsFile(os.path.join(
            os.path.dirname(os.path.abspath(self.settings_store.filename)), USER_PREFS_FILENAME)) \
            if login_manager is not None else None
        if login_manager is not None and not storage_secret:
            raise ValueError("A storage secret is required when login is enabled.")

    @staticmethod
    def _client_address(request):
        return request.client.host if request is not None and request.client else "?"

    def log_event(self, text, address="?"):
        """@brief Record an access/login event in the access log file (if configured)."""
        if not self.access_log_file:
            return
        try:
            with open(self.access_log_file, "a") as fd:
                fd.write(f"{datetime.now().isoformat(timespec='seconds')} {address} {text}\n")
        except Exception as ex:
            self.uio.debug(f"Access log write failed: {ex}")

    def _add_login(self):
        """@brief Require a login for every page except /login (and NiceGUI's own assets)."""
        mgr = self.login_manager

        class AuthMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                path = request.url.path
                if not (path.startswith("/_nicegui") or path in ("/login", "/favicon.ico")):
                    if mgr.session_user(app.storage.user) is None:
                        return RedirectResponse(f"/login?redirect_to={quote(path)}")
                return await call_next(request)

        app.add_middleware(AuthMiddleware)

        @ui.page("/login", title=f"{self.PAGE_TITLE} - Log in")
        def login_page(request: Request, redirect_to: str = "/"):
            target = auth.safe_redirect(redirect_to)
            if mgr.session_user(app.storage.user) is not None:
                return RedirectResponse(target)
            address = self._client_address(request)

            async def try_login():
                user = (username.value or "").strip()
                remaining = mgr.lockout_remaining(address)
                if remaining:
                    message.set_text(f"Too many failed logins. Try again in {remaining} seconds.")
                    return
                login_btn.disable()
                message.set_text("")
                try:
                    ok = await run.io_bound(mgr.verify, user, password.value or "")
                    if ok:
                        mgr.clear_failures(address)
                        app.storage.user.update(mgr.new_session(user))
                        self.log_event(f"login {user}", address)
                        self.uio.info(f"ct6_dash2: {user} logged in from {address}.")
                        ui.navigate.to(target)
                        return
                    locked = mgr.record_failure(address)
                    self.log_event(f"login failed {user}", address)
                    self.uio.warn(f"ct6_dash2: failed login for '{user}' from {address}.")
                    await asyncio.sleep(auth.FAILURE_DELAY_SECS)
                    if locked:
                        message.set_text(f"Too many failed logins. Try again in {auth.LOCKOUT_SECS // 60} minutes.")
                    else:
                        message.set_text("Incorrect username or password.")
                    password.value = ""
                finally:
                    login_btn.enable()

            ui.dark_mode(bool(app.storage.user.get(up.STORAGE_PREFIX + up.DARK_THEME, self.dark)))
            with ui.card().classes("absolute-center w-80 q-pa-lg"):
                ui.label(self.PAGE_TITLE).classes("text-h6")
                username = ui.input("Username").props("autofocus autocomplete=username").classes("w-full")
                password = ui.input("Password", password=True, password_toggle_button=True) \
                             .props("autocomplete=current-password").classes("w-full")
                message = ui.label("").classes("text-negative text-sm")
                login_btn = ui.button("Log in", on_click=try_login).classes("w-full")
                username.on("keydown.enter", lambda: password.run_method("focus"))
                password.on("keydown.enter", try_login)

    def run(self):
        """@brief Start the web server. Blocks until shutdown."""
        if self.storage_path:
            # Keep session data with the config rather than in the working directory
            # (which may not be writable when running as a service).
            Storage.path = Path(self.storage_path).resolve()
            Storage.path.mkdir(mode=0o700, parents=True, exist_ok=True)
            Storage.path.chmod(0o700)   # Session files are only for this user
        if self.login_manager is not None:
            self._add_login()

        @ui.page("/")
        def index(request: Request):
            address = self._client_address(request)
            if self.login_manager is not None and self.login_manager.session_user(app.storage.user) is None:
                return RedirectResponse("/login")
            self.log_event("GET /", address)
            _ClientSession(self, address).build()

        app.on_startup(lambda: self.uio.info(f"ct6_dash2 serving on port {self.port}."))
        ui.run(host=self.address or "0.0.0.0",
               port=self.port,
               title=self.PAGE_TITLE,
               dark=self.dark,
               reload=False,
               show=not self.options.no_gui,
               show_welcome_message=False,
               storage_secret=self.storage_secret,
               uvicorn_logging_level="debug" if self.uio.isDebugEnabled() else "warning")
