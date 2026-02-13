from django.contrib import admin
from .models import (
    Stock, StockPrice, TradingConfig, ConditionSearch,
    ConditionMatch, Order, Balance, TradeHistory
)


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'market', 'is_active']
    search_fields = ['code', 'name']
    list_filter = ['market', 'is_active']


@admin.register(StockPrice)
class StockPriceAdmin(admin.ModelAdmin):
    list_display = ['stock', 'current_price', 'change_rate', 'volume', 'timestamp']
    list_filter = ['stock__market']


@admin.register(TradingConfig)
class TradingConfigAdmin(admin.ModelAdmin):
    list_display = ['name', 'trade_mode', 'account_no', 'is_active', 'max_buy_amount', 'max_buy_per_stock']
    list_filter = ['trade_mode', 'is_active']


@admin.register(ConditionSearch)
class ConditionSearchAdmin(admin.ModelAdmin):
    list_display = ['condition_index', 'condition_name', 'is_realtime', 'auto_trade', 'status']
    list_filter = ['status', 'auto_trade', 'is_realtime']


@admin.register(ConditionMatch)
class ConditionMatchAdmin(admin.ModelAdmin):
    list_display = ['condition', 'stock', 'match_type', 'matched_at']
    list_filter = ['match_type', 'condition']
    search_fields = ['stock__code', 'stock__name']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['stock', 'order_type', 'quantity', 'price', 'status', 'trade_mode', 'created_at']
    list_filter = ['order_type', 'status', 'trade_mode']
    search_fields = ['stock__code', 'stock__name', 'order_no']


@admin.register(Balance)
class BalanceAdmin(admin.ModelAdmin):
    list_display = ['stock', 'quantity', 'avg_price', 'current_price', 'profit_rate', 'trade_mode']
    list_filter = ['trade_mode']


@admin.register(TradeHistory)
class TradeHistoryAdmin(admin.ModelAdmin):
    list_display = ['stock', 'order_type', 'quantity', 'price', 'total_amount', 'trade_mode', 'traded_at']
    list_filter = ['order_type', 'trade_mode']
    search_fields = ['stock__code', 'stock__name']
