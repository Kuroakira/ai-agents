# AI Agents Repository

LangGraphを使用したAIエージェントの実験・開発リポジトリ。

## 目的

- LangGraphフレームワークを用いたAIエージェントの構築・検証
- 再利用可能なツールやパターンの蓄積
- 様々なユースケースに対応するエージェントのプロトタイピング

## 技術スタック

| 項目 | 技術 |
|------|------|
| フレームワーク | LangGraph |
| LLM | Google Gemini |
| 言語 | Python 3.11+ |
| パッケージ管理 | pip + venv |
| リンター/フォーマッター | ruff |

## セットアップ

### 1. 仮想環境の作成・有効化

```bash
# 仮想環境を作成（初回のみ）
python3 -m venv .venv

# 仮想環境を有効化
source .venv/bin/activate
```

### 2. 依存関係のインストール

```bash
pip install -e ".[dev]"
```

### 3. 環境変数の設定

```bash
cp .env.example .env
```

`.env`ファイルを編集し、APIキーを設定:

```
GOOGLE_API_KEY=your-api-key-here
```

## プロジェクト構造

```
ai-agents/
├── agents/           # 各エージェントの実装
│   └── {agent_name}/ # 個別エージェントディレクトリ
├── shared/           # 共通モジュール
│   └── tools/        # 再利用可能なツール
├── tests/            # テストコード
├── pyproject.toml    # プロジェクト設定・依存関係
└── .env.example      # 環境変数テンプレート
```

## 開発コマンド

```bash
# テスト実行
pytest

# リントチェック
ruff check .

# 自動フォーマット
ruff format .
```

## エージェント作成ガイドライン

### ディレクトリ構成

新しいエージェントは `agents/{agent_name}/` 配下に作成:

```
agents/my_agent/
├── __init__.py
├── graph.py      # LangGraphのグラフ定義
├── nodes.py      # ノード関数
├── state.py      # 状態スキーマ
└── README.md     # エージェントの説明
```

### コーディング規約

- 型ヒントを必須とする
- docstringはGoogle形式を使用
- 状態スキーマは `TypedDict` または `Pydantic BaseModel` で定義
- ノード関数は単一責任の原則に従う

### 共通ツール

複数のエージェントで使用するツールは `shared/tools/` に配置し、再利用可能にする。

## 今後の拡張予定

- [ ] MCPサーバーとの統合
- [ ] エージェント間のオーケストレーション
- [ ] 追加LLMプロバイダー対応（Anthropic, OpenAI等）
