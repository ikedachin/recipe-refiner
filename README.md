# Recipe Refiner

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

- このリポジトリは`GPT-6 Astra時代のCodex ― 基礎・セキュリティ・実践活用を学ぶ`というイベントで活用したアプリです。実運用などは考慮されていませんので、ご理解ください。


いつものレシピを、今の気分に。元レシピと変更希望を入力すると、LLMが料理として成立するように材料・分量・水分・油脂・味付け・火入れ・工程・器具を見直します。変更の必要がない部分は維持します。

個人がローカルで使うためのDjangoアプリです。ログインは不要。Python 3.12以上、Django 5.2 LTS、SQLite、Django Templates、HTML/CSS/Vanilla JavaScriptで構成し、Node.js/npmやフロントエンドのビルド工程、Dockerは使いません。

現在の `settings/llm.yaml` は、作者がOllama向けに変更した設定です。ローカルのOllamaで `gemma4:latest` を使用します。変更箇所と設定の意味は、後述の「LLM設定」で説明しています。

## このアプリの作成経緯

Recipe Refinerは、ChatGPTとの対話で要件を整理し、そこで作成した実装プロンプトをCodexに渡して開発しました。アイデアの相談、30項目の質問への回答、初回プロンプトの作成を経て、YAMLでOpenAI APIとローカルLLMを切り替える要件を追加しています。

