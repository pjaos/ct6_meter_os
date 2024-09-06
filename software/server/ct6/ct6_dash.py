#!/usr/bin/env python3

import os
import argparse
import threading
import re
import calendar
import itertools
import inspect

from queue import Queue
from time import time, sleep
from datetime import datetime, timedelta, date

from bokeh.layouts import column, row
from bokeh.models import Div, Button, HoverTool, CustomJS
from bokeh.models import TabPanel, Tabs
from bokeh.models.css import Styles
from bokeh.plotting import figure, ColumnDataSource
from bokeh.models import DatetimePicker
from bokeh.palettes import Category20_20
from bokeh.models import RadioButtonGroup, DataTable, \
                         TableColumn, InlineStyleSheet, Tooltip, HelpButton
from bokeh.models.widgets import HTMLTemplateFormatter

from p3lib.helper import logTraceBack
from p3lib.uio import UIO
from p3lib.bokeh_gui import MultiAppServer

from lib.config import ConfigBase
from lib.db_handler import DBHandler
from lib.base_constants import BaseConstants

from ct6.ct6_dash_mgr import CRED_JSON_FILE

class CT6DashConfig(ConfigBase):
    DEFAULT_CONFIG_FILENAME = "ct6Dash.cfg"
    DEFAULT_CONFIG = {
        ConfigBase.DB_HOST:                     "127.0.0.1",
        ConfigBase.DB_PORT:                     3306,
        ConfigBase.DB_USERNAME:                 "",
        ConfigBase.DB_PASSWORD:                 "",
        ConfigBase.LOCAL_GUI_SERVER_ADDRESS:    "",
        ConfigBase.LOCAL_GUI_SERVER_PORT:       10000,
        ConfigBase.SERVER_LOGIN:                False,
        ConfigBase.SERVER_ACCESS_LOG_FILE:      ""
    }

