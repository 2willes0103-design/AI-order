import json
import re
import os
import io
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import google.generativeai as genai
from PIL import Image

app = Flask(__name__, static_folder='.')
CORS(app)

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.0-flash")

# Serve the frontend at the root URL
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/proxy', methods=['GET', 'POST'])
def gas_proxy():
    import requests
    gas_url = "https://script.google.com/macros/s/AKfycbyqafkBR1-p-CQN12V2xaUbiumyaATSt80l7AjhmFdHUck-n-8rNprIzCKiMO4GNqAL/exec"

    try:
        if request.method == 'GET':
            params = request.args.to_dict()
            print(f"--- GET Proxy: {params.get('action')}")
            resp = requests.get(gas_url, params=params, allow_redirects=True, timeout=30)
            print(f"--- GET Proxy Result: Status {resp.status_code}")
            try:
                return jsonify(resp.json())
            except:
                return resp.text, resp.status_code
        else:
            headers = {'Content-Type': 'application/json'}
            post_data = request.get_data()
            print(f"--- POST Proxy: Sending {len(post_data)} bytes to GAS")
            resp = requests.post(gas_url, data=post_data, headers=headers, allow_redirects=True, timeout=30)
            print(f"--- POST Proxy Result: Status {resp.status_code}")
            print(f"--- Raw Response: {resp.text[:500]}")
            try:
                result = resp.json()
                return jsonify(result)
            except Exception:
                print(f"--- GAS 回傳非 JSON: {resp.text[:200]}")
                return jsonify({"error": f"GAS 回傳非 JSON (HTTP {resp.status_code})", "raw": resp.text[:300]}), 502
    except requests.exceptions.Timeout:
        print("--- Proxy Timeout: GAS 沒有在 30 秒內回應")
        return jsonify({"error": "GAS 連線逾時，請稍後再試"}), 504
    except requests.exceptions.SSLError as e:
        print(f"--- Proxy SSL Error: {str(e)}")
        return jsonify({"error": f"SSL 憑證錯誤: {str(e)}"}), 502
    except Exception as e:
        print(f"--- Proxy Critical Error: {type(e).__name__}: {str(e)}")
        return jsonify({"error": f"{type(e).__name__}: {str(e)}"}), 500

@app.route('/recognize', methods=['POST'])
def recognize_menu():
    if 'image' not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file = request.files['image']
    image_bytes = file.read()

    prompt = """
    請分析這張菜單圖片，並根據菜單上的標題提取所有餐點項目。
    回傳 JSON 格式為一個陣列，每個物件包含：
    - "name": 餐點名稱（保持繁體中文，區分大小份）。
    - "price": 價格（數字）。
    - "category": 該餐點屬於的分類（例如：飯類、湯類、主菜、小菜、飲料等）。
    只回傳 JSON 陣列。
    """

    try:
        image = Image.open(io.BytesIO(image_bytes))
        response = model.generate_content([prompt, image])
        text = response.text
        print("--- AI Raw Response ---")
        print(text)

        json_match = re.search(r'\[.*\]', text, re.DOTALL)
        if json_match:
            text = json_match.group(0)

        items = json.loads(text.strip())
        return jsonify({"items": items})
    except Exception as e:
        print(f"Error during recognition: {str(e)}")
        return jsonify({"error": f"辨識失敗: {str(e)}"}), 500

if __name__ == '__main__':
    print("--- 點餐系統已啟動 ---")
    print("網址：http://localhost:5000")
    app.run(debug=True, port=5000)
