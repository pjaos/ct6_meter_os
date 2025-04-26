import itertools
import os
import psutil
import objgraph
import inspect
import copy
import platform
import rich
import json
import sys
import threading
from time import time, sleep

import sqlite3

import pandas as pd

from datetime import datetime
from queue import Queue, Empty

from bokeh.layouts import column, row
from bokeh.models import HoverTool
from bokeh.models import TabPanel, Tabs
from bokeh.models.css import Styles
from bokeh.plotting import figure, ColumnDataSource
from bokeh.palettes import Category20_20

from lib.base_constants import BaseConstants
from lib.config import ConfigBase

from lib.yview import YView

from ct6.gui_base import GUIBase

class GUI(GUIBase):
    """@brief Responsible for providing the GUI dashboard for viewing data from CT6 devices.
              This is provided over a Web interface."""

    META_DATA_ROW               = "META_DATA_ROW"

    META_TABLE_ID_INDEX = 0
    META_TABLE_ASSY_INDEX = 1
    META_TABLE_DEVNAME_INDEX = 2
    META_TABLE_CT1_NAME_INDEX = 3
    META_TABLE_CT2_NAME_INDEX = 4
    META_TABLE_CT3_NAME_INDEX = 5
    META_TABLE_CT4_NAME_INDEX = 6
    META_TABLE_CT5_NAME_INDEX = 7
    META_TABLE_CT6_NAME_INDEX = 8

    def __init__(self, uio, options, config, loginCredentialsFile, db_client):
        """@brief Constructor.
           @param uio A UIO instance responsible for stdout/stdin input output.
           @param options The command line argparse options instance.
           @param config The dash app config.
           @param loginCredentialsFile A file containing the login credentials or None if no server authentication is required.
           @param db_client An instance of SQLite3DBClient."""
        super().__init__(uio,
                         options,
                         config,
                         loginCredentialsFile,
                         config.getAttr(AppConfig.LOCAL_GUI_SERVER_ADDRESS),
                         config.getAttr(AppConfig.LOCAL_GUI_SERVER_PORT),
                         config.getAttr(AppConfig.SERVER_ACCESS_LOG_FILE) )

        self._db_client = db_client
        self._db_dicts = {}

    def _executeSQL(self, conn, cmd):
        """@brief Execute an SQL cmd.
           @param cmd The SQL command.
           @return The response tuple."""
        cursor = conn.cursor()
        self._uio.debug(f"SQL CMD: {cmd}")
        cursor.execute(cmd)
        response_tuple = cursor.fetchall()
        conn.commit()
        cursor.close()
        return response_tuple

    def _update_db_dicts(self):
        """@brief Connect to all available databases."""
        db_storage_folder = self._config.getAttr(AppConfig.DB_STORAGE_PATH)
        db_file_list = SQLite3DBClient.GetDBFileList(db_storage_folder)
        for db_file in db_file_list:
            conn = None
            try:
                # Connect to the database
                conn = sqlite3.connect(db_file)
                # We'll store parameters in this dict
                db_dict = {}
                self._db_dicts[db_file]=db_dict
                # Get the meta data for the db and store in the db_dict
                cmd = "select * from {} limit 1;".format(GUI.DB_META_TABLE_NAME)
                response_tuple = self._executeSQL(conn, cmd)
                if response_tuple and len(response_tuple) > 0:
                    # The key in this dict will be the database name.
                    # The value is the contents of the first row in the table.
                    db_dict[GUI.META_DATA_ROW]=response_tuple[0]
            finally:
                if conn:
                    conn.close()
                    # Help garbage collector
                    conn = None

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
        threading.Thread( target=self._readDataBase, args=(self._getSelectedDataBase(),
                                                           self._startDateTimePicker.value,
                                                           self._stopDateTimePicker.value,
                                                           self._resRadioButtonGroup.active)).start()

    def _showACVolts(self):
        """@brief Show the AC volts plot."""
        self._updatePlotType = GUI.PLOT_TYPE_AC_VOLTS
        self._startUpdateTime = time()
        self._clearSummaryTable()
        self._enableReadDBButtons(False)
        self._showStatus(0, "Reading Data...")
        # Run thread to recover the data from the database.
        threading.Thread( target=self._readDataBase, args=(self._getSelectedDataBase(),
                                                           self._startDateTimePicker.value,
                                                           self._stopDateTimePicker.value,
                                                           self._resRadioButtonGroup.active)).start()

    def _showACFreq(self):
        """@brief Show the AC freq plot."""
        self._updatePlotType = GUI.PLOT_TYPE_AC_FREQ
        self._startUpdateTime = time()
        self._clearSummaryTable()
        self._enableReadDBButtons(False)
        self._showStatus(0, "Reading Data...")
        # Run thread to recover the data from the database.
        threading.Thread( target=self._readDataBase, args=(self._getSelectedDataBase(),
                                                           self._startDateTimePicker.value,
                                                           self._stopDateTimePicker.value,
                                                           self._resRadioButtonGroup.active)).start()

    def _showTemp(self):
        """@brief Show unit temperature plot."""
        self._updatePlotType = GUI.PLOT_TYPE_TEMP
        self._startUpdateTime = time()
        self._clearSummaryTable()
        self._enableReadDBButtons(False)
        self._showStatus(0, "Reading Data...")
        # Run thread to recover the data from the database.
        threading.Thread( target=self._readDataBase, args=(self._getSelectedDataBase(),
                                                           self._startDateTimePicker.value,
                                                           self._stopDateTimePicker.value,
                                                           self._resRadioButtonGroup.active)).start()

    def _showRSSI(self):
        """@brief Show the WiFi RSSI plot."""
        self._updatePlotType = GUI.PLOT_TYPE_RSSI
        self._startUpdateTime = time()
        self._clearSummaryTable()
        self._enableReadDBButtons(False)
        self._showStatus(0, "Reading Data...")
        # Run thread to recover the data from the database.
        threading.Thread( target=self._readDataBase, args=(self._getSelectedDataBase(),
                                                           self._startDateTimePicker.value,
                                                           self._stopDateTimePicker.value,
                                                           self._resRadioButtonGroup.active)).start()

    def _getSelectedDataBase(self):
        """@brief The name of the db file selected.
           @return The db file selected."""
        selected_dev = self._getSelectedDevice()
        selected_db_file = None
        for db_file in self._db_dicts.keys():
            db_dict = self._db_dicts[db_file]
            meta_row_data = db_dict[GUI.META_DATA_ROW]
            if selected_dev == meta_row_data[GUI.META_TABLE_DEVNAME_INDEX]:
                selected_db_file = db_file
                break
        return selected_db_file

    def _mainApp(self, doc):
        """@brief create the GUI page.
           @param doc The document to add the plot to."""
        self._startupShow = True

        self._update_db_dicts()

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
        for dbName in self._db_dicts.keys():
            db_dict = self._db_dicts[dbName]

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

            hover = HoverTool()
            dateS =  '@{}'.format(GUI.X_AXIS_NAME)
            dateS += '{%F}'
            hover.tooltips = [("","$name"),("kW", "$y{1.1f}"), ('date', "$x{%Y-%m-%d}"), ('time', "$x{%H:%M:%S}"), ("sample", "$index")]
            hover.formatters = {'$x': 'datetime'}
            self._plotPanel.add_tools(hover)

            self._dbTableList.append( (dbName,0) )
            plotNames = self._get_db_plot_names(dbName)
            for i in range(0,6):
                if plotNames[i] and len(plotNames[i]) > 0:

                    cds = ColumnDataSource({GUI.X_AXIS_NAME: [],
                                            GUI.DEFAULT_YAXIS_NAME: []})
                    self._cdsDict[dbName + plotNames[i]] = cds
                    self._plotPanel.line(GUI.X_AXIS_NAME, GUI.DEFAULT_YAXIS_NAME, source=cds, name=plotNames[i], legend_label=plotNames[i], line_color=next(colors), line_width=3)
                    self._plotPanel.legend.click_policy="hide"
            self._plotPanel.legend.location = 'bottom_left'

            self._tabList.append( TabPanel(child=self._plotPanel,  title=db_dict[GUI.META_DATA_ROW][GUI.META_TABLE_DEVNAME_INDEX]) )
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

        self._showStatus(5, f"Software Version: {self._programVersion}")

    def _get_db_plot_names(self, db_file):
        """@return A list (6 items) of the configured CT6 port names. If not found
                   a list of 6 empty names are returned."""
        plotNames = ['','','','','','']
        if db_file in self._db_dicts:
            db_dict = self._db_dicts[db_file]
            plotNames = (db_dict[GUI.META_DATA_ROW][GUI.META_TABLE_CT1_NAME_INDEX],
                         db_dict[GUI.META_DATA_ROW][GUI.META_TABLE_CT2_NAME_INDEX],
                         db_dict[GUI.META_DATA_ROW][GUI.META_TABLE_CT3_NAME_INDEX],
                         db_dict[GUI.META_DATA_ROW][GUI.META_TABLE_CT4_NAME_INDEX],
                         db_dict[GUI.META_DATA_ROW][GUI.META_TABLE_CT5_NAME_INDEX],
                         db_dict[GUI.META_DATA_ROW][GUI.META_TABLE_CT6_NAME_INDEX])
        return plotNames

    def _plotSingleField(self, plotName, units, appPlotIndex, rxDict):
        """@brief Show a single value list on the plot area
           @param plotName The name of the plot.
           @param units The unit (Y axis label).
           @param appPlotIndex The index of the field on the row data.
           @param rxDict The dict containing the value/s to plot."""
        try:
            self._showStatus(0, "Plotting Data...")

            self._plotPanel.legend.visible=False

            for dbName in self._db_dicts.keys():
                ct1Name, ct2Name, ct3Name, ct4Name, ct5Name, ct6Name = self._get_db_plot_names(dbName)
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
                    if ct2TraceKey in self._cdsDict:
                        self._cdsDict[ct2TraceKey].data = ct2Dict
                    if ct3TraceKey in self._cdsDict:
                        self._cdsDict[ct3TraceKey].data = ct3Dict
                    if ct4TraceKey in self._cdsDict:
                        self._cdsDict[ct4TraceKey].data = ct4Dict
                    if ct5TraceKey in self._cdsDict:
                        self._cdsDict[ct5TraceKey].data = ct5Dict
                    if ct6TraceKey in self._cdsDict:
                        self._cdsDict[ct6TraceKey].data = ct6Dict

                    for recordDict in data:
                        if appPlotIndex < len(recordDict):
                            ts = datetime.fromisoformat(recordDict[BaseConstants.TIMESTAMP_INDEX])
                            ct1Dict[GUI.X_AXIS_NAME].append(ts)
                            ct1Dict[GUI.DEFAULT_YAXIS_NAME].append(recordDict[appPlotIndex])
                    # Plot the value of interest using the ct1Dict trace
                    self._cdsDict[ct1TraceKey].data = ct1Dict

        finally:
            self._showStatus(0, "")
            self._enableReadDBButtons(True)
            exeTime = time()-self._startUpdateTime
            msg = f"Took {exeTime:.1f} seconds to read and plot the data."
            self._showStatus(0, msg)

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
                appPlotIndex = BaseConstants.VOLTAGE_INDEX
                plotName = "AC Voltage"
                units = GUI.AC_VOLTS_YAXIS_NAME
                self._plotSingleField(plotName, units, appPlotIndex, rxDict)

            elif self._updatePlotType == GUI.PLOT_TYPE_AC_FREQ:
                appPlotIndex = BaseConstants.FREQUENCY_INDEX
                plotName = "AC Frequency"
                units = GUI.AC_FREQ_YAXIS_NAME
                self._plotSingleField(plotName, units, appPlotIndex, rxDict)

            elif self._updatePlotType == GUI.PLOT_TYPE_TEMP:
                appPlotIndex = BaseConstants.TEMPERATURE_INDEX
                plotName = "CT6 device Temperature"
                units = GUI.TEMP_YAXIS_NAME
                self._plotSingleField(plotName, units, appPlotIndex, rxDict)

            elif self._updatePlotType == GUI.PLOT_TYPE_RSSI:
                appPlotIndex = BaseConstants.RSSI_DBM_INDEX
                plotName = "WiFi RSSI"
                units = GUI.RSSI_YAXIS_NAME
                self._plotSingleField(plotName, units, appPlotIndex, rxDict)

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

            fieldIndexList = None
            if plotType == GUI.PLOT_TYPE_POWER_ACTIVE:
                fieldIndexList = (BaseConstants.CT1_ACT_WATTS_INDEX,
                                 BaseConstants.CT2_ACT_WATTS_INDEX,
                                 BaseConstants.CT3_ACT_WATTS_INDEX,
                                 BaseConstants.CT4_ACT_WATTS_INDEX,
                                 BaseConstants.CT5_ACT_WATTS_INDEX,
                                 BaseConstants.CT6_ACT_WATTS_INDEX)

            elif plotType == GUI.PLOT_TYPE_POWER_REACTIVE:
                fieldIndexList = (BaseConstants.CT1_REACT_WATTS_INDEX,
                                 BaseConstants.CT2_REACT_WATTS_INDEX,
                                 BaseConstants.CT3_REACT_WATTS_INDEX,
                                 BaseConstants.CT4_REACT_WATTS_INDEX,
                                 BaseConstants.CT5_REACT_WATTS_INDEX,
                                 BaseConstants.CT6_REACT_WATTS_INDEX)
                self._plotPanel.yaxis.axis_label = "kVA"
                self._line1StatusDiv.text = ""

            elif plotType == GUI.PLOT_TYPE_POWER_APPARENT:
                fieldIndexList = (BaseConstants.CT1_APP_WATTS_INDEX,
                                 BaseConstants.CT2_APP_WATTS_INDEX,
                                 BaseConstants.CT3_APP_WATTS_INDEX,
                                 BaseConstants.CT4_APP_WATTS_INDEX,
                                 BaseConstants.CT5_APP_WATTS_INDEX,
                                 BaseConstants.CT6_APP_WATTS_INDEX)
                self._plotPanel.yaxis.axis_label = "kVA"
                self._line1StatusDiv.text = ""

            elif plotType == GUI.PLOT_TYPE_POWER_FACTOR:
                fieldIndexList = (BaseConstants.CT1_PF_INDEX,
                                 BaseConstants.CT2_PF_INDEX,
                                 BaseConstants.CT3_PF_INDEX,
                                 BaseConstants.CT4_PF_INDEX,
                                 BaseConstants.CT5_PF_INDEX,
                                 BaseConstants.CT6_PF_INDEX)
                self._plotPanel.yaxis.axis_label = "Power Factor"
                self._line1StatusDiv.text = ""

            self._plotPanel.legend.visible=True
            for dbName in self._db_dicts.keys():
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
                    ct1Name, ct2Name, ct3Name, ct4Name, ct5Name, ct6Name = self._get_db_plot_names(dbName)

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
                            self._addToPlot(ct1Dict, _row, fieldIndexList[0], plotType)

                        if ct2TraceKey:
                            self._addToPlot(ct2Dict, _row, fieldIndexList[1], plotType)

                        if ct3TraceKey:
                            self._addToPlot(ct3Dict, _row, fieldIndexList[2], plotType)

                        if ct4TraceKey:
                            self._addToPlot(ct4Dict, _row, fieldIndexList[3], plotType)

                        if ct5TraceKey:
                            self._addToPlot(ct5Dict, _row, fieldIndexList[4], plotType)

                        if ct6TraceKey:
                            self._addToPlot(ct6Dict, _row, fieldIndexList[5], plotType)

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

    def _addToPlot(self, plotDict, rowData, index, plotType):
        """@brief Add to plot dict for a single trace.
           @param plotDict A dict containing x and Y values lists.
           @param rowData The source data.
           @param index The index to the field/column to be plotted.
           @param plotType The type of data being plotted."""
        invertKw = self._invertKW()

        ts = datetime.fromisoformat(rowData[BaseConstants.TIMESTAMP_INDEX])

        plotDict[GUI.X_AXIS_NAME].append(ts)
        if plotType == GUI.PLOT_TYPE_POWER_FACTOR:
            plotDict[GUI.DEFAULT_YAXIS_NAME].append(abs(rowData[index]))
        else:
            if invertKw:
                plotDict[GUI.DEFAULT_YAXIS_NAME].append(-rowData[index]/1000.0)
            else:
                plotDict[GUI.DEFAULT_YAXIS_NAME].append(rowData[index]/1000.0)

        # If plotting hourly we add a plot point at the end of the hour so
        # the user sees a stepped chart
        if self._resRadioButtonGroup.active == GUI.HOUR_RESOLUTION:
            ts=ts=ts.replace(minute=59, second=59, microsecond=999)
            plotDict[GUI.X_AXIS_NAME].append(ts)
            if plotType == GUI.PLOT_TYPE_POWER_FACTOR:
                plotDict[GUI.DEFAULT_YAXIS_NAME].append(abs(rowData[index]))
            else:
                if invertKw:
                    plotDict[GUI.DEFAULT_YAXIS_NAME].append(-rowData[index]/1000.0)
                else:
                    plotDict[GUI.DEFAULT_YAXIS_NAME].append(rowData[index]/1000.0)


        # If plotting daily we add a plot point at the end of the day so
        # the user sees a stepped chart
        if self._resRadioButtonGroup.active == GUI.DAY_RESOLUTION:
            ts=ts=ts.replace(hour=23, minute=59, second=59, microsecond=999)
            plotDict[GUI.X_AXIS_NAME].append(ts)
            if plotType == GUI.PLOT_TYPE_POWER_FACTOR:
                plotDict[GUI.DEFAULT_YAXIS_NAME].append(abs(rowData[index]))
            else:
                if invertKw:
                    plotDict[GUI.DEFAULT_YAXIS_NAME].append(-rowData[index]/1000.0)
                else:
                    plotDict[GUI.DEFAULT_YAXIS_NAME].append(rowData[index]/1000.0)

    def _readDataBase(self, db_file, startDateTime, stopDateTime, resolution):
        """@brief Read data from the database.
           @param db_file The database file to read.
           @param startDateTime The first date/time of interest as epoch time
           @param stopDateTime The last date/time of interest as epoch time.
           @param The resolution of the data to read.
           @return A dict containing the results of the DB read."""
        results={}
        conn = None
        try:
            conn = sqlite3.connect(db_file)

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
            self._uio.debug(f"{fName}: DB={db_file}, startDate={startDate}, stopDate={stopDate}, resolution={resolution}")

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
            responseTuple = self._executeSQL(conn, cmd)
            exeTime = time()-startT
            self._uio.debug(f"SQL command execution time {exeTime:.1f} seconds.")
            recordCount = responseTuple[0][0]
            self._uio.debug(f"recordCount = {recordCount}")

