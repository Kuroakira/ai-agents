"""Travel Concierge Agent 実行サンプル.

コンソールでの対話テスト用スクリプト。
"""

from dotenv import load_dotenv

from agents.travel_concierge.graph import app
from agents.travel_concierge.state import Phase, TravelConciergeState

# 環境変数を読み込み
load_dotenv()


def run_console_chat() -> None:
    """コンソールでチャットを実行."""
    print("=" * 50)
    print("🌴 Travel Concierge へようこそ！")
    print("旅行の計画をお手伝いします。")
    print("終了するには 'quit' または 'exit' と入力してください。")
    print("=" * 50)
    print()

    # 初期状態
    state = TravelConciergeState()

    # 最初の挨拶を生成
    initial_input = "こんにちは、旅行の相談をしたいです"
    state.messages.append({"role": "user", "content": initial_input})

    while True:
        # グラフを実行
        result = app.invoke(state)

        # 応答を表示
        if result.get("response_text"):
            print(f"\n🤖 コンシェルジュ: {result['response_text']}\n")

        # フェーズを確認
        current_phase = result.get("phase", Phase.INTERVIEWING)

        # 完了またはエラーの場合は終了
        if current_phase == Phase.COMPLETED:
            if result.get("notion_page_url"):
                print(f"📝 Notionページ: {result['notion_page_url']}")
            if result.get("error_message"):
                print(f"⚠️ エラー: {result['error_message']}")
            break

        # リサーチ中やパブリッシュ中は自動で進む
        if current_phase in (Phase.RESEARCHING, Phase.PUBLISHING):
            state = TravelConciergeState(**result)
            continue

        # ユーザー入力を待つ（インタビューフェーズ）
        try:
            user_input = input("👤 あなた: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n👋 ご利用ありがとうございました！")
            break

        if user_input.lower() in ("quit", "exit", "終了"):
            print("\n👋 ご利用ありがとうございました！")
            break

        if not user_input:
            continue

        # 状態を更新してメッセージを追加
        state = TravelConciergeState(**result)
        state.messages.append({"role": "user", "content": user_input})


def run_demo() -> None:
    """デモ用の固定シナリオを実行.

    Tavily/Notion APIなしでインタビュー部分のみテスト。
    """
    print("=" * 50)
    print("🌴 Travel Concierge デモ（インタビューのみ）")
    print("=" * 50)
    print()

    # デモ用の会話シナリオ
    demo_messages = [
        "北海道に旅行したいんだよね",
        "GWあたりかな、4月末から5月頭",
        "大人2人と子供2人、5歳と2歳です",
        "和室で布団がいいな、あとカニ料理が食べたい！",
    ]

    state = TravelConciergeState()

    for user_input in demo_messages:
        print(f"👤 あなた: {user_input}")
        state.messages.append({"role": "user", "content": user_input})

        # グラフを実行（インタビューノードのみ）
        result = app.invoke(state)

        if result.get("response_text"):
            print(f"🤖 コンシェルジュ: {result['response_text']}\n")

        # フェーズをチェック
        current_phase = result.get("phase", Phase.INTERVIEWING)
        if current_phase == Phase.RESEARCHING:
            print("✅ インタビュー完了！リサーチフェーズへ移行します。")
            print(f"📋 収集した情報: {result.get('travel_context')}")
            break

        state = TravelConciergeState(**result)

    print("\n" + "=" * 50)
    print("デモ終了")
    print("=" * 50)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        run_demo()
    else:
        run_console_chat()
