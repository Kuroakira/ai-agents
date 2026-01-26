"""状態スキーマ定義.

Scheduler Agentで使用する入力・出力・中間状態のスキーマを定義。
"""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field


class CalendarEvent(BaseModel):
    """カレンダーイベントの情報."""

    summary: str = Field(..., description="イベントの件名")
    start_time: datetime = Field(..., description="開始時刻")
    end_time: datetime = Field(..., description="終了時刻")
    description: str | None = Field(default=None, description="イベントの説明")
    event_id: str | None = Field(
        default=None, description="Google Calendar上のイベントID"
    )


class TaskItem(BaseModel):
    """ユーザーから抽出されたタスク."""

    title: str = Field(..., description="タスクの名前")
    estimated_duration_minutes: int = Field(
        default=30, description="推定所要時間（分）"
    )
    preferred_time: str | None = Field(
        default=None, description="ユーザー指定の希望時間（例: '10時', '午後'）"
    )
    is_scheduled: bool = Field(default=False, description="カレンダーに登録済みか")


def add_messages(existing: list[dict], new: list[dict]) -> list[dict]:
    """メッセージリストを追加するリデューサー."""
    return existing + new


class SchedulerState(BaseModel):
    """Scheduler Agentの状態スキーマ.

    LangGraphのワークフローで共有される状態を定義。
    """

    # 入力
    user_input: str = Field(default="", description="ユーザーからの入力メッセージ")
    user_id: str = Field(default="", description="SlackのユーザーID")
    channel_id: str = Field(default="", description="SlackのチャンネルID")

    # カレンダー情報
    todays_events: list[CalendarEvent] = Field(
        default_factory=list, description="今日の既存予定リスト"
    )
    free_slots: list[tuple[datetime, datetime]] = Field(
        default_factory=list, description="空き時間スロットのリスト"
    )

    # タスク解析結果
    extracted_tasks: list[TaskItem] = Field(
        default_factory=list, description="ユーザー入力から抽出されたタスク"
    )

    # 登録結果
    scheduled_events: list[CalendarEvent] = Field(
        default_factory=list, description="カレンダーに登録されたイベント"
    )

    # LLMとの対話履歴
    messages: Annotated[list[dict], add_messages] = Field(
        default_factory=list, description="LLMとの対話履歴"
    )

    # 処理状態
    error_message: str | None = Field(default=None, description="エラーメッセージ")
    response_text: str = Field(default="", description="ユーザーへの応答メッセージ")
