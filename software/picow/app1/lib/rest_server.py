import json
import uasyncio as asyncio
import machine
import hashlib
import binascii
import os

from lib.uo import UOBase
from lib.io import IO

import gc
from lib.fs import VFS
from lib.wifi import WiFi
from lib.hardware import Hardware

class BuiltInCmdHandler(object):
    """@brief Handle the rest server builtin commands dicts sent over the network."""
    # Examples of API's returning JSON.
    # http://<IP ADDRESS>/<Built in REST interface command>

    # Builtin REST interface commmands.
    GET_STATUS_CMD          = "/get_sys_stats"
    GET_FLE_LIST_CMD        = "/get_file_list"
    GET_MACHINE_CFG_CMD     = "/get_machine_config"
    ERASE_OFFLINE_APP       = "/erase_offline_app"
    MKDIR_CMD               = "/mkdir"
    RMDIR_CMD               = "/rmdir"
    RM_FILE_CMD             = "/rmfile"
    GET_FILE_CMD            = "/get_file"
    RESET_WIFI_CONFIG_CMD   = "/reset_wifi_config"
    GET_ACTIVE_APP_FOLDER   = "/get_active_app_folder"
    GET_INACTIVE_APP_FOLDER = "/get_inactive_app_folder"
    SWAP_ACTIVE_APP         = "/swap_active_app"
    REBOOT_DEVICE           = "/reboot"
    RESET_TO_DEFAULT_CONFIG = "/reset_to_default_config"
    WIFI_SCAN               = "/wifi_scan"

    ACTIVE_APP_FOLDER_KEY   = "ACTIVE_APP_FOLDER"
    INACTIVE_APP_FOLDER_KEY = "INACTIVE_APP_FOLDER"
    RAM_USED_BYTES          = "RAM_USED_BYTES"
    RAM_FREE_BYTES          = "RAM_FREE_BYTES"
    RAM_TOTAL_BYTES         = "RAM_TOTAL_BYTES"
    DISK_TOTAL_BYTES        = "DISK_TOTAL_BYTES"
    DISK_USED_BYTES         = "DISK_USED_BYTES"
    DISK_PERCENTAGE_USED    = "DISK_PERCENTAGE_USED"

    def __init__(self, machineConfig, activeAppKey):
        """@brief Constructor
           @param machineConfig The machine configuration instance.
           @param activeAppKey The key in the config dict that details which app (1 or 2) we are running from."""
        self._machineConfig = machineConfig
        self._activeAppKey = activeAppKey
        self._savePersistentDataMethod = None

    def handle(self, cmdDict):
        """@brief Process the commands and return a response dict.
           @return A dict in response to the command or None if the command was not handled."""
        responseDict = None
        if RestServer.CMD_KEY in cmdDict:
            cmd = cmdDict[RestServer.CMD_KEY]
            responseDict = None
            if cmd == BuiltInCmdHandler.GET_STATUS_CMD:
                responseDict = {}
                self._updateRamStats(responseDict)
                self._updateDiskUsageStats(responseDict)

            elif cmd == BuiltInCmdHandler.GET_FLE_LIST_CMD:
                responseDict = self._getFileList()

            elif cmd == BuiltInCmdHandler.GET_MACHINE_CFG_CMD:
                responseDict = self._machineConfig

            elif cmd == BuiltInCmdHandler.ERASE_OFFLINE_APP:
                responseDict = self._eraseOfflineApp()

            elif cmd.startswith(BuiltInCmdHandler.MKDIR_CMD):
                responseDict = self._makeDir(cmdDict)

            elif cmd.startswith(BuiltInCmdHandler.RMDIR_CMD):
                responseDict = self._rmDir(cmdDict)

            elif cmd.startswith(BuiltInCmdHandler.RM_FILE_CMD):
                responseDict = self._rmFile(cmdDict)

            elif cmd.startswith(BuiltInCmdHandler.GET_ACTIVE_APP_FOLDER):
                responseDict = self._getAppFolder(True)

            elif cmd.startswith(BuiltInCmdHandler.GET_INACTIVE_APP_FOLDER):
                responseDict = self._getAppFolder(False)

            elif cmd.startswith(BuiltInCmdHandler.SWAP_ACTIVE_APP):
                responseDict = self._swapActiveAppFolder()

            elif cmd.startswith(BuiltInCmdHandler.REBOOT_DEVICE):
                responseDict = self._rebootDevice()

            elif cmd.startswith(BuiltInCmdHandler.RESET_TO_DEFAULT_CONFIG):
                responseDict = self._resetToDefaultConfig()

            elif cmd.startswith(BuiltInCmdHandler.WIFI_SCAN):
                responseDict = self._getWiFiScan()

            elif cmd.startswith(BuiltInCmdHandler.GET_FILE_CMD):
                responseDict = self._getFile(cmdDict)

            elif cmd.startswith(BuiltInCmdHandler.RESET_WIFI_CONFIG_CMD):
                self._machineConfig.resetWiFiConfig()
                responseDict = RestServer.GetOKDict()

        return responseDict

    def _getWiFiScan(self):
        """@brief Get the results of a WiFi scan."""
        return {"WIFI_SCAN_RESULTS": WiFi.Get_Wifi_Networks() }

    def _resetToDefaultConfig(self):
        """@reset the configuration to defaults."""
        self._machineConfig.setDefaults()
        self._machineConfig.store()
        return {"INFO": "The unit has been reset to the default configuration."}

    def _rebootDevice(self):
        """@brief reboot the device."""
        # Save any persistent data before we reboot
        if self._savePersistentDataMethod:
            self._savePersistentDataMethod()
        # Ensure the file system is synced before we reboot.
        os.sync()
        rebootTimer = Hardware.GetTimer()
        rebootTimer.init(mode=machine.Timer.ONE_SHOT, period=500, callback=self._doReboot) # Reboot in 500 ms
        return {"INFO": "Reboot in progress..."}

    def _doReboot(self, v):
        """@brief Perform a device restart."""
        print("Rebooting now.")
        machine.reset()

    def _swapActiveAppFolder(self):
        """@brief Swap the active app folder.
           @return a dict containing the active app folder."""
        if self._machineConfig.isParameter(self._activeAppKey):
            runningApp = self._machineConfig.get(self._activeAppKey)
            if runningApp == 1:
                newActiveApp = 2
            else:
                newActiveApp = 1
            self._machineConfig.set(self._activeAppKey, newActiveApp)
            self._machineConfig.store()
        return {BuiltInCmdHandler.ACTIVE_APP_FOLDER_KEY: newActiveApp}

    def _getAppFolder(self, active):
        """@brief Get the app folder.
           @param active If True then get the active application folder.
           @param responseDict containing the active app folder."""
        runningApp = self._machineConfig.get(self._activeAppKey)

        if runningApp == 1:
            offLineApp = 2
        if runningApp == 2:
            offLineApp = 1

        if active:
            appRoot = "/app{}".format(runningApp)
            returnDict = {BuiltInCmdHandler.ACTIVE_APP_FOLDER_KEY: appRoot}
        else:
            appRoot = "/app{}".format(offLineApp)
            returnDict = {BuiltInCmdHandler.INACTIVE_APP_FOLDER_KEY: appRoot}

        return returnDict


    def _rmFile(self, cmdDict):
        """@brief Remove a dir on the devices file system.
           @return The response dict."""
        responseDict = RestServer.GetErrorDict("Unknown /rmfile error")
        if 'file' in cmdDict:
            fileToDel = cmdDict['file']
            try:
                os.remove(fileToDel)
                responseDict = RestServer.GetOKDict()
            except OSError:
                responseDict = RestServer.GetErrorDict("Failed to delete {}".format(fileToDel))
        else:
            responseDict = RestServer.GetErrorDict("No file passed to /rmfile")
        return responseDict

    def _rmDir(self, cmdDict):
        """@brief Remove a dir on the devices file system.
           @param cmdDict The command dictionary.
           @return The response dict."""
        responseDict = RestServer.GetErrorDict("Unknown /rmdir error")
        if 'dir' in cmdDict:
            dirToRemove = cmdDict['dir']
            try:
                os.rmdir(dirToRemove)
                responseDict = RestServer.GetOKDict()
            except OSError:
                responseDict = RestServer.GetErrorDict("Failed to remove {}".format(dirToRemove))
        else:
            responseDict = RestServer.GetErrorDict("No dir passed to /rmdir")
        return responseDict
    
    def _getFile(self, cmdDict):
        """@brief Get the contents of a file on the devices file system.
           @param cmdDict The command dictionary.
           @return The response dict."""
        responseDict = RestServer.GetErrorDict("Unknown /get_file error")
        if 'file' in cmdDict:
            fileToGet = cmdDict['file']
            try:
                fd = None
                try:
                    fd = open(fileToGet)
                    fileContent = fd.read()
                    fd.close()
                    responseDict = RestServer.GetOKDict()
                    responseDict[fileToGet]=fileContent
                finally:
                    if fd:
                        fd.close()
                        fd = None

            except Exception as ex:
                responseDict["ERROR"]=str(ex)

        return responseDict
        
    def _makeDir(self, cmdDict):
        """@brief Create a dir on the devices file system.
           @return The response dict."""
        responseDict = RestServer.GetErrorDict("Unknown /mkdir error")
        if 'dir' in cmdDict:
            dirToMake = cmdDict['dir']
            try:
                os.mkdir(dirToMake)
                responseDict = RestServer.GetOKDict()
            except OSError:
                responseDict = RestServer.GetErrorDict("Failed to create {}".format(dirToMake))
        else:
            responseDict = RestServer.GetErrorDict("No dir passed to /mkdir")
        return responseDict

    def _removeDir(self, theDirectory):
        """@brief Remove the directory an all of it's contents.
           @param theDirectory The directory to remove."""
        if IO.DirExists(theDirectory):
            entryList = []
            self._getFolderEntries(theDirectory, entryList)
            for entry in entryList:
                if IO.DirExists(entry):
                    self._removeDir(entry)
                    
                elif IO.FileExists(entry):
                    os.remove(entry)
            # All contents removed so remove the top level.
            os.remove(theDirectory)  
        
    def _eraseOfflineApp(self):
        """@brief Erase the offline app."""
        runningApp = self._machineConfig.get(self._activeAppKey)
        if runningApp == 1:
            offLineApp = 2
        if runningApp == 2:
            offLineApp = 1
        appRoot = "/app{}".format(offLineApp)
        self._removeDir(appRoot)
        return RestServer.GetOKDict()

    def _getFileList(self):
        """@brief List all the files on disk.
           @return a dict containing all the files on disk."""
        fileList = []
        self._getFolderEntries('/', fileList)
        return fileList

    def _getFolderEntries(self, folder, fileList):
        """@brief List the entries in a folder.
           @brief folder The folder to look for files in.
           @brief fileList The list to add files to."""
        fsIterator = os.ilistdir(folder)
        for nodeList in fsIterator:
            if len(nodeList) >= 3:
                name = nodeList[0]
                type = nodeList[1]
                if len(name) > 0:
                    if folder == '/':
                        anEntry = folder + name
                    else:
                        anEntry = folder + "/" + name
                    if type == IO.TYPE_FILE:
                        fileList.append(anEntry)

                    elif type == IO.TYPE_DIR:
                        # All folders end in /
                        fileList.append(anEntry + '/')
                        # Recurse through dirs
                        self._getFolderEntries(anEntry, fileList)

    def _updateRamStats(self, responseDict):
        """@brief Update the RAM usage stats.
           @param responseDict the dict to add the stats to."""
        usedBytes = gc.mem_alloc()
        freeBytes = gc.mem_free()
        responseDict[BuiltInCmdHandler.RAM_USED_BYTES] = usedBytes
        responseDict[BuiltInCmdHandler.RAM_FREE_BYTES] = freeBytes
        responseDict[BuiltInCmdHandler.RAM_TOTAL_BYTES] = usedBytes + freeBytes

    def _updateDiskUsageStats(self, responseDict):
        """@brief Update the RAM usage stats.
           @param responseDict the dict to add the stats to."""
        totalBytes, usedSpace, percentageUsed = VFS.GetFSInfo()
        responseDict[BuiltInCmdHandler.DISK_USED_BYTES] = usedSpace
        responseDict[BuiltInCmdHandler.DISK_PERCENTAGE_USED] = percentageUsed

    def setSavePersistentDataMethod(self, savePersistentDataMethod):
        """@brief Set the method to be called to save all persistent data on the device.
                  This method will be called before a reboot or power cycle in order to save the current system state.
           @param savePersistentDataMethod The method to be called to save all persistent data on the unit."""
        self._savePersistentDataMethod = savePersistentDataMethod
        
