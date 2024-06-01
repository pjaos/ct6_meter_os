#!/usr/bin/python3

import sys, os
import site
import subprocess
from pathlib import Path

BATCH_FILE = 'ct6_configurator.bat'

def main():
    print("Launching the Application. This may take a few seconds...")

    scriptdir, script = os.path.split(os.path.abspath(__file__))
    pkgdir = os.path.join(scriptdir, 'pkgs')
    # Ensure .pth files in pkgdir are handled properly
    site.addsitedir(pkgdir)
    sys.path.insert(0, pkgdir)
    # Ensure working dir is correct
    installFolder = Path(scriptdir).parent
    installFolder = str(installFolder)
    os.chdir(installFolder)
    #Start the batch file to launch the program
    subprocess.call([f'{BATCH_FILE}'], env=os.environ)

if __name__ == "__main__":
    main()
