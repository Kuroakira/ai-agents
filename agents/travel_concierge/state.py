"""状態スキーマ定義.

Travel Concierge Agentで使用する入力・出力・中間状態のスキーマを定義。
"""

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field


class Phase(str, Enum):
    """エージェントの処理フェーズ."""

    INTERVIEWING = "interviewing"
    RESEARCHING = "researching"
    PUBLISHING = "publishing"
    COMPLETED = "completed"


class Travelers(BaseModel):
    """旅行者構成."""

    adults: int = Field(default=0, description="大人の人数")
    children: int = Field(default=0, description="子供の人数")
    notes: str | None = Field(default=None, description="備考（例: 5歳と2歳）")


class TravelContext(BaseModel):
    """旅行要件コンテキスト.

    ヒアリングで収集する必須パラメータ。
    """

    destination: str | None = Field(default=None, description="目的地")
    timing: str | None = Field(default=None, description="時期（曖昧でOK）")
    travelers: Travelers | None = Field(default=None, description="人数構成")
    constraints: list[str] = Field(
        default_factory=list, description="こだわり条件（和室、布団、カニ料理など）"
    )

    def is_complete(self) -> bool:
        """必須項目がすべて埋まっているか確認."""
        return (
            self.destination is not None
            and self.timing is not None
            and self.travelers is not None
            and self.travelers.adults > 0
        )

    def get_missing_fields(self) -> list[str]:
        """不足している項目を返す."""
        missing = []
        if not self.destination:
            missing.append("destination（目的地）")
        if not self.timing:
            missing.append("timing（時期）")
        if not self.travelers or self.travelers.adults == 0:
            missing.append("travelers（人数構成）")
        return missing


class TimingInfo(BaseModel):
    """時期・相場情報."""

    period: str = Field(..., description="時期（例: 4月中旬）")
    price_estimate: str = Field(..., description="価格目安（例: ¥20,000〜）")
    advantages: list[str] = Field(default_factory=list, description="メリット")
    disadvantages: list[str] = Field(default_factory=list, description="デメリット")


class AccommodationInfo(BaseModel):
    """宿泊施設情報."""

    name: str = Field(..., description="宿名")
    url: str | None = Field(default=None, description="URL")
    features: list[str] = Field(default_factory=list, description="特徴")
    recommendation: str | None = Field(default=None, description="AIの推薦コメント")


class ResearchResult(BaseModel):
    """調査結果."""

    timing_options: list[TimingInfo] = Field(
        default_factory=list, description="時期・相場オプション"
    )
    accommodations: list[AccommodationInfo] = Field(
        default_factory=list, description="宿泊施設リスト"
    )
    summary: str | None = Field(default=None, description="調査サマリー")


def add_messages(existing: list[dict], new: list[dict]) -> list[dict]:
    """メッセージリストを追加するリデューサー."""
    return existing + new


class TravelConciergeState(BaseModel):
    """Travel Concierge Agentの状態スキーマ.

    LangGraphのワークフローで共有される状態を定義。
    """

    # 現在のフェーズ
    phase: Phase = Field(default=Phase.INTERVIEWING, description="現在の処理フェーズ")

    # ヒアリング結果
    travel_context: TravelContext = Field(
        default_factory=TravelContext, description="旅行要件コンテキスト"
    )

    # 調査結果
    research_result: ResearchResult | None = Field(default=None, description="調査結果")

    # Notion出力結果
    notion_page_url: str | None = Field(
        default=None, description="作成されたNotionページURL"
    )

    # 会話履歴
    messages: Annotated[list[dict], add_messages] = Field(
        default_factory=list, description="会話履歴"
    )

    # 処理状態
    error_message: str | None = Field(default=None, description="エラーメッセージ")
    response_text: str = Field(default="", description="ユーザーへの応答メッセージ")
