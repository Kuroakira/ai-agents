"""LangGraph workflow for customer persona feedback agent."""

from langgraph.graph import END, StateGraph

from .nodes import finalize, generate_feedback, review_feedback, should_regenerate
from .state import AgentState


def create_graph() -> StateGraph:
    """顧客ペルソナフィードバックエージェントのグラフを構築する.

    Returns:
        構築されたStateGraph
    """
    # グラフの初期化
    graph = StateGraph(AgentState)

    # ノードの追加
    graph.add_node("generate", generate_feedback)
    graph.add_node("review", review_feedback)
    graph.add_node("finalize", finalize)

    # エッジの追加
    graph.add_edge("__start__", "generate")
    graph.add_edge("generate", "review")

    # 条件分岐: 再生成 or 完了
    graph.add_conditional_edges(
        "review",
        should_regenerate,
        {
            "regenerate": "generate",
            "complete": "finalize",
        },
    )

    graph.add_edge("finalize", END)

    return graph


def compile_graph():
    """コンパイル済みグラフを返す.

    Returns:
        コンパイル済みのグラフ
    """
    graph = create_graph()
    return graph.compile()


# デフォルトのコンパイル済みグラフ
app = compile_graph()
