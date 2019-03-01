import json

from hyperquant.api import Platform, ErrorCode, Endpoint, ParamName, Sorting, Direction
from hyperquant.clients import PrivatePlatformRESTClient, RESTConverter, Error, Trade, Candle, WSClient, WSConverter

from hyperquant.clients.bitmex import generate_nonce, generate_signature


class OkexRESTConverterV1(RESTConverter):
    # Main params:
    base_url = 'https://www.okex.com/api/v{version}/'

    # Settings:

    endpoint_lookup = {
        Endpoint.TRADE_HISTORY: "trades.do",
        Endpoint.CANDLE: "kline.do",

    }
    param_name_lookup = {
        ParamName.SYMBOL: "symbol",
        ParamName.TIMESTAMP: "since",
        ParamName.ORDER_TYPE: "type",

    }
    param_value_lookup = {
        Sorting.DEFAULT_SORTING: Sorting.ASCENDING,
    }
    max_limit_by_endpoint = {
        Endpoint.TRADE: 1000,
        Endpoint.TRADE_HISTORY: 1000,
        Endpoint.ORDER_BOOK: 1000,
        Endpoint.CANDLE: 1000,
    }

    # For parsing
    param_lookup_by_class = {
        Error: ["", "code", "message"],
        Trade: {
            "date_ms": ParamName.TIMESTAMP,
            "tid": ParamName.ITEM_ID,
            "amount": ParamName.AMOUNT,
            "price": ParamName.PRICE,
            "type": ParamName.DIRECTION,
        },
        Candle:
            [
                ParamName.TIMESTAMP,
                ParamName.PRICE_OPEN,
                ParamName.PRICE_HIGH,
                ParamName.PRICE_LOW,
                ParamName.PRICE_CLOSE,
                None  # ParamName.TRADES_COUNT,

            ],
    }

    error_code_by_platform_error_code = {
        # "": ErrorCode.UNAUTHORIZED,
        10020: ErrorCode.WRONG_LIMIT,
        11010: ErrorCode.RATE_LIMIT,
    }
    error_code_by_http_status = {}

    # For converting time
    is_source_in_milliseconds = True
    timestamp_platform_names = ["start", "end"]

    def prepare_params(self, endpoint=None, params=None):
        # # Symbol needs "t" prefix for trading pair
        # if ParamName.SYMBOL in params:
        #     params[ParamName.SYMBOL] = "t" + str(params[ParamName.SYMBOL])

        resources, platform_params = super().prepare_params(endpoint, params)

        return resources, platform_params

    def _process_param_value(self, name, value):
        # # Symbol needs "t" prefix for trading pair
        # if name == ParamName.SYMBOL and value:
        #     return "t" + value
        # elif
        if name == ParamName.FROM_ITEM or name == ParamName.TO_ITEM:
            if isinstance(value, Trade):
                return value.timestamp
        return super()._process_param_value(name, value)

    def _parse_item(self, endpoint, item_data):
        result = super()._parse_item(endpoint, item_data)

        # TODO: why do we often use this logic and don't use _post_process_item???
        if result and isinstance(result, Trade):
            # Determine direction
            result.direction = Direction.BUY if result.amount > 0 else Direction.SELL
            # Stringify and check sign
            result.price = str(result.price)
            result.amount = str(result.amount) if result.amount > 0 else str(-result.amount)
        return result

    def parse_error(self, error_data=None, response=None):
        result = super().parse_error(error_data, response)

        if error_data and isinstance(error_data, dict) and "error" in error_data:
            if error_data["error"] == "ERR_RATE_LIMIT":
                result.error_code = ErrorCode.RATE_LIMIT
                result.message = ErrorCode.get_message_by_code(result.code) + result.message
        return result


