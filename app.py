"""
東証33業種チャート 一括監視モニター - Webサーバー
Flaskで静的ファイルとダッシュボードHTMLを配信する。
"""

import os
import json
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, send_from_directory, jsonify

app = Flask(__name__)

SCREENSHOT_DIR = Path(__file__).parent / "screenshots"


@app.route("/")
def dashboard():
    """ダッシュボードページを配信"""
    # scraper.py から業種定義をインポート
    from scraper import SECTORS
    return render_template("dashboard.html", sectors=SECTORS)


@app.route("/screenshots/<path:filename>")
def serve_screenshot(filename):
    """スクリーンショット画像を配信"""
    return send_from_directory(str(SCREENSHOT_DIR), filename)


@app.route("/api/status")
def api_status():
    """最終更新時刻を返すAPI"""
    latest_mtime = 0
    if SCREENSHOT_DIR.exists():
        for f in SCREENSHOT_DIR.glob("*.png"):
            mtime = f.stat().st_mtime
            if mtime > latest_mtime:
                latest_mtime = mtime

    if latest_mtime > 0:
        last_updated = datetime.fromtimestamp(latest_mtime).strftime("%Y-%m-%d %H:%M:%S")
    else:
        last_updated = "未取得"

    return jsonify({
        "last_updated": last_updated,
        "screenshot_count": len(list(SCREENSHOT_DIR.glob("*.png"))) if SCREENSHOT_DIR.exists() else 0,
    })


@app.route("/api/prices")
def api_prices():
    """値動きデータを返すAPI"""
    price_file = SCREENSHOT_DIR / "price_data.json"
    if price_file.exists():
        with open(price_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    return jsonify({})


if __name__ == "__main__":
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    app.run(host="0.0.0.0", port=5001, debug=False)
