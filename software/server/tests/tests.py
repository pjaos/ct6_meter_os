import unittest
import string
import copy
from mean_stats import MeanCT6StatsDict
from random import randint, choices

class TestCT6(unittest.TestCase):

    CT1 = 'CT1'
    PRMS = 'PRMS'
    NAME = 'NAME'
    RSSI = 'RSSI'
    ASSY = 'ASSY'

    TEST_DICT = {
        CT1: {
            NAME: 1.0,
            PRMS: 0.0,
        },
        RSSI: -54.01538,
        ASSY: "ASY0398_V001.600_SN00001831",
    }

    NUMERIC_CT_FIELD_LIST = (PRMS,)
    NON_NUMERIC_CT_FIELD_LIST = (NAME,)
    NUMERIC_FIELD_LIST = (RSSI,)
    NON_NUMERIC_FIELD_LIST = (ASSY,)

    COUNT = 1000

    def setUp(self):
        """This method runs before each test."""
        self.mean_stats = MeanCT6StatsDict(TestCT6.NUMERIC_CT_FIELD_LIST,
                                           TestCT6.NON_NUMERIC_CT_FIELD_LIST,
                                           TestCT6.NUMERIC_FIELD_LIST,
                                           TestCT6.NON_NUMERIC_FIELD_LIST)

    def test_ct_prms(self):
        """@brief Check the CT PRMS field mean value is calculated correctly.
                  This checks that CT mean values are calculated correctly."""
        stats_dict = copy.deepcopy(TestCT6.TEST_DICT)
        prms_total = 0
        for _ in range(0,TestCT6.COUNT):
            v = randint(-10000, 10000)
            stats_dict[TestCT6.CT1][TestCT6.PRMS] = v
            prms_total += v
            self.mean_stats.addStatsDict(stats_dict)

        prms_avg = round(prms_total / TestCT6.COUNT, 5)
        mean_stats_dict = self.mean_stats.getStatsDict()
        calc_prms_avg = round(mean_stats_dict[TestCT6.CT1][TestCT6.PRMS], 5)
        assert prms_avg == calc_prms_avg

    def test_ct_name(self):
        """@brief Check the last CT NAME field is returned."""
        stats_dict = copy.deepcopy(TestCT6.TEST_DICT)
        for _ in range(0,TestCT6.COUNT):
            name_str = ''.join(choices(string.ascii_letters + string.digits, k=8))
            stats_dict[TestCT6.CT1][TestCT6.NAME] = name_str
            self.mean_stats.addStatsDict(stats_dict)

        mean_stats_dict = self.mean_stats.getStatsDict()
        last_name_str = mean_stats_dict[TestCT6.CT1][TestCT6.NAME]
        assert name_str == last_name_str

    def test_rssi(self):
        """@brief Check the RSSI field mean value is calculated correctly.
                  This checks that top level mean values are calculated correctly."""
        stats_dict = copy.deepcopy(TestCT6.TEST_DICT)
        rssi_total = 0
        for _ in range(0,TestCT6.COUNT):
            v = randint(-10000, 10000)
            stats_dict[TestCT6.RSSI] = v
            rssi_total += v
            self.mean_stats.addStatsDict(stats_dict)

        rssi_avg = round(rssi_total / TestCT6.COUNT, 5)
        mean_stats_dict = self.mean_stats.getStatsDict()
        calc_rssi_avg = round(mean_stats_dict[TestCT6.RSSI], 5)
        assert rssi_avg == calc_rssi_avg

    def test_assy(self):
        """@brief Check the last ASSY field is returned."""
        stats_dict = copy.deepcopy(TestCT6.TEST_DICT)
        for _ in range(0,TestCT6.COUNT):
            assy_str = ''.join(choices(string.ascii_letters + string.digits, k=20))
            stats_dict[TestCT6.ASSY] = assy_str
            self.mean_stats.addStatsDict(stats_dict)

        mean_stats_dict = self.mean_stats.getStatsDict()
        last_assy_str = mean_stats_dict[TestCT6.ASSY]
        assert assy_str == last_assy_str

if __name__ == '__main__':
    unittest.main()
