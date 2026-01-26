"""Google Calendar API操作用ツール.

カレンダーの読み取り・書き込み機能を提供。
"""

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from agents.scheduler.state import CalendarEvent

# Google Calendar APIのスコープ
SCOPES = ["https://www.googleapis.com/auth/calendar"]

# タイムゾーン設定
TIMEZONE = ZoneInfo("Asia/Tokyo")

# 認証ファイルのパス（プロジェクトルート基準）
PROJECT_ROOT = Path(__file__).parent.parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / "credentials.json"
TOKEN_PATH = PROJECT_ROOT / "token.json"


def get_calendar_service():
    """Google Calendar APIのサービスオブジェクトを取得.

    初回実行時はブラウザでOAuth認証を行い、token.jsonを保存する。
    2回目以降はtoken.jsonを使用して自動認証する。

    Returns:
        googleapiclient.discovery.Resource: Calendar APIサービスオブジェクト

    Raises:
        FileNotFoundError: credentials.jsonが存在しない場合
    """
    creds = None

    # 既存のトークンを読み込む
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    # トークンが無効または期限切れの場合
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"credentials.jsonが見つかりません: {CREDENTIALS_PATH}\n"
                    "Google Cloud Consoleからダウンロードしてください。"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # トークンを保存
        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def get_todays_events() -> list[CalendarEvent]:
    """今日のカレンダーイベントを取得.

    Returns:
        list[CalendarEvent]: 今日のイベントリスト（開始時刻順）
    """
    service = get_calendar_service()

    # 今日の開始・終了時刻を取得
    now = datetime.now(TIMEZONE)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    # イベントを取得
    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=today_start.isoformat(),
            timeMax=today_end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = events_result.get("items", [])

    calendar_events = []
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))

        # 終日イベントの場合は日付文字列のみ
        if "T" in start:
            start_dt = datetime.fromisoformat(start)
            end_dt = datetime.fromisoformat(end)
        else:
            # 終日イベントは0時から24時として扱う
            start_dt = datetime.fromisoformat(start).replace(tzinfo=TIMEZONE)
            end_dt = datetime.fromisoformat(end).replace(tzinfo=TIMEZONE)

        calendar_events.append(
            CalendarEvent(
                summary=event.get("summary", "（タイトルなし）"),
                start_time=start_dt,
                end_time=end_dt,
                description=event.get("description"),
                event_id=event.get("id"),
            )
        )

    return calendar_events


def add_event_to_calendar(
    summary: str,
    start_time: datetime,
    end_time: datetime,
    description: str | None = None,
) -> CalendarEvent:
    """カレンダーにイベントを追加.

    Args:
        summary: イベントの件名
        start_time: 開始時刻
        end_time: 終了時刻
        description: イベントの説明（省略可）

    Returns:
        CalendarEvent: 作成されたイベント情報
    """
    service = get_calendar_service()

    # タイムゾーンを付与（なければ）
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=TIMEZONE)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=TIMEZONE)

    event_body = {
        "summary": summary,
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": "Asia/Tokyo",
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": "Asia/Tokyo",
        },
    }

    if description:
        event_body["description"] = description

    event = service.events().insert(calendarId="primary", body=event_body).execute()

    return CalendarEvent(
        summary=summary,
        start_time=start_time,
        end_time=end_time,
        description=description,
        event_id=event.get("id"),
    )


def calculate_free_slots(
    events: list[CalendarEvent],
    work_start_hour: int = 9,
    work_end_hour: int = 21,
) -> list[tuple[datetime, datetime]]:
    """今日の空き時間スロットを計算.

    Args:
        events: 既存のカレンダーイベントリスト
        work_start_hour: 稼働開始時刻（デフォルト9時）
        work_end_hour: 稼働終了時刻（デフォルト21時）

    Returns:
        list[tuple[datetime, datetime]]: 空き時間スロットのリスト（開始, 終了）
    """
    now = datetime.now(TIMEZONE)
    today_start = now.replace(hour=work_start_hour, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=work_end_hour, minute=0, second=0, microsecond=0)

    # 現在時刻より前の時間は除外
    if now > today_start:
        today_start = now

    # 既に稼働時間を過ぎている場合
    if now >= today_end:
        return []

    # イベントを開始時刻でソート
    sorted_events = sorted(events, key=lambda e: e.start_time)

    free_slots = []
    current_time = today_start

    for event in sorted_events:
        event_start = event.start_time
        event_end = event.end_time

        # 稼働時間外のイベントはスキップ
        if event_end <= today_start or event_start >= today_end:
            continue

        # イベント開始前に空き時間があれば追加
        if event_start > current_time:
            free_slots.append((current_time, event_start))

        # 現在時刻をイベント終了時刻に更新
        if event_end > current_time:
            current_time = event_end

    # 最後のイベント後に空き時間があれば追加
    if current_time < today_end:
        free_slots.append((current_time, today_end))

    return free_slots
