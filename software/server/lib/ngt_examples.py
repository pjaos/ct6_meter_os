import argparse

from p3lib.uio import UIO
from p3lib.helper import logTraceBack

from ngt import TabbedNiceGui, YesNoDialog

from nicegui import ui

class NGT_Examples(object):

    def tabbedGUI(self, debugEnabled):
            tabNameList = ('TAB 0 NAME', 
                           'TAB 1 NAME', 
                           'TAB 2 NAME')
            # This must have the same number of elements as the above list
            tabMethodInitList = [self._initTab0, 
                                 self._initTab1, 
                                 self._initTab2]

            tabbedNiceGui = TabbedNiceGui(debugEnabled=debugEnabled)
            tabbedNiceGui.initGUI(tabNameList, 
                                  tabMethodInitList, 
                                  pageTitle="Application Name")

    def _initTab0(self):
        with ui.row():
            self.yesNoDialog1()
            self.yesNoDialog2()
            self.yesNoDialog3()
    
    def _initTab1(self):
        pass
    
    def _initTab2(self):
        pass
    
    def yesNoDialog1(self):
        """@brief Show a dialog with a prompt and yes/no buttons."""
        self._dialog1 = YesNoDialog("The dialog message asking for a yes/no selection.", self.successMethod1, failureMethod=self.failureMethod1)
        ui.button('Show Dialog 1', on_click=lambda: self._dialog1.show() )

    def yesNoDialog2(self):
        """@brief Show a dialog with a prompt and yes/no buttons and a text input field."""
        self._dialog2 = YesNoDialog("The dialog message asking for a yes/no selection with text input field.", self.successMethod2)
        self._dialog2.addField("Name", YesNoDialog.TEXT_INPUT_FIELD_TYPE)
        self._dialog2.addField("Date", YesNoDialog.DATE_INPUT_FIELD)
        self._dialog2.addField("Time", YesNoDialog.TIME_INPUT_FIELD)
        ui.button('Show Dialog 2', on_click=lambda: self._dialog2.show() )

    def yesNoDialog3(self):
        """@brief Show a dialog with a prompt and yes/no buttons and a number of input fields."""
        self._dialog3 = YesNoDialog("The dialog message asking for a yes/no selection with text and number input fields.", self.successMethod3)
        self._dialog3.addField("Name", YesNoDialog.TEXT_INPUT_FIELD_TYPE, value="Paul")
        self._dialog3.addField("Age", YesNoDialog.NUMBER_INPUT_FIELD_TYPE, minNumber=1, maxNumber=100)
        self._dialog3.addField("Male", YesNoDialog.SWITCH_INPUT_FIELD_TYPE)
        self._dialog3.addField("Letter", YesNoDialog.DROPDOWN_INPUT_FIELD, options=["A4","B4"])
        self._dialog3.addField("Color", YesNoDialog.COLOR_INPUT_FIELD)
        self._dialog3.addField("Height", YesNoDialog.KNOB_INPUT_FIELD)
        ui.button('Show Dialog 3', on_click=lambda: self._dialog3.show() )

    def successMethod1(self):
        """@brief Called when the success button is selected by the user."""
        ui.notify("Success button selected")

    def failureMethod1(self):
        """@brief Called when the failure button is selected by the user."""
        ui.notify("Failure button selected")

    def successMethod2(self):
        """@brief Called when the success button is selected by the user."""
        ui.notify(f"Success button selected. NAME = {self._dialog2.getValue('Name')}")

    def successMethod3(self):
        """@brief Called when the success button is selected by the user."""
        ui.notify("Success button selected.")
        ui.notify(f"Name = {self._dialog3.getValue('Name')}" )
        ui.notify(f"Age = {self._dialog3.getValue('Age')}" )
        ui.notify(f"Male = {self._dialog3.getValue('Male')}" )
        ui.notify(f"Letter = {self._dialog3.getValue('Letter')}" )
        ui.notify(f"Color = {self._dialog3.getValue('Color')}" )
        ui.notify(f"AVALUE = {self._dialog3.getValue('AVALUE')}" )
        ui.notify(f"File = {self._dialog3.getValue('File')}" )

def main():
    """@brief Program entry point"""
    uio = UIO()
    options = None

    try:
        parser = argparse.ArgumentParser(description="ngt examples.",
                                         formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument("-d", "--debug",  action='store_true', help="Enable debugging.")
        parser.add_argument("-enable_syslog", action='store_true', help="Enable syslog.")
 
        options = parser.parse_args()
        uio.enableDebug(options.debug)
        uio.logAll(True)
        uio.enableSyslog(options.enable_syslog, programName="ngt")
        if options.enable_syslog:
            uio.info("Syslog enabled")

        ngtExamples = NGT_Examples()
        
        ngtExamples.tabbedGUI(options.debug)

    #If the program throws a system exit exception
    except SystemExit:
        pass
    #Don't print error information if CTRL C pressed
    except KeyboardInterrupt:
        pass
    except Exception as ex:
        logTraceBack(uio)

        if not options or options.debug:
            raise
        else:
            uio.error(str(ex))


# Note __mp_main__ is used by the nicegui module
if __name__ in {"__main__", "__mp_main__"}:
    main()