"""
키움 OpenAPI+ 브릿지 에이전트 (Windows 전용)
Django 서버와 HTTP로 통신하며, 키움 OpenAPI+ COM을 직접 제어합니다.

사용법:
1. Windows PC에 키움 OpenAPI+ 설치
2. pip install -r requirements.txt
3. python kiwoom_bridge.py --server-url http://your-django-server:8000

주의: 이 파일은 반드시 Windows에서 32bit Python으로 실행해야 합니다.
"""
import sys
import time
import json
import logging
import argparse
import threading
from flask import Flask, request, jsonify

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 키움 API 인스턴스 (전역)
kiwoom = None
django_server_url = 'http://localhost:8000'


class KiwoomAPI:
    """키움 OpenAPI+ COM 래퍼"""

    def __init__(self):
        self.connected = False
        self.ocx = None
        self.account_no = ''
        self.condition_list = {}
        self._event_handlers = {}

        try:
            import pythoncom
            import win32com.client
            self.pythoncom = pythoncom
            self.win32com = win32com
            self._init_ocx()
        except ImportError:
            logger.warning("pywin32를 찾을 수 없습니다. 시뮬레이션 모드로 실행합니다.")
            self.simulation_mode = True

    def _init_ocx(self):
        """키움 OpenAPI OCX 초기화"""
        try:
            self.ocx = self.win32com.client.Dispatch("KHOPENAPI.KHOpenAPICtrl.1")
            self.simulation_mode = False
            self._connect_events()
            logger.info("키움 OpenAPI OCX 초기화 완료")
        except Exception as e:
            logger.error("키움 OpenAPI OCX 초기화 실패: %s", e)
            self.simulation_mode = True

    def _connect_events(self):
        """이벤트 핸들러 연결"""
        if self.simulation_mode:
            return
        try:
            import win32com.client
            handler = win32com.client.WithEvents(self.ocx, KiwoomEventHandler)
            handler.api = self
        except Exception as e:
            logger.error("이벤트 핸들러 연결 실패: %s", e)

    # ===== 접속 =====

    def connect(self, trade_mode='mock'):
        """로그인"""
        if self.simulation_mode:
            self.connected = True
            return {'success': True, 'message': '시뮬레이션 모드 접속'}

        # 모의투자 서버 설정
        if trade_mode == 'mock':
            self.ocx.KOA_Functions("SetServerGubun", "1")
        else:
            self.ocx.KOA_Functions("SetServerGubun", "0")

        ret = self.ocx.CommConnect()
        if ret == 0:
            self.connected = True
            return {'success': True}
        return {'success': False, 'error': f'로그인 실패 (코드: {ret})'}

    def get_connect_state(self):
        """접속 상태"""
        if self.simulation_mode:
            return {'connected': self.connected}
        state = self.ocx.GetConnectState()
        return {'connected': state == 1}

    # ===== 조건검색 =====

    def get_condition_list(self):
        """조건검색식 목록 조회"""
        if self.simulation_mode:
            return {
                'conditions': [
                    {'index': 0, 'name': '테스트조건1'},
                    {'index': 1, 'name': '테스트조건2'},
                ]
            }

        ret = self.ocx.GetConditionLoad()
        if ret != 1:
            return {'error': '조건검색식 로드 실패'}

        # 조건식 목록 파싱
        raw = self.ocx.GetConditionNameList()
        conditions = []
        for item in raw.split(';'):
            if '^' in item:
                idx, name = item.split('^')
                conditions.append({'index': int(idx), 'name': name})
                self.condition_list[int(idx)] = name

        return {'conditions': conditions}

    def send_condition(self, screen_no, condition_name, condition_index, is_realtime=True):
        """조건검색 실행"""
        if self.simulation_mode:
            return {
                'stocks': ['005930', '000660', '035420'],
                'message': f'조건검색 실행: {condition_name}'
            }

        search_type = 1 if is_realtime else 0
        ret = self.ocx.SendCondition(screen_no, condition_name, condition_index, search_type)

        if ret == 1:
            return {'message': f'조건검색 실행 성공: {condition_name}', 'stocks': []}
        return {'error': f'조건검색 실행 실패: {condition_name}'}

    def stop_condition(self, screen_no, condition_name, condition_index):
        """실시간 조건검색 중지"""
        if self.simulation_mode:
            return {'message': f'조건검색 중지: {condition_name}'}

        self.ocx.SendConditionStop(screen_no, condition_name, condition_index)
        return {'message': f'조건검색 중지: {condition_name}'}

    # ===== 시세 =====

    def get_stock_price(self, stock_code):
        """현재가 조회"""
        if self.simulation_mode:
            return {
                'stock_code': stock_code,
                'current_price': 50000,
                'open_price': 49500,
                'high_price': 51000,
                'low_price': 49000,
                'volume': 1234567,
                'change_rate': 1.01,
            }

        self.ocx.SetInputValue("종목코드", stock_code)
        self.ocx.CommRqData("주식기본정보요청", "opt10001", 0, "0101")

        # 동기 대기 (실제로는 이벤트 기반)
        time.sleep(0.5)

        current_price = abs(int(self.ocx.GetCommData("opt10001", "주식기본정보요청", 0, "현재가").strip()))
        open_price = abs(int(self.ocx.GetCommData("opt10001", "주식기본정보요청", 0, "시가").strip()))
        high_price = abs(int(self.ocx.GetCommData("opt10001", "주식기본정보요청", 0, "고가").strip()))
        low_price = abs(int(self.ocx.GetCommData("opt10001", "주식기본정보요청", 0, "저가").strip()))
        volume = abs(int(self.ocx.GetCommData("opt10001", "주식기본정보요청", 0, "거래량").strip()))

        return {
            'stock_code': stock_code,
            'current_price': current_price,
            'open_price': open_price,
            'high_price': high_price,
            'low_price': low_price,
            'volume': volume,
        }

    def get_stock_info(self, stock_code):
        """종목 기본정보"""
        if self.simulation_mode:
            return {
                'code': stock_code,
                'name': f'시뮬종목_{stock_code}',
                'market': 'KOSPI',
            }

        name = self.ocx.GetMasterCodeName(stock_code)
        market_code = self.ocx.GetMasterStockState(stock_code)
        market = 'KOSDAQ' if '코스닥' in market_code else 'KOSPI'

        return {'code': stock_code, 'name': name, 'market': market}

    # ===== 주문 =====

    def send_order(self, order_type, stock_code, quantity, price, price_type, account_no):
        """주문 전송"""
        if self.simulation_mode:
            import random
            order_no = str(random.randint(100000, 999999))
            logger.info(
                "시뮬레이션 주문: %s %s %d주 @ %d (주문번호: %s)",
                '매수' if order_type == 1 else '매도',
                stock_code, quantity, price, order_no
            )
            # 시뮬레이션: 바로 체결 콜백 전송
            threading.Timer(1.0, self._sim_fill_callback, args=(order_no, quantity, price, stock_code)).start()
            return {'order_no': order_no}

        ret = self.ocx.SendOrder(
            "주문",        # 사용자구분명
            "0101",       # 화면번호
            account_no,
            order_type,   # 1:매수, 2:매도
            stock_code,
            quantity,
            price,
            price_type,   # 00:지정가, 03:시장가
            ""            # 원주문번호
        )

        if ret == 0:
            return {'message': '주문 접수 성공'}
        return {'error': f'주문 실패 (코드: {ret})'}

    def _sim_fill_callback(self, order_no, quantity, price, stock_code):
        """시뮬레이션 체결 콜백"""
        import requests as req
        try:
            if price <= 0:
                price = 50000
            req.post(
                f"{django_server_url}/api/callback/order-filled/",
                json={
                    'order_no': order_no,
                    'filled_quantity': quantity,
                    'filled_price': price,
                },
                timeout=5,
            )
        except Exception as e:
            logger.error("시뮬레이션 체결 콜백 실패: %s", e)

    # ===== 잔고 =====

    def get_balance(self, account_no):
        """잔고 조회"""
        if self.simulation_mode:
            return {'items': []}

        self.ocx.SetInputValue("계좌번호", account_no)
        self.ocx.SetInputValue("비밀번호", "")
        self.ocx.SetInputValue("비밀번호입력매체구분", "00")
        self.ocx.SetInputValue("조회구분", "1")
        self.ocx.CommRqData("계좌평가잔고내역요청", "opw00018", 0, "0102")

        time.sleep(0.5)
        # 실제 구현에서는 OnReceiveTrData 이벤트에서 데이터 수집
        return {'items': []}


