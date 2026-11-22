#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""
Heat pump run days for the ct6_dash2 Heat pump tab (pure Python, no GUI or SQL).

The same idea as ct6_heatpump_days.py: a day is an "on" day when the heat pump
(one CT port) ran at or above a power threshold for at least a minimum time,
and on days are labelled heating or cooling by calendar month.

Differences from ct6_heatpump_days.py, so the tab is quick on a year of data
and works on MySQL (any version) and SQLite:
- It uses the minute table (CT6_SENSOR_MINUTE, 1 minute averages written by
  ct6_db_store) instead of the ~1 per second CT6_SENSOR table. A minute counts
  as running when its average power is at or above the threshold.
- Run-time is the number of such minutes. A missing minute (device offline)
  simply isn't counted, so no gap capping is needed.
- It also reports the heat pump's kWh per day, per month and per mode.
"""

import csv
import io
from dataclasses import dataclass, field
from datetime import timedelta

from ct6.ct6_heatpump_days import DEFAULT_COOLING_MONTHS, classifyDays

DEFAULT_THRESHOLD_W = 100.0
DEFAULT_MIN_MINUTES = 10.0
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

HEATING = "heating"
COOLING = "cooling"
OFF = "off"


@dataclass
class HeatPumpSettings:
    """@brief The Heat pump tab settings (saved with the tariff in ct6Dash2Settings.json)."""
    ct_key: str = ""                        # ct6_tariff.CTRef key of the heat pump CT, "" = not set
    threshold_w: float = DEFAULT_THRESHOLD_W
    min_minutes: float = DEFAULT_MIN_MINUTES
    cooling_months: list = field(default_factory=lambda: list(DEFAULT_COOLING_MONTHS))

    def validate(self):
        if not self.threshold_w > 0:
            raise ValueError("The heat pump on threshold must be more than 0 W.")
        if not 0 < self.min_minutes <= 1440:
            raise ValueError("The minimum run-time per day must be between 1 and 1440 minutes.")
        if any(m not in range(1, 13) for m in self.cooling_months):
            raise ValueError("Cooling months must be 1 to 12.")

    def to_dict(self):
        return {"ct": self.ct_key, "threshold_w": self.threshold_w, "min_minutes": self.min_minutes,
                "cooling_months": sorted(set(int(m) for m in self.cooling_months))}

    @staticmethod
    def from_dict(d):
        d = d or {}
        return HeatPumpSettings(ct_key=str(d.get("ct", "") or ""),
                                threshold_w=float(d.get("threshold_w", DEFAULT_THRESHOLD_W)),
                                min_minutes=float(d.get("min_minutes", DEFAULT_MIN_MINUTES)),
                                cooling_months=[int(m) for m in d.get("cooling_months", DEFAULT_COOLING_MONTHS)])


@dataclass
class HeatPumpResult:
    days: list          # One dict per day with data (see analyse())
    summary: dict
    months: list        # One dict per month with data


def analyse(records, settings):
    """@brief Classify days and total run-time and kWh.
       @param records From CT6DataSource.daily_run_time(): dicts with day, on_minutes,
                      minutes, peak_w and kwh, oldest first.
       @param settings A HeatPumpSettings.
       @return A HeatPumpResult. Each day dict has date, on_minutes, peak_watts, samples,
               on, mode (as ct6_heatpump_days.py) plus kwh."""
    rows = [(r["day"], float(r["on_minutes"] or 0) * 60.0, r["peak_w"], r["minutes"]) for r in records]
    days, summary = classifyDays(rows, settings.min_minutes, set(settings.cooling_months))
    for d, r in zip(days, records):
        d["kwh"] = round(float(r["kwh"] or 0.0), 3)

    run_minutes = {HEATING: 0.0, COOLING: 0.0, OFF: 0.0}
    kwh = {HEATING: 0.0, COOLING: 0.0, OFF: 0.0}
    months = {}
    for d in days:
        run_minutes[d["mode"]] += d["on_minutes"]
        kwh[d["mode"]] += d["kwh"]
        key = d["date"][:7]
        m = months.setdefault(key, {"month": key, "days_with_data": 0, "on_days": 0, "run_minutes": 0.0,
                                    "kwh": 0.0, "mode": COOLING if int(key[5:7]) in settings.cooling_months
                                    else HEATING})
        m["days_with_data"] += 1
        m["on_days"] += 1 if d["on"] else 0
        m["run_minutes"] += d["on_minutes"]
        m["kwh"] += d["kwh"]
    summary.update({
        "run_hours": sum(run_minutes.values()) / 60.0,
        "heating_hours": run_minutes[HEATING] / 60.0,
        "cooling_hours": run_minutes[COOLING] / 60.0,
        "kwh": sum(kwh.values()),
        "heating_kwh": kwh[HEATING],
        "cooling_kwh": kwh[COOLING],
        "off_day_kwh": kwh[OFF],
    })
    return HeatPumpResult(days, summary, [months[k] for k in sorted(months)])


def summary_text(result):
    """@return The one line summary shown above the chart."""
    s = result.summary
    if not s["days_with_data"]:
        return "No heat pump data for the selected dates."
    return (f"{s['on_days']} on day(s) of {s['days_with_data']} with data "
            f"(heating {s['heating_days']} · cooling {s['cooling_days']}) · "
            f"Run {s['run_hours']:.1f} h · {s['kwh']:.1f} kWh "
            f"(heating {s['heating_kwh']:.1f} · cooling {s['cooling_kwh']:.1f})")


def month_table_rows(result):
    """@return Rows for the monthly table."""
    rows = []
    for m in result.months:
        y, mo = m["month"].split("-")
        rows.append({"id": m["month"], "month": f"{MONTH_NAMES[int(mo) - 1]} {y}",
                     "mode": m["mode"].capitalize(), "data_days": m["days_with_data"], "on_days": m["on_days"],
                     "hours": f"{m['run_minutes'] / 60.0:.1f}", "kwh": f"{m['kwh']:.1f}"})
    return rows


def chart_data(result, start, stop):
    """@brief Daily bars of run hours, one series per mode, plus the daily kWh.
       @param start, stop The selected range (datetimes). Every day in it gets a category.
       @return dict(labels, heating, cooling, off, kwh, peak) lists, one value per day (None = no value)."""
    by_day = {d["date"]: d for d in result.days}
    out = {"labels": [], HEATING: [], COOLING: [], OFF: [], "kwh": [], "peak": []}
    day = start.date()
    while day <= stop.date():
        key = day.isoformat()
        d = by_day.get(key)
        out["labels"].append(key)
        for mode in (HEATING, COOLING, OFF):
            out[mode].append(round(d["on_minutes"] / 60.0, 2) if d and d["mode"] == mode else None)
        out["kwh"].append(d["kwh"] if d else None)
        out["peak"].append(d["peak_watts"] if d else None)
        day += timedelta(days=1)
    return out


def to_csv(result):
    """@return The per-day detail as CSV text (the ct6_heatpump_days.py --csv columns plus kwh)."""
    if not result.days:
        return ""
    fields = ["date", "on_minutes", "peak_watts", "samples", "on", "mode", "kwh"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for d in result.days:
        writer.writerow({k: d[k] for k in fields})
    return buf.getvalue()