class GUI(MultiAppServer):
    """@brief Responsible for providing the GUI dashboard for viewing data from CT6 devices.
              This is provided over a Web interface."""

    PAGE_TITLE                  = "CT6 Dashboard"
    BOKEH_ALLOW_WS_ORIGIN       = 'BOKEH_ALLOW_WS_ORIGIN'

    DB_META_TABLE_NAME          = BaseConstants.CT6_META_TABLE_NAME

    CT1_NAME                    = BaseConstants.CT1_NAME
    CT2_NAME                    = BaseConstants.CT2_NAME
    CT3_NAME                    = BaseConstants.CT3_NAME
    CT4_NAME                    = BaseConstants.CT4_NAME
    CT5_NAME                    = BaseConstants.CT5_NAME
    CT6_NAME                    = BaseConstants.CT6_NAME

    UPDATE_SECONDS              = "UPDATE_SECONDS"
    STATUS_MESSAGE              = "STATUS"
    STATUS_LINE_INDEX           = "STATUS_LINE_INDEX"
    CMD_COMPLETE                = "CMD_COMPLETE"
    ENABLE_ACTION_BUTTONS       = "ENABLE_ACTION_BUTTONS"
    SUMMARY_ROW                 = "SUMMARY_ROW"

    X_AXIS_NAME                 = "date"
    DEFAULT_YAXIS_NAME          = "kW"
    AC_VOLTS_YAXIS_NAME         = "Volts"
    AC_FREQ_YAXIS_NAME          = "Hertz"
    TEMP_YAXIS_NAME             = "°C"
    RSSI_YAXIS_NAME             = "dBm"

    MAX_RESOLUTION              = 0
    MINUTE_RESOLUTION           = 1
    HOUR_RESOLUTION             = 2
    DAY_RESOLUTION              = 3

    TOOLS                       = "crosshair,pan,wheel_zoom,zoom_in,zoom_out,box_zoom,undo,redo,reset,tap,save,box_select,poly_select,lasso_select"
    TOOLBAR_LOCATION            = "below"

    PLOT_TYPE_POWER_ACTIVE      = 1 # Show the active power plot.
    PLOT_TYPE_POWER_REACTIVE    = 2 # Show the reactive power plot.
    PLOT_TYPE_POWER_APPARENT    = 3 # Show the apparent power plot.
    PLOT_TYPE_POWER_FACTOR      = 4 # # Show the power factor plot.
    PLOT_TYPE_AC_VOLTS          = 5 # Show the AC voltage plot.
    PLOT_TYPE_AC_FREQ           = 6 # Show the AC frequency
    PLOT_TYPE_TEMP              = 7 # Show the unit temperature
    PLOT_TYPE_RSSI              = 8 # Show the WiFi signal strength

    BUTTON_TYPE                 = "success"

    SENSOR_COUNT                = 6

    LOCAL_PATH                  = os.path.dirname(os.path.abspath(__file__))

    @staticmethod
    def GetLoginPage():
        """@brief Get the abs path to the login.html file.
           @return The full path to the login.html file."""
        loginHtmlFile = os.path.join(GUI.LOCAL_PATH, "assets/login.html")
        if not os.path.isfile(loginHtmlFile):
            loginHtmlFile = os.path.join(GUI.LOCAL_PATH, "../assets/login.html")
            if not os.path.isfile(loginHtmlFile):
                raise Exception(f'{loginHtmlFile} file not found.')
        return loginHtmlFile

    def __init__(self, uio, options, config, loginCredentialsFile):
        """@brief Constructor.
           @param uio A UIO instance responsible for stdout/stdin input output.
           @param options The command line argparse options instance.
           @param config The dash app config.
           @param loginCredentialsFile A file containing the login credentials or None if no server authentication is required."""
        super().__init__(address=config.getAttr(CT6DashConfig.LOCAL_GUI_SERVER_ADDRESS),
                         bokehPort=config.getAttr(CT6DashConfig.LOCAL_GUI_SERVER_PORT),
                         credentialsJsonFile=loginCredentialsFile,
                         loginHTMLFile=GUI.GetLoginPage(),
                         accessLogFile=config.getAttr(CT6DashConfig.SERVER_ACCESS_LOG_FILE) )
        self._uio = uio
        self._options = options
        self._config = config

        self._doc = None
        self._server = None
        self._tabList = None
        self._dbHandler = None
        self._dbIF = None
        self._startUpdateTime = None

        # this queue is used to send commands from the GUI thread and read responses received from outside the GUI thread.
        self._commsQueue = Queue()

        self._ct4DBDict = {}

        self._startupShow = True

        self._plotPanel = None
        self._updatePlotType = GUI.PLOT_TYPE_POWER_ACTIVE
        self._cmdButtonList = []

    def getAppMethodDict(self):
        """@return The server app method dict."""
        appMethodDict = {}
        appMethodDict['/']=self._mainApp
        return appMethodDict

    def _connectToDB(self):
        """@brief Connect to a database."""
        if self._dbHandler:
            self._dbHandler.disconnect()
            self._dbHandler = None
        self._dbHandler = CTDBClient(self._uio, self._config)
        self._dbHandler.connect()
        self._dbIF = self._dbHandler.getDatabaseIF()

    def _getMetaDict(self):
        """@brief Get the Meta data from the database.
           @return A dict that contains
                   key = The name of the database
                   value = A dict with the contents of the QUAD_CT_META table.
                   This contains
                   HW_ASSY  The hardware assembly number ASYXXXX_YYY.YY_ZZZZZZ
                   CT1_NAME The name of the CT1 sensor
                   CT2_NAME The name of the CT2 sensor
                   CT3_NAME The name of the CT3 sensor
                   CT4_NAME The name of the CT1 sensor
                   CT5_NAME The name of the CT2 sensor
                   CT6_NAME The name of the CT3 sensor"""
        dbDict = {}
        sql = 'SHOW DATABASES;'
        recordTuple = self._dbIF.executeSQL(sql)
        for record in recordTuple:
            if 'Database' in record:
                dbName = record['Database']
                self._dbIF.executeSQL("USE {};".format(dbName))
                cmd = "SHOW TABLES LIKE '{}';".format(GUI.DB_META_TABLE_NAME)
                responseTuple = self._dbIF.executeSQL(cmd)
                if len(responseTuple) > 0:
                    cmd = "SHOW TABLES LIKE '{}';".format(BaseConstants.MAX_RES_DB_DATA_TABLE_NAME)
                    responseTuple = self._dbIF.executeSQL(cmd)
                    if len(responseTuple) > 0:
                        cmd = "select * from {} limit 1;".format(GUI.DB_META_TABLE_NAME)
                        responseTuple = self._dbIF.executeSQL(cmd)
                        if responseTuple and len(responseTuple) > 0:
                            # The key in this dict will be the database name.
                            # The value is the contents of the first row in the table.
                            dbDict[dbName]=responseTuple[0]
        return dbDict

    def _updateEnabledState(self, newState, field, enabledText):
        """@brief Update the enabled/disabled state of the field
                  based upon its state.
           @param newState The new state as text.
           @param field The Widget to be updated.
           @param enabledText The value of newState when the field should be enabled."""
        if newState == enabledText:
            field.disabled = False
        else:
            field.disabled = True

    def _getDictValue(self, aDict, aKey, retInt=False):
        """@brief Get a value from a dict.
           @param aDict The idtc to read the value from.
           @param aKey The key to read from the dict.
           @param retInt If True then return an integer.
           @return The value read from the dict or None if not found."""
        retValue=None
        if aKey in aDict:
            retValue = aDict[aKey]
            if retInt:
                retValue=int(retValue)
        return retValue

    def _updateField(self, inputField, value):
        """@brief Update the input field if the value has changed.
           @param inputField The input field instance.
           @param value The value to be displayed in this input field."""
        if inputField.value != value:
            inputField.value = value

    def _refreshDevConfig(self):
        """@brief Refresh the displayed configuration."""
        assy = self._selectDeviceSelect.value
        if assy and len(assy) > 0:
            devDict = self._deviceDict[assy]
            self._updateSelectedDevice(devDict)

    def _todayButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        today = datetime.today()
        self._startDateTimePicker.value = today.date()
        # Set resolution to mins to set a good trade off between plot time and resolution
        self._resRadioButtonGroup.active = 1
        endDateTime = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        self._stopDateTimePicker.value = endDateTime
        # Kick of a plot attempt to save pressing the power button afterwards
        self._plotSensorData(True)

    def _yesterdayButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        today = datetime.today()
        yesterday = today - timedelta(days = 1)
        self._startDateTimePicker.value = yesterday.date()
        # Set resolution to mins to set a good trade off between plot time and resolution
        self._resRadioButtonGroup.active = 1
        endDateTime = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        self._stopDateTimePicker.value = endDateTime
       # Kick of a plot attempt to save pressing the power button afterwards
        self._plotSensorData(True)

    def _thisWeekButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        today = datetime.today()
        dayOfWeek = today.weekday()
        startOfWeek = today - timedelta(days = dayOfWeek)
        today = datetime.today()
        self._startDateTimePicker.value = startOfWeek.date()
        # Set resolution to mins to set a good trade off between plot time and resolution
        self._resRadioButtonGroup.active = 1
        endDateTime = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        self._stopDateTimePicker.value = endDateTime
        # Kick of a plot attempt to save pressing the power button afterwards
        self._plotSensorData(True)

    def _lastWeekButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        today = datetime.today()
        dayOfWeek = today.weekday()
        endOfLastWeek = today - timedelta(days = dayOfWeek+1)
        startOfLastWeek = endOfLastWeek - timedelta(days = 6)
        self._startDateTimePicker.value = startOfLastWeek.date()
        # Set resolution to mins to set a good trade off between plot time and resolution
        self._resRadioButtonGroup.active = 1
        endDateTime = endOfLastWeek.replace(hour=23, minute=59, second=59, microsecond=999999)
        self._stopDateTimePicker.value = endDateTime
        # Kick of a plot attempt to save pressing the power button afterwards
        self._plotSensorData(True)

    def _thisMonthButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        today = datetime.today()
        dayOfMonth = today.day
        firstDayOfMonth = today - timedelta(days = dayOfMonth-1)
        self._startDateTimePicker.value = firstDayOfMonth.date()
        # Set resolution to hours to set a good trade off between plot time and resolution
        self._resRadioButtonGroup.active = 2
        endDateTime = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        self._stopDateTimePicker.value = endDateTime
        # Kick of a plot attempt to save pressing the power button afterwards
        self._plotSensorData(True)

    def _lastMonthButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        today = datetime.today()
        dayOfMonth = today.day
        lastDayOfLastMonth = today - timedelta(days = dayOfMonth)
        daysInLastMonth = calendar.monthrange(lastDayOfLastMonth.year, lastDayOfLastMonth.month)[1]
        firstDayOfLastMonth = lastDayOfLastMonth - timedelta(days = daysInLastMonth-1)
        self._startDateTimePicker.value = firstDayOfLastMonth.date()
        # Set resolution to hours to set a good trade off between plot time and resolution
        self._resRadioButtonGroup.active = 2   
        endDateTime = lastDayOfLastMonth.replace(hour=23, minute=59, second=59, microsecond=999999)
        self._stopDateTimePicker.value = endDateTime
        # Kick of a plot attempt to save pressing the power button afterwards
        self._plotSensorData(True)

    def _thisYearButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        today = datetime.today()
        self._startDateTimePicker.value = datetime(today.year, 1, 1, 0, 0 , 0, 0)
        self._stopDateTimePicker.value  = datetime(today.year, 12, 31, 23,59, 39, 999999)
        # Set resolution to hours to set a good trade off between plot time and resolution
        self._resRadioButtonGroup.active = 2
        # Kick of a plot attempt to save pressing the power button afterwards
        self._plotSensorData(True)

    def _lastYearButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        today = date.today()
        self._startDateTimePicker.value = datetime(today.year-1, 1, 1, 0, 0 , 0, 0)
        self._stopDateTimePicker.value  = datetime(today.year-1, 12, 31, 23,59, 39, 999999)
        # Set resolution to hours to set a good trade off between plot time and resolution
        self._resRadioButtonGroup.active = 2
        # Kick of a plot attempt to save pressing the power button afterwards
        self._plotSensorData(True)

    def _powerButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        self._plotSensorData(True)

    def _powerFactorButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        self._plotSensorData(False)

    def _plotSensorData(self, plotPower):
        if plotPower:
            if self._pwrTypeRadioButtonGroup.active == 0:
                self._updatePlotType = GUI.PLOT_TYPE_POWER_ACTIVE

            elif self._pwrTypeRadioButtonGroup.active == 1:
                self._updatePlotType = GUI.PLOT_TYPE_POWER_REACTIVE

            elif self._pwrTypeRadioButtonGroup.active == 2:
                self._updatePlotType = GUI.PLOT_TYPE_POWER_APPARENT

        else:
            self._updatePlotType = GUI.PLOT_TYPE_POWER_FACTOR

        self._startUpdateTime = time()
        self._enableReadDBButtons(False)
        self._clearSummaryTable()
        self._showStatus(0, "Reading Data...")
        # Run thread to recover the data from the database.
        threading.Thread( target=self._readDataBase, args=(self._startDateTimePicker.value,self._stopDateTimePicker.value, self._resRadioButtonGroup.active)).start()

    def _enableReadDBButtons(self, enabled):
        """@brief Enable/Disable all buttons that allow the user to read from the database.
           @param enabled If True the buttons are enabled."""
        # Set the button state in a callback or a locking error will ensue
        if enabled:
            self._doc.add_next_tick_callback(self._setButtonsActive)
        else:
            self._doc.add_next_tick_callback(self._setButtonsDisabled)

    def _enableButtons(self, enabled):
        """@brief Enable/disable buttons.
           @param enabled True if buttons are to be enabled."""
        for button in self._cmdButtonList:
            button.disabled = not enabled
            
    def _setButtonsActive(self):
        self._enableButtons(True)

    def _setButtonsDisabled(self):
        self._enableButtons(False)
    
    def _getActionButtonPanel(self):
        self._powerButton = Button(label="Power", button_type=GUI.BUTTON_TYPE)
        self._powerButton.on_click(self._powerButtonHandler)
        
        self._powerFactorButton = Button(label="Power Factor", button_type=GUI.BUTTON_TYPE)
        self._powerFactorButton.on_click(self._powerFactorButtonHandler)

        self._voltageButton = Button(label="AC Voltage", button_type=GUI.BUTTON_TYPE)
        self._voltageButton.on_click(self._showACVolts)

        self._freqButton = Button(label="AC Frequency", button_type=GUI.BUTTON_TYPE)
        self._freqButton.on_click(self._showACFreq)

        row1 = row(children=[self._powerButton, self._powerFactorButton, self._voltageButton])

        self._tempButton = Button(label="Temperature", button_type=GUI.BUTTON_TYPE)
        self._tempButton.on_click(self._showTemp)

        self._rssiButton = Button(label="WiFi RSSI", button_type=GUI.BUTTON_TYPE)
        self._rssiButton.on_click(self._showRSSI)

        row2 = row(children=[self._freqButton, self._tempButton, self._rssiButton])

        return column(children=[row1, row2])

    def _showACVolts(self):
        """@brief Show the AC volts plot."""
        self._updatePlotType = GUI.PLOT_TYPE_AC_VOLTS
        self._startUpdateTime = time()
        self._clearSummaryTable()
        self._enableReadDBButtons(False)
        self._showStatus(0, "Reading Data...")
        # Run thread to recover the data from the database.
        threading.Thread( target=self._readDataBase, args=(self._startDateTimePicker.value,self._stopDateTimePicker.value, self._resRadioButtonGroup.active)).start()

    def _showACFreq(self):
        """@brief Show the AC freq plot."""
        self._updatePlotType = GUI.PLOT_TYPE_AC_FREQ
        self._startUpdateTime = time()
        self._clearSummaryTable()
        self._enableReadDBButtons(False)
        self._showStatus(0, "Reading Data...")
        # Run thread to recover the data from the database.
        threading.Thread( target=self._readDataBase, args=(self._startDateTimePicker.value,self._stopDateTimePicker.value, self._resRadioButtonGroup.active)).start()

    def _showTemp(self):
        """@brief Show unit temperature plot."""
        self._updatePlotType = GUI.PLOT_TYPE_TEMP
        self._startUpdateTime = time()
        self._clearSummaryTable()
        self._enableReadDBButtons(False)
        self._showStatus(0, "Reading Data...")
        # Run thread to recover the data from the database.
        threading.Thread( target=self._readDataBase, args=(self._startDateTimePicker.value,self._stopDateTimePicker.value, self._resRadioButtonGroup.active)).start()

    def _showRSSI(self):
        """@brief Show the WiFi RSSI plot."""
        self._updatePlotType = GUI.PLOT_TYPE_RSSI
        self._startUpdateTime = time()
        self._clearSummaryTable()
        self._enableReadDBButtons(False)
        self._showStatus(0, "Reading Data...")
        # Run thread to recover the data from the database.
        threading.Thread( target=self._readDataBase, args=(self._startDateTimePicker.value,self._stopDateTimePicker.value, self._resRadioButtonGroup.active)).start()

    def _getControlPanel(self, sensorNames):
        """@brief Get an instance of the button panel.
           @param sensorNames A list of the names of the sensors.
           @return an instance of the button panel."""
        self._todayButton = Button(label="Today", button_type=GUI.BUTTON_TYPE)
        self._todayButton.on_click(self._todayButtonHandler)

        self._yesterdayButton = Button(label="Yesterday", button_type=GUI.BUTTON_TYPE)
        self._yesterdayButton.on_click(self._yesterdayButtonHandler)

        self._thisWeekButton = Button(label="This week", button_type=GUI.BUTTON_TYPE)
        self._thisWeekButton.on_click(self._thisWeekButtonHandler)

        self._lastWeekButton = Button(label="Last week", button_type=GUI.BUTTON_TYPE)
        self._lastWeekButton.on_click(self._lastWeekButtonHandler)

        self._thisMonthButton = Button(label="This Month", button_type=GUI.BUTTON_TYPE)
        self._thisMonthButton.on_click(self._thisMonthButtonHandler)

        self._lastMonthButton = Button(label="Last Month", button_type=GUI.BUTTON_TYPE)
        self._lastMonthButton.on_click(self._lastMonthButtonHandler)

        self._thisYearButton = Button(label="This Year", button_type=GUI.BUTTON_TYPE)
        self._thisYearButton.on_click(self._thisYearButtonHandler)

        self._lastYearButton = Button(label="Last Year", button_type=GUI.BUTTON_TYPE)
        self._lastYearButton.on_click(self._lastYearButtonHandler)
        
        addStartDaybutton = Button(label = ">")
        addStartDaybutton.on_click(self._addStartDayCallBack)
        
        subtractStartDaybutton = Button(label = "<")
        subtractStartDaybutton.on_click(self._subtractStartDayCallBack)
                 
        addStopDaybutton = Button(label = ">") 
        addStopDaybutton.on_click(self._addStopDayCallBack)
        
        subtractStopDaybutton = Button(label = "<")
        subtractStopDaybutton.on_click(self._subtractStopDayCallBack)
        
        self._startDateTimePicker = DatetimePicker(title='Start (year-month-day hour:min)')
        self._stopDateTimePicker = DatetimePicker(title='Stop (year-month-day hour:min)')

        # Div to move the table down to the top edge of the plot.
        div1 = Div(height=20)
        leftButtonPanel = column(children=[self._todayButton, self._thisWeekButton, self._thisMonthButton, self._thisYearButton])
        rightButtonPanel = column(children=[self._yesterdayButton, self._lastWeekButton, self._lastMonthButton, self._lastYearButton])
        buttonPanel0 = row(children=[leftButtonPanel, rightButtonPanel])
        buttonPanel1 = row(children=[subtractStartDaybutton, self._startDateTimePicker, addStartDaybutton])
        buttonPanel2 = row(children=[subtractStopDaybutton, self._stopDateTimePicker, addStopDaybutton])
        self._line0StatusDiv = Div()
        self._line1StatusDiv = Div()
        self._line2StatusDiv = Div()
        self._line3StatusDiv = Div()
        self._line4StatusDiv = Div()
        self._line5StatusDiv = Div()

        summaryTable = self._getSummaryTable()

        resLabels = ["Sec", "Min", "Hour", "Day"]
        self._resRadioButtonGroup = RadioButtonGroup(labels=resLabels, active=1)
        buttonPanel3 = row(children=[self._resRadioButtonGroup])

        pwrTypeLabels = ["Active", "Reactive", "Apparent"]
        self._pwrTypeRadioButtonGroup = RadioButtonGroup(labels=pwrTypeLabels, active=0)
        buttonPanel4 = row(children=[self._pwrTypeRadioButtonGroup])

        pwrPolarityLabels = ["Import is positive", "Import is negative"]
        if self._options.positive:
            defaultpwrPolarity = 0
        else:
            defaultpwrPolarity = 1
        self._pwrPolarityRadioButtonGroup = RadioButtonGroup(labels=pwrPolarityLabels, active=defaultpwrPolarity)
        buttonPanel5 = row(children=[self._pwrPolarityRadioButtonGroup])

        buttonPanel6 = column(children=[buttonPanel3,
                                        buttonPanel4,
                                        buttonPanel5])

        resLabelButton = HelpButton(label="", button_type="default", disabled=True, tooltip = Tooltip(content="Select the plot resolution.", position="left"))
        pwrTypeLabelButton = HelpButton(label="", button_type="default", disabled=True, tooltip = Tooltip(content="Select the power type. Active = Power normally charged by electricity supplier.", position="left"))
        pwrPolarityLabelButton = HelpButton(label="", button_type="default", disabled=True, tooltip = Tooltip(content="Select imported electrical power to be plotted as negative or positive values.", position="left"))

        labelPanel = column(children=[resLabelButton,
                                      pwrTypeLabelButton,
                                      pwrPolarityLabelButton])

        optionsButtonPanel = row(children=[labelPanel, buttonPanel6])

        actionButtonPanel = self._getActionButtonPanel()

        buttonPanel = column(children=[div1,
                                       summaryTable,
                                       buttonPanel0,
                                       buttonPanel1,
                                       buttonPanel2,
                                       optionsButtonPanel,
                                       actionButtonPanel,
                                       self._line0StatusDiv,
                                       self._line1StatusDiv,
                                       self._line2StatusDiv,
                                       self._line3StatusDiv,
                                       self._line4StatusDiv,
                                       self._line5StatusDiv])
        
        self._cmdButtonList = ( self._powerButton,
                                self._powerFactorButton,
                                self._voltageButton,
                                self._freqButton,
                                self._tempButton,
                                self._rssiButton,
                                self._todayButton,
                                self._yesterdayButton,
                                self._thisWeekButton,
                                self._lastWeekButton,
                                self._thisMonthButton,
                                self._lastMonthButton,
                                self._thisYearButton,
                                self._lastYearButton)

        return buttonPanel

    def _addStartDayCallBack(self, event):
        """@brief Called when the associated button is clicked to add a day to the start time.
           @param event The event that triggered the method call."""
        dateTimeObj=datetime.fromtimestamp(self._startDateTimePicker.value/1000)
        self._startDateTimePicker.value = dateTimeObj + timedelta(days=1)
        
    def _subtractStartDayCallBack(self, event):
        """@brief Called when the associated button is clicked to subtract a day to the start time.
           @param event The event that triggered the method call."""
        dateTimeObj=datetime.fromtimestamp(self._startDateTimePicker.value/1000)
        self._startDateTimePicker.value = dateTimeObj - timedelta(days=1)
        
    def _addStopDayCallBack(self, event):
        """@brief Called when the associated button is clicked to add a day to the stop time.
           @param event The event that triggered the method call."""
        dateTimeObj=datetime.fromtimestamp(self._stopDateTimePicker.value/1000)
        self._stopDateTimePicker.value = dateTimeObj + timedelta(days=1)

    def _subtractStopDayCallBack(self, event):
        """@brief Called when the associated button is clicked to subtract a day to the stop time.
           @param event The event that triggered the method call."""
        dateTimeObj=datetime.fromtimestamp(self._stopDateTimePicker.value/1000)
        self._stopDateTimePicker.value = dateTimeObj - timedelta(days=1)

    def _getSelectedDataBase(self):
        """@brief The user can select the tab on the GUI. This tab is the name of the database for the CT6
                  unit of interest.
           @return The name of the selected database of None if no database found."""
        if len(self._tabList) > 0 and \
           self._allTabsPanel.active >= 0 and \
           self._allTabsPanel.active < len(self._tabList):
            return self._tabList[self._allTabsPanel.active].title

        return None

    def _getSummaryTable(self):
        """@brief Get a DataTable instance of the summary table.
           @param sensorNames A list of  the names of the sensors.
           @return A DataTable instance."""
        summaryTable = None
        self._baseV = 0.0
        # We need separate row instances for each parameter to ensure first update works on first read.
        self._emptySensorColumn1 = ["" for i in range(0, GUI.SENSOR_COUNT)]
        self._emptySensorColumn2 = ["" for i in range(0, GUI.SENSOR_COUNT)]
        self._emptySensorColumn3 = ["" for i in range(0, GUI.SENSOR_COUNT)]
        self._emptySensorColumn4 = ["" for i in range(0, GUI.SENSOR_COUNT)]
        self._data = dict(
                sensor      =   self._emptySensorColumn1, # At this point we don't know the sensor names as multiple databases from multiple CT6 devices may be found
                total       =   self._emptySensorColumn2,
                positive    =   self._emptySensorColumn3,
                negative    =   self._emptySensorColumn4,
            )
        self._summaryTableSource = ColumnDataSource(self._data)

        greenColTemplate="""<div style="background:green; color: black"><%= value %></div>"""
        greenFormatter =  HTMLTemplateFormatter(template=greenColTemplate)
        redColTemplate="""<div style="background:orange; color: white"><%= value %></div>"""
        redFormatter =  HTMLTemplateFormatter(template=redColTemplate)

        columns = [
                TableColumn(field="sensor", title="Sensor"),
                TableColumn(field="total", title="kWh"),
                TableColumn(field="positive", title="kWh",formatter=greenFormatter),
                TableColumn(field="negative", title="kWh",formatter=redFormatter),
            ]
        # Width 300 sets the width of the control panel on the left
        # 300 is wide enough to display the date picker when either
        # the start or stop dates are selected.
        # 180 is tall enough to display all 6 sensor names if configured.
        summaryTable = DataTable(source=self._summaryTableSource,
                                 columns=columns,
                                 index_position = None,
                                 height=180,
                                 width=340,
                                 )

        table_style = InlineStyleSheet(css="""
            .slick-header-columns {
                background-color: #17648D !important;
                font-weight: bold;
                font-size: 12pt;
                color: #FFFFFF;
                text-align: right;
            }
            .slick-row {
                font-size:12pt;
                text-align: left;
            }
        """)
        summaryTable.stylesheets = [table_style]


        return summaryTable


    def _clearSummaryTable(self):
        """@brief Clear the sensor summary table of all data except the names of the sensors."""
        rowCount = GUI.SENSOR_COUNT
        emptySensorColumn = ["" for i in range(0, rowCount)]
        data = dict(sensor=[(slice(rowCount),emptySensorColumn)],
                    total=[(slice(rowCount),emptySensorColumn)],
                    positive=[(slice(rowCount),emptySensorColumn)],
                    negative=[(slice(rowCount),emptySensorColumn)]
                    )
        self._summaryTableSource.patch(data)

    def _updateSummaryTable(self, rxDict):
        """@brief Clear the sensor summary table of all data except the names of the sensors.
           @brief rxDict The dict received from the _calcKWH() method"""
        invertKw = self._invertKW()
        if GUI.SUMMARY_ROW in rxDict:
            row = rxDict[GUI.SUMMARY_ROW]
            if len(row) == 5:
                rowIndex = row[0]-1 # Row index is one less than the CT number               
                if invertKw:
                    data = dict(sensor=[(rowIndex,f"{row[1]}")],
                                total=[(rowIndex,f"{row[2]:.2f}")],
                                negative=[(rowIndex,f"{row[3]:.2f}")],
                                positive=[(rowIndex,f"{row[4]:.2f}")]
                                )
                else:
                    data = dict(sensor=[(rowIndex,f"{row[1]}")],
                                total=[(rowIndex,f"{row[2]:.2f}")],
                                positive=[(rowIndex,f"{row[3]:.2f}")],
                                negative=[(rowIndex,f"{row[4]:.2f}")]
                                )
                self._summaryTableSource.patch(data)

    def _showStatus(self, statusID, line):
        """@brief Show Status messages
           @param statusID The status line index.
           @param line The message text."""
        if statusID == 0:
            self._line0StatusDiv.text = line
        if statusID == 1:
            self._line1StatusDiv.text = line
        if statusID == 2:
            self._line2StatusDiv.text = line
        if statusID == 3:
            self._line3StatusDiv.text = line
        if statusID == 4:
            self._line4StatusDiv.text = line
        if statusID == 5:
            self._line5StatusDiv.text = line

    def _clearStatusLines(self):
        """@brief Clear all status line text."""
        self._line0StatusDiv.text = ""
        self._line1StatusDiv.text = ""
        self._line2StatusDiv.text = ""
        self._line3StatusDiv.text = ""
        self._line4StatusDiv.text = ""
        self._line5StatusDiv.text = ""

    def _mainApp(self, doc):
        """@brief create the GUI page.
           @param doc The document to add the plot to."""
        self._startupShow = True

        self._connectToDB()

        self._metaDataDict = self._getMetaDict()

        # Clear the queue once we have the lock to ensure it's
        # not being read inside the _update() method.
        while not self._commsQueue.empty():
            self._commsQueue.get(block=False)

        doc.clear()
        self._doc = doc
        # Set the Web page title
        self._doc.title = GUI.PAGE_TITLE
        self._tabList = []
        # 1 rem generally = 16px
        # Using rem rather than px can help ensure consistency of font size and spacing throughout your UI.
        fontSize='1rem'
        theme = "dark_minimal"
        self._plotPanels = []

        self._dbTableList = []
        self._cdsDict = {}
        for dbName in self._metaDataDict:
            devInfoDict = self._metaDataDict[dbName]

            colors = itertools.cycle(Category20_20)
            
            # One panel multiple plot traces
            # By default select the zoom tool
            self._plotPanel = figure(title="",
                               sizing_mode="stretch_both",
                               tools=GUI.TOOLS,
                               toolbar_location="below",
                               x_axis_type='datetime',
                               active_drag="box_zoom",
                               y_axis_label="kW")
            self._plotPanels.append(self._plotPanel)
            # PJA: This simply reverses the values on the plot. Not used as when inverting the data we also
            #      want the kWh table to be updated.