class KiwoomEventHandler:
    """키움 OpenAPI 이벤트 핸들러"""
    api = None

    def OnReceiveConditionVer(self, ret, msg):
        """조건검색식 로드 완료"""
        logger.info("조건검색식 로드: ret=%d, msg=%s", ret, msg)

    def OnReceiveTrCondition(self, screen_no, code_list, condition_name, condition_index, next_flag):
        """조건검색 결과 수신"""
        import requests as req
        codes = [c for c in code_list.split(';') if c]
        logger.info("조건검색 결과 [%s]: %d종목", condition_name, len(codes))

        # Django 서버에 편입 알림
        for code in codes:
            try:
                req.post(
                    f"{django_server_url}/api/callback/condition-match/",
                    json={
                        'condition_id': condition_index,
                        'stock_code': code,
                        'match_type': 'I',
                    },
                    timeout=5,
                )
            except Exception as e:
                logger.error("조건검색 콜백 실패: %s", e)

    def OnReceiveRealCondition(self, stock_code, event_type, condition_name, condition_index):
        """실시간 조건검색 편입/이탈"""
        import requests as req
        match_type = 'I' if event_type == 'I' else 'D'
        logger.info(
            "실시간 조건검색 %s: [%s] %s",
            '편입' if match_type == 'I' else '이탈',
            condition_name, stock_code
        )

        try:
            req.post(
                f"{django_server_url}/api/callback/condition-match/",
                json={
                    'condition_id': int(condition_index),
                    'stock_code': stock_code,
                    'match_type': match_type,
                },
                timeout=5,
            )
        except Exception as e:
            logger.error("실시간 조건검색 콜백 실패: %s", e)

    def OnReceiveChejanData(self, gubun, item_cnt, fid_list):
        """체결/잔고 변경"""
        import requests as req
        if gubun == '0':  # 주문체결
            order_no = self.api.ocx.GetChejanData(9203).strip()
            filled_qty = abs(int(self.api.ocx.GetChejanData(911).strip() or '0'))
            filled_price = abs(int(self.api.ocx.GetChejanData(910).strip() or '0'))

            if filled_qty > 0 and filled_price > 0:
                try:
                    req.post(
                        f"{django_server_url}/api/callback/order-filled/",
                        json={
                            'order_no': order_no,
                            'filled_quantity': filled_qty,
                            'filled_price': filled_price,
                        },
                        timeout=5,
                    )
                except Exception as e:
                    logger.error("체결 콜백 실패: %s", e)


