# Memo Observer エージェント

Slackから受け取ったメモ・つぶやきを解析し、NotionのDatabaseに自動で追記するAIエージェント。

## 概要

- **入力**: Slackへのテキストメッセージ（音声入力経由のつぶやき、Kindle共有など）
- **処理**: Gemini 2.5 Flashでテキストを解析し、動的タグ・コンテンツを抽出
- **出力**: Notionデータベースへのページ作成

## 特徴: 動的タグシステム

固定カテゴリではなく、**AIが内容に応じてタグを動的生成**します。

- 内容を表す具体的なタグを1〜3個自動生成
- 既存タグがあれば再利用（「AI Agent」と「AIエージェント」は同一視）
- 新しい概念の場合は新規タグを自動作成
- 例: 「AIエージェント」「組織構築」「LangGraph」「読書メモ」

## アーキテクチャ

```mermaid
graph TD;
    __start__([__start__])
    fetch_tags(fetch_tags<br/>既存タグ取得)
    parser(parser<br/>テキスト解析)
    tag_matcher(tag_matcher<br/>タグマッチング)
    saver(saver<br/>Notion保存)
    __end__([__end__])
    __start__ --> fetch_tags;
    fetch_tags --> parser;
    parser --> tag_matcher;
    tag_matcher --> saver;
    saver --> __end__;
```

### フロー説明

1. **fetch_tags**: Notionから既存タグ一覧を取得
2. **parser**: LLMでテキストを解析、既存タグを考慮してタグ候補を生成
3. **tag_matcher**: 候補タグと既存タグを類似判定でマッチング
4. **saver**: 最終タグと共にNotionへ保存

## ディレクトリ構成

```
agents/memo/
├── __init__.py              # パッケージ初期化
├── state.py                 # 状態スキーマ（MemoState）
├── schema.py                # LLM出力スキーマ（MemoItem）
├── nodes.py                 # ノード関数（fetch_tags, parser, tag_matcher, saver）
├── graph.py                 # LangGraphワークフロー
├── tools.py                 # Notion API統合 + タグ類似判定
├── slack_app.py             # Slack Bot連携
├── slack_app_manifest.yaml  # Slack App Manifest
├── example.py               # デモスクリプト
├── README.md                # このファイル
└── README.en.md             # 英語版ドキュメント
```

---

## セットアップ

### 1. Google Gemini API

