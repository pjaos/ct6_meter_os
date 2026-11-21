#!/usr/bin/env python3
"""@brief Electricity tariff, CT role settings and cost calculation for ct6_dash2.

   Nothing here touches a database or a GUI.

   Costing model
   - Costs come from the grid CT. Each minute of data is split into import and
     export energy and totalled per half-hour (as suppliers bill).
   - A half-hour is off-peak if it starts inside the off-peak window
     (default 23:30-05:30, local clock time). All other import is peak.
   - Rates (pence) have a 'valid from' date so a past period is costed at the
     rates that applied then.
   - The daily standing charge is added for each calendar day in the range,
     up to and including today.
   - Optional Intelligent Octopus Go (IOG) rule (Tariff.ev_slots_offpeak): a half-hour
     outside the off-peak window counts as off-peak for the whole house when the EV CT
     used at least ev_slot_min_kwh in it (with at least ev_slot_min_grid_share of that
     energy coming from the grid). IOG only gives these slots while the car charges
     under Octopus control, and bills in half-hours, so this matches the bill. Up to
     ev_daily_cap_hours of EV charging per day (midday to midday, in or out of the
     window) is off-peak; EV charging beyond that is costed at peak, as IOG does."""

import json
import os
import tempfile
import threading
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta

DEFAULT_OFFPEAK_START = "23:30"
DEFAULT_OFFPEAK_END = "05:30"
SETTINGS_VERSION = 3

DEFAULT_EV_SLOT_MIN_KWH = 0.1        # EV energy in a half-hour that marks an IOG slot
DEFAULT_EV_SLOT_MIN_GRID_SHARE = 0.5 # Share of that EV energy that must come from the grid
DEFAULT_EV_DAILY_CAP_HOURS = 6.0     # IOG off-peak EV charging allowance per day (0 = no cap)


def _parse_hhmm(value):
    return datetime.strptime(str(value).strip(), "%H:%M").time()


@dataclass
class RatePeriod:
    """@brief Rates that apply from valid_from until the next period starts. All in pence."""
    valid_from: date
    peak: float             # p/kWh imported outside the off-peak window
    offpeak: float          # p/kWh imported inside the off-peak window
    export: float           # p/kWh exported
    standing: float = 0.0   # p/day

    def to_dict(self):
        d = asdict(self)
        d["valid_from"] = self.valid_from.isoformat()
        return d

    @staticmethod
    def from_dict(d):
        return RatePeriod(valid_from=date.fromisoformat(str(d["valid_from"])),
                          peak=float(d["peak"]),
                          offpeak=float(d["offpeak"]),
                          export=float(d.get("export", 0.0)),
                          standing=float(d.get("standing", 0.0)))


@dataclass
class Tariff:
    offpeak_start: str = DEFAULT_OFFPEAK_START
    offpeak_end: str = DEFAULT_OFFPEAK_END
    rates: list = field(default_factory=list)   # RatePeriod, any order
    ev_slots_offpeak: bool = False              # Intelligent Octopus Go EV slot rule (see module doc)
    ev_slot_min_kwh: float = DEFAULT_EV_SLOT_MIN_KWH
    ev_slot_min_grid_share: float = DEFAULT_EV_SLOT_MIN_GRID_SHARE
    ev_daily_cap_hours: float = DEFAULT_EV_DAILY_CAP_HOURS

    def validate(self):
        """@raise ValueError if the tariff is not valid."""
        try:
            start = _parse_hhmm(self.offpeak_start)
            end = _parse_hhmm(self.offpeak_end)
        except ValueError:
            raise ValueError("The off-peak start/end times must be HH:MM.")
        if start == end:
            raise ValueError("The off-peak start and end times must be different.")
        for t in (start, end):
            if t.minute not in (0, 30) or t.second:
                raise ValueError("The off-peak start/end times must be on the hour or half hour.")
        days = [r.valid_from for r in self.rates]
        if len(days) != len(set(days)):
            raise ValueError("Two rate periods have the same 'valid from' date.")
        for r in self.rates:
            for name in ("peak", "offpeak", "export", "standing"):
                if getattr(r, name) < 0:
                    raise ValueError(f"The {name} rate must not be negative.")
        if not self.ev_slot_min_kwh > 0:
            raise ValueError("The minimum EV kWh per half-hour must be more than 0.")
        if not 0 <= self.ev_slot_min_grid_share <= 1:
            raise ValueError("The minimum grid share must be between 0 and 100%.")
        if self.ev_daily_cap_hours < 0 or (self.ev_daily_cap_hours * 2) % 1:
            raise ValueError("The daily EV cap must be 0 (no cap) or a whole number of half hours.")

    def is_offpeak(self, slot_start):
        """@param slot_start The start of a half-hour (datetime or time).
           @return True if the half-hour is in the off-peak window."""
        t = slot_start.time() if isinstance(slot_start, datetime) else slot_start
        start = _parse_hhmm(self.offpeak_start)
        end = _parse_hhmm(self.offpeak_end)
        if start < end:
            return start <= t < end
        return t >= start or t < end      # Window crosses midnight

    def rate_for(self, day):
        """@return The RatePeriod in force on day, or None if no period has started."""
        best = None
        for r in self.rates:
            if r.valid_from <= day and (best is None or r.valid_from > best.valid_from):
                best = r
        return best


