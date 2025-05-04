import os
import calendar
import pytz
import re

from time import time, sleep

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from queue import Queue

from p3lib.bokeh_gui import MultiAppServer
from lib.base_constants import BaseConstants

from ct6.ct6_tool import CT6Base

from bokeh.models import Div, Button, CustomJS
from bokeh.models import DatetimePicker
from bokeh.models import RadioButtonGroup, DataTable, \
                         TableColumn, InlineStyleSheet, Tooltip, HelpButton
from bokeh.models.widgets import HTMLTemplateFormatter
from bokeh.layouts import column, row
from bokeh.plotting import ColumnDataSource

class GUIBase(MultiAppServer):
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
        loginHtmlFile = os.path.join(GUIBase.LOCAL_PATH, "assets/login.html")
        if not os.path.isfile(loginHtmlFile):
            loginHtmlFile = os.path.join(GUIBase.LOCAL_PATH, "../assets/login.html")
            if not os.path.isfile(loginHtmlFile):
                raise Exception(f'{loginHtmlFile} file not found.')
        return loginHtmlFile

    def __init__(self,
                 uio,
                 options,
                 config,
                 loginCredentialsFile,
                 address,
                 bokehPort,
                 accessLogFile):
        """@brief Constructor.
           @param uio A UIO instance responsible for stdout/stdin input output.
           @param options The command line argparse options instance.
           @param config The dash app config.
           @param loginCredentialsFile A file containing the login credentials or None if no server authentication is required.
           @param address The local address for the bokeh server.
           @param bokehPort The bokeh server port.
           @param accessLogFile The server access log file."""
        super().__init__(address=address,
                         bokehPort=bokehPort,
                         credentialsJsonFile=loginCredentialsFile,
                         loginHTMLFile=GUIBase.GetLoginPage(),
                         accessLogFile=accessLogFile )
        self._uio = uio
        self._options = options
        self._config = config

        self._doc = None
        self._server = None
        self._tabList = None
        self._dbHandler = None
        self._startUpdateTime = None
        self._programVersion = CT6Base.GetProgramVersion()

        # this queue is used to send commands from the GUI thread and read responses received from outside the GUI thread.
        self._commsQueue = Queue()

        self._startupShow = True

        self._plotPanel = None
        self._updatePlotType = GUIBase.PLOT_TYPE_POWER_ACTIVE
        self._cmdButtonList = []

    def getAppMethodDict(self):
        """@return The server app method dict."""
        appMethodDict = {}
        appMethodDict['/']=self._mainApp
        return appMethodDict

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
        # Set resolution to mins to set a good trade off between plot time and resolution
        self._resRadioButtonGroup.active = 1
        today = datetime.today()
        startOfDay = today.replace(hour=0, minute=0, second=0, microsecond=0)
        self._startDateTimePicker.value = startOfDay.astimezone(pytz.utc)
        endDateTime = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        self._stopDateTimePicker.value = endDateTime.astimezone(pytz.utc)
        # Kick of a plot attempt to save pressing the power button afterwards
        self._plotSensorData(True)

    def _yesterdayButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        # Set resolution to mins to set a good trade off between plot time and resolution
        self._resRadioButtonGroup.active = 1
        today = datetime.today()
        yesterday = today - timedelta(days = 1)
        startOfYesterday = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        self._startDateTimePicker.value = startOfYesterday.astimezone(pytz.utc)
        endDateTime = startOfYesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        self._stopDateTimePicker.value = endDateTime.astimezone(pytz.utc)
       # Kick of a plot attempt to save pressing the power button afterwards
        self._plotSensorData(True)

    def _thisWeekButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        # Set resolution to mins to set a good trade off between plot time and resolution
        self._resRadioButtonGroup.active = 1
        today = datetime.today()
        dayOfWeek = today.weekday()
        startOfWeek = today - timedelta(days = dayOfWeek)
        startOfWeek = startOfWeek.replace(hour=0, minute=0, second=0, microsecond=0)
        endOfWeek = startOfWeek + timedelta(days=7)
        endOfWeek = endOfWeek - timedelta(seconds=1)
        self._startDateTimePicker.value = startOfWeek.astimezone(pytz.utc)
        self._stopDateTimePicker.value = endOfWeek.astimezone(pytz.utc)
        # Kick of a plot attempt to save pressing the power button afterwards
        self._plotSensorData(True)

    def _lastWeekButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        # Set resolution to mins to set a good trade off between plot time and resolution
        self._resRadioButtonGroup.active = 1
        today = datetime.today()
        dayOfWeek = today.weekday()
        startOfWeek = today - timedelta(days = dayOfWeek+7)
        startOfWeek = startOfWeek.replace(hour=0, minute=0, second=0, microsecond=0)
        endOfWeek = startOfWeek + timedelta(days=7)
        endOfWeek = endOfWeek - timedelta(seconds=1)
        self._startDateTimePicker.value = startOfWeek.astimezone(pytz.utc)
        self._stopDateTimePicker.value = endOfWeek.astimezone(pytz.utc)
        # Kick of a plot attempt to save pressing the power button afterwards
        self._plotSensorData(True)

    def _get_last_of_month(self, dt: datetime) -> datetime:
        """Returns the last day of the month at 23:59:59."""
        last_day = calendar.monthrange(dt.year, dt.month)[1]  # Get last day of the month
        return dt.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)

    def _thisMonthButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        # Set resolution to hours to set a good trade off between plot time and resolution
        self._resRadioButtonGroup.active = 2
        now = datetime.now()
        startD = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        stopD = self._get_last_of_month(now)
        self._startDateTimePicker.value = startD.astimezone(pytz.utc)
        self._stopDateTimePicker.value = stopD.astimezone(pytz.utc)
        # Kick of a plot attempt to save pressing the power button afterwards
        self._plotSensorData(True)

    def _get_first_of_previous_month(self, dt: datetime) -> datetime:
        """Returns the first day of the previous month at 00:00:00."""
        first_day = dt.replace(day=1) - relativedelta(months=1)  # Move to the first of last month
        return first_day.replace(hour=0, minute=0, second=0, microsecond=0)

    def _get_last_of_previous_month(self, dt: datetime) -> datetime:
        """Returns the last day of the previous month at 23:59:59."""
        first_this_month = dt.replace(day=1)  # First day of current month
        last_day = first_this_month - relativedelta(days=1)  # Go back one day
        return last_day.replace(hour=23, minute=59, second=59, microsecond=999999)

    def _lastMonthButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        # Set resolution to hours to set a good trade off between plot time and resolution
        self._resRadioButtonGroup.active = 2
        now = datetime.now()
        startD = self._get_first_of_previous_month(now)
        stopD = self._get_last_of_previous_month(now)
        self._startDateTimePicker.value = startD.astimezone(pytz.utc)
        self._stopDateTimePicker.value = stopD.astimezone(pytz.utc)
        # Kick of a plot attempt to save pressing the power button afterwards
        self._plotSensorData(True)

    def _get_first_and_last_of_year(self, dt: datetime):
        """Returns the first and last day of the current year."""
        first_day = dt.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        last_day = dt.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)
        return first_day, last_day

    def _thisYearButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        # Set resolution to hours to set a good trade off between plot time and resolution
        self._resRadioButtonGroup.active = 2
        now = datetime.now()
        startD, stopD = self._get_first_and_last_of_year(now)
        self._startDateTimePicker.value = startD.astimezone(pytz.utc)
        self._stopDateTimePicker.value  = stopD.astimezone(pytz.utc)
        # Kick of a plot attempt to save pressing the power button afterwards
        self._plotSensorData(True)

    def _lastYearButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        # Set resolution to hours to set a good trade off between plot time and resolution
        self._resRadioButtonGroup.active = 2
        now = datetime.now()
        startD, stopD = self._get_first_and_last_of_year(now)
        startD = startD.replace(year=startD.year-1)
        stopD = stopD.replace(year=stopD.year-1)
        self._startDateTimePicker.value = startD.astimezone(pytz.utc)
        self._stopDateTimePicker.value  = stopD.astimezone(pytz.utc)
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

        self._powerFactorButton = Button(label="Power Factor", button_type=GUIBase.BUTTON_TYPE)
        self._powerFactorButton.on_click(self._powerFactorButtonHandler)

        self._voltageButton = Button(label="AC Voltage", button_type=GUIBase.BUTTON_TYPE)
        self._voltageButton.on_click(self._showACVolts)

        self._freqButton = Button(label="AC Frequency", button_type=GUIBase.BUTTON_TYPE)
        self._freqButton.on_click(self._showACFreq)

        row1 = row(children=[self._powerFactorButton, self._voltageButton, self._freqButton])

        self._tempButton = Button(label="Temperature", button_type=GUIBase.BUTTON_TYPE)
        self._tempButton.on_click(self._showTemp)

        self._rssiButton = Button(label="WiFi RSSI", button_type=GUIBase.BUTTON_TYPE)
        self._rssiButton.on_click(self._showRSSI)

        row2 = row(children=[self._tempButton, self._rssiButton])

        return column(children=[row1, row2])

    def _getControlPanel(self, sensorNames):
        """@brief Get an instance of the button panel.
           @param sensorNames A list of the names of the sensors.
           @return an instance of the button panel."""
        self._updateButton = Button(label="Update", button_type=GUIBase.BUTTON_TYPE)
        self._updateButton.on_click(self._powerButtonHandler)

        self._todayButton = Button(label="Today", button_type=GUIBase.BUTTON_TYPE)
        self._todayButton.on_click(self._todayButtonHandler)

        self._yesterdayButton = Button(label="Yesterday", button_type=GUIBase.BUTTON_TYPE)
        self._yesterdayButton.on_click(self._yesterdayButtonHandler)

        self._thisWeekButton = Button(label="This week", button_type=GUIBase.BUTTON_TYPE)
        self._thisWeekButton.on_click(self._thisWeekButtonHandler)

        self._lastWeekButton = Button(label="Last week", button_type=GUIBase.BUTTON_TYPE)
        self._lastWeekButton.on_click(self._lastWeekButtonHandler)

        self._thisMonthButton = Button(label="This Month", button_type=GUIBase.BUTTON_TYPE)
        self._thisMonthButton.on_click(self._thisMonthButtonHandler)

        self._lastMonthButton = Button(label="Last Month", button_type=GUIBase.BUTTON_TYPE)
        self._lastMonthButton.on_click(self._lastMonthButtonHandler)

        self._thisYearButton = Button(label="This Year", button_type=GUIBase.BUTTON_TYPE)
        self._thisYearButton.on_click(self._thisYearButtonHandler)

        self._lastYearButton = Button(label="Last Year", button_type=GUIBase.BUTTON_TYPE)
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
        leftButtonPanel0 = column(children=[self._updateButton])
        leftButtonPanel = column(children=[self._todayButton, self._thisWeekButton, self._thisMonthButton, self._thisYearButton])
        rightButtonPanel = column(children=[self._yesterdayButton, self._lastWeekButton, self._lastMonthButton, self._lastYearButton])
        buttonPanelA = row(children=[subtractStartDaybutton, self._startDateTimePicker, addStartDaybutton])
        buttonPanelB = row(children=[subtractStopDaybutton, self._stopDateTimePicker, addStopDaybutton])
        buttonPanelC = row(children=[leftButtonPanel0, leftButtonPanel, rightButtonPanel])
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
        if hasattr(self._options, 'positive'):
            if self._options.positive:
                defaultpwrPolarity = 0
            else:
                defaultpwrPolarity = 1

        elif hasattr(self._options, 'negative'):
            if self._options.negative:
                defaultpwrPolarity = 1
            else:
                defaultpwrPolarity = 0

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
                                       buttonPanelA,
                                       buttonPanelB,
                                       buttonPanelC,
                                       optionsButtonPanel,
                                       actionButtonPanel,
                                       self._line0StatusDiv,
                                       self._line1StatusDiv,
                                       self._line2StatusDiv,
                                       self._line3StatusDiv,
                                       self._line4StatusDiv,
                                       self._line5StatusDiv])

        self._cmdButtonList = ( self._updateButton,
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
        self._startDateTimePicker.value = (dateTimeObj + timedelta(days=1)).astimezone(pytz.utc)

    def _subtractStartDayCallBack(self, event):
        """@brief Called when the associated button is clicked to subtract a day to the start time.
           @param event The event that triggered the method call."""
        dateTimeObj=datetime.fromtimestamp(self._startDateTimePicker.value/1000)
        self._startDateTimePicker.value = (dateTimeObj - timedelta(days=1)).astimezone(pytz.utc)

    def _addStopDayCallBack(self, event):
        """@brief Called when the associated button is clicked to add a day to the stop time.
           @param event The event that triggered the method call."""
        dateTimeObj=datetime.fromtimestamp(self._stopDateTimePicker.value/1000)
        self._stopDateTimePicker.value = (dateTimeObj + timedelta(days=1)).astimezone(pytz.utc)

    def _subtractStopDayCallBack(self, event):
        """@brief Called when the associated button is clicked to subtract a day to the stop time.
           @param event The event that triggered the method call."""
        dateTimeObj=datetime.fromtimestamp(self._stopDateTimePicker.value/1000)
        self._stopDateTimePicker.value = (dateTimeObj - timedelta(days=1)).astimezone(pytz.utc)

    def _getSelectedDevice(self):
        """@brief Get the name of the selected CT6 device.
           @return The name of the selected CT6 device or None if not selected."""
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
        self._emptySensorColumn1 = ["" for i in range(0, GUIBase.SENSOR_COUNT)]
        self._emptySensorColumn2 = ["" for i in range(0, GUIBase.SENSOR_COUNT)]
        self._emptySensorColumn3 = ["" for i in range(0, GUIBase.SENSOR_COUNT)]
        self._emptySensorColumn4 = ["" for i in range(0, GUIBase.SENSOR_COUNT)]
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
        rowCount = GUIBase.SENSOR_COUNT
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
        if GUIBase.SUMMARY_ROW in rxDict:
            row = rxDict[GUIBase.SUMMARY_ROW]
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

    def _updateYAxis(self):
        """@brief Add the callbacks to set the Y Axis label."""
        for pp in self._plotPanels:
            pwrCallback = CustomJS(args=dict(axis=pp.yaxis[0]), code="""
                axis.axis_label = "kW"
            """)
            self._updateButton.js_on_click(pwrCallback)
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


    def _updateCallBack(self):
        # Call the update method so that to ensure it's safe to update the document.
        # This ensures an exception won't be thrown.
        self._doc.add_next_tick_callback(self._update)


    def _update(self, maxDwellMS=1000):
        """@brief Called periodically to update the Web GUI."""
        try:
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

        except Exception:
            self._uio.errorException()

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
        msgDict[GUIBase.UPDATE_SECONDS]=time()
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
        """@brief Send a status message to be displayed in the GUI.
           @param msg The message to be displayed."""
        msgDict = {GUIBase.STATUS_MESSAGE: msg}
        self.updateGUI(msgDict)

    def _sendCmdComplete(self, msg=""):
        """@brief Send a status message to be dislayed in the GUIBase.
           @param msg The message to be displayed."""
        msgDict = {GUIBase.CMD_COMPLETE: msg}
        self.updateGUI(msgDict)

    def _error(self, msg):
        """@brief Report an error to the user.
           @param The error message."""
        msgDict = {}
        # We use the first line for info/error messages.
        msgDict[GUIBase.STATUS_LINE_INDEX]=0
        msgDict[GUIBase.STATUS_MESSAGE]=msg
        self._commsQueue.put(msgDict)

    def _sendEnableActionButtonsMsg(self, enabled):
        """@brief Send an enable update button message through the Queue into the GUI thread.
           @param enabled If True the button is enabled."""
        msgDict = {}
        msgDict[GUIBase.ENABLE_ACTION_BUTTONS]=enabled
        self._commsQueue.put(msgDict)

    def _invertKW(self):
        """@brief Determine if the user wishes to invert the kW plots.
                  By default imported electricity is shown as negative values.
           @return False if the user wishes to plot imported electicity as -ve values.
                   True if the user wishes to plot imported electicity as +ve values."""
        invertkW=False
        if self._pwrPolarityRadioButtonGroup.active == 0:
            invertkW=True
        return invertkW