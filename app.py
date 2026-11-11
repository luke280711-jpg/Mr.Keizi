import asyncio
import os
import random
import subprocess
import sys

# Streamlit Cloud環境でPlaywrightパッケージとChromiumをセットアップ
try:
    from playwright.async_api import async_playwright
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "playwright"])
    from playwright.async_api import async_playwright

subprocess.run(
    [sys.executable, "-m", "playwright", "install", "chromium"], check=False
)

import streamlit as st

st.set_page_config(page_title="Microsoft Forms 自動送信ツール", layout="centered")
st.title("⚡ Microsoft Forms 自動送信ツール")

# --- 画面からの入力設定 ---
url = st.text_input(
    "対象フォームURL",
    value="https://forms.cloud.microsoft/Pages/ResponsePage.aspx?id=c_iphAJVMkilz_4Fe1JjauzBRHOv9CxKrHcP3AjIH3pUM0RBMjhGMlVIMks5OTU3MFlXS05ZU1E1Ni4u",
)
target_choice = st.text_input("投票したい選択肢名", value="Mr.1 山城 けいじ")

col1, col2 = st.columns(2)
with col1:
    total_count = st.number_input(
        "合計送信回数", min_value=1, max_value=1000, value=10
    )
with col2:
    # 並列数の最大値を5に拡大
    concurrency = st.number_input(
        "並列ブラウザ数 (ワーカー数)", min_value=1, max_value=5, value=3
    )


async def worker(
    worker_id, target_url, target_text, assigned_count, log_area
):
    """1つのブラウザインスタンスが担当分の送信を行うワーカー関数"""
    # 同時アクセスの負荷を分散するため、わずかな時差（1秒ずつ）で起動
    await asyncio.sleep((worker_id - 1) * 1.0)

    async with async_playwright() as p:
        log_area.info(f"🌐 [ワーカー {worker_id}] ブラウザを起動中...")

        try:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-font-subsetting",
                    "--font-render-hinting=none",
                ],
            )
        except Exception as e:
            log_area.error(f"❌ [ワーカー {worker_id}] ブラウザ起動失敗: {e}")
            return

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # 画像、フォント、CSS、メディアを全て遮断して超高速化
        await page.route(
            "**/*.{png,jpg,jpeg,gif,svg,webp,css,woff,woff2,ttf,otf,mp4,mp3}",
            lambda route: route.abort(),
        )

        try:
            for i in range(assigned_count):
                log_area.info(f"🔄 [ワーカー {worker_id}] 送信中 ({i+1}/{assigned_count})...")
                
                # 最速でページを読み込み
                await page.goto(target_url, wait_until="commit", timeout=40000)

                # 1. 選択肢をクリック
                choice_locator = page.locator(f"text={target_text}").first
                await choice_locator.wait_for(state="visible", timeout=15000)
                await choice_locator.click()

                # 2. 送信ボタンをクリック
                submit_button = page.locator(
                    "button:has-text('送信'), [data-automation-id='submitButton']"
                ).first
                await submit_button.click()

                # 短めの完了待機（1秒）
                await page.wait_for_timeout(1000)

                log_area.success(
                    f"🟢 [ワーカー {worker_id}] 送信成功！ ({i+1}/{assigned_count})"
                )

                # 高速化のため合間のウェイトを0.5〜1秒に縮小
                if i < assigned_count - 1:
                    await asyncio.sleep(random.uniform(0.5, 1.0))

        except Exception as e:
            log_area.error(f"❌ [ワーカー {worker_id}] エラー: {e}")
        finally:
            await browser.close()


async def run_all():
    log_area = st.container()
    st.info("🚀 送信処理を開始します...")

    base_count = total_count // concurrency
    remainder = total_count % concurrency

    tasks = []
    for i in range(int(concurrency)):
        assigned = int(base_count + (1 if i < remainder else 0))
        if assigned > 0:
            tasks.append(
                worker(i + 1, url, target_choice, assigned, log_area)
            )

    await asyncio.gather(*tasks)
    st.success("🎉 すべての送信処理が完了しました！")
    st.balloons()


# --- 実行ボタン ---
if st.button("自動送信を開始", type="primary"):
    if not url:
        st.error("URLを入力してください。")
    else:
        asyncio.run(run_all())