1. [Google AI Studio](https://aistudio.google.com/apikey) にアクセス
2. **Create API Key** をクリック
3. APIキーをコピー → `.env` に設定

```bash
GOOGLE_API_KEY=your_gemini_api_key
```

### 2. Notion Integration

#### 2.1 Integrationの作成

1. [Notion Integrations](https://www.notion.so/my-integrations) にアクセス
2. **New integration** をクリック
3. 設定:
   - **Name**: `Memo Observer`
   - **Associated workspace**: 使用するワークスペースを選択
   - **Capabilities**:
     - ✅ Read content
     - ✅ Insert content
     - ✅ Update content
4. **Submit** → **Internal Integration Secret** をコピー

```bash
MEMO_NOTION_TOKEN=secret_xxxxxxxxxxxxx
```

#### 2.2 データベースの作成

1. Notionで新しいページを作成
2. `/database` と入力 → **Database - Full page** を選択
3. データベース名を設定（例: `Memos`）

#### 2.3 プロパティの設定

以下のプロパティを追加（**事前設定が必要**）:

| プロパティ名 | タイプ | 設定方法 |
|-------------|--------|----------|
| Name | Title | デフォルトで存在（変更不要） |
| Category | Multi-select | `+` → **Multi-select** を選択 |
| Source | Text | `+` → **Text** を選択 |
| Created | Date | `+` → **Date** を選択 |

**Category について**:
- Multi-selectタイプを使用（複数タグ対応）
- 初期オプションは不要（AIが動的に作成）
- 使っていくうちに自動的にタグが増えていく

#### 2.4 Integrationの接続

1. データベースページ右上の `•••` をクリック
2. **Connections** → **Connect to** → `Memo Observer` を選択

#### 2.5 Database IDの取得

ブラウザのURLからIDを取得:

```
https://www.notion.so/yourworkspace/abc123def456789012345678901234?v=xyz
                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                    この部分がDatabase ID
```

URLをそのまま設定してもOK（自動でIDを抽出）:

```bash
MEMO_NOTION_DB_ID=https://www.notion.so/yourworkspace/abc123def456...
# または
MEMO_NOTION_DB_ID=abc123def456789012345678901234
```

### 3. Slack App

#### 3.1 Manifestを使った作成（推奨）

1. [Slack API](https://api.slack.com/apps) → **Create New App**
2. **From an app manifest** を選択
3. ワークスペースを選択
4. `slack_app_manifest.yaml` の内容を貼り付け
5. **Create** をクリック

#### 3.2 App-Level Token の取得

1. **Basic Information** → **App-Level Tokens**
2. **Generate Token and Scopes**
   - Token Name: `socket-mode`
   - Scope: `connections:write` を追加
3. **Generate** → `xapp-...` トークンをコピー

```bash
MEMO_SLACK_APP_TOKEN=xapp-1-xxxxxxxxxxxxx
```

#### 3.3 Bot Token の取得

1. **OAuth & Permissions** → **Install to Workspace**
2. **Allow** をクリック
3. **Bot User OAuth Token** (`xoxb-...`) をコピー

```bash
MEMO_SLACK_BOT_TOKEN=xoxb-xxxxxxxxxxxxx
```

#### 3.4 Botをチャンネルに追加

1. Slackでメモを送信したいチャンネルを開く
2. チャンネル名をクリック → **Integrations** タブ
3. **Add apps** → `Memo Observer` を追加

---

## 環境変数まとめ

`.env` ファイル:

```bash
# Google Gemini API
GOOGLE_API_KEY=your_gemini_api_key

# Notion Integration
MEMO_NOTION_TOKEN=secret_xxxxxxxxxxxxx
MEMO_NOTION_DB_ID=your_database_id_or_url

# Slack Bot (Socket Mode)
MEMO_SLACK_BOT_TOKEN=xoxb-xxxxxxxxxxxxx
MEMO_SLACK_APP_TOKEN=xapp-1-xxxxxxxxxxxxx
```

---

## 入力パターン

### 1. 通常の思考メモ

```
今日、AIエージェントの設計について考えていた。
LangGraphを使うと、状態管理がシンプルになる。
```

→ タグ例: `AIエージェント`, `LangGraph`, `設計`

### 2. Kindle共有

```
"知識は力なり" フランシス・ベーコン『ノヴム・オルガヌム』より
```

→ タグ例: `読書メモ`, `哲学`, `名言`

---

## タグの類似判定

以下のケースは同一タグとして扱われます:

| 候補タグ | 既存タグ | 結果 |
|---------|---------|------|
| `AI Agent` | `ai agent` | 既存を使用 |
| `AIエージェント` | `ＡＩエージェント` | 既存を使用 |
| `Lang Graph` | `langgraph` | 既存を使用 |

正規化ルール:
- 全角英数字 → 半角
- 大文字 → 小文字
- 連続空白 → 単一空白

---

## 使い方

### デモスクリプト

```bash
# サンプルメモで実行
python -m agents.memo.example

# インタラクティブモード
python -m agents.memo.example --interactive
```

### Slack Bot起動

```bash
python -m agents.memo.slack_app
```

### コードから利用

```python
import asyncio
from dotenv import load_dotenv
from agents.memo.graph import app
from agents.memo.state import MemoState

async def main():
    load_dotenv()

    state = MemoState(input_text="今日学んだこと：LangGraphの使い方")
    result = await app.ainvoke(state)

    print(f"Status: {result.get('status')}")
    print(f"Tags: {result.get('final_tags')}")
    print(f"Notion URL: {result.get('notion_url')}")

asyncio.run(main())
```

---

## トラブルシューティング

### Notion APIエラー

**"Could not find property with name..."**
→ データベースにプロパティが存在しません。[プロパティの設定](#23-プロパティの設定)を確認してください。

**"Could not find database..."**
→ Database IDが正しくないか、IntegrationがConnectされていません。

### Slack Botが反応しない

1. Socket Modeが有効になっているか確認
2. Event Subscriptionsでイベントが購読されているか確認
3. Botがチャンネルに追加されているか確認

---

## 拡張予定

- [ ] Human-in-the-loopによる確認フロー
- [ ] 複数メモの一括処理
- [x] ~~タグ自動生成~~ ✅ 実装済み
- [ ] 類似メモの検索・紐付け
- [ ] タグの定期整理（類似タグの統合）