#            self._plotPanel.y_range.flipped = True
            
            hover = HoverTool()
            dateS =  '@{}'.format(GUI.X_AXIS_NAME)
            dateS += '{%F}'
            hover.tooltips = [("","$name"),("kW", "$y{1.1f}"), ('date', "$x{%Y-%m-%d}"), ('time', "$x{%H:%M:%S}"), ("sample", "$index")]
            hover.formatters = {'$x': 'datetime'}
            self._plotPanel.add_tools(hover)

            self._dbTableList.append( (dbName,0) )

            plotNames = (devInfoDict[GUI.CT1_NAME],
                         devInfoDict[GUI.CT2_NAME],
                         devInfoDict[GUI.CT3_NAME],
                         devInfoDict[GUI.CT4_NAME],
                         devInfoDict[GUI.CT5_NAME],
                         devInfoDict[GUI.CT6_NAME])
            for i in range(0,6):
                if plotNames[i] and len(plotNames[i]) > 0:

                    cds = ColumnDataSource({GUI.X_AXIS_NAME: [],
                                            GUI.DEFAULT_YAXIS_NAME: []})
                    self._cdsDict[dbName + plotNames[i]] = cds
                    self._plotPanel.line(GUI.X_AXIS_NAME, GUI.DEFAULT_YAXIS_NAME, source=cds, name=plotNames[i], legend_label=plotNames[i], line_color=next(colors), line_width=3)
                    self._plotPanel.legend.click_policy="hide"
            self._plotPanel.legend.location = 'bottom_left'

            # The dBname = the device name = the tab name
            self._tabList.append( TabPanel(child=self._plotPanel,  title=dbName) )
            controlPanel = self._getControlPanel(plotNames)

        tabTextSizeSS = [{'.bk-tab': Styles(font_size='{}'.format(fontSize))}, {'.bk-tab': Styles(background='{}'.format('grey'))}]
        self._allTabsPanel = Tabs(tabs=self._tabList, sizing_mode="stretch_both", stylesheets=tabTextSizeSS)
        controlPanel = self._getControlPanel(plotNames)
        leftPanel = column(children=[self._allTabsPanel], sizing_mode="stretch_both")
        mainPanel = row(children=[leftPanel, controlPanel], sizing_mode="stretch_both")

        self._updateYAxis()
        
        self._doc.add_root( mainPanel )

        self._doc.theme = theme
        self._doc.add_periodic_callback(self._updateCallBack, 100)

        # On Startup set the start/stop dates to show today's data.
        self._todayButtonHandler(None)

    def _updateYAxis(self):
        """@brief Add the callbacks to set the Y Axis label."""
        for pp in self._plotPanels:
            pwrCallback = CustomJS(args=dict(axis=pp.yaxis[0]), code="""
                axis.axis_label = "kW"
            """)
            self._powerButton.js_on_click(pwrCallback)
            self._todayButton.js_on_click(pwrCallback)
            self._yesterdayButton.js_on_click(pwrCallback)
            self._thisWeekButton.js_on_click(pwrCallback)
            self._lastWeekButton.js_on_click(pwrCallback)
            self._thisMonthButton.js_on_click(pwrCallback)
            self._lastMonthButton.js_on_click(pwrCallback)
            self._thisYearButton.js_on_click(pwrCallback)
            self._lastYearButton.js_on_click(pwrCallback)
            pwrFactorCallback = CustomJS(args=dict(axis=pp.yaxis[0]), code="""
                axis.axis_label = "Power Factor"
            """)
            self._powerFactorButton.js_on_click(pwrFactorCallback)
            voltageCallback = CustomJS(args=dict(axis=pp.yaxis[0]), code="""
                axis.axis_label = "Volts"
            """)
            self._voltageButton.js_on_click(voltageCallback)
            freqCallback = CustomJS(args=dict(axis=pp.yaxis[0]), code="""
                axis.axis_label = "Hz"
            """)
            self._freqButton.js_on_click(freqCallback)
            tempCallback = CustomJS(args=dict(axis=pp.yaxis[0]), code="""
                axis.axis_label = "°C"
            """)
            self._tempButton.js_on_click(tempCallback)
            rssiCallback = CustomJS(args=dict(axis=pp.yaxis[0]), code="""
                axis.axis_label = "dBm"
            """)
            self._rssiButton.js_on_click(rssiCallback)
            
    def _plotSingleField(self, plotName, units, appPlotField, rxDict):
        """@brief Show a single value list on the plot area
           @param plotName The name of the plot.
           @param units The unit (Y axis label).
           @param appPlotField The field in the dict to plot."""
        try:
            self._showStatus(0, "Plotting Data...")

            self._plotPanel.legend.visible=False

            for dbName in self._metaDataDict:
                devInfoDict = self._metaDataDict[dbName]
                ct1Name = devInfoDict[GUI.CT1_NAME]
                ct2Name = devInfoDict[GUI.CT2_NAME]
                ct3Name = devInfoDict[GUI.CT3_NAME]
                ct4Name = devInfoDict[GUI.CT4_NAME]
                ct5Name = devInfoDict[GUI.CT5_NAME]
                ct6Name = devInfoDict[GUI.CT6_NAME]
                ct1TraceKey=dbName+ct1Name
                ct2TraceKey=dbName+ct2Name
                ct3TraceKey=dbName+ct3Name
                ct4TraceKey=dbName+ct4Name
                ct5TraceKey=dbName+ct5Name
                ct6TraceKey=dbName+ct6Name
                if dbName in rxDict:
                    data = rxDict[dbName]
                    #Replace the data set with empty sets to remove traces from plot
                    ct1Dict = {GUI.X_AXIS_NAME: [], GUI.DEFAULT_YAXIS_NAME: []}
                    ct2Dict = {GUI.X_AXIS_NAME: [], GUI.DEFAULT_YAXIS_NAME: []}
                    ct3Dict = {GUI.X_AXIS_NAME: [], GUI.DEFAULT_YAXIS_NAME: []}
                    ct4Dict = {GUI.X_AXIS_NAME: [], GUI.DEFAULT_YAXIS_NAME: []}
                    ct5Dict = {GUI.X_AXIS_NAME: [], GUI.DEFAULT_YAXIS_NAME: []}
                    ct6Dict = {GUI.X_AXIS_NAME: [], GUI.DEFAULT_YAXIS_NAME: []}

                    # Remove all data from other traces and use CT1 to display the single trace of interest
                    self._cdsDict[ct2TraceKey].data = ct2Dict
                    self._cdsDict[ct3TraceKey].data = ct3Dict
                    self._cdsDict[ct4TraceKey].data = ct4Dict
                    self._cdsDict[ct5TraceKey].data = ct5Dict
                    self._cdsDict[ct6TraceKey].data = ct6Dict

                    for recordDict in data:
                        if appPlotField in recordDict and \
                           BaseConstants.TIMESTAMP in recordDict:
                            ts = recordDict[BaseConstants.TIMESTAMP]
                            ct1Dict[GUI.X_AXIS_NAME].append(ts)
                            ct1Dict[GUI.DEFAULT_YAXIS_NAME].append(recordDict[appPlotField])
                    # Plot the value of interest using the ct1Dict trace
                    self._cdsDict[ct1TraceKey].data = ct1Dict

        finally:
            self._showStatus(0, "")
            self._enableReadDBButtons(True)
            exeTime = time()-self._startUpdateTime
            msg = f"Took {exeTime:.1f} seconds to read and plot the data."
            self._showStatus(0, msg)

    def _updateCallBack(self):
        # Call the update method so that to ensure it's safe to update the document.
        # This ensures an exception won't be thrown.
        self._doc.add_next_tick_callback(self._update)

    def _update(self, maxDwellMS=1000):
        """@brief Called periodically to update the Web GUI."""
        startTime = time()

        # Show todays data by default
        if self._startupShow:
            # We need a slight delay on startup of the web GUI is not
            # ready to receive the data from the database.
            sleep(.8)
            self._powerButtonHandler(None)
            self._startupShow = False

        else:

            while not self._commsQueue.empty():
                rxMessage = self._commsQueue.get()
                if isinstance(rxMessage, dict):
                    self._processRXDict(rxMessage)

                # If we've spent long enough processing messages then exit.
                # Unprocessed messages can be handled the next time _update() is called.
                if time() > startTime+maxDwellMS:
                    break

    def _processRXDict(self, rxDict):
        """@brief Process the dicts received from the GUI message queue.
           @param rxDict The dict received from the GUI message queue."""
        startT = time()
        fName = inspect.currentframe().f_code.co_name
        self._uio.debug(f"{fName}:")
        if GUI.STATUS_MESSAGE in rxDict:
            index = rxDict[GUI.STATUS_LINE_INDEX]
            msg = rxDict[GUI.STATUS_MESSAGE]
            self._showStatus(index, msg)

        elif GUI.CMD_COMPLETE in rxDict:
            self._statusLabel.text = rxDict[GUI.CMD_COMPLETE]

        elif GUI.ENABLE_ACTION_BUTTONS in rxDict:
            enabled = rxDict[GUI.ENABLE_ACTION_BUTTONS]
            self._enableActionButtons(enabled)

        elif GUI.SUMMARY_ROW in rxDict:
            self._updateSummaryTable(rxDict)

        else:

            if self._updatePlotType == GUI.PLOT_TYPE_AC_VOLTS:
                appPlotField = BaseConstants.VOLTAGE
                plotName = "AC Voltage"
                units = GUI.AC_VOLTS_YAXIS_NAME
                self._plotSingleField(plotName, units, appPlotField, rxDict)

            elif self._updatePlotType == GUI.PLOT_TYPE_AC_FREQ:
                appPlotField = BaseConstants.FREQUENCY
                plotName = "AC Frequency"
                units = GUI.AC_FREQ_YAXIS_NAME
                self._plotSingleField(plotName, units, appPlotField, rxDict)

            elif self._updatePlotType == GUI.PLOT_TYPE_TEMP:
                appPlotField = BaseConstants.TEMPERATURE
                plotName = "CT6 device Temperature"
                units = GUI.TEMP_YAXIS_NAME
                self._plotSingleField(plotName, units, appPlotField, rxDict)

            elif self._updatePlotType == GUI.PLOT_TYPE_RSSI:
                appPlotField = BaseConstants.RSSI_DBM
                plotName = "WiFi RSSI"
                units = GUI.RSSI_YAXIS_NAME
                self._plotSingleField(plotName, units, appPlotField, rxDict)

            else:
                self._plotKWH(rxDict, self._updatePlotType)

        exeTime = time()-startT
        self._uio.debug(f"{fName}: Execution time {exeTime:.1f} seconds.")


    def _plotKWH(self, rxDict, plotType):
        """@brief Plot the measured powers from the CT sensors.
           @param rxDict The dict of values read from the database.
           @param plotType The type of data to plot."""
        try:
            self._showStatus(0, "Plotting Data...")
            
            fieldNameList = None
            if plotType == GUI.PLOT_TYPE_POWER_ACTIVE:
                fieldNameList = (BaseConstants.CT1_ACT_WATTS,
                                 BaseConstants.CT2_ACT_WATTS,
                                 BaseConstants.CT3_ACT_WATTS,
                                 BaseConstants.CT4_ACT_WATTS,
                                 BaseConstants.CT5_ACT_WATTS,
                                 BaseConstants.CT6_ACT_WATTS)

                 # Not sure how useful this message is, it may confuse rather than inform.