# PJA
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

                responseTuple = self._executeSQL(conn, cmd)
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
        finally:
            if conn:
                conn.close()
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
            key = BaseConstants.CT1_ACT_WATTS_INDEX
        elif sensorID == 2:
            key = BaseConstants.CT2_ACT_WATTS_INDEX
        elif sensorID == 3:
            key = BaseConstants.CT3_ACT_WATTS_INDEX
        elif sensorID == 4:
            key = BaseConstants.CT4_ACT_WATTS_INDEX
        elif sensorID == 5:
            key = BaseConstants.CT5_ACT_WATTS_INDEX
        elif sensorID == 6:
            key = BaseConstants.CT6_ACT_WATTS_INDEX

        wattHoursList = []
        pWattHoursList = []
        nWattHoursList = []
        lastTime = None
        pTotalkWh = 0.0
        nTotalkWh = 0.0
        for rowDict in rowDictList:
            thisTime = datetime.fromisoformat(rowDict[BaseConstants.TIMESTAMP_INDEX])
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



class AppConfig(ConfigBase):

    @staticmethod
    def GetAppConfigPath():
        """@brief Get the config path.
           @return The config path."""
        if platform.system() == 'Linux' and os.geteuid() == 0:
            homePath = "/root"
        else:
            homePath = os.path.expanduser("~")

        if not os.path.isdir(homePath):
            raise Exception(f"{homePath} HOME path does not exist.")

        top_level_config_folder = os.path.join(homePath, '.config')
        # Create the ~/.config folder if it does not exist
        if not os.path.isdir(top_level_config_folder):
            # Create the ~/.config folder
            os.makedirs(top_level_config_folder)

        progName = sys.argv[0]
        if progName.endswith('.py'):
            progName = progName[0:-3]
        progName = os.path.basename(progName).strip()
        config_folder = os.path.join(top_level_config_folder, progName)
        return config_folder

    DB_STORAGE_PATH = "DB_STORAGE_PATH"

    DEFAULT_CONFIG = {
        DB_STORAGE_PATH: GetAppConfigPath(), # By default the db's are stored in the same folder as the config files, but the user can re configure this.
        ConfigBase.CT6_DEVICE_DISCOVERY_INTERFACE: "",
        ConfigBase.LOCAL_GUI_SERVER_ADDRESS: "0.0.0.0",
        ConfigBase.LOCAL_GUI_SERVER_PORT: 10000,
        ConfigBase.SERVER_LOGIN: False,
        ConfigBase.SERVER_ACCESS_LOG_FILE: ""
    }

    def _enter_storage_path(self):
        """@brief Allow the user to enter the storage path."""
        # Ensure the user enters an IP address of an interface on this machine.
        while True:
            self.inputStr(AppConfig.DB_STORAGE_PATH, "Enter path to store database and config files (enter d for the default value).", False)
            config_path = self.getAttr(AppConfig.DB_STORAGE_PATH)
            if config_path.lower() == 'd':
                config_path = AppConfig.GetAppConfigPath()
                if not os.path.isdir(config_path):
                    os.makedirs(config_path)
                self.addAttr(AppConfig.DB_STORAGE_PATH, config_path)
            if os.path.isdir(config_path):
                break

            else:
                self._uio.error(f"{config_path} path not found.")

    def edit(self, key):
        """@brief Provide the functionality to allow the user to enter any ct4 config parameter
                  regardless of the config type.
           @param key The dict key to be edited.
           @return True if the config parameter was handled/updated"""
        if key == ConfigBase.CT6_DEVICE_DISCOVERY_INTERFACE:
            self._enterDiscoveryInterface()

        elif key == ConfigBase.LOCAL_GUI_SERVER_ADDRESS:
            localIPList = self._showLocalIPAddressList()
            # Ensure the user enters an IP address of an interface on this machine.
            while True:
                self.inputStr(ConfigBase.LOCAL_GUI_SERVER_ADDRESS, "Enter the local IP address to serve the GUI/Bokeh web interface from", False)
                ipAddr = self.getAttr(ConfigBase.LOCAL_GUI_SERVER_ADDRESS)
                if ipAddr in localIPList:
                    break
                else:
                    self._uio.error("{} is not a IP address of an interface on this machine.".format(ipAddr))

        elif key == ConfigBase.LOCAL_GUI_SERVER_PORT:
            self.inputDecInt(ConfigBase.LOCAL_GUI_SERVER_PORT, "Enter the TCP port to serve the GUI/Bokeh web interface from", minValue=1024, maxValue=65535)

        elif key == ConfigBase.SERVER_LOGIN:
            self.inputBool(ConfigBase.SERVER_LOGIN, "Enable server login")

        elif key == ConfigBase.SERVER_ACCESS_LOG_FILE:
            self._enterServerAccessLogFile()

        elif key == AppConfig.DB_STORAGE_PATH:
            self._enter_storage_path()

        elif key == ConfigBase.DB_HOST:
            self.inputStr(ConfigBase.DB_HOST, "Enter the address of the MYSQL database server", False)

        elif key == ConfigBase.DB_PORT:
            self.inputDecInt(ConfigBase.DB_PORT, "Enter TCP port to connect to the MYSQL database server", minValue=1024, maxValue=65535)

        elif key == ConfigBase.DB_USERNAME:
            self.inputStr(ConfigBase.DB_USERNAME, "Enter the database username", False)


