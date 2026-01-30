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
    ActivityInfo,
    Phase,
    ResearchResult,
    TimingInfo,
    TravelConciergeState,
    TravelContext,
    Travelers,
    TripType,
)
from agents.travel_concierge.tools import (
    create_notion_page,
    search_accommodations,
    search_activities,
    search_day_trip_info,
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


class PlannerOutput(BaseModel):
    """Plannerノードの出力スキーマ."""

    travel_context: TravelContextOutput = Field(
        ..., description="収集した旅行コンテキスト"
    )
    is_ready_for_research: bool = Field(
        ..., description="詳細調査の準備ができたかどうか"
    )
    recommended_trip_type: str | None = Field(
        default=None, description="推奨する旅行タイプ（day_trip または overnight）"
    )
    recommendation_reason: str | None = Field(
        default=None, description="旅行タイプを推奨する理由"
    )
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


class ActivityOutput(BaseModel):
    """アクティビティ・スポットの出力スキーマ（日帰り用）."""

    name: str = Field(..., description="スポット名・アクティビティ名")
    url: str | None = Field(default=None, description="URL")
    features: list[str] = Field(default_factory=list, description="特徴・楽しめること")
    access: str | None = Field(default=None, description="アクセス情報")
    price_hint: str | None = Field(default=None, description="料金目安")
    recommendation: str | None = Field(default=None, description="AIの推薦コメント")


class ResearcherOutput(BaseModel):
    """リサーチノードの出力スキーマ（宿泊旅行用）."""

    timing_options: list[TimingOptionOutput] = Field(
        default_factory=list, description="時期・相場オプション"
    )
    accommodations: list[AccommodationOutput] = Field(
        default_factory=list, description="宿泊施設リスト（最大3件）"
    )
    summary: str = Field(..., description="調査結果のサマリー（2-3文）")


class DayTripResearcherOutput(BaseModel):
    """日帰りリサーチノードの出力スキーマ."""

    timing_options: list[TimingOptionOutput] = Field(
        default_factory=list, description="おすすめ時期・季節オプション"
    )
    activities: list[ActivityOutput] = Field(
        default_factory=list, description="おすすめスポット・アクティビティ（最大3件）"
    )
    summary: str = Field(..., description="調査結果のサマリー（2-3文）")


# ========================================
# システムプロンプト
# ========================================


PLANNER_SYSTEM_PROMPT = """あなたは旅行プランナーAIです。
ユーザーの旅行願望をヒアリングし、最適な旅行プランを提案します。

## 役割
1. ユーザーの希望をヒアリングする
2. 日帰り/宿泊のどちらが適切かを判断・提案する
3. ユーザーの承認を得てから詳細調査に移る

## 収集する情報
1. destination（目的地）- 具体的な地名が必要
2. timing（時期）- 曖昧でOK（例: GWあたり、夏休み、週末）
3. travelers（人数構成）- 大人・子供の人数、**子供がいる場合は年齢も確認**
4. constraints（こだわり条件）- 体験したいこと、食べたいもの等

## 日帰り/宿泊の判断基準

### 重要な注意
- 「宿泊施設がある場所」≠「泊まりたい」：ユーザーが「宿泊施設がある場所」と言っても、
  それは選択肢として存在することを求めているだけで、実際に泊まりたいとは限らない
- **ユーザーが明確に「泊まりたい」「一泊したい」と言っていない限り、宿泊を前提としない**
- 不明な場合は必ず確認する：「日帰りと宿泊、どちらをお考えですか？」

### 日帰り（day_trip）を推奨するケース
- ユーザーが「日帰り」と明言している
- 目的地がユーザーの居住地から片道2時間以内
- 小さい子供（0-3歳）がいる（長距離移動が大変）
- 特定のアクティビティ・スポットを楽しむのが主目的
- 「近場」「週末にサクッと」などの表現がある

### 宿泊（overnight）を推奨するケース
- ユーザーが**明確に**「泊まりたい」「一泊」「旅館」「ホテルに泊まる」と言っている
- 目的地が遠方（北海道、沖縄、東北など）で日帰りが現実的でない
- 「ゆっくり」「のんびり」「温泉旅行」など宿泊を示唆する希望がある
- 複数日かけて回りたいエリア

### どちらか不明な場合
- recommended_trip_type = null のまま
- ユーザーに直接確認する：「日帰りと宿泊、どちらをイメージされていますか？」

## プラン提案の流れ
1. まず必要な情報を収集（目的地、時期、人数）
2. 日帰り/宿泊の希望が不明確な場合は、**先に確認する**
3. 情報が揃い、日帰り/宿泊が決まったら、確認して同意を得る
4. ユーザーが同意したら is_ready_for_research = true

## 注意点
- 親しみやすく、カジュアルな口調で会話
- 一度に複数の質問をせず、1つずつ確認
- 子供の年齢は必ず確認（「5歳と2歳」のように具体的に）
- 目的地が曖昧な場合は、エリアや希望を聞いて候補を提案
- **ユーザーがプランに同意するまでは is_ready_for_research = false**
- constraintsは任意なので、特になければ空配列でOK
- **日帰り/宿泊が明確でない場合は勝手に決めず、必ず確認する**
- 「宿泊施設がある」は条件であって希望ではない点に注意"""

RESEARCHER_SYSTEM_PROMPT = """あなたは旅行リサーチャーAIです。
Web検索結果から宿泊旅行に役立つ情報を抽出・整理します。

## 注意点
- 検索結果から確実に読み取れる情報のみを記載
- 価格は目安として幅を持たせて記載
- 宿は最大3件まで厳選
- サマリーは2-3文で簡潔に"""

DAYTRIP_RESEARCHER_SYSTEM_PROMPT = """あなたは日帰り旅行リサーチャーAIです。
Web検索結果から日帰りお出かけに役立つ情報を抽出・整理します。

## 重要
これは**日帰り旅行**です。宿泊施設の情報は不要です。

## 出力内容
1. おすすめの時期・季節（timing_options）
   - 各季節のメリット・デメリット
   - 混雑状況や気候の情報
   - 料金は日帰りの交通費・入場料・食事等の目安
2. おすすめスポット・アクティビティ（activities）
   - 具体的な施設名・スポット名
   - 体験できること・楽しめること
   - アクセス情報（最寄り駅、車での所要時間など）
   - 料金の目安（入場料、体験料など）
   - 子連れ・ファミリー向けの情報があれば記載

## 注意点
- 検索結果から確実に読み取れる情報のみを記載
- 価格は目安として幅を持たせて記載
- スポットは最大3件まで厳選
- サマリーは2-3文で簡潔に、日帰りで楽しめるポイントを強調"""


# ========================================
# ノード関数
# ========================================


def plan_trip(state: TravelConciergeState) -> dict:
    """旅行プランを立てるノード（Planner）.

    会話履歴を解析し、旅行タイプ（日帰り/宿泊）を判断・提案。
    ユーザーの承認を得てからリサーチに移行する。

    Args:
        state: 現在の状態

    Returns:
        dict: 更新する状態の差分
    """
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7)
    structured_llm = llm.with_structured_output(PlannerOutput)

    # 会話履歴を整形
    conversation_history = ""
    for msg in state.messages:
        role = "ユーザー" if msg["role"] == "user" else "AI"
        conversation_history += f"{role}: {msg['content']}\n"

    # 現在のコンテキストも含める
    current_context = state.travel_context.model_dump_json(indent=2)

    # 現在の旅行タイプ提案状態
    current_trip_type = state.trip_type.value if state.trip_type else "未決定"
    current_recommendation = state.planner_recommendation or "なし"

    user_message = f"""## 現在の旅行コンテキスト
{current_context}

## 現在の旅行タイプ提案
- 提案タイプ: {current_trip_type}
- 提案理由: {current_recommendation}

## 会話履歴
{conversation_history}

上記の情報を分析し、旅行コンテキストを更新してください。
必要な情報が揃ったら、日帰り/宿泊のどちらが良いか提案し、ユーザーの同意を得てください。
ユーザーがプランに同意したら is_ready_for_research = true にしてください。"""

    messages = [
        SystemMessage(content=PLANNER_SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ]

    try:
        logger.info("Starting planner LLM call")
        result: PlannerOutput = structured_llm.invoke(messages)
        logger.info(
            f"Planner result: is_ready={result.is_ready_for_research}, "
            f"trip_type={result.recommended_trip_type}, "
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

        # 旅行タイプを更新
        trip_type = None
        if result.recommended_trip_type:
            if result.recommended_trip_type == "day_trip":
                trip_type = TripType.DAY_TRIP
            elif result.recommended_trip_type == "overnight":
                trip_type = TripType.OVERNIGHT

        # フェーズを更新
        new_phase = (
            Phase.RESEARCHING if result.is_ready_for_research else Phase.PLANNING
        )

        return {
            "travel_context": travel_context,
            "trip_type": trip_type,
            "planner_recommendation": result.recommendation_reason,
            "phase": new_phase,
            "response_text": result.response_to_user,
            "messages": [{"role": "assistant", "content": result.response_to_user}],
        }

    except Exception as e:
        return {
            "error_message": f"プランニング処理でエラーが発生しました: {e}",
            "response_text": (
                "すみません、うまく処理できませんでした。もう一度お話しいただけますか？"
            ),
        }


def research_travel(state: TravelConciergeState) -> dict:
    """旅行情報をリサーチするノード.

    trip_typeに基づいて日帰り/宿泊の適切な検索を実行。

    Args:
        state: 現在の状態

    Returns:
        dict: 更新する状態の差分
    """
    if state.error_message:
        return {}

    context = state.travel_context
    is_day_trip_mode = state.trip_type == TripType.DAY_TRIP

    logger.info(f"Research mode: {'日帰り' if is_day_trip_mode else '宿泊'}")

    try:
        travelers_info = ""
        if context.travelers:
            travelers_info = f"大人{context.travelers.adults}名"
            if context.travelers.children > 0:
                travelers_info += f"、子供{context.travelers.children}名"
            if context.travelers.notes:
                travelers_info += f"（{context.travelers.notes}）"

        if is_day_trip_mode:
            # 日帰りモード
            return _research_day_trip(context, travelers_info)
        else:
            # 宿泊モード
            return _research_overnight(context, travelers_info)

    except Exception as e:
        return {
            "error_message": f"リサーチ中にエラーが発生しました: {e}",
            "phase": Phase.COMPLETED,
        }


def _research_day_trip(context: TravelContext, travelers_info: str) -> dict:
    """日帰り旅行のリサーチを実行.

    Args:
        context: 旅行要件コンテキスト
        travelers_info: 人数情報テキスト

    Returns:
        dict: 更新する状態の差分
    """
    # Step 1: 日帰り基本情報
    logger.info(f"Starting day trip info search for: {context.destination}")
    day_trip_results = search_day_trip_info(context)
    logger.info("Day trip info search completed")

    # Step 2: アクティビティ・スポット検索
    logger.info("Starting activities search")
    activity_results = search_activities(context)
    logger.info("Activities search completed")

    # 検索結果をLLMで整理（日帰り用スキーマ）
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.3)
    structured_llm = llm.with_structured_output(DayTripResearcherOutput)

    search_data = f"""## 日帰り旅行条件
- 目的地: {context.destination}
- 時期: {context.timing}
- 人数: {travelers_info}
- やりたいこと: {", ".join(context.constraints) if context.constraints else "なし"}

## 日帰り基本情報（アクセス・時期等）
{json.dumps(day_trip_results, ensure_ascii=False, indent=2)}

## アクティビティ・スポット検索結果
{json.dumps(activity_results, ensure_ascii=False, indent=2)}

上記の検索結果を分析し、日帰り旅行プランに役立つ情報を整理してください。"""

    messages = [
        SystemMessage(content=DAYTRIP_RESEARCHER_SYSTEM_PROMPT),
        HumanMessage(content=search_data),
    ]

    logger.info("Starting LLM analysis of day trip results")
    result: DayTripResearcherOutput = structured_llm.invoke(messages)
    logger.info("LLM analysis completed")

    # ResearchResultを構築（日帰り用）
    timing_options = [
        TimingInfo(
            period=t.period,
            price_estimate=t.price_estimate,
            advantages=t.advantages,
            disadvantages=t.disadvantages,
        )
        for t in result.timing_options
    ]
    activities = [
        ActivityInfo(
            name=a.name,
            url=a.url,
            features=a.features,
            access=a.access,
            price_hint=a.price_hint,
            recommendation=a.recommendation,
        )
        for a in result.activities
    ]

    research_result = ResearchResult(
        timing_options=timing_options,
        activities=activities,
        is_day_trip=True,
        summary=result.summary,
    )

    return {
        "research_result": research_result,
        "phase": Phase.PUBLISHING,
        "response_text": "リサーチが完了しました！Notionに記事を作成しています...",
    }


def _research_overnight(context: TravelContext, travelers_info: str) -> dict:
    """宿泊旅行のリサーチを実行.

    Args:
        context: 旅行要件コンテキスト
        travelers_info: 人数情報テキスト

    Returns:
        dict: 更新する状態の差分
    """
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

    # 検索結果をLLMで整理（宿泊用スキーマ）
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.3)
    structured_llm = llm.with_structured_output(ResearcherOutput)

    search_data = f"""## 宿泊旅行条件
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

    logger.info("Starting LLM analysis of overnight results")
    result: ResearcherOutput = structured_llm.invoke(messages)
    logger.info("LLM analysis completed")

    # ResearchResultを構築（宿泊用）
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
        is_day_trip=False,
        summary=result.summary,
    )

    return {
        "research_result": research_result,
        "phase": Phase.PUBLISHING,
        "response_text": "リサーチが完了しました！Notionに記事を作成しています...",
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
        # 旅行タイプに応じたタイトル
        is_day_trip = state.trip_type == TripType.DAY_TRIP
        if is_day_trip:
            title = f"🚗 {state.travel_context.destination} 日帰りお出かけプラン"
        else:
            title = f"✈️ {state.travel_context.destination} 旅行プラン案"

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
        case Phase.PLANNING:
            return "planner"
        case Phase.RESEARCHING:
            return "research"
        case Phase.PUBLISHING:
            return "publish"
        case Phase.COMPLETED:
            return "end"
        case _:
            return "end"
