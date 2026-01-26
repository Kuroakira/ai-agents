"""実行サンプル.

Scheduler Agentの動作確認用スクリプト。
Slack連携なしでローカルでテスト実行できる。
"""

from dotenv import load_dotenv

from agents.scheduler.graph import app
from agents.scheduler.state import SchedulerState


def main() -> None:
    """サンプル実行."""
    # 環境変数の読み込み
    load_dotenv()

    # テスト入力
    test_inputs = [
        "10時に会議資料の見直しと、あと牛乳買いたい。夜はジム行く",
        "今日中にメール返信したい。あと請求書の確認と、15時からのミーティング準備",
        "午後にコードレビューをやりたい。1時間くらいかな",
    ]

    for user_input in test_inputs:
        print("=" * 60)
        print(f"入力: {user_input}")
        print("-" * 60)

        try:
            initial_state = SchedulerState(
                user_input=user_input,
                user_id="test_user",
                channel_id="test_channel",
            )

            result = app.invoke(initial_state)

            print(f"応答:\n{result.get('response_text', '応答なし')}")

            if result.get("extracted_tasks"):
                print("\n抽出されたタスク:")
                for task in result["extracted_tasks"]:
                    print(f"  - {task.title} ({task.estimated_duration_minutes}分)")

            if result.get("scheduled_events"):
                print("\n登録されたイベント:")
                for event in result["scheduled_events"]:
                    print(
                        f"  - {event.start_time.strftime('%H:%M')}〜"
                        f"{event.end_time.strftime('%H:%M')}: {event.summary}"
                    )

        except Exception as e:
            print(f"エラー: {e}")

        print()


if __name__ == "__main__":
    main()
