"""Activity category normalization and meta-category mapping."""

from __future__ import annotations

# Canonical activity categories and their aliases
ACTIVITY_ALIASES: dict[str, list[str]] = {
    "プログラミング": ["コーディング", "開発", "プログラミングと会話", "コード書き"],
    "YouTube視聴": ["動画視聴", "YouTube", "YouTube閲覧"],
    "ブラウジング": ["ウェブ閲覧", "Web閲覧", "ネットサーフィン", "インターネット"],
    "チャット": ["メッセージ", "メッセージング", "LINE", "Slack", "Discord"],
    "SNS": ["Twitter", "X閲覧", "Instagram", "SNS閲覧", "ソーシャルメディア"],
    "ゲーム": ["ゲームプレイ", "ゲーム中"],
    "休憩": ["リラックス", "休息"],
    "離席": ["不在", "席外し"],
    "ドキュメント閲覧": ["ドキュメント", "資料閲覧", "PDF閲覧"],
    "コンテンツ制作": ["コンテンツ作成", "ブログ執筆", "記事作成"],
    "会話": ["通話", "電話", "ビデオ通話", "ミーティング"],
    "読書": ["本を読む", "電子書籍"],
    "音楽": ["音楽鑑賞", "音楽再生"],
    "食事": ["食事中", "ご飯"],
}

# Meta-categories for productivity scoring
META_CATEGORIES: dict[str, list[str]] = {
    "focus": ["プログラミング", "ドキュメント閲覧", "コンテンツ制作", "読書"],
    "communication": ["チャット", "会話"],
    "entertainment": ["YouTube視聴", "ゲーム", "SNS", "音楽"],
    "browsing": ["ブラウジング"],
    "break": ["休憩", "離席", "食事"],
}


def _build_alias_map() -> dict[str, str]:
    """Build a reverse map from alias to canonical name."""
    alias_map: dict[str, str] = {}
    for canonical, aliases in ACTIVITY_ALIASES.items():
        alias_map[canonical.lower()] = canonical
        for alias in aliases:
            alias_map[alias.lower()] = canonical
    return alias_map


_ALIAS_MAP = _build_alias_map()


def normalize_activity(raw: str) -> str:
    """Normalize an activity name to its canonical form.

    Returns the canonical category if a match is found, otherwise returns
    the original string (allowing new categories to emerge).
    """
    if not raw:
        return raw
    key = raw.strip().lower()
    return _ALIAS_MAP.get(key, raw.strip())


def get_meta_category(activity: str) -> str:
    """Get the meta-category for a given activity.

    Returns 'other' if no meta-category is found.
    """
    normalized = normalize_activity(activity)
    for meta, activities in META_CATEGORIES.items():
        if normalized in activities:
            return meta
    return "other"


def get_canonical_categories() -> list[str]:
    """Return list of all canonical activity category names."""
    return list(ACTIVITY_ALIASES.keys())
