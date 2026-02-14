"""
키움증권 주식 트레이딩 시스템 - PyQt5 데스크탑 UI
Django REST API (http://localhost:8000/api/)에 연결하여 트레이딩 기능을 관리합니다.
"""

import sys
import requests
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QComboBox, QLineEdit, QSpinBox, QGroupBox, QHeaderView, QStatusBar,
    QMessageBox, QAbstractItemView, QFrame, QSplitter
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QIntValidator

API_BASE = "http://localhost:8000/api"


def fmt_amount(value):
    """금액을 콤마 구분 포맷으로 변환"""
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return str(value)


def fmt_rate(value):
    """수익률 포맷 (소수점 2자리)"""
    try:
        return f"{float(value):.2f}%"
    except (ValueError, TypeError):
        return str(value)


def api_get(endpoint):
    """API GET 요청"""
    try:
        resp = requests.get(f"{API_BASE}/{endpoint}", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        return {"error": "API 서버에 연결할 수 없습니다."}
    except requests.exceptions.Timeout:
        return {"error": "API 요청 시간 초과"}
    except requests.exceptions.HTTPError as e:
        try:
            return e.response.json()
        except Exception:
            return {"error": f"HTTP {e.response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def api_post(endpoint, data=None):
    """API POST 요청"""
    try:
        resp = requests.post(f"{API_BASE}/{endpoint}", json=data or {}, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        return {"error": "API 서버에 연결할 수 없습니다."}
    except requests.exceptions.Timeout:
        return {"error": "API 요청 시간 초과"}
    except requests.exceptions.HTTPError as e:
        try:
            return e.response.json()
        except Exception:
            return {"error": f"HTTP {e.response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def api_patch(endpoint, data=None):
    """API PATCH 요청"""
    try:
        resp = requests.patch(f"{API_BASE}/{endpoint}", json=data or {}, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        return {"error": "API 서버에 연결할 수 없습니다."}
    except requests.exceptions.Timeout:
        return {"error": "API 요청 시간 초과"}
    except requests.exceptions.HTTPError as e:
        try:
            return e.response.json()
        except Exception:
            return {"error": f"HTTP {e.response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


class TradingConfigTab(QWidget):
    """매매설정 탭"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 현재 설정 그룹
        config_group = QGroupBox("현재 매매 설정")
        config_layout = QGridLayout()

        labels = ["모드:", "계좌번호:", "최대매수금액:", "종목당 최대매수:", "설정명:", "상태:"]
        self.value_labels = {}
        keys = ["trade_mode", "account_no", "max_buy_amount", "max_buy_per_stock", "name", "is_active"]

        for i, (label_text, key) in enumerate(zip(labels, keys)):
            row, col = divmod(i, 2)
            label = QLabel(label_text)
            label.setFont(QFont("맑은 고딕", 10, QFont.Bold))
            value = QLabel("-")
            value.setFont(QFont("맑은 고딕", 10))
            config_layout.addWidget(label, row, col * 2)
            config_layout.addWidget(value, row, col * 2 + 1)
            self.value_labels[key] = value

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # 모드 전환 버튼
        mode_group = QGroupBox("모드 전환")
        mode_layout = QHBoxLayout()

        self.btn_mock = QPushButton("모의투자 모드로 전환")
        self.btn_mock.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; padding: 10px; font-size: 13px; }")
        self.btn_mock.clicked.connect(lambda: self.switch_mode("mock"))

        self.btn_real = QPushButton("실투자 모드로 전환")
        self.btn_real.setStyleSheet("QPushButton { background-color: #f44336; color: white; padding: 10px; font-size: 13px; }")
        self.btn_real.clicked.connect(lambda: self.switch_mode("real"))

        self.btn_refresh = QPushButton("새로고침")
        self.btn_refresh.setStyleSheet("QPushButton { padding: 10px; font-size: 13px; }")
        self.btn_refresh.clicked.connect(self.load_config)

        mode_layout.addWidget(self.btn_mock)
        mode_layout.addWidget(self.btn_real)
        mode_layout.addWidget(self.btn_refresh)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # 전체 설정 목록
        list_group = QGroupBox("전체 설정 목록")
        list_layout = QVBoxLayout()

        self.config_table = QTableWidget()
        self.config_table.setColumnCount(7)
        self.config_table.setHorizontalHeaderLabels(["ID", "설정명", "모드", "계좌번호", "최대매수금액", "종목당 최대", "활성"])
        self.config_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.config_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.config_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        list_layout.addWidget(self.config_table)

        list_group.setLayout(list_layout)
        layout.addWidget(list_group)

        layout.addStretch()

    def load_config(self):
        """현재 활성 설정 로드"""
        data = api_get("config/current/")
        if "error" in data:
            self.main_window.update_status(f"설정 로드 실패: {data['error']}")
            for v in self.value_labels.values():
                v.setText("-")
            return

        mode_text = data.get("mode_display", data.get("trade_mode", "-"))
        self.value_labels["trade_mode"].setText(mode_text)
        self.value_labels["account_no"].setText(data.get("account_no", "-") or "-")
        self.value_labels["max_buy_amount"].setText(fmt_amount(data.get("max_buy_amount", 0)))
        self.value_labels["max_buy_per_stock"].setText(fmt_amount(data.get("max_buy_per_stock", 0)))
        self.value_labels["name"].setText(data.get("name", "-"))
        self.value_labels["is_active"].setText("활성" if data.get("is_active") else "비활성")

        if self.main_window:
            self.main_window.current_mode = data.get("trade_mode", "")
            self.main_window.update_status(f"설정 로드 완료 - {mode_text}")

        # 전체 목록도 로드
        self.load_config_list()

    def load_config_list(self):
        """전체 설정 목록 로드"""
        data = api_get("config/")
        if isinstance(data, dict) and "error" in data:
            return

        results = data if isinstance(data, list) else data.get("results", data)
        if not isinstance(results, list):
            return

        self.config_table.setRowCount(len(results))
        for row, item in enumerate(results):
            self.config_table.setItem(row, 0, QTableWidgetItem(str(item.get("id", ""))))
            self.config_table.setItem(row, 1, QTableWidgetItem(item.get("name", "")))
            self.config_table.setItem(row, 2, QTableWidgetItem(item.get("mode_display", item.get("trade_mode", ""))))
            self.config_table.setItem(row, 3, QTableWidgetItem(item.get("account_no", "") or ""))
            self.config_table.setItem(row, 4, QTableWidgetItem(fmt_amount(item.get("max_buy_amount", 0))))
            self.config_table.setItem(row, 5, QTableWidgetItem(fmt_amount(item.get("max_buy_per_stock", 0))))
            active_item = QTableWidgetItem("●" if item.get("is_active") else "")
            active_item.setTextAlignment(Qt.AlignCenter)
            if item.get("is_active"):
                active_item.setForeground(QColor("#4CAF50"))
            self.config_table.setItem(row, 6, active_item)

    def switch_mode(self, mode):
        """모드 전환"""
        confirm = QMessageBox.question(
            self, "모드 전환 확인",
            f"{'모의투자' if mode == 'mock' else '실투자'} 모드로 전환하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        result = api_post("config/switch_mode/", {"mode": mode})
        if "error" in result:
            QMessageBox.warning(self, "오류", f"모드 전환 실패: {result['error']}")
        else:
            QMessageBox.information(self, "성공", f"{'모의투자' if mode == 'mock' else '실투자'} 모드로 전환되었습니다.")
            self.load_config()


class ConditionSearchTab(QWidget):
    """조건검색 탭"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 상단 버튼
        btn_layout = QHBoxLayout()
        self.btn_load = QPushButton("조건식 불러오기")
        self.btn_load.setStyleSheet("QPushButton { background-color: #2196F3; color: white; padding: 8px 16px; font-size: 12px; }")
        self.btn_load.clicked.connect(self.load_conditions)

        self.btn_start = QPushButton("선택 조건식 시작")
        self.btn_start.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; padding: 8px 16px; font-size: 12px; }")
        self.btn_start.clicked.connect(self.start_condition)

        self.btn_stop = QPushButton("선택 조건식 중지")
        self.btn_stop.setStyleSheet("QPushButton { background-color: #f44336; color: white; padding: 8px 16px; font-size: 12px; }")
        self.btn_stop.clicked.connect(self.stop_condition)

        self.btn_toggle_auto = QPushButton("자동매매 토글")
        self.btn_toggle_auto.setStyleSheet("QPushButton { background-color: #FF9800; color: white; padding: 8px 16px; font-size: 12px; }")
        self.btn_toggle_auto.clicked.connect(self.toggle_auto_trade)

        self.btn_refresh = QPushButton("새로고침")
        self.btn_refresh.setStyleSheet("QPushButton { padding: 8px 16px; font-size: 12px; }")
        self.btn_refresh.clicked.connect(self.refresh_conditions)

        btn_layout.addWidget(self.btn_load)
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_stop)
        btn_layout.addWidget(self.btn_toggle_auto)
        btn_layout.addWidget(self.btn_refresh)
        layout.addLayout(btn_layout)

        # 스플리터로 상/하 분리
        splitter = QSplitter(Qt.Vertical)

        # 조건식 목록 테이블
        cond_widget = QWidget()
        cond_layout = QVBoxLayout(cond_widget)
        cond_layout.setContentsMargins(0, 0, 0, 0)
        cond_label = QLabel("조건검색식 목록")
        cond_label.setFont(QFont("맑은 고딕", 11, QFont.Bold))
        cond_layout.addWidget(cond_label)

        self.condition_table = QTableWidget()
        self.condition_table.setColumnCount(6)
        self.condition_table.setHorizontalHeaderLabels(["ID", "인덱스", "조건식 이름", "상태", "자동매매", "실시간"])
        self.condition_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.condition_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.condition_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.condition_table.currentItemChanged.connect(self.on_condition_selected)
        cond_layout.addWidget(self.condition_table)
        splitter.addWidget(cond_widget)

        # 매칭 결과 테이블
        match_widget = QWidget()
        match_layout = QVBoxLayout(match_widget)
        match_layout.setContentsMargins(0, 0, 0, 0)
        match_label = QLabel("매칭 결과")
        match_label.setFont(QFont("맑은 고딕", 11, QFont.Bold))
        match_layout.addWidget(match_label)

        self.match_table = QTableWidget()
        self.match_table.setColumnCount(5)
        self.match_table.setHorizontalHeaderLabels(["종목코드", "종목명", "매칭유형", "매칭시각", "시장"])
        self.match_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.match_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.match_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        match_layout.addWidget(self.match_table)
        splitter.addWidget(match_widget)

        layout.addWidget(splitter)

    def get_selected_condition_id(self):
        """선택된 조건식 ID 반환"""
        row = self.condition_table.currentRow()
        if row < 0:
            return None
        item = self.condition_table.item(row, 0)
        return item.text() if item else None

    def load_conditions(self):
        """조건식 불러오기 (키움에서 로드)"""
        self.btn_load.setEnabled(False)
        result = api_post("conditions/load/")
        self.btn_load.setEnabled(True)

        if isinstance(result, dict) and "error" in result:
            QMessageBox.warning(self, "오류", f"조건식 로드 실패: {result['error']}")
        else:
            self.main_window.update_status("조건식 로드 완료")
            self.refresh_conditions()

    def refresh_conditions(self):
        """조건식 목록 갱신"""
        data = api_get("conditions/")
        if isinstance(data, dict) and "error" in data:
            self.main_window.update_status(f"조건식 갱신 실패: {data['error']}")
            return

        results = data if isinstance(data, list) else data.get("results", data)
        if not isinstance(results, list):
            return

        self.condition_table.setRowCount(len(results))
        for row, item in enumerate(results):
            self.condition_table.setItem(row, 0, QTableWidgetItem(str(item.get("id", ""))))
            self.condition_table.setItem(row, 1, QTableWidgetItem(str(item.get("condition_index", ""))))
            self.condition_table.setItem(row, 2, QTableWidgetItem(item.get("condition_name", "")))

            status = item.get("status_display", item.get("status", ""))
            status_item = QTableWidgetItem(status)
            status_item.setTextAlignment(Qt.AlignCenter)
            if item.get("status") == "active":
                status_item.setForeground(QColor("#4CAF50"))
            elif item.get("status") == "error":
                status_item.setForeground(QColor("#f44336"))
            self.condition_table.setItem(row, 3, status_item)

            auto_item = QTableWidgetItem("ON" if item.get("auto_trade") else "OFF")
            auto_item.setTextAlignment(Qt.AlignCenter)
            if item.get("auto_trade"):
                auto_item.setForeground(QColor("#4CAF50"))
            else:
                auto_item.setForeground(QColor("#999999"))
            self.condition_table.setItem(row, 4, auto_item)

            rt_item = QTableWidgetItem("●" if item.get("is_realtime") else "")
            rt_item.setTextAlignment(Qt.AlignCenter)
            self.condition_table.setItem(row, 5, rt_item)

        self.main_window.update_status("조건식 목록 갱신 완료")

    def on_condition_selected(self, current, previous):
        """조건식 선택 시 매칭 결과 로드"""
        cond_id = self.get_selected_condition_id()
        if cond_id:
            self.load_matches(cond_id)

    def load_matches(self, condition_id):
        """매칭 결과 로드"""
        data = api_get(f"conditions/{condition_id}/matches/")
        if isinstance(data, dict) and "error" in data:
            self.match_table.setRowCount(0)
            return

        results = data if isinstance(data, list) else data.get("results", data)
        if not isinstance(results, list):
            self.match_table.setRowCount(0)
            return

        self.match_table.setRowCount(len(results))
        for row, item in enumerate(results):
            stock = item.get("stock", {})
            self.match_table.setItem(row, 0, QTableWidgetItem(stock.get("code", "")))
            self.match_table.setItem(row, 1, QTableWidgetItem(stock.get("name", "")))

            match_type = item.get("match_type_display", item.get("match_type", ""))
            type_item = QTableWidgetItem(match_type)
            type_item.setTextAlignment(Qt.AlignCenter)
            if item.get("match_type") == "I":
                type_item.setForeground(QColor("#f44336"))
            else:
                type_item.setForeground(QColor("#2196F3"))
            self.match_table.setItem(row, 2, type_item)

            matched_at = item.get("matched_at", "")
            if matched_at:
                try:
                    dt = datetime.fromisoformat(matched_at.replace("Z", "+00:00"))
                    matched_at = dt.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, AttributeError):
                    pass
            self.match_table.setItem(row, 3, QTableWidgetItem(matched_at))
            self.match_table.setItem(row, 4, QTableWidgetItem(stock.get("market", "")))

    def start_condition(self):
        """선택된 조건식 시작"""
        cond_id = self.get_selected_condition_id()
        if not cond_id:
            QMessageBox.warning(self, "알림", "조건식을 선택해주세요.")
            return
        result = api_post(f"conditions/{cond_id}/start/")
        if isinstance(result, dict) and "error" in result:
            QMessageBox.warning(self, "오류", f"시작 실패: {result['error']}")
        else:
            self.main_window.update_status("조건검색 시작됨")
            self.refresh_conditions()

    def stop_condition(self):
        """선택된 조건식 중지"""
        cond_id = self.get_selected_condition_id()
        if not cond_id:
            QMessageBox.warning(self, "알림", "조건식을 선택해주세요.")
            return
        result = api_post(f"conditions/{cond_id}/stop/")
        if isinstance(result, dict) and "error" in result:
            QMessageBox.warning(self, "오류", f"중지 실패: {result['error']}")
        else:
            self.main_window.update_status("조건검색 중지됨")
            self.refresh_conditions()

    def toggle_auto_trade(self):
        """자동매매 토글"""
        cond_id = self.get_selected_condition_id()
        if not cond_id:
            QMessageBox.warning(self, "알림", "조건식을 선택해주세요.")
            return
        result = api_patch(f"conditions/{cond_id}/toggle_auto_trade/")
        if isinstance(result, dict) and "error" in result:
            QMessageBox.warning(self, "오류", f"토글 실패: {result['error']}")
        else:
            auto = result.get("auto_trade", False)
            self.main_window.update_status(f"자동매매 {'활성화' if auto else '비활성화'}")
            self.refresh_conditions()


class OrdersTab(QWidget):
    """주문 탭"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 수동 주문 폼
        order_group = QGroupBox("수동 주문")
        form_layout = QGridLayout()

        form_layout.addWidget(QLabel("종목코드:"), 0, 0)
        self.input_stock_code = QLineEdit()
        self.input_stock_code.setPlaceholderText("예: 005930")
        self.input_stock_code.setMaxLength(6)
        form_layout.addWidget(self.input_stock_code, 0, 1)

        form_layout.addWidget(QLabel("매매유형:"), 0, 2)
        self.combo_order_type = QComboBox()
        self.combo_order_type.addItems(["매수 (buy)", "매도 (sell)"])
        form_layout.addWidget(self.combo_order_type, 0, 3)

        form_layout.addWidget(QLabel("수량:"), 1, 0)
        self.input_quantity = QSpinBox()
        self.input_quantity.setRange(1, 999999)
        self.input_quantity.setValue(1)
        form_layout.addWidget(self.input_quantity, 1, 1)

        form_layout.addWidget(QLabel("가격:"), 1, 2)
        self.input_price = QLineEdit()
        self.input_price.setPlaceholderText("시장가일 경우 0")
        self.input_price.setValidator(QIntValidator(0, 999999999))
        self.input_price.setText("0")
        form_layout.addWidget(self.input_price, 1, 3)

        form_layout.addWidget(QLabel("가격유형:"), 2, 0)
        self.combo_price_type = QComboBox()
        self.combo_price_type.addItems(["시장가 (market)", "지정가 (limit)"])
        form_layout.addWidget(self.combo_price_type, 2, 1)

        self.btn_place_order = QPushButton("주문하기")
        self.btn_place_order.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; padding: 10px 30px; font-size: 13px; font-weight: bold; }"
        )
        self.btn_place_order.clicked.connect(self.place_order)
        form_layout.addWidget(self.btn_place_order, 2, 2, 1, 2)

        order_group.setLayout(form_layout)
        layout.addWidget(order_group)

        # 주문 내역 테이블
        history_group = QGroupBox("주문 내역")
        history_layout = QVBoxLayout()

        btn_row = QHBoxLayout()
        self.btn_refresh_orders = QPushButton("새로고침")
        self.btn_refresh_orders.clicked.connect(self.load_orders)
        btn_row.addWidget(self.btn_refresh_orders)
        btn_row.addStretch()
        history_layout.addLayout(btn_row)

        self.order_table = QTableWidget()
        self.order_table.setColumnCount(9)
        self.order_table.setHorizontalHeaderLabels([
            "주문번호", "종목코드", "종목명", "유형", "가격유형", "수량", "가격", "상태", "주문시각"
        ])
        self.order_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.order_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.order_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        history_layout.addWidget(self.order_table)

        history_group.setLayout(history_layout)
        layout.addWidget(history_group)

    def place_order(self):
        """주문 실행"""
        stock_code = self.input_stock_code.text().strip()
        if not stock_code:
            QMessageBox.warning(self, "알림", "종목코드를 입력해주세요.")
            return

        order_type = "buy" if self.combo_order_type.currentIndex() == 0 else "sell"
        price_type = "market" if self.combo_price_type.currentIndex() == 0 else "limit"
        quantity = self.input_quantity.value()

        try:
            price = int(self.input_price.text() or "0")
        except ValueError:
            price = 0

        if price_type == "limit" and price <= 0:
            QMessageBox.warning(self, "알림", "지정가 주문은 가격을 입력해주세요.")
            return

        type_text = "매수" if order_type == "buy" else "매도"
        confirm = QMessageBox.question(
            self, "주문 확인",
            f"종목: {stock_code}\n유형: {type_text}\n수량: {quantity}\n"
            f"가격: {fmt_amount(price)} ({'시장가' if price_type == 'market' else '지정가'})\n\n주문하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        self.btn_place_order.setEnabled(False)
        result = api_post("orders/place/", {
            "stock_code": stock_code,
            "order_type": order_type,
            "quantity": quantity,
            "price": price,
            "price_type": price_type,
        })
        self.btn_place_order.setEnabled(True)

        if isinstance(result, dict) and "error" in result:
            QMessageBox.warning(self, "주문 실패", f"오류: {result['error']}")
        else:
            QMessageBox.information(self, "성공", "주문이 접수되었습니다.")
            self.main_window.update_status("주문 접수 완료")
            self.load_orders()

    def load_orders(self):
        """주문 내역 로드"""
        data = api_get("orders/")
        if isinstance(data, dict) and "error" in data:
            self.main_window.update_status(f"주문 내역 로드 실패: {data['error']}")
            return

        results = data if isinstance(data, list) else data.get("results", data)
        if not isinstance(results, list):
            return

        self.order_table.setRowCount(len(results))
        for row, item in enumerate(results):
            stock = item.get("stock", {})
            self.order_table.setItem(row, 0, QTableWidgetItem(item.get("order_no", "") or ""))
            self.order_table.setItem(row, 1, QTableWidgetItem(stock.get("code", "")))
            self.order_table.setItem(row, 2, QTableWidgetItem(stock.get("name", "")))

            otype = item.get("order_type_display", item.get("order_type", ""))
            type_item = QTableWidgetItem(otype)
            type_item.setTextAlignment(Qt.AlignCenter)
            if item.get("order_type") == "buy":
                type_item.setForeground(QColor("#f44336"))
            else:
                type_item.setForeground(QColor("#2196F3"))
            self.order_table.setItem(row, 3, type_item)

            self.order_table.setItem(row, 4, QTableWidgetItem(
                item.get("price_type_display", item.get("price_type", ""))
            ))

            qty_item = QTableWidgetItem(fmt_amount(item.get("quantity", 0)))
            qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.order_table.setItem(row, 5, qty_item)

            price_item = QTableWidgetItem(fmt_amount(item.get("price", 0)))
            price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.order_table.setItem(row, 6, price_item)

            status = item.get("status_display", item.get("status", ""))
            status_item = QTableWidgetItem(status)
            status_item.setTextAlignment(Qt.AlignCenter)
            if item.get("status") == "filled":
                status_item.setForeground(QColor("#4CAF50"))
            elif item.get("status") in ("cancelled", "rejected"):
                status_item.setForeground(QColor("#999999"))
            self.order_table.setItem(row, 7, status_item)

            created = item.get("created_at", "")
            if created:
                try:
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    created = dt.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, AttributeError):
                    pass
            self.order_table.setItem(row, 8, QTableWidgetItem(created))

        self.main_window.update_status("주문 내역 갱신 완료")


class BalanceTab(QWidget):
    """잔고 탭"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 버튼
        btn_layout = QHBoxLayout()
        self.btn_sync = QPushButton("잔고 동기화 (키움)")
        self.btn_sync.setStyleSheet("QPushButton { background-color: #2196F3; color: white; padding: 8px 16px; font-size: 12px; }")
        self.btn_sync.clicked.connect(self.sync_balance)

        self.btn_refresh = QPushButton("새로고침")
        self.btn_refresh.setStyleSheet("QPushButton { padding: 8px 16px; font-size: 12px; }")
        self.btn_refresh.clicked.connect(self.load_balance)

        btn_layout.addWidget(self.btn_sync)
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 잔고 테이블
        self.balance_table = QTableWidget()
        self.balance_table.setColumnCount(7)
        self.balance_table.setHorizontalHeaderLabels([
            "종목코드", "종목명", "수량", "평균매입가", "현재가", "수익률", "평가손익"
        ])
        self.balance_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.balance_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.balance_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.balance_table)

    def load_balance(self):
        """잔고 로드"""
        data = api_get("balance/")
        if isinstance(data, dict) and "error" in data:
            self.main_window.update_status(f"잔고 로드 실패: {data['error']}")
            return

        results = data if isinstance(data, list) else data.get("results", data)
        if not isinstance(results, list):
            return

        self.balance_table.setRowCount(len(results))
        for row, item in enumerate(results):
            stock = item.get("stock", {})
            self.balance_table.setItem(row, 0, QTableWidgetItem(stock.get("code", "")))
            self.balance_table.setItem(row, 1, QTableWidgetItem(stock.get("name", "")))

            qty_item = QTableWidgetItem(fmt_amount(item.get("quantity", 0)))
            qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.balance_table.setItem(row, 2, qty_item)

            avg_item = QTableWidgetItem(fmt_amount(item.get("avg_price", 0)))
            avg_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.balance_table.setItem(row, 3, avg_item)

            cur_item = QTableWidgetItem(fmt_amount(item.get("current_price", 0)))
            cur_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.balance_table.setItem(row, 4, cur_item)

            # 수익률 색상 표시
            profit_rate = float(item.get("profit_rate", 0) or 0)
            rate_item = QTableWidgetItem(fmt_rate(profit_rate))
            rate_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if profit_rate > 0:
                rate_item.setForeground(QColor("#f44336"))  # 빨간색 (양수)
            elif profit_rate < 0:
                rate_item.setForeground(QColor("#2196F3"))  # 파란색 (음수)
            rate_item.setFont(QFont("맑은 고딕", 10, QFont.Bold))
            self.balance_table.setItem(row, 5, rate_item)

            # 평가손익 색상 표시
            profit_amount = int(item.get("profit_amount", 0) or 0)
            pnl_item = QTableWidgetItem(fmt_amount(profit_amount))
            pnl_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if profit_amount > 0:
                pnl_item.setForeground(QColor("#f44336"))
            elif profit_amount < 0:
                pnl_item.setForeground(QColor("#2196F3"))
            pnl_item.setFont(QFont("맑은 고딕", 10, QFont.Bold))
            self.balance_table.setItem(row, 6, pnl_item)

        self.main_window.update_status("잔고 갱신 완료")

    def sync_balance(self):
        """잔고 동기화"""
        self.btn_sync.setEnabled(False)
        result = api_post("balance/sync/")
        self.btn_sync.setEnabled(True)

        if isinstance(result, dict) and "error" in result:
            QMessageBox.warning(self, "오류", f"잔고 동기화 실패: {result['error']}")
        else:
            self.main_window.update_status("잔고 동기화 완료")
            self.load_balance()


class TradeHistoryTab(QWidget):
    """체결내역 탭"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 버튼
        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("새로고침")
        self.btn_refresh.setStyleSheet("QPushButton { padding: 8px 16px; font-size: 12px; }")
        self.btn_refresh.clicked.connect(self.load_trades)
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 체결내역 테이블
        self.trade_table = QTableWidget()
        self.trade_table.setColumnCount(7)
        self.trade_table.setHorizontalHeaderLabels([
            "종목코드", "종목명", "매매유형", "수량", "가격", "체결금액", "체결시각"
        ])
        self.trade_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.trade_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.trade_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.trade_table)

    def load_trades(self):
        """체결내역 로드"""
        data = api_get("trades/")
        if isinstance(data, dict) and "error" in data:
            self.main_window.update_status(f"체결내역 로드 실패: {data['error']}")
            return

        results = data if isinstance(data, list) else data.get("results", data)
        if not isinstance(results, list):
            return

        self.trade_table.setRowCount(len(results))
        for row, item in enumerate(results):
            stock = item.get("stock", {})
            self.trade_table.setItem(row, 0, QTableWidgetItem(stock.get("code", "")))
            self.trade_table.setItem(row, 1, QTableWidgetItem(stock.get("name", "")))

            otype = item.get("order_type", "")
            type_text = "매수" if otype == "buy" else "매도" if otype == "sell" else otype
            type_item = QTableWidgetItem(type_text)
            type_item.setTextAlignment(Qt.AlignCenter)
            if otype == "buy":
                type_item.setForeground(QColor("#f44336"))
            else:
                type_item.setForeground(QColor("#2196F3"))
            self.trade_table.setItem(row, 2, type_item)

            qty_item = QTableWidgetItem(fmt_amount(item.get("quantity", 0)))
            qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.trade_table.setItem(row, 3, qty_item)

            price_item = QTableWidgetItem(fmt_amount(item.get("price", 0)))
            price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.trade_table.setItem(row, 4, price_item)

            total_item = QTableWidgetItem(fmt_amount(item.get("total_amount", 0)))
            total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.trade_table.setItem(row, 5, total_item)

            traded_at = item.get("traded_at", "")
            if traded_at:
                try:
                    dt = datetime.fromisoformat(traded_at.replace("Z", "+00:00"))
                    traded_at = dt.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, AttributeError):
                    pass
            self.trade_table.setItem(row, 6, QTableWidgetItem(traded_at))

        self.main_window.update_status("체결내역 갱신 완료")


class MainWindow(QMainWindow):
    """메인 윈도우"""

    def __init__(self):
        super().__init__()
        self.current_mode = ""
        self.api_connected = False
        self.init_ui()
        self.setup_timer()
        self.initial_load()

    def init_ui(self):
        self.setWindowTitle("키움증권 트레이딩 시스템")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)

        # 탭 위젯
        self.tabs = QTabWidget()
        self.tabs.setFont(QFont("맑은 고딕", 11))
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #cccccc; }
            QTabBar::tab { padding: 8px 20px; font-size: 13px; }
            QTabBar::tab:selected { background-color: #e3f2fd; font-weight: bold; }
        """)

        self.config_tab = TradingConfigTab(self)
        self.condition_tab = ConditionSearchTab(self)
        self.orders_tab = OrdersTab(self)
        self.balance_tab = BalanceTab(self)
        self.trade_history_tab = TradeHistoryTab(self)

        self.tabs.addTab(self.config_tab, "매매설정")
        self.tabs.addTab(self.condition_tab, "조건검색")
        self.tabs.addTab(self.orders_tab, "주문")
        self.tabs.addTab(self.balance_tab, "잔고")
        self.tabs.addTab(self.trade_history_tab, "체결내역")

        self.setCentralWidget(self.tabs)

        # 상태바
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("초기화 중...")
        self.mode_label = QLabel("")
        self.time_label = QLabel("")
        self.status_bar.addWidget(self.status_label, 1)
        self.status_bar.addPermanentWidget(self.mode_label)
        self.status_bar.addPermanentWidget(self.time_label)

    def setup_timer(self):
        """30초 간격 자동 갱신 타이머"""
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.auto_refresh)
        self.refresh_timer.start(30000)

        # 시간 표시 타이머 (1초)
        self.time_timer = QTimer(self)
        self.time_timer.timeout.connect(self.update_time)
        self.time_timer.start(1000)

    def initial_load(self):
        """초기 데이터 로드"""
        self.config_tab.load_config()
        self.condition_tab.refresh_conditions()
        self.orders_tab.load_orders()
        self.balance_tab.load_balance()
        self.trade_history_tab.load_trades()

    def auto_refresh(self):
        """자동 갱신"""
        current_tab = self.tabs.currentIndex()
        if current_tab == 0:
            self.config_tab.load_config()
        elif current_tab == 1:
            self.condition_tab.refresh_conditions()
            cond_id = self.condition_tab.get_selected_condition_id()
            if cond_id:
                self.condition_tab.load_matches(cond_id)
        elif current_tab == 2:
            self.orders_tab.load_orders()
        elif current_tab == 3:
            self.balance_tab.load_balance()
        elif current_tab == 4:
            self.trade_history_tab.load_trades()

    def update_status(self, message):
        """상태바 메시지 업데이트"""
        self.api_connected = "실패" not in message and "연결할 수 없" not in message
        conn_text = "● 연결됨" if self.api_connected else "○ 연결 끊김"
        conn_color = "#4CAF50" if self.api_connected else "#f44336"

        self.status_label.setText(f"<span style='color:{conn_color}'>{conn_text}</span>  |  {message}")

        if self.current_mode:
            mode_text = "모의투자" if self.current_mode == "mock" else "실투자"
            mode_color = "#4CAF50" if self.current_mode == "mock" else "#f44336"
            self.mode_label.setText(f"<span style='color:{mode_color}; font-weight:bold;'>[{mode_text}]</span>")

    def update_time(self):
        """현재 시간 표시"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.time_label.setText(now)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 전체 폰트 설정
    font = QFont("맑은 고딕", 10)
    app.setFont(font)

    # 전체 스타일시트
    app.setStyleSheet("""
        QMainWindow { background-color: #fafafa; }
        QGroupBox {
            font-weight: bold;
            font-size: 12px;
            border: 1px solid #cccccc;
            border-radius: 4px;
            margin-top: 10px;
            padding-top: 15px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }
        QTableWidget {
            gridline-color: #e0e0e0;
            alternate-background-color: #f5f5f5;
            selection-background-color: #bbdefb;
        }
        QTableWidget::item { padding: 4px; }
        QHeaderView::section {
            background-color: #e3f2fd;
            padding: 6px;
            border: 1px solid #cccccc;
            font-weight: bold;
        }
        QPushButton {
            border: 1px solid #cccccc;
            border-radius: 4px;
            padding: 6px 12px;
        }
        QPushButton:hover { background-color: #e3f2fd; }
        QPushButton:pressed { background-color: #bbdefb; }
        QPushButton:disabled { background-color: #eeeeee; color: #999999; }
        QLineEdit, QSpinBox, QComboBox {
            border: 1px solid #cccccc;
            border-radius: 3px;
            padding: 5px;
        }
        QStatusBar { font-size: 11px; }
    """)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
