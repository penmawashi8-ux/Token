#!/usr/bin/env python3
"""
YouTube OAuth リフレッシュトークン取得スクリプト（デバイス認証フロー）

使い方:
    python get_token.py --client-id <ID> --client-secret <SECRET>

環境変数でも指定可能:
    YOUTUBE_CLIENT_ID=... YOUTUBE_CLIENT_SECRET=... python get_token.py
"""

import argparse
import os
import sys
import time

import requests

DEVICE_CODE_URL = "https://oauth2.googleapis.com/device/code"
TOKEN_URL = "https://oauth2.googleapis.com/token"
GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.upload",
]


def get_device_code(client_id: str, scopes: list[str]) -> dict:
    resp = requests.post(
        DEVICE_CODE_URL,
        data={"client_id": client_id, "scope": " ".join(scopes)},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        print(f"[ERROR] デバイスコード取得失敗: {data.get('error_description', data['error'])}", file=sys.stderr)
        sys.exit(1)
    return data


def poll_for_token(client_id: str, client_secret: str, device_code: str, interval: int, expires_in: int) -> dict:
    deadline = time.time() + expires_in
    while time.time() < deadline:
        time.sleep(interval)
        resp = requests.post(
            TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "device_code": device_code,
                "grant_type": GRANT_TYPE,
            },
            timeout=30,
        )
        data = resp.json()
        error = data.get("error")
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            interval += 5
            continue
        if error == "access_denied":
            print("[ERROR] 認証が拒否されました。", file=sys.stderr)
            sys.exit(1)
        if error == "expired_token":
            print("[ERROR] コードの有効期限が切れました。再実行してください。", file=sys.stderr)
            sys.exit(1)
        if error:
            print(f"[ERROR] トークン取得エラー: {data.get('error_description', error)}", file=sys.stderr)
            sys.exit(1)
        if "refresh_token" in data:
            return data
    print("[ERROR] タイムアウト: 認証が完了しませんでした。", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="YouTube OAuth リフレッシュトークン取得")
    parser.add_argument("--client-id", default=os.environ.get("YOUTUBE_CLIENT_ID"), help="OAuth クライアント ID")
    parser.add_argument("--client-secret", default=os.environ.get("YOUTUBE_CLIENT_SECRET"), help="OAuth クライアント シークレット")
    parser.add_argument(
        "--scopes",
        nargs="+",
        default=SCOPES,
        help="OAuth スコープ（スペース区切り）",
    )
    args = parser.parse_args()

    if not args.client_id:
        parser.error("--client-id または環境変数 YOUTUBE_CLIENT_ID が必要です")
    if not args.client_secret:
        parser.error("--client-secret または環境変数 YOUTUBE_CLIENT_SECRET が必要です")

    print("[1/3] デバイスコードを取得中...")
    device_data = get_device_code(args.client_id, args.scopes)

    user_code = device_data["user_code"]
    verification_url = device_data["verification_url"]
    device_code = device_data["device_code"]
    interval = device_data.get("interval", 5)
    expires_in = device_data.get("expires_in", 1800)

    print()
    print("=" * 60)
    print("[2/3] 以下のURLにアクセスして認証コードを入力してください")
    print()
    print(f"  URL  : {verification_url}")
    print(f"  CODE : {user_code}")
    print()
    print(f"  (有効期限: {expires_in // 60} 分)")
    print("=" * 60)
    print()

    # GitHub Actions 向けのアノテーション出力
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::notice title=YouTube認証が必要です::URL: {verification_url}  /  コード: {user_code}")

    print("[3/3] 認証完了を待機中...")
    tokens = poll_for_token(args.client_id, args.client_secret, device_code, interval, expires_in)

    refresh_token = tokens["refresh_token"]
    access_token = tokens.get("access_token", "")

    print()
    print("=" * 60)
    print("取得完了!")
    print()
    print(f"REFRESH_TOKEN={refresh_token}")
    print()
    print("=" * 60)

    # GitHub Actions の出力変数に書き込む
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"refresh_token={refresh_token}\n")
            f.write(f"access_token={access_token}\n")
        print("::notice title=完了::リフレッシュトークンが GITHUB_OUTPUT に書き込まれました。")

    return refresh_token


if __name__ == "__main__":
    main()
