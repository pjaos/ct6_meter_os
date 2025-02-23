import json
import time
from constants import Constants

class MeanCT6StatsDict(object):
    """@brief Responsible for accepting CT6 stats dicts and averaging the values
              to provide a mean stats dict when required."""

    @staticmethod
    def GetMean(currentValue, count, newValue):
        """@brief Get the cumulative mean using the method suggested by Byan Montgomery to fix
                  an error on the previous averaging code."""
        return ((currentValue * (count - 1)) + newValue) / count

    def __init__(self,
                 numeric_ct_field_list,
                 non_numeric_ct_field_list,
                 numeric_field_list,
                 non_numeric_field_list):
        self._numeric_ct_field_list = numeric_ct_field_list
        self._non_numeric_ct_field_list = non_numeric_ct_field_list
        self._numeric_field_list = numeric_field_list
        self._non_numeric_field_list = non_numeric_field_list
        self._init_stats()

    def _init_stats(self):
        """@brief Init the stats to start/restart the averaging process."""
        self._statsDict = None
        self._statsDictCount = 0

    def addStatsDict(self, statsDict):
        """@brief Add a CT6 stats dict.
           @param statsDict The dict holding the port stats and CT6 unit stats."""
        if statsDict:
            self._statsDictCount += 1

            if self._statsDict:
                for ct in Constants.VALID_CT_ID_LIST:
                    ct = f"CT{ct}"
                    if ct in statsDict and ct in self._statsDict:
                        srcSubDict = statsDict[ct]
                        destSubDict = self._statsDict[ct]

                        # Update numeric CT port fields
                        # Update a cumulative average of this and the previous value.
                        # This is reset when getStatsDict() is called when the averaging restarts.
                        for key in self._numeric_ct_field_list:
                            if key in srcSubDict and key in destSubDict:
                                destSubDict[key] = MeanCT6StatsDict.GetMean(destSubDict[key], self._statsDictCount, srcSubDict[key])

                        # For non numeric CT port fields, copy the latest values across.
                        for key in self._non_numeric_ct_field_list:
                            if key in srcSubDict and key in destSubDict:
                                destSubDict[key] = srcSubDict[key]

                # Calc averages for top level numeric fields
                for key in self._numeric_field_list:
                    if key in statsDict and key in self._statsDict:
                        self._statsDict[key] = MeanCT6StatsDict.GetMean(self._statsDict[key], self._statsDictCount, statsDict[key])

                # For non numeric top level fields, copy the latest values across.
                for key in self._non_numeric_field_list:
                    if key in statsDict and key in self._statsDict:
                        self._statsDict[key] = statsDict[key]

            else:
                # We need a deepcopy of the statsDict as we need to ensure there are no references to the dict
                # that could be updated outside this MeanCT6StatsDict instance.
                # copy.deepcopy is not available in micropython by default.
                # Therefore we convert to and from a json string to get a copy of the statsDict.
                statsDictStr = json.dumps(statsDict)
                self._statsDict = json.loads(statsDictStr)

    def _add_send_time(self, stats_dict):
        """@brief Add the timesent to the stats_dict."""
        # Add the time (UTC) that it's being sent to the stats dict.
        # This method is called to get a snapshot of the stats before it is sent to its destination.
        # An NTP server is used to update this system time periodically on the CT6 unit.
        # This returns a list containing
        #
        # year includes the century (for example 2014).
        # month is 1-12
        # mday is 1-31
        # hour is 0-23
        # minute is 0-59
        # second is 0-59
        # weekday is 0-6 for Mon-Sun
        # yearday is 1-366
        # The epoch time in seconds for the above.
        epoch_time = time.time()
        t_list = list(time.gmtime(epoch_time))
        t_list.append(epoch_time)
        stats_dict[Constants.TIMESENT] = t_list

    def getStatsDict(self):
        """@brief Get the CT6 stats dict. This is not thread safe. It must not be called during
                  addStatsDict execution.
           @return The CT6 stats dict all numeric values will be the average of all values added.
                   None is returned if no statsDict data is available."""
        statsDict = self._statsDict
        if statsDict:
            self._add_send_time(statsDict)
        self._init_stats()
        return statsDict