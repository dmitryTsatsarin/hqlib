from hyperquant.api import Platform, Interval
from hyperquant.clients.bitmex import BitMEXRESTConverterV1, BitMEXRESTClient, BitMEXWSClient, BitMEXWSConverterV1
from hyperquant.clients.tests.test_init import TestRESTClient, TestWSClient, TestConverter, TestRESTClientHistory

from hyperquant.clients import Endpoint

# REST

class TestOkexRESTClientHistoryV1(TestRESTClientHistory):
    platform_id = Platform.OKEX
    version = "1"
    testing_symbol = "ltc_btc"

    is_sorting_supported = True

    has_limit_error = True
    is_symbol_case_sensitive = True


    def test_fetch_candles(self):
        client = self.client
        testing_interval = Interval.DAY_3

        # Error ## todo: fix error part of test or make it separate as a "negative" test case
        #result = client.fetch_candles(None, None)
        #self.assertErrorResult(result)
        #result = client.fetch_candles(self.testing_symbol, None, **{'type': '1min'})
        #self.assertErrorResult(result)

        # Good
        result = client.fetch_candles(self.testing_symbol, testing_interval, **{'type': '1min'})

        self.assertGoodResult(result)
        for item in result:
            self.assertCandleIsValid(item, self.testing_symbol)
            self.assertEqual(item.interval, testing_interval)


# # WebSocket
#
class TestOkexWSClientV1(TestWSClient):
    platform_id = Platform.OKEX
    version = "1"

    testing_symbol = "ltc_btc"
    testing_symbols = ["ltc_btc",]


    def test_trade_1_channel(self):
        self._test_endpoint_channels([Endpoint.TRADE], [self.testing_symbol], self.assertTradeIsValid)

    def test_trade_2_channel(self):
        self._test_endpoint_channels([Endpoint.TRADE], self.testing_symbols, self.assertTradeIsValid)
