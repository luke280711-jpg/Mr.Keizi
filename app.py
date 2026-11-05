import asyncio
import os
import subprocess
import sys

# Streamlit Cloud環境でPlaywrightパッケージとChromiumをインストール
try:
    from playwright.async_api import async_playwright
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "playwright"])
    from playwright.async_api import async_playwright

# ブラウザバイナリと依存関係のインストール
subprocess.run(
    [sys.executable, "-m", "playwright", "install", "chromium"], check=False
)
subprocess.run(
    [sys.executable, "-m", "playwright", "install-deps"], check=False
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
    concurrency = st.number_input(
        "並列ブラウザ数 (ワーカー数)", min_value=1, max_value=5, value=1
    )


async def worker(
    worker_id, target_url, target_text, assigned_count, log_area
):
    """1つのブラウザインスタンスが担当分の送信を行うワーカー関数"""
    async with async_playwright() as p:
        log_area.info(f"🌐 [ワーカー {worker_id}] ブラウザを起動中...")

        # Linux環境でシステムにインストールされているChromiumのパスを探索
        chromium_path = None
        for path in ["/usr/bin/chromium", "/usr/bin/chromium-browser"]:
            if os.path.exists(path):
                chromium_path = path
                break

        # 起動引数を指定してブラウザを起動
        launch_kwargs = {
            "headless": True,
            "args": [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        }
        if chromium_path:
            launch_kwargs["executable_path"] = chromium_path

        try:
            browser = await p.chromium.launch(**launch_kwargs)
        except Exception as e:
            log_area.error(f"❌ [ワーカー {worker_id}] ブラウザ起動失敗: {e}")
            return

        context = await browser.new_context()
        page = await context.new_page()

        # 画像やCSSなどを遮断して高速化
        await page.route(
            "**/*.{png,jpg,jpeg,gif,svg,webp,css,font,woff,woff2}",
            lambda route: route.abort(),
        )

        try:
            for i in range(assigned_count):
                log_area.info(
                    f"🔄 [ワーカー {worker_id}] ページ読込中 ({i+1}/{assigned_count})"
                )
                await page.goto(target_url, wait_until="domcontentloaded")

                # 1. 選択肢をクリック
                choice_locator = page.locator(
                    f"xpath=//span[contains(text(), '{target_text}')] | //div[contains(text(), '{target_text}')]"
                )
                await choice_locator.click()

                # 2. 送信ボタンをクリック
                submit_locator = page.locator(
                    "xpath=//button[.//span[contains(text(), '送信')] or contains(text(), '送信')]"
                )
                await submit_locator.click()

                # 3. 「別の回答を送信」をクリック
                another_locator = page.locator(
                    "xpath=//a[contains(text(), '別の回答を送信')] | //div[contains(text(), '別の回答を送信')] | //span[contains(text(), '別の回答を送信')]"
                )
                await another_locator.click(timeout=5000)

                log_area.success(
                    f"🟢 [ワーカー {worker_id}] 送信成功！ ({i+1}/{assigned_count})"
                )

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
