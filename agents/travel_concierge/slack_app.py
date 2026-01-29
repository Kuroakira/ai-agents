"""Slack Bot統合.

Travel Concierge AgentのSlack Bot実装。
スレッドで会話をまとめ、インタビュー→リサーチ→Notion出力を実行。
"""

import logging
import os
import re
from dataclasses import dataclass

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from agents.travel_concierge.graph import app as travel_app
from agents.travel_concierge.state import Phase, TravelConciergeState

# 環境変数を読み込み
load_dotenv()

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Slack App初期化（Travel Concierge専用のトークンを使用）
slack_app = App(token=os.environ.get("TRAVEL_SLACK_BOT_TOKEN"))


@dataclass
class ThreadSession:
    """スレッドごとのセッション情報."""

    state: TravelConciergeState
    channel_id: str
    thread_ts: str


# スレッドごとの会話状態を保持（メモリ内）
# キー: thread_ts
thread_sessions: dict[str, ThreadSession] = {}


def get_session(thread_ts: str) -> ThreadSession | None:
    """スレッドセッションを取得.

    Args:
        thread_ts: スレッドのタイムスタンプ

    Returns:
        ThreadSession | None: セッション（存在しない場合はNone）
    """
    return thread_sessions.get(thread_ts)


def create_session(channel_id: str, thread_ts: str) -> ThreadSession:
    """新しいスレッドセッションを作成.

    Args:
        channel_id: チャンネルID
        thread_ts: スレッドのタイムスタンプ

    Returns:
        ThreadSession: 新しいセッション
    """
    session = ThreadSession(
        state=TravelConciergeState(),
        channel_id=channel_id,
        thread_ts=thread_ts,
    )
    thread_sessions[thread_ts] = session
    logger.info(f"New thread session created: {thread_ts}")
    return session


def delete_session(thread_ts: str) -> None:
    """スレッドセッションを削除.

    Args:
        thread_ts: スレッドのタイムスタンプ
    """
    if thread_ts in thread_sessions:
        del thread_sessions[thread_ts]
        logger.info(f"Thread session deleted: {thread_ts}")


def process_message(session: ThreadSession, message: str) -> tuple[str, bool]:
    """メッセージを処理してレスポンスを生成.

    Args:
        session: スレッドセッション
        message: ユーザーからのメッセージ

    Returns:
        tuple[str, bool]: (応答メッセージ, セッション終了フラグ)
    """
    state = session.state

    # メッセージを追加
    state.messages.append({"role": "user", "content": message})

    try:
        # グラフを実行
        result = travel_app.invoke(state)

        # 状態を更新
        session.state = TravelConciergeState(**result)

        # フェーズに応じた処理
        current_phase = result.get("phase", Phase.INTERVIEWING)
        response_text = result.get("response_text", "")
        is_completed = False

        if current_phase == Phase.COMPLETED:
            is_completed = True

        elif current_phase in (Phase.RESEARCHING, Phase.PUBLISHING):
            # リサーチ・パブリッシュ中は自動で継続実行
            response_text = "🔍 リサーチ中です...少々お待ちください。"

            # 継続実行（最大10回までのループ制限）
            max_iterations = 10
            iteration = 0
            while current_phase not in (Phase.INTERVIEWING, Phase.COMPLETED):
                iteration += 1
                if iteration > max_iterations:
                    logger.error(f"Max iterations reached: {iteration}")
                    response_text = "⚠️ 処理がタイムアウトしました。もう一度お試しください。"
                    is_completed = True
                    break

                try:
                    logger.info(f"Processing iteration {iteration}, phase: {current_phase}")
                    result = travel_app.invoke(TravelConciergeState(**result))
                    current_phase = result.get("phase", Phase.COMPLETED)
                except Exception as loop_error:
                    logger.error(f"Error in processing loop: {loop_error}", exc_info=True)
                    response_text = f"⚠️ 処理中にエラーが発生しました: {loop_error}"
                    is_completed = True
                    break

            # 最終結果を取得
            if iteration <= max_iterations and "response_text" in result:
                response_text = result.get("response_text", "完了しました。")
            is_completed = True

        return response_text, is_completed

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        return f"⚠️ エラーが発生しました: {e}", True


