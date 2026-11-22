#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""
Solar and battery self-consumption figures for ct6_dash2 (pure Python, no GUI or SQL).

Inputs are the half-hour energy totals (CT6DataSource.half_hour_energy(), each with
pos_kwh >= 0 and neg_kwh <= 0) of the grid CT and, optionally, a solar CT and a
battery CT. They may be on different CT6 devices.

Per half-hour:
  import I and export E come from the grid CT, solar generation S from the solar CT,
  battery charge C and discharge D from the battery CT. Because pos/neg are summed
  per minute, these are true totals, not netted.

  Home use        H = I - E + S + D - C   (everything except the battery)
  Solar used      U = S - E               (export is solar surplus; an AC-coupled
                                           battery set to zero export never exports)
  Solar to battery  = min(C, max(0, U - H))   (solar serves the home first, then
                                               charges the battery)
  Grid to battery   = C - solar to battery
  Home from solar   = U - solar to battery
  Home from battery = D
  Home from grid    = I - grid to battery

The solar/grid split of the battery charge is an estimate (it is worked out per
half-hour, not per minute). Everything else is exact for the CT readings.
"""

from dataclasses import dataclass


@dataclass
class SelfUseResult:
    has_solar: bool = False
    has_battery: bool = False
    import_kwh: float = 0.0
    export_kwh: float = 0.0
    solar_kwh: float = 0.0              # Generated
    solar_reverse_kwh: float = 0.0      # Energy in the other direction (inverter standby, or the sign is wrong)
    solar_home_kwh: float = 0.0         # Used directly by the home
    solar_battery_kwh: float = 0.0      # Charged into the battery
    charge_kwh: float = 0.0
    discharge_kwh: float = 0.0
    grid_battery_kwh: float = 0.0       # Battery charge from the grid
    home_kwh: float = 0.0
    home_grid_kwh: float = 0.0
    slots: int = 0
    days: int = 0                       # Days with data
    solar_sign_detected: bool = False   # The solar CT sign was detected from the data

    @property
    def solar_used_kwh(self):
        return self.solar_home_kwh + self.solar_battery_kwh

    @property
    def self_consumption(self):
        """@return The share of solar generation used on site (0..1), or None."""
        return self.solar_used_kwh / self.solar_kwh if self.solar_kwh > 0.005 else None

    @property
    def battery_solar_share(self):
        """@return The share of the battery's charge that came from solar (0..1)."""
        return self.solar_battery_kwh / self.charge_kwh if self.charge_kwh > 0.005 else 0.0

    @property
    def self_sufficiency(self):
        """@return The share of home use supplied by solar (0..1), or None. With a solar CT, battery
                   discharge counts only in proportion to the solar share of its charge, so a
                   battery charged from the grid overnight doesn't count as self-supplied.
                   Without a solar CT, the share supplied by the battery."""
        if self.home_kwh <= 0.005:
            return None
        if self.has_solar:
            own = self.solar_home_kwh + self.discharge_kwh * self.battery_solar_share
        else:
            own = self.discharge_kwh
        return max(0.0, min(1.0, own / self.home_kwh))

    @property
    def battery_efficiency(self):
        """@return Battery discharge / charge over the period, or None."""
        return self.discharge_kwh / self.charge_kwh if self.charge_kwh > 0.005 else None

    @property
    def solar_sign_suspect(self):
        """@return True if the solar CT reads more in the 'consumption' direction than generation."""
        return self.has_solar and not self.solar_sign_detected and self.solar_reverse_kwh > max(0.5, self.solar_kwh)

    @property
    def battery_sign_suspect(self):
        """@return True if, over a week or more, more came out of the battery than went in
                   (impossible, so the battery CT sign is probably the wrong way round)."""
        return self.has_battery and self.days >= BATTERY_CHECK_DAYS and \
            self.discharge_kwh > max(1.0, self.charge_kwh * 1.05)


BATTERY_CHECK_DAYS = 7      # Range needed before battery out > in is flagged
MIN_DETECT_KWH = 1.0        # Solar energy needed to detect the solar CT sign


def detect_gen_negative(solar_slots):
    """@brief Detect which way the solar CT reads generation. Generation is far larger than the
              inverter's overnight standby, so it is the direction with more energy.
       @return True if generation reads negative, False if positive, or None if there isn't
               enough energy to tell (e.g. a range at night)."""
    pos = sum(float(s["pos_kwh"] or 0.0) for s in solar_slots or [])
    neg = -sum(float(s["neg_kwh"] or 0.0) for s in solar_slots or [])
    if max(pos, neg) < MIN_DETECT_KWH:
        return None
    return neg > pos


def _by_slot(slots):
    return {s["slot"]: s for s in slots or []}


