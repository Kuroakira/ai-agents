"""外部API操作用ツール.

Tavily検索APIとNotion APIの操作機能を提供。
"""

import os

from notion_client import Client as NotionClient
from tavily import TavilyClient

from agents.travel_concierge.state import (
    ResearchResult,
    TravelContext,
)


def is_day_trip(context: TravelContext) -> bool:
    """日帰り旅行かどうかを判定.

    Args:
        context: 旅行要件コンテキスト

    Returns:
        bool: 日帰りの場合True
    """
    if not context.timing:
        return False

    timing_lower = context.timing.lower()
    day_trip_keywords = [
        "日帰り",
        "ひがえり",
        "daytrip",
        "day trip",
        "日帰",
    ]
    return any(keyword in timing_lower for keyword in day_trip_keywords)


def get_tavily_client() -> TavilyClient:
    """Tavilyクライアントを取得.

    Returns:
        TavilyClient: 初期化済みのTavilyクライアント

    Raises:
        ValueError: TAVILY_API_KEY環境変数が設定されていない場合
    """
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise ValueError(
            "TAVILY_API_KEY環境変数が設定されていません。\n"
            "https://tavily.com/ でAPIキーを取得してください。"
        )
    return TavilyClient(api_key=api_key)


def get_notion_client() -> NotionClient:
    """Notionクライアントを取得.

    Returns:
        NotionClient: 初期化済みのNotionクライアント

    Raises:
        ValueError: NOTION_API_KEY環境変数が設定されていない場合
    """
    api_key = os.environ.get("NOTION_API_KEY")
    if not api_key:
        raise ValueError(
            "NOTION_API_KEY環境変数が設定されていません。\n"
            "https://www.notion.so/my-integrations でAPIキーを取得してください。"
        )
    return NotionClient(auth=api_key)


def get_user_location() -> str:
    """ユーザーの居住地を取得.

    環境変数から取得。未設定の場合は「東京」をデフォルトとする。

    Returns:
        str: ユーザーの居住地
    """
    return os.environ.get("USER_LOCATION", "東京")


def get_notion_database_id() -> str:
    """NotionデータベースIDを取得.

    環境変数からNotionデータベースIDを取得する。
    URLの場合はIDを抽出する。

    Returns:
        str: データベースID

    Raises:
        ValueError: NOTION_DATABASE_ID環境変数が設定されていない場合
    """
    db_id = os.environ.get("NOTION_DATABASE_ID")
    if not db_id:
        raise ValueError(
            "NOTION_DATABASE_ID環境変数が設定されていません。\n"
            "NotionデータベースのURLまたはIDを設定してください。"
        )

    # URLからIDを抽出（URLの場合）
    # 例: https://www.notion.so/xxx/abc123def456?v=... → abc123def456
    if "notion.so" in db_id:
        # URLの最後のパス部分を取得
        parts = db_id.split("/")
        for part in reversed(parts):
            if "?" in part:
                part = part.split("?")[0]
            # 32文字のIDを探す（ハイフンなし）
            clean_part = part.replace("-", "")
            if len(clean_part) == 32:
                return clean_part
        raise ValueError(f"NotionデータベースIDをURLから抽出できませんでした: {db_id}")

    return db_id.replace("-", "")


def search_timing_trends(context: TravelContext) -> list[dict]:
    """時期トレンドを検索.

    Args:
        context: 旅行要件コンテキスト

    Returns:
        list[dict]: 検索結果リスト
    """
    client = get_tavily_client()
    query = (
        f'"{context.destination}" 旅行 安い時期 ベストシーズン "{context.timing}" 比較'
    )

    response = client.search(
        query=query,
        search_depth="basic",
        max_results=5,
        include_answer=True,
    )

    return response.get("results", [])


def search_flight_prices(context: TravelContext, timing_hint: str = "") -> list[dict]:
    """フライト価格相場を検索.

    Args:
        context: 旅行要件コンテキスト
        timing_hint: 時期のヒント（前段の調査結果から）

    Returns:
        list[dict]: 検索結果リスト
    """
    client = get_tavily_client()
    timing = timing_hint if timing_hint else context.timing
    user_location = get_user_location()
    query = (
        f'site:google.com/travel "{user_location}" '
        f'"{context.destination}" "JAL" {timing} 往復 価格'
    )

    response = client.search(
        query=query,
        search_depth="basic",
        max_results=3,
        include_answer=True,
    )

    return response.get("results", [])


def search_accommodations(context: TravelContext) -> list[dict]:
    """宿泊施設を検索.

    Args:
        context: 旅行要件コンテキスト

    Returns:
        list[dict]: 検索結果リスト
    """
    client = get_tavily_client()
    constraints_str = " ".join(context.constraints) if context.constraints else ""

    # 子連れの場合は検索条件に追加
    family_hint = ""
    if context.travelers and context.travelers.children > 0:
        family_hint = "子連れ ファミリー"

    query = (
        f'"{context.destination}" {family_hint} {constraints_str} 旅館 ホテル おすすめ'
    )

    response = client.search(
        query=query,
        search_depth="advanced",
        max_results=5,
        include_answer=True,
    )

    return response.get("results", [])


