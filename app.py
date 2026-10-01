import os
import hashlib
import hmac
import base64
import requests
from urllib.parse import urlencode, quote_plus
from flask import Flask, request, jsonify

app = Flask(__name__)

BASE_URL = "https://api.novofon.com"
METHOD_PATH = "/v1/info/balance/"

PROXIES = None
proxy_url = os.environ.get("PROXY_URL")
if proxy_url:
    PROXIES = {"http": proxy_url, "https": proxy_url}


def build_signature(method_path, params, secret):
    sorted_params = dict(sorted(params.items()))
    params_str = urlencode(sorted_params, quote_via=quote_plus)
    md5_str = hashlib.md5(params_str.encode()).hexdigest()
    hmac_str = hmac.new(
        secret.encode(),
        (method_path + params_str + md5_str).encode(),
        hashlib.sha1
    ).hexdigest()
    return base64.b64encode(hmac_str.encode()).decode()


def parse_auth_header():
    """Достаёт API_KEY:API_SECRET из заголовка Authorization."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        auth = auth[len("Bearer "):]
    parts = auth.split(":", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None, None
    return parts[0], parts[1]


@app.route("/balance", methods=["GET"])
def get_balance():
    api_key, api_secret = parse_auth_header()
    if not api_key or not api_secret:
        return jsonify({"status": "error", "message": "Authorization header required: API_KEY:API_SECRET"}), 401

    params = {}
    signature = build_signature(METHOD_PATH, params, api_secret)

    headers = {"Authorization": f"{api_key}:{signature}"}
    url = BASE_URL + METHOD_PATH

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            proxies=PROXIES,
            timeout=30
        )
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Request to Novofon failed: {e}")
        return jsonify({"status": "error", "message": f"Request failed: {str(e)}"}), 502

    app.logger.info(f"Novofon response: status_code={response.status_code}, body={response.text}")

    if response.status_code == 429:
        return jsonify({"status": "error", "message": "Rate limit exceeded (100/min)"}), 429

    try:
        data = response.json()
    except ValueError:
        return jsonify({"status": "error", "message": f"Non-JSON response: {response.text}"}), 502

    if data.get("status") == "success":
        return jsonify({
            "status": "success",
            "balance": data.get("balance"),
            "currency": data.get("currency")
        }), 200
    else:
        return jsonify({
            "status": "error",
            "message": data.get("message", "unknown error"),
            "raw": data
        }), 502


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
