import json

from constants import Constants

class MachineConfig(object):
    """@brief Responsible for management of config attributes for the machine.
              The machine configuration is saved to flash for persistent storage."""

    CONFIG_FILENAME         = "this.machine.cfg"
    FACTORY_CONFIG_FILENAME = "factory.cfg"

    @staticmethod
    def Merge(resultDict, dict1, dict2):
        """@brief Merge dict 2 into dict 1. The resultDict will contain all the keys from
                  dict 1. Values from dict 2 will override those held in dict 1.
                  This method allows merging of dicts that contain dicts."""
        for dict1Key in dict1:
            if dict1Key in dict2:
                dict1Value = dict1[dict1Key]
                dict2Value = dict2[dict1Key]
                if isinstance(dict1Value, dict) and isinstance(dict2Value, dict):
                    subDict = {}
                    MachineConfig.Merge(subDict, dict1Value, dict2Value)
                    resultDict[dict1Key]=subDict
                else:
                    resultDict[dict1Key] = dict2[dict1Key]

            else:
                resultDict[dict1Key]=dict1[dict1Key]

    def __init__(self, defaultConfigDict):
        """@brief Constructor."""
        self._defaultConfigDict = defaultConfigDict
        self._configDict = self._defaultConfigDict
        self.load()

    def merge(self, cfgDict):
        """@brief Merge the cfgDict into the config dict. All the key value pairs in
                  cfgDict are copied into the internal config dict."""
        for key in cfgDict:
            self._configDict[key] = cfgDict[key]

    def load(self, purgeKeys=True, filename=None):
        """@brief Load the config. If the config file exists in flash then this will
                  be loaded. If not then the default config is loaded and saved to flash.
           @param purgeKeys If True remove unused (not in default dict) keys.
           @param filename The filename to load the config from. If this is unset then the
                  MachineConfig.CONFIG_FILENAME file is used."""
        # The default config filename.
        cfgFilename = MachineConfig.CONFIG_FILENAME
        # If the caller has defined a non default file
        if filename is not None:
            cfgFilename = filename

        configDict = {}
        try:
            with open(cfgFilename, "r") as read_file:
                 configDict = json.load(read_file)
        except:
             configDict = self._defaultConfigDict

        # Merge the factory config into the machine config file if present.
        factoryDict = {}
        try:
            with open(MachineConfig.FACTORY_CONFIG_FILENAME, "r") as read_file:
                 factoryDict = json.load(read_file)

            for key in factoryDict:
                configDict[key] =  factoryDict[key]

        except:
             pass

        # Merge the self._defaultConfigDict and configDict dicts so that we ensure we have all the keys from
        # self._defaultConfigDict. This ensures if keys are added to self._defaultConfigDict then they are
        # automatically added to any saved config.
        self._configDict = {}
        MachineConfig.Merge(self._configDict, self._defaultConfigDict, configDict)
        self.store()

    def store(self, filename=None, cfgDict=None):
        """@brief Save the config dict to flash.
           @param filename The filename in which to store the config. If this is unset then the
                  MachineConfig.CONFIG_FILENAME file is used.
           @param cfgDict The dictionary to store. If left as None then the machine config
                  dictionary is stored."""
        if cfgDict is None:
            cfgDict = self._configDict

        # The default config filename.
        cfgFilename = MachineConfig.CONFIG_FILENAME
        if filename is not None:
            cfgFilename = filename
        fd = open(cfgFilename, 'w')
        fd.write( json.dumps(cfgDict)  )
        fd.close()

    def isParameter(self, key):
        """@brief Determine if the key is present in the config Dictionary.
           @return True if the key is present in the config dictionary."""
        present = False
        if key in self._configDict:
            present = True
        return present

    def get(self, _key):
        """@brief Get a value from the config dict.
           @param _key This may be
                       - A string that is the key to a dict value at the top level.
                       - A list of keys that lead to the value in the dict.
           @return The attribute value or None if not found."""

        if isinstance(_key, str):
            if _key in self._configDict:
                currentValue = self._configDict[_key]
            else:
                currentValue = None
        else:
            currentValue = self._configDict
            for key in _key:
                if key in currentValue:
                    currentValue = currentValue[key]
                else:
                    currentValue = None

        return currentValue

    def set(self, _key, value):
        """@brief Set the value of a dict key.
           @param _key This may be
                       - A string that is the key to a dict value at the top level.
                       - A list of keys that lead to the value in the dict.
           @param value The value to set the attribute to."""
        if isinstance(_key, str):
            self._configDict[_key]=value

        else:
            currentValue = self._configDict
            for key in _key:
                if key in currentValue:
                    if isinstance(currentValue[key], dict):
                        currentValue = currentValue[key]
            currentValue[key]=value

        self.store()

    def setDefaults(self):
        """@brief Reset the dict to the defaults."""
        # We set all config values to defaults except for the running app because we
        # don't want to change to a different software release when the WiFi button
        # is held down to force config defaults.
        currentApp = None
        if Constants.RUNNING_APP_KEY and Constants.RUNNING_APP_KEY in self._configDict:
            currentApp = self._configDict[Constants.RUNNING_APP_KEY]
        self._configDict = self._defaultConfigDict
        if currentApp:
            self._configDict[Constants.RUNNING_APP_KEY] = currentApp
        self.store()

    def __repr__(self):
        """@brief Get a string representation of the config instance."""
        return str(self._configDict)

    def saveFactoryConfig(self, requiredKeys):
        """@brief Save the factory configuration file.
           @param requiredKeys A list of the dict keys required.
           @return The filename the factory config is saved to."""
        factoryDict = {}
        for key in requiredKeys:
            if key in self._configDict:
                factoryDict[key] = self._configDict[key]
        self.store(filename=MachineConfig.FACTORY_CONFIG_FILENAME, cfgDict=factoryDict)
        return MachineConfig.FACTORY_CONFIG_FILENAME

    def resetWiFiConfig(self):
        """@breif Reset the WiFi configuration to the default values."""
        self._configDict[Constants.WIFI_KEY] = Constants.DEFAULT_CONFIG[Constants.WIFI_KEY]
        self.store()

# Test code

#    mc = MachineConfig()
#    value = mc.get( MachineConfig.CODES_TO_VOLTS_KEY )
#    print("PJA: 1 value="+str(value))
#    print("PJA: 1 mc=<{}>".format( str(mc) ))

#    keyTuple=(MachineConfig.WIFI_KEY, MachineConfig.SSID_KEY)
#    value = mc.get( keyTuple )
#    print("PJA: 2 value="+str(value))
#    print("PJA: 2 mc=<{}>".format( str(mc) ))

#    value=337
#    mc.set( MachineConfig.CODES_TO_VOLTS_KEY, value )
#    print("PJA: 3 Set {} to ="+str(value))
#    print("PJA: 3 mc=<{}>".format( str(mc) ))

#    value="PICOW_0123"
#    mc.set( keyTuple, value )
#    print("PJA: 4 value="+str(value))
#    print("PJA: 4 mc=<{}>".format( str(mc) ))

#    mc.setDefaults()

#    print("PJA: DEFAULT: mc=<{}>".format( str(mc) ))


