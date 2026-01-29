# Travel Concierge Agent

旅行願望ヒアリング＆リサーチAIエージェント。

## 概要

ユーザーの曖昧な「旅行願望」をチャット形式でヒアリングし、要件が固まり次第、自律的にWebリサーチを実行。その結果を比較検討しやすい「旅行雑誌」のような形式でNotionに自動出力するエージェントです。

## アーキテクチャ

```mermaid
graph TD;
    __start__([__start__])
    interview(interview<br/>ヒアリング)
    research(research<br/>Webリサーチ)
    publish(publish<br/>Notion出力)
    __end__([__end__])
    __start__ --> interview;
    interview -->|情報不足| interview;
    interview -->|情報完了| research;
    research --> publish;
    publish --> __end__;
```

## 機能

- **ヒアリング**: 自然な会話で旅行要件を収集（目的地、時期、人数、こだわり）
- **Webリサーチ**: Tavily APIで時期トレンド・価格相場・宿泊施設を検索
- **Notion出力**: 調査結果を「旅行雑誌」形式でデータベースに自動作成

## セットアップ

### 1. 環境変数設定

プロジェクトルートの`.env`ファイルに以下を追加:

```bash
# Google Gemini API Key（LLM用）
GOOGLE_API_KEY=your_gemini_api_key

# Tavily API Key（Web検索用）
# https://tavily.com/ で取得
TAVILY_API_KEY=your_tavily_api_key

# Notion API Key
# https://www.notion.so/my-integrations で取得
NOTION_API_KEY=your_notion_api_key

# Notion Database ID（出力先データベース）
# データベースのURLまたはIDを設定
NOTION_DATABASE_ID=your_database_id_or_url

# ユーザーの居住地（フライト検索用、デフォルト: 東京）
USER_LOCATION=東京

# Slack Bot Token（Travel Concierge専用）
TRAVEL_SLACK_BOT_TOKEN=xoxb-your-bot-token
TRAVEL_SLACK_APP_TOKEN=xapp-your-app-token
```

### 2. Slack App設定

Scheduler Agentとは別のSlack Appを作成します。

#### 2.1 Slack App作成

1. [Slack API](https://api.slack.com/apps)で「Create New App」→「From scratch」
2. App名: `Travel Concierge`、ワークスペースを選択

#### 2.2 Socket Mode有効化

1. 「Socket Mode」→ Enable Socket Mode を ON
2. 「Generate」→ App Token (`xapp-...`) をコピー → `TRAVEL_SLACK_APP_TOKEN`

#### 2.3 App Manifestで権限付与
```
display_information:
  name: Travel Concierge
  description: 旅行コンシェルジュAI - 旅行計画をお手伝いします
  background_color: "#2eb886"
features:
  app_home:
    home_tab_enabled: true
    messages_tab_enabled: true
    messages_tab_read_only_enabled: false
  bot_user:
    display_name: Travel Concierge
    always_online: true
oauth_config:
  scopes:
    bot:
      - app_mentions:read
      - chat:write
      - im:history
      - im:read
      - im:write
settings:
  event_subscriptions:
    bot_events:
      - app_home_opened
      - app_mention
      - message.im
  interactivity:
    is_enabled: true
  org_deploy_enabled: false
  socket_mode_enabled: true
  token_rotation_enabled: false
```

#### 2.5 インストール

「Install App」→「Install to Workspace」
Bot User OAuth Token (`xoxb-...`) をコピー → `TRAVEL_SLACK_BOT_TOKEN`

### 3. Notion設定

#### 3.1 インテグレーション作成

1. [Notion Integrations](https://www.notion.so/my-integrations)にアクセス
2. 「New integration」をクリック
3. 名前を入力（例: Travel Concierge）
4. 「Submit」→ 表示された **Internal Integration Secret** をコピー

#### 3.2 データベース作成と連携

1. Notionで新しいデータベースを作成
2. データベースページの右上「...」→「Connections」→ 作成したインテグレーションを追加
3. データベースのURLをコピーして`NOTION_DATABASE_ID`に設定

### 4. 依存関係インストール

```bash
pip install -e ".[dev]"
```

## 使い方

### Slack Bot

```bash
python -m agents.travel_concierge.slack_app
```

チャンネルで `@Travel Concierge 北海道に行きたい` のようにメンションすると、スレッドで会話が始まります。

### コンソールチャット

```bash
python -m agents.travel_concierge.example
```

### デモモード（インタビューのみ）

```bash
python -m agents.travel_concierge.example --demo
```

### 入力例

```
北海道に旅行したいんだよね
↓
GWあたりかな、4月末から5月頭
↓
大人2人と子供2人、5歳と2歳です
↓
和室で布団がいいな、あとカニ料理が食べたい！
```

### 出力例

Notionに以下のような記事が自動作成されます:

```
✈️ 北海道 家族旅行プラン案

📋 旅行条件
• 目的地: 北海道
• 時期: GWあたり
• 人数: 大人2名、子供2名（5歳と2歳）
• こだわり: 和室、布団、カニ料理

📅 狙い目の時期と相場
• 4月中旬 - ¥25,000〜¥35,000
  メリット: 混雑少ない、桜が見頃
  デメリット: 天候不安定

🏨 おすすめ宿泊施設
• ○○旅館
  特徴: 和室あり、カニ料理自慢
  💡 家族連れに最適な静かな旅館です
```

## ファイル構成

```
agents/travel_concierge/
├── __init__.py      # パッケージ初期化
├── state.py         # 状態スキーマ（Pydantic）
├── tools.py         # Tavily/Notion API操作
├── nodes.py         # ノード関数（LLM連携含む）
├── graph.py         # LangGraphワークフロー
├── slack_app.py     # Slack Bot統合
├── example.py       # コンソール実行サンプル
├── README.md        # 日本語ドキュメント
└── README.en.md     # 英語ドキュメント
```

## パラメータ

### TravelContext（収集する情報）

| パラメータ | 型 | 説明 |
|-----------|-----|------|
| destination | str | 目的地 |
| timing | str | 時期（曖昧でOK） |
| travelers | Travelers | 人数構成（大人・子供・備考） |
| constraints | list[str] | こだわり条件 |

### 出力（TravelConciergeState）

| パラメータ | 型 | 説明 |
|-----------|-----|------|
| research_result | ResearchResult | 調査結果（時期・宿泊施設） |
| notion_page_url | str | 作成されたNotionページURL |
| response_text | str | ユーザーへの応答メッセージ |

## トラブルシューティング

### TAVILY_API_KEYエラー

[Tavily](https://tavily.com/)でAPIキーを取得し、`.env`に設定してください。

### NOTION_API_KEYエラー

[Notion Integrations](https://www.notion.so/my-integrations)でインテグレーションを作成し、APIキーを取得してください。

### Notionにページが作成されない

- データベースにインテグレーションが接続されているか確認
- データベースIDが正しいか確認

## ライセンス

MIT
