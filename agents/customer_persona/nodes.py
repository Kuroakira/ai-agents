"""Node functions for customer persona feedback agent."""

from functools import lru_cache

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from .state import AgentState, PersonaFeedback, ReviewResult


@lru_cache(maxsize=1)
def get_llm() -> ChatGoogleGenerativeAI:
    """LLMインスタンスを遅延初期化で取得する."""
    return ChatGoogleGenerativeAI(model="gemini-2.0-flash")


async def generate_feedback(state: AgentState) -> dict:
    """ペルソナになりきって顧客視点でフィードバックを生成する.

    Args:
        state: 現在のエージェント状態

    Returns:
        更新された状態の部分辞書
    """
    # 履歴がある場合は参考情報として含める
    history_context = ""
    if state.feedback_history:
        history_context = "\n\n過去のフィードバック（改善が必要と判断されたもの）:\n"
        for i, fb in enumerate(state.feedback_history, 1):
            history_context += f"{i}. {fb.feedback[:200]}...\n"
        history_context += (
            "\n上記の問題点を踏まえ、より適切なフィードバックを生成してください。"
        )

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            """あなたは以下のペルソナになりきって、提示されたアイデアに対してフィードバックを提供します。

## ペルソナ設定
{persona_description}

## 重要な指示
- 完全にこのペルソナの視点・価値観・知識レベルで考えてください
- このペルソナが実際に持つであろう疑問、懸念、期待を表現してください
- 専門用語はペルソナの知識レベルに合わせて使用してください
- 感情的な反応も含めて、リアルな顧客の声を再現してください
{history_context}"""
        ),
        (
            "human",
            """以下のアイデア・コンセプトについて、あなた（ペルソナ）の視点でフィードバックをください。

## アイデア
{idea}

以下の形式でJSON形式で回答してください:
{{
    "feedback": "全体的なフィードバック（ペルソナの言葉で）",
    "concerns": ["懸念点1", "懸念点2", ...],
    "interests": ["興味を持った点1", "興味を持った点2", ...],
    "suggestions": ["こうしてほしい1", "こうしてほしい2", ...]
}}"""
        ),
    ])

    structured_llm = get_llm().with_structured_output(PersonaFeedback)
    chain = prompt | structured_llm

    feedback = await chain.ainvoke({
        "persona_description": state.persona_description,
        "idea": state.idea,
        "history_context": history_context,
    })

    return {
        "feedback": feedback,
        "status": "reviewing",
        "iteration": state.iteration + 1,
    }


async def review_feedback(state: AgentState) -> dict:
    """生成されたフィードバックの品質をチェックする.

    Args:
        state: 現在のエージェント状態

    Returns:
        更新された状態の部分辞書
    """
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            """あなたはフィードバックの品質を評価するレビュアーです。
以下の観点でフィードバックを評価してください:

1. ペルソナ一貫性: フィードバックがペルソナ設定と一致しているか
2. 具体性: 抽象的すぎず、具体的な指摘があるか
3. 建設性: 批判だけでなく、建設的な内容が含まれているか
4. リアリティ: 実際の顧客が言いそうな内容か
5. 網羅性: アイデアの重要な側面に触れているか

スコア基準:
- 1-3: 不適切（再生成が必要）
- 4-6: 改善の余地あり
- 7-10: 適切"""
        ),
        (
            "human",
            """## ペルソナ設定
{persona_description}

## 評価対象のアイデア
{idea}

## 生成されたフィードバック
{feedback}

## 懸念点
{concerns}

## 興味を持った点
{interests}

## 提案
{suggestions}

このフィードバックの品質を評価してください。
JSON形式で回答:
{{
    "is_appropriate": true/false（スコア7以上ならtrue）,
    "score": 1-10の整数,
    "issues": ["問題点1", "問題点2", ...],
    "reasoning": "判断理由"
}}"""
        ),
    ])

    structured_llm = get_llm().with_structured_output(ReviewResult)
    chain = prompt | structured_llm

    review = await chain.ainvoke({
        "persona_description": state.persona_description,
        "idea": state.idea,
        "feedback": state.feedback.feedback,
        "concerns": "\n".join(f"- {c}" for c in state.feedback.concerns),
        "interests": "\n".join(f"- {i}" for i in state.feedback.interests),
        "suggestions": "\n".join(f"- {s}" for s in state.feedback.suggestions),
    })

    # 不適切な場合は履歴に追加
    new_history = state.feedback_history.copy()
    if not review.is_appropriate and state.feedback:
        new_history.append(state.feedback)

    return {
        "review": review,
        "feedback_history": new_history,
    }


def should_regenerate(state: AgentState) -> str:
    """再生成が必要かどうかを判定する.

    Args:
        state: 現在のエージェント状態

    Returns:
        次のノード名 ("regenerate" or "complete")
    """
    # 最大回数に達した場合は終了
    if state.iteration >= state.max_iterations:
        return "complete"

    # レビュー結果が適切なら終了
    if state.review and state.review.is_appropriate:
        return "complete"

    # それ以外は再生成
    return "regenerate"


def finalize(state: AgentState) -> dict:
    """最終状態を設定する.

    Args:
        state: 現在のエージェント状態

    Returns:
        更新された状態の部分辞書
    """
    # レビューが適切、または最大回数に達した場合
    if state.review and state.review.is_appropriate:
        return {"status": "completed"}
    else:
        return {"status": "failed"}
