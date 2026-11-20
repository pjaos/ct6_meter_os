#!/usr/bin/env python3
"""@brief NiceGUI dashboard for viewing CT6 data (ct6_dash2).

   Threading model
   - Every action that touches the database runs in a worker thread.
   - Workers never touch widgets. They post dicts onto a queue.Queue.
   - Each browser client has its own queue and its own 100 ms ui.timer that
     drains the queue and updates that client's widgets.
   - Each request carries an incrementing job ID. Messages from older jobs are
     dropped so the newest request always wins."""

import queue
import threading
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from time import time

from nicegui import app, ui

from ct6 import ct6_data as cd
from ct6.ct6_data import PlotType, PowerType, Polarity, Resolution, EnergyBucket

# Message types posted by worker threads.
MSG_STATUS = "status"
MSG_DEVICES = "devices"
MSG_PLOT_DATA = "plot_data"
MSG_SUMMARY_ROW = "summary_row"
MSG_PEAK_RESULT = "peak_result"
MSG_ENABLE_CONTROLS = "enable_controls"
MSG_ERROR = "error"
MSG_DONE = "done"
MSG_DOWNLOAD = "download"
MSG_LIVE = "live"           # Live tab update (has its own request counter, see _start_live_job())

LIVE_TAB = "__live__"       # Tab name of the Live tab
LIVE_SECONDS = 2.0          # Live tab refresh period
LIVE_STATUS_COLOURS = {"ok": "text-positive", "stale": "text-warning", "offline": "text-negative"}

# The ECharts default palette. Energy bars set colours explicitly (two series per CT)
# using the same order, so a CT keeps its colour in every view.
PALETTE = ["#5470c6", "#91cc75", "#fac858", "#ee6666", "#73c0de", "#3ba272", "#fc8452", "#9a60b4", "#ea7ccc"]
HELP_ENERGY_BUCKET = "Energy per bar. Auto = one bar per day for ranges up to " \
                     f"{cd.ENERGY_AUTO_MAX_DAYS} days, else one bar per month."

# Chart height = viewport height minus the space used by the header, tabs,
# plot type selector and the collapsed kWh bar.
CHART_OFFSET_PX = 235
KWH_ROW_PX = 29
KWH_TABLE_HEADER_PX = 36

POLL_SECONDS = 0.1
MAX_MSGS_PER_POLL = 200

HELP_RESOLUTION = "Select the plot resolution."
HELP_POWER_TYPE = "Select the power type. Active = Power normally charged by electricity supplier."
HELP_POLARITY = "Select imported electrical power to be plotted as negative or positive values."
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
]


