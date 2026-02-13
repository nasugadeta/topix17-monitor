"""
TOPIX-17業種 ETFチャート スクレイピングエンジン
JPX公式サイトからTOPIX-17業種ETFのチャートを
Playwrightでスクリーンショット撮影し、ローカルに保存する。
"""

import asyncio
import random
import json
import os
import sys
import time
import logging
import datetime
import jpholiday
from pathlib import Path
from playwright.async_api import async_playwright

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── TOPIX-17業種 ETFコード → 業種名 マッピング ──────────────
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

BASE_URL = "https://quote.jpx.co.jp/jpxhp/main/index.aspx?f=stock_detail&disptype=chart&qcode={qcode}"

# プロジェクトルートの screenshots/ に保存
SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
PRICE_DATA_FILE = Path(__file__).parent / "screenshots" / "price_data.json"

# 各アクセス間のスリープ (秒) ─ ランダム化してBOT検出を回避
ACCESS_DELAY_MIN = 3.0
ACCESS_DELAY_MAX = 6.0

# 定期実行間隔 (秒) ─ 余裕を持たせてレート制限回避
LOOP_INTERVAL = 300  # 5分


async def extract_price_data(page) -> dict:
    """ページから現在値・前日比データを抽出する"""
    try:
        data = await page.evaluate("""
            (() => {
                const result = { price: '', change: '', changePercent: '', direction: '' };
                const headers = Array.from(document.querySelectorAll('th.tbl-s1-th'));
                
                for (const th of headers) {
                    const text = th.innerText.trim();
                    const colIndex = Array.from(th.parentElement.children).indexOf(th);
                    const rows = Array.from(th.closest('table').querySelectorAll('tr'));
                    const valueRow = rows[rows.indexOf(th.parentElement) + 1];
                    if (!valueRow) continue;
                    const td = valueRow.children[colIndex];
                    if (!td) continue;
                    
                    if (text.includes('現在値')) {
                        const spans = td.querySelectorAll('span');
                        if (spans.length > 0) result.price = spans[0].textContent.trim();
                    }
                    if (text.includes('前日比')) {
                        const spans = td.querySelectorAll('span');
                        if (spans.length >= 2) {
                            result.change = spans[0].textContent.trim();
                            result.changePercent = spans[1].textContent.trim();
                        } else if (spans.length === 1) {
                            result.change = spans[0].textContent.trim();
                        }
                        const plusSpan = td.querySelector('.txt-plus');
                        const minusSpan = td.querySelector('.txt-minus');
                        if (plusSpan) result.direction = 'up';
                        else if (minusSpan) result.direction = 'down';
                        else result.direction = 'flat';
                    }
                }
                return result;
            })()
        """)
        return data
    except Exception as e:
        logger.warning(f"値動きデータ取得失敗: {e}")
        return {"price": "", "change": "", "changePercent": "", "direction": ""}


async def hide_non_chart_elements(page):
    """CSSで不要な要素を非表示にしてチャートだけを残す"""
    await page.evaluate("""
        // ヘッダー・ナビゲーション全般を非表示
        document.querySelectorAll('header, .header, nav, .nav, .gnav').forEach(el => el.style.display = 'none');
        // 株価情報テーブルを非表示
        document.querySelectorAll('.stock-detail, .tbl-s1, table').forEach(el => el.style.display = 'none');
        // メインタブ（株価情報・チャート・決算...）を非表示
        document.querySelectorAll('.stock-tabMenu, .tabMenu, ul.tab, [class*="tab-menu"], [class*="tabmenu"]').forEach(el => el.style.display = 'none');
        // 日中足・日足・週足・月足の切り替えタブを非表示
        document.querySelectorAll('.chart-tabMenu, [class*="chart-tab"], [class*="chartTab"], ul.chart').forEach(el => el.style.display = 'none');
        // 銘柄名のエリアを非表示
        document.querySelectorAll('.stock-name, .stock-info, h1, h2').forEach(el => el.style.display = 'none');
        // ボタン類を非表示
        document.querySelectorAll('.btn, button, [class*="portfolio"]').forEach(el => el.style.display = 'none');
        // 下部の免責事項を非表示
        document.querySelectorAll('.disclaimer, [class*="disclaimer"], [class*="caution"], footer, .footer').forEach(el => el.style.display = 'none');
        // ページトップボタンを非表示
        document.querySelectorAll('[class*="pagetop"], [class*="scroll-top"], [id*="pagetop"], .scroll-top').forEach(el => el.style.display = 'none');
        // 検索バーを非表示
        document.querySelectorAll('[class*="search"], .search-box, .searchBox').forEach(el => el.style.display = 'none');
        
        // テキスト内容で要素を非表示にする
        document.querySelectorAll('div, section, aside, p').forEach(el => {
            const text = el.textContent?.trim() || '';
            if (text.startsWith('免責事項') || text.startsWith('四本値、売買高') || text.startsWith('株式会社日本取引所')) {
                el.style.display = 'none';
            }
        });
        
        document.body.style.paddingTop = '0';
        document.body.style.marginTop = '0';
    """)


