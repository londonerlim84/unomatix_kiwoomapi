from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'config', views.TradingConfigViewSet, basename='config')
router.register(r'stocks', views.StockViewSet, basename='stocks')
router.register(r'conditions', views.ConditionSearchViewSet, basename='conditions')
router.register(r'orders', views.OrderViewSet, basename='orders')
router.register(r'balance', views.BalanceViewSet, basename='balance')
router.register(r'trades', views.TradeHistoryViewSet, basename='trades')

urlpatterns = [
    path('', include(router.urls)),
    # 브릿지 콜백 엔드포인트
    path('callback/condition-match/', views.condition_match_callback, name='condition-match-callback'),
    path('callback/order-filled/', views.order_filled_callback, name='order-filled-callback'),
]
