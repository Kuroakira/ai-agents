"""ノード関数定義.

LangGraphワークフローの各処理ステップを実装。
"""

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from agents.travel_concierge.state import (
    AccommodationInfo,
    ActivityInfo,
    ModelCourse,
    ModelCourseStep,
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

logger = logging.getLogger(__name__)

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
    url: str = Field(..., description="公式サイトまたは予約サイトのURL（必須）")
    price_range: str = Field(
        ..., description="価格帯（必須。例: ¥15,000〜25,000/人・泊）"
    )
    price_category: str = Field(
        ..., description="価格カテゴリ（必須。budget/standard/premiumのいずれか）"
    )
    features: list[str] = Field(default_factory=list, description="特徴")
    recommendation: str | None = Field(default=None, description="AIの推薦コメント")


class ActivityOutput(BaseModel):
    """アクティビティ・スポットの出力スキーマ."""

    name: str = Field(..., description="スポット名・アクティビティ名")
    url: str = Field(..., description="公式サイトURL（必須）")
    features: list[str] = Field(
        ..., min_length=1, description="特徴・楽しめること（必須）"
    )
    access: str = Field(..., description="アクセス情報（必須）")
    price_hint: str = Field(
        ..., description="料金目安（必須。例: 大人¥1,800、子供¥900）"
    )
    recommendation: str = Field(..., description="AIの推薦コメント（必須）")
    special_point: str | None = Field(
        default=None, description="旅行者に合わせた特別ポイント（年齢別、シニア向け等）"
    )


class ModelCourseStepOutput(BaseModel):
    """モデルコースの1ステップ出力スキーマ."""

    time: str = Field(..., description="時間（例: 9:00）")
    title: str = Field(..., description="やること（例: 出発！）")
    description: str = Field(..., description="詳細説明・子供の楽しみポイント")
    tips: str | None = Field(default=None, description="親向けTips（駐車場、トイレ等）")


class ModelCourseOutput(BaseModel):
    """モデルコース出力スキーマ."""

    title: str = Field(
        ..., description="コースタイトル（例: わんぱくキッズ大満足コース）"
    )
    steps: list[ModelCourseStepOutput] = Field(
        ..., min_length=5, description="タイムライン（必須。5-10ステップ）"
    )
    total_budget: str = Field(
        ..., description="総予算目安（必須。例: 家族4人で約¥150,000〜200,000）"
    )


class ResearcherOutput(BaseModel):
    """リサーチノードの出力スキーマ（宿泊旅行用）."""

    timing_options: list[TimingOptionOutput] = Field(
        ...,
        min_length=2,
        description="時期・相場オプション（必須。安い時期、ベストシーズン等を2件以上）",
    )
    accommodations: list[AccommodationOutput] = Field(
        ...,
        min_length=3,
        description="宿泊施設リスト（必須。価格帯別に3〜5件）",
    )
    activities: list[ActivityOutput] = Field(
        ...,
        min_length=3,
        description="観光スポット・アクティビティ（必須。3〜5件、URL・料金付き）",
    )
    model_course: ModelCourseOutput = Field(
        ..., description="2日間のモデルコース（必須。Day1/Day2形式）"
    )
    summary: str = Field(..., description="旅行代理店の提案書の冒頭サマリー（3-4文）")


class DayTripResearcherOutput(BaseModel):
    """日帰りリサーチノードの出力スキーマ."""

    timing_options: list[TimingOptionOutput] = Field(
        default_factory=list, description="おすすめ時期・季節オプション"
    )
    activities: list[ActivityOutput] = Field(
        default_factory=list, description="おすすめスポット・アクティビティ（最大3件）"
    )
    model_course: ModelCourseOutput = Field(
        ..., description="おすすめモデルコース（タイムライン形式）"
    )
    summary: str = Field(..., description="ワクワクするサマリー（旅行雑誌風、3-4文）")


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
- 「宿泊施設がある」は条件であって希望ではない点に注意

## ★★★ 最重要：会話履歴から情報を抽出する ★★★
**ユーザーが既に言及した情報は絶対に再度聞かない！**

会話履歴を必ず確認し、以下の情報が既に言及されていれば travel_context に反映：
- 「沖縄」「北海道」など → destination に設定
- 「9歳と6歳」など → travelers.notes に設定
- 「家族4人」「大人2人」など → travelers.adults/children に設定
- 「和室」「美ら海水族館」など → constraints に設定
- 「安い時期」「GW」「夏休み」など → timing に設定（「安い時期」も有効な時期指定）

**例：ユーザーが「沖縄に行きたい」と言っていたら、絶対に「どちらの方面へ？」と聞かない**"""

RESEARCHER_SYSTEM_PROMPT = """あなたはJTBやHISのような旅行代理店のコンサルタントです。
検索結果から、**お客様が旅行を具体的に検討できる情報**を整理してください。

## あなたの役割
旅行代理店に相談に来たお客様に対して、以下を提供すること：
1. **お得な時期と相場感** - いつ行けば安いか、相場はどのくらいか
2. **宿泊施設の選択肢** - 価格帯別に複数の選択肢を提示
3. **観光スポット情報** - どこに行けば何ができるか
4. **おすすめプラン** - 上記を踏まえた具体的な旅程案

## 重要：情報の具体性
- **価格は必ず記載**: 「安い」ではなく「¥15,000〜20,000/人・泊」のように
- **URLは必ず記載**: 検索結果のURLを活用し、お客様が詳細を確認できるように
- **時期は具体的に**: 「オフシーズン」ではなく「1月中旬〜2月」のように

## 出力内容

### 1. サマリー（summary）
旅行代理店の提案書の冒頭のように：
- この旅行の魅力を簡潔に（3〜4文）
- お客様のご要望に沿った提案であることを示す
- 物語調よりも「〜がおすすめです」「〜をご提案します」調で

### 2. 狙い目の時期（timing_options）- 重要！
**価格と混雑を軸に整理**してください：
- **安い時期**: 「1月中旬〜2月は閑散期で最も安い。航空券+宿泊で¥XX,XXX〜」
- **混雑を避けられる時期**: 「GW直後の5月中旬は穴場」
- **ベストシーズン**: 「気候・海の透明度は6月がベストだが、価格は高め」
- メリット・デメリットを具体的に

### 3. おすすめ宿（accommodations）- 価格帯別に3〜5件
**★★★ 必須: 各宿泊施設に price_range と price_category を必ず設定 ★★★**

価格帯の分類基準：
- **budget**: ¥10,000以下/人・泊
- **standard**: ¥10,000〜20,000/人・泊
- **premium**: ¥20,000以上/人・泊

各宿泊施設に**必ず**以下を含める（省略不可）：
- **price_range**: 「¥12,000〜18,000/人・泊」のように具体的に（必須）
- **price_category**: 「budget」「standard」「premium」のいずれか（必須）
- **url**: 検索結果から取得したURL（必須）
- **features**: この家族に合う特徴
- **recommendation**: なぜこの宿がおすすめか

### 4. おすすめスポット（activities）- 3〜5件
**★★★ 必須: 観光スポット・アクティビティを必ず含める ★★★**

各スポットに**必ず**以下を含める：
- **name**: スポット名
- **url**: 公式サイトのURL（検索結果から取得、必須）
- **price_hint**: 「大人¥1,800、子供¥900」のように具体的に
- **access**: アクセス情報
- **features**: 楽しめること
- **recommendation**: なぜおすすめか

### 5. モデルコース（model_course）
**具体的な旅程**として：
- 2日間の流れ（出発〜帰着）
- 各スポットの所要時間・入場料の目安
- 子連れの場合の実用Tips（トイレ、休憩スポット、混雑時間）
- 合計予算の目安（総予算目安: 家族4人で¥XX,XXX〜）

## 文体のルール
- 「です・ます」調で丁寧に
- 「〜がおすすめです」「〜をご検討ください」のような提案調
- 価格は具体的な数字で（検索結果から読み取れる範囲で）
- 「約」「〜程度」を使って幅を持たせてOK
- 検索結果から確実に読み取れる情報のみを記載

## ★★★ 出力チェックリスト（必ず確認）★★★
出力前に以下を必ず確認してください：
□ accommodations の各項目に price_range と price_category が設定されているか
□ activities に3件以上のスポット情報が含まれているか
□ 各 url フィールドに検索結果から取得したURLが設定されているか
□ model_course に2日間のタイムラインが含まれているか
□ model_course.total_budget に総予算目安が設定されているか"""

DAYTRIP_RESEARCHER_SYSTEM_PROMPT = """あなたは旅行代理店のコンサルタントです。
検索結果から、**お客様が日帰り旅行を具体的に検討できる情報**を整理してください。

## あなたの役割
旅行代理店に相談に来たお客様に対して、以下を提供すること：
1. **おすすめの時期** - いつ行けば良いか、混雑状況
2. **スポット情報** - どこに行けば何ができるか、料金、アクセス、リンク
3. **おすすめプラン** - 上記を踏まえた具体的な旅程案

## 重要：情報の具体性
- **価格は必ず記載**: 入場料、体験料など「大人¥1,500、子供¥800」のように
- **URLは必ず記載**: 検索結果のURLを活用し、お客様が詳細を確認できるように
- **アクセス情報**: 最寄り駅、駐車場の有無など

## 出力内容

### 1. おすすめ時期（timing_options）
**混雑と季節を軸に整理**してください：
- **空いている時期**: 「平日」「〇月は穴場」など
- **ベストシーズン**: 「紅葉は11月中旬がピーク」など
- 子連れの場合は学校の長期休暇との兼ね合いも考慮

### 2. おすすめスポット（activities）- 3〜5件
各スポットに必ず以下を含める：
- **url**: 公式サイトのURL（検索結果から取得）
- **price_hint**: 料金目安（大人¥X,XXX、子供¥XXX）
- **access**: アクセス情報（最寄り駅、駐車場）
- **features**: 楽しめること、見どころ
- **special_point**: この家族に合うポイント（子供の年齢別など）
- **recommendation**: なぜおすすめか

### 3. モデルコース（model_course）
**具体的な旅程**として：
- 出発〜帰宅までのタイムライン（5〜7ステップ）
- 各スポットの所要時間
- 子連れの場合の実用Tips（トイレ、休憩スポット）
- 総予算目安（交通費・入場料・食事込み）

### 4. サマリー（summary）
旅行代理店の提案書の冒頭のように：
- この日帰り旅行の魅力を簡潔に（3〜4文）
- 「〜がおすすめです」「〜をご提案します」調で

## 注意点
- 検索結果から確実に読み取れる情報のみを記載
- 価格は「約」「〜程度」を使って幅を持たせてOK
- **宿泊施設の情報は不要**（日帰りプランです）"""


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

    # 旅行者の詳細プロフィール（子供の年齢、シニア、ペット等）
    travelers_profile = ""
    if context.travelers and context.travelers.notes:
        travelers_profile = (
            f"\n- 詳細: {context.travelers.notes}"
            "（★重要：この情報に合わせた提案をしてください）"
        )

    search_data = f"""## 旅行者プロフィール
- 目的地: {context.destination}
- 時期: {context.timing}
- 人数: {travelers_info}{travelers_profile}
- やりたいこと: {", ".join(context.constraints) if context.constraints else "特になし"}

**この旅行者だけの特別なお出かけプラン**を作ってください！

## 検索結果：日帰り基本情報
{json.dumps(day_trip_results, ensure_ascii=False, indent=2)}

## 検索結果：アクティビティ・スポット
{json.dumps(activity_results, ensure_ascii=False, indent=2)}

上記を参考に、この旅行者にぴったりの日帰りプランを提案してください。
特に**モデルコース（タイムライン）**は必ず作成してください！"""

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
            special_point=a.special_point,
        )
        for a in result.activities
    ]

    # モデルコースを構築
    model_course = ModelCourse(
        title=result.model_course.title,
        steps=[
            ModelCourseStep(
                time=s.time,
                title=s.title,
                description=s.description,
                tips=s.tips,
            )
            for s in result.model_course.steps
        ],
        total_budget=result.model_course.total_budget,
    )

    research_result = ResearchResult(
        timing_options=timing_options,
        activities=activities,
        model_course=model_course,
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

    # Step 4: 観光スポット調査
    logger.info("Starting activities/spots search")
    activity_results = search_activities(context)
    logger.info("Activities search completed")

    # 検索結果をLLMで整理（宿泊用スキーマ）
    # 創造的な文章を書くためtemperatureを上げる
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7)
    structured_llm = llm.with_structured_output(ResearcherOutput)

    # 旅行者の詳細プロフィール（子供の年齢、シニア、ペット等）
    travelers_profile = ""
    if context.travelers and context.travelers.notes:
        travelers_profile = (
            f"\n- 詳細: {context.travelers.notes}"
            "（★重要：この家族に合わせた物語を書いてください）"
        )

    search_data = f"""## お客様情報
- 目的地: {context.destination}
- 時期: {context.timing}
- 人数: {travelers_info}{travelers_profile}
- ご要望: {", ".join(context.constraints) if context.constraints else "特になし"}

**このお客様に最適な旅行プラン**をご提案ください。

## 検索結果：時期・相場トレンド
{json.dumps(timing_results, ensure_ascii=False, indent=2)}

## 検索結果：フライト価格
{json.dumps(flight_results, ensure_ascii=False, indent=2)}

## 検索結果：宿泊施設
{json.dumps(accommodation_results, ensure_ascii=False, indent=2)}

## 検索結果：観光スポット・アクティビティ
{json.dumps(activity_results, ensure_ascii=False, indent=2)}

上記を参考に、旅行代理店としてお客様にご提案ください：
1. **狙い目の時期**（安い時期、ベストシーズン等を価格とともに）
2. **宿泊施設一覧**（★必須: 各施設に price_range と price_category を設定）
3. **観光スポット一覧**（★必須: activities に3件以上、各スポットにURL・料金を設定）
4. **おすすめ2日間プラン**（総予算目安付き）

★重要★
- price_category は必ず budget/standard/premium のいずれかを設定
- activities は空にせず、必ず3件以上のスポット情報を含める
- URLは検索結果から取得して設定"""

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
            price_range=a.price_range,
            price_category=a.price_category,
            features=a.features,
            recommendation=a.recommendation,
        )
        for a in result.accommodations
    ]

    # 観光スポット・アクティビティを構築
    activities = [
        ActivityInfo(
            name=a.name,
            url=a.url,
            features=a.features,
            access=a.access,
            price_hint=a.price_hint,
            recommendation=a.recommendation,
            special_point=a.special_point,
        )
        for a in result.activities
    ]

    # モデルコースを構築（2日間）
    model_course = ModelCourse(
        title=result.model_course.title,
        steps=[
            ModelCourseStep(
                time=s.time,
                title=s.title,
                description=s.description,
                tips=s.tips,
            )
            for s in result.model_course.steps
        ],
        total_budget=result.model_course.total_budget,
    )

    research_result = ResearchResult(
        timing_options=timing_options,
        accommodations=accommodations,
        activities=activities,
        model_course=model_course,
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
