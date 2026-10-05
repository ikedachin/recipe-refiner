#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v uv >/dev/null 2>&1; then
    printf 'エラー: uv が見つかりません。READMEのセットアップ手順に従ってインストールしてください。\n' >&2
    exit 1
fi

if [[ ! -f .env ]]; then
    printf 'エラー: .env がありません。.env.example を .env にコピーして設定してください。\n' >&2
    exit 1
fi

uv run python manage.py migrate
exec uv run python manage.py runserver "$@"
