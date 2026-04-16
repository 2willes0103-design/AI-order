import os
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import google.generativeai as genai
from PIL import Image
import io

app = Flask(__name__, static_folder='.')
CORS(app)

# --- Configuration ---
# Replace with your actual Gemini API Key
GEMINI_API_KEY = "AIzaSyDIPMigdLI-0WWDd4-7sOkYT2nM2VRllfU"
# Configure Gemini with explicit REST transport to bypass gRPC issues
genai.configure(api_key=GEMINI_API_KEY, transport='rest')

# List available models for debugging and initialize
try:
    print("--- 正在檢查可用模型 ---")
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    print(f"您的金鑰可使用的模型: {available_models}")
    
    # Use the most common one if found, otherwise default to flash
    target_model = 'models/gemini-1.5-flash' if 'models/gemini-1.5-flash' in available_models else available_models[0]
    model = genai.GenerativeModel(target_model)
    print(f"已選擇使用模型: {target_model}")
except Exception as e:
    print(f"檢查模型失敗: {str(e)}")
    model = genai.GenerativeModel('gemini-1.5-flash')

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
            resp = requests.get(gas_url, params=params, allow_redirects=True)
            print(f"--- GET Proxy: {params.get('action')} -> Status {resp.status_code}")
            try:
                # Attempt to return the JSON directly
                return jsonify(resp.json())
            except:
                # If GAS returns something else (like an error page), forward it as text
                return resp.text, resp.status_code
        else:
            # POST: 使用 Session 處理可能的轉發並保持 Method
            headers = {'Content-Type': 'application/json'}
            post_data = request.get_data()
            
            print(f"--- POST Proxy: Sending {len(post_data)} bytes to GAS")
            
            # GAS 流程：POST 觸發 doPost → 302 redirect → GET 取回結果
            # allow_redirects=True 會在 302 時自動轉成 GET，這是正確行為
            resp = requests.post(gas_url, data=post_data, headers=headers, allow_redirects=True)

            print(f"--- POST Proxy Result: Status {resp.status_code}")
            print(f"--- Raw Response from Google: {resp.text[:500]}")

            # 嘗試回傳 JSON，失敗時包成 JSON 錯誤回傳（避免前端收到 HTML）
            try:
                result = resp.json()
                return jsonify(result)
            except Exception:
                print(f"--- GAS 回傳非 JSON，內容: {resp.text[:200]}")
                return jsonify({"error": f"GAS 回傳非 JSON 內容 (HTTP {resp.status_code})，可能是權限或部署問題", "raw": resp.text[:300]}), 502
    except Exception as e:
        print(f"--- Proxy Critical Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/recognize', methods=['POST'])
def recognize_menu():
    if 'image' not in request.files:
        return jsonify({"error": "No image uploaded"}), 400
    
    file = request.files['image']
    image_bytes = file.read()
    img = Image.open(io.BytesIO(image_bytes))

    prompt = """
    請分析這張菜單圖片，並根據菜單上的標題提取所有餐點項目。
    回傳 JSON 格式為一個陣列，每個物件包含：
    - "name": 餐點名稱（保持繁體中文，區分大小份）。
    - "price": 價格（數字）。
    - "category": 該餐點屬於的分類（例如：飯類、湯類、主菜、小菜、飲料等）。
    只回傳 JSON 陣列。
    """

    try:
        response = model.generate_content([prompt, img])
        text = response.text
        print("--- AI Raw Response ---")
        print(text)
        
        # More robust JSON extraction
        import re
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
