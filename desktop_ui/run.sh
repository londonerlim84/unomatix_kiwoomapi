#!/bin/bash
# 키움증권 트레이딩 UI 실행 스크립트
cd "$(dirname "$0")"

# Nix 환경에서 필요한 라이브러리 경로 설정
export LD_LIBRARY_PATH="/nix/store/6lzcb4zv3lysq4yjhmgi1dkc6fqrgphy-libglvnd-1.7.0/lib:/nix/store/3c275grvmby79gqgnjych830sld6bziw-glib-2.80.2/lib:$LD_LIBRARY_PATH"

# venv의 Python 사용
PYTHON="../.venv/bin/python"

if [ ! -f "$PYTHON" ]; then
    echo "Error: Python venv not found. Run: python -m venv .venv && .venv/bin/pip install PyQt5 requests"
    exit 1
fi

exec "$PYTHON" main.py "$@"