@dataclass(frozen=True)
class CTRef:
    """@brief One CT port on one CT6 device."""
    device_id: str
    ct: int             # 1-6

    def to_dict(self):
        return {"device_id": self.device_id, "ct": self.ct}

    @staticmethod
    def from_dict(d):
        if not d or not d.get("device_id") or not d.get("ct"):
            return None
        return CTRef(str(d["device_id"]), int(d["ct"]))

    def key(self):
        """@return A string key (DEVICE:ct) for use in GUI selects."""
        return f"{self.device_id}:{self.ct}"

    @staticmethod
    def from_key(key):
        if not key or ":" not in str(key):
            return None
        device_id, ct = str(key).rsplit(":", 1)
        return CTRef(device_id, int(ct))


@dataclass
class SiteRoles:
    """@brief Which CTs measure the grid connection and the EV charger.
              They may be on different CT6 devices. None = not set."""
    grid: CTRef = None
    ev: CTRef = None
    grid_import_negative: bool = True   # CT6 default: import power is a negative value

    def to_dict(self):
        return {"grid": self.grid.to_dict() if self.grid else None,
                "ev": self.ev.to_dict() if self.ev else None,
                "grid_import_negative": self.grid_import_negative}

    @staticmethod
    def from_dict(d):
        d = d or {}
        return SiteRoles(grid=CTRef.from_dict(d.get("grid")),
                         ev=CTRef.from_dict(d.get("ev")),
                         grid_import_negative=bool(d.get("grid_import_negative", True)))

    @staticmethod
    def from_v1_devices(devices):
        """@brief Convert version 1 settings (roles per device) to SiteRoles.
                  The first device with a grid CT and the first with an EV CT are used."""
        roles = SiteRoles()
        for device_id, d in sorted((devices or {}).items()):
            if roles.grid is None and d.get("grid_ct"):
                roles.grid = CTRef(device_id, int(d["grid_ct"]))
                roles.grid_import_negative = bool(d.get("grid_import_negative", True))
            if roles.ev is None and d.get("ev_ct"):
                roles.ev = CTRef(device_id, int(d["ev_ct"]))
        return roles


@dataclass
class Settings:
    tariff: Tariff = field(default_factory=Tariff)
    roles: SiteRoles = field(default_factory=SiteRoles)

    def to_dict(self):
        return {"version": SETTINGS_VERSION,
                "tariff": {"offpeak_start": self.tariff.offpeak_start,
                           "offpeak_end": self.tariff.offpeak_end,
                           "rates": [r.to_dict() for r in sorted(self.tariff.rates, key=lambda r: r.valid_from)],
                           "ev_slots_offpeak": self.tariff.ev_slots_offpeak,
                           "ev_slot_min_kwh": self.tariff.ev_slot_min_kwh,
                           "ev_slot_min_grid_share": self.tariff.ev_slot_min_grid_share,
                           "ev_daily_cap_hours": self.tariff.ev_daily_cap_hours},
                "roles": self.roles.to_dict()}

    @staticmethod
    def from_dict(d):
        t = d.get("tariff", {})
        tariff = Tariff(offpeak_start=t.get("offpeak_start", DEFAULT_OFFPEAK_START),
                        offpeak_end=t.get("offpeak_end", DEFAULT_OFFPEAK_END),
                        rates=[RatePeriod.from_dict(r) for r in t.get("rates", [])],
                        ev_slots_offpeak=bool(t.get("ev_slots_offpeak", False)),
                        ev_slot_min_kwh=float(t.get("ev_slot_min_kwh", DEFAULT_EV_SLOT_MIN_KWH)),
                        ev_slot_min_grid_share=float(t.get("ev_slot_min_grid_share", DEFAULT_EV_SLOT_MIN_GRID_SHARE)),
                        ev_daily_cap_hours=float(t.get("ev_daily_cap_hours", DEFAULT_EV_DAILY_CAP_HOURS)))
        if "roles" in d:
            roles = SiteRoles.from_dict(d["roles"])
        else:
            roles = SiteRoles.from_v1_devices(d.get("devices"))
        return Settings(tariff, roles)


