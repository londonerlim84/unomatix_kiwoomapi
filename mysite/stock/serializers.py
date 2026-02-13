from rest_framework import serializers
from .models import (
    Stock, StockPrice, TradingConfig, ConditionSearch,
    ConditionMatch, Order, Balance, TradeHistory
)


class StockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stock
        fields = ['id', 'code', 'name', 'market', 'is_active', 'created_at']


class StockPriceSerializer(serializers.ModelSerializer):
    stock = StockSerializer(read_only=True)

    class Meta:
        model = StockPrice
        fields = [
            'id', 'stock', 'current_price', 'open_price', 'high_price',
            'low_price', 'prev_close', 'volume', 'change_rate', 'timestamp'
        ]


class TradingConfigSerializer(serializers.ModelSerializer):
    mode_display = serializers.CharField(source='get_trade_mode_display', read_only=True)

    class Meta:
        model = TradingConfig
        fields = [
            'id', 'name', 'trade_mode', 'mode_display', 'account_no',
            'is_active', 'max_buy_amount', 'max_buy_per_stock',
            'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'app_key': {'write_only': True},
            'app_secret': {'write_only': True},
        }


class TradingConfigCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TradingConfig
        fields = [
            'name', 'trade_mode', 'app_key', 'app_secret',
            'account_no', 'is_active', 'max_buy_amount', 'max_buy_per_stock'
        ]


class ConditionSearchSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ConditionSearch
        fields = [
            'id', 'condition_index', 'condition_name', 'is_realtime',
            'auto_trade', 'status', 'status_display', 'config',
            'created_at', 'updated_at'
        ]


class ConditionMatchSerializer(serializers.ModelSerializer):
    stock = StockSerializer(read_only=True)
    match_type_display = serializers.CharField(source='get_match_type_display', read_only=True)

    class Meta:
        model = ConditionMatch
        fields = ['id', 'condition', 'stock', 'match_type', 'match_type_display', 'matched_at']


class OrderSerializer(serializers.ModelSerializer):
    stock = StockSerializer(read_only=True)
    order_type_display = serializers.CharField(source='get_order_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'stock', 'order_type', 'order_type_display', 'price_type',
            'quantity', 'price', 'filled_quantity', 'filled_price',
            'status', 'status_display', 'order_no', 'trade_mode',
            'condition', 'reason', 'created_at'
        ]


class OrderCreateSerializer(serializers.Serializer):
    stock_code = serializers.CharField(max_length=10)
    order_type = serializers.ChoiceField(choices=['buy', 'sell'])
    quantity = serializers.IntegerField(min_value=1)
    price = serializers.IntegerField(min_value=0, default=0)
    price_type = serializers.ChoiceField(choices=['market', 'limit'], default='market')
    reason = serializers.CharField(max_length=200, required=False, default='수동주문')


class BalanceSerializer(serializers.ModelSerializer):
    stock = StockSerializer(read_only=True)

    class Meta:
        model = Balance
        fields = [
            'id', 'stock', 'quantity', 'avg_price', 'current_price',
            'profit_rate', 'profit_amount', 'trade_mode', 'updated_at'
        ]


class TradeHistorySerializer(serializers.ModelSerializer):
    stock = StockSerializer(read_only=True)

    class Meta:
        model = TradeHistory
        fields = [
            'id', 'stock', 'order', 'order_type', 'quantity',
            'price', 'total_amount', 'trade_mode', 'traded_at'
        ]


class ConditionMatchCallbackSerializer(serializers.Serializer):
    """브릿지에서 조건검색 편입/이탈 콜백"""
    condition_id = serializers.IntegerField()
    stock_code = serializers.CharField(max_length=10)
    match_type = serializers.ChoiceField(choices=['I', 'D'])


class OrderFilledCallbackSerializer(serializers.Serializer):
    """브릿지에서 체결 콜백"""
    order_no = serializers.CharField(max_length=20)
    filled_quantity = serializers.IntegerField(min_value=1)
    filled_price = serializers.IntegerField(min_value=1)


class SwitchModeSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=['mock', 'real'])
