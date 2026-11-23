#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""
Remembered display settings for ct6_dash2 (no NiceGUI dependency).

Without login they are kept per browser (in NiceGUI's app.storage.user, which the
GUI passes in as a dict). With login they are kept per user in a JSON file next to
the config file, so they follow the user to any browser.
"""

import json
import os
import tempfile
import threading

# Keys and their defaults (None = use the program default, e.g. --negative for polarity).
TAB = "tab"                     # Selected tab: a device ID, the Live tab or the Heat pump tab
PRESET = "preset"               # Last date preset clicked (applied again on startup)
RESOLUTION = "resolution"       # Resolution chosen by hand after the preset (None = the preset's)
POWER_TYPE = "power_type"
POLARITY = "polarity"
PLOT_TYPE = "plot_type"         # Last plot type selected on a device tab
BUCKET = "bucket"               # Energy view Auto/Day/Month
KWH_BAR_OPEN = "kwh_bar_open"
HP_BAR_OPEN = "hp_bar_open"
SHOW_GAPS = "show_gaps"
DARK_THEME = "dark_theme"
COMPARE = "compare"             # Period overlay

DEFAULTS = {TAB: None, PRESET: "Today", RESOLUTION: None, POWER_TYPE: None, POLARITY: None, PLOT_TYPE: None,
            BUCKET: None, KWH_BAR_OPEN: False, HP_BAR_OPEN: False, SHOW_GAPS: True, DARK_THEME: None,
            COMPARE: None}
STORAGE_PREFIX = "pref_"        # Key prefix in app.storage.user


class UserPrefsFile:
    """@brief Thread safe per-user preferences in one JSON file: {username: {key: value}}."""

    def __init__(self, filename):
        self.filename = filename
        self._lock = threading.Lock()
        self._data = None

    def _load(self):
        if self._data is None:
            try:
                with open(self.filename) as fd:
                    data = json.load(fd)
                self._data = data if isinstance(data, dict) else {}
            except (OSError, ValueError):
                self._data = {}
        return self._data

    def get_all(self, username):
        with self._lock:
            return dict(self._load().get(username, {}))

    def set(self, username, key, value):
        with self._lock:
            data = self._load()
            data.setdefault(username, {})[key] = value
            folder = os.path.dirname(os.path.abspath(self.filename))
            fd, tmp = tempfile.mkstemp(dir=folder, prefix=".prefs", suffix=".tmp")
            try:
                with os.fdopen(fd, "w") as out:
                    json.dump(data, out, indent=2, sort_keys=True)
                os.replace(tmp, self.filename)
            except Exception:
                if os.path.exists(tmp):
                    os.remove(tmp)
                raise

    def clear(self, username):
        with self._lock:
            data = self._load()
            if username in data:
                del data[username]
                with open(self.filename, "w") as out:
                    json.dump(data, out, indent=2, sort_keys=True)


class Prefs:
    """@brief One client's remembered settings: per user (file) when logged in, else per browser."""

    def __init__(self, browser_storage, user_file=None, username=None):
        """@param browser_storage A dict-like store for this browser (app.storage.user).
           @param user_file A UserPrefsFile, used with username when login is enabled.
           @param username The logged in user, or None."""
        self._browser = browser_storage
        self._file = user_file if username else None
        self._user = username
        self._cache = self._file.get_all(username) if self._file else None

    @property
    def per_user(self):
        return self._file is not None

    def get(self, key, default=None):
        if key not in DEFAULTS:
            raise KeyError(key)
        if self._file:
            value = self._cache.get(key)
        else:
            value = self._browser.get(STORAGE_PREFIX + key)
        if value is None:
            value = DEFAULTS[key]
        return default if value is None else value

    def set(self, key, value):
        if key not in DEFAULTS:
            raise KeyError(key)
        if self._file:
            if self._cache.get(key) == value:
                return
            self._cache[key] = value
            self._file.set(self._user, key, value)
        else:
            self._browser[STORAGE_PREFIX + key] = value

    def clear(self):
        """@brief Forget all remembered settings for this user / browser."""
        if self._file:
            self._cache = {}
            self._file.clear(self._user)
        else:
            for key in list(self._browser.keys()):
                if str(key).startswith(STORAGE_PREFIX):
                    del self._browser[key]
