"""Memoエージェントのワークフロー定義.

LangGraphを使用してメモ処理のフローを構築。
"""

from langgraph.graph import END, StateGraph

from agents.memo.nodes import (
    fetch_tags_node,
    parser_node,
    saver_node,
    tag_matcher_node,
)
from agents.memo.state import MemoState


def compile_graph() -> StateGraph:
    """メモ処理グラフを構築・コンパイル.

    フロー:
        START -> fetch_tags -> parser -> tag_matcher -> saver -> END

    fetch_tags: Notionから既存タグを取得
    parser: 入力テキストを解析し、タグ候補・コンテンツを抽出
    tag_matcher: 候補タグと既存タグをマッチング
    saver: 解析結果をNotionデータベースに保存

    Returns:
        StateGraph: コンパイル済みのワークフロー
    """
    workflow = StateGraph(MemoState)

    # ノードを追加
    workflow.add_node("fetch_tags", fetch_tags_node)
    workflow.add_node("parser", parser_node)
    workflow.add_node("tag_matcher", tag_matcher_node)
    workflow.add_node("saver", saver_node)

    # エッジを定義
    workflow.set_entry_point("fetch_tags")
    workflow.add_edge("fetch_tags", "parser")
    workflow.add_edge("parser", "tag_matcher")
    workflow.add_edge("tag_matcher", "saver")
    workflow.add_edge("saver", END)

    return workflow.compile()


# コンパイル済みグラフをエクスポート
app = compile_graph()
