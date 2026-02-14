"""UI 자동화 테스트 (headless offscreen 모드)"""
import os
import sys

# Nix 환경 라이브러리 경로 설정
nix_libs = [
    "/nix/store/6lzcb4zv3lysq4yjhmgi1dkc6fqrgphy-libglvnd-1.7.0/lib",
    "/nix/store/3c275grvmby79gqgnjych830sld6bziw-glib-2.80.2/lib",
    "/nix/store/35kyrfkzrm1am5l91iz0srdp2wh8j1an-fontconfig-2.15.0-lib/lib",
    "/nix/store/0npkjmcmq2zjmwfr8n9qiphikhi0h27n-freetype-2.13.2/lib",
    "/nix/store/298lasn37whh7042pbfz0jxp403pai76-libXext-1.3.6/lib",
    "/nix/store/5z1p38q7crvid944wrhmiiglvvald0j4-libX11-1.8.9/lib",
]
existing = os.environ.get("LD_LIBRARY_PATH", "")
os.environ["LD_LIBRARY_PATH"] = ":".join(nix_libs) + (":" + existing if existing else "")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_PLUGIN_PATH"] = os.path.join(
    os.path.dirname(sys.executable), "..", "lib", "python3.11", "site-packages", "PyQt5", "Qt5", "plugins"
)

# Must set env before importing Qt
from PyQt5.QtWidgets import QApplication
from main import MainWindow, api_get, fmt_amount, fmt_rate

def test_utils():
    print("=== Utility Functions ===")
    assert fmt_amount(1000000) == "1,000,000"
    print(f"  fmt_amount(1000000) = {fmt_amount(1000000)} ✓")
    assert fmt_amount(0) == "0"
    print(f"  fmt_amount(0) = {fmt_amount(0)} ✓")
    assert fmt_rate(12.345) == "12.35%"
    print(f"  fmt_rate(12.345) = {fmt_rate(12.345)} ✓")
    assert fmt_rate(-5.1) == "-5.10%"
    print(f"  fmt_rate(-5.1) = {fmt_rate(-5.1)} ✓")
    assert fmt_rate(0) == "0.00%"
    print(f"  fmt_rate(0) = {fmt_rate(0)} ✓")

def test_api_endpoints():
    print("\n=== API Endpoint Tests ===")

    result = api_get("config/current/")
    assert "error" not in result, f"config/current failed: {result}"
    print(f"  GET config/current/ ✓ - mode: {result['mode_display']}, account: {result['account_no']}")

    result = api_get("config/")
    assert isinstance(result, list), f"config list failed: {result}"
    print(f"  GET config/ ✓ - {len(result)} config(s)")

    result = api_get("conditions/")
    assert isinstance(result, list), f"conditions failed: {result}"
    print(f"  GET conditions/ ✓ - {len(result)} condition(s)")

    result = api_get("orders/")
    assert isinstance(result, list), f"orders failed: {result}"
    print(f"  GET orders/ ✓ - {len(result)} order(s)")

    result = api_get("balance/")
    assert isinstance(result, list), f"balance failed: {result}"
    print(f"  GET balance/ ✓ - {len(result)} balance(s)")

    result = api_get("trades/")
    assert isinstance(result, list), f"trades failed: {result}"
    print(f"  GET trades/ ✓ - {len(result)} trade(s)")

def test_ui_init(app):
    print("\n=== UI Initialization Test ===")
    window = MainWindow()

    assert window.tabs.count() == 5
    tab_names = [window.tabs.tabText(i) for i in range(5)]
    print(f"  Tabs: {tab_names} ✓")

    print(f"  Config mode: {window.config_tab.value_labels['trade_mode'].text()} ✓")
    print(f"  Config account: {window.config_tab.value_labels['account_no'].text()} ✓")
    print(f"  Config max buy: {window.config_tab.value_labels['max_buy_amount'].text()} ✓")

    print(f"  Conditions rows: {window.condition_tab.condition_table.rowCount()} ✓")
    print(f"  Orders rows: {window.orders_tab.order_table.rowCount()} ✓")
    print(f"  Balance rows: {window.balance_tab.balance_table.rowCount()} ✓")
    print(f"  Trades rows: {window.trade_history_tab.trade_table.rowCount()} ✓")
    print(f"  Config list rows: {window.config_tab.config_table.rowCount()} ✓")

    print(f"  API connected: {window.api_connected} ✓")
    print(f"  Current mode: {window.current_mode} ✓")

    return window

if __name__ == "__main__":
    test_utils()
    test_api_endpoints()

    app = QApplication(sys.argv)
    window = test_ui_init(app)

    print("\n=== All Tests Passed ===")