class OkexRESTClient(PrivatePlatformRESTClient):
    # Settings:
    platform_id = Platform.OKEX
    version = "1"  # Default version

    _converter_class_by_version = {
        "1": OkexRESTConverterV1,
    }

    # State:
    ratelimit_error_in_row_count = 0

    # TODO: use custom on response logic
    def _on_response(self, response, result):
        return super()._on_response(response, result)

    def fetch_trades_history(self, symbol, limit=None, from_item=None,
                             sorting=None, from_time=None, to_time=None, **kwargs):
        if from_item and self.version == "1":
            # todo check
            self.logger.warning("Bitfinex v1 API has no trades-history functionality.")
            return None
        # return self.fetch_trades(symbol, limit, **kwargs)
        return super().fetch_trades_history(symbol, limit, from_item, sorting=sorting,
                                            from_time=from_time, to_time=to_time, **kwargs)

    def fetch_history(self, endpoint, symbol, limit=None, from_item=None, to_item=None, sorting=None,
                      is_use_max_limit=False, from_time=None, to_time=None,
                      version=None, **kwargs):
        if from_item is None:
            from_item = 0
        return super().fetch_history(endpoint, symbol, limit, from_item, to_item, sorting, is_use_max_limit, from_time,
                                     to_time, **kwargs)


class OkexWSConverterV1(WSConverter):
    # Main params:
    base_url = "wss://real.okex.com:10440/ws/v{version}"

    IS_SUBSCRIPTION_COMMAND_SUPPORTED = True

    endpoint_lookup = {
        Endpoint.TRADE: "trade:{symbol}",
    }

    # For parsing
    param_lookup_by_class = {
        Error: {
            "status": "code",
            "error": "message",
        },
        # todo: adopt to Okex params
        Trade: {
            "trdMatchID": ParamName.ITEM_ID,
            "timestamp": ParamName.TIMESTAMP,
            "symbol": ParamName.SYMBOL,
            "price": ParamName.PRICE,
            "size": ParamName.AMOUNT,
            "side": ParamName.DIRECTION,
        },
    }
    event_type_param = "table"

    # For converting time
    is_source_in_timestring = True

    # timestamp_platform_names = []

    def parse(self, endpoint, data):
        if data:
            endpoint = data.get(self.event_type_param)
            if "error" in data:
                result = self.parse_error(data)
                if "request" in data:
                    result.message += "request: " + json.dumps(data["request"])
                return result
            if "data" in data:
                data = data["data"]
        return super().parse(endpoint, data)

    def _parse_item(self, endpoint, item_data):
        result = super()._parse_item(endpoint, item_data)

        # (For Trade)
        if hasattr(result, ParamName.SYMBOL) and result.symbol[0] == ".":
            return None

        # Convert direction
        if result and isinstance(result, Trade):
            result.direction = Direction.BUY if result.direction == "Buy" else (
                Direction.SELL if result.direction == "Sell" else None)
            result.price = str(result.price)
            result.amount = str(result.amount)
        return result


class OkexWSClient(WSClient):
    platform_id = Platform.OKEX
    version = "1"  # Default version

    _converter_class_by_version = {
        "1": OkexWSConverterV1,
    }

    @property
    def url(self):
        self.is_subscribed_with_url = True
        params = {"subscribe": ",".join(self.current_subscriptions)}
        url, platform_params = self.converter.make_url_and_platform_params(params=params, is_join_get_params=True)
        return url

    @property
    def headers(self):
        result = super().headers or []
        # Return auth headers
        if self._api_key:
            self.logger.info("Authenticating with API Key.")
            # To auth to the WS using an API key, we generate
            # a signature of a nonce and the WS API endpoint.
            expire = generate_nonce()
            result += [
                "api-expires: " + str(expire),
            ]
            if self._api_key and self._api_secret:
                signature = generate_signature(self._api_secret, "GET", "/realtime", expire, "")
                result += [
                    "api-signature: " + signature,
                    "api-key: " + self._api_key,
                ]
        else:
            self.logger.info("Not authenticating by headers because api_key is not set.")

        return result

    def _send_subscribe(self, subscriptions):
        self._send_command("subscribe", subscriptions)

    def _send_unsubscribe(self, subscriptions):
        self._send_command("unsubscribe", subscriptions)

    def _send_command(self, command, params=None):
        if params is None:
            params = []
        self._send({"op": command, "args": list(params)})