class SQLite3DBClient(BaseConstants):
    """@brief Responsible for interfacing with the sqlite3 database."""

    DB_CONNECTION = "DB_CONNECTION"
    META_TABLE_UPDATE_TIME = "META_TABLE_UPDATE_TIME"
    HISTORY_RECORD_SET = "HISTORY_RECORD_SETS"
    RUNNING_ATTR_DICT = {DB_CONNECTION: None,
                         META_TABLE_UPDATE_TIME: None,
                         HISTORY_RECORD_SET: []}
    @staticmethod
    def GetQuotedValue(value):
        return '\"{}"'.format(str(value))

    @staticmethod
    def GetConfigPathFile(filename):
        """@brief Get the abs path to a file in the config path.
           @param filename The filename to reside in the config path.
           @return The abs file."""
        config_folder = AppConfig.GetAppConfigPath()
        # Create the ~/.config/<app name> folder if it does not exist
        if not os.path.isdir(config_folder):
            # Create the app config folder
            os.makedirs(config_folder)

        return os.path.join(config_folder, filename)

    @staticmethod
    def GetDeviceIPAddress(rxDict):
        """@brief Get the IP address of the device.
           @return the IP address of the device or None if the dict does not contain the device IP address."""
        ipAddress = None
        if SQLite3DBClient.IP_ADDRESS in rxDict:
            ipAddress = rxDict[SQLite3DBClient.IP_ADDRESS]
        return ipAddress

    @staticmethod
    def GetValidColName(colName):
        """@brief Get a valid database column name."""

        VALID_CHAR_LIST = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ$_"
        for aChar in colName:
            if aChar not in VALID_CHAR_LIST:
                colName = colName.replace(aChar, '_')

        return colName

    @staticmethod
    def GetDBFileList(db_storage_path):
        """@return A list of all the available db files."""
        db_file_list = []
        entry_list = os.listdir(db_storage_path)
        for entry in entry_list:
            abs_path = os.path.join(db_storage_path, entry)
            if abs_path.endswith(".db"):
                db_file_list.append(abs_path)
        return db_file_list

    def __init__(self, uio, options, app_config, start_db_update=True):
        """@brief Constructor
           @param uio A UIO instance.
           @param options The command line options instance.
           @param config A ConfigBase instance."""
        self._uio = uio
        self._options = options
        self._config = app_config
        self._running_attr_dicts = {} # This dict contains RUNNING_ATTR_DICT's
        self._conn = None
        self._last__record_device_time = None
        self._dbLock = threading.Lock()
        self._tableSchema = SQLite3DBClient.GetTableSchema(SQLite3DBClient.CT6_DB_TABLE_SCHEMA_SQLITE)
        self._dev_dict_queue = Queue()
        # Start the thread that reads from the queue containing the dev_dicts received from  CT6 units.
        if start_db_update:
            # Thread to read data from the above queue
            pthread = threading.Thread(target=self._process_dev_dict_queue)
            pthread.daemon = True
            pthread.start()

    def warn(self, msg):
        """@brief Show the user a warning level message.
           @param msg The message text."""
        if self._uio:
            self._uio.warn(msg)

    def info(self, msg):
        """@brief Show the user an info message.
           @param msg The message text."""
        if self._uio:
            self._uio.info(msg)

    def debug(self, msg):
        """@brief Show the user a debug message.
           @param msg The message text."""
        if self._uio:
            self._uio.debug(msg)

    def show_tables(self):
        """@brief List the tables."""
        try:
            db_storage_folder = self._config.getAttr(AppConfig.DB_STORAGE_PATH)
            db_file_list = SQLite3DBClient.GetDBFileList(db_storage_folder)
            for db_file in db_file_list:
                self._connect(db_file)
                conn = self._running_attr_dicts[db_file][SQLite3DBClient.DB_CONNECTION]
                cursor = conn.cursor()
                # Execute query to get table names
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                if len(tables) > 0:
                    for table in tables:
                        self._uio.info( table[0] )
                else:
                    self.info("No tables found.")

        finally:
            self.disconnect()

    def _report_memory_usage(self):
        """@brief Report the memory usage while running. Useful when debugging."""
        _, _, load15 = psutil.getloadavg()
        loadAvg = (load15/os.cpu_count()) * 100
        usedMB = psutil.virtual_memory()[3]/1000000
        freeMB = psutil.virtual_memory()[4]/1000000
        self.debug(f"CPU Load AVG: {loadAvg:.1f}, Used Mem (MB): {usedMB:.1f} Free Mem (MB): {freeMB:.1f}")

        objList = objgraph.most_common_types()
        for elemList in objList:
            _type = elemList[0]
            _count = elemList[1]
            self.debug(f"Found {_count: <8.0f} object of type {_type}")

    def _showdev_dict(self, dev_dict):
        """@brief Show the JSON data to the user.
           @return True if the device was shown."""
        ip_address = dev_dict[SQLite3DBClient.IP_ADDRESS]
        show_dev = False

        # If we have an include list check this device is in this list
        if self._options.include:
            include_list = self._options.include.split(",")
            if ip_address in include_list:
                show_dev = True
        else:
            show_dev = True

        # If we have an exclude list check for the device in this list.
        if self._options.exclude and show_dev:
            exclude_list = self._options.exclude.split(",")
            if ip_address in exclude_list:
                show_dev = False

        # Don't record data from CT6 units that are inactive.
        active = dev_dict[SQLite3DBClient.ACTIVE]
        if not active:
            show_dev = False

        if show_dev:
            rich.print_json(json.dumps(dev_dict))

        return show_dev

    def hear(self, dev_dict):
        """@brief Called when data is received from the device.
           @param dev_dict The CT6 device dict."""

        # We add to a queue and process the response in another thread
        # so as not to block the receipt of JSON messages from CT6 devices
        self._dev_dict_queue.put(dev_dict)

    def update_db_from_dev_dict_queue(self):
        """@brief Read all dev dicts from the queue and update db.
           @return The number of dev_dicts received."""
        msg_count = 0
        try:
            # Process all available dev_dict's in the queue
            while True:
                dev_dict = self._dev_dict_queue.get_nowait()
                if dev_dict:
                    self._handle_dev_dict(dev_dict)
                    msg_count += 1

        except Empty:
            pass

        except Exception:
            self._uio.errorException()

        return msg_count

    def _process_dev_dict_queue(self):
        """@brief Called periodically to read dev_dict's received from CT6 devices from
                  the _dev_dict_queue."""
        self._read_thread_running = True
        while self._read_thread_running:

            self.update_db_from_dev_dict_queue()

            sleep(0.25)

    def _handle_dev_dict(self, dev_dict):
        """@brief Called when data is received from the device.
           @param dev_dict The CT6 device dict."""
        self._record_device_timestamp(dev_dict, 1)
        self._report_memory_usage()
        process_dev_dict = True
        if SQLite3DBClient.IP_ADDRESS in dev_dict:
            if self._options.show:
                process_dev_dict = self._showdev_dict(dev_dict)

            if process_dev_dict:
                self._record_device_timestamp(dev_dict, 2)
                if SQLite3DBClient.ACTIVE in dev_dict:
                    active = dev_dict[SQLite3DBClient.ACTIVE]
                    # We don't record data from units that are not active
                    if active:
                        if SQLite3DBClient.UNIT_NAME in dev_dict:
                            unit_name = dev_dict[SQLite3DBClient.UNIT_NAME]
                            unit_name = unit_name.strip()
                            # We don't record data from units that don't have a name.
                            if len(unit_name) > 0:
                                # We lock around each database store action as hear() may not always
                                # be called from the same thread.
                                with self._dbLock:
                                    self._record_device_timestamp(dev_dict, 3)
                                    self._record(dev_dict)
                                    self._record_device_timestamp(dev_dict, 4)

    def _connect(self, db_file):
        """@brief Connect to an sqlite3 database.
           @param db_file The file containing the database.
           return True If the database has juct been created."""
        self.info(f"Connecting to {db_file}")
        db_created = False
        if not os.path.isfile(db_file):
            db_created = True
        # This will create the database if it is not present
        conn = sqlite3.connect(db_file)
        self.info("Connected.")
        # Create a RUNNING_ATTR_DICT for this db and add the database connection
        # to the dict of connections.
        self._running_attr_dicts[db_file] = copy.deepcopy(SQLite3DBClient.RUNNING_ATTR_DICT)
        self._running_attr_dicts[db_file][SQLite3DBClient.DB_CONNECTION] = conn
        return db_created

