"""Slack Bolt連携.

Slack BotをSocket Modeで起動し、メモを受け取ってNotionに保存する。
"""

import asyncio
import logging
import os
from collections import OrderedDict

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from agents.memo.graph import app as memo_app
from agents.memo.state import MemoState

# 環境変数の読み込み
load_dotenv()

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Slack Appの初期化
slack_app = App(token=os.environ.get("MEMO_SLACK_BOT_TOKEN"))

# 処理済みメッセージのキャッシュ（重複処理防止）
# 最大100件を保持
_processed_messages: OrderedDict[str, bool] = OrderedDict()
MAX_CACHE_SIZE = 100


def _is_already_processed(message_ts: str) -> bool:
    """メッセージが処理済みかどうかを確認.

    Args:
        message_ts: メッセージのタイムスタンプ

    Returns:
        bool: 処理済みならTrue
    """
    if message_ts in _processed_messages:
        return True

    # キャッシュに追加
    _processed_messages[message_ts] = True

    # キャッシュサイズを制限
    while len(_processed_messages) > MAX_CACHE_SIZE:
        _processed_messages.popitem(last=False)

    return False


def run_async_graph(input_text: str) -> dict:
    """非同期グラフを同期的に実行.

    Args:
        input_text: ユーザー入力テキスト

    Returns:
        dict: 実行結果
    """
    initial_state = MemoState(input_text=input_text)

    async def _run():
        return await memo_app.ainvoke(initial_state)

    return asyncio.run(_run())


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

    message_ts = event.get("ts", "")

    # 重複処理を防止
    if _is_already_processed(message_ts):
        logger.debug(f"Skipping already processed message: {message_ts}")
        return

    user_input = event.get("text", "")
    user_id = event.get("user", "")
    channel_id = event.get("channel", "")

    if not user_input.strip():
        return

    logger.info(f"Received memo from {user_id}: {user_input[:50]}...")

    # 処理中のリアクションを追加
    try:
        client.reactions_add(
            channel=channel_id,
            name="memo",
            timestamp=message_ts,
        )
    except Exception as e:
        logger.warning(f"Failed to add reaction: {e}")

    # Memo Agentを実行
    try:
        result = run_async_graph(user_input)

        if result.get("status") == "completed":
            notion_url = result.get("notion_url", "")
            source_type = result.get("source_type", "thought")
            parsed = result.get("parsed_result", {})
            final_tags = result.get("final_tags", [])

            type_emoji = "📚" if source_type == "kindle" else "💭"
            tags_str = ", ".join(final_tags) if final_tags else ""
            topic = parsed.get("topic", "")

            response_text = (
                f"{type_emoji} メモを保存しました！\n"
                f"📝 *{topic}* [{tags_str}]\n"
                f"🔗 {notion_url}"
            )
            say(response_text)
        else:
            error_msg = result.get("error_message", "不明なエラー")
            say(f"⚠️ メモの保存に失敗しました: {error_msg}")

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        say(f"⚠️ エラーが発生しました: {e}")

    # 処理完了のリアクションに変更
    try:
        client.reactions_remove(
            channel=channel_id,
            name="memo",
            timestamp=message_ts,
        )
        client.reactions_add(
            channel=channel_id,
            name="white_check_mark",
            timestamp=message_ts,
        )
    except Exception as e:
        logger.warning(f"Failed to update reaction: {e}")


@slack_app.event("app_mention")
def handle_app_mention(event: dict, say, client) -> None:
    """アプリへのメンションを処理.

    message イベントと重複するため、こちらでは処理をスキップ。
    （message イベント側で処理済みかどうかをチェックしている）

    Args:
        event: Slackイベントデータ
        say: メッセージ送信関数
        client: Slack WebClient
    """
    # message イベントで処理されるため、ここでは何もしない
    # ただし、イベントを購読していないとエラーになるため、空のハンドラを残す
    pass


def start_slack_bot() -> None:
    """Slack Botを起動.

    Socket Modeでボットを起動し、メッセージを待ち受ける。

    Raises:
        ValueError: 必要な環境変数が設定されていない場合
    """
    bot_token = os.environ.get("MEMO_SLACK_BOT_TOKEN")
    app_token = os.environ.get("MEMO_SLACK_APP_TOKEN")

    if not bot_token:
        raise ValueError("MEMO_SLACK_BOT_TOKEN環境変数が設定されていません")
    if not app_token:
        raise ValueError("MEMO_SLACK_APP_TOKEN環境変数が設定されていません")

    logger.info("Starting Memo Observer Bot in Socket Mode...")
    handler = SocketModeHandler(slack_app, app_token)
    handler.start()


if __name__ == "__main__":
    start_slack_bot()
