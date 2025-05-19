import threading
import itertools
import inspect

from time import time

from datetime import datetime

from bokeh.layouts import column, row
from bokeh.models import HoverTool
from bokeh.models import TabPanel, Tabs
from bokeh.models.css import Styles
from bokeh.plotting import figure, ColumnDataSource
from bokeh.palettes import Category20_20

from lib.base_constants import BaseConstants
from lib.db_handler import DBHandler
from lib.config import ConfigBase

from ct6.gui_base import GUIBase

class GUI(GUIBase):
    """@brief Responsible for providing the GUI dashboard for viewing data from CT6 devices.
              This is provided over a Web interface."""

    def __init__(self, uio, options, config, loginCredentialsFile):
        """@brief Constructor.
           @param uio A UIO instance responsible for stdout/stdin input output.
           @param options The command line argparse options instance.
           @param config The dash app config.
           @param loginCredentialsFile A file containing the login credentials or None if no server authentication is required."""
        super().__init__(uio,
                         options,
                         config,
                         loginCredentialsFile,
                         config.getAttr(CT6DashConfig.LOCAL_GUI_SERVER_ADDRESS),
                         config.getAttr(CT6DashConfig.LOCAL_GUI_SERVER_PORT),
                         config.getAttr(CT6DashConfig.SERVER_ACCESS_LOG_FILE) )
        self._dbIF = None

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
        start_epoch, stop_epoch = self._getStartStopDateTimes()
        # Run thread to recover the data from the database.
        threading.Thread( target=self._readDataBase, args=(start_epoch,
                                                        stop_epoch,
                                                        self._resRadioButtonGroup.active)).start()

    def _showACVolts(self):
        """@brief Show the AC volts plot."""
        self._updatePlotType = GUI.PLOT_TYPE_AC_VOLTS
        self._startUpdateTime = time()
        self._clearSummaryTable()
        self._enableReadDBButtons(False)
        self._showStatus(0, "Reading Data...")
        start_epoch, stop_epoch = self._getStartStopDateTimes()
        # Run thread to recover the data from the database.
        threading.Thread( target=self._readDataBase, args=(start_epoch,
                                                        stop_epoch,
                                                        self._resRadioButtonGroup.active)).start()

    def _showACFreq(self):
        """@brief Show the AC freq plot."""
        self._updatePlotType = GUI.PLOT_TYPE_AC_FREQ
        self._startUpdateTime = time()
        self._clearSummaryTable()
        self._enableReadDBButtons(False)
        self._showStatus(0, "Reading Data...")
        start_epoch, stop_epoch = self._getStartStopDateTimes()
        # Run thread to recover the data from the database.
        threading.Thread( target=self._readDataBase, args=(start_epoch,
                                                        stop_epoch,
                                                        self._resRadioButtonGroup.active)).start()

    def _showTemp(self):
        """@brief Show unit temperature plot."""
        self._updatePlotType = GUI.PLOT_TYPE_TEMP
        self._startUpdateTime = time()
        self._clearSummaryTable()
        self._enableReadDBButtons(False)
        self._showStatus(0, "Reading Data...")
        start_epoch, stop_epoch = self._getStartStopDateTimes()
        # Run thread to recover the data from the database.
        threading.Thread( target=self._readDataBase, args=(start_epoch,
                                                        stop_epoch,
                                                        self._resRadioButtonGroup.active)).start()

    def _showRSSI(self):
        """@brief Show the WiFi RSSI plot."""
        self._updatePlotType = GUI.PLOT_TYPE_RSSI
        self._startUpdateTime = time()
        self._clearSummaryTable()
        self._enableReadDBButtons(False)
        self._showStatus(0, "Reading Data...")
        start_epoch, stop_epoch = self._getStartStopDateTimes()
        # Run thread to recover the data from the database.
        threading.Thread( target=self._readDataBase, args=(start_epoch,
                                                        stop_epoch,
                                                        self._resRadioButtonGroup.active)).start()

    def _getSelectedDataBase(self):
        """@brief The user can select the tab on the GUI. This tab is the name of the database for the CT6
                  unit of interest.
           @return The name of the selected database of None if no database found."""
        return self._getSelectedDevice()

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
        rightPanel = column(children=[self._allTabsPanel], sizing_mode="stretch_both")
        mainPanel = row(children=[controlPanel, rightPanel], sizing_mode="stretch_both")

        self._updateYAxis()

        self._doc.add_root( mainPanel )

        self._doc.theme = theme
        self._doc.add_periodic_callback(self._updateCallBack, 100)

        # On Startup set the start/stop dates to show today's data.
        self._todayButtonHandler(None)

        self._showStatus(5, f"Software Version: {self._programVersion}")

    def _plotSingleField(self, plotName, units, appPlotField, rxDict):
        """@brief Show a single value list on the plot area
           @param plotName The name of the plot.
           @param units The unit (Y axis label).
           @param appPlotField The field in the dict to plot.
           @param rxDict The dict containing the value/s to plot."""
        try:
            self._showStatus(0, "Plotting Data...")

# PJA            self._plotPanel.legend.visible=False

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

    def _readDataBase(self, startDateTime, stopDateTime, resolution):
        """@brief Read data from the database.
           @param startDateTime The first date/time of interest as epoch time
           @param stopDateTime The last date/time of interest as epoch time.
           @param The resolution of the data to read.
           @return A dict containing the results of the DB read."""
        results={}
        if startDateTime is None:
            self._error("The start time is not correct.")
            self._sendEnableActionButtonsMsg(True)
            return results

        if stopDateTime is None:
            self._error("The stop time is not correct.")
            self._sendEnableActionButtonsMsg(True)
            return results

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

class CTDBClient(DBHandler):
    """@brief Responsible for CT6 sensor database access."""

    def __init__(self, uio, config):
        """@brief Constructor
           @param uio A UIO instance.
           @param config A CT6DashConfig instance."""
        super().__init__(uio, config)
        self._metaTableSchema = DBHandler.GetTableSchema( CTDBClient.CT6_DB_META_TABLE_SCHEMA )
        self._tableSchema = DBHandler.GetTableSchema( CTDBClient.CT6_DB_TABLE_SCHEMA )
