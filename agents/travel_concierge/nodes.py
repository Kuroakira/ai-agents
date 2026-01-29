"""ノード関数定義.

LangGraphワークフローの各処理ステップを実装。
"""

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from agents.travel_concierge.state import (
    AccommodationInfo,
    Phase,
    ResearchResult,
    TimingInfo,
    TravelConciergeState,
    TravelContext,
    Travelers,
)
from agents.travel_concierge.tools import (
    create_notion_page,
    search_accommodations,
    search_flight_prices,
    search_timing_trends,
)

# ========================================
# 構造化出力用のスキーマ
# ========================================


class TravelersOutput(BaseModel):
    """旅行者構成の出力スキーマ."""

    adults: int = Field(default=0, description="大人の人数")
    children: int = Field(default=0, description="子供の人数")
    notes: str | None = Field(default=None, description="備考（例: 5歳と2歳）")


class TravelContextOutput(BaseModel):
    """旅行コンテキストの出力スキーマ."""

    destination: str | None = Field(default=None, description="目的地")
    timing: str | None = Field(default=None, description="時期（曖昧でOK）")
    travelers: TravelersOutput | None = Field(default=None, description="人数構成")
    constraints: list[str] = Field(default_factory=list, description="こだわり条件")


class InterviewerOutput(BaseModel):
    """インタビューノードの出力スキーマ."""

    travel_context: TravelContextOutput = Field(
        ..., description="収集した旅行コンテキスト"
    )
    is_complete: bool = Field(..., description="必須情報がすべて揃ったかどうか")
    response_to_user: str = Field(..., description="ユーザーへの返答メッセージ")


class TimingOptionOutput(BaseModel):
    """時期オプションの出力スキーマ."""

    period: str = Field(..., description="時期（例: 4月中旬）")
    price_estimate: str = Field(..., description="価格目安（例: ¥20,000〜）")
    advantages: list[str] = Field(default_factory=list, description="メリット")
    disadvantages: list[str] = Field(default_factory=list, description="デメリット")


class AccommodationOutput(BaseModel):
    """宿泊施設の出力スキーマ."""

    name: str = Field(..., description="宿名")
    url: str | None = Field(default=None, description="URL")
    features: list[str] = Field(default_factory=list, description="特徴")
    recommendation: str | None = Field(default=None, description="AIの推薦コメント")


class ResearcherOutput(BaseModel):
    """リサーチノードの出力スキーマ."""

    timing_options: list[TimingOptionOutput] = Field(
        default_factory=list, description="時期・相場オプション"
    )
    accommodations: list[AccommodationOutput] = Field(
        default_factory=list, description="宿泊施設リスト（最大3件）"
    )
    summary: str = Field(..., description="調査結果のサマリー（2-3文）")


# ========================================
# システムプロンプト
# ========================================


INTERVIEWER_SYSTEM_PROMPT = """あなたは旅行コンシェルジュAIです。
ユーザーの旅行願望をヒアリングし、必要な情報を収集します。

## 役割
ユーザーとの自然な会話を通じて、以下の情報を収集してください：
1. destination（目的地）- 具体的な地名が必要
2. timing（時期）- 曖昧でOK（例: GWあたり、夏休み、週末）
3. travelers（人数構成）- 大人・子供の人数
4. constraints（こだわり条件）- 和室、布団、カニ料理など

## 重要な注意点

### 目的地について
- 「体験型スポットを探している」「おすすめを教えて」など、目的地が決まっていない場合：
  - まずエリア（関東、東京近郊、車で2時間以内など）を確認する
  - やりたいこと・体験の種類を具体化する
  - その上で、具体的な目的地の候補（例：群馬の鍾乳洞、栃木の牧場など）を1-2個提案し、ユーザーに選んでもらう
  - ユーザーが具体的な場所を選ぶまでは is_complete を false にする

### 日帰りの場合
- 「日帰り」と言われた場合は、timing に「日帰り」または「週末日帰り」と設定してOK

## その他の注意点
- 親しみやすく、カジュアルな口調で会話してください
- 一度に複数の質問をせず、1つずつ確認してください
- **具体的な目的地（地名）が確定するまでは is_complete を true にしないでください**
- constraintsは任意なので、特になければ空配列でOKです"""

RESEARCHER_SYSTEM_PROMPT = """あなたは旅行リサーチャーAIです。
Web検索結果から旅行に役立つ情報を抽出・整理します。

## 注意点
- 検索結果から確実に読み取れる情報のみを記載
- 価格は目安として幅を持たせて記載
- 宿は最大3件まで厳選
- サマリーは2-3文で簡潔に"""


# ========================================
# ノード関数
# ========================================