def calc_self_use(grid_slots, solar_slots=None, battery_slots=None, grid_import_negative=True,
                  solar_gen_negative=True, battery_charge_negative=False):
    """@brief Work out the self-consumption figures.
       @param grid_slots, solar_slots, battery_slots Half-hour energy dicts (slot, pos_kwh, neg_kwh).
              solar_slots / battery_slots may be None if that CT isn't set.
       @param grid_import_negative True if the grid CT reads import as negative (CT6 default).
       @param solar_gen_negative True if the solar CT reads generation as negative.
       @param battery_charge_negative True if the battery CT reads charging as negative.
       @return A SelfUseResult."""
    r = SelfUseResult(has_solar=solar_slots is not None, has_battery=battery_slots is not None)
    grid, solar, battery = _by_slot(grid_slots), _by_slot(solar_slots), _by_slot(battery_slots)

    def split(s, first_is_negative):
        """@return (energy in the 'first' direction, energy in the other direction), both >= 0."""
        if s is None:
            return 0.0, 0.0
        pos, neg = float(s["pos_kwh"] or 0.0), -float(s["neg_kwh"] or 0.0)
        return (neg, pos) if first_is_negative else (pos, neg)

    for slot in sorted(set(grid) | set(solar) | set(battery)):
        imp, exp = split(grid.get(slot), grid_import_negative)
        gen, rev = split(solar.get(slot), solar_gen_negative)
        chg, dis = split(battery.get(slot), battery_charge_negative)
        home = max(0.0, imp - exp + gen + dis - chg)
        used = max(0.0, gen - exp)
        to_batt = min(chg, max(0.0, used - home))
        r.import_kwh += imp
        r.export_kwh += exp
        r.solar_kwh += gen
        r.solar_reverse_kwh += rev
        r.solar_battery_kwh += to_batt
        r.solar_home_kwh += used - to_batt
        r.charge_kwh += chg
        r.discharge_kwh += dis
        r.grid_battery_kwh += chg - to_batt
        r.home_kwh += home
        r.home_grid_kwh += max(0.0, imp - (chg - to_batt))
        r.slots += 1
    r.days = len({slot.date() for slot in grid})
    return r


def _pc(value):
    return "–" if value is None else f"{value * 100:.0f}%"


def summary_text(r):
    """@return The one line summary shown in the kWh bar header."""
    parts = []
    if r.has_solar:
        parts.append(f"Solar {r.solar_kwh:.2f} kWh, {_pc(r.self_consumption)} used on site")
    if r.has_battery:
        parts.append(f"Battery in {r.charge_kwh:.2f} · out {r.discharge_kwh:.2f} kWh")
    parts.append(f"Home {r.home_kwh:.2f} kWh, {_pc(r.self_sufficiency)} from "
                 f"{'solar' if r.has_solar else 'battery'}")
    text = " · ".join(parts)
    if r.battery_sign_suspect:
        text = "⚠ Check the battery CT sign (more out than in) · " + text
    if r.solar_sign_suspect:
        text = "⚠ Check the solar CT sign · " + text
    return text


def table_rows(r):
    """@return Rows (id, item, kwh, pc) for the self-consumption table."""
    rows = []

    def add(item, kwh=None, pc=None):
        rows.append({"id": len(rows), "item": item, "kwh": "" if kwh is None else f"{kwh:.2f}",
                     "pc": "" if pc is None else pc})

    def share(part, whole):
        return _pc(part / whole) if whole > 0.005 else "–"

    if r.has_solar:
        add("Solar generated (% used)", r.solar_kwh, _pc(r.self_consumption))
        add("  used in the home", r.solar_home_kwh, share(r.solar_home_kwh, r.solar_kwh))
        if r.has_battery:
            add("  charged into the battery", r.solar_battery_kwh, share(r.solar_battery_kwh, r.solar_kwh))
        add("  exported", min(r.export_kwh, r.solar_kwh), share(min(r.export_kwh, r.solar_kwh), r.solar_kwh))
    if r.has_battery:
        add("Battery charged", r.charge_kwh)
        if r.has_solar:
            add("  from solar (estimate)", r.solar_battery_kwh, share(r.solar_battery_kwh, r.charge_kwh))
        add("  from the grid" + (" (estimate)" if r.has_solar else ""), r.grid_battery_kwh,
            share(r.grid_battery_kwh, r.charge_kwh))
        add("Battery discharged (% of in)", r.discharge_kwh, _pc(r.battery_efficiency))
    add("Home use (% from solar)" if r.has_solar else "Home use (% from battery)", r.home_kwh,
        _pc(r.self_sufficiency))
    if r.has_solar:
        add("  from solar", r.solar_home_kwh, share(r.solar_home_kwh, r.home_kwh))
    if r.has_battery:
        add("  from the battery", r.discharge_kwh, share(r.discharge_kwh, r.home_kwh))
    add("  from the grid", r.home_grid_kwh, share(r.home_grid_kwh, r.home_kwh))
    return rows


CAVEAT = ("Whole site, from the grid, solar and battery CTs set in 'Tariff & CT roles'. "
          "Home use is everything except the battery (it includes the EV, Eddi etc.). "
          "Self-consumption = solar used on site ÷ solar generated. "
          "Home use from solar = solar used directly plus battery discharge in proportion to the "
          "share of the battery's charge that came from solar (grid-charged battery energy counts as grid). "
          "The solar/grid split of the battery charge is estimated per half-hour. "
          "The solar CT sign is detected from the data unless set in 'Tariff & CT roles'.")