class SettingsStore:
    """@brief Thread safe load/save of the Settings JSON file (shared by all browser clients)."""

    def __init__(self, filename):
        self.filename = filename
        self._lock = threading.Lock()

    def load(self):
        """@return The Settings (defaults if the file does not exist)."""
        with self._lock:
            if not os.path.isfile(self.filename):
                return Settings()
            with open(self.filename) as fd:
                return Settings.from_dict(json.load(fd))

    def save(self, settings):
        """@brief Validate and atomically write the settings."""
        settings.tariff.validate()
        data = json.dumps(settings.to_dict(), indent=2)
        with self._lock:
            folder = os.path.dirname(os.path.abspath(self.filename))
            os.makedirs(folder, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=folder, prefix=".ct6dash2_", suffix=".json")
            try:
                with os.fdopen(fd, "w") as f:
                    f.write(data)
                os.replace(tmp, self.filename)
            except Exception:
                if os.path.exists(tmp):
                    os.remove(tmp)
                raise


# ---------------------------------------------------------------- cost calculation

@dataclass
class CostResult:
    import_peak_kwh: float = 0.0
    import_offpeak_kwh: float = 0.0
    export_kwh: float = 0.0
    import_peak_p: float = 0.0
    import_offpeak_p: float = 0.0
    export_p: float = 0.0           # Earnings (positive number)
    standing_p: float = 0.0
    standing_days: int = 0
    unpriced_slots: int = 0         # Half-hours with energy but no rate period in force
    priced_days: int = 0            # Days (with data) that had a rate period in force
    unpriced_days: int = 0          # Days (with data) before the first rate period
    ev: object = None               # EVResult or None
    ev_rule: bool = False           # True if the IOG EV slot rule was applied
    ev_slot_halfhours: int = 0      # Half-hours outside the window costed off-peak (EV slots)
    ev_over_cap_halfhours: int = 0  # EV charging half-hours beyond the daily cap (EV costed at peak)

    @property
    def import_p(self):
        return self.import_peak_p + self.import_offpeak_p

    @property
    def net_p(self):
        """@return Import cost + standing charge - export earnings (pence)."""
        return self.import_p + self.standing_p - self.export_p


@dataclass
class EVResult:
    peak_kwh: float = 0.0
    offpeak_kwh: float = 0.0
    peak_p: float = 0.0
    offpeak_p: float = 0.0

    @property
    def kwh(self):
        return self.peak_kwh + self.offpeak_kwh

    @property
    def cost_p(self):
        return self.peak_p + self.offpeak_p


def _grid_import_export(s, import_negative):
    pos = float(s.get("pos_kwh") or 0.0)
    neg = -float(s.get("neg_kwh") or 0.0)
    return (neg, pos) if import_negative else (pos, neg)


def _ev_kwh(s):
    """@return The EV energy in a half-hour: the size of its net energy (CT orientation doesn't matter)."""
    return abs(float(s.get("pos_kwh") or 0.0) + float(s.get("neg_kwh") or 0.0))