def search_activities(context: TravelContext) -> list[dict]:
    """日帰り向けアクティビティ・スポットを検索.

    Args:
        context: 旅行要件コンテキスト

    Returns:
        list[dict]: 検索結果リスト
    """
    client = get_tavily_client()
    constraints_str = " ".join(context.constraints) if context.constraints else ""

    # 子連れの場合は検索条件に追加
    family_hint = ""
    if context.travelers and context.travelers.children > 0:
        family_hint = "子連れ ファミリー 子供"

    query = (
        f'"{context.destination}" {family_hint} {constraints_str} '
        f"日帰り 体験 アクティビティ スポット おすすめ"
    )

    response = client.search(
        query=query,
        search_depth="advanced",
        max_results=5,
        include_answer=True,
    )

    return response.get("results", [])


def search_day_trip_info(context: TravelContext) -> list[dict]:
    """日帰り旅行の基本情報を検索.

    Args:
        context: 旅行要件コンテキスト

    Returns:
        list[dict]: 検索結果リスト
    """
    client = get_tavily_client()
    user_location = get_user_location()

    query = (
        f'"{context.destination}" {user_location}から 日帰り '
        f"アクセス 所要時間 駐車場 おすすめ時期"
    )

    response = client.search(
        query=query,
        search_depth="basic",
        max_results=5,
        include_answer=True,
    )

    return response.get("results", [])


def create_notion_page(
    title: str,
    context: TravelContext,
    research: ResearchResult,
) -> str:
    """Notionデータベースにページを作成.

    Args:
        title: ページタイトル
        context: 旅行要件コンテキスト
        research: 調査結果

    Returns:
        str: 作成されたページのURL
    """
    client = get_notion_client()
    database_id = get_notion_database_id()

    # データベースにページを追加
    page = client.pages.create(
        parent={"database_id": database_id},
        properties={
            "Name": {"title": [{"text": {"content": title}}]},
        },
        children=_build_notion_blocks(context, research),
    )

    return page.get("url", "")


def _build_notion_blocks(
    context: TravelContext, research: ResearchResult
) -> list[dict]:
    """Notion Blocksを構築.

    Args:
        context: 旅行要件コンテキスト
        research: 調査結果

    Returns:
        list[dict]: Notionブロックリスト
    """
    blocks = []

    # 日帰りかどうかでアイコンを変更
    trip_icon = "🚗" if research.is_day_trip else "✈️"

    # サマリー（Callout）
    if research.summary:
        blocks.append(
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": [
                        {"type": "text", "text": {"content": research.summary}}
                    ],
                    "icon": {"emoji": trip_icon},
                },
            }
        )

    # 旅行条件
    blocks.append(
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "📋 旅行条件"}}],
            },
        }
    )

    travelers_text = ""
    if context.travelers:
        travelers_text = f"大人{context.travelers.adults}名"
        if context.travelers.children > 0:
            travelers_text += f"、子供{context.travelers.children}名"
        if context.travelers.notes:
            travelers_text += f"（{context.travelers.notes}）"

    blocks.append(
        {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": f"目的地: {context.destination}"},
                    }
                ],
            },
        }
    )
    blocks.append(
        {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [
                    {"type": "text", "text": {"content": f"時期: {context.timing}"}}
                ],
            },
        }
    )
    blocks.append(
        {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [
                    {"type": "text", "text": {"content": f"人数: {travelers_text}"}}
                ],
            },
        }
    )
    if context.constraints:
        blocks.append(
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": f"こだわり: {', '.join(context.constraints)}"
                            },
                        }
                    ],
                },
            }
        )

    # 時期・相場
    if research.timing_options:
        blocks.append(
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "📅 狙い目の時期と相場"}}
                    ],
                },
            }
        )

        for timing in research.timing_options:
            timing_text = f"**{timing.period}** - {timing.price_estimate}"
            if timing.advantages:
                timing_text += f"\n  メリット: {', '.join(timing.advantages)}"
            if timing.disadvantages:
                timing_text += f"\n  デメリット: {', '.join(timing.disadvantages)}"

            blocks.append(
                {
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [
                            {"type": "text", "text": {"content": timing_text}}
                        ],
                    },
                }
            )

    # 日帰りの場合: アクティビティ・スポット
    if research.is_day_trip and research.activities:
        blocks.append(
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "🎯 おすすめスポット・アクティビティ"}}
                    ],
                },
            }
        )

        for act in research.activities:
            act_text = f"**{act.name}**"
            if act.features:
                act_text += f"\n  特徴: {', '.join(act.features)}"
            if act.access:
                act_text += f"\n  🚃 アクセス: {act.access}"
            if act.price_hint:
                act_text += f"\n  💰 料金目安: {act.price_hint}"
            if act.recommendation:
                act_text += f"\n  💡 {act.recommendation}"
            if act.url:
                act_text += f"\n  🔗 {act.url}"

            blocks.append(
                {
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": act_text}}],
                    },
                }
            )

    # 宿泊旅行の場合: 宿泊施設
    elif not research.is_day_trip and research.accommodations:
        blocks.append(
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "🏨 おすすめ宿泊施設"}}
                    ],
                },
            }
        )

        for acc in research.accommodations:
            acc_text = f"**{acc.name}**"
            if acc.features:
                acc_text += f"\n  特徴: {', '.join(acc.features)}"
            if acc.recommendation:
                acc_text += f"\n  💡 {acc.recommendation}"
            if acc.url:
                acc_text += f"\n  🔗 {acc.url}"

            blocks.append(
                {
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": acc_text}}],
                    },
                }
            )

    return blocks
