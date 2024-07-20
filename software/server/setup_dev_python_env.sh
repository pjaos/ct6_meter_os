# This is for use when developing CT6 on an Ubuntu 24.04 platform.

# We need PIP installed
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python3 get-pip.py

# Ensure we have the latest pip version
python3 -m pip install --break-system-packages --upgrade pip

# Install poetry
python3 -m pip install --break-system-packages poetry