def _base_chart_options(dark=True):
    text = "#cccccc" if dark else "#333333"
    grid_line = "#3a3a3a" if dark else "#e0e0e0"
    axis_line = {"lineStyle": {"color": "#777777"}}
    return {
        "animation": False,
        "backgroundColor": "transparent",
        "textStyle": {"color": text},
        "tooltip": {"trigger": "axis"},
        "legend": {"type": "scroll", "top": 0, "left": "center", "textStyle": {"color": text}},
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
    bucket_toggle: object = None  # Auto/Day/Month (Energy plot only)
    bucket_row: object = None
    mode: str = "line"          # Current chart layout: "line" or "bar"
    chart_box: object = None    # Container the chart is (re)built in


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

    def __init__(self, gui):
        self._gui = gui
        self._uio = gui.uio
        self._options = gui.options
        self._queue = queue.Queue()
        self._job_id = 0
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
            self._update_summary_row(msg["device_id"], msg["row"])
        elif t == MSG_PEAK_RESULT:
            self._peak_label.set_text(msg["message"])
        elif t == MSG_ENABLE_CONTROLS:
            self._set_controls_enabled(msg["enabled"])
        elif t == MSG_DOWNLOAD:
            ui.download.content(msg["content"], msg["filename"], media_type="text/csv")
            self._show_status(msg["device_id"], msg["message"])
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
        post(MSG_STATUS, device_id=dev_id,
             message=f"Energy per {bucket.value.lower()} from minute data: {len(labels)} bar(s) "
                     f"in {time() - start_t:.1f} seconds.")

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
        if plot_type.is_per_ct:
            is_power = plot_type == PlotType.POWER
            for ct_number, name in device.active_cts():
                column = cd.ct_field(ct_number, plot_type, p["power_type"])
                points = cd.build_series(rows, column, p["resolution"], p["invert"], is_power=is_power)
                if not is_power:
                    points = [[x, abs(y)] for x, y in points]
                reduced = cd.downsample_minmax(points, p["maxdp"])
                downsampled |= len(reduced) < len(points)
                series.append({"name": name, "data": reduced})
        else:
            points = cd.build_series(rows, plot_type.single_field, p["resolution"], is_power=False)
            reduced = cd.downsample_minmax(points, p["maxdp"])
            downsampled = len(reduced) < len(points)
            series.append({"name": plot_type.single_trace_name(), "data": reduced})

        post(MSG_PLOT_DATA, device_id=dev_id, series=series,
             y_label=plot_type.y_axis_label(p["power_type"]), scale=plot_type != PlotType.POWER,
             has_kwh=plot_type.is_per_ct)

        if plot_type.is_per_ct:
            for ct_number, name in device.active_cts():
                kwh = cd.calc_kwh(rows, cd.act_watts_field(ct_number), p["invert"])
                post(MSG_SUMMARY_ROW, device_id=dev_id, row=cd.summary_row(ct_number, name, kwh, p["invert"]))

        msg = f"Took {time() - start_t:.1f} seconds to read and plot the data " \
              f"({len(rows)} rows, DB read {read_secs:.1f} s)."
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
        dt = self._selected_tab()
        if dt is None:
            ui.notify("Select a device tab to export its data.", type="info")
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
                  "bucket": EnergyBucket(dt.bucket_toggle.value)}
        self._start_job(self._worker_read, params)

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

    def _on_preset(self, preset):
        r = cd.preset_range(preset)
        dt = self._selected_tab()
        self._suppress_events = True
        try:
            self._resolution.value = r.resolution.value
            self._start_date.value = r.start_date.isoformat()
            self._start_time.value = r.start_time
            self._stop_date.value = r.stop_date.isoformat()
            self._stop_time.value = r.stop_time
            if dt is not None and dt.plot_toggle.value != PlotType.ENERGY.value:
                dt.plot_toggle.value = PlotType.POWER.value
        finally:
            self._suppress_events = False
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
        dt = self._selected_tab()
        if dt is not None and dt.device.device_id == device_id and dt.plot_toggle.value:
            self._read_selected()

    def _on_bucket_change(self, device_id):
        if self._suppress_events:
            return
        dt = self._selected_tab()
        if dt is not None and dt.device.device_id == device_id and dt.plot_toggle.value == PlotType.ENERGY.value:
            self._read_selected()

    def _on_tab_change(self):
        if self._suppress_events:
            return
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

    def _show_status(self, device_id, message, error=False):
        dt = self._tabs.get(device_id) if device_id else self._selected_tab()
        label = dt.status if dt else self._global_status
        label.set_text(message)
        label.classes(replace="text-sm " + ("text-negative" if error else "text-grey-5"))

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
            opts["series"] = [{"name": s["name"], "type": "line", "showSymbol": False, "sampling": "lttb",
                               "lineStyle": {"width": 2}, "emphasis": {"disabled": True}, "data": s["data"]}
                              for s in msg["series"]]
            opts["legend"]["data"] = [s["name"] for s in msg["series"]]
        dt.chart.update()
        dt.kwh_bar.set_visibility(msg["has_kwh"])
        self._set_chart_height(dt)

    def _set_chart_mode(self, dt, mode):
        """@brief Switch a device chart between the time series ("line") and Energy ("bar") layouts."""
        if dt.mode == mode:
            return
        dt.mode = mode
        opts = _base_chart_options(self._gui.dark)
        if mode == "bar":
            opts["xAxis"] = {**opts["xAxis"], "type": "category", "data": []}
            opts["tooltip"] = {"trigger": "axis", "axisPointer": {"type": "shadow"}}
            opts["toolbox"]["feature"] = {"saveAsImage": {}}
        # Rebuild the chart element: ECharts doesn't reliably switch axis types in place.
        dt.chart_box.clear()
        with dt.chart_box:
            dt.chart = ui.echart(opts).classes("w-full")
        self._set_chart_height(dt)

    def _update_summary_row(self, device_id, row):
        dt = self._tabs.get(device_id)
        if dt is None:
            return
        rows = [r for r in dt.table.rows if r["ct"] != row["ct"]] + [row]
        dt.table.rows = sorted(rows, key=lambda r: r["ct"])
        dt.table.update()
        dt.kwh_summary.set_text(" · ".join(f"{r['sensor']} {r['total']}" for r in dt.table.rows))

    def _clear_summary(self, dt):
        dt.table.rows = []
        dt.table.update()
        dt.kwh_summary.set_text("")

    def _kwh_table_px(self, dt):
        """@return The height the open kWh table adds below its header."""
        return KWH_TABLE_HEADER_PX + KWH_ROW_PX * max(1, len(dt.device.active_cts())) + 8

    def _set_chart_height(self, dt):
        """@brief Size the chart so the page fits the window with the kWh table open or closed."""
        offset = CHART_OFFSET_PX
        if self._kwh_expanded and dt.kwh_bar.visible:
            offset += self._kwh_table_px(dt)
        dt.chart.style(f"height: calc(100vh - {offset}px); min-height: 300px")

    def _on_kwh_toggle(self, value):
        """@brief Keep the kWh table open/closed state the same on every tab."""
        if self._suppress_events or value == self._kwh_expanded:
            return
        self._kwh_expanded = value
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
            with self._tab_panels:
                self._build_live_panel(live_tab, devices)
                for dev in devices:
                    self._build_device_panel(self._tabs[dev.device_id])
            self._tab_panels.value = devices[0].device_id
        finally:
            self._suppress_events = False
        self._update_peak_options()
        # On startup show today's data (as ct6_dash).
        self._on_preset("Today")

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
                            card.age = ui.label("").classes("text-sm text-grey-5")
                            ui.space()
                            card.stats = ui.label("").classes("text-sm text-grey-4")
                        with ui.row().classes("w-full gap-6"):
                            for ct_number, name in dev.active_cts():
                                with ui.column().classes("gap-0"):
                                    ui.label(name).classes("text-xs text-grey-5")
                                    card.ct_values[ct_number] = ui.label("–").classes("text-h6")
                        opts = _base_chart_options(self._gui.dark)
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
                    dt.status = ui.label("").classes("text-sm text-grey-5")
                # kWh table above the plot, collapsed by default. The header shows the totals.
                dt.kwh_bar = ui.expansion(value=self._kwh_expanded,
                                          on_value_change=lambda e: self._on_kwh_toggle(e.value)) \
                               .props("dense dense-toggle header-class=q-px-sm").classes("w-full")
                with dt.kwh_bar.add_slot("header"):
                    with ui.row().classes("w-full items-center gap-3 no-wrap"):
                        ui.label("kWh").classes("text-sm text-weight-bold")
                        dt.kwh_summary = ui.label("").classes("text-sm text-grey-4 ellipsis")
                with dt.kwh_bar:
                    dt.table = ui.table(columns=SUMMARY_COLUMNS, rows=[], row_key="ct") \
                                 .props("dense flat bordered hide-bottom").classes("min-w-[340px]")
                with ui.element("div").classes("w-full") as dt.chart_box:
                    dt.chart = ui.echart(_base_chart_options(self._gui.dark)).classes("w-full")
                self._set_chart_height(dt)

    # ------------------------------------------------------------ page

    def build(self):
        """@brief Build the page for this client."""
        self._peak_label = None
        self._tab_panels = None
        with ui.header().classes("items-center py-1"):
            ui.button(icon="menu", on_click=lambda: drawer.toggle()).props("flat round color=white")
            ui.label(self._gui.PAGE_TITLE).classes("text-lg")
            ui.space()
            ui.label(f"Software Version: {self._gui.version}").classes("text-xs")

        with ui.left_drawer(value=None, bordered=True).props("width=370").classes("q-pa-sm") as drawer:
            self._build_controls()

        with ui.column().classes("w-full gap-1"):
            self._tabs_bar = ui.tabs(on_change=None).classes("w-full").props("align=left no-caps")
            self._tab_panels = ui.tab_panels(self._tabs_bar, on_change=self._on_tab_change).classes("w-full")
            self._global_status = ui.label("").classes("text-sm text-grey-5")

        ui.timer(POLL_SECONDS, self._poll)
        ui.timer(LIVE_SECONDS, self._live_tick)
        self._start_job(self._worker_list_devices)

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
        ui.icon("help_outline").classes("text-grey-5 cursor-help").tooltip(text)

    def _build_controls(self):
        with ui.column().classes("w-full gap-3"):
            update_btn = ui.button("Update", icon="refresh", on_click=self._on_update).classes("w-full")
            csv_btn = ui.button("Download CSV", icon="download", on_click=self._on_csv) \
                        .props("outline no-caps dense").classes("w-full") \
                        .tooltip("Save the selected device's data for the selected dates and resolution "
                                 "(every column, values as stored). On the Energy view, saves the bar figures.")
            self._controls += [update_btn, csv_btn]

            with ui.grid(columns=2).classes("w-full gap-1"):
                for preset in cd.PRESETS:
                    b = ui.button(preset, on_click=lambda _e, p=preset: self._on_preset(p)) \
                          .props("outline no-caps dense")
                    self._controls.append(b)

            self._start_date, self._start_time = self._date_row("Start Date", "Start Time")
            self._stop_date, self._stop_time = self._date_row("Stop Date", "Stop Time")

            with ui.row().classes("items-center gap-1 no-wrap"):
                self._resolution = ui.toggle([r.value for r in Resolution], value=Resolution.MIN.value) \
                                     .props("no-caps dense")
                self._help(HELP_RESOLUTION)
            with ui.row().classes("items-center gap-1 no-wrap"):
                self._power_type = ui.toggle([p.value for p in PowerType], value=PowerType.ACTIVE.value) \
                                     .props("no-caps dense")
                self._help(HELP_POWER_TYPE)
            with ui.row().classes("items-center gap-1 no-wrap"):
                default_pol = Polarity.IMPORT_NEGATIVE if self._options.negative else Polarity.IMPORT_POSITIVE
                self._polarity = ui.toggle([p.value for p in Polarity], value=default_pol.value) \
                                   .props("no-caps dense")
                self._help(HELP_POLARITY)
            self._controls += [self._resolution, self._power_type, self._polarity]

            ui.separator()
            ui.label("Peak daily kWh").classes("text-sm text-grey-5")
            with ui.row().classes("items-center gap-2 no-wrap"):
                self._peak_ct = ui.select([], label="CT Port").props("dense").classes("w-36")
                peak_btn = ui.button("Find Peak Day", on_click=self._on_find_peak).props("no-caps dense")
                self._help(HELP_PEAK)
            self._peak_label = ui.label("").classes("text-sm whitespace-normal")
            self._controls += [peak_btn]


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

    PAGE_TITLE = "CT6 Dashboard"

    def __init__(self, uio, options, data_source_factory, address, port, access_log_file=None,
                 version="", dark=True):
        """@param uio A UIO instance.
           @param options The argparse options (uses maxpp, maxdp, negative, no_gui).
           @param data_source_factory A callable returning a new CT6DataSource (called once per job).
           @param address The address to serve on ("" = all interfaces).
           @param port The TCP port to serve on.
           @param access_log_file If set, page accesses are appended to this file.
           @param version The software version shown in the GUI.
           @param dark If True use the dark theme."""
        self.uio = uio
        self.options = options
        self.data_source_factory = data_source_factory
        self.address = address
        self.port = int(port)
        self.access_log_file = access_log_file
        self.version = version
        self.dark = dark

    def _log_access(self, client):
        if not self.access_log_file:
            return
        try:
            host = client.request.client.host if client.request and client.request.client else "?"
            with open(self.access_log_file, "a") as fd:
                fd.write(f"{datetime.now().isoformat(timespec='seconds')} {host} GET /\n")
        except Exception as ex:
            self.uio.debug(f"Access log write failed: {ex}")

    def run(self):
        """@brief Start the web server. Blocks until shutdown."""
        @ui.page("/")
        def index(client):
            self._log_access(client)
            _ClientSession(self).build()

        app.on_startup(lambda: self.uio.info(f"ct6_dash2 serving on port {self.port}."))
        ui.run(host=self.address or "0.0.0.0",
               port=self.port,
               title=self.PAGE_TITLE,
               dark=self.dark,
               reload=False,
               show=not self.options.no_gui,
               show_welcome_message=False,
               uvicorn_logging_level="debug" if self.uio.isDebugEnabled() else "warning")
