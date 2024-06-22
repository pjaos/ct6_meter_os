# !/usr/bin/env python3

"""NiceGui Tools
   Responsible for providing helper classes for nicegui interfaces 
   aimed at reducing coding required for a GUI.
"""

import traceback
import os
import platform
import argparse

from p3lib.uio import UIO
from p3lib.helper import logTraceBack

from queue import Queue
from time import time, strftime, localtime


from nicegui import ui, app

from pathlib import Path
from typing import Optional

from nicegui import events

class TabbedNiceGui(object):
    """@brief Responsible for starting the providing a tabbed GUI.
              This class is designed to ease the creation of a tabbed GUI interface.
              The contents of each tab can be defined in the subclass.
              The GUI includes a message log area below each tab. Tasks can send messages 
              to this log area.
              If a subclass sets the self._logFile attributed then all messages sent to the 
              log area are written to a log file with timestamps."""

    # This can be used in the markdown text for a TAB description to give slightly larger text
    # than normal.
    DESCRIP_STYLE               = '<span style="font-size:1.5em;">'
    ENABLE_BUTTONS              = "ENABLE_BUTTONS"
    UPDATE_SECONDS              = "UPDATE_SECONDS"
    INFO_MESSAGE                = "INFO:  "
    WARN_MESSAGE                = "WARN:  "
    ERROR_MESSAGE               = "ERROR: "
    DEBUG_MESSAGE               = "DEBUG: "
    MAX_PROGRESS_VALUE          = 100
    DEFAULT_SERVER_PORT         = 9812

    @staticmethod
    def GetDateTimeStamp():
        """@return The log file date/time stamp """
        return strftime("%Y%m%d%H%M%S", localtime()).lower()
    
    @staticmethod
    def GetInstallFolder():
        """@return The folder where the apps are installed."""
        installFolder = os.path.dirname(__file__)
        if not os.path.isdir(installFolder):
            raise Exception(f"{installFolder} folder not found.")
        return installFolder
    
    @staticmethod
    def GetLogFileName(logFilePrefix):
        """@param logFilePrefix The text in the log file name before the timestamp.
           @return The name of the logfile including datetime stamp."""
        dateTimeStamp = TabbedNiceGui.GetDateTimeStamp()
        logFileName = f"{logFilePrefix}_{dateTimeStamp}.log"
        return logFileName
    
    def __init__(self, debugEnabled, logPath=None):
        """@brief Constructor
           @param debugEnabled True if debugging is enabled.
           @param logPath The path to store log files. If left as None then no log files are created."""
        self._debugEnabled      = debugEnabled
        self._logFile           = None              # This must be defined in subclass if logging to a file is required.
        self._buttonList        = []
        self._logMessageCount   = 0
        self._progressStepValue = 0

        self._logPath           = None
        if logPath:
            self._logPath       = os.path.join(os.path.expanduser('~'), logPath)
            self._ensureLogPathExists()

        self._isWindows         = platform.system() == "Windows"
        self._installFolder     = TabbedNiceGui.GetInstallFolder()

        # Make the install folder our current dir
        os.chdir(self._installFolder)

        

        # this queue is used to send commands from the GUI thread and read responses received from outside the GUI thread.
        self._commsQueue = Queue()

    def _ensureLogPathExists(self):
        """@brief Ensure that the log path exists."""
        if not os.path.isdir(self._logPath):
            os.makedirs(self._logPath)

    def getLogPath(self):
        """@return the Log file path if defined."""
        return self._logPath

    # Start ------------------------------
    # Methods that allow the GUI to display standard UIO messages
    # This allows the GUI to be used with code that was written 
    # to be used on the command line using UIO class instances 
    #
    def info(self, msg):
        """@brief Send a info message to be displayed in the GUI.
                  This can be called from outside the GUI thread.
           @param msg The message to be displayed."""
        msgDict = {TabbedNiceGui.INFO_MESSAGE: msg}
        self.updateGUI(msgDict)

    def warn(self, msg):
        """@brief Send a warning message to be displayed in the GUI.
                  This can be called from outside the GUI thread.
           @param msg The message to be displayed."""
        msgDict = {TabbedNiceGui.WARN_MESSAGE: msg}
        self.updateGUI(msgDict)
        
    def error(self, msg):
        """@brief Send a error message to be displayed in the GUI.
                  This can be called from outside the GUI thread.
           @param msg The message to be displayed."""
        msgDict = {TabbedNiceGui.ERROR_MESSAGE: msg}
        self.updateGUI(msgDict)
        
    def debug(self, msg):
        """@brief Send a debug message to be displayed in the GUI.
                  This can be called from outside the GUI thread.
           @param msg The message to be displayed."""
        if self._debugEnabled:
            msgDict = {TabbedNiceGui.DEBUG_MESSAGE: msg}
            self.updateGUI(msgDict)

    async def getInput(self, prompt):
        """@brief Allow the user to enter some text.
                  This can be called from outside the GUI thread.
           @param prompt The user prompt."""
        with ui.dialog() as dialog, ui.card():
            inputObj = ui.input(label=prompt)
            with ui.row():
                ui.button('OK', on_click=lambda: dialog.submit('OK'))
                ui.button('Cancel', on_click=lambda: dialog.submit('Cancel'))

        result = await dialog
        if result != 'OK':
            returnText = None
        else:
            returnText = inputObj.value
        return returnText
            
    def reportException(self, exception):
        """@brief Report an exception.
                  If debug is enabled a full stack trace is displayed.
                  If not then the exception message is displayed.
           @param exception The exception instance."""
        if self._debugEnabled:
            self.error(traceback.format_exc())
            
        else:
            self.error( exception.args[0] )

    def _sendEnableAllButtons(self, state):
        """@brief Send a message to the GUI to enable/disable all the GUI buttons.
                  This can be called from outside the GUI thread.
           @param state If True enable the buttons, else disable them."""
        msgDict = {TabbedNiceGui.ENABLE_BUTTONS: state}
        self.updateGUI(msgDict)

    def updateGUI(self, msgDict):
        """@brief Send a message to the GUI so that it updates itself.
           @param msgDict A dict containing details of how to update the GUI."""
        # Record the seconds when we received the message
        msgDict[TabbedNiceGui.UPDATE_SECONDS]=time()
        self._commsQueue.put(msgDict)

    def showTable(self, table, rowSeparatorChar = "-", colSeparatorChar = "|"):
        """@brief Show the contents of a table to the user.
           @param table This must be a list. Each list element must be a table row (list).
                        Each element in each row must be a string.
           @param rowSeparatorChar The character used for horizontal lines to separate table rows.
           @param colSeparatorChar The character used to separate table columns."""
        columnWidths = []
        # Check we have a table to display
        if len(table) == 0:
            raise Exception("No table rows to display")
        
        # Check all rows have the same number of columns in the table
        colCount = len(table[0])
        for row in table:
            if len(row) != colCount:
                raise Exception(f"{str(row)} column count different from first row ({colCount})")
        
        for row in table:
            for col in row:
                if not isinstance(col, str):
                    raise Exception(f"Table column is not a string: {col} in {row}")
                
        # Get the max width for each column
        for col in range(0,colCount):
            maxWidth=0
            for row in table:
                if len(row[col]) > maxWidth:
                    maxWidth = len(row[col])
            columnWidths.append(maxWidth)

        tableWidth = 1
        for columnWidth in columnWidths:
            tableWidth += columnWidth + 3 # Space each side of the column + a column divider character
                    
        # Add the top line of the table
        self.info(rowSeparatorChar*tableWidth)
               
        # The starting row index
        for rowIndex in range(0, len(table)):
            rowText = colSeparatorChar
            colIndex = 0
            for col in table[rowIndex]:
                colWidth = columnWidths[colIndex]
                rowText = rowText + " " + f"{col:>{colWidth}s}" + " " + colSeparatorChar
                colIndex += 1
            self.info(rowText)
            # Add the row separator line
            self.info(rowSeparatorChar*tableWidth)

    def logAll(self, enabled):
        pass

    def setLogFile(self, logFile):
        pass

    # End ------------------------------   

    def _saveLogMsg(self, msg):
        """@brief Save the message to a log file.
           @param msg The message text to be stored in the log file."""
        # If a log file has been set
        if self._logFile:
            # If the log file does not exist
            if not os.path.isfile(self._logFile):
                with open(self._logFile, 'w') as fd:
                    pass
            # Update the log file
            with open(self._logFile, 'a') as fd:
                dateTimeStamp = TabbedNiceGui.GetDateTimeStamp()
                fd.write(dateTimeStamp + ": " + msg + '\n')
    
    def _getDisplayMsg(self, msg, prefix):
        """@brief Get the msg to display. If the msg does not already have a msg level we add one.
           @param msg The source msg.
           @param prefix The message prefix (level indcator) to add."""
        if msg.startswith(TabbedNiceGui.INFO_MESSAGE) or \
           msg.startswith(TabbedNiceGui.WARN_MESSAGE) or \
           msg.startswith(TabbedNiceGui.ERROR_MESSAGE) or \
           msg.startswith(TabbedNiceGui.DEBUG_MESSAGE):
            _msg = msg
        else:
            _msg = prefix + msg
        return _msg

    def _handleMsg(self, msg):
        """@brief Log a message.
           @param msg the message to the log window and the log file."""
        self._log.push(msg)
        self._saveLogMsg(msg)
        self._logMessageCount += 1
        self._progress.set_value( int(self._logMessageCount*self._progressStepValue) )

    def _infoGT(self, msg):
        """@brief Update an info level message. This must be called from the GUI thread.
           @param msg The message to display."""
        _msg = self._getDisplayMsg(msg, TabbedNiceGui.INFO_MESSAGE)
        self._handleMsg(_msg)

    def _warnGT(self, msg):
        """@brief Update an warning level message. This must be called from the GUI thread.
           @param msg The message to display."""
        _msg = self._getDisplayMsg(msg, TabbedNiceGui.WARN_MESSAGE)
        self._handleMsg(_msg)

    def _errorGT(self, msg):
        """@brief Update an error level message. This must be called from the GUI thread.
           @param msg The message to display."""
        _msg = self._getDisplayMsg(msg, TabbedNiceGui.ERROR_MESSAGE)
        self._handleMsg(_msg)

    def _debugGT(self, msg):
        """@brief Update an debug level message. This must be called from the GUI thread.
           @param msg The message to display."""
        _msg = self._getDisplayMsg(msg, TabbedNiceGui.DEBUG_MESSAGE)
        self._handleMsg(_msg)

    def _clearMessages(self):
        """@brief Clear all messages from the log."""
        self._log.clear()
        self._logMessageCount = 0

    def _getLogMessageCount(self):
        """@return the number of messages written to the log window/file"""
        return self._logMessageCount

    def _enableAllButtons(self, enabled):
        """@brief Enable/Disable all buttons.
           @param enabled True if button is enabled."""
        if enabled:
            for button in self._buttonList:
                button.enable()
            self._progress.set_visibility(False)
        else:
            for button in self._buttonList:
                button.disable()
            # If the caller has defined the number of log messages for normal completion
            if self._progressStepValue > 0:
                self._progress.set_visibility(True)

    def periodicTimer(self):
        """@called periodically to allow updates of the GUI."""
        while not self._commsQueue.empty():
            rxMessage = self._commsQueue.get()
            if isinstance(rxMessage, dict):
                self._processRXDict(rxMessage)

    def initGUI(self, tabNameList, tabMethodInitList, reload=True, address="0.0.0.0", port=DEFAULT_SERVER_PORT, pageTitle="NiceGUI"):
        """@brief Init the tabbed GUI.
           @param tabNameList A list of the names of each tab to be created.
           @param tabMethodInitList A list of the methods to be called to init each of the above tabs. 
                                    The two lists must be the same size.
           @param reload If reload is set False then changes to python files will not cause the server to be restarted.
           @param address The address to bind the server to.
           @param The TCP port to bind the server to.
           @param pageTitle The page title that appears in the browser."""
        # A bit of defensive programming.
        if len(tabNameList) != len(tabMethodInitList):
            raise Exception(f"initGUI: BUG: tabNameList ({len(tabNameList)}) and tabMethodInitList ({len(tabMethodInitList)}) are not the same length.")
        tabObjList = []
        with ui.row():
            with ui.tabs().classes('w-full') as tabs:
                for tabName in tabNameList:
                    tabObj = ui.tab(tabName)
                    tabObjList.append(tabObj)
                
            with ui.tab_panels(tabs, value=tabObjList[0]).classes('w-full'):
                for tabObj in tabObjList:
                    with ui.tab_panel(tabObj):
                        tabIndex = tabObjList.index(tabObj)
                        tabMethodInitList[tabIndex]()

        guiLogLevel = "warning"
        if self._debugEnabled:
            guiLogLevel = "debug"

        ui.label("Message Log")
        self._progress = ui.slider(min=0,max=TabbedNiceGui.MAX_PROGRESS_VALUE,step=1)
        self._progress.set_visibility(False)
        self._log = ui.log(max_lines=2000)
        self._log.set_visibility(True)

        with ui.row():
            ui.button('Quit', on_click=self.close)
            ui.button('Log Message Count', on_click=self._showLogMsgCount)
            ui.button('Clear Log', on_click=self._clearLog)

        ui.timer(interval=0.1, callback=self.periodicTimer)
        ui.run(host=address, port=port, title=pageTitle, dark=True, uvicorn_logging_level=guiLogLevel, reload=reload)

    def _setProgressMessageCount(self, normalCount, debugCount):
        """@brief Set the number of log messages expected for normal completion of the current action.
           @param normalCount The number of messages expected when debug is off.
           @param debugCount The number of messages expected when debug is on."""
        self._progressStepValue = 0
        if self._debugEnabled:
            self._progress.min=0
            if debugCount > 0:
                self._progressStepValue = TabbedNiceGui.MAX_PROGRESS_VALUE/float(debugCount)
        else:
            self._progress.min=0
            if normalCount > 0:
                self._progressStepValue = TabbedNiceGui.MAX_PROGRESS_VALUE/float(normalCount)

    def _initTask(self, normalCount, debugCount):
        """@brief Should be called before a task is started.
           @param normalCount The number of messages expected when debug is off.
           @param debugCount The number of messages expected when debug is on."""
        self._setProgressMessageCount(normalCount, debugCount)
        self._enableAllButtons(False)
        self._clearMessages()
        
    def _clearLog(self):
        """@brief Clear the log text"""
        if self._log:
            self._log.clear()

    def _showLogMsgCount(self):
        """@brief Show the number of log messages"""
        ui.notify(f"{self._getLogMessageCount()} messages in the log.")
        
    def close(self):
        """@brief Close down the app server."""
        ui.notify("Press 'CTRL C' at command line to quit.")
        # A subclass close() method can call 
        # app.shutdown()
        # if reload=False on ui.run()

    def _appendButtonList(self, button):
        """@brief Add to the button list. These buttons are disabled during the progress of a task.
           @param button The button instance."""
        self._buttonList.append(button)

    def _processRXDict(self, rxDict):
        """@brief Process the dicts received from the GUI message queue.
           @param rxDict The dict received from the GUI message queue."""
        if TabbedNiceGui.INFO_MESSAGE in rxDict:
            msg = rxDict[TabbedNiceGui.INFO_MESSAGE]
            self._infoGT(msg)

        elif TabbedNiceGui.WARN_MESSAGE in rxDict:
            msg = rxDict[TabbedNiceGui.WARN_MESSAGE]
            self._warnGT(msg)

        elif TabbedNiceGui.ERROR_MESSAGE in rxDict:
            msg = rxDict[TabbedNiceGui.ERROR_MESSAGE]
            self._errorGT(msg)

        elif TabbedNiceGui.DEBUG_MESSAGE in rxDict:
            msg = rxDict[TabbedNiceGui.DEBUG_MESSAGE]
            self._debugGT(msg)
            
        elif TabbedNiceGui.ENABLE_BUTTONS in rxDict:
            state = rxDict[TabbedNiceGui.ENABLE_BUTTONS]
            self._enableAllButtons(state)

        else:

            self._handleGUIUpdate(rxDict)

    def _handleGUIUpdate(self, rxDict):
        """@brief Process the dicts received from the GUI message queue
                  that were not handled by the parent class.
           @param rxDict The dict received from the GUI message queue."""
        raise NotImplementedError("_handleGUIUpdate() is not implemented. Implement this method in a subclass of TabbedNiceGUI")


