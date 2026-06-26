from flask import Flask, request, send_file, render_template
import pandas as pd
import os
from playwright.sync_api import sync_playwright

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# =========================
# 核心：生成短链（Playwright）
# =========================
def create_short_link(long_url, medium, campaign):

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto("https://reurl.cc/main/cn", wait_until="domcontentloaded")

            # 输入长链接
            page.locator("#shortenBox").fill(str(long_url))

            # 打开选项
            page.locator("text=选项").click()
            page.wait_for_timeout(500)

            # 填UTM
            page.locator("input[placeholder='utm_source']").fill("KOL")
            page.locator("input[placeholder='utm_medium']").fill(str(medium))
            page.locator("input[placeholder='utm_campaign']").fill(str(campaign))

            # 点击生成
            page.locator("button.btn.btn-success").click()

            # 等待结果
            page.wait_for_selector("a[href^='https://reurl.cc/']", timeout=20000)

            short_url = page.locator("a[href^='https://reurl.cc/']").first.get_attribute("href")

        except Exception as e:
            print("错误：", e)
            short_url = None

        browser.close()
        return short_url


# =========================
# 首页
# =========================
@app.route("/")
def index():
    return render_template("index.html")


# =========================
# 上传Excel处理
# =========================
@app.route("/upload", methods=["POST"])
def upload_file():

    file = request.files["file"]

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    df = pd.read_excel(file_path)
    results = []

    for i, row in df.iterrows():

        url = row.get("长标记链")

        if not isinstance(url, str) or url.strip() == "":
            results.append(None)
            continue

        medium = row.get("utm_medium", "")
        campaign = row.get("utm_campaign", "")

        print(f"处理第{i}行")

        try:
            short = create_short_link(url, medium, campaign)
        except Exception as e:
            print("生成失败：", e)
            short = None

        results.append(short)

    df["short_url"] = results

    output_path = os.path.join(OUTPUT_FOLDER, "output.xlsx")
    df.to_excel(output_path, index=False)

    return send_file(output_path, as_attachment=True)


# =========================
# 启动服务（Render专用）
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)