#                 invertKw = self._invertKW()
#                if invertKw:
#                    self._line1StatusDiv.text = "Values above 0 = Electricity imported from the grid."
#                else:
#                    self._line1StatusDiv.text = "Values below 0 = Electricity imported from the grid."

            elif plotType == GUI.PLOT_TYPE_POWER_REACTIVE:
                fieldNameList = (BaseConstants.CT1_REACT_WATTS,
                                 BaseConstants.CT2_REACT_WATTS,
                                 BaseConstants.CT3_REACT_WATTS,
                                 BaseConstants.CT4_REACT_WATTS,
                                 BaseConstants.CT5_REACT_WATTS,
                                 BaseConstants.CT6_REACT_WATTS)
                self._plotPanel.yaxis.axis_label = "kVA"
                self._line1StatusDiv.text = ""

            elif plotType == GUI.PLOT_TYPE_POWER_APPARENT:
                fieldNameList = (BaseConstants.CT1_APP_WATTS,
                                 BaseConstants.CT2_APP_WATTS,
                                 BaseConstants.CT3_APP_WATTS,
                                 BaseConstants.CT4_APP_WATTS,
                                 BaseConstants.CT5_APP_WATTS,
                                 BaseConstants.CT6_APP_WATTS)
                self._plotPanel.yaxis.axis_label = "kVA"
                self._line1StatusDiv.text = ""

            elif plotType == GUI.PLOT_TYPE_POWER_FACTOR:
                fieldNameList = (BaseConstants.CT1_PF,
                                 BaseConstants.CT2_PF,
                                 BaseConstants.CT3_PF,
                                 BaseConstants.CT4_PF,
                                 BaseConstants.CT5_PF,
                                 BaseConstants.CT6_PF)
                self._plotPanel.yaxis.axis_label = "Power Factor"
                self._line1StatusDiv.text = ""

            self._plotPanel.legend.visible=True
            for dbName in self._metaDataDict:
                # This dict holds the values to be plotted
                # key = The name of the trace
                # value = A tuple containing
                #     0 = A list of the X values
                #     1 = A list of the Y values
                # If we have the results from this CT4 device in the database
                if dbName in rxDict:
                    ct1TraceKey = None
                    ct2TraceKey = None
                    ct3TraceKey = None
                    ct4TraceKey = None
                    ct5TraceKey = None
                    ct6TraceKey = None
                    rowList = rxDict[dbName]
                    devInfoDict = self._metaDataDict[dbName]
                    ct1Name = devInfoDict[GUI.CT1_NAME]
                    ct2Name = devInfoDict[GUI.CT2_NAME]
                    ct3Name = devInfoDict[GUI.CT3_NAME]
                    ct4Name = devInfoDict[GUI.CT4_NAME]
                    ct5Name = devInfoDict[GUI.CT5_NAME]
                    ct6Name = devInfoDict[GUI.CT6_NAME]

                    #If CT1 is in use
                    if ct1Name and len(ct1Name) > 0:
                        ct1TraceKey=dbName+ct1Name

                    #If CT2 is in use
                    if ct2Name and len(ct2Name) > 0:
                        ct2TraceKey=dbName+ct2Name

                    #If CT3 is in use
                    if ct3Name and len(ct3Name) > 0:
                        ct3TraceKey=dbName+ct3Name

                    #If CT4 is in use
                    if ct4Name and len(ct4Name) > 0:
                        ct4TraceKey=dbName+ct4Name

                    #If CT5 is in use
                    if ct5Name and len(ct5Name) > 0:
                        ct5TraceKey=dbName+ct5Name

                    #If CT6 is in use
                    if ct6Name and len(ct6Name) > 0:
                        ct6TraceKey=dbName+ct6Name

                    #Replace the data set
                    ct1Dict = {GUI.X_AXIS_NAME: [], GUI.DEFAULT_YAXIS_NAME: []}
                    ct2Dict = {GUI.X_AXIS_NAME: [], GUI.DEFAULT_YAXIS_NAME: []}
                    ct3Dict = {GUI.X_AXIS_NAME: [], GUI.DEFAULT_YAXIS_NAME: []}
                    ct4Dict = {GUI.X_AXIS_NAME: [], GUI.DEFAULT_YAXIS_NAME: []}
                    ct5Dict = {GUI.X_AXIS_NAME: [], GUI.DEFAULT_YAXIS_NAME: []}
                    ct6Dict = {GUI.X_AXIS_NAME: [], GUI.DEFAULT_YAXIS_NAME: []}

                    for _row in rowList:

                        if ct1TraceKey:
                            self._addToPlot(ct1Dict, _row, fieldNameList[0], plotType)

                        if ct2TraceKey:
                            self._addToPlot(ct2Dict, _row, fieldNameList[1], plotType)

                        if ct3TraceKey:
                            self._addToPlot(ct3Dict, _row, fieldNameList[2], plotType)

                        if ct4TraceKey:
                            self._addToPlot(ct4Dict, _row, fieldNameList[3], plotType)

                        if ct5TraceKey:
                            self._addToPlot(ct5Dict, _row, fieldNameList[4], plotType)

                        if ct6TraceKey:
                            self._addToPlot(ct6Dict, _row, fieldNameList[5], plotType)

                    if ct1TraceKey:
                        self._cdsDict[ct1TraceKey].data = ct1Dict
                        # Start a thread to calculate the kWh for this sensor
                        threading.Thread( target=self._calcKWH, args=(1, ct1Name, rowList, self._resRadioButtonGroup.active)).start()

                    if ct2TraceKey:
                        self._cdsDict[ct2TraceKey].data = ct2Dict
                        # Start a thread to calculate the kWh for this sensor
                        threading.Thread( target=self._calcKWH, args=(2, ct2Name, rowList, self._resRadioButtonGroup.active)).start()

                    if ct3TraceKey:
                        self._cdsDict[ct3TraceKey].data = ct3Dict
                        # Start a thread to calculate the kWh for this sensor
                        threading.Thread( target=self._calcKWH, args=(3, ct3Name, rowList, self._resRadioButtonGroup.active)).start()

                    if ct4TraceKey:
                        self._cdsDict[ct4TraceKey].data = ct4Dict
                        # Start a thread to calculate the kWh for this sensor
                        threading.Thread( target=self._calcKWH, args=(4, ct4Name, rowList, self._resRadioButtonGroup.active)).start()

                    if ct5TraceKey:
                        self._cdsDict[ct5TraceKey].data = ct5Dict
                        # Start a thread to calculate the kWh for this sensor
                        threading.Thread( target=self._calcKWH, args=(5, ct5Name, rowList, self._resRadioButtonGroup.active)).start()

                    if ct6TraceKey:
                        self._cdsDict[ct6TraceKey].data = ct6Dict
                        # Start a thread to calculate the kWh for this sensor
                        threading.Thread( target=self._calcKWH, args=(6, ct6Name, rowList, self._resRadioButtonGroup.active)).start()

        finally:
            self._showStatus(0, "")
            self._enableReadDBButtons(True)
            exeTime = time()-self._startUpdateTime
            msg = f"Took {exeTime:.1f} seconds to read and plot the data."
            self._showStatus(0, msg)

    def _invertKW(self):
        """@brief Determine if the user wishes to invert the kW plots.
                  By default imported electricity is shown as negative values.
           @return False if the user wishes to plot imported electicity as -ve values.
                   True if the user wishes to plot imported electicity as +ve values."""
        invertkW=False
        if self._pwrPolarityRadioButtonGroup.active == 0:
            invertkW=True
        return invertkW

    def _addToPlot(self, plotDict, rowData, key, plotType):
        """@brief Add to plot dict for a single trace.
           @param traceDict A dict containing x and Y values lists.
           @param rowData The source data.
           @param plotType The type of data being plotted."""
        invertKw = self._invertKW()
        ts = rowData[BaseConstants.TIMESTAMP]
        plotDict[GUI.X_AXIS_NAME].append(ts)
        if plotType == GUI.PLOT_TYPE_POWER_FACTOR:
            plotDict[GUI.DEFAULT_YAXIS_NAME].append(abs(rowData[key]))
        else:
            if invertKw:
                plotDict[GUI.DEFAULT_YAXIS_NAME].append(-rowData[key]/1000.0)
            else:
                plotDict[GUI.DEFAULT_YAXIS_NAME].append(rowData[key]/1000.0)

        # If plotting hourly we add a plot point at the end of the hour so
        # the user sees a stepped chart
        if self._resRadioButtonGroup.active == GUI.HOUR_RESOLUTION:
            ts=ts=ts.replace(minute=59, second=59, microsecond=999)
            plotDict[GUI.X_AXIS_NAME].append(ts)
            if plotType == GUI.PLOT_TYPE_POWER_FACTOR:
                plotDict[GUI.DEFAULT_YAXIS_NAME].append(abs(rowData[key]))
            else:
                if invertKw:
                    plotDict[GUI.DEFAULT_YAXIS_NAME].append(-rowData[key]/1000.0)
                else:
                    plotDict[GUI.DEFAULT_YAXIS_NAME].append(rowData[key]/1000.0)


        # If plotting daily we add a plot point at the end of the day so
        # the user sees a stepped chart
        if self._resRadioButtonGroup.active == GUI.DAY_RESOLUTION:
            ts=ts=ts.replace(hour=23, minute=59, second=59, microsecond=999)
            plotDict[GUI.X_AXIS_NAME].append(ts)
            if plotType == GUI.PLOT_TYPE_POWER_FACTOR:
                plotDict[GUI.DEFAULT_YAXIS_NAME].append(abs(rowData[key]))
            else:
                if invertKw:
                    plotDict[GUI.DEFAULT_YAXIS_NAME].append(-rowData[key]/1000.0)
                else:
                    plotDict[GUI.DEFAULT_YAXIS_NAME].append(rowData[key]/1000.0)

    def _enableActionButtons(self, enabled):
        """@brief Enable/disable the action buttons.
           @param enabled If True enable the button."""
        if enabled:
            self._setButtonsActive()
        else:
            self._setButtonsDisabled()

    def updateGUI(self, msgDict):
        """@brief Send a message to the GUI so that it updates itself.
           @param msgDict A dict containing details of how to update the GUI."""
        # Record the seconds when we received the message
        msgDict[GUI.UPDATE_SECONDS]=time()
        self._commsQueue.put(msgDict)

    def _debug(self, msg):
        """@brief Show a debug message.
           @param msg The message text to show."""
        self._uio.debug(msg)

    def _stripInvalidCharacters(self, valueString):
        """@brief Strip invalid (non alphanumeric) characters.
           @param valueString The string entered by the user."""
        return re.sub(r'[^A-Za-z0-9]+-_', '', str(valueString) )

    # The following methods are called from the GUI but are executed in separate threads
    # outside the GUI thread.

    def _sendStatus(self, msg):
        """@brief Send a status message to be dislayed in the GUI.
           @param msg The message to be displayed."""
        msgDict = {GUI.STATUS_MESSAGE: msg}
        self.updateGUI(msgDict)

    def _sendCmdComplete(self, msg=""):
        """@brief Send a status message to be dislayed in the GUI.
           @param msg The message to be displayed."""
        msgDict = {GUI.CMD_COMPLETE: msg}
        self.updateGUI(msgDict)

    def _error(self, msg):
        """@brief Report an error to the user.
           @param The error message."""
        msgDict = {}
        # We use the first line for info/error messages.
        msgDict[GUI.STATUS_LINE_INDEX]=0
        msgDict[GUI.STATUS_MESSAGE]=msg
        self._commsQueue.put(msgDict)

    def _sendEnableActionButtonsMsg(self, enabled):
        """@brief Send an enable update button message through the Queue into the GUI thread.
           @param enabled If True the button is enabled."""
        msgDict = {}
        msgDict[GUI.ENABLE_ACTION_BUTTONS]=enabled
        self._commsQueue.put(msgDict)

    def _readDataBase(self, startDateTime, stopDateTime, resolution):
        """@brief Read data from the database.
           @param startDateTime The first date/time of interest as epoch time
           @param stopDateTime The last date/time of interest as epoch time.
           @param The resolution of the data to read.
           @return A dict containing the results of the DB read."""
        results={}
        # Start and stop dates are in milliseconds since epoch time, convert to seconds since epoch time.
        startDT=datetime.fromtimestamp(startDateTime/1000)
        stopDT=datetime.fromtimestamp(stopDateTime/1000)
        if startDT >= stopDT:
            self._error("Stop must be after the start date.")
            self._sendEnableActionButtonsMsg(True)
            return results

        startDate = startDT.strftime("%Y-%m-%d")
        stopDate = stopDT.strftime("%Y-%m-%d")
        startHoursMins = startDT.strftime("%H:%M")
        stopHoursMins = stopDT.strftime("%H:%M")

        dBName = self._getSelectedDataBase()
        startT = time()
        fName = inspect.currentframe().f_code.co_name
        self._uio.debug(f"{fName}: startDate={startDate}, stopDate={stopDate}, resolution={resolution}")
        connectedToDB = False
        try:
            cmd = "use {};".format(dBName)
            responseTuple = self._dbIF.executeSQL(cmd)
            connectedToDB=True
        except:
            pass
        if not connectedToDB:
            self._uio.info("Connecting to database.")
            self._connectToDB()
            self._uio.info("Connected to database.")
        # We need to use the DB again as we may have failed above
        cmd = "use {};".format(dBName)
        try:
            responseTuple = self._dbIF.executeSQL(cmd)
        except:
            # If the database no longer exists. It may have been manually deleted.
            return
        if resolution == GUI.MAX_RESOLUTION:
            tableName = BaseConstants.MAX_RES_DB_DATA_TABLE_NAME

        elif resolution == GUI.MINUTE_RESOLUTION:
            tableName = BaseConstants.MINUTE_RES_DB_DATA_TABLE_NAME

        elif resolution == GUI.HOUR_RESOLUTION:
            tableName = BaseConstants.HOUR_RES_DB_DATA_TABLE_NAME

        elif resolution == GUI.DAY_RESOLUTION:
            tableName = BaseConstants.DAY_RES_DB_DATA_TABLE_NAME

        maxRecordCount = self._options.maxpp
        # We find how many records match the search before read every nth (stride value) record.
        # This should allow resonable search times on large data sets.
        cmd = f"SELECT COUNT(*) FROM {tableName} where TIMESTAMP BETWEEN '{startDate} {startHoursMins}:00:000' AND '{stopDate} {stopHoursMins}:59:999';"
        self._uio.debug(f"MYSQL CMD: {cmd}")
        responseTuple = self._dbIF.executeSQL(cmd)
        exeTime = time()-startT
        self._uio.debug(f"MYSQL command execution time {exeTime:.1f} seconds.")
        key = "COUNT(*)"
        if key in responseTuple[0]:
            recordCount = responseTuple[0][key]
            self._uio.debug(f"recordCount = {recordCount}")

            if recordCount > maxRecordCount:
                # PJA: Wired this out as it's probably better to abort very large plots due to the time and memory it takes.
                # The user can always use the '-m/--maxpp' command line argument to increase the default number of maximum
                # plot points if they have fast machines with lots of memory.
                pass
                # If we will have more than the max number of plot points then reduce the number of points
