"""ノード関数定義.

LangGraphワークフローの各処理ステップを実装。
"""

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from agents.scheduler.state import SchedulerState, TaskItem
from agents.scheduler.tools import (
    add_event_to_calendar,
    calculate_free_slots,
    get_todays_events,
)

TIMEZONE = ZoneInfo("Asia/Tokyo")

SYSTEM_PROMPT = """あなたはユーザーの脳内整理を助ける秘書AIです。

## 役割
ユーザーから投げられた雑多なタスク（脳内ダンプ）を受け取り、
整理してGoogle Calendarに登録します。

## 処理手順
1. ユーザーの入力からタスクを抽出する
2. 各タスクの所要時間を推測する
3. 今日の空き時間に適切に配置する

## タスクの所要時間の目安
- 買い物・簡単な用事: 30分
- 資料の確認・レビュー: 30分〜1時間
- 会議準備: 30分
- 運動・ジム: 1時間〜1時間30分
- 集中作業・執筆: 1時間〜2時間
- ミーティング: 30分〜1時間

## 出力形式
タスクを抽出して以下のJSON形式で出力してください：
```json
{
  "tasks": [
    {
      "title": "タスク名",
      "estimated_duration_minutes": 30,
      "preferred_time": "10時" または null
    }
  ]
}
```

## 注意点
- タスク名には「📝」のプレフィックスを付けて、既存の予定と区別しやすくする
- 指定時間があればそれを優先、なければ空き時間に配置
- 現実的なスケジュールになるよう配慮する"""


def fetch_calendar_events(state: SchedulerState) -> dict:
    """今日のカレンダーイベントを取得するノード.

    Args:
        state: 現在の状態

    Returns:
        dict: 更新する状態の差分
    """
    try:
        events = get_todays_events()
        free_slots = calculate_free_slots(events)

        return {
            "todays_events": events,
            "free_slots": free_slots,
        }
    except FileNotFoundError as e:
        return {
            "error_message": str(e),
            "todays_events": [],
            "free_slots": [],
        }
    except Exception as e:
        return {
            "error_message": f"カレンダーの取得に失敗しました: {e}",
            "todays_events": [],
            "free_slots": [],
        }


def analyze_tasks(state: SchedulerState) -> dict:
    """ユーザー入力からタスクを抽出するノード.

    LLMを使用してユーザーの自然言語入力からタスクを抽出・解析する。

    Args:
        state: 現在の状態

    Returns:
        dict: 更新する状態の差分
    """
    if state.error_message:
        return {}

    # 今日の予定と空き時間の情報を整形
    now = datetime.now(TIMEZONE)
    events_info = "なし"
    if state.todays_events:
        events_list = []
        for e in state.todays_events:
            start_str = e.start_time.strftime("%H:%M")
            end_str = e.end_time.strftime("%H:%M")
            events_list.append(f"  - {start_str}〜{end_str}: {e.summary}")
        events_info = "\n".join(events_list)

    free_slots_info = "なし"
    if state.free_slots:
        slots_list = []
        for start, end in state.free_slots:
            start_str = start.strftime("%H:%M")
            end_str = end.strftime("%H:%M")
            duration = int((end - start).total_seconds() / 60)
            slots_list.append(f"  - {start_str}〜{end_str}（{duration}分）")
        free_slots_info = "\n".join(slots_list)

    user_message = f"""現在時刻: {now.strftime("%Y年%m月%d日 %H:%M")}

## 今日の予定
{events_info}

## 空き時間
{free_slots_info}

## ユーザーの入力
{state.user_input}

上記の入力からタスクを抽出し、JSON形式で出力してください。"""

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.3)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ]

    response = llm.invoke(messages)
    response_text = response.content

    # JSONを抽出
    try:
        # ```json ... ``` の形式に対応
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            json_str = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            json_str = response_text[json_start:json_end].strip()
        else:
            # JSONのみの出力を想定
            json_str = response_text.strip()

        data = json.loads(json_str)
        tasks = []
        for task_data in data.get("tasks", []):
            tasks.append(
                TaskItem(
                    title=task_data.get("title", "タスク"),
                    estimated_duration_minutes=task_data.get(
                        "estimated_duration_minutes", 30
                    ),
                    preferred_time=task_data.get("preferred_time"),
                )
            )

        return {
            "extracted_tasks": tasks,
            "messages": [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": response_text},
            ],
        }

    except json.JSONDecodeError as e:
        return {
            "error_message": f"タスクの解析に失敗しました: {e}",
            "extracted_tasks": [],
        }


