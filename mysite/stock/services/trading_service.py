"""
매매 서비스
매수/매도 주문 처리, 잔고 관리, 모의/실투자 전환
"""
import logging
from django.db import transaction
from stock.models import (
    Stock, Order, Balance, TradeHistory, TradingConfig, ConditionSearch
)
from .kiwoom_service import KiwoomService

logger = logging.getLogger(__name__)


class TradingService:
    """매매 실행 서비스"""

    def __init__(self, config: TradingConfig = None):
        self.kiwoom = KiwoomService(config)
        self.config = config
        self.trade_mode = config.trade_mode if config else 'mock'

    def get_active_config(self):
        """현재 활성화된 매매설정 반환"""
        if self.config:
            return self.config
        return TradingConfig.objects.filter(is_active=True).first()

    def switch_mode(self, mode):
        """
        모의투자/실투자 전환
        mode: 'mock' 또는 'real'
        """
        config = self.get_active_config()
        if not config:
            return {'success': False, 'error': '활성화된 매매설정이 없습니다.'}

        if mode not in ('mock', 'real'):
            return {'success': False, 'error': "모드는 'mock' 또는 'real'만 가능합니다."}

        if mode == 'real':
            # 실투자 전환 시 안전 확인
            if not config.app_key or not config.app_secret:
                return {'success': False, 'error': '실투자 API 키가 설정되지 않았습니다.'}

        config.trade_mode = mode
        config.save()

        # 서비스 내부 모드도 갱신
        self.trade_mode = mode
        self.kiwoom = KiwoomService(config)

        logger.info("투자모드 전환: %s", '실투자' if mode == 'real' else '모의투자')
        return {
            'success': True,
            'data': {
                'mode': mode,
                'mode_display': '실투자' if mode == 'real' else '모의투자',
            }
        }

    def buy(self, stock, quantity, price=0, price_type='market',
            condition=None, reason=''):
        """
        매수 주문
        """
        config = self.get_active_config()

        # 주문 금액 한도 체크
        if config and price_type == 'limit' and price > 0:
            total = price * quantity
            if total > config.max_buy_per_stock:
                return {
                    'success': False,
                    'error': f'종목당 최대매수금액({config.max_buy_per_stock:,}원) 초과'
                }

        # DB에 주문 기록 생성
        order = Order.objects.create(
            stock=stock,
            order_type='buy',
            price_type=price_type,
            quantity=quantity,
            price=price,
            trade_mode=self.trade_mode,
            condition=condition,
            reason=reason,
            status='pending',
        )

        # 키움 브릿지로 주문 전송
        result = self.kiwoom.send_order(
            order_type='buy',
            stock_code=stock.code,
            quantity=quantity,
            price=price,
            price_type=price_type,
        )

        if result['success']:
            order.status = 'submitted'
            order.order_no = result['data'].get('order_no', '')
            order.save()
            logger.info("매수주문 접수: %s %d주", stock.name, quantity)
        else:
            order.status = 'rejected'
            order.reason = result.get('error', '주문 실패')
            order.save()
            logger.error("매수주문 실패: %s - %s", stock.name, result.get('error'))

        return {
            'success': result['success'],
            'data': {
                'order_id': order.id,
                'order_no': order.order_no,
                'stock': stock.name,
                'quantity': quantity,
                'status': order.status,
            },
            'error': result.get('error'),
        }

    def sell(self, stock, quantity, price=0, price_type='market',
             condition=None, reason=''):
        """
        매도 주문
        """
        # 보유 잔고 확인
        balance = Balance.objects.filter(
            stock=stock, trade_mode=self.trade_mode
        ).first()

        if not balance or balance.quantity < quantity:
            available = balance.quantity if balance else 0
            return {
                'success': False,
                'error': f'보유수량 부족 (보유: {available}주, 요청: {quantity}주)'
            }

        # DB에 주문 기록 생성
        order = Order.objects.create(
            stock=stock,
            order_type='sell',
            price_type=price_type,
            quantity=quantity,
            price=price,
            trade_mode=self.trade_mode,
            condition=condition,
            reason=reason,
            status='pending',
        )

        # 키움 브릿지로 주문 전송
        result = self.kiwoom.send_order(
            order_type='sell',
            stock_code=stock.code,
            quantity=quantity,
            price=price,
            price_type=price_type,
        )

        if result['success']:
            order.status = 'submitted'
            order.order_no = result['data'].get('order_no', '')
            order.save()
            logger.info("매도주문 접수: %s %d주", stock.name, quantity)
        else:
            order.status = 'rejected'
            order.reason = result.get('error', '주문 실패')
            order.save()
            logger.error("매도주문 실패: %s - %s", stock.name, result.get('error'))

        return {
            'success': result['success'],
            'data': {
                'order_id': order.id,
                'order_no': order.order_no,
                'stock': stock.name,
                'quantity': quantity,
                'status': order.status,
            },
            'error': result.get('error'),
        }

    def auto_buy(self, stock, condition=None, reason=''):
        """
        자동매수 - 조건검색 편입 시 호출
        매매설정의 종목당 최대금액 기준으로 수량 계산
        """
        config = self.get_active_config()
        if not config:
            return {'success': False, 'error': '매매설정 없음'}

        # 현재가 조회
        price_result = self.kiwoom.get_stock_price(stock.code)
        if not price_result['success']:
            return {'success': False, 'error': '현재가 조회 실패'}

        current_price = price_result['data'].get('current_price', 0)
        if current_price <= 0:
            return {'success': False, 'error': '현재가 비정상'}

        # 매수 수량 계산 (종목당 최대금액 / 현재가)
        quantity = config.max_buy_per_stock // current_price
        if quantity <= 0:
            return {'success': False, 'error': '매수 가능 수량 없음 (가격 > 종목당 최대금액)'}

        # 이미 보유 중인지 확인
        existing = Balance.objects.filter(
            stock=stock, trade_mode=self.trade_mode, quantity__gt=0
        ).exists()
        if existing:
            logger.info("이미 보유중인 종목 매수 스킵: %s", stock.name)
            return {'success': False, 'error': f'이미 보유중인 종목: {stock.name}'}

        return self.buy(
            stock=stock,
            quantity=quantity,
            price_type='market',
            condition=condition,
            reason=reason,
        )

    def auto_sell(self, stock, condition=None, reason=''):
        """
        자동매도 - 조건검색 이탈 시 호출
        보유 수량 전량 시장가 매도
        """
        balance = Balance.objects.filter(
            stock=stock, trade_mode=self.trade_mode, quantity__gt=0
        ).first()

        if not balance:
            return {'success': False, 'error': f'보유하지 않은 종목: {stock.name}'}

        return self.sell(
            stock=stock,
            quantity=balance.quantity,
            price_type='market',
            condition=condition,
            reason=reason,
        )

    @transaction.atomic
    def process_order_filled(self, order_no, filled_quantity, filled_price):
        """
        체결 처리 (브릿지 콜백)
        주문 상태 업데이트 + 잔고 반영 + 체결내역 기록
        """
        try:
            order = Order.objects.select_for_update().get(order_no=order_no)
        except Order.DoesNotExist:
            return {'success': False, 'error': f'주문번호 없음: {order_no}'}

        order.filled_quantity += filled_quantity
        order.filled_price = filled_price
        if order.filled_quantity >= order.quantity:
            order.status = 'filled'
        else:
            order.status = 'partial'
        order.save()

        # 체결내역 기록
        TradeHistory.objects.create(
            stock=order.stock,
            order=order,
            order_type=order.order_type,
            quantity=filled_quantity,
            price=filled_price,
            total_amount=filled_quantity * filled_price,
            trade_mode=order.trade_mode,
        )

        # 잔고 업데이트
        self._update_balance(order, filled_quantity, filled_price)

        return {'success': True, 'data': {'order_no': order_no, 'status': order.status}}

    def _update_balance(self, order, filled_quantity, filled_price):
        """잔고 업데이트"""
        balance, created = Balance.objects.get_or_create(
            stock=order.stock,
            trade_mode=order.trade_mode,
            defaults={'quantity': 0, 'avg_price': 0},
        )

        if order.order_type == 'buy':
            # 매수: 평균단가 재계산
            total_cost = (balance.avg_price * balance.quantity) + (filled_price * filled_quantity)
            balance.quantity += filled_quantity
            balance.avg_price = total_cost // balance.quantity if balance.quantity > 0 else 0
        elif order.order_type == 'sell':
            # 매도: 수량 차감
            balance.quantity -= filled_quantity

        balance.current_price = filled_price
        if balance.avg_price > 0 and balance.quantity > 0:
            balance.profit_rate = round(
                ((balance.current_price - balance.avg_price) / balance.avg_price) * 100, 2
            )
            balance.profit_amount = (balance.current_price - balance.avg_price) * balance.quantity
        else:
            balance.profit_rate = 0
            balance.profit_amount = 0

        balance.save()

    def sync_balance(self):
        """키움에서 잔고 동기화"""
        result = self.kiwoom.get_balance()
        if not result['success']:
            return result

        items = result['data'].get('items', [])
        for item in items:
            stock = Stock.objects.filter(code=item['stock_code']).first()
            if not stock:
                stock = Stock.objects.create(
                    code=item['stock_code'],
                    name=item.get('stock_name', item['stock_code']),
                    market='KOSPI',
                )

            Balance.objects.update_or_create(
                stock=stock,
                trade_mode=self.trade_mode,
                defaults={
                    'quantity': item.get('quantity', 0),
                    'avg_price': item.get('avg_price', 0),
                    'current_price': item.get('current_price', 0),
                    'profit_rate': item.get('profit_rate', 0),
                    'profit_amount': item.get('profit_amount', 0),
                },
            )

        return {'success': True, 'data': {'synced': len(items)}}
