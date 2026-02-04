"""Memoエージェントのノード関数.

各処理ステップを実装するノード関数群。
"""

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from agents.memo.schema import MemoItem
from agents.memo.state import MemoState
from agents.memo.tools import (
    create_memo_page,
    get_existing_tags,
    match_tags,
)


def get_llm() -> ChatGoogleGenerativeAI:
    """LLMインスタンスを取得する.

    Note:
        asyncio.run()で毎回イベントループが作成・破棄されるため、
        キャッシュせずに毎回新しいインスタンスを生成する。

    Returns:
        ChatGoogleGenerativeAI: Gemini 2.5 Flashモデル
    """
    return ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2)


def fetch_tags_node(state: MemoState) -> dict:
    """Notionから既存タグを取得.

    Args:
        state: 現在のエージェント状態

    Returns:
        更新された状態の部分辞書
    """
    try:
        existing_tags = get_existing_tags()
        return {
            "status": "parsing",
            "existing_tags": existing_tags,
        }
    except Exception as e:
        # タグ取得に失敗しても処理は続行（空リストで進める）
        return {
            "status": "parsing",
            "existing_tags": [],
            "error_message": f"既存タグ取得警告: {e}",
        }


PARSER_SYSTEM_PROMPT = """あなたはメモ解析アシスタントです。
ユーザーからのテキスト入力を分析し、構造化されたメモデータに変換します。

入力パターンは2種類あります：

## 1. Kindle共有（is_kindle: true）
Kindleからのハイライト共有は通常以下の形式です：
- 引用文が含まれる
- 書籍タイトルと著者名が含まれる
- 「Kindleより」「ハイライト」などのキーワードが含まれることがある

Kindle共有の場合：
- content: 引用文のみを抽出
- source: 書籍名と著者名を「書籍名 / 著者名」の形式で記載

## 2. 通常の思考メモ（is_kindle: false）
ユーザーの思いつきやメモ：
- content: 入力テキスト全文を整理して記載
- source: 空文字

## タグの生成ルール
- 内容を表す具体的なタグを1〜3個生成
- 既存タグがある場合は、可能な限り既存タグを再利用
- 新しい概念の場合は新規タグを作成
- タグ名は具体的で検索しやすいものにする
- 例: 「AIエージェント」「組織構築」「LangGraph」「読書メモ」「リーダーシップ」

## topicの作成
- 30文字以内で内容を端的に表す
- 具体的で検索しやすい見出しにする
"""

PARSER_USER_PROMPT = """以下のテキストを解析し、構造化されたメモデータに変換してください。

{existing_tags_section}

入力テキスト:
{input_text}
"""  # noqa: E501


async def parser_node(state: MemoState) -> dict:
    """入力テキストを解析し、構造化データに変換.

    Gemini 2.5 Flashを使用して、ユーザー入力を解析し、
    適切なタグとコンテンツを抽出する。

    Args:
        state: 現在のエージェント状態

    Returns:
        更新された状態の部分辞書
    """
    if state.status == "failed":
        return {}

    llm = get_llm()
    structured_llm = llm.with_structured_output(MemoItem)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", PARSER_SYSTEM_PROMPT),
            ("human", PARSER_USER_PROMPT),
        ]
    )

    chain = prompt | structured_llm

    # 既存タグセクションを構築
    if state.existing_tags:
        existing_tags_section = (
            "既存のタグ一覧（可能な限りこれらを再利用してください）:\n"
            + ", ".join(state.existing_tags)
        )
    else:
        existing_tags_section = ""

    try:
        result: MemoItem = await chain.ainvoke(
            {
                "input_text": state.input_text,
                "existing_tags_section": existing_tags_section,
            }
        )
        return {
            "status": "matching",
            "source_type": "kindle" if result.is_kindle else "thought",
            "parsed_result": result.model_dump(),
            "candidate_tags": result.tags,
        }
    except Exception as e:
        return {
            "status": "failed",
            "error_message": f"テキスト解析エラー: {e}",
        }


def tag_matcher_node(state: MemoState) -> dict:
    """候補タグを既存タグとマッチング.

    類似タグがあれば既存のものを使用し、タグの一貫性を保つ。

    Args:
        state: 現在のエージェント状態

    Returns:
        更新された状態の部分辞書
    """
    if state.status == "failed":
        return {}

    final_tags = match_tags(state.candidate_tags, state.existing_tags)

    return {
        "status": "saving",
        "final_tags": final_tags,
    }


def saver_node(state: MemoState) -> dict:
    """解析結果をNotionに保存.

    Args:
        state: 現在のエージェント状態

    Returns:
        更新された状態の部分辞書
    """
    if state.status == "failed":
        return {}

    if not state.parsed_result:
        return {
            "status": "failed",
            "error_message": "解析結果がありません",
        }

    try:
        memo = MemoItem(**state.parsed_result)
        notion_url = create_memo_page(memo, state.final_tags)

        return {
            "status": "completed",
            "notion_url": notion_url,
        }
    except Exception as e:
        return {
            "status": "failed",
            "error_message": f"Notion保存エラー: {e}",
        }