def schedule_tasks(state: SchedulerState) -> dict:
    """タスクをカレンダーに登録するノード.

    抽出されたタスクを空き時間に配置し、Google Calendarに登録する。

    Args:
        state: 現在の状態

    Returns:
        dict: 更新する状態の差分
    """
    if state.error_message or not state.extracted_tasks:
        return {}

    now = datetime.now(TIMEZONE)
    scheduled_events = []
    available_slots = list(state.free_slots)  # コピーして使用

    for task in state.extracted_tasks:
        duration = timedelta(minutes=task.estimated_duration_minutes)

        # 希望時間の解析
        preferred_start = None
        if task.preferred_time:
            preferred_start = _parse_preferred_time(task.preferred_time, now)

        # スロットを探す
        start_time = None
        end_time = None

        if preferred_start:
            # 希望時間に近いスロットを探す
            for i, (slot_start, slot_end) in enumerate(available_slots):
                # 希望時間がスロット内にあり、十分な時間があるか
                if slot_start <= preferred_start < slot_end:
                    if slot_end - preferred_start >= duration:
                        start_time = preferred_start
                        end_time = preferred_start + duration
                        # スロットを更新
                        _update_slots(available_slots, i, start_time, end_time)
                        break

        # 希望時間に配置できなかった場合、最初の空きスロットに配置
        if not start_time:
            for i, (slot_start, slot_end) in enumerate(available_slots):
                if slot_end - slot_start >= duration:
                    start_time = slot_start
                    end_time = slot_start + duration
                    _update_slots(available_slots, i, start_time, end_time)
                    break

        # スロットが見つかった場合、カレンダーに登録
        if start_time and end_time:
            try:
                event = add_event_to_calendar(
                    summary=task.title,
                    start_time=start_time,
                    end_time=end_time,
                    description="Scheduler Agentによる自動登録",
                )
                scheduled_events.append(event)
            except Exception as e:
                return {
                    "error_message": f"カレンダーへの登録に失敗しました: {e}",
                    "scheduled_events": scheduled_events,
                }

    return {"scheduled_events": scheduled_events}


def _parse_preferred_time(time_str: str, base_date: datetime) -> datetime | None:
    """希望時間の文字列をdatetimeに変換.

    Args:
        time_str: 時間を表す文字列（例: "10時", "14:30", "午後3時"）
        base_date: 基準となる日付

    Returns:
        datetime | None: 解析結果、解析できない場合はNone
    """
    import re

    # "午後"/"午前"の処理
    is_pm = "午後" in time_str or "PM" in time_str.upper()
    is_am = "午前" in time_str or "AM" in time_str.upper()

    # 数字を抽出
    numbers = re.findall(r"\d+", time_str)
    if not numbers:
        return None

    hour = int(numbers[0])
    minute = int(numbers[1]) if len(numbers) > 1 else 0

    # 午後の場合は12時間加算（12時は除く）
    if is_pm and hour < 12:
        hour += 12
    elif is_am and hour == 12:
        hour = 0

    try:
        return base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
    except ValueError:
        return None


def _update_slots(
    slots: list[tuple[datetime, datetime]],
    index: int,
    used_start: datetime,
    used_end: datetime,
) -> None:
    """使用したスロットを更新.

    Args:
        slots: スロットリスト（in-place更新）
        index: 更新するスロットのインデックス
        used_start: 使用した開始時刻
        used_end: 使用した終了時刻
    """
    slot_start, slot_end = slots[index]

    # スロットを削除
    slots.pop(index)

    # 前後に残りがあれば追加
    if used_start > slot_start:
        slots.insert(index, (slot_start, used_start))
        index += 1
    if used_end < slot_end:
        slots.insert(index, (used_end, slot_end))


def generate_response(state: SchedulerState) -> dict:
    """ユーザーへの応答を生成するノード.

    Args:
        state: 現在の状態

    Returns:
        dict: 更新する状態の差分
    """
    if state.error_message:
        return {"response_text": f"⚠️ エラーが発生しました:\n{state.error_message}"}

    if not state.scheduled_events:
        return {
            "response_text": "📋 登録するタスクが見つかりませんでした。\n"
            "タスクを含むメッセージを送信してください。"
        }

    # 登録結果を整形
    lines = ["✅ 以下のタスクをカレンダーに登録しました：\n"]
    for event in state.scheduled_events:
        start_str = event.start_time.strftime("%H:%M")
        end_str = event.end_time.strftime("%H:%M")
        lines.append(f"• {start_str}〜{end_str}: {event.summary}")

    return {"response_text": "\n".join(lines)}
