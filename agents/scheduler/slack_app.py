"""Slack Bolt連携.

Slack BotをSocket Modeで起動し、ユーザーメッセージを処理する。
"""

import logging
import os

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from agents.scheduler.graph import app as scheduler_app
from agents.scheduler.state import SchedulerState

# 環境変数の読み込み
load_dotenv()

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Slack Appの初期化
slack_app = App(token=os.environ.get("SLACK_BOT_TOKEN"))


@slack_app.event("message")
def handle_message(event: dict, say, client) -> None:
    """メッセージイベントを処理.

    Args:
        event: Slackイベントデータ
        say: メッセージ送信関数
        client: Slack WebClient
    """
    # Bot自身のメッセージは無視
    if event.get("bot_id"):
        return

    # サブタイプがあるメッセージ（編集、削除など）は無視
    if event.get("subtype"):
        return

    user_input = event.get("text", "")
    user_id = event.get("user", "")
    channel_id = event.get("channel", "")

    if not user_input.strip():
        return

    logger.info(f"Received message from {user_id}: {user_input[:50]}...")

    # 処理中のリアクションを追加
    try:
        client.reactions_add(
            channel=channel_id,
            name="hourglass_flowing_sand",
            timestamp=event.get("ts"),
        )
    except Exception as e:
        logger.warning(f"Failed to add reaction: {e}")

    # Scheduler Agentを実行
    try:
        initial_state = SchedulerState(
            user_input=user_input,
            user_id=user_id,
            channel_id=channel_id,
        )

        result = scheduler_app.invoke(initial_state)
        response_text = result.get("response_text", "処理が完了しました。")

        # 応答を送信
        say(response_text)

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        say(f"⚠️ エラーが発生しました: {e}")

    # 処理完了のリアクションに変更
    try:
        client.reactions_remove(
            channel=channel_id,
            name="hourglass_flowing_sand",
            timestamp=event.get("ts"),
        )
        client.reactions_add(
            channel=channel_id,
            name="white_check_mark",
            timestamp=event.get("ts"),
        )
    except Exception as e:
        logger.warning(f"Failed to update reaction: {e}")


@slack_app.event("app_mention")
def handle_app_mention(event: dict, say, client) -> None:
    """アプリへのメンションを処理.

    Args:
        event: Slackイベントデータ
        say: メッセージ送信関数
        client: Slack WebClient
    """
    # メッセージイベントと同じ処理を実行
    handle_message(event, say, client)


def start_slack_bot() -> None:
    """Slack Botを起動.

    Socket Modeでボットを起動し、メッセージを待ち受ける。

    Raises:
        ValueError: 必要な環境変数が設定されていない場合
    """
    bot_token = os.environ.get("SLACK_BOT_TOKEN")
    app_token = os.environ.get("SLACK_APP_TOKEN")

    if not bot_token:
        raise ValueError("SLACK_BOT_TOKEN環境変数が設定されていません")
    if not app_token:
        raise ValueError("SLACK_APP_TOKEN環境変数が設定されていません")

    logger.info("Starting Scheduler Bot in Socket Mode...")
    handler = SocketModeHandler(slack_app, app_token)
    handler.start()


if __name__ == "__main__":
    start_slack_bot()