async def take_chart_screenshot(page, save_path: Path):
    """チャートエリアのスクリーンショットを撮影する"""
    # チャートのimg要素またはcanvasを探してスクリーンショット
    chart_element = None
    for selector in ['img[src*="chart"]', 'canvas', '.chart-area', '.chartArea', '#chartArea', '.chart img', '.chart-image']:
        el = page.locator(selector).first
        if await el.count() > 0:
            chart_element = el
            break

    if chart_element and await chart_element.is_visible():
        await chart_element.screenshot(path=str(save_path))
    else:
        # フォールバック: スクロールしてビューポートをスクリーンショット
        await page.evaluate("window.scrollTo(0, 580)")
        await asyncio.sleep(0.3)
        await page.screenshot(path=str(save_path), full_page=False)


async def capture_chart(page, qcode: str, sector_name: str) -> dict | None:
    """1業種のチャートを日足・日中足の2種類スクリーンショット撮影し、値動きデータを返す"""
    url = BASE_URL.format(qcode=qcode)
    intraday_path = SCREENSHOT_DIR / f"{qcode}_intraday.png"
    daily_path = SCREENSHOT_DIR / f"{qcode}_daily.png"

    try:
        logger.info(f"[{qcode}] {sector_name} - アクセス中...")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=30000)

        # 値動きデータを抽出
        price_data = await extract_price_data(page)

        # ── 1) 日足チャートをキャプチャ (デフォルト表示) ──
        await hide_non_chart_elements(page)
        await asyncio.sleep(random.uniform(0.5, 1.5))  # 人間らしい遅延
        await take_chart_screenshot(page, daily_path)

        # ── 2) 日中足チャートをキャプチャ ──
        try:
            intraday_tab = page.locator("text=日中足").first
            await intraday_tab.click(timeout=5000)
            await page.wait_for_load_state("networkidle", timeout=15000)
            await asyncio.sleep(2)
        except Exception:
            await asyncio.sleep(1.5)

        await hide_non_chart_elements(page)
        await asyncio.sleep(random.uniform(0.5, 1.5))  # 人間らしい遅延
        await take_chart_screenshot(page, intraday_path)

        logger.info(f"[{qcode}] {sector_name} - 保存完了 | {price_data.get('change', '')} {price_data.get('changePercent', '')}")
        return price_data

    except Exception as e:
        logger.error(f"[{qcode}] {sector_name} - エラー: {e}")
        return None


