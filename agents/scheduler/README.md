# Scheduler Agent

脳内ダンプ整理＆カレンダー登録AIエージェント。

## 概要

Slackから投げられた雑多なタスク（脳内ダンプ）を受け取り、Google Calendarの空き時間に自動でスケジュール登録するエージェントです。

## アーキテクチャ

```mermaid
graph TD;
    __start__([__start__])
    fetch_calendar_events(fetch_calendar_events<br/>今日の予定を取得)
    analyze_tasks(analyze_tasks<br/>LLMでタスク抽出)
    schedule_tasks(schedule_tasks<br/>カレンダーに登録)
    generate_response(generate_response<br/>応答を生成)
    __end__([__end__])
    __start__ --> fetch_calendar_events;
    fetch_calendar_events --> analyze_tasks;
    analyze_tasks --> schedule_tasks;
    schedule_tasks --> generate_response;
    generate_response --> __end__;
```

## 機能

- **タスク抽出**: 自然言語からタスクを自動識別
- **所要時間推測**: タスクの内容から適切な時間を見積もり
- **空き時間検出**: Google Calendarから今日の空きスロットを計算
- **自動スケジューリング**: 希望時間または空き時間にタスクを配置
- **Slack連携**: Socket Modeで常駐し、メッセージに即時応答

## セットアップ

### 1. Google Cloud設定（Calendar API用）

Google Calendar APIはOAuth 2.0認証を使用します。

#### 1.1 プロジェクト作成とAPI有効化

