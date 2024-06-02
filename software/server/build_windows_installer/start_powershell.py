#!/usr/bin/python3

import sys, os
import site
import subprocess
from pathlib import Path


def main():
    print(sys.argv)
    
    print("***************************************************************************")
    print("* The following commands are available.                                   *")
    print("* - ct6_db_store.bat                                                      *")
    print("* Allow data from CT6 devices to be stored in a MYSQL databse.            *")
    print("* - ct6_dash.bat                                                          *")
    print("* Display a dashboard to read and display the data in the database.       *")
    print("* - ct6_dash_mgr.bat                                                      *")
    print("* Add/Remove users to the access list for the server if enabled in config *")
    print("* - ct6_mfg_tool.bat                                                      *")
    print("* Perform manufacturing test and calibration of a CT6 unit.               *")
    print("* - ct6_tool.bat                                                          *")
    print("* Provides functionality that is useful when developing CT6 software.     *")
    print("* - ct6_configurator.bat                                                  *")
    print("* Provides the ability to configure a CT6 unit from a web GUI.            *")
    print("***************************************************************************")

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