async def create_browser_context(p):
    """headless検出を回避したブラウザコンテキストを作成する"""
    browser = await p.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ],
    )
    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        locale="ja-JP",
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        extra_http_headers={
            "Referer": "https://quote.jpx.co.jp/jpxhp/main/index.aspx",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        },
    )
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => false });
    """)
    return browser, context



def save_price_data(all_price_data: dict):
    """全業種の値動きデータをJSONファイルに保存 (既存データを読み込んで更新)"""
    PRICE_DATA_FILE.parent.mkdir(exist_ok=True)
    
    current_data = {}
    if PRICE_DATA_FILE.exists():
        try:
            with open(PRICE_DATA_FILE, "r", encoding="utf-8") as f:
                current_data = json.load(f)
        except Exception as e:
            logger.warning(f"既存データの読み込み失敗: {e}")

    # 新しいデータで更新
    current_data.update(all_price_data)

    with open(PRICE_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(current_data, f, ensure_ascii=False, indent=2)


async def scrape_all_sectors():
    """全17業種のチャートをスクレイピングする (1サイクル)"""
    SCREENSHOT_DIR.mkdir(exist_ok=True)

    async with async_playwright() as p:
        browser, context = await create_browser_context(p)
        page = await context.new_page()

        success_count = 0
        total = len(SECTORS)
        all_price_data = {}

        for i, (qcode, name) in enumerate(SECTORS.items()):
            price_data = await capture_chart(page, qcode, name)
            if price_data is not None:
                success_count += 1
                all_price_data[qcode] = price_data

            if i < total - 1:
                delay = random.uniform(ACCESS_DELAY_MIN, ACCESS_DELAY_MAX)
                await asyncio.sleep(delay)

        await browser.close()

    save_price_data(all_price_data)
    logger.info(f"スクレイピング完了: {success_count}/{total} 業種成功")
    return success_count


async def wait_until_market_open():
    """現在時刻が市場オープン中（平日 9:00-11:30, 12:30-15:30）か確認し、
    オープンしていなければ次の開始時刻まで待機する。
    """
    while True:
        now = datetime.datetime.now()
        
        # 週末チェック
        if now.weekday() >= 5:
            # 次の月曜9:00まで待機
            days_ahead = 7 - now.weekday()
            next_start = (now + datetime.timedelta(days=days_ahead)).replace(hour=9, minute=0, second=0, microsecond=0)
            wait_sec = (next_start - now).total_seconds()
            logger.info(f"現在は週末です。次の開始時刻({next_start})まで待機します... ({wait_sec/3600:.1f}時間)")
            await asyncio.sleep(wait_sec)
            continue

        # 祝日チェック
        if jpholiday.is_holiday(now.date()):
            # 明日の9:00まで待機（ループすれば週末チェックも入る）
            next_start = (now + datetime.timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
            wait_sec = (next_start - now).total_seconds()
            logger.info(f"現在は祝日です。次の開始時刻({next_start})まで待機します... ({wait_sec/3600:.1f}時間)")
            await asyncio.sleep(wait_sec)
            continue
            
        t = now.time()
        start_am = datetime.time(9, 0)
        end_am = datetime.time(11, 30)
        start_pm = datetime.time(12, 30)
        end_pm = datetime.time(15, 30)
        
        # 営業時間内チェック
        is_am = start_am <= t <= end_am
        is_pm = start_pm <= t <= end_pm
        
        if is_am or is_pm:
            return  # 実行OK

        # 待機時間を計算
        wait_sec = 60 # デフォルト
        next_msg = ""
        
        if t < start_am:
            # 9:00まで待機
            target = now.replace(hour=9, minute=0, second=0, microsecond=0)
            wait_sec = (target - now).total_seconds()
            next_msg = f"前場開始({target.time()})まで待機"
        elif end_am < t < start_pm:
            # 12:30まで待機
            target = now.replace(hour=12, minute=30, second=0, microsecond=0)
            wait_sec = (target - now).total_seconds()
            next_msg = f"後場開始({target.time()})まで待機"
        elif t > end_pm:
            # 明日の9:00まで待機
            target = (now + datetime.timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
            wait_sec = (target - now).total_seconds()
            next_msg = f"翌日の開始({target})まで待機"
        
        if wait_sec > 0:
            logger.info(f"現在は営業時間外です。{next_msg}します... ({wait_sec:.0f}秒)")
            await asyncio.sleep(wait_sec)
        else:
            await asyncio.sleep(60) # フォールバック


async def run_loop():
    """5分間隔で定期実行するメインループ"""
    logger.info("=== TOPIX-17業種 ETFチャート スクレイパー 起動 ===")
    while True:
        await wait_until_market_open()  # 営業時間チェック＆待機
        start = time.time()
        await scrape_all_sectors()
        elapsed = time.time() - start
        logger.info(f"1サイクル完了 ({elapsed:.1f}秒)")

        wait_time = max(0, LOOP_INTERVAL - elapsed)
        if wait_time > 0:
            logger.info(f"次の更新まで {wait_time:.0f}秒 待機...")
            await asyncio.sleep(wait_time)


async def test_single():
    """テスト: 1業種 (食品) のみ撮影"""
    SCREENSHOT_DIR.mkdir(exist_ok=True)

    async with async_playwright() as p:
        browser, context = await create_browser_context(p)
        page = await context.new_page()
        price_data = await capture_chart(page, "1617", "食品")
        if price_data:
            save_price_data({"1617": price_data})
            logger.info(f"テスト結果: {json.dumps(price_data, ensure_ascii=False)}")
        await browser.close()


if __name__ == "__main__":
    if "--test" in sys.argv:
        asyncio.run(test_single())
    else:
        asyncio.run(run_loop())
