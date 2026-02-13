"""
TOPIX-17業種 ETFチャート監視モニター - Streamlit版
スクレイパーが取得したチャート画像をリアルタイム表示する。
"""

import json
import time
from pathlib import Path
from datetime import datetime
from PIL import Image

import streamlit as st

# ── ページ設定 ────────────────────────────────────────
st.set_page_config(
    page_title="TOPIX-17 ETFチャート監視モニター",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── 定数 ──────────────────────────────────────────────
SECTORS = {
    "1617": "食品",
    "1618": "エネルギー資源",
    "1619": "建設・資材",
    "1620": "素材・化学",
    "1621": "医薬品",
    "1622": "自動車・輸送機",
    "1623": "鉄鋼・非鉄",
    "1624": "機械",
    "1625": "電機・精密",
    "1626": "情報通信・サービスその他",
    "1627": "電力・ガス",
    "1628": "運輸・物流",
    "1629": "商社・卸売",
    "1630": "小売",
    "1631": "銀行",
    "1632": "金融（除く銀行）",
    "1633": "不動産",
}

SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
PRICE_DATA_FILE = SCREENSHOT_DIR / "price_data.json"
COLS_PER_ROW = 3
AUTO_REFRESH_SEC = 300  # 5分


# ── カスタムCSS ───────────────────────────────────────
def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Noto+Sans+JP:wght@300;400;500;600;700&display=swap');

    /* 全体 */
    .stApp {
        background-color: #050507 !important;
        font-family: 'Inter', 'Noto Sans JP', sans-serif;
    }

    /* ヘッダーバー非表示 */
    header[data-testid="stHeader"] {
        background: rgba(5, 5, 7, 0.85) !important;
        backdrop-filter: blur(20px);
    }

    /* カスタムヘッダー */
    .dashboard-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 8px 0 16px;
        border-bottom: 1px solid rgba(255,255,255,0.06);
        margin-bottom: 16px;
    }
    .dashboard-header .logo {
        width: 36px; height: 36px;
        background: linear-gradient(135deg, #6c63ff, #a78bfa);
        border-radius: 10px;
        display: inline-flex; align-items: center; justify-content: center;
        font-size: 16px; font-weight: 700; color: white;
        margin-right: 12px; vertical-align: middle;
        box-shadow: 0 4px 15px rgba(108,99,255,0.15);
    }
    .dashboard-header .title {
        font-size: 18px; font-weight: 600; color: #e8e8ed;
        letter-spacing: -0.02em; vertical-align: middle;
    }
    .dashboard-header .subtitle {
        font-size: 12px; color: #8b8b9e; font-weight: 400;
        margin-left: 48px; margin-top: -2px;
    }
    .dashboard-header .status {
        display: flex; align-items: center; gap: 8px;
        font-size: 12px; color: #8b8b9e;
    }
    .dashboard-header .status-dot {
        width: 7px; height: 7px; border-radius: 50%;
        background: #00e676;
        animation: pulse-dot 2s ease-in-out infinite;
    }
    @keyframes pulse-dot {
        0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(0,230,118,0.4); }
        50% { opacity: 0.7; box-shadow: 0 0 0 6px rgba(0,230,118,0); }
    }

    /* カード */
    .sector-card {
        background: #13131a;
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 12px;
        padding: 10px 12px 8px;
        transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
        margin-bottom: 8px;
    }
    .sector-card:hover {
        background: #1a1a24;
        border-color: rgba(255,255,255,0.12);
        transform: translateY(-2px);
        box-shadow: 0 8px 30px rgba(0,0,0,0.4);
    }
    .sector-card .card-name {
        font-size: 13px; font-weight: 600; color: #e8e8ed;
        display: inline;
    }
    .sector-card .badge-up {
        font-size: 11px; font-weight: 500; color: #22c55e;
        background: rgba(34,197,94,0.1); padding: 1px 6px;
        border-radius: 4px; margin-left: 6px;
    }
    .sector-card .badge-down {
        font-size: 11px; font-weight: 500; color: #ef4444;
        background: rgba(239,68,68,0.1); padding: 1px 6px;
        border-radius: 4px; margin-left: 6px;
    }
    .sector-card .badge-flat {
        font-size: 11px; font-weight: 500; color: #55556a;
        background: rgba(148,163,184,0.1); padding: 1px 6px;
        border-radius: 4px; margin-left: 6px;
    }
    .sector-card img {
        border-radius: 6px;
        margin-top: 6px;
    }

    /* Streamlitウィジェット微調整 */
    div[data-testid="stHorizontalBlock"] {
        gap: 12px;
    }
    div[data-testid="column"] {
        padding: 0 4px;
    }

    /* ラジオボタンをトグル風に */
    div[data-testid="stRadio"] > label { display: none; }
    div[data-testid="stRadio"] > div {
        display: flex; gap: 2px;
        background: #0e0e12; border: 1px solid rgba(255,255,255,0.06);
        border-radius: 8px; padding: 3px; width: fit-content;
    }
    div[data-testid="stRadio"] > div > label {
        padding: 6px 16px !important; border-radius: 6px !important;
        font-size: 12px !important; font-weight: 500 !important;
        color: #8b8b9e !important; cursor: pointer;
        transition: all 0.3s;
    }
    div[data-testid="stRadio"] > div > label[data-checked="true"] {
        background: #6c63ff !important; color: white !important;
        box-shadow: 0 2px 8px rgba(108,99,255,0.15);
    }


    /* サイドバー非表示 */
    section[data-testid="stSidebar"] { display: none; }
    </style>
    """, unsafe_allow_html=True)


# ── データ読み込み ────────────────────────────────────
@st.cache_data(ttl=30)
def load_price_data() -> dict:
    if PRICE_DATA_FILE.exists():
        with open(PRICE_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_last_update() -> str:
    """最新のスクリーンショットの更新時刻を取得"""
    latest = 0
    if SCREENSHOT_DIR.exists():
        for f in SCREENSHOT_DIR.glob("*.png"):
            mtime = f.stat().st_mtime
            if mtime > latest:
                latest = mtime
    if latest > 0:
        return datetime.fromtimestamp(latest).strftime("%H:%M:%S")
    return "--:--:--"


# ── メイン ────────────────────────────────────────────
def main():
    inject_css()

    # ── ヘッダー ──
    # レイアウト調整: 中央を広げる [3, 4, 3]
    h_left, h_center, h_right = st.columns([3, 4, 3])
    with h_left:
        st.markdown("""
        <div style="display:flex; align-items:center; gap:12px;">
            <div class="dashboard-header">
                <div style="display:flex; align-items:center;">
                    <span class="logo">17</span>
                    <div>
                        <div class="title">TOPIX-17業種 ETFチャート監視モニター</div>
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with h_center:
        # チャートモードと並び順を横並びにする
        c_mode, c_sort = st.columns(2)
        with c_mode:
            mode = st.radio(
                "チャートモード",
                ["5分足", "日足"],
                horizontal=True,
                key="chart_mode",
            )
        with c_sort:
            sort_order = st.radio(
                "並び順",
                ["コード順", "上昇率順", "下落率順"],
                horizontal=True,
                key="sort_order",
            )

    with h_right:
        last_update = get_last_update()
        st.markdown(f"""
        <div style="display:flex; align-items:center; justify-content:flex-end; gap:16px; padding-top:8px;">
            <div class="dashboard-header">
                <div class="status">
                    <div class="status-dot"></div>
                    <span>監視中</span>
                </div>
            </div>
            <div style="font-size:12px; color:#55556a;">
                最終更新: {last_update}
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── チャート表示用suffix ──
    suffix = "_intraday" if mode == "5分足" else "_daily"

    # ── 値動きデータ ──
    price_data = load_price_data()

    # ── グリッド表示 ──
    sector_list = list(SECTORS.items())

    # 並び替えロジック
    if sort_order != "コード順":
        def get_change_percent(item):
            qcode = item[0]
            info = price_data.get(qcode, {})
            pct_str = info.get("changePercent", "0.00%")
            try:
                # "+0.68%" -> 0.68, "-5.92%" -> -5.92
                return float(pct_str.replace("%", "").replace("+", ""))
            except ValueError:
                return -999.0

        reverse = True if sort_order == "上昇率順" else False
        sector_list.sort(key=get_change_percent, reverse=reverse)

    for row_start in range(0, len(sector_list), COLS_PER_ROW):
        row_sectors = sector_list[row_start:row_start + COLS_PER_ROW]
        cols = st.columns(COLS_PER_ROW)

        for col_idx, (qcode, name) in enumerate(row_sectors):
            with cols[col_idx]:
                # 値動きバッジ
                info = price_data.get(qcode, {})
                pct = info.get("changePercent", "")
                direction = info.get("direction", "")

                if direction == "up":
                    badge_class = "badge-up"
                elif direction == "down":
                    badge_class = "badge-down"
                else:
                    badge_class = "badge-flat"

                badge_html = f'<span class="{badge_class}">{pct}</span>' if pct else ""

                st.markdown(
                    f'<div class="sector-card">'
                    f'<span class="card-name">{name}</span>{badge_html}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # チャート画像
                img_path = SCREENSHOT_DIR / f"{qcode}{suffix}.png"
                
                if img_path.exists():
                    try:
                        image = Image.open(img_path)
                        st.image(image)
                    except Exception as e:
                        st.error(f"画像読み込みエラー: {e}")
                else:
                    # デバッグ表示
                    st.warning(f"画像未検出: {img_path.name}")

    # ── デバッグ用情報を下部に表示 ──
    with st.expander("デバッグ情報 (管理者用)"):
        st.write(f"SCREENSHOT_DIR: {SCREENSHOT_DIR.absolute()}")
        if SCREENSHOT_DIR.exists():
            files = [f.name for f in SCREENSHOT_DIR.glob("*") if f.name.endswith(".png")]
            st.write(f"検出された画像ファイル ({len(files)}個):")
            st.write(files)
        else:
            st.error("SCREENSHOT_DIRが存在しません")

    # ── 自動更新 ──
    # フッターに次回更新までのカウントダウン的な情報
    st.markdown(
        f"<div style='text-align:center; color:#55556a; font-size:11px; "
        f"padding:20px 0 40px;'>自動更新: {AUTO_REFRESH_SEC}秒間隔 "
        f"| スクレイパーが別途実行中であることを確認してください</div>",
        unsafe_allow_html=True,
    )

    # 5分後に自動リフレッシュ
    time.sleep(AUTO_REFRESH_SEC)
    st.rerun()


if __name__ == "__main__":
    main()
