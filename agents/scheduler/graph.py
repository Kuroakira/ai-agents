"""LangGraphワークフロー定義.

Scheduler Agentのグラフ構造を定義。
"""

from langgraph.graph import END, StateGraph

from agents.scheduler.nodes import (
    analyze_tasks,
    fetch_calendar_events,
    generate_response,
    schedule_tasks,
)
from agents.scheduler.state import SchedulerState


def compile_graph() -> StateGraph:
    """Scheduler Agentのワークフローグラフをコンパイル.

    ワークフロー:
    1. fetch_calendar_events: 今日のカレンダー予定を取得
    2. analyze_tasks: LLMでユーザー入力からタスクを抽出
    3. schedule_tasks: タスクをカレンダーに登録
    4. generate_response: ユーザーへの応答を生成

    Returns:
        StateGraph: コンパイル済みのグラフ
    """
    # グラフの構築
    workflow = StateGraph(SchedulerState)

    # ノードの追加
    workflow.add_node("fetch_calendar_events", fetch_calendar_events)
    workflow.add_node("analyze_tasks", analyze_tasks)
    workflow.add_node("schedule_tasks", schedule_tasks)
    workflow.add_node("generate_response", generate_response)

    # エッジの定義
    workflow.set_entry_point("fetch_calendar_events")
    workflow.add_edge("fetch_calendar_events", "analyze_tasks")
    workflow.add_edge("analyze_tasks", "schedule_tasks")
    workflow.add_edge("schedule_tasks", "generate_response")
    workflow.add_edge("generate_response", END)

    return workflow.compile()


# コンパイル済みグラフのエクスポート
app = compile_graph()
