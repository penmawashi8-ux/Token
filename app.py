import os
import secrets
import requests
from urllib.parse import urlencode
from flask import Flask, render_template, request, redirect, session, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

YOUTUBE_SCOPE = " ".join([
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
])


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/auth", methods=["POST"])
def start_auth():
    client_id = request.form.get("client_id", "").strip()
    client_secret = request.form.get("client_secret", "").strip()

    if not client_id or not client_secret:
        return render_template("index.html", error="クライアントIDとシークレットを入力してください。")

    session["client_id"] = client_id
    session["client_secret"] = client_secret
    session["state"] = secrets.token_urlsafe(32)

    redirect_uri = url_for("callback", _external=True)

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": YOUTUBE_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": session["state"],
    }

    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    return redirect(auth_url)


@app.route("/callback")
def callback():
    error = request.args.get("error")
    if error:
        return render_template(
            "index.html",
            error=f"認証エラー: {error}。クライアントIDとシークレットが正しいか確認してください。",
        )

    state = request.args.get("state")
    if state != session.get("state"):
        return render_template("index.html", error="不正なリクエストです (state mismatch)。")

    code = request.args.get("code")
    if not code:
        return render_template("index.html", error="認証コードが取得できませんでした。")

    client_id = session.get("client_id")
    client_secret = session.get("client_secret")
    redirect_uri = url_for("callback", _external=True)

    token_data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    response = requests.post(GOOGLE_TOKEN_URL, data=token_data)
    tokens = response.json()

    if "error" in tokens:
        return render_template(
            "index.html",
            error=f"トークン取得エラー: {tokens.get('error_description', tokens['error'])}",
        )

    refresh_token = tokens.get("refresh_token")
    access_token = tokens.get("access_token")
    scope = tokens.get("scope", "")

    if not refresh_token:
        return render_template(
            "index.html",
            error="リフレッシュトークンが取得できませんでした。Google Cloud Consoleでアプリを削除してから再度お試しください。",
        )

    return render_template(
        "result.html",
        refresh_token=refresh_token,
        access_token=access_token,
        client_id=client_id,
        client_secret=client_secret,
        scope=scope,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    print(f"\n YouTube OAuth Token Generator")
    print(f" http://localhost:{port} を開いてください\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
