#!/usr/bin/env python3
"""@brief Login support for ct6_dash2.

   Users are the same as for ct6_dash: they are stored (argon2 hashed) in the
   credentials file managed by ct6_dash_mgr. The file is re-read when it changes,
   so users added or removed with ct6_dash_mgr take effect without a restart, and
   a removed user's sessions stop working.

   Nothing in this module depends on NiceGUI, so it can be unit tested."""

import json
import os
import secrets
import threading
from time import time

SESSION_DAYS = 30           # A login lasts this long (or until Log out)
MAX_FAILURES = 5            # Failed logins from one address before it is locked out ...
FAILURE_WINDOW_SECS = 300   # ... within this period
LOCKOUT_SECS = 300          # Lockout duration
FAILURE_DELAY_SECS = 1.0    # Delay after each failed login

AUTHENTICATED = "authenticated"
USERNAME = "username"
LOGIN_TIME = "login_time"


def load_or_create_secret(filename):
    """@brief Get the secret used to sign session cookies, creating it (mode 0600) if needed.
              Keeping it in a file means logins survive a restart.
       @param filename The secret file.
       @return The secret string."""
    if os.path.isfile(filename):
        with open(filename) as fd:
            value = fd.read().strip()
        if len(value) >= 32:
            return value
    os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
    value = secrets.token_hex(32)
    fd = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(value)
    return value


def safe_redirect(target):
    """@return target if it is a local path on this server, else '/'.
               Prevents the login page being used to redirect to another site."""
    if not target or not isinstance(target, str):
        return "/"
    if not target.startswith("/") or target.startswith("//") or "\\" in target or "://" in target:
        return "/"
    if target.startswith("/login"):
        return "/"
    return target


class LoginManager:
    """@brief Checks usernames/passwords against the ct6_dash_mgr credentials file,
              tracks failed logins per client address and decides whether a session is valid.
              Thread safe."""

    def __init__(self, credentials_file, session_days=SESSION_DAYS, clock=time):
        """@param credentials_file The ct6_dash_mgr credentials (JSON) file.
           @param session_days How long a login lasts.
           @param clock A function returning the time in seconds (for testing)."""
        self.credentials_file = credentials_file
        self._session_secs = session_days * 86400
        self._clock = clock
        self._lock = threading.Lock()
        self._users = set()
        self._users_mtime = None
        self._failures = {}      # address -> list of failure times
        self._locked_until = {}  # address -> time

    # ------------------------------------------------------------ users

    def usernames(self):
        """@return The set of usernames in the credentials file (re-read when the file changes)."""
        with self._lock:
            try:
                mtime = os.path.getmtime(self.credentials_file)
            except OSError:
                self._users, self._users_mtime = set(), None
                return set()
            if mtime != self._users_mtime:
                try:
                    with open(self.credentials_file) as fd:
                        self._users = set(json.load(fd).keys())
                except (OSError, ValueError):
                    self._users = set()
                self._users_mtime = mtime
            return set(self._users)

    def user_count(self):
        return len(self.usernames())

    def verify(self, username, password):
        """@brief Check a username and password (slow: argon2). Run it outside the GUI thread.
           @return True if they match an entry in the credentials file."""
        if not username or password is None or username not in self.usernames():
            return False
        from p3lib.bokeh_auth import CredentialsHasher
        return bool(CredentialsHasher(self.credentials_file).verify(username, password))

    # ------------------------------------------------------------ failed logins

    def lockout_remaining(self, address):
        """@return Seconds until the address may try again, or 0 if it is not locked out."""
        with self._lock:
            until = self._locked_until.get(address, 0)
            remaining = until - self._clock()
            if remaining <= 0:
                self._locked_until.pop(address, None)
                return 0
            return int(remaining) + 1

    def record_failure(self, address):
        """@brief Record a failed login. Locks the address out after MAX_FAILURES within FAILURE_WINDOW_SECS.
           @return True if the address is now locked out."""
        with self._lock:
            now = self._clock()
            times = [t for t in self._failures.get(address, []) if now - t < FAILURE_WINDOW_SECS] + [now]
            if len(times) >= MAX_FAILURES:
                self._locked_until[address] = now + LOCKOUT_SECS
                self._failures.pop(address, None)
                return True
            self._failures[address] = times
            return False

    def clear_failures(self, address):
        with self._lock:
            self._failures.pop(address, None)
            self._locked_until.pop(address, None)

    # ------------------------------------------------------------ sessions

    def new_session(self, username):
        """@return The values to store in the user's session after a successful login."""
        return {AUTHENTICATED: True, USERNAME: username, LOGIN_TIME: self._clock()}

    def session_user(self, session):
        """@brief Check a session (NiceGUI app.storage.user or any dict).
           @return The username if the session is logged in, not expired and the user still
                   exists in the credentials file, else None."""
        if not session or not session.get(AUTHENTICATED):
            return None
        username = session.get(USERNAME)
        login_time = session.get(LOGIN_TIME) or 0
        if self._clock() - login_time > self._session_secs:
            return None
        if username not in self.usernames():
            return None
        return username
