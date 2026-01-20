"""Example usage of customer persona feedback agent."""

import asyncio

from dotenv import load_dotenv

from agents.customer_persona.graph import app
from agents.customer_persona.state import AgentState


async def main():
    """メイン実行関数."""
    load_dotenv()

    # 初期状態の設定
    initial_state = AgentState(
        idea="""
        家計簿アプリ「MoneyTrack」
        - レシートをカメラで撮影すると自動で支出を記録
        - AIが支出パターンを分析して節約アドバイス
        - 家族で支出を共有できる機能
        """,
        persona_description="""
        35歳の共働き主婦、田中美咲。
        小学生の子供が2人いる4人家族。
        ITには詳しくないが、スマホは日常的に使用。
        家計管理は月末にまとめてやるタイプで、
        細かい記録は面倒だと感じている。
        節約には興味があるが、時間がない。
        """,
    )

    print("顧客ペルソナフィードバックエージェントを実行中...\n")

    # エージェントの実行
    result = await app.ainvoke(initial_state)

    # 結果の表示
    print("=" * 50)
    print("フィードバック結果")
    print("=" * 50)

    if result["feedback"]:
        print("\n【全体的なフィードバック】")
        print(result["feedback"].feedback)

        print("\n【懸念点・疑問点】")
        for concern in result["feedback"].concerns:
            print(f"  - {concern}")

        print("\n【興味を持った点】")
        for interest in result["feedback"].interests:
            print(f"  - {interest}")

        print("\n【改善提案】")
        for suggestion in result["feedback"].suggestions:
            print(f"  - {suggestion}")

    if result["review"]:
        print("\n" + "=" * 50)
        print("レビュー結果")
        print("=" * 50)
        print(f"スコア: {result['review'].score}/10")
        print(f"適切: {'はい' if result['review'].is_appropriate else 'いいえ'}")
        print(f"判断理由: {result['review'].reasoning}")

    print("\n" + "=" * 50)
    print("実行情報")
    print("=" * 50)
    print(f"ステータス: {result['status']}")
    print(f"反復回数: {result['iteration']}")


if __name__ == "__main__":
    asyncio.run(main())
