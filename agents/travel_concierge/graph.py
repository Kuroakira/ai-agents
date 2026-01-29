"""LangGraphワークフロー定義.

Travel Concierge Agentのワークフローを構築。
"""

from langgraph.graph import END, StateGraph

from agents.travel_concierge.nodes import (
    interview_user,
    publish_to_notion,
    research_travel,
    route_by_phase,
)
from agents.travel_concierge.state import TravelConciergeState


def compile_graph() -> StateGraph:
    """Travel Conciergeのワークフローグラフを構築.

    Returns:
        StateGraph: コンパイル済みのグラフ
    """
    # グラフを初期化
    workflow = StateGraph(TravelConciergeState)

    # ノードを追加
    workflow.add_node("interview", interview_user)
    workflow.add_node("research", research_travel)
    workflow.add_node("publish", publish_to_notion)

    # エントリーポイントを設定
    workflow.set_entry_point("interview")

    # 条件付きエッジを追加（interviewノードの後）
    # インタビュー中は一度ENDに遷移し、次のユーザー入力を待つ
    workflow.add_conditional_edges(
        "interview",
        route_by_phase,
        {
            "interview": END,  # ユーザー入力待ち（次のinvokeで再開）
            "research": "research",  # リサーチへ移行
            "end": END,  # エラー時は終了
        },
    )

    # researchノードからpublishへ
    workflow.add_conditional_edges(
        "research",
        route_by_phase,
        {
            "publish": "publish",
            "end": END,
        },
    )

    # publishノードから終了へ
    workflow.add_edge("publish", END)

    return workflow.compile()


# コンパイル済みグラフをエクスポート
app = compile_graph()