class RestServer(UOBase):
    """@brief Responsible for providing a REST interface to allow clients to
              collect data but could be extended to send arguments to the Pico W."""

    TCP_PORT = 80                                            # The TCP port to present the REST server on.
    SERVER_EXCEPTION_LOG_FILE = '/rest_server_exception.txt' # Rest server exceptions are stored in for debug purposes.
    OK_KEY = "OK"                                            # The key in the JSON response if no error occurs.
    ERROR_KEY = "ERROR"                                      # The key in the JSON response if an error occurs.
    CMD_KEY = "CMD"                                          # The command from the http request.
    GET_REQ = "GET_REQ"                                      # The full http get request line.

    FILE_READ_BUFFER_SIZE = 256                              # The max number of bytes read from the socket buffer
                                                             # when receiving a file.
    @staticmethod
    def GetErrorDict(msg):
        """@brief Get an error response dict.
           @param msg The message to include in the response.
           @return The dict containing the error response"""
        return { RestServer.ERROR_KEY: msg}

    @staticmethod
    def GetOKDict():
        """@brief Get an OK dict response.
           @param msg The message to include in the response.
           @return The dict containing the error response"""
        return { RestServer.OK_KEY: True}

    def __init__(self, machineConfig, activeAppKey, projectCmdHandler, uo=None):
        """@brief Constructor
           @brief machineConfig A MachineConfig as defined in project.
           @param activeAppKey The key in the config dict that details which app (1 or 2) we are running from.
           @param projectCmdHandler The object responsible for handling command dicts . This object
                             must have a method named handle that takes a single argument
                             (the command dict) and returns a response dict that is
                             converted to JSON and sent back to the source.
           @param uo A UO instance for presenting data to the user. If Left as None
                     no data is sent to the user."""
        super().__init__(uo=uo)
        self._builtInCmdHandler = BuiltInCmdHandler(machineConfig, activeAppKey)
        self._projectCmdHandler = projectCmdHandler
        self._serverRunning = False
        self._savePersistentDataMethod = None

    def setSavePersistentDataMethod(self, savePersistentDataMethod):
        """@brief Set the method to be called to save all persistent data on the device.
           @param savePersistentDataMethod The method to be called to save all persistent data on the unit."""
        self._builtInCmdHandler.setSavePersistentDataMethod(savePersistentDataMethod)
        self._projectCmdHandler.setSavePersistentDataMethod(savePersistentDataMethod)
        
    def startServer(self):
        asyncio.create_task(asyncio.start_server(self._serve_client, "0.0.0.0", RestServer.TCP_PORT))
        self._serverRunning = True

    def isServerRunning(self):
        """@brief Determine if the server is running."""
        return self._serverRunning

    def _ok_json_response(self, writer):
        """@brief Send an HTTP OK response and header to define JSON data following.
           @param writer The writer object used to send data."""
        writer.write('HTTP/1.0 200 OK\r\nContent-type: application/json\r\n\r\n')

    def _error_json_response(self, writer):
        """@brief Send an HTTP error response and header to define JSON data following.
           @param writer The writer object used to send data."""
        writer.write('HTTP/1.0 500 ERROR\r\nContent-type: application/json\r\n\r\n')

    def _getFileAttr(self, requestLine):
        """@brief Read the file attributes from the request line.
           @param requestLine The HTTP file request line.
           @return A tuple of the following elements
                   0 = fileName
                   1 = filePath
                   2 = length
                   3 = sha256

                   These elements may be None if not found in the request line."""
        fileName=None
        filePath=None
        length=None
        sha256=None
        if requestLine.startswith("FILE "):
            try:
                # Receive the file and save to disk
                elems = requestLine.split()
                if( len(elems) == 6 ):
                    length   = int(elems[3].decode())
                    fileName = elems[1].decode()
                    filePath = elems[2].decode()
                    sha256   = elems[4].decode()
                    # If the path ends with a '/' character, remove it
                    if len(filePath) != 1 and filePath.endswith('/'):
                        filePath = filePath[:-1]
            except ValueError:
                pass

            return (fileName, filePath, length, sha256)

    async def _serve_client(self, reader, writer):
        """@brief Called to serve a request for data."""
        self._info("Client connected")
        request_line = await reader.readline()
        self._info("Request: %s" % request_line)
        # If this is the propriatary HTTP FILE command
        if request_line.startswith("FILE "):
            #Receive a file and write to disk in chunks
            readSize = RestServer.FILE_READ_BUFFER_SIZE
            fileName, filePath, length, sha256 = self._getFileAttr(request_line)
            # We don't check the file length as we may need o transfer a file of 0 length
            if fileName and filePath and sha256:
                self._debug("fileName: {}".format(fileName))
                self._debug("filePath: {}".format(filePath))
                self._debug("length:   {}".format(length))
                rxHash = None
                fd = None
                try:
                    # The if the dest path does not exist create it.
                    if not IO.DirExists(filePath):
                        self._debug("Creating {} folder".format(filePath))
                        os.mkdir(filePath)

                    absFile=filePath + '/' + fileName
                    fd = open(absFile, 'w')
                    bytesLeftToRead = length
                    # If we have an empty file we still need a sha256
                    if length == 0:
                        rxHash = hashlib.sha256()
                    while bytesLeftToRead > 0:
                        if bytesLeftToRead < readSize:
                            readSize = bytesLeftToRead
                        data = await reader.readexactly(readSize)
                        if rxHash:
                            rxHash.update(data)
                        else:
                            rxHash = hashlib.sha256(data)
                        fd.write(data)
                        bytesLeftToRead = bytesLeftToRead - readSize
                    fd.close()
                    fd = None
                    digest = binascii.hexlify(rxHash.digest())
                    self._debug("Expected sha256: {}".format(sha256))
                    self._debug("Found sha256:    {}".format(digest.decode()))
                    if digest.decode() == sha256:
                        # Send the HTTP OK header detailing JSON text to follow.
                        self._ok_json_response(writer)
                        self._info("{} XFER OK".format(absFile))
                        response_dict = RestServer.GetOKDict()
                    else:
                        self._error_json_response(writer)
                        os.remove(absFile)
                        response_dict = RestServer.GetErrorDict("{} XFER ERROR (deleted).".format(absFile))
                    response = json.dumps(response_dict)
                finally:
                    if fd:
                        fd.close()
        else:
            # We are not interested in HTTP request headers, skip them
            while await reader.readline() != b"\r\n":
                pass

            req = request_line.decode()

            # We don't respond with an HTTP 404 error but return a JSON message
            # in the event of an error.
            response_dict = RestServer.GetErrorDict("{} is a malformed request.".format(req))
            response = json.dumps(response_dict)

            args_dict  = self._get_args_dict(req)
            self._debug("args_dict={}".format(args_dict))
            # First see if we have received a command that can be handled by the rest server
            response_dict = self._builtInCmdHandler.handle(args_dict)
            if response_dict is None and self._projectCmdHandler:
                # If not handled then see if the project handler can handle the command.
                response_dict = self._projectCmdHandler.handle(args_dict)
            response = json.dumps(response_dict)

        # We don't allow ' characters in the json string
        # as browsers will raise an error,
        response = response.replace("'",'"')

        try:
            # Send the HTTP OK header detailing JSON text to follow.
            self._ok_json_response(writer)
            # Send the response to the request
            writer.write(response)
            await writer.drain()
            await writer.wait_closed()
        except OSError as ex:
            print("OSError: {}".format(ex))
        self._info("Client disconnected")

    def _get_args_dict(self, http_request):
        """@brief Get a dict containing the arguments detailed in the http request.
           @param http_request The http request line.
           @return A dict containing the arguments passed in the HTTP GET request.
                   This may include the following keys but others may be included
                   if key=value pairs (separated by ? characters) are present in
                   the http request.

                   CMD = The command in the http request. This is the first element
                   of the http request. This is only included if an HTTP get request
                   was found.
                   GET_REQ = The full http request string. This is only included
                   if an HTTP get request was found."""
        return_dict = {}
        pos = http_request.find("GET ")
        if pos >= 0:
            return_dict[RestServer.GET_REQ]=http_request
            sub_str = http_request[pos+4:]
            elems = sub_str.split()
            if len(elems) > 0:
                args_str=elems[0]
                args_list = args_str.split('?')
                if len(args_list) > 0:
                    # Add the command (first arg) to the list of args
                    if len(args_list) > 0:
                        return_dict[RestServer.CMD_KEY]=args_list[0].lower()
                        # Add any subsequent arguments
                        if len(args_list) > 1:
                            # Args are separated by , character not &
                            subArgs = args_list[1].split(",")
                            for arg in subArgs:
                                keyValue = arg.split("=")
                                if len(keyValue) == 2:
                                    return_dict[keyValue[0].lower()]=keyValue[1]

        return return_dict
