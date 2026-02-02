"""LLM構造化出力用スキーマ.

Gemini 2.5 Flashからの出力をバリデートするPydanticモデル。
"""

from pydantic import BaseModel, Field


class MemoItem(BaseModel):
    """メモアイテムの構造化スキーマ.

    LLMがユーザー入力を解析して生成する構造化データ。
    Notionデータベースへの保存に使用する。

    Attributes:
        topic: 30文字以内の要約タイトル
        tags: 内容を表すタグのリスト（1〜3個）
        content: 本文（Kindleなら引用文のみ、思考なら全文）
        source: 出典（書名・著者）。思考の場合は空文字
        is_kindle: Kindle共有からの入力かどうか
    """

    topic: str = Field(description="30文字以内の要約タイトル。内容を端的に表す見出し")
    tags: list[str] = Field(
        description=(
            "内容を表すタグのリスト。1〜3個。"
            "具体的で検索しやすい名前にする。"
            "例: 'AIエージェント', '組織構築', 'LangGraph', '読書メモ'"
        )
    )
    content: str = Field(
        description="本文。Kindleの場合は引用文のみ、思考メモの場合は全文を記載"
    )
    source: str = Field(
        default="",
        description="出典（書名・著者）。Kindle共有の場合のみ記載。思考メモの場合は空文字",
    )
    is_kindle: bool = Field(
        default=False,
        description=(
            "Kindle共有からの入力かどうか。True: Kindle共有, False: 通常の思考メモ"
        ),
    )
