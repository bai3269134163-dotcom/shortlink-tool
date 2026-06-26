from flask import Flask, request, send_file, render_template
import pandas as pd
import os
import requests
import urllib.parse

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ==========================================
# 核心替换：使用超稳定的 TinyURL API 替代爬虫
# ==========================================
def create_short_link(long_url, medium, campaign):
    try:
        # 1. 自动拼接 UTM 参数
        parsed_url = urllib.parse.urlparse(str(long_url).strip())
        query = urllib.parse.parse_qs(parsed_url.query)
        
        # 填入你的 UTM 逻辑
        query['utm_source'] = 'KOL'
        if medium: query['utm_medium'] = str(medium)
        if campaign: query['utm_campaign'] = str(campaign)
        
        # 重新组装完整的长链接
        new_query = urllib.parse.urlencode(query, doseq=True)
        final_long_url = urllib.parse.urlunparse((
            parsed_url.scheme, parsed_url.netloc, parsed_url.path,
            parsed_url.params, new_query, parsed_url.fragment
        ))
        
        # 2. 调用 TinyURL 开放接口生成短链（无需 API Key，免费公开）
        api_url = f"http://tinyurl.com/api-create.php?url={urllib.parse.quote(final_long_url)}"
        
        print(f"[正在请求短链] 最终长链: {final_long_url}")
        response = requests.get(api_url, timeout=10)
        
        if response.status_code == 200 and response.text.strip():
            short_url = response.text.strip()
            print(f"[生成成功] -> {short_url}")
            return short_url
        else:
            print(f"[接口返回错误] 状态码: {response.status_code}")
            return None
            
    except Exception as e:
        print("[生成发生异常]:", e)
        return None

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
