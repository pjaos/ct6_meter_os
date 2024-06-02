class UO(object):
    """@brief Responsible for displaying messages to the user over the serial interface to the picow."""

    INFO_LEVEL  = "INFO:  "
    ERROR_LEVEL = "ERROR: "
    DEBUG_LEVEL = "DEBUG: "

    @staticmethod
    def Info(uo, msg):
        """@brief Show an info message.
           @param msg The message to display."""
        if uo:
            uo.info(msg)
            
    @staticmethod
    def Debug(uo, msg):
        """@brief Show a debug message.
           @param msg The message to display."""
        if uo:
            uo.debug(msg)

    def __init__(self, enabled=True, debug_enabled=True):
        """@brief Constructor.
           @param enabled If True messages will be displayed.
           @param enable_debug If True then debug messages will be displayed."""
        self._enabled = enabled
        self._debug_enabled = debug_enabled
        
    def setEnabled(self, enabled):
        """@brief Enable/Disable the user output. You may want to disable user output
                  to speed up the code so that it's not sending data out of the serial port.
           @param enabled If True then enable the user output."""
        self._enabled = enabled

    def info(self, msg):
        """@brief Display an info level message.
           @param msg The message text."""
        self._print(UO.INFO_LEVEL, msg)

    def error(self, msg):
        """@brief Display an error level message.
           @param msg The message text."""
        self._print(UO.ERROR_LEVEL, msg)

    def debug(self, msg):
        """@brief Display a debug level message.
           @param msg The message text."""
        if self._debug_enabled:
            self._print(UO.DEBUG_LEVEL, msg)

    def _print(self, prefix, msg):
        """@brief display a message.
           @param prefix The prefix text that defines the message level.
           @param msg The message text."""
        if self._enabled:
            print('{}{}'.format(prefix, msg))

class UOBase(object):
    """brief A base class for classes that use UO instances to send data to the user.
             This provides instance methods to send data to the user."""

    def __init__(self, uo=None):
        """@brief Constructor
           @param uo A UO instance for presenting data to the user. If Left as None
                     no data is sent to the user."""
        self._uo = uo

    def _info(self, message):
        """@brief Show an info level message to the user.
           @param message The message to be displayed."""
        if self._uo:
            self._uo.info(message)

    def _debug(self, message):
        """@brief Show a debug level message to the user.
           @param message The message to be displayed."""
        if self._uo:
            self._uo.debug(message)
