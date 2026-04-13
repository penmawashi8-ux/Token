#!/usr/bin/env python3
"""
YouTube OAuth リフレッシュトークン取得スクリプト（認証コードフロー）

【ステップ1】認証URLを生成して表示:
    python get_token.py --client-id <ID>

【ステップ2】認証コードをトークンに交換:
    python get_token.py --client-id <ID> --client-secret <SECRET> --code <CODE>

環境変数でも指定可能:
    YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_AUTH_CODE
"""

import argparse
import os
import sys
from urllib.parse import urlencode, urlparse, parse_qs

import requests

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/youtube"
# ウェブアプリ・デスクトップアプリ共通で使えるリダイレクトURI
REDIRECT_URI = "http://localhost"


def generate_auth_url(client_id: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def exchange_code(client_id: str, client_secret: str, code: str) -> dict:
    resp = requests.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    data = resp.json()
    if "error" in data:
        print(f"[ERROR] {data.get('error_description', data['error'])}", file=sys.stderr)
        sys.exit(1)
    return data


def extract_code_from_url(url: str) -> str | None:
    """リダイレクト先のURL全体を貼った場合でもcodeを抽出する"""
    try:
        qs = parse_qs(urlparse(url).query)
        codes = qs.get("code")
        return codes[0] if codes else None
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="YouTube OAuth リフレッシュトークン取得")
    parser.add_argument("--client-id", default=os.environ.get("YOUTUBE_CLIENT_ID"))
    parser.add_argument("--client-secret", default=os.environ.get("YOUTUBE_CLIENT_SECRET"))
    parser.add_argument("--code", default=os.environ.get("YOUTUBE_AUTH_CODE"),
                        help="認証コード（Googleリダイレクト先URLごと貼り付けてもOK）")
    args = parser.parse_args()

    if not args.client_id:
        parser.error("--client-id または環境変数 YOUTUBE_CLIENT_ID が必要です")

    # ステップ1: 認証URLを生成して表示
    if not args.code:
        url = generate_auth_url(args.client_id)
        print()
        print("=" * 70)
        print("【ステップ1】以下のURLにアクセスして Google アカウントで認証してください")
        print()
        print(f"  {url}")
        print()
        print("認証後、ブラウザのアドレスバーに")
        print("  http://localhost/?code=xxxxxxxx&scope=...")
        print("のようなURLが表示されます（ページは開かなくてOK）。")
        print()
        print("そのURLをまるごとコピーして --code に渡してください:")
        print(f'  python get_token.py --client-id ... --client-secret ... --code "<URL>"')
        print("=" * 70)
        print()

        if os.environ.get("GITHUB_ACTIONS") == "true":
            print(f"::notice title=【ステップ1】認証URLにアクセスしてください::{url}")
            print("::notice title=次のステップ::認証後にリダイレクト先URLをコピーし、step2-exchange-code ワークフローの auth_code に貼り付けてください")
        sys.exit(0)

    # URLごと貼られた場合はcodeだけ抽出
    code = args.code
    extracted = extract_code_from_url(code)
    if extracted:
        code = extracted

    if not args.client_secret:
        parser.error("--client-secret または環境変数 YOUTUBE_CLIENT_SECRET が必要です")

    print("[1/1] 認証コードをトークンに交換中...")
    tokens = exchange_code(args.client_id, args.client_secret, code)

    refresh_token = tokens.get("refresh_token")
    access_token = tokens.get("access_token", "")

    if not refresh_token:
        print("[ERROR] リフレッシュトークンが含まれていません。", file=sys.stderr)
        print("        同じアカウントで過去に認証済みの場合、Google の管理画面でアクセスを削除してから再試行してください。", file=sys.stderr)
        print("        https://myaccount.google.com/permissions", file=sys.stderr)
        sys.exit(1)

    print()
    print("=" * 70)
    print("取得完了!")
    print()
    print(f"REFRESH_TOKEN={refresh_token}")
    print()
    print("=" * 70)

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"refresh_token={refresh_token}\n")
            f.write(f"access_token={access_token}\n")
        print("::notice title=完了::リフレッシュトークンが GITHUB_OUTPUT に書き込まれました")


if __name__ == "__main__":
    main()