def classify_ev_slots(ev_slots, grid_import, tariff):
    """@brief Apply the Intelligent Octopus Go rule to the EV CT's half-hours.
       @param ev_slots half_hour_energy() dicts for the EV CT.
       @param grid_import dict: half-hour start -> grid import kWh.
       @param tariff The Tariff (uses its ev_* settings and off-peak window).
       @return (offpeak, over_cap):
               offpeak  - half-hours outside the window that count as off-peak for the whole house;
               over_cap - EV charging half-hours beyond the daily cap (their EV energy is costed at peak)."""
    offpeak, over_cap = set(), set()
    cap = int(round(tariff.ev_daily_cap_hours * 2))      # In half-hours; 0 = no cap
    used = {}                                            # Charging day (midday to midday) -> half-hours
    for s in sorted(ev_slots, key=lambda x: x["slot"]):
        slot = s["slot"]
        ev = _ev_kwh(s)
        if ev < tariff.ev_slot_min_kwh:
            continue
        in_window = tariff.is_offpeak(slot)
        if not in_window and grid_import.get(slot, 0.0) < tariff.ev_slot_min_grid_share * ev:
            continue        # Mostly not from the grid (e.g. solar charging): not an Octopus slot
        day = (slot - timedelta(hours=12)).date()
        used[day] = used.get(day, 0) + 1
        if cap and used[day] > cap:
            over_cap.add(slot)
        elif not in_window:
            offpeak.add(slot)
    return offpeak, over_cap


def calc_cost(grid_slots, tariff, start_dt, stop_dt, now=None, import_negative=True, ev_slots=None):
    """@brief Calculate the electricity cost for a period.
       @param grid_slots Iterable of dicts from CT6DataSource.half_hour_energy() for the grid CT:
              slot (datetime, half-hour start), pos_kwh (>= 0) and neg_kwh (<= 0).
       @param tariff A Tariff.
       @param start_dt The start of the period (for the standing charge).
       @param stop_dt The end of the period (for the standing charge).
       @param now The current datetime (standing charge is not added for future days).
       @param import_negative True if import power is negative on the grid CT (CT6 default).
       @param ev_slots Optional half_hour_energy() dicts for the EV CT. The EV energy in each
              half-hour is the magnitude of its net energy, costed at the import rate for that
              half-hour. Needed for the IOG EV slot rule (tariff.ev_slots_offpeak).
       @return A CostResult. All kWh and £ figures cover only the days that have a rate
               period in force. Days before the first rate period are counted in
               unpriced_days / unpriced_slots and left out of every total."""
    res = CostResult()
    grid_slots = list(grid_slots)
    ev_slots = list(ev_slots) if ev_slots is not None else None
    grid = {s["slot"]: _grid_import_export(s, import_negative) for s in grid_slots}
    ev_by_slot = {s["slot"]: _ev_kwh(s) for s in ev_slots} if ev_slots is not None else {}

    ev_offpeak, over_cap = set(), set()
    if tariff.ev_slots_offpeak and ev_slots is not None:
        res.ev_rule = True
        ev_offpeak, over_cap = classify_ev_slots(ev_slots, {k: v[0] for k, v in grid.items()}, tariff)

    priced_dates, unpriced_dates = set(), set()
    for slot, (imp, exp) in grid.items():
        rate = tariff.rate_for(slot.date())
        (priced_dates if rate is not None else unpriced_dates).add(slot.date())
        if rate is None:
            # Not costed. Leave its kWh out too so the kWh and £ figures always cover the same days.
            if imp > 0 or exp > 0:
                res.unpriced_slots += 1
            continue
        in_window = tariff.is_offpeak(slot)
        if slot in ev_offpeak:
            res.ev_slot_halfhours += 1
        if slot in over_cap:
            res.ev_over_cap_halfhours += 1
        if in_window or slot in ev_offpeak:
            # EV charging beyond the daily cap is billed at peak even in the off-peak window.
            peak_part = min(ev_by_slot.get(slot, 0.0), imp) if slot in over_cap else 0.0
            off_part = imp - peak_part
        else:
            peak_part, off_part = imp, 0.0
        res.import_offpeak_kwh += off_part
        res.import_offpeak_p += off_part * rate.offpeak
        res.import_peak_kwh += peak_part
        res.import_peak_p += peak_part * rate.peak
        res.export_kwh += exp
        res.export_p += exp * rate.export

    res.priced_days = len(priced_dates)
    res.unpriced_days = len(unpriced_dates)

    now = now or datetime.now()
    last_day = min(stop_dt.date(), now.date())
    day = start_dt.date()
    while day <= last_day:
        rate = tariff.rate_for(day)
        if rate is not None:
            res.standing_p += rate.standing
            res.standing_days += 1
        day += timedelta(days=1)

    if ev_slots is not None:
        ev = EVResult()
        for slot, kwh in ev_by_slot.items():
            rate = tariff.rate_for(slot.date())
            if rate is None:
                continue        # Not costed (before the first rate period)
            offpeak = slot in ev_offpeak or (tariff.is_offpeak(slot) and slot not in over_cap)
            if offpeak:
                ev.offpeak_kwh += kwh
                ev.offpeak_p += kwh * rate.offpeak
            else:
                ev.peak_kwh += kwh
                ev.peak_p += kwh * rate.peak
        res.ev = ev
    return res