class YesNoDialog(object):
    """@brief Responsible for displaying a dialog box to the user with a boolean (I.E yes/no, ok/cancel) response."""
    TEXT_INPUT_FIELD_TYPE   = 1
    NUMBER_INPUT_FIELD_TYPE = 2
    SWITCH_INPUT_FIELD_TYPE = 3
    DROPDOWN_INPUT_FIELD    = 4
    COLOR_INPUT_FIELD       = 5
    DATE_INPUT_FIELD        = 6
    TIME_INPUT_FIELD        = 7
    KNOB_INPUT_FIELD        = 8
    VALID_FIELD_TYPE_LIST   = (TEXT_INPUT_FIELD_TYPE, 
                               NUMBER_INPUT_FIELD_TYPE, 
                               SWITCH_INPUT_FIELD_TYPE, 
                               DROPDOWN_INPUT_FIELD,
                               COLOR_INPUT_FIELD,
                               DATE_INPUT_FIELD,
                               TIME_INPUT_FIELD,
                               KNOB_INPUT_FIELD)

    FIELD_TYPE_KEY          = "FIELD_TYPE_KEY"      # The type of field to be displayed.
    VALUE_KEY               = "VALUE_KEY"           # The value to be displayed in the field when the dialog is displayed. 
    MIN_NUMBER_KEY          = "MIN_NUMBER_KEY"      # If the type is NUMBER_INPUT_FIELD_TYPE, the min value that can be entered.
    MAX_NUMBER_KEY          = "MAX_NUMBER_KEY"      # If the type is NUMBER_INPUT_FIELD_TYPE, the max value that can be entered.
    WIDGET_KEY              = "WIDGET_KEY"          # The key to the GUI widget (E.G ui.input, ui.number etc)
    OPTIONS_KEY             = "OPTIONS_KEY"         # Some input fields require a list of options (E.G DROPDOWN_INPUT_FIELD).

    def __init__(self, 
                 prompt,
                 successMethod,
                 failureMethod=None,
                 successButtonText="Yes",
                 failureButtonText="No"):
        """@brief Constructor"""
        self._dialog                 = None
        self._selectedFile           = None
        self._successButtonText      = None          # The dialogs success button text
        self._failureButtonText      = None          # The dialogs failure button text
        self._prompt                 = None          # The prompt to be displayed in the dialog
        self._successMethod          = None          # The method to be called when the success button is selected.
        self._failureMethod          = None          # The method to be called when the failure button is selected.
        self._inputFieldDict         = {}            # A dict of input field details to be included in the dialog. Can be left as an empty dict if no input fields are required.
                                                     # The key in this dict is the name of the input field that the user sees. 
                                                     # The value in this dict is another dict containing details of the input field which may be

        self.setPrompt(prompt)
        self.setSuccessMethod(successMethod)
        self.setFailureMethod(failureMethod)
        self.setSuccessButtonLabel(successButtonText)
        self.setFailureButtonLabel(failureButtonText)


    def addField(self, name, fieldType, value=None, minNumber=None, maxNumber=None, options=None):
        """@brief Add a field to the dialog.
           @param name          The name of the field to be added.
           @param fieldType     The type of field to be entered.
           @param value         The optional initial value for the field when the dialog is displayed.
           @param minNumber     The optional min value if the fieldType = NUMBER_INPUT_FIELD_TYPE.
           @param maxNumber     The optional max value if the fieldType = NUMBER_INPUT_FIELD_TYPE.
           """
        if name and len(name) > 0:
            if fieldType in YesNoDialog.VALID_FIELD_TYPE_LIST:
                self._inputFieldDict[name] = {YesNoDialog.FIELD_TYPE_KEY:     fieldType,
                                              YesNoDialog.VALUE_KEY:          value,
                                              YesNoDialog.MIN_NUMBER_KEY:     minNumber,
                                              YesNoDialog.MAX_NUMBER_KEY:     maxNumber,
                                              YesNoDialog.OPTIONS_KEY:        options}

            else:
                raise Exception(f"YesNoDialog.addField() {fieldType} is an invalid field type.")

        else:
            raise Exception("YesNoDialog.addField() name not set.")
        
    def _init(self):
        """@brief Init the dialog."""
        with ui.dialog() as self._dialog, ui.card():
            ui.label(self._prompt)
            for fieldName in self._inputFieldDict:
                fieldType = self._inputFieldDict[fieldName][YesNoDialog.FIELD_TYPE_KEY]
                if fieldType == YesNoDialog.TEXT_INPUT_FIELD_TYPE:
                    widget = ui.input(label=fieldName)

                elif fieldType == YesNoDialog.NUMBER_INPUT_FIELD_TYPE:
                    value = self._inputFieldDict[fieldName][YesNoDialog.VALUE_KEY]
                    min = self._inputFieldDict[fieldName][YesNoDialog.MIN_NUMBER_KEY]
                    max = self._inputFieldDict[fieldName][YesNoDialog.MAX_NUMBER_KEY]
                    widget = ui.number(label=fieldName, 
                                        value=value, 
                                        min=min, 
                                        max=max)
                    
                elif fieldType == YesNoDialog.SWITCH_INPUT_FIELD_TYPE:
                    widget = ui.switch(fieldName)

                elif fieldType == YesNoDialog.DROPDOWN_INPUT_FIELD:
                    #ui.label(fieldName)
                    options = self._inputFieldDict[fieldName][YesNoDialog.OPTIONS_KEY]
                    if options:
                        widget = ui.select(options)
                        widget.tooltip(fieldName)
                    else:
                        raise Exception("BUG: DROPDOWN_INPUT_FIELD defined without defining the options.")
                    
                elif fieldType == YesNoDialog.COLOR_INPUT_FIELD:
                    widget = ui.color_input(label=fieldName)

                elif fieldType == YesNoDialog.DATE_INPUT_FIELD:
                    widget = ui.date()
                    widget.tooltip(fieldName)

                elif fieldType == YesNoDialog.TIME_INPUT_FIELD:
                    widget = ui.time()
                    widget.tooltip(fieldName)

                elif fieldType == YesNoDialog.KNOB_INPUT_FIELD:
                    widget = ui.knob(show_value=True)
                    widget.tooltip(fieldName)

                # Save a ref to the widet in the field dict
                self._inputFieldDict[fieldName][YesNoDialog.WIDGET_KEY] = widget

                # If we have an initial value then set it
                value = self._inputFieldDict[fieldName][YesNoDialog.VALUE_KEY]
                if value:
                    widget.value = value

            with ui.row():
                ui.button(self._successButtonText, on_click=self._internalSuccessMethod)
                ui.button(self._failureButtonText,  on_click=self._internalFailureMethod)

    def setPrompt(self, prompt):
        """@brief Set the user prompt.
           @param prompt The user prompt."""
        self._prompt = prompt

    def setSuccessMethod(self, successMethod):
        """@brief Set the text of the success button.
           @param successMethod The method called when the user selects the success button."""
        self._successMethod = successMethod
        
    def setFailureMethod(self, failureMethod):
        """@brief Set the text of the success button.
           @param failureMethod The method called when the user selects the failure button."""
        self._failureMethod = failureMethod

    def setSuccessButtonLabel(self, label):
        """@brief Set the text of the success button.
           @param label The success button text."""
        self._successButtonText = label

    def setFailureButtonLabel(self, label):
        """@brief Set the text of the failure button.
           @param label The failure button text."""
        self._failureButtonText = label
        
    def show(self):
        """@brief Allow the user to select yes/no, ok/cancel etc in response to a question."""
        self._init()
        self._dialog.open()

    def getValue(self, fieldName):
        """@brief Get the value entered by the user.
           @param fieldName The name of the field entered."""
        value = None
        widget = self._inputFieldDict[fieldName][YesNoDialog.WIDGET_KEY]
        if hasattr(widget, 'value'):
            value = widget.value

        elif isinstance(widget, ui.upload):
            value = self._selectedFile

        return value

    def _internalSuccessMethod(self):
        """@brief Called when the user selects the success button."""
        self.close()
        # Save the entered values for all fields
        for fieldName in self._inputFieldDict:
            widget = self._inputFieldDict[fieldName][YesNoDialog.WIDGET_KEY]
            if hasattr(widget, 'value'):
                self._inputFieldDict[fieldName][YesNoDialog.VALUE_KEY] = self._inputFieldDict[fieldName][YesNoDialog.WIDGET_KEY].value
        # If defined call the method 
        if self._successMethod:
            self._successMethod()

    def _internalFailureMethod(self):
        """@brief Called when the user selects the failure button."""
        self.close()
        if self._failureMethod:
            self._failureMethod()

    def close(self):
        """@brief Close the boolean dialog."""
        self._dialog.close()