対話の記録と各プロンプトは「作成プロンプト」フォルダに保存しています。詳しい流れは[作成経緯のREADME](作成プロンプト/README.md)、元のやり取りは[ChatGPTの共有チャット](https://chatgpt.com/share/6abe5ce0-63fc-83e8-87b1-f7905928c23e)を参照してください。

## 主な機能と画面

- **新しいリファイン**: 左に自由形式の元レシピ、右に自然言語の変更希望。送信はfetchによるAJAXで、ページを再読み込みしません。
- **結果**: 料理名、人数、所要時間、材料、全工程、変更前→変更後と理由、推測、注意点を表示。レシピ文章のコピーもできます。
- **大きな変更の確認**: 問題の理由・必要な大きな変更・代替案を表示。「この条件で続行」のときだけ再生成します。「変更内容を修正」または入力の編集で確認を取り消します。
- **再リファイン**: 成功した直前の結果が次のベースになります。入力欄は読み取り専用に切り替わり、元の履歴を上書きしません。
- **レシピの履歴**: Original / Revisionを選択。各Revisionの変更指示、使用モデル、API方式、生成日時、親Revisionが分かります。過去のRevisionやOriginalから分岐できます。
- **お気に入り**: レシピ単位の☆/★で登録・解除。一覧画面から開けます。
- **LLM表示**: 画面上部にYAMLの現在のProviderとモデルを読み取り専用で表示。過去の結果には生成時のモデルを表示します。

結果の保存は自動です。正常な結果だけをRecipeとRecipeRevisionへ一つのトランザクションで保存します。生成失敗や確認待ちは通常のRevisionに保存しません。

## 必要環境・セットアップ

- Python 3.12以上
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Ollama](https://ollama.com/)と、Ollamaに取得済みの `gemma4:latest` モデル（現在の設定）
- OpenAI APIに切り替える場合のみ、利用可能なモデルとOpenAI APIキー


このディレクトリで実行します。

```bash
uv sync
cp .env.example .env
```

ローカルで試す場合は `.env.example` を `.env` にコピーした状態で利用できます。現在のOllama設定ではOpenAI APIキーは不要です。`DJANGO_DEBUG=True` の開発用途では、秘密鍵が未設定または `change-me` の場合、アプリが開発用の鍵を使用します。`DJANGO_DEBUG=False` にする場合は固有の秘密鍵が必要です。

`uv sync` は `pyproject.toml` と `uv.lock` に従って `.venv` を作成します。仮想環境の手動activateは不要です。以降のコマンドは `uv run` で実行します。共有キャッシュへ書き込めない環境では `UV_CACHE_DIR=/tmp/recipe-refiner-uv-cache uv sync` のように書き込み可能なキャッシュを指定できます。

必要に応じて `.env` を編集します（既存の `.env` がある場合、コピーで上書きしないでください）。以下は設定項目の例です。

```dotenv
DJANGO_SECRET_KEY=ここに固有のランダム文字列を設定
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,[::1]
OPENAI_API_KEY=
LOCAL_LLM_API_KEY=dummy
```

固有の秘密鍵を設定する場合の生成例:

```bash
uv run python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

- OpenAIを使う場合は `OPENAI_API_KEY` を設定します。
- 現在のローカルOllamaでは `OPENAI_API_KEY` は不要です。`LOCAL_LLM_API_KEY=dummy` はSDKが要求するキーの値を満たすためのもので、OpenAIへの認証には使いません。通常のローカルOllamaではこの値は無視されます。認証付きのOpenAI互換サーバーに変更する場合のみ、そのサーバー用のキーを指定します。詳しくは[Ollama公式のOpenAI互換APIの説明](https://docs.ollama.com/api/openai-compatibility)を参照してください。
- Provider、モデル名、API方式、接続先は `.env` に書きません。
- `.env`、SQLite、`.venv`、収集済み静的ファイルは `.gitignore` で除外済みです。

## LLM設定: 作者がOllama向けに変更したYAML

ChatGPTで作成した実装プロンプトでは、OpenAI APIとローカルLLMをYAMLで切り替える構成を指定していました。実装後、作者自身が `settings/llm.yaml` をOllamaで使えるように変更しました。現在のREADMEは、この変更後のファイルに合わせています。

LLMの非機密設定は `settings/llm.yaml` にまとめています。APIキーなどの秘密情報は `.env` に分けます。

### 現在の設定

コメントを省いた現在の `settings/llm.yaml` は以下のとおりです。

```yaml
provider: local

openai:
  model: gpt-5.6
  api_style: responses
  send_temperature: false
  structured_output: json_schema

local:
  base_url: http://127.0.0.1:11434/v1
  model: gemma4:latest
  api_style: chat_completions
  send_temperature: true
  structured_output: json_schema

generation:
  timeout_seconds: 300
  temperature: 0.2

retry:
  invalid_response_max_retries: 1
```

`provider: local` により、現在は `local` セクションのOllama設定が選択されます。`openai` セクションは切り替え用に残っており、現在の生成には使用されません。設定ローダーは両セクションを検証するため、Ollamaだけを使う場合も `openai` セクションは残してください。

### 作者による変更内容

従来のREADMEに掲載していたOpenAI / vLLM向けの設定例と、現在のファイルの違いは次のとおりです。

| 設定項目 | 従来のREADMEの設定例 | 現在のOllama用設定 | 変更の意味 |
| --- | --- | --- | --- |
| `provider` | `openai` | `local` | ローカルLLM用のProviderを選択し、Ollamaへ接続する |
| `local.base_url` | `http://localhost:8001/v1` | `http://127.0.0.1:11434/v1` | vLLM向けの接続先を、同じPC上のOllamaのOpenAI互換APIへ変更する |
| `local.model` | `Qwen3.8-27B-NVFP4` | `gemma4:latest` | Ollamaで使用するモデル名に変更する |
| `generation.timeout_seconds` | `120` | `300` | ローカルでの生成に時間がかかる場合に備え、各API通信のタイムアウトを120秒から300秒（5分）へ延長する |

`local.api_style: chat_completions`、`local.send_temperature: true`、`local.structured_output: json_schema`、`generation.temperature: 0.2`、`retry.invalid_response_max_retries: 1` は、従来のREADMEの設定例から維持しています。それぞれの役割は次のとおりです。

- **`api_style: chat_completions`**: Ollamaの `/v1/chat/completions` に、元レシピと変更希望を送信します。このアプリはOpenAI Python SDKを通じてOllamaのOpenAI互換APIを利用します。[Ollama公式ドキュメント](https://docs.ollama.com/api/openai-compatibility)
- **`send_temperature: true` と `temperature: 0.2`**: 生成時にtemperatureを送信し、低めの値で出力のばらつきを抑える設定です。
- **`structured_output: json_schema`**: アプリが定義したJSON SchemaをAPIへ渡し、材料・手順・変更点などを構造化したJSONとして生成させます。受信後もPydanticで検証します。
- **`invalid_response_max_retries: 1`**: 空の出力や形式が不正な出力に対し、1回だけ再生成を試みます。初回を含めて最大2回の生成となります。API接続エラーやタイムアウトはこの再試行の対象に含まれません。

300秒は各API通信のタイムアウトです。不正な出力の再生成が発生すると、操作全体の待ち時間は300秒を超える場合があります。

YAML内には、以前のvLLM用のURLとポート説明がコメントとして残っています。`# base_url: http://localhost:8001/v1` は無効で、実際に使う接続先は `http://127.0.0.1:11434/v1` です。

### Ollamaで使う準備

Ollamaをインストールし、ローカルサーバーを起動してください。デスクトップアプリなどで既に起動している場合はそのまま利用できます。手動で起動する場合は、別のターミナルで次を実行します。

```bash
ollama serve
```

使用できるモデルを確認します。

```bash
ollama list
```

`gemma4:latest` が未取得の場合は、次のコマンドで取得します。

```bash
ollama pull gemma4:latest
```

別のモデルを使う場合は、`ollama list` に表示されるモデル名に合わせて `local.model` を変更してください。現在の接続先はローカルOllamaのポート11434で、Djangoの既定ポート8000と分かれています。Ollamaのコマンドについては[公式CLIの説明](https://docs.ollama.com/cli)も参照してください。

Ollamaとモデルを準備したら、後述の「マイグレーション・起動」の手順でDjangoを起動します。

### OpenAI APIや別のローカルLLMへ切り替える場合

現在のOllama設定を使う場合は `provider: local` のままにします。別のOpenAI互換サーバーを使う場合は、`local.base_url` と `local.model` をそのサーバーに合わせて変更します。

OpenAI APIへ切り替える場合は、次のように変更します。

```yaml
provider: openai
```

そのうえで `openai.model` を利用可能なモデル名に設定し、`.env` に `OPENAI_API_KEY` を設定してDjangoを再起動してください。YAMLに残っている `gpt-5.6` は当初の設定例なので、利用するモデルに合わせて見直してください。`api_style: responses` の場合はResponses APIを呼びます。

両方の接続先を設定済みであれば、`provider` の1行でOllamaとOpenAI APIを切り替えられます。画面には現在のProviderとモデルを表示します。

YAMLは画面表示と生成リクエストごとに専用ローダーで読み込みます。そのためYAMLの編集は次の操作から反映されますが、環境変数の変更も含めて確実に適用するには再起動してください。各生成では一つの設定スナップショットを使用します。

### 設定schema

| 項目 | 値・検証 |
| --- | --- |
| `provider` | `openai` / `local` |
| `openai.model`, `local.model` | 空でない文字列、200文字以内。両セクションが必要 |
| `api_style` | `responses` / `chat_completions`。両Providerとも対応 |
| `local.base_url` | http/httpsのURL。認証情報・クエリ・フラグメント不可 |
| `send_temperature` | trueのProviderだけtemperatureを送信 |
| `structured_output` | `json_schema` / `json_object` / `prompt` |
| `generation.timeout_seconds` | 0より大きく600以下。各SDK通信のタイムアウト |
| `generation.temperature` | 0〜2、またはnull（送信しない） |
| `retry.invalid_response_max_retries` | 不正・空出力の再生成回数、0〜3 |

不明な設定キーはエラーです。APIキーをYAMLに追加しても受け付けません。設定値を含むPydanticの生エラーはブラウザへ返さず、問題の項目名だけを表示します。

`temperature` を受け付けないモデルがあるため、OpenAIの例では送信を無効にしています。対応モデルを使う場合は `send_temperature: true` にしてください。未対応パラメーターをエラー後に勝手に変えて再送する処理は行いません。

現在のOllama設定では、OpenAI互換APIへJSON Schemaを渡す `json_schema` 方式を使用します。Ollamaの構造化出力については[公式の説明](https://docs.ollama.com/capabilities/structured-outputs)を参照してください。利用するサーバーでJSON Schemaが未対応なら `json_object`、形式指定パラメーターも未対応なら `prompt` に変更できます。どの方式でも、プロンプトでJSON Schemaを指定し、受信後のPydantic検証は必ず実行します。

### 別のローカルLLMを使う場合: vLLMの設定例

現在の設定はOllama用です。vLLMへ変更する場合は、別途、対応するGPU環境で起動してください。このアプリの依存関係には含めていません。配備済みモデルを使う概念例:

```bash
vllm serve /path/to/your/model --served-model-name recipe-local --host 127.0.0.1 --port 8001
```

```yaml
provider: local
local:
  base_url: http://localhost:8001/v1
  model: recipe-local
  api_style: chat_completions
  send_temperature: true
  structured_output: json_schema
```

YAMLの他のセクションは残してください。Djangoの既定ポート8000との衝突を避けるため、例ではLLMに8001を使用しています。既にvLLMが8000を使っている場合は `base_url` を合わせ、Djangoを `uv run python manage.py runserver 8080` などで起動します。GPU、モデル形式、構造化出力の対応状況は利用するvLLM環境で確認してください。

## マイグレーション・起動

現在の設定では、先にOllamaの起動と `gemma4:latest` の準備を済ませてください。初回セットアップ後は、プロジェクトのディレクトリで次のコマンドを実行します。データベースのマイグレーションを適用してから、開発サーバーを起動します。

```bash
./start.sh
```

ポートなどの開発サーバー引数も渡せます（例: `./start.sh 8080`）。

[http://127.0.0.1:8000/](http://127.0.0.1:8000/) を開きます。「サンプルを入力」で、牛肉カレーから2人前のポークカレーへ変える入力例を試せます。サンプルボタンは入力を埋めるだけで、生成にはLLM接続が必要です。

この環境でホスト名の逆引きが起動を長時間止めたため、`recipes/management/commands/runserver.py` で開発サーバーの逆引きだけを省略しています。Django標準のオプション、静的ファイル配信、リロードは引き続き使えます。

表示名は `config/settings.py` の `APP_DISPLAY_NAME` 一か所で変更できます。

### DEBUG=False

`.env` に固有の `DJANGO_SECRET_KEY` と許可ホストを設定し、`DJANGO_DEBUG=False` にします。プレースホルダーの秘密鍵では起動しません。静的ファイルはWhiteNoiseで配信するので、先に次を実行します。

```bash
uv run python manage.py collectstatic --noinput
uv run python manage.py runserver --nostatic
```

このアプリには認証がありません。ローカル個人利用を前提に、通常は127.0.0.1で起動してください。DEBUG=Falseにするだけでは公開サーバー向けの認証や運用構成にはなりません。

## テスト・コードチェック

```bash
uv sync
uv run python manage.py makemigrations
uv run python manage.py migrate
uv run python manage.py check
uv run python manage.py test
uv run ruff check .
uv run ruff format --check .
```

テストはAPIキーなしで実行できます。ProviderのSDKをモックし、Web/APIテストではProviderをモックします。HTTPXの送信もテスト基底クラスで禁止し、外部APIへ誤って通信した場合は失敗させます。テストDBは本体の履歴とは別です。

検証対象:

- Recipe/Revision、親子関係、別レシピの親の拒否、お気に入り
- YAMLの正常/不正/欠損、モデル・URL・timeout・temperature、Factory
- JSON schema、状態とpayloadの整合性、材料・工程、順序
- OpenAI Responses / Local Chat Completions、両API方式、構造化出力設定
- 不正JSONの再試行、回数上限、空/途中終了、timeout・接続・認証・HTTPエラー
- 初回生成、確認・期限・改ざん、再リファイン、Originalと過去Revisionからの分岐
- 履歴、モデル変更後の履歴保持、CSRF、HTML escape、DBロールバック、DEBUG=Falseのエラー

現在のOllamaへの接続と `gemma4:latest` の生成品質は、Ollamaを起動して実際の画面から別途確認してください。OpenAI APIに切り替えた場合も、接続先に応じて確認してください。通常のテストでは課金APIもローカルLLMも呼びません。

## ディレクトリ構成

```text
recipe-refiner/
├── config/                    # Django設定、URL、WSGI/ASGI
├── recipes/
│   ├── management/commands/runserver.py # 逆引きに依存しないローカル起動
│   ├── migrations/            # 初期migrationを同梱
│   ├── services/
│   │   ├── refinement.py      # 入力・確認・生成・トランザクション保存
│   │   └── llm/
│   │       ├── base.py        # 抽象Provider、ユーザー向け例外
│   │       ├── config.py      # 唯一のYAMLローダーと型付き設定
│   │       ├── factory.py     # YAMLからProvider選択
│   │       ├── openai_provider.py
│   │       ├── openai_compatible_provider.py
│   │       ├── sdk_provider.py # 共通SDK通信、再試行、検証
│   │       ├── prompts.py     # 料理の再設計方針と入力構築
│   │       └── schemas.py     # Pydanticによる出力契約
│   ├── static/recipes/
│   │   ├── css/app.css
│   │   └── js/                # app.js / refine.js / render.js
│   ├── templates/recipes/     # 入力、履歴/お気に入り、エラー
│   ├── tests/                 # 外部通信なしのテスト
│   ├── models.py
│   ├── views.py               # HTTPと表示のみ、Provider分岐なし
│   ├── context_processors.py
│   ├── urls.py
│   └── admin.py
├── settings/llm.yaml          # LLM非機密設定の唯一の設定元
├── .env.example
├── .gitignore
├── .python-version
├── manage.py
├── pyproject.toml
├── uv.lock
└── README.md
```

## データベース構造

`db.sqlite3` に保存します。

**Recipe**: `id`, `title`, `original_text`, `is_favorite`, `created_at`, `updated_at`

**RecipeRevision**: `id`, `recipe`, `parent_revision`, `request_text`, `provider`, `model_name`, `api_style`, `result_json`, `result_text`, `confirmation_json`, `created_at`

- 元テキストはRecipeに保持します。Recipeのタイトルは最初の生成結果を使い、各Revisionのタイトルはその結果JSONに保持します。
- Revisionは追加のみ。初回/Originalから生成したRevisionの親はnullです。再生成時には選択元のRevisionを親にします。
- `result_json` は検証済みの全出力、`result_text` は次の生成に使える全文です。
- `confirmation_json` は大きな変更の了承内容を残します。確認待ちの入力はDBへ保存しません。
- APIキーや秘密情報は保存しません。生成時のProvider/モデル/API方式はYAML変更後も変わりません。
- バックアップはアプリを停止して `db.sqlite3` をコピーしてください。

## LLMの呼び出し構造

```text
fetch + CSRF
  → Django View (JSON入力 / エラーの整形)
  → refinement (入力検証 / ベースRevision選択)
  → load_llm_config (YAML → immutable Pydanticモデル)
  → Factory → OpenAIProvider または OpenAICompatibleProvider
  → SDKProvider (現在のOllama設定は Chat Completions)
  → JSON解析 + Pydantic + 状態と工程の検証
  → needs_confirmation: 確認表示用の署名付きトークンを返す
  → ok: Recipe/Revisionをatomic保存 → HTMLとして結果表示
```

現在の設定では `OpenAICompatibleProvider` が選択され、OpenAI Python SDKから `http://127.0.0.1:11434/v1/chat/completions` へリクエストを送ります。Provider名が `local`、SDK名がOpenAIでも、生成の接続先はローカルのOllamaです。

確認トークンは元入力・変更希望・親Revision・確認内容に紐づき、有効期限は30分です。続行時にクライアントから別の入力を渡しても置き換えません。トークンは署名付きで暗号化ではありません。ログインの代わりにはなりません。入力変更後は再度リファインして新しい確認を取得します。

レスポンスschemaは必須フィールドを統一しています。`status=ok` では `recipe` が必須で `confirmation=null`、`needs_confirmation` ではその逆です。`changes` / `assumptions` / `warnings` は常に配列です。LLMがJSONを守らなくても最大再試行回数で打ち切り、読みやすいエラーを表示します。API通信エラーにSDK側の隠れた再試行はありません。

### API

| メソッド・URL | 用途 |
| --- | --- |
| `POST /api/refine/` | 新規: `original_text`, `request_text` |
| `POST /api/refine/<revision_id>/` | Revisionから: `request_text` |
| `POST /api/recipes/<recipe_id>/refine/` | Originalから: `request_text` |
| `POST /api/refine/confirm/` | 確認続行: `confirmation_token` |
| `POST /api/recipes/<recipe_id>/favorite/` | お気に入り切り替え |
| `GET /api/recipes/<recipe_id>/history/` | 元レシピとRevision一覧 |

POSTのリファイン入力は `application/json`。すべてのPOSTにDjango標準のCSRF対策が適用されます。入力上限は元レシピ30,000文字・変更希望6,000文字です。送信中はボタンと入力欄を無効化して二重送信を防ぎます。

## エラーの対処

| 表示 | 確認すること |
| --- | --- |
| YAMLが読めない / 設定が不正 | `settings/llm.yaml` の存在、構文、表示された項目 |
| APIキーが未設定 / 認証失敗 | `.env` のキー、再起動、利用権限 |
| LLMに接続できない | Ollamaの起動、`local.base_url`、ポート11434（別サーバーへ変更した場合はその接続先） |
| タイムアウト | サーバー負荷、モデル、YAMLのtimeout |
| LLM APIエラー | `ollama list` でモデル名を確認。`gemma4:latest` の取得状況、API方式、構造化出力/temperatureの対応 |
| 解析できない | モデルのJSON能力、構造化出力設定、入力内容を見直して再実行 |
| データベースエラー | migrate済みか、ファイルの書き込み権限、ディスク空き容量 |
| 確認の期限切れ | もう一度リファインして確認内容を取得 |
| ページの有効期限切れ | 再読み込みしてCSRFトークンを更新 |

## 今後の拡張

親Revisionモデルを使った履歴ツリー、別Providerの追加、出力schemaの拡張が可能です。URL取得・OCR・画像/PDF入力・栄養DB・複数ユーザー・共有・クラウド同期・ストリーミングは実装していません。

## ライセンス

このプロジェクトは [MIT License](LICENSE) のもとで公開しています。

Copyright (c) 2026 ikedachin