# ===== Flask API 엔드포인트 =====

@app.route('/api/connect', methods=['POST'])
def connect():
    data = request.get_json() or {}
    result = kiwoom.connect(trade_mode=data.get('trade_mode', 'mock'))
    return jsonify(result)


@app.route('/api/connect/state', methods=['GET'])
def connect_state():
    return jsonify(kiwoom.get_connect_state())


@app.route('/api/condition/list', methods=['GET'])
def condition_list():
    return jsonify(kiwoom.get_condition_list())


@app.route('/api/condition/search', methods=['POST'])
def condition_search():
    data = request.get_json()
    result = kiwoom.send_condition(
        screen_no=data['screen_no'],
        condition_name=data['condition_name'],
        condition_index=data['condition_index'],
        is_realtime=data.get('is_realtime', True),
    )
    return jsonify(result)


@app.route('/api/condition/stop', methods=['POST'])
def condition_stop():
    data = request.get_json()
    result = kiwoom.stop_condition(
        screen_no=data['screen_no'],
        condition_name=data['condition_name'],
        condition_index=data['condition_index'],
    )
    return jsonify(result)


@app.route('/api/stock/price', methods=['GET'])
def stock_price():
    code = request.args.get('code')
    return jsonify(kiwoom.get_stock_price(code))


@app.route('/api/stock/info', methods=['GET'])
def stock_info():
    code = request.args.get('code')
    return jsonify(kiwoom.get_stock_info(code))


@app.route('/api/order', methods=['POST'])
def order():
    data = request.get_json()
    result = kiwoom.send_order(
        order_type=data['order_type'],
        stock_code=data['stock_code'],
        quantity=data['quantity'],
        price=data.get('price', 0),
        price_type=data.get('price_type', '03'),
        account_no=data['account_no'],
    )
    return jsonify(result)


@app.route('/api/order/cancel', methods=['POST'])
def order_cancel():
    return jsonify({'message': '주문 취소 기능 (미구현)'})


@app.route('/api/balance', methods=['GET'])
def balance():
    account_no = request.args.get('account_no', '')
    return jsonify(kiwoom.get_balance(account_no))


@app.route('/api/orders', methods=['GET'])
def orders():
    return jsonify({'orders': []})


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'running',
        'connected': kiwoom.connected if kiwoom else False,
        'simulation_mode': getattr(kiwoom, 'simulation_mode', True),
    })


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='키움 OpenAPI+ 브릿지 에이전트')
    parser.add_argument('--host', default='0.0.0.0', help='바인드 호스트')
    parser.add_argument('--port', type=int, default=5000, help='바인드 포트')
    parser.add_argument('--server-url', default='http://localhost:8000', help='Django 서버 URL')
    args = parser.parse_args()

    django_server_url = args.server_url
    kiwoom = KiwoomAPI()

    logger.info("키움 브릿지 에이전트 시작")
    logger.info("Django 서버: %s", django_server_url)
    logger.info("시뮬레이션 모드: %s", getattr(kiwoom, 'simulation_mode', True))

    app.run(host=args.host, port=args.port, debug=False)
