"""Unit tests for ct6_dash2_prefs (remembered display settings)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ct6 import ct6_dash2_prefs as up  # noqa: E402


class TestPrefs(unittest.TestCase):

    def test_browser_storage(self):
        store = {"other": 1}
        p = up.Prefs(store)
        self.assertFalse(p.per_user)
        self.assertEqual(p.get(up.PRESET), "Today")              # Default
        self.assertTrue(p.get(up.SHOW_GAPS))
        self.assertEqual(p.get(up.POLARITY, "Import is negative"), "Import is negative")   # Caller default
        p.set(up.PRESET, "This week")
        p.set(up.DARK_THEME, False)
        self.assertEqual(store[up.STORAGE_PREFIX + up.PRESET], "This week")
        self.assertEqual(up.Prefs(store).get(up.PRESET), "This week")
        self.assertFalse(up.Prefs(store).get(up.DARK_THEME, True))
        p.clear()
        self.assertEqual(store, {"other": 1})                     # Only our keys removed
        with self.assertRaises(KeyError):
            p.get("nonsense")

    def test_per_user_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "prefs.json")
            f = up.UserPrefsFile(path)
            browser = {}
            alice = up.Prefs(browser, f, "alice")
            self.assertTrue(alice.per_user)
            alice.set(up.TAB, "HOUSE")
            alice.set(up.KWH_BAR_OPEN, True)
            up.Prefs({}, f, "bob").set(up.TAB, "GARAGE")
            self.assertEqual(browser, {})                         # Nothing in the browser store
            # A new file object (e.g. after a restart) and another browser see alice's settings.
            again = up.Prefs({}, up.UserPrefsFile(path), "alice")
            self.assertEqual(again.get(up.TAB), "HOUSE")
            self.assertTrue(again.get(up.KWH_BAR_OPEN))
            self.assertEqual(json.load(open(path))["bob"], {"tab": "GARAGE"})
            again.clear()
            self.assertEqual(up.Prefs({}, up.UserPrefsFile(path), "alice").get(up.TAB), None)
            self.assertEqual(up.Prefs({}, up.UserPrefsFile(path), "bob").get(up.TAB), "GARAGE")

    def test_no_username_uses_browser(self):
        with tempfile.TemporaryDirectory() as folder:
            store = {}
            p = up.Prefs(store, up.UserPrefsFile(os.path.join(folder, "p.json")), None)
            self.assertFalse(p.per_user)
            p.set(up.TAB, "X")
            self.assertEqual(store, {up.STORAGE_PREFIX + up.TAB: "X"})


if __name__ == "__main__":
    unittest.main()