def interview_user(state: TravelConciergeState) -> dict:
    """ユーザーをインタビューするノード.

    会話履歴を解析し、TravelContextを更新。
    不足項目があれば質問を生成する。

    Args:
        state: 現在の状態

    Returns:
        dict: 更新する状態の差分
    """
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7)
    structured_llm = llm.with_structured_output(InterviewerOutput)

    # 会話履歴を整形
    conversation_history = ""
    for msg in state.messages:
        role = "ユーザー" if msg["role"] == "user" else "AI"
        conversation_history += f"{role}: {msg['content']}\n"

    # 現在のコンテキストも含める
    current_context = state.travel_context.model_dump_json(indent=2)

    user_message = f"""## 現在の旅行コンテキスト
{current_context}

## 会話履歴
{conversation_history}

上記の情報を分析し、旅行コンテキストを更新してください。
不足している情報があれば、ユーザーに質問してください。"""

    messages = [
        SystemMessage(content=INTERVIEWER_SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ]

    try:
        logger.info("Starting interview LLM call")
        result: InterviewerOutput = structured_llm.invoke(messages)
        logger.info(
            f"Interview result: is_complete={result.is_complete}, "
            f"destination={result.travel_context.destination}"
        )

        # TravelContextを更新
        ctx = result.travel_context
        travelers = None
        if ctx.travelers:
            travelers = Travelers(
                adults=ctx.travelers.adults,
                children=ctx.travelers.children,
                notes=ctx.travelers.notes,
            )

        travel_context = TravelContext(
            destination=ctx.destination,
            timing=ctx.timing,
            travelers=travelers,
            constraints=ctx.constraints,
        )

        # フェーズを更新
        new_phase = Phase.RESEARCHING if result.is_complete else Phase.INTERVIEWING

        return {
            "travel_context": travel_context,
            "phase": new_phase,
            "response_text": result.response_to_user,
            "messages": [{"role": "assistant", "content": result.response_to_user}],
        }

    except Exception as e:
        return {
            "error_message": f"インタビュー処理でエラーが発生しました: {e}",
            "response_text": (
                "すみません、うまく処理できませんでした。もう一度お話しいただけますか？"
            ),
        }


def research_travel(state: TravelConciergeState) -> dict:
    """旅行情報をリサーチするノード.

    Tavily APIを使用してWeb検索を実行し、結果を整理する。

    Args:
        state: 現在の状態

    Returns:
        dict: 更新する状態の差分
    """
    if state.error_message:
        return {}

    context = state.travel_context

    try:
        # Step 1: 時期トレンド調査
        logger.info(f"Starting timing trends search for: {context.destination}")
        timing_results = search_timing_trends(context)
        logger.info("Timing trends search completed")

        # Step 2: フライト価格調査
        logger.info("Starting flight prices search")
        flight_results = search_flight_prices(context)
        logger.info("Flight prices search completed")

        # Step 3: 宿泊施設調査
        logger.info("Starting accommodations search")
        accommodation_results = search_accommodations(context)
        logger.info("Accommodations search completed")

        # 検索結果をLLMで整理（構造化出力）
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.3)
        structured_llm = llm.with_structured_output(ResearcherOutput)

        travelers_info = ""
        if context.travelers:
            travelers_info = f"大人{context.travelers.adults}名"
            if context.travelers.children > 0:
                travelers_info += f"、子供{context.travelers.children}名"

        search_data = f"""## 旅行条件
- 目的地: {context.destination}
- 時期: {context.timing}
- 人数: {travelers_info}
- こだわり: {", ".join(context.constraints) if context.constraints else "なし"}

## 時期トレンド検索結果
{json.dumps(timing_results, ensure_ascii=False, indent=2)}

## フライト価格検索結果
{json.dumps(flight_results, ensure_ascii=False, indent=2)}

## 宿泊施設検索結果
{json.dumps(accommodation_results, ensure_ascii=False, indent=2)}

上記の検索結果を分析し、旅行プランに役立つ情報を整理してください。"""

        messages = [
            SystemMessage(content=RESEARCHER_SYSTEM_PROMPT),
            HumanMessage(content=search_data),
        ]

        logger.info("Starting LLM analysis of search results")
        result: ResearcherOutput = structured_llm.invoke(messages)
        logger.info("LLM analysis completed")

        # ResearchResultを構築
        timing_options = [
            TimingInfo(
                period=t.period,
                price_estimate=t.price_estimate,
                advantages=t.advantages,
                disadvantages=t.disadvantages,
            )
            for t in result.timing_options
        ]
        accommodations = [
            AccommodationInfo(
                name=a.name,
                url=a.url,
                features=a.features,
                recommendation=a.recommendation,
            )
            for a in result.accommodations
        ]

        research_result = ResearchResult(
            timing_options=timing_options,
            accommodations=accommodations,
            summary=result.summary,
        )

        return {
            "research_result": research_result,
            "phase": Phase.PUBLISHING,
            "response_text": "リサーチが完了しました！Notionに記事を作成しています...",
        }

    except Exception as e:
        return {
            "error_message": f"リサーチ中にエラーが発生しました: {e}",
            "phase": Phase.COMPLETED,
        }


def publish_to_notion(state: TravelConciergeState) -> dict:
    """Notionにページを作成するノード.

    調査結果をNotionデータベースに記事として出力する。

    Args:
        state: 現在の状態

    Returns:
        dict: 更新する状態の差分
    """
    if state.error_message or not state.research_result:
        return {"phase": Phase.COMPLETED}

    try:
        title = f"✈️ {state.travel_context.destination} 家族旅行プラン案"

        page_url = create_notion_page(
            title=title,
            context=state.travel_context,
            research=state.research_result,
        )

        response_text = f"""🎉 旅行プランをNotionに作成しました！

📝 {title}

🔗 {page_url}

ご質問があればお気軽にどうぞ！"""

        return {
            "notion_page_url": page_url,
            "phase": Phase.COMPLETED,
            "response_text": response_text,
        }

    except Exception as e:
        return {
            "error_message": f"Notionへの出力中にエラーが発生しました: {e}",
            "phase": Phase.COMPLETED,
            "response_text": f"⚠️ Notionへの出力に失敗しました: {e}",
        }


def route_by_phase(state: TravelConciergeState) -> str:
    """フェーズに基づいて次のノードを決定.

    Args:
        state: 現在の状態

    Returns:
        str: 次のノード名
    """
    if state.error_message:
        return "end"

    match state.phase:
        case Phase.INTERVIEWING:
            return "interview"
        case Phase.RESEARCHING:
            return "research"
        case Phase.PUBLISHING:
            return "publish"
        case Phase.COMPLETED:
            return "end"
        case _:
            return "end"