#                    stride = math.ceil( recordCount/maxRecordCount )
#                    cmd = f' WITH ordering AS ( SELECT ROW_NUMBER() OVER (ORDER BY TIMESTAMP) AS n, {tableName}.*'\
#                          f" FROM {tableName} where TIMESTAMP BETWEEN '{startDate} 00:00:00:000' AND '{stopDate} 23:59:59:999' ORDER BY TIMESTAMP"\
#                          " )"\
#                          f' SELECT * FROM ordering WHERE MOD(n, {stride}) = 0;'
            else:
                cmd = f"select * from {tableName} where TIMESTAMP BETWEEN '{startDate} {startHoursMins}:00:000' AND '{stopDate} {stopHoursMins}:59:999';"

                self._uio.debug(f"MYSQL CMD: {cmd}")
                responseTuple = self._dbIF.executeSQL(cmd)
                recordCount = len(responseTuple)
        self._uio.debug("Found {} records.".format( recordCount ))
        if recordCount > self._options.maxpp:
            self._error(f"Reduce plot resolution ({recordCount} values read, max = {self._options.maxpp}).")
            self._sendEnableActionButtonsMsg(True)
        else:
            results[dBName]=responseTuple
            self._commsQueue.put(results)

        self._uio.debug(f"{fName}: Execution time {exeTime:.1f} seconds.")
        msgDict = {}
        msgDict[GUI.STATUS_LINE_INDEX]=0
        msgDict[GUI.STATUS_MESSAGE]=f"Took {exeTime:.1f} seconds to read data from DB."
        return results

    def _calcKWH(self, sensorID, sensorName, rowDictList, resolution):
        """@brief Calculate the kWh usage for the CT data.
           @param sensorID The ID of the sensor (0-3)
           @param sensorName The name of the sensor.
           @param rowDictList A list of dicts of each row in the database table."""
        invertKw = self._invertKW()
        startT = time()
        fName = inspect.currentframe().f_code.co_name
        self._uio.debug(f"{fName}: sensorID={sensorID}, sensorName={sensorName}")
        totalkWH = 0.0
        if sensorID == 1:
            key = BaseConstants.CT1_ACT_WATTS
        elif sensorID == 2:
            key = BaseConstants.CT2_ACT_WATTS
        elif sensorID == 3:
            key = BaseConstants.CT3_ACT_WATTS
        elif sensorID == 4:
            key = BaseConstants.CT4_ACT_WATTS
        elif sensorID == 5:
            key = BaseConstants.CT5_ACT_WATTS
        elif sensorID == 6:
            key = BaseConstants.CT6_ACT_WATTS

        wattHoursList = []
        pWattHoursList = []
        nWattHoursList = []
        lastTime = None
        pTotalkWh = 0.0
        nTotalkWh = 0.0
        for rowDict in rowDictList:
            thisTime = rowDict[BaseConstants.TIMESTAMP]
            if invertKw:
                watts = -rowDict[key]
            else:
                watts = rowDict[key]
            if lastTime is not None:
                elapsedHours = (thisTime-lastTime).total_seconds()/3600.0
                wh = elapsedHours*watts
                if wh >= 0.0:
                    pWattHoursList.append(wh)
                else:
                    nWattHoursList.append(wh)
                wattHoursList.append(wh)

            lastTime = thisTime

        totalkWH = sum(wattHoursList)/1000.0
        pTotalkWh = sum(pWattHoursList)/1000.0
        nTotalkWh = sum(nWattHoursList)/1000.0
        summaryDict = {}
        summaryDict[GUI.SUMMARY_ROW]=[sensorID, sensorName, totalkWH, pTotalkWh, nTotalkWh]
        self._commsQueue.put(summaryDict)

        msgDict = {}
        exeTime = time()-startT
        msgDict[GUI.STATUS_LINE_INDEX]=0
        msgDict[GUI.STATUS_MESSAGE]=f"Took {exeTime:.1f} seconds to read data from DB."

        self._uio.debug(f"{fName}: Execution time {exeTime:.1f} seconds.")




