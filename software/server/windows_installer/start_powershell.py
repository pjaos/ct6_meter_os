#!/usr/bin/python3

import sys, os
import site
import subprocess
from pathlib import Path


def main():
    print(sys.argv)
    
    print("*****************************************************************")
    print("* CT6 app commands can be executed from the PowerShell         *")
    print("* command line interface.                                       *")
    print("*                                                               *")
    print("*****************************************************************")

    scriptdir, script = os.path.split(os.path.abspath(__file__))
    pkgdir = os.path.join(scriptdir, 'pkgs')
    # Ensure .pth files in pkgdir are handled properly
    site.addsitedir(pkgdir)
    sys.path.insert(0, pkgdir)
    #Start the powershell in the folder where all the python files reside.
    installFolder = Path(scriptdir).parent
 
    #This path is created from data in the installer.cfg file. Need to use wildcard character to fill in spaces.
    iFolder = str(installFolder)
    iFolder = iFolder.replace(" ", "*")
    #subprocess.call(['powershell', '-NoExit', '-Command', 'python3 -m pipenv shell', f'Set-Location -Path "{iFolder}"'])
    subprocess.call(['powershell', '-NoExit', f'Set-Location -Path "{iFolder}"'])

if __name__ == "__main__":
    main()