# PJA this must be called from the db thread !!!
    def disconnect(self):
        """@brief Disconnect from all the databases."""
        db_files = list(self._running_attr_dicts.keys())
        for db_file in db_files:
            conn = self._running_attr_dicts[db_file][SQLite3DBClient.DB_CONNECTION]
            if conn:
                conn.close()
            del self._running_attr_dicts[db_file]

    def _get_db_conn(self, db_file, dev_dict):
        """@brief Get the connection to the database.
           @param db_file The database file (full path).
           @param dev_dict The CT6 device dict.
           @return A connection to the database."""
        # If we don't yet have a connection to the database file.
        if db_file not in self._running_attr_dicts:
            created_db = self._connect(db_file)
            if created_db:
                # If we've just created the database ensure it contains the required tables.
                self._set_db_tables(dev_dict)
        return self._running_attr_dicts[db_file][SQLite3DBClient.DB_CONNECTION]

    def _get_running_attr_dict(self, assy):
        """@brief Get the running attr dict for the given assy.
           @param assy This may be the device assembly number as contained
                       in a dev_dict or the db file (this contains the assy text).
           @return A RUNNING_ATTR_DICT instance or None if not found"""
        running_attr_dict = None
        db_file_list = list(self._running_attr_dicts.keys())
        for db_file in db_file_list:
            if assy in db_file:
                running_attr_dict = self._running_attr_dicts[db_file]
        return running_attr_dict

    def _get_db_meta_table_update_time(self, assy):
        """@param assy This may be the device assembly number as contained
                       in a dev_dict or the db file (this contains the assy text).
           @return The time that the db meta table should be updated or None if it's never been updated."""
        running_attr_dict = self._get_running_attr_dict(assy)
        return running_attr_dict[SQLite3DBClient.META_TABLE_UPDATE_TIME]

    def _set_db_meta_table_update_time(self, assy, next_update_time):
        """@brief Set the time that the meta table data should be next updated.
           @param assy This may be the device assembly number as contained
                       in a dev_dict or the db file (this contains the assy text).
           @param next_update_time The time it should be updated."""
        running_attr_dict = self._get_running_attr_dict(assy)
        running_attr_dict[SQLite3DBClient.META_TABLE_UPDATE_TIME] = next_update_time

    def _get_db_history_record_sets(self, assy):
        """@param assy This may be the device assembly number as contained
                       in a dev_dict or the db file (this contains the assy text).
           @return A list containing threee lists
                   mins,
                   hours,
                   days
                   These are used to update these derived tables."""
        running_attr_dict = self._get_running_attr_dict(assy)
        record_sets = running_attr_dict[SQLite3DBClient.HISTORY_RECORD_SET]
        if len(record_sets) == 0:
            # We need lists to hold the min, hour and day records
            record_sets.append([])
            record_sets.append([])
            record_sets.append([])
        return record_sets

    def _get_db_cursor(self, dev_dict):
        """@brief Get a cursor connected to the correct database.
           @param dev_dict The CT6 device dict.
           @param db_conn_dict A dictionary that holds connection to each
                  database keyed by the database file.
           @return The cursor instance or None if no connection found."""
        cursor = None
        if SQLite3DBClient.ASSY in dev_dict:
            assy = dev_dict[SQLite3DBClient.ASSY]
            running_attr_dict = self._get_running_attr_dict(assy)
            conn = running_attr_dict[SQLite3DBClient.DB_CONNECTION]
            if conn:
                cursor = conn.cursor()
        return cursor

    def _execute_sql_cmd(self, cursor, cmd):
        """@brief Execute an SQL command."""
        self.debug(f">>>> SQL CMD: {cmd}")
        cursor.execute(cmd)

    def create_table(self, cursor, tableName, tableSchemaDict):
        """"@brief Create a table in the currently used database..
            @param cursor A cursor connected to the correct database.
            @param tableName The name of the database table.
            @param tableSchemaDict A python dictionary that defines the table schema.
                                   Each dictionary key is the name of the column in the table.
                                   Each associated value is the SQL definition of the column type (E.G VARCHAR(64), FLOAT(5,2) etc).
                                   Alternatively this may be a SQL string to create the table."""
        if isinstance(tableSchemaDict, str):
            cmd = f"CREATE TABLE {tableName} (" + tableSchemaDict + ");"
            self._execute_sql_cmd(cursor, cmd)
        else:
            sqlCmd = 'CREATE TABLE IF NOT EXISTS `{}` ('.format(tableName)
            for colName in list(tableSchemaDict.keys()):
                colDef = tableSchemaDict[colName]
                correctedColName = SQLite3DBClient.GetValidColName(colName)
                sqlCmd = sqlCmd + "`{}` {},\n".format(correctedColName, colDef)

            sqlCmd = sqlCmd[:-2]
            sqlCmd = sqlCmd + ");"
            self._execute_sql_cmd(cursor, sqlCmd)

    def _set_db_tables(self, dev_dict):
        """@brief Set the database tables. This is called after the database is created to
                  ensure the required tables are present.
           @param dev_dict The CT6 device dict."""
        self._record_device_timestamp(dev_dict, 1)
        if SQLite3DBClient.UNIT_NAME in dev_dict and SQLite3DBClient.PRODUCT_ID in dev_dict :
            unit_name = dev_dict[SQLite3DBClient.UNIT_NAME]
            if len(unit_name) == 0:
                ip_address = SQLite3DBClient.GetDeviceIPAddress(dev_dict)
                if ip_address:
                    self.warn(f"{ip_address}: Device name not set.")

                else:
                    self.warn("Found a CT6 device that does not have the device name field set.")

            # Don't record data unless the device name has been set.
            # The device name is used as the database name.
            else:
                self._record_device_timestamp(dev_dict, 2)
                cursor = self._get_db_cursor(dev_dict)
                # Create the database tables
                self.create_table(cursor, SQLite3DBClient.CT6_META_TABLE_NAME, SQLite3DBClient.CT6_DB_META_TABLE_SCHEMA_SQLITE)
                self.create_table(cursor, SQLite3DBClient.CT6_TABLE_NAME, self._tableSchema)
                self.create_table(cursor, SQLite3DBClient.MINUTE_RES_DB_DATA_TABLE_NAME, self._tableSchema)
                self.create_table(cursor, SQLite3DBClient.HOUR_RES_DB_DATA_TABLE_NAME, self._tableSchema)
                self.create_table(cursor, SQLite3DBClient.DAY_RES_DB_DATA_TABLE_NAME, self._tableSchema)
                try:
                    # Index on time stamp as most searches will be based around a date/time
                    cmd = f"CREATE INDEX {SQLite3DBClient.CT6_TABLE_NAME}_INDEX ON {SQLite3DBClient.CT6_TABLE_NAME} ({SQLite3DBClient.TIMESTAMP})"
                    self._execute_sql_cmd(cursor, cmd)
                    cmd = f"CREATE INDEX {SQLite3DBClient.MINUTE_RES_DB_DATA_TABLE_NAME}_INDEX ON {SQLite3DBClient.MINUTE_RES_DB_DATA_TABLE_NAME} ({SQLite3DBClient.TIMESTAMP})"
                    self._execute_sql_cmd(cursor, cmd)
                    cmd = f"CREATE INDEX {SQLite3DBClient.HOUR_RES_DB_DATA_TABLE_NAME}_INDEX ON {SQLite3DBClient.HOUR_RES_DB_DATA_TABLE_NAME} ({SQLite3DBClient.TIMESTAMP})"
                    self._execute_sql_cmd(cursor, cmd)
                    cmd = f"CREATE INDEX {SQLite3DBClient.DAY_RES_DB_DATA_TABLE_NAME}_INDEX ON {SQLite3DBClient.DAY_RES_DB_DATA_TABLE_NAME} ({SQLite3DBClient.TIMESTAMP})"
                    self._execute_sql_cmd(cursor, cmd)
                except:
                    pass

        self._record_device_timestamp(dev_dict, 3)

    def _record_device_timestamp(self, dev_dict, id):
        """@brief Record the time since device data was received from the CT6 device. This is
                  useful when debugging to see how long operations are taking.
           @param dev_dict The device dict.
           @param id A string identifying the call location."""
        start_time = dev_dict[YView.RX_TIME_SECS] # This field is not added to the database. It holds the time
                                                 # the CT6 dict was received on this machine.
        callerRef = inspect.stack()[2][4][0]
        callerRef = callerRef.strip()
        now = time()
        elapsed_ms =  int((now - start_time) * 1000)
        ms_since_last_call = -1
        if self._last__record_device_time is not None:
            ms_since_last_call = int((now - self._last__record_device_time) * 1000)

        self._uio.debug(f"DEVTS: {callerRef: >40} id={id} elapsed time = {elapsed_ms:d}/{ms_since_last_call:d} MS.")
        self._last__record_device_time = now

    def _record(self, dev_dict):
        """@brief Save the dev_dict data to a database.
           @param unit_name The name of the CT6 unit.
           @param dev_dict The CT6 device dict."""
        assy_label = dev_dict[SQLite3DBClient.ASSY]
        assy_label = assy_label.strip()
        db_storage_folder = self._config.getAttr(AppConfig.DB_STORAGE_PATH)
        db_file = os.path.join(db_storage_folder, assy_label + '.db')
        conn = self._get_db_conn(db_file, dev_dict)
        cursor = conn.cursor()
