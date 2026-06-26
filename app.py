from flask import Flask, request, send_file, render_template
import pandas as pd
import os
import urllib.parse
from playwright.sync_api import sync_playwright

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ==========================================
# 核心：全新强力版 reurl.cc 自动化抓取函数
# ==========================================
def create_short_link(long_url, medium, campaign):
    with sync_playwright() as p:
        # 1. 启动并进行高级防爬特征伪装
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN"
        )
        page = context.new_page()
        short_url = None

        try:
            # 2. 在代码底层直接把 UTM 参数拼接到长链中
            parsed_url = urllib.parse.urlparse(str(long_url).strip())
            query = urllib.parse.parse_qs(parsed_url.query)
            
            # 固定设置 utm_source 为 KOL
            query['utm_source'] = ['KOL']
            if medium: query['utm_medium'] = [str(medium)]
            if campaign: query['utm_campaign'] = [str(campaign)]
            
            # 重新组装成带有完整 UTM 的长链接
            new_query = urllib.parse.urlencode(query, doseq=True)
            final_long_url = urllib.parse.urlunparse((
                parsed_url.scheme, parsed_url.netloc, parsed_url.path,
                parsed_url.params, new_query, parsed_url.fragment
            ))

            print(f"[正在处理 reurl] 拼接后的长链: {final_long_url}")

            # 3. 访问 reurl.cc 官方中文页（等待网络空闲）
            page.goto("https://reurl.cc/main/cn", wait_until="networkidle", timeout=30000)

            # 4. 精准定位并填入完整的长链接
            page.locator("#shortenBox").fill(final_long_url)
            page.wait_for_timeout(500)

            # 5. 点击“缩短网址”按钮
            page.locator("button#shortenBtn, button.btn-success").first.click()

            # 6. 等待生成的短链接输入框或者跳转链接出现（容错时间延长至 15 秒）
            page.wait_for_selector("input#shortenResult, a[href^='https://reurl.cc/']", timeout=15000)
            
            # 7. 提取生成的 reurl 短链结果
            result_element = page.locator("input#shortenResult")
            if result_element.count() > 0:
                short_url = result_element.input_value()
            else:
                short_url = page.locator("a[href^='https://reurl.cc/']").first.get_attribute("href")

            print(f"[reurl 生成成功] -> {short_url}")

        except Exception as e:
            print("[reurl 生成发生异常，卡在某步骤]:", e)
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
    if "file" not in request.files:
        return "没有上传文件", 400
        
    file = request.files["file"]
    if file.filename == "":
        return "未选择文件", 400

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

        print(f"--- 正在处理第 {i} 行 ---")
        short = create_short_link(url, medium, campaign)
        results.append(short)

    df["short_url"] = results

    output_path = os.path.join(OUTPUT_FOLDER, "output.xlsx")
    df.to_excel(output_path, index=False)

    return send_file(output_path, as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
