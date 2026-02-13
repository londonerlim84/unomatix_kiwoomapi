from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from .models import (
    Stock, StockPrice, TradingConfig, ConditionSearch,
    ConditionMatch, Order, Balance, TradeHistory
)
from .serializers import (
    StockSerializer, StockPriceSerializer, TradingConfigSerializer,
    TradingConfigCreateSerializer, ConditionSearchSerializer,
    ConditionMatchSerializer, OrderSerializer, OrderCreateSerializer,
    BalanceSerializer, TradeHistorySerializer,
    ConditionMatchCallbackSerializer, OrderFilledCallbackSerializer,
    SwitchModeSerializer,
)
from .services import KiwoomService, TradingService, ConditionService


def _get_active_config():
    return TradingConfig.objects.filter(is_active=True).first()


class TradingConfigViewSet(viewsets.ModelViewSet):
    """매매설정 관리 API"""
    queryset = TradingConfig.objects.all()

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return TradingConfigCreateSerializer
        return TradingConfigSerializer

    @action(detail=False, methods=['post'])
    def switch_mode(self, request):
        """모의투자/실투자 전환"""
        serializer = SwitchModeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        config = _get_active_config()
        if not config:
            return Response(
                {'error': '활성화된 매매설정이 없습니다.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        service = TradingService(config)
        result = service.switch_mode(serializer.validated_data['mode'])

        if result['success']:
            return Response(result['data'])
        return Response({'error': result['error']}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def current(self, request):
        """현재 활성 설정 조회"""
        config = _get_active_config()
        if not config:
            return Response(
                {'error': '활성화된 매매설정이 없습니다.'},
                status=status.HTTP_404_NOT_FOUND
            )
        return Response(TradingConfigSerializer(config).data)


class StockViewSet(viewsets.ReadOnlyModelViewSet):
    """종목 조회 API"""
    queryset = Stock.objects.filter(is_active=True)
    serializer_class = StockSerializer

    @action(detail=True, methods=['get'])
    def price(self, request, pk=None):
        """종목 시세 조회"""
        stock = self.get_object()
        config = _get_active_config()
        kiwoom = KiwoomService(config)
        result = kiwoom.get_stock_price(stock.code)

        if result['success']:
            return Response(result['data'])
        return Response({'error': result['error']}, status=status.HTTP_502_BAD_GATEWAY)


class ConditionSearchViewSet(viewsets.ModelViewSet):
    """조건검색식 관리 API"""
    queryset = ConditionSearch.objects.all()
    serializer_class = ConditionSearchSerializer

    @action(detail=False, methods=['post'])
    def load(self, request):
        """키움에서 조건검색식 목록 불러오기"""
        config = _get_active_config()
        service = ConditionService(config)
        result = service.load_condition_list()

        if result['success']:
            return Response(result['data'])
        return Response({'error': result['error']}, status=status.HTTP_502_BAD_GATEWAY)

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """조건검색 실행"""
        is_realtime = request.data.get('is_realtime', True)
        config = _get_active_config()
        service = ConditionService(config)
        result = service.start_condition_search(pk, is_realtime=is_realtime)

        if result['success']:
            return Response(result['data'])
        return Response(
            {'error': result.get('error', '조건검색 실행 실패')},
            status=status.HTTP_400_BAD_REQUEST
        )

    @action(detail=True, methods=['post'])
    def stop(self, request, pk=None):
        """조건검색 중지"""
        config = _get_active_config()
        service = ConditionService(config)
        result = service.stop_condition_search(pk)

        if result['success']:
            return Response(result['data'])
        return Response({'error': result['error']}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def matches(self, request, pk=None):
        """조건검색 편입/이탈 결과 조회"""
        match_type = request.query_params.get('type')
        config = _get_active_config()
        service = ConditionService(config)
        matches = service.get_condition_matches(pk, match_type=match_type)
        serializer = ConditionMatchSerializer(matches, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'])
    def toggle_auto_trade(self, request, pk=None):
        """자동매매 켜기/끄기"""
        condition = self.get_object()
        condition.auto_trade = not condition.auto_trade
        condition.save()
        return Response({
            'id': condition.id,
            'condition_name': condition.condition_name,
            'auto_trade': condition.auto_trade,
        })


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    """주문 API"""
    serializer_class = OrderSerializer

    def get_queryset(self):
        config = _get_active_config()
        mode = config.trade_mode if config else 'mock'
        return Order.objects.filter(trade_mode=mode).select_related('stock')

    @action(detail=False, methods=['post'])
    def place(self, request):
        """수동 주문 실행"""
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        stock = Stock.objects.filter(code=data['stock_code']).first()
        if not stock:
            return Response(
                {'error': f"종목을 찾을 수 없습니다: {data['stock_code']}"},
                status=status.HTTP_404_NOT_FOUND
            )

        config = _get_active_config()
        service = TradingService(config)

        if data['order_type'] == 'buy':
            result = service.buy(
                stock=stock,
                quantity=data['quantity'],
                price=data['price'],
                price_type=data['price_type'],
                reason=data.get('reason', '수동주문'),
            )
        else:
            result = service.sell(
                stock=stock,
                quantity=data['quantity'],
                price=data['price'],
                price_type=data['price_type'],
                reason=data.get('reason', '수동주문'),
            )

        if result['success']:
            return Response(result['data'], status=status.HTTP_201_CREATED)
        return Response({'error': result['error']}, status=status.HTTP_400_BAD_REQUEST)


class BalanceViewSet(viewsets.ReadOnlyModelViewSet):
    """잔고 API"""
    serializer_class = BalanceSerializer

    def get_queryset(self):
        config = _get_active_config()
        mode = config.trade_mode if config else 'mock'
        return Balance.objects.filter(
            trade_mode=mode, quantity__gt=0
        ).select_related('stock')

    @action(detail=False, methods=['post'])
    def sync(self, request):
        """키움에서 잔고 동기화"""
        config = _get_active_config()
        service = TradingService(config)
        result = service.sync_balance()

        if result['success']:
            return Response(result['data'])
        return Response({'error': result['error']}, status=status.HTTP_502_BAD_GATEWAY)


class TradeHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """체결내역 API"""
    serializer_class = TradeHistorySerializer

    def get_queryset(self):
        config = _get_active_config()
        mode = config.trade_mode if config else 'mock'
        return TradeHistory.objects.filter(
            trade_mode=mode
        ).select_related('stock')


# ===== 브릿지 콜백 API =====

@api_view(['POST'])
def condition_match_callback(request):
    """브릿지에서 조건검색 편입/이탈 알림 수신"""
    serializer = ConditionMatchCallbackSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    config = _get_active_config()
    service = ConditionService(config)
    result = service.process_condition_match(
        condition_id=data['condition_id'],
        stock_code=data['stock_code'],
        match_type=data['match_type'],
    )

    if result['success']:
        return Response(result['data'])
    return Response({'error': result['error']}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def order_filled_callback(request):
    """브릿지에서 체결 알림 수신"""
    serializer = OrderFilledCallbackSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    config = _get_active_config()
    service = TradingService(config)
    result = service.process_order_filled(
        order_no=data['order_no'],
        filled_quantity=data['filled_quantity'],
        filled_price=data['filled_price'],
    )

    if result['success']:
        return Response(result['data'])
    return Response({'error': result['error']}, status=status.HTTP_400_BAD_REQUEST)
