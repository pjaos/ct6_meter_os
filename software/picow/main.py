import sys
import json
import uasyncio as asyncio

RUNNING_APP_KEY = "APP"
CONFIG_FILENAME = "this.machine.cfg"
ALLOW_APP_TO_CRASH = True          # !!! This must be set to False on released product.
                                   # This can be useful when debugging to see app crashes on stdout
                                   # This should be set to False on production code.
                                   # Note !!!
                                   # The main.py file is not updated when an over the air upgrade
                                   # is performed. To update main.py use deploy_and_run.py.
def getActiveApp():
    """@brief Get the active app from the field in the config dict file.
       @return Either 1 or 2"""
    activeApp = 1
    try:
        with open(CONFIG_FILENAME, "r") as read_file:
            configDict = json.load(read_file)
            if RUNNING_APP_KEY in configDict:
                aa = configDict[RUNNING_APP_KEY]
                if aa == 2:
                    activeApp = 2
    except:
        # Any errors reading the active app and we revert to app1
        pass
    return activeApp

def runApp(appID, initialModules):
    """@brief Run an app.
       @param appID The ID of the app to run (1 or 2).
       @param initialModules The keys of the initially python modules loaded at startup."""
    # Remove any previously added paths
    for _path in ("/app1", "/app1.lib", "/app2", "/app2.lib"):
        try:
            sys.path.remove(_path)
        except ValueError:
            pass
    # Remove app from the known modules list if it's present
    keys = list(sys.modules.keys())
    for key in keys:
        if key not in initialModules:
            try:
                del sys.modules[key]
            except KeyError:
                pass

    # Add the required paths
    if appID == 2:
        sys.path.append("/app2")
        sys.path.append("/app2.lib")
        from app2 import app
    else:
        sys.path.append("/app1")
        sys.path.append("/app1.lib")
        from app1 import app
    asyncio.run(app.start(CONFIG_FILENAME, RUNNING_APP_KEY, activeApp))

def debug(msg):
    print("DEBUG: {}".format(msg))

def addBootLog(msg, create, bootLogFile="/bootlog.txt"):
    """@brief Create a log of the boot process. As the flash is small
              it is bext not to write to much data into this file.
              This file will hold exception details should the app
              crash."""
    if create:
        fd = open(bootLogFile, 'w')
    else:
        fd = open(bootLogFile, 'a')
    fd.write(f"{msg}\n")
    fd.close()

def getLoadedModules():
    """@brief Get a list of the python modules currently loaded."""
    keyList = []
    for key in list(sys.modules.keys()):
        keyList.append(key)
    return keyList

#Program entry point
try:
    addBootLog( "Booting", True)

    initialModules = getLoadedModules()
    activeApp = getActiveApp()
    exceptionCount = 0
    while True:
        # Save the sys path in case we need to restore it.
        addedSysPaths = []
        try:
            addBootLog( f"activeApp={activeApp}", False)

            debug("activeApp={}".format(activeApp))
            runApp(activeApp, initialModules)

        except Exception as ex:
            exceptionCount += 1
            addBootLog( f"Exception {exceptionCount}: ={str(ex)}", False)
            if ALLOW_APP_TO_CRASH:
                raise
            if activeApp == 2:
                activeApp = 1
            else:
                activeApp = 2
            addBootLog( f"Reverting to app {activeApp}", False)

finally:
    asyncio.new_event_loop()
