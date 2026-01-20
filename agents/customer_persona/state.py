"""State schema for customer persona feedback agent."""

from typing import Literal

from pydantic import BaseModel, Field


class PersonaFeedback(BaseModel):
    """顧客ペルソナからのフィードバック."""

    feedback: str = Field(description="ペルソナ視点でのフィードバック")
    concerns: list[str] = Field(default_factory=list, description="懸念点・疑問点")
    interests: list[str] = Field(default_factory=list, description="興味を持った点")
    suggestions: list[str] = Field(default_factory=list, description="改善提案")


class ReviewResult(BaseModel):
    """レビュー結果."""

    is_appropriate: bool = Field(description="フィードバックが適切かどうか")
    score: int = Field(ge=1, le=10, description="フィードバック品質スコア (1-10)")
    issues: list[str] = Field(default_factory=list, description="問題点")
    reasoning: str = Field(description="判断理由")


class AgentState(BaseModel):
    """エージェントの状態."""

    # 入力
    idea: str = Field(description="評価対象のアイデア・コンセプト")
    persona_description: str = Field(description="ペルソナの説明（自由テキスト）")

    # 中間結果
    feedback: PersonaFeedback | None = Field(
        default=None, description="生成されたフィードバック"
    )
    review: ReviewResult | None = Field(default=None, description="レビュー結果")

    # 制御
    iteration: int = Field(default=0, description="再生成回数")
    max_iterations: int = Field(default=3, description="最大再生成回数")
    status: Literal[
        "pending", "generating", "reviewing", "completed", "failed"
    ] = Field(
        default="pending", description="処理状態"
    )

    # 履歴（再生成時の参考用）
    feedback_history: list[PersonaFeedback] = Field(
        default_factory=list, description="過去のフィードバック履歴"
    )
