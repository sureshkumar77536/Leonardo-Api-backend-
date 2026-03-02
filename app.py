from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import time

app = Flask(__name__)
CORS(app) # Frontend se request allow karne ke liye

def upload_image_to_leonardo(image_file, headers):
    # Get presigned URL
    url = "https://cloud.leonardo.ai/api/rest/v1/init-image"
    payload = {"extension": image_file.filename.split('.')[-1]}
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code != 200:
        return None
    
    # Upload image
    data = response.json()['uploadInitImage']
    fields = json.loads(data['fields'])
    upload_url = data['url']
    image_id = data['id']
    
    files = {'file': (image_file.filename, image_file.read(), image_file.content_type)}
    upload_response = requests.post(upload_url, data=fields, files=files)
    
    if upload_response.status_code == 204:
        return image_id
    return None

@app.route('/generate-video', methods=['POST'])
def generate_video():
    # Frontend se details lena
    api_key = request.form.get('api_key')
    prompt = request.form.get('prompt', 'The koala plays with the cat')
    img1 = request.files.get('image1')
    img2 = request.files.get('image2')

    if not api_key or not img1 or not img2:
        return jsonify({"error": "API Key aur dono images dena zaroori hai!"}), 400

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {api_key}"
    }

    try:
        # 1. Upload both images
        image_id_1 = upload_image_to_leonardo(img1, headers)
        image_id_2 = upload_image_to_leonardo(img2, headers)

        if not image_id_1 or not image_id_2:
            return jsonify({"error": "Images upload karne mein error aayi"}), 500

        # 2. Generate Video
        gen_url = "https://cloud.leonardo.ai/api/rest/v2/generations"
        payload = {
            "model": "seedance-1.0-lite",
            "public": False,
            "parameters": {
                "prompt": prompt,
                "guidances": {
                    "image_reference": [
                        {"image": {"id": image_id_1, "type": "UPLOADED"}},
                        {"image": {"id": image_id_2, "type": "UPLOADED"}}
                    ]
                },
                "duration": 4,
                "mode": "RESOLUTION_720",
                "prompt_enhance": "OFF",
                "width": 1248,
                "height": 704
            }
        }

        gen_response = requests.post(gen_url, json=payload, headers=headers)
        if gen_response.status_code != 200:
            return jsonify({"error": "Video generation start nahi hui", "details": gen_response.text}), 500

        generation_id = gen_response.json()['generate']['generationId']

        # 3. Wait and fetch video URL (Aap isko frontend par polling se bhi kar sakte hain future mein)
        fetch_url = f"https://cloud.leonardo.ai/api/rest/v1/generations/{generation_id}"
        
        # NOTE: Sync sleep lagana best practice nahi hai, but simple API ke liye abhi 180 sec wait kar rahe hain
        time.sleep(180) 
        
        # API call headers for GET request shouldn't have content-type for body
        get_headers = {
            "accept": "application/json",
            "authorization": f"Bearer {api_key}"
        }
        final_response = requests.get(fetch_url, headers=get_headers)
        
        return jsonify({"success": True, "data": final_response.json()})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