1. [Google Cloud Console](https://console.cloud.google.com/)にアクセス
2. 新しいプロジェクトを作成（または既存のプロジェクトを選択）
3. 左メニュー「APIとサービス」→「ライブラリ」
4. 「Google Calendar API」を検索して「有効にする」

#### 1.2 OAuth同意画面の設定

1. 左メニュー「APIとサービス」→「OAuth同意画面」
2. User Type: **External** を選択して「作成」
3. アプリ情報を入力:
   - アプリ名: 任意（例: Scheduler Bot）
   - ユーザーサポートメール: 自分のメールアドレス
   - デベロッパーの連絡先: 自分のメールアドレス
4. 「保存して次へ」→ スコープは追加せず「保存して次へ」
5. テストユーザーに**自分のGmailアドレス**を追加 → 「保存して次へ」

#### 1.3 認証情報の作成

1. 左メニュー「APIとサービス」→「認証情報」
2. 「認証情報を作成」→「OAuthクライアントID」
3. アプリケーションの種類: **デスクトップアプリ**
4. 名前: 任意（例: Scheduler Bot Desktop）
5. 「作成」→ JSONをダウンロード
6. ダウンロードしたファイルを **`credentials.json`** としてプロジェクトルートに配置

### 2. Slack App設定

#### 2.1 アプリ作成

1. [Slack API](https://api.slack.com/apps)にアクセス
2. 「Create New App」→「**From scratch**」を選択
3. App Name: 任意（例: Scheduler Bot）
4. Workspace: インストール先のワークスペースを選択
5. 「Create App」

#### 2.2 Socket Mode有効化とApp Token取得

1. 左メニュー「Socket Mode」
2. 「Enable Socket Mode」をON
3. Token Name: 任意（例: scheduler-socket）
4. 「Generate」→ 表示された **App Token (`xapp-...`)** をコピーして保存

#### 2.3 App Manifestで一括設定（推奨）

1. 左メニュー「App Manifest」
2. YAMLタブで以下の内容に置き換え:

```yaml
display_information:
  name: Scheduler Bot
features:
  bot_user:
    display_name: Scheduler Bot
    always_online: false
oauth_config:
  scopes:
    bot:
      - app_mentions:read
      - chat:write
      - im:history
      - im:read
      - reactions:read
      - reactions:write
settings:
  event_subscriptions:
    bot_events:
      - app_mention
      - message.im
  interactivity:
    is_enabled: true
  org_deploy_enabled: false
  socket_mode_enabled: true
  token_rotation_enabled: false
```

3. 「Save Changes」

#### 2.4 アプリのインストールとBot Token取得

1. 左メニュー「Install App」
2. 「Install to Workspace」→「許可する」
3. 表示された **Bot User OAuth Token (`xoxb-...`)** をコピーして保存

### 3. 環境変数設定

プロジェクトルートに`.env`ファイルを作成:

```bash
# Google Gemini API Key（LLM用）
# https://aistudio.google.com/app/apikey で取得
GOOGLE_API_KEY=your_gemini_api_key

# Slack Bot Token（OAuth & Permissionsで取得）
SLACK_BOT_TOKEN=xoxb-your-bot-token

# Slack App Token（Socket Mode有効化時に取得）
SLACK_APP_TOKEN=xapp-your-app-token

# LangChain トレーシング（オプション）
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langchain_api_key
```

#### 認証方式の違い

| 用途 | 認証方式 | 必要なもの |
|------|----------|-----------|
| Google Calendar API | OAuth 2.0 | `credentials.json` + `token.json`（自動生成） |
| Google Gemini (LLM) | API Key | `GOOGLE_API_KEY` 環境変数 |
| Slack Bot | Token | `SLACK_BOT_TOKEN` + `SLACK_APP_TOKEN` |

### 4. 依存関係インストール

```bash
pip install -e ".[dev]"
```

### 5. 初回認証（Google Calendar）

初回実行時にブラウザが開き、Googleアカウントの認証を求められます。

1. 「続行」をクリック
2. 自分のGoogleアカウントを選択
3. 「このアプリは確認されていません」と表示されたら「詳細」→「（アプリ名）に移動」
4. 「許可」をクリック

認証成功後、`token.json`がプロジェクトルートに自動生成されます。

## 使い方

### Slack Bot起動

```bash
python -m agents.scheduler.slack_app
```

### ローカルテスト（Slack連携なし）

```bash
python -m agents.scheduler.example
```

### 入力例

```
10時に会議資料の見直しと、あと牛乳買いたい。夜はジム行く
```

### 出力例

```
✅ 以下のタスクをカレンダーに登録しました：

• 10:00〜10:30: 📝会議資料の見直し
• 12:00〜12:30: 📝牛乳を買う
• 19:00〜20:30: 📝ジムに行く
```

## ファイル構成

```
agents/scheduler/
├── __init__.py      # パッケージ初期化
├── state.py         # 状態スキーマ（Pydantic）
├── tools.py         # Google Calendar API操作
├── nodes.py         # ノード関数（LLM連携含む）
├── graph.py         # LangGraphワークフロー
├── slack_app.py     # Slack Bot連携
├── example.py       # 実行サンプル
├── README.md        # 日本語ドキュメント
└── README.en.md     # 英語ドキュメント
```

## パラメータ

### 入力（SchedulerState）

| パラメータ | 型 | 説明 |
|-----------|-----|------|
| user_input | str | ユーザーからの入力メッセージ |
| user_id | str | SlackのユーザーID |
| channel_id | str | SlackのチャンネルID |

### 出力（SchedulerState）

| パラメータ | 型 | 説明 |
|-----------|-----|------|
| response_text | str | ユーザーへの応答メッセージ |
| scheduled_events | list[CalendarEvent] | 登録されたイベントリスト |
| extracted_tasks | list[TaskItem] | 抽出されたタスクリスト |
| error_message | str \| None | エラーメッセージ |

## 設定

### 稼働時間

デフォルトでは9:00〜21:00を稼働時間として空き時間を計算します。
変更する場合は`tools.py`の`calculate_free_slots()`を修正してください。

### タスク名のプレフィックス

登録されるタスクには「📝」がプレフィックスとして付与されます。
変更する場合は`nodes.py`のシステムプロンプトを修正してください。

## トラブルシューティング

### credentials.jsonが見つからない

Google Cloud Consoleから再度ダウンロードしてください。

### token.jsonの認証エラー

`token.json`を削除して再認証してください。

### Slackに応答しない

- Bot TokenとApp Tokenが正しいか確認
- Socket Modeが有効になっているか確認
- Event Subscriptionsが正しく設定されているか確認

## ライセンス

MIT
