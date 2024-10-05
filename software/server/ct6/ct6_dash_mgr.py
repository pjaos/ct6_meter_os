#!/usr/bin/env python3

import  os
from    p3lib.uio import UIO
from    p3lib.bokeh_auth import CredentialsManager

CRED_JSON_FILE = os.path.join( os.path.expanduser("~"), ".ct6_dash_credentials.json")
# If root user then the above can return an incorrect path (/home/root/...). Fix this.
if os.geteuid()  == 0:
    CRED_JSON_FILE = os.path.join( '/root', ".ct6_dash_credentials.json")

def main():
    uio = UIO()
    credentialsManager = CredentialsManager(uio, CRED_JSON_FILE)
    credentialsManager.manage()

if __name__ == '__main__':
    main()