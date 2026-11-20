"""Unit tests for ct6/ct6_dash2_auth.py (ct6_dash2 login support).

   Run from the software/server folder:  python3 -m pytest tests/test_ct6_dash2_auth.py"""
import json
import os
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from p3lib.bokeh_auth import CredentialsHasher  # noqa: E402
from ct6 import ct6_dash2_auth as auth  # noqa: E402


class Clock:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


class TestLoginManager(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cred = os.path.join(self.tmp.name, "creds.json")
        CredentialsHasher(self.cred).add("alice", "s3cret")       # as ct6_dash_mgr does
        self.clock = Clock()
        self.mgr = auth.LoginManager(self.cred, clock=self.clock)

    def tearDown(self):
        self.tmp.cleanup()

    def test_verify_uses_ct6_dash_mgr_file(self):
        self.assertTrue(self.mgr.verify("alice", "s3cret"))
        self.assertFalse(self.mgr.verify("alice", "wrong"))
        self.assertFalse(self.mgr.verify("bob", "s3cret"))
        self.assertFalse(self.mgr.verify("", ""))

    def test_users_added_and_removed_without_restart(self):
        self.assertEqual(self.mgr.usernames(), {"alice"})
        CredentialsHasher(self.cred).add("bob", "pw")
        os.utime(self.cred, (self.clock.t, os.path.getmtime(self.cred) + 1))   # ensure mtime changes
        self.assertEqual(self.mgr.usernames(), {"alice", "bob"})
        self.assertTrue(self.mgr.verify("bob", "pw"))
        CredentialsHasher(self.cred).remove("alice")
        os.utime(self.cred, (self.clock.t, os.path.getmtime(self.cred) + 2))
        self.assertEqual(self.mgr.usernames(), {"bob"})

    def test_missing_or_bad_file_means_no_users(self):
        self.assertEqual(auth.LoginManager(os.path.join(self.tmp.name, "none.json")).user_count(), 0)
        with open(self.cred, "w") as fd:
            fd.write("{not json")
        os.utime(self.cred, (self.clock.t, os.path.getmtime(self.cred) + 1))
        self.assertEqual(self.mgr.user_count(), 0)

    def test_session_validity(self):
        s = self.mgr.new_session("alice")
        self.assertEqual(self.mgr.session_user(s), "alice")
        self.assertIsNone(self.mgr.session_user({}))
        self.assertIsNone(self.mgr.session_user({**s, auth.AUTHENTICATED: False}))
        self.clock.t += auth.SESSION_DAYS * 86400 + 1
        self.assertIsNone(self.mgr.session_user(s))          # expired

    def test_session_ends_when_user_removed(self):
        s = self.mgr.new_session("alice")
        with open(self.cred, "w") as fd:
            json.dump({}, fd)
        os.utime(self.cred, (self.clock.t, os.path.getmtime(self.cred) + 1))
        self.assertIsNone(self.mgr.session_user(s))

    def test_lockout_after_repeated_failures(self):
        ip = "10.0.0.5"
        for _ in range(auth.MAX_FAILURES - 1):
            self.assertFalse(self.mgr.record_failure(ip))
        self.assertEqual(self.mgr.lockout_remaining(ip), 0)
        self.assertTrue(self.mgr.record_failure(ip))
        self.assertGreater(self.mgr.lockout_remaining(ip), 0)
        self.assertEqual(self.mgr.lockout_remaining("10.0.0.6"), 0)   # other addresses unaffected
        self.clock.t += auth.LOCKOUT_SECS + 1
        self.assertEqual(self.mgr.lockout_remaining(ip), 0)

    def test_old_failures_expire_and_success_clears(self):
        ip = "10.0.0.7"
        for _ in range(auth.MAX_FAILURES - 1):
            self.mgr.record_failure(ip)
        self.clock.t += auth.FAILURE_WINDOW_SECS + 1
        self.assertFalse(self.mgr.record_failure(ip))     # earlier failures no longer count
        for _ in range(auth.MAX_FAILURES - 2):
            self.mgr.record_failure(ip)
        self.mgr.clear_failures(ip)
        self.assertFalse(self.mgr.record_failure(ip))


class TestHelpers(unittest.TestCase):

    def test_secret_created_private_and_reused(self):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "sub", "ct6Dash2.secret")
            s1 = auth.load_or_create_secret(f)
            self.assertEqual(len(s1), 64)
            self.assertEqual(stat.S_IMODE(os.stat(f).st_mode), 0o600)
            self.assertEqual(auth.load_or_create_secret(f), s1)

    def test_safe_redirect(self):
        self.assertEqual(auth.safe_redirect("/"), "/")
        self.assertEqual(auth.safe_redirect("/page?x=1"), "/page?x=1")
        for bad in (None, "", "https://evil.example", "//evil.example", "evil", "/\\evil", "/login", "/x?u=http://a"):
            self.assertEqual(auth.safe_redirect(bad), "/", bad)


if __name__ == "__main__":
    unittest.main()
