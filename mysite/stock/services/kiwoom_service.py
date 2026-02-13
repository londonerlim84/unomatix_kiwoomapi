"""
키움 API 통신 서비스
Windows 브릿지 에이전트와 HTTP로 통신하여 키움 OpenAPI+ 기능을 사용합니다.
모의투자/실투자 전환을 API 키 기반으로 처리합니다.
"""
import logging
import requests
from django.conf import settings
from stock.models import TradingConfig

logger = logging.getLogger(__name__)


class KiwoomService:
    """키움 OpenAPI+ 브릿지 통신 서비스"""

    def __init__(self, config: TradingConfig = None):
        if config:
            self.trade_mode = config.trade_mode
            self.app_key = config.app_key
            self.app_secret = config.app_secret
            self.account_no = config.account_no
        else:
            self.trade_mode = settings.KIWOOM_TRADE_MODE
            self._load_keys_from_settings()

        self.bridge_url = settings.KIWOOM_BRIDGE_URL
        self.timeout = 10

    def _load_keys_from_settings(self):
        """설정에서 모드에 따라 API 키 로드"""
        if self.trade_mode == 'real':
            self.app_key = settings.KIWOOM_APP_KEY_REAL
            self.app_secret = settings.KIWOOM_APP_SECRET_REAL
        else:
            self.app_key = settings.KIWOOM_APP_KEY_MOCK
            self.app_secret = settings.KIWOOM_APP_SECRET_MOCK
        self.account_no = settings.KIWOOM_ACCOUNT_NO

    def _request(self, endpoint, method='GET', data=None):
        """브릿지 에이전트에 HTTP 요청"""
        url = f"{self.bridge_url}/api/{endpoint}"
        headers = {
            'Content-Type': 'application/json',
            'X-Trade-Mode': self.trade_mode,
            'X-App-Key': self.app_key,
            'X-App-Secret': self.app_secret,
            'X-Account-No': self.account_no,
        }

        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=data, timeout=self.timeout)
            else:
                response = requests.post(url, headers=headers, json=data, timeout=self.timeout)

            response.raise_for_status()
            return {'success': True, 'data': response.json()}
        except requests.ConnectionError:
            logger.error("브릿지 에이전트 연결 실패: %s", url)
            return {'success': False, 'error': '브릿지 에이전트에 연결할 수 없습니다.'}
        except requests.Timeout:
            logger.error("브릿지 에이전트 응답 타임아웃: %s", url)
            return {'success': False, 'error': '브릿지 에이전트 응답 시간 초과'}
        except requests.HTTPError as e:
            logger.error("브릿지 에이전트 HTTP 오류: %s", e)
            return {'success': False, 'error': f'HTTP 오류: {e}'}

    # ===== 접속 관련 =====

    def connect(self):
        """키움 OpenAPI 로그인"""
        return self._request('connect', method='POST', data={
            'trade_mode': self.trade_mode,
        })

    def get_connect_state(self):
        """접속 상태 확인"""
        return self._request('connect/state')

    # ===== 조건검색 관련 =====

    def get_condition_list(self):
        """조건검색식 목록 조회"""
        return self._request('condition/list')

    def send_condition(self, screen_no, condition_name, condition_index, is_realtime=True):
        """조건검색 요청 (편입 종목 조회)"""
        return self._request('condition/search', method='POST', data={
            'screen_no': screen_no,
            'condition_name': condition_name,
            'condition_index': condition_index,
            'is_realtime': is_realtime,
        })

    def stop_condition(self, screen_no, condition_name, condition_index):
        """실시간 조건검색 중지"""
        return self._request('condition/stop', method='POST', data={
            'screen_no': screen_no,
            'condition_name': condition_name,
            'condition_index': condition_index,
        })

    # ===== 시세 관련 =====

    def get_stock_price(self, stock_code):
        """종목 현재가 조회"""
        return self._request('stock/price', data={'code': stock_code})

    def get_stock_info(self, stock_code):
        """종목 기본 정보 조회"""
        return self._request('stock/info', data={'code': stock_code})

    # ===== 주문 관련 =====

    def send_order(self, order_type, stock_code, quantity, price=0, price_type='market'):
        """
        주문 전송
        order_type: 'buy' 또는 'sell'
        price_type: 'market'(시장가) 또는 'limit'(지정가)
        """
        # 키움 주문유형 코드 변환
        kiwoom_order_type = 1 if order_type == 'buy' else 2
        # 키움 호가유형: 시장가=03, 지정가=00
        kiwoom_price_type = '03' if price_type == 'market' else '00'

        return self._request('order', method='POST', data={
            'order_type': kiwoom_order_type,
            'stock_code': stock_code,
            'quantity': quantity,
            'price': price,
            'price_type': kiwoom_price_type,
            'account_no': self.account_no,
        })

    def cancel_order(self, order_no, stock_code, quantity):
        """주문 취소"""
        return self._request('order/cancel', method='POST', data={
            'order_no': order_no,
            'stock_code': stock_code,
            'quantity': quantity,
            'account_no': self.account_no,
        })

    # ===== 잔고 관련 =====

    def get_balance(self):
        """계좌 잔고 조회"""
        return self._request('balance', data={'account_no': self.account_no})

    def get_order_list(self):
        """미체결 주문 조회"""
        return self._request('orders', data={'account_no': self.account_no})
