"""Regression test: ct6_dash2 must find its version when started from an installed entry
   point script (e.g. ~/.local/bin/ct6_dash2 under pip/pipx), not only from the source tree.

   Run from the software/server folder:  python3 -m pytest tests/test_ct6_dash2_version.py"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ct6 import ct6_dash2  # noqa: E402


def pyproject_version():
    path = os.path.join(os.path.dirname(ct6_dash2.__file__), "assets", "pyproject.toml")
    with open(path) as fd:
        for line in fd:
            if line.startswith("version"):
                return line.split("=")[1].strip().strip('"')


class TestProgramVersion(unittest.TestCase):

    def test_version_from_installed_entry_point(self):
        with mock.patch.object(sys, "argv", ["/root/.local/bin/ct6_dash2"]):
            self.assertEqual(ct6_dash2.program_version(), pyproject_version())

    def test_never_raises(self):
        with mock.patch.object(ct6_dash2, "get_program_version", side_effect=Exception("boom")), \
             mock.patch.object(ct6_dash2.metadata, "version", side_effect=Exception("boom")):
            self.assertEqual(ct6_dash2.program_version(), "unknown")


if __name__ == "__main__":
    unittest.main()
