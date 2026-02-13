"""
조건검색 서비스
조건검색식 관리, 실시간 편입/이탈 처리, 자동매매 트리거
"""
import logging
from django.utils import timezone
from stock.models import (
    Stock, ConditionSearch, ConditionMatch, TradingConfig
)
from .kiwoom_service import KiwoomService
from .trading_service import TradingService

logger = logging.getLogger(__name__)


class ConditionService:
    """조건검색 관리 서비스"""

    def __init__(self, config: TradingConfig = None):
        self.kiwoom = KiwoomService(config)
        self.trading = TradingService(config)
        self.config = config

    def load_condition_list(self):
        """
        키움에서 조건검색식 목록을 불러와 DB에 저장
        Returns: 조건검색식 목록 또는 에러
        """
        result = self.kiwoom.get_condition_list()
        if not result['success']:
            return result

        conditions = result['data'].get('conditions', [])
        saved = []

        for cond in conditions:
            obj, created = ConditionSearch.objects.update_or_create(
                condition_index=cond['index'],
                condition_name=cond['name'],
                defaults={'config': self.config}
            )
            saved.append({
                'id': obj.id,
                'index': obj.condition_index,
                'name': obj.condition_name,
                'status': obj.status,
                'auto_trade': obj.auto_trade,
                'created': created,
            })

        return {'success': True, 'data': saved}

    def start_condition_search(self, condition_id, is_realtime=True):
        """
        조건검색 실행
        is_realtime=True: 실시간 조건검색 (편입/이탈 모니터링)
        """
        try:
            condition = ConditionSearch.objects.get(id=condition_id)
        except ConditionSearch.DoesNotExist:
            return {'success': False, 'error': '조건검색식을 찾을 수 없습니다.'}

        screen_no = f"09{condition.condition_index:02d}"

        result = self.kiwoom.send_condition(
            screen_no=screen_no,
            condition_name=condition.condition_name,
            condition_index=condition.condition_index,
            is_realtime=is_realtime,
        )

        if result['success']:
            condition.is_realtime = is_realtime
            condition.status = 'active'
            condition.save()

            # 초기 편입 종목 처리
            matched_stocks = result['data'].get('stocks', [])
            self._process_initial_matches(condition, matched_stocks)

        return result

    def stop_condition_search(self, condition_id):
        """실시간 조건검색 중지"""
        try:
            condition = ConditionSearch.objects.get(id=condition_id)
        except ConditionSearch.DoesNotExist:
            return {'success': False, 'error': '조건검색식을 찾을 수 없습니다.'}

        screen_no = f"09{condition.condition_index:02d}"

        result = self.kiwoom.stop_condition(
            screen_no=screen_no,
            condition_name=condition.condition_name,
            condition_index=condition.condition_index,
        )

        condition.status = 'stopped'
        condition.save()

        return {'success': True, 'data': {'message': f'조건검색 [{condition.condition_name}] 중지됨'}}

    def process_condition_match(self, condition_id, stock_code, match_type):
        """
        조건검색 편입/이탈 이벤트 처리 (브릿지에서 콜백)
        match_type: 'I' (편입) 또는 'D' (이탈)
        """
        try:
            condition = ConditionSearch.objects.get(id=condition_id)
        except ConditionSearch.DoesNotExist:
            return {'success': False, 'error': '조건검색식을 찾을 수 없습니다.'}

        # 종목 정보 조회 또는 생성
        stock = self._get_or_create_stock(stock_code)
        if not stock:
            return {'success': False, 'error': f'종목 정보를 찾을 수 없습니다: {stock_code}'}

        # 편입/이탈 기록 저장
        match = ConditionMatch.objects.create(
            condition=condition,
            stock=stock,
            match_type=match_type,
        )

        logger.info(
            "조건검색 %s: [%s] %s %s",
            '편입' if match_type == 'I' else '이탈',
            condition.condition_name,
            stock.name,
            stock.code,
        )

        # 자동매매 실행
        trade_result = None
        if condition.auto_trade:
            trade_result = self._execute_auto_trade(condition, stock, match_type)

        return {
            'success': True,
            'data': {
                'match_id': match.id,
                'stock_code': stock.code,
                'stock_name': stock.name,
                'match_type': match_type,
                'auto_trade_result': trade_result,
            }
        }

    def _execute_auto_trade(self, condition, stock, match_type):
        """
        조건검색 결과에 따른 자동매매 실행
        편입(I) -> 매수 / 이탈(D) -> 매도
        """
        if match_type == 'I':
            # 편입 시 매수
            logger.info("자동매수 실행: [%s] %s", condition.condition_name, stock.name)
            return self.trading.auto_buy(
                stock=stock,
                condition=condition,
                reason=f"조건검색 편입: {condition.condition_name}",
            )
        elif match_type == 'D':
            # 이탈 시 매도
            logger.info("자동매도 실행: [%s] %s", condition.condition_name, stock.name)
            return self.trading.auto_sell(
                stock=stock,
                condition=condition,
                reason=f"조건검색 이탈: {condition.condition_name}",
            )

    def _process_initial_matches(self, condition, stock_codes):
        """조건검색 초기 편입 종목 처리"""
        for code in stock_codes:
            stock = self._get_or_create_stock(code)
            if stock:
                ConditionMatch.objects.create(
                    condition=condition,
                    stock=stock,
                    match_type='I',
                )
                if condition.auto_trade:
                    self._execute_auto_trade(condition, stock, 'I')

    def _get_or_create_stock(self, stock_code):
        """종목 정보 조회 또는 생성"""
        stock = Stock.objects.filter(code=stock_code).first()
        if stock:
            return stock

        # 브릿지에서 종목 정보 조회
        info = self.kiwoom.get_stock_info(stock_code)
        if info['success']:
            data = info['data']
            stock = Stock.objects.create(
                code=stock_code,
                name=data.get('name', stock_code),
                market=data.get('market', 'KOSPI'),
            )
            return stock

        # 브릿지 연결 실패 시 코드만으로 생성
        stock = Stock.objects.create(
            code=stock_code,
            name=stock_code,
            market='KOSPI',
        )
        return stock

    def get_condition_matches(self, condition_id, match_type=None, limit=100):
        """조건검색 결과 조회"""
        queryset = ConditionMatch.objects.filter(condition_id=condition_id)
        if match_type:
            queryset = queryset.filter(match_type=match_type)
        return queryset.select_related('stock')[:limit]
