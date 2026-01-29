# 🏗️ Project: Personal Travel Concierge (AI Agent) 基本設計書

## 1. プロダクト概要

ユーザーの曖昧な「旅行願望」をチャット形式でヒアリングし、要件が固まり次第、自律的にWebリサーチを実行。その結果を比較検討しやすい「旅行雑誌」のような形式でNotionに自動出力するエージェント。

---

## 2. システム・アーキテクチャ

システムを3つの自律モジュールに分割し、メインスクリプト（`main.py`）がそれらを指揮します。

1. **👂 Interviewer (ヒアリング担当)**: ユーザーから必須パラメータを引き出す。
2. **🕵️‍♂️ Researcher (調査担当)**: Tavily APIを使い、時期・価格・宿を調査する。
3. **✍️ Publisher (編集・出力担当)**: 調査結果をNotion Block形式に変換し、APIを叩く。

---

## 3. 処理フロー詳細 (Sequence)

### Phase 1: ヒアリングと要件定義 (The Loop)

ユーザーが情報を吐き出し、AIが不足を埋めるフェーズ。

* **Input**: ユーザーの自然言語
* **Logic**:
* LLMが会話履歴を解析し、以下の`TravelContext` (JSON) が埋まっているか判定する。
* **欠損あり** → 不足項目について質問を生成してユーザーに返す（ループ継続）。
* **欠損なし** → `[READY_TO_SEARCH]` フラグを立ててPhase 2へ移行。



**【必須パラメータ定義 (TravelContext)】**

```json
{
  "destination": "北海道",      // 目的地
  "timing": "GWあたり",        // 時期（曖昧でOK）
  "travelers": {               // 人数構成
    "adults": 2,
    "children": 2,
    "notes": "5歳と2歳"
  },
  "constraints": [             // こだわり条件
    "和室", "布団", "カニ料理"
  ]
}

```

### Phase 2: 戦略的Webリサーチ (The Agent Work)

API代を節約しつつ、精度を高める2段階検索ロジック。

* **Step 1: 時期トレンド調査**
* Query: `"{destination}" 旅行 安い時期 ベストシーズン "{timing}" 比較`
* Goal: 「4月中旬が安い」「GWは5/6以降が狙い目」といったテキスト情報を取得。


* **Step 2: 価格相場ハッキング (JAL/Flight)**
* Query: `site:google.com/travel "東京" "{destination}" "JAL" {Step1の日付} 往復 価格`
* Goal: 検索スニペットに出てくる `¥20,000〜` という数字を取得（サイト遷移なし）。


* **Step 3: 宿・体験のスクリーニング**
* Query: `"{destination}" 子連れ 和室 布団 旅館 おすすめ "{constraints}"`
* Validation: 検索結果の上位3件のURL内容を読み込み、「本当に和室か？」をLLMが判定。



### Phase 3: Notion記事生成 (The Output)

Notion APIの `blocks.children.append` を使用し、リッチなページを作成する。

**【Notionページ構成案】**

1. **Header**: ✈️ {Destination} 家族旅行プラン案
2. **Callout (概要)**: AIによるプランの推奨理由サマリー。
3. **Heading 2**: 📅 狙い目の時期と相場（JAL想定）
4. **Table Block**:
* | 時期 | JAL相場(目安) | メリット | デメリット |


5. **Heading 2**: 🏨 「{こだわり}」を満たす宿 3選
6. **Bulleted List**: 宿ごとの詳細・URL・AIの推薦コメント

---

## 4. 技術スタック選定 (Tech Stack)

達人を目指すための「堅牢」かつ「拡張可能」な構成です。

| レイヤー | 技術/ツール | 選定理由 |
| --- | --- | --- |
| **Language** | **Python 3.11+** | エージェント開発のデファクトスタンダード。型ヒントを活用して堅牢に書く。 |
| **LLM** | **Google Gemini 2.5-flash** | 高速かつ低コスト。`langchain-google-genai`経由で使用。Scheduler Agentと統一。 |
| **Web Search** | **Tavily API** | AIエージェント専用検索API。不要なHTMLタグを除去した綺麗なコンテキストを返してくれるため、解析精度が高い。 |
| **Database** | **Notion API** | `notion-client` ライブラリを使用。情報のストックに最適。 |
| **Environment** | `.env` | APIキー管理（セキュリティ必須）。 |

---

## 5. 実装ステップ (Roadmap)

いきなり全部書くとバグの特定が困難になります。以下の順で進めましょう。

1. **Step 1 (Console Chat)**:
* `Interviewer` モジュールを作成。コンソール上でAIと会話して、JSONが完成したら終了するループを作る。


2. **Step 2 (Search Logic)**:
* `Researcher` モジュールを作成。固定のJSONを渡して、Tavilyで検索し、結果をテキストで返す部分を作る。


3. **Step 3 (Notion Connect)**:
* `Publisher` モジュールを作成。固定のテキストデータをNotionに書き込むテストをする。


4. **Step 4 (Integration)**:
* 全てを繋ぎこむ。