@slack_app.event("app_mention")
def handle_mention(event: dict, say, client) -> None:
    """メンションを処理.

    新しいメンション → 新しいスレッドを開始
    スレッド内のメンション → 既存セッションで継続

    Args:
        event: Slackイベント
        say: メッセージ送信関数
        client: Slackクライアント
    """
    user_id = event.get("user", "")
    channel_id = event.get("channel", "")
    text = event.get("text", "")
    message_ts = event.get("ts", "")
    thread_ts = event.get("thread_ts")  # スレッド内の場合のみ存在

    # メンション部分を除去
    text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()

    if not text:
        say(
            text="こんにちは！旅行の相談をしたい場合は、行きたい場所を教えてください。",
            thread_ts=thread_ts or message_ts,
        )
        return

    logger.info(f"Mention from {user_id}: {text}")

    # スレッド内のメッセージの場合、既存セッションを探す
    if thread_ts:
        session = get_session(thread_ts)
        if session:
            # 既存セッションで継続
            response, is_completed = process_message(session, text)
            say(text=response, thread_ts=thread_ts)

            if is_completed:
                delete_session(thread_ts)
            return

    # 新しいスレッドを開始
    # まず最初のメッセージを送信してスレッドを作成
    client.chat_postMessage(
        channel=channel_id,
        text="🌴 *旅行コンシェルジュ* を開始します！\n\n処理中...",
        thread_ts=message_ts,  # このメッセージへの返信としてスレッドを開始
    )

    # スレッドのtsを取得（親メッセージのts = thread_ts）
    new_thread_ts = message_ts

    # セッションを作成
    session = create_session(channel_id, new_thread_ts)

    # メッセージを処理
    response, is_completed = process_message(session, text)

    # 応答を送信
    say(text=response, thread_ts=new_thread_ts)

    if is_completed:
        delete_session(new_thread_ts)


@slack_app.event("message")
def handle_message(event: dict, say, client) -> None:
    """メッセージを処理.

    DMまたはスレッド内のメッセージを処理。

    Args:
        event: Slackイベント
        say: メッセージ送信関数
        client: Slackクライアント
    """
    # Bot自身のメッセージは無視
    if event.get("bot_id"):
        return

    # サブタイプがあるメッセージは無視（編集、削除など）
    if event.get("subtype"):
        return

    user_id = event.get("user", "")
    channel_id = event.get("channel", "")
    channel_type = event.get("channel_type", "")
    text = event.get("text", "")
    message_ts = event.get("ts", "")
    thread_ts = event.get("thread_ts")

    if not text:
        return

    # スレッド内のメッセージ（メンションなし）
    if thread_ts:
        session = get_session(thread_ts)
        if session:
            logger.info(f"Thread message from {user_id}: {text}")
            response, is_completed = process_message(session, text)
            say(text=response, thread_ts=thread_ts)

            if is_completed:
                delete_session(thread_ts)
        return

    # DMの場合
    if channel_type == "im":
        logger.info(f"DM from {user_id}: {text}")

        # DMでは各メッセージを独立したスレッドとして扱う
        # または、ユーザーごとに1つのセッションを維持することも可能
        # ここではDMでもスレッドを使用
        session = create_session(channel_id, message_ts)
        response, is_completed = process_message(session, text)
        say(text=response, thread_ts=message_ts)

        if is_completed:
            delete_session(message_ts)


@slack_app.event("app_home_opened")
def handle_app_home_opened(event: dict, client) -> None:
    """App Homeを開いた時の処理.

    Args:
        event: Slackイベント
        client: Slackクライアント
    """
    user_id = event.get("user", "")

    try:
        client.views_publish(
            user_id=user_id,
            view={
                "type": "home",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                "*🌴 Travel Concierge へようこそ！*\n\n"
                                "旅行の計画をお手伝いします。\n"
                                "チャンネルでメンションするとスレッドで会話が始まります。"
                            ),
                        },
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                "*使い方*\n"
                                "1. チャンネルで `@Travel Concierge 北海道に行きたい` "
                                "のようにメンション\n"
                                "2. スレッドで会話を続けます\n"
                                "3. 時期や人数を聞かれたら答えてください\n"
                                "4. 自動でリサーチしてNotionに記事を作成！"
                            ),
                        },
                    },
                ],
            },
        )
    except Exception as e:
        logger.error(f"Error publishing home tab: {e}")


def main() -> None:
    """Slack Botを起動."""
    bot_token = os.environ.get("TRAVEL_SLACK_BOT_TOKEN")
    app_token = os.environ.get("TRAVEL_SLACK_APP_TOKEN")

    if not bot_token:
        raise ValueError("TRAVEL_SLACK_BOT_TOKEN環境変数が設定されていません")
    if not app_token:
        raise ValueError("TRAVEL_SLACK_APP_TOKEN環境変数が設定されていません")

    logger.info("🌴 Travel Concierge Bot starting...")
    handler = SocketModeHandler(slack_app, app_token)
    handler.start()


if __name__ == "__main__":
    main()
