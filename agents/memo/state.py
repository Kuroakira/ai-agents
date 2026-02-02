"""Memoエージェントの状態スキーマ.

入力、中間処理結果、出力の状態を管理するPydanticモデル。
"""

from typing import Literal

from pydantic import BaseModel, Field


class MemoState(BaseModel):
    """Memoエージェントの状態.

    Attributes:
        input_text: ユーザーからの生入力テキスト
        existing_tags: Notionから取得した既存タグ一覧
        source_type: 入力元タイプ（kindle: Kindle共有, thought: 通常の思考）
        parsed_result: LLMによる解析結果
        candidate_tags: LLMが生成したタグ候補
        final_tags: 類似判定後の最終タグ
        notion_url: 作成されたNotionページのURL
        status: 処理ステータス
        error_message: エラーメッセージ（失敗時のみ）
    """

    # Input
    input_text: str = Field(description="ユーザーからの生入力テキスト")

    # Context (fetched from Notion)
    existing_tags: list[str] = Field(
        default_factory=list, description="Notionから取得した既存タグ一覧"
    )

    # Intermediate
    source_type: Literal["kindle", "thought"] | None = Field(
        default=None, description="入力元タイプ"
    )
    parsed_result: dict | None = Field(
        default=None, description="LLMによる解析結果（MemoItem形式）"
    )
    candidate_tags: list[str] = Field(
        default_factory=list, description="LLMが生成したタグ候補"
    )
    final_tags: list[str] = Field(
        default_factory=list, description="類似判定後の最終タグ"
    )

    # Output
    notion_url: str | None = Field(
        default=None, description="作成されたNotionページのURL"
    )

    # Control
    status: Literal[
        "pending", "fetching", "parsing", "matching", "saving", "completed", "failed"
    ] = Field(default="pending", description="処理ステータス")
    error_message: str | None = Field(
        default=None, description="エラーメッセージ（失敗時のみ）"
    )