class CTDBClient(DBHandler):
    """@brief Responsible for CT6 sensor database access."""

    def __init__(self, uio, config):
        """@brief Constructor
           @param uio A UIO instance.
           @param config A CT6DashConfig instance."""
        super().__init__(uio, config)
        self._metaTableSchema = DBHandler.GetTableSchema( CTDBClient.CT6_DB_META_TABLE_SCHEMA )
        self._tableSchema = DBHandler.GetTableSchema( CTDBClient.CT6_DB_TABLE_SCHEMA )

class CTAppServer(object):
    """@brief Responsible for
        - Starting the YViewCollector.
        - Storing data in the database.
        - Presenting the user with a web GUI to allow data to be displayed and manipulated."""

    def __init__(self, uio, options, config):
        """@brief Constructor
           @param uio A UIO instance
           @param options The command line options instance
           @param config A GUIConfigBase instance."""
        self._uio                   = uio
        self._options               = options
        self._config                = config
        self._dbHandler             = None

    def close(self):
        """@brief Close down the app server."""

        if self._dbHandler:
            self._dbHandler.disconnect()
            self._dbHandler = None

    def start(self):
        """@Start the App server running."""
        try:
            loginEnabled = self._config.getAttr(ConfigBase.SERVER_LOGIN)
            if loginEnabled:
                credFile = CRED_JSON_FILE
            else:
                credFile = None
            gui = GUI(self._uio, self._options, self._config, credFile)
            openBrowser = not self._options.no_gui
            gui.runBlockingBokehServer(gui.getAppMethodDict(), openBrowser=openBrowser)

        finally:
            self.close()