def cost_caveat(tariff):
    """@return The text explaining how off-peak was decided (shown as a tooltip)."""
    window = f"{tariff.offpeak_start}-{tariff.offpeak_end}"
    if tariff.ev_slots_offpeak:
        cap = (f"up to {tariff.ev_daily_cap_hours:g} h of EV charging per day (midday to midday); "
               "EV charging beyond that is costed at peak" if tariff.ev_daily_cap_hours else "no daily EV cap")
        return (f"Intelligent Octopus Go: import in {window} is off-peak, and so is any half-hour outside it "
                f"where the EV used at least {tariff.ev_slot_min_kwh:g} kWh with at least "
                f"{tariff.ev_slot_min_grid_share * 100:.0f}% of it from the grid (a smart charging slot), "
                f"{cap}. Boost charging is billed at peak but is treated as a slot here.")
    return (f"Only {window} is off-peak. Smart charging slots outside it are costed at the peak rate, "
            "so the actual cost may be lower.")


def first_rate_date(tariff):
    """@return The earliest 'valid from' date, or None if there are no rate periods."""
    return min((r.valid_from for r in tariff.rates), default=None)


def uncosted_warning(res, tariff):
    """@return A warning if some days in the period were not costed (no rate period yet), else None."""
    if not res.unpriced_days:
        return None
    total = res.priced_days + res.unpriced_days
    first = first_rate_date(tariff)
    why = f"no rate before {first.day} {first:%b %Y}" if first else "no rates entered"
    if res.priced_days == 0:
        return f"⚠ No days costed ({why})"
    return f"⚠ Only {res.priced_days} of {total} days costed ({why})"


def pounds(pence):
    """@return pence formatted as £x.xx (negative values as -£x.xx)."""
    sign = "-" if pence < 0 else ""
    return f"{sign}£{abs(pence) / 100.0:.2f}"


def cost_summary_text(res, ev_name=None):
    """@return The one line cost summary shown in the collapsed kWh bar header."""
    parts = [f"Import {pounds(res.import_p)} (peak {pounds(res.import_peak_p)} · off-peak {pounds(res.import_offpeak_p)})",
             f"Export {pounds(-res.export_p)}"]
    if res.standing_days:
        parts.append(f"Standing {pounds(res.standing_p)}")
    parts.append(f"Net {pounds(res.net_p)}")
    if res.ev is not None:
        parts.append(f"{ev_name or 'EV'} {pounds(res.ev.cost_p)}")
    return " · ".join(parts)


def cost_table_rows(res, ev_name=None):
    """@return Rows (dicts with item, kwh, cost) for the cost breakdown table."""
    rows = [{"item": "Import (peak)", "kwh": f"{res.import_peak_kwh:.2f}", "cost": pounds(res.import_peak_p)},
            {"item": "Import (off-peak)", "kwh": f"{res.import_offpeak_kwh:.2f}", "cost": pounds(res.import_offpeak_p)},
            {"item": "Export", "kwh": f"{res.export_kwh:.2f}", "cost": pounds(-res.export_p)},
            {"item": f"Standing charge ({res.standing_days} day{'s' if res.standing_days != 1 else ''})",
             "kwh": "", "cost": pounds(res.standing_p)},
            {"item": "Net", "kwh": "", "cost": pounds(res.net_p)}]
    if res.ev is not None:
        name = ev_name or "EV"
        rows.append({"item": f"{name} (peak / off-peak kWh)",
                     "kwh": f"{res.ev.peak_kwh:.2f} / {res.ev.offpeak_kwh:.2f}",
                     "cost": pounds(res.ev.cost_p)})
    if res.ev_rule:
        rows.append({"item": "EV slots costed off-peak (half-hours)", "kwh": str(res.ev_slot_halfhours), "cost": ""})
        if res.ev_over_cap_halfhours:
            rows.append({"item": "EV charging over daily cap (half-hours)",
                         "kwh": str(res.ev_over_cap_halfhours), "cost": ""})
    for i, r in enumerate(rows):
        r["id"] = i
    return rows
