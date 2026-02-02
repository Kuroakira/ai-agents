"""外部API操作用ツール.

Notion APIの操作機能を提供。
"""

import os
import re
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

from notion_client import Client as NotionClient

from agents.memo.schema import MemoItem

TIMEZONE = ZoneInfo("Asia/Tokyo")


def get_notion_client() -> NotionClient:
    """Notionクライアントを取得.

    Returns:
        NotionClient: 初期化済みのNotionクライアント

    Raises:
        ValueError: MEMO_NOTION_TOKEN環境変数が設定されていない場合
    """
    api_key = os.environ.get("MEMO_NOTION_TOKEN")
    if not api_key:
        raise ValueError(
            "MEMO_NOTION_TOKEN環境変数が設定されていません。\n"
            "https://www.notion.so/my-integrations でAPIキーを取得してください。"
        )
    return NotionClient(auth=api_key)


def get_notion_database_id() -> str:
    """NotionデータベースIDを取得.

    環境変数からNotionデータベースIDを取得する。
    URLの場合はIDを抽出する。

    Returns:
        str: データベースID

    Raises:
        ValueError: MEMO_NOTION_DB_ID環境変数が設定されていない場合
    """
    db_id = os.environ.get("MEMO_NOTION_DB_ID")
    if not db_id:
        raise ValueError(
            "MEMO_NOTION_DB_ID環境変数が設定されていません。\n"
            "NotionデータベースのURLまたはIDを設定してください。"
        )

    # URLからIDを抽出（URLの場合）
    if "notion.so" in db_id:
        parts = db_id.split("/")
        for part in reversed(parts):
            if "?" in part:
                part = part.split("?")[0]
            clean_part = part.replace("-", "")
            if len(clean_part) == 32:
                return clean_part
        raise ValueError(f"NotionデータベースIDをURLから抽出できませんでした: {db_id}")

    return db_id.replace("-", "")


def get_existing_tags() -> list[str]:
    """Notionデータベースから既存のタグ一覧を取得.

    CategoryプロパティのMulti Selectオプションを取得する。

    Returns:
        list[str]: 既存タグのリスト
    """
    client = get_notion_client()
    database_id = get_notion_database_id()

    # データベースのスキーマを取得
    database = client.databases.retrieve(database_id=database_id)
    properties = database.get("properties", {})

    # Categoryプロパティからオプションを取得
    category_prop = properties.get("Category", {})
    if category_prop.get("type") == "multi_select":
        options = category_prop.get("multi_select", {}).get("options", [])
        return [opt.get("name", "") for opt in options if opt.get("name")]

    return []


def normalize_tag(tag: str) -> str:
    """タグを正規化.

    - 全角英数字 → 半角
    - 大文字 → 小文字
    - 前後の空白を削除

    Args:
        tag: 正規化するタグ

    Returns:
        str: 正規化されたタグ
    """
    # NFKCで正規化（全角→半角など）
    normalized = unicodedata.normalize("NFKC", tag)
    # 小文字に変換
    normalized = normalized.lower()
    # 前後の空白を削除
    normalized = normalized.strip()
    # 連続する空白を1つに
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def find_similar_tag(candidate: str, existing_tags: list[str]) -> str | None:
    """類似タグを検索.

    候補タグと既存タグを正規化して比較し、一致するものがあれば返す。

    Args:
        candidate: 候補タグ
        existing_tags: 既存タグのリスト

    Returns:
        str | None: 類似する既存タグ。見つからない場合はNone
    """
    normalized_candidate = normalize_tag(candidate)

    for existing in existing_tags:
        if normalize_tag(existing) == normalized_candidate:
            return existing

    return None


def match_tags(candidate_tags: list[str], existing_tags: list[str]) -> list[str]:
    """候補タグを既存タグとマッチング.

    類似タグがあれば既存のものを使用、なければ候補をそのまま使用。

    Args:
        candidate_tags: LLMが生成した候補タグ
        existing_tags: Notionから取得した既存タグ

    Returns:
        list[str]: マッチング後の最終タグリスト
    """
    final_tags = []
    for candidate in candidate_tags:
        similar = find_similar_tag(candidate, existing_tags)
        if similar:
            # 既存タグを使用
            if similar not in final_tags:
                final_tags.append(similar)
        else:
            # 新規タグ
            if candidate not in final_tags:
                final_tags.append(candidate)
    return final_tags


def create_memo_page(memo: MemoItem, tags: list[str]) -> str:
    """Notionデータベースにメモページを作成.

    Args:
        memo: 解析済みメモアイテム
        tags: 適用するタグのリスト

    Returns:
        str: 作成されたページのURL
    """
    client = get_notion_client()
    database_id = get_notion_database_id()

    # 現在時刻を取得
    now = datetime.now(TIMEZONE)

    # プロパティを構築
    properties = {
        "Name": {"title": [{"text": {"content": memo.topic}}]},
        "Category": {"multi_select": [{"name": tag} for tag in tags]},
        "Source": {"rich_text": [{"text": {"content": memo.source}}]},
        "Created": {"date": {"start": now.isoformat()}},
    }

    # ページの本文ブロックを構築
    blocks = _build_memo_blocks(memo)

    # データベースにページを追加
    page = client.pages.create(
        parent={"database_id": database_id},
        properties=properties,
        children=blocks,
    )

    return page.get("url", "")


def _build_memo_blocks(memo: MemoItem) -> list[dict]:
    """Notion Blocksを構築.

    Args:
        memo: メモアイテム

    Returns:
        list[dict]: Notionブロックリスト
    """
    blocks = []

    # Kindleの場合は引用ブロック
    if memo.is_kindle:
        blocks.append(
            {
                "object": "block",
                "type": "quote",
                "quote": {
                    "rich_text": [{"type": "text", "text": {"content": memo.content}}],
                },
            }
        )
        if memo.source:
            blocks.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {"content": f"— {memo.source}"},
                                "annotations": {"italic": True, "color": "gray"},
                            }
                        ],
                    },
                }
            )
    else:
        blocks.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": memo.content}}],
                },
            }
        )

    return blocks