# PJA Handle exceptions adding to db ?
        # We update the meta table every 60 seconds, so fairly low CPU cost
        self._update_meta_table(cursor, dev_dict)
        # We update the CT6_SENSOR table for all CT6 stats/data received.
        self._add_device(cursor, dev_dict)
        cursor.close()
        conn.commit()

    def _add_device(self, cursor, dev_dict):
        """@brief Add device data to the database.
           @param cursor The cursor to execute the sql command.
           @param dev_dict The CT6 device dict."""
        start_time = dev_dict[YView.RX_TIME_SECS] # This field is not added to the database. It holds the time
                                                  # the dict was received on this machine.

        self._record_device_timestamp(dev_dict, 1)
        sensor_data_dict = {}
        # Record the time the message was received on the TCP socket rather than the time now
        # as CPU delays may cause dither in the time we get to this point.
        sensor_data_dict[SQLite3DBClient.TIMESTAMP] = datetime.fromtimestamp(start_time)

        # active power
        sensor_data_dict[SQLite3DBClient.CT1_ACT_WATTS]=dev_dict[SQLite3DBClient.CT1][SQLite3DBClient.PRMS]
        sensor_data_dict[SQLite3DBClient.CT2_ACT_WATTS]=dev_dict[SQLite3DBClient.CT2][SQLite3DBClient.PRMS]
        sensor_data_dict[SQLite3DBClient.CT3_ACT_WATTS]=dev_dict[SQLite3DBClient.CT3][SQLite3DBClient.PRMS]
        sensor_data_dict[SQLite3DBClient.CT4_ACT_WATTS]=dev_dict[SQLite3DBClient.CT4][SQLite3DBClient.PRMS]
        sensor_data_dict[SQLite3DBClient.CT5_ACT_WATTS]=dev_dict[SQLite3DBClient.CT5][SQLite3DBClient.PRMS]
        sensor_data_dict[SQLite3DBClient.CT6_ACT_WATTS]=dev_dict[SQLite3DBClient.CT6][SQLite3DBClient.PRMS]
        # Reactive power
        sensor_data_dict[SQLite3DBClient.CT1_REACT_WATTS]=dev_dict[SQLite3DBClient.CT1][SQLite3DBClient.PREACT]
        sensor_data_dict[SQLite3DBClient.CT2_REACT_WATTS]=dev_dict[SQLite3DBClient.CT2][SQLite3DBClient.PREACT]
        sensor_data_dict[SQLite3DBClient.CT3_REACT_WATTS]=dev_dict[SQLite3DBClient.CT3][SQLite3DBClient.PREACT]
        sensor_data_dict[SQLite3DBClient.CT4_REACT_WATTS]=dev_dict[SQLite3DBClient.CT4][SQLite3DBClient.PREACT]
        sensor_data_dict[SQLite3DBClient.CT5_REACT_WATTS]=dev_dict[SQLite3DBClient.CT5][SQLite3DBClient.PREACT]
        sensor_data_dict[SQLite3DBClient.CT6_REACT_WATTS]=dev_dict[SQLite3DBClient.CT6][SQLite3DBClient.PREACT]
        # Aparent power
        sensor_data_dict[SQLite3DBClient.CT1_APP_WATTS]=dev_dict[SQLite3DBClient.CT1][SQLite3DBClient.PAPPARENT]
        sensor_data_dict[SQLite3DBClient.CT2_APP_WATTS]=dev_dict[SQLite3DBClient.CT2][SQLite3DBClient.PAPPARENT]
        sensor_data_dict[SQLite3DBClient.CT3_APP_WATTS]=dev_dict[SQLite3DBClient.CT3][SQLite3DBClient.PAPPARENT]
        sensor_data_dict[SQLite3DBClient.CT4_APP_WATTS]=dev_dict[SQLite3DBClient.CT4][SQLite3DBClient.PAPPARENT]
        sensor_data_dict[SQLite3DBClient.CT5_APP_WATTS]=dev_dict[SQLite3DBClient.CT5][SQLite3DBClient.PAPPARENT]
        sensor_data_dict[SQLite3DBClient.CT6_APP_WATTS]=dev_dict[SQLite3DBClient.CT6][SQLite3DBClient.PAPPARENT]

        # Power factor
        sensor_data_dict[SQLite3DBClient.CT1_PF]=dev_dict[SQLite3DBClient.CT1][SQLite3DBClient.PF]
        sensor_data_dict[SQLite3DBClient.CT2_PF]=dev_dict[SQLite3DBClient.CT2][SQLite3DBClient.PF]
        sensor_data_dict[SQLite3DBClient.CT3_PF]=dev_dict[SQLite3DBClient.CT3][SQLite3DBClient.PF]
        sensor_data_dict[SQLite3DBClient.CT4_PF]=dev_dict[SQLite3DBClient.CT4][SQLite3DBClient.PF]
        sensor_data_dict[SQLite3DBClient.CT5_PF]=dev_dict[SQLite3DBClient.CT5][SQLite3DBClient.PF]
        sensor_data_dict[SQLite3DBClient.CT6_PF]=dev_dict[SQLite3DBClient.CT6][SQLite3DBClient.PF]

        # Misc
        sensor_data_dict[SQLite3DBClient.VOLTAGE]=dev_dict[SQLite3DBClient.CT1][SQLite3DBClient.VRMS]
        sensor_data_dict[SQLite3DBClient.FREQUENCY]=dev_dict[SQLite3DBClient.CT1][SQLite3DBClient.FREQ]
        sensor_data_dict[SQLite3DBClient.TEMPERATURE]=dev_dict[SQLite3DBClient.TEMPERATURE]
        sensor_data_dict[SQLite3DBClient.RSSI_DBM]=dev_dict[SQLite3DBClient.RSSI]

        self._record_device_timestamp(dev_dict, 2)

        # Add sensor data to the table containing all sensor data
        self._add_to_table(cursor, SQLite3DBClient.CT6_TABLE_NAME, sensor_data_dict)

        self._record_device_timestamp(dev_dict, 3)

        assy = dev_dict[SQLite3DBClient.ASSY]

        # Update the mins, hours and days tables.
        # This may block for some time if the ct6 app is started with a large database
        # that needs mins, hours and days tables recreating. This is ok because we have
        # a queue between the receipt of CT6 JSON messages and this thread that processes them.
        self._update_derived_tables(assy, sensor_data_dict, cursor)

    def _update_meta_table(self, cursor, dev_dict):
        """@brief Update the table containing meta data. This keeps the meta table up to date.
           @param cursor A cursor for the db.
           @param devDict The device dict."""
        assy = dev_dict[SQLite3DBClient.ASSY]
        _time = self._get_db_meta_table_update_time(assy)
        #If not set yet
        if _time is None:
            _time = time()
        # If it's time to update the meta data for this CT6 unit/db
        if time() >= _time:
            # We use replace into with an id (primary key) of 1 so that we only ever have one record in the table.
            cmd = 'REPLACE INTO {} (id,{},{},{},{},{},{},{},{}) VALUES("1","{}","{}","{}","{}","{}","{}","{}","{}");'.format(SQLite3DBClient.CT6_META_TABLE_NAME,
                                                                             SQLite3DBClient.HW_ASSY,
                                                                             SQLite3DBClient.UNIT_NAME,
                                                                             SQLite3DBClient.CT1_NAME,
                                                                             SQLite3DBClient.CT2_NAME,
                                                                             SQLite3DBClient.CT3_NAME,
                                                                             SQLite3DBClient.CT4_NAME,
                                                                             SQLite3DBClient.CT5_NAME,
                                                                             SQLite3DBClient.CT6_NAME,
                                                                             dev_dict[SQLite3DBClient.ASSY],
                                                                             dev_dict[SQLite3DBClient.UNIT_NAME],
                                                                             dev_dict[SQLite3DBClient.CT1][SQLite3DBClient.NAME],
                                                                             dev_dict[SQLite3DBClient.CT2][SQLite3DBClient.NAME],
                                                                             dev_dict[SQLite3DBClient.CT3][SQLite3DBClient.NAME],
                                                                             dev_dict[SQLite3DBClient.CT4][SQLite3DBClient.NAME],
                                                                             dev_dict[SQLite3DBClient.CT5][SQLite3DBClient.NAME],
                                                                             dev_dict[SQLite3DBClient.CT6][SQLite3DBClient.NAME])
            self._execute_sql_cmd(cursor, cmd)
            # We update the meta table every 60 seconds for each CT6 when we received the dev_dict
            self._set_db_meta_table_update_time(assy, time() + 60)

    def _update_derived_tables(self, db_file, sensor_data_dDict, cursor):
        """@brief Update the min, hour and day tables in the database with new data just read from a sensor.
           @param db_file The db_file to be updated.
           @param dev_dict The dict containing the device data to be added to the database.
           @param cursor The cursor to execute the sql command."""
        thisRecord = sensor_data_dDict
        lowResTableList = SQLite3DBClient.LOW_RES_DATA_TABLE_LIST
        recordSets = self._get_db_history_record_sets(db_file)

        # First derived table (minute)
        tableName = lowResTableList[0]
        recordSet = recordSets[0]
        # If we've moved into the next minute
        if len(recordSet) > 0 and (thisRecord[BaseConstants.TIMESTAMP].minute != recordSet[0][BaseConstants.TIMESTAMP].minute):
            # Ensure we have several records as we may get two readings in the same second (microseconds apart) but we don't want to add
            # data to the database unless it's valid. We should have 60 second values in the list but will vary as
            # poll/response and network delays to-from the CT6 device may move the sampling times.
            if len(recordSet) >= 3:
                # Use a pandas data frame to calculate the mean values for each column
                df = pd.DataFrame(recordSet)
                self._add_to_table(cursor, tableName, df.mean())
                recordSet.clear() # Clear rather than creating a new list so we don't change it's reference
                recordSet.append(thisRecord) # Add the new data to the next record set.
                self._uio.debug(f"{db_file}: Record added to {tableName} table: {datetime.now()}")

                # Second derived table (hour)
                tableName = lowResTableList[1]
                recordSet = recordSets[1]
                # If we've moved into the next hour
                if len(recordSet) > 0 and (thisRecord[BaseConstants.TIMESTAMP].hour != recordSet[0][BaseConstants.TIMESTAMP].hour):
                    # Use a pandas data frame to calculate the mean values for each column
                    df = pd.DataFrame(recordSet)
                    self._add_to_table(cursor, tableName, df.mean())
                    recordSet.clear() # Clear rather than creating a new list so we don't change it's reference
                    recordSet.append(thisRecord) # Add the new data to the next record set.
                    self._uio.debug(f"{db_file}: Record added to {tableName} table: {datetime.now()}")

                    # Third derived table (day)
                    tableName = lowResTableList[2]
                    recordSet = recordSets[2]
                    # If we've moved into the next day
                    if len(recordSet) > 0 and (thisRecord[BaseConstants.TIMESTAMP].day != recordSet[0][BaseConstants.TIMESTAMP].day):
                        # Use a pandas data frame to calculate the mean values for each column
                        df = pd.DataFrame(recordSet)
                        self._add_to_table(cursor, tableName, df.mean())
                        recordSet.clear() # Clear rather than creating a new list so we don't change it's reference
                        recordSet.append(thisRecord) # Add the new data to the next record set.

                        self._uio.debug(f"{db_file}: Record added to {tableName} table: {datetime.now()}")

                    else:
                        # Add to the set of record to be averaged later
                        recordSet.append(thisRecord)

                else:
                    # Add to the set of record to be averaged later
                    recordSet.append(thisRecord)

        else:
            # Add to the set of record to be averaged later
            recordSet.append(thisRecord)

    def _add_to_table(self, cursor, tableName, dictData):
        """@brief Add data to table. We assume this is in the currently selected database.
           @param cursor The cursor to execute the sql command.
           @param tableName The name of the table to add to. If the table does not exist it will be created.
           @param dictData The dict holding the data to be added to the table.
           @param databaseIF The database interface instance."""
        # Saw an issue on some platforms where the pandas dataframe returned the timestamp with 9 digits below the
        # decimal point,(ns resolution). This caused problems later when datetime.fromisoformat() is called to
        # read the data as it throws an exception. Therefore we convert the datetime instance to a string and
        # chop it down if required.
        dictDataCopy = copy.deepcopy(dictData)
        tsStr = str(dictDataCopy[SQLite3DBClient.TIMESTAMP])
        if len(tsStr) > 26:
            dictDataCopy[SQLite3DBClient.TIMESTAMP] = tsStr[:26]

        keyList = list(dictDataCopy.keys())
        valueList = []
        for key in keyList:
            valueList.append(str(dictDataCopy[key]))
        sql = 'INSERT INTO `' + tableName
        sql += '` ('
        sql += ', '.join(keyList)
        sql += ') VALUES ('
        sql += ', '.join(map(SQLite3DBClient.GetQuotedValue, valueList))
        sql += ');'
        self._execute_sql_cmd(cursor, sql)