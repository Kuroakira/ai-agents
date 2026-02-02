"""Memoエージェントのデモスクリプト.

コマンドラインからメモを入力し、Notionに保存するサンプル。
"""

import asyncio

from dotenv import load_dotenv

from agents.memo.graph import app
from agents.memo.state import MemoState


async def run_memo_example(input_text: str) -> None:
    """メモエージェントを実行.

    Args:
        input_text: ユーザー入力テキスト
    """
    print(f"\n📝 入力テキスト:\n{input_text}\n")
    print("-" * 50)

    initial_state = MemoState(input_text=input_text)
    result = await app.ainvoke(initial_state)

    if result.get("status") == "completed":
        print("\n✅ 処理完了！")
        print(f"📂 ソースタイプ: {result.get('source_type')}")
        parsed = result.get("parsed_result", {})
        print(f"📋 トピック: {parsed.get('topic')}")
        final_tags = result.get("final_tags", [])
        print(f"🏷️  タグ: {', '.join(final_tags)}")
        print(f"📄 コンテンツ: {parsed.get('content')[:100]}...")
        if parsed.get("source"):
            print(f"📚 出典: {parsed.get('source')}")
        print(f"\n🔗 Notion URL: {result.get('notion_url')}")
    else:
        print(f"\n❌ エラー: {result.get('error_message')}")


async def main():
    """デモを実行."""
    load_dotenv()

    # サンプル1: 通常の思考メモ
    thought_example = """
    今日、AIエージェントの設計について考えていた。
    LangGraphを使うと、状態管理がシンプルになって、
    複雑なワークフローも整理しやすくなる。
    将来的にはHuman-in-the-loopも組み込みたい。
    """

    # サンプル2: Kindle共有（形式例）
    kindle_example = """
    "知識は力なり" フランシス・ベーコン『ノヴム・オルガヌム』より
    Kindleのメモより
    """

    print("=" * 60)
    print("📌 サンプル1: 通常の思考メモ")
    print("=" * 60)
    await run_memo_example(thought_example)

    print("\n")
    print("=" * 60)
    print("📌 サンプル2: Kindle共有")
    print("=" * 60)
    await run_memo_example(kindle_example)


def run_interactive() -> None:
    """インタラクティブモードでメモを入力."""
    load_dotenv()

    print("=" * 60)
    print("📝 Memoエージェント - インタラクティブモード")
    print("メモを入力してください（終了: Ctrl+C）")
    print("=" * 60)

    while True:
        try:
            print("\n📝 メモを入力（複数行の場合は空行で終了）:")
            lines = []
            while True:
                line = input()
                if not line:
                    break
                lines.append(line)

            if not lines:
                print("⚠️ 入力がありません")
                continue

            input_text = "\n".join(lines)
            asyncio.run(run_memo_example(input_text))

        except KeyboardInterrupt:
            print("\n\n👋 終了します")
            break


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        run_interactive()
    else:
        asyncio.run(main())
