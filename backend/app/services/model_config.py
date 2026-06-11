"""
User-editable model provider configuration.
"""

from app.config import settings
from app.database import get_db_connection, init_db


SETTING_KEYS = {
    "chat.api_base": lambda: settings.OPENAI_API_BASE,
    "chat.api_key": lambda: settings.OPENAI_API_KEY,
    "chat.model": lambda: settings.MODEL_NAME,
    "chat.thinking_enabled": lambda: "false",
    "chat.reasoning_effort": lambda: "high",
    "embedding.api_base": lambda: settings.EMBEDDING_API_BASE,
    "embedding.api_key": lambda: settings.EMBEDDING_API_KEY,
    "embedding.model": lambda: settings.EMBEDDING_MODEL,
    "rerank.enabled": lambda: "true" if settings.RERANK_ENABLED else "false",
    "rerank.model": lambda: settings.RERANK_MODEL,
    "rerank.candidates": lambda: str(settings.RERANK_CANDIDATES),
    "rerank.top_n": lambda: str(settings.RERANK_TOP_N),
}


def get_model_config() -> dict:
    """Return stored model config with environment settings as defaults."""
    defaults = {key: get_default() for key, get_default in SETTING_KEYS.items()}

    try:
        init_db()
        conn = get_db_connection()
        rows = conn.execute(
            "SELECT key, value FROM app_settings WHERE key IN ({})".format(
                ",".join("?" for _ in SETTING_KEYS)
            ),
            tuple(SETTING_KEYS.keys()),
        ).fetchall()
        conn.close()
    except Exception:
        rows = []

    values = defaults.copy()
    values.update({row["key"]: row["value"] for row in rows})
    return {
        "chat": {
            "api_base": values["chat.api_base"],
            "api_key": values["chat.api_key"],
            "model": values["chat.model"],
            "thinking_enabled": str(values["chat.thinking_enabled"]).lower() in {"1", "true", "yes", "on"},
            "reasoning_effort": values["chat.reasoning_effort"] or "high",
        },
        "embedding": {
            "api_base": values["embedding.api_base"],
            "api_key": values["embedding.api_key"],
            "model": values["embedding.model"],
        },
        "rerank": {
            "enabled": str(values["rerank.enabled"]).lower() in {"1", "true", "yes", "on"},
            "model": values["rerank.model"],
            "candidates": int(values["rerank.candidates"] or 30),
            "top_n": int(values["rerank.top_n"] or 8),
        },
    }


def save_model_config(config: dict) -> dict:
    """Persist model config and return the saved effective values."""
    init_db()
    values = {
        "chat.api_base": config["chat"]["api_base"].strip(),
        "chat.api_key": config["chat"]["api_key"].strip(),
        "chat.model": config["chat"]["model"].strip(),
        "chat.thinking_enabled": "false",
        "chat.reasoning_effort": config["chat"].get("reasoning_effort", "high").strip() or "high",
        "embedding.api_base": config["embedding"]["api_base"].strip(),
        "embedding.api_key": config["embedding"]["api_key"].strip(),
        "embedding.model": config["embedding"]["model"].strip(),
        "rerank.enabled": "true" if config.get("rerank", {}).get("enabled") else "false",
        "rerank.model": config.get("rerank", {}).get("model", settings.RERANK_MODEL).strip(),
        "rerank.candidates": str(config.get("rerank", {}).get("candidates", settings.RERANK_CANDIDATES)),
        "rerank.top_n": str(config.get("rerank", {}).get("top_n", settings.RERANK_TOP_N)),
    }

    conn = get_db_connection()
    cursor = conn.cursor()
    for key, value in values.items():
        cursor.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, value),
        )
    conn.commit()
    conn.close()
    return get_model_config()