def main():
    """@brief Program entry point"""
    uio = UIO()

    try:
        parser = argparse.ArgumentParser(description="This application is responsible for the following.\n"\
                                                     "- Connecting to a YView icon server to receive device data.\n"\
                                                     "- Storing the Data in a mysql database.\n"\
                                                     "- Presenting a web interface to view and manipulate the data.",
                                         formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument("-d", "--debug",  action='store_true', help="Enable debugging.")
        parser.add_argument("-c", "--configure",    help="Enter/Modify the app configuration.", action='store_true')
        parser.add_argument("-f", "--config_file",  help="The configuration file for the CT6 Dash Server"\
                            " (default={}).".format(CT6DashConfig.GetConfigFile(CT6DashConfig.DEFAULT_CONFIG_FILENAME)),
                            default=CT6DashConfig.GetConfigFile(CT6DashConfig.DEFAULT_CONFIG_FILENAME))
        parser.add_argument("-p", "--positive",      action='store_true', help="Display imported electricity (kW) on plots as positive values.")
        parser.add_argument("-n", "--no_gui",       action='store_true', help="Do not display the GUI. By default a local web browser is opend displaying the GUI.")
        parser.add_argument("-s", "--enable_syslog",action='store_true', help="Enable syslog debug data.")
        # Default plot points allows 1 week of minute resolution (60*24*7 = 10080)
        parser.add_argument("-m", "--maxpp",        help="The maximum number of plot points (default=11000).", type=int, default=11000)

        options = parser.parse_args()
        uio.enableDebug(options.debug)
        uio.logAll(True)
        uio.enableSyslog(options.enable_syslog, programName="ct6_dash")
        if options.enable_syslog:
            uio.info("Syslog enabled")

        dashConfig = CT6DashConfig(uio, options.config_file, CT6DashConfig.DEFAULT_CONFIG)

        if options.configure:
            dashConfig.configure(editConfigMethod=dashConfig.edit)

        else:
            ctAppServer = CTAppServer(uio, options, dashConfig)
            ctAppServer.start()

    #If the program throws a system exit exception
    except SystemExit:
        pass
    #Don't print error information if CTRL C pressed
    except KeyboardInterrupt:
        pass
    except Exception as ex:
        logTraceBack(uio)

        if options.debug:
            raise
        else:
            uio.error(str(ex))

if __name__== '__main__':
    main()
