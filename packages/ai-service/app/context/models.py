"""模型上下文窗口注册表。

窗口值用于计算 Context Budget（模型最大上下文 - 预留输出 - 安全余量）。
默认值取自官方文档/公开资料，可通过环境变量 MODEL_CONTEXT_WINDOW_OVERRIDES
以 JSON 覆盖，例如：{"glm-4.7-flash": 200000, "gemini-3.7-flash": 1048576}
"""
import json

from ..config import settings

# provider 名 → 模型名 → 上下文窗口（token）
MODEL_CONTEXT_WINDOWS: dict[str, dict[str, int]] = {
    "glm": {
        "glm-4.7-flash": 200_000,
        "glm-4-flash-250414": 128_000,
        "glm-4.6v-flash": 128_000,
        "glm-4.1v-thinking-flash": 128_000,
        "glm-4v-flash": 128_000,
    },
    "gemini": {
        "gemini-3.7-flash": 1_000_000,
        "gemini-3.6-flash": 1_000_000,
        "gemini-3.5-flash": 1_000_000,
        "gemini-3.5-flash-lite": 1_000_000,
        "gemini-3.1-flash-lite": 1_000_000,
        "gemini-3-flash-preview": 1_000_000,
        "gemini-2.5-pro": 1_000_000,
        "gemini-2.5-flash": 1_000_000,
    },
}

_OVERRIDES: dict[str, int] | None = None


def _load_overrides() -> dict[str, int]:
    """解析环境变量 MODEL_CONTEXT_WINDOW_OVERRIDES（JSON 对象）。"""
    raw = (settings.MODEL_CONTEXT_WINDOW_OVERRIDES or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {}
        return {
            str(k): int(v)
            for k, v in data.items()
            if isinstance(v, (int, float)) and int(v) > 0
        }
    except Exception:
        return {}


def get_context_window(provider_name: str, model: str | None) -> int:
    """查询某 provider 某模型的上下文窗口；未知时回落默认窗口。"""
    global _OVERRIDES
    if _OVERRIDES is None:
        _OVERRIDES = _load_overrides()
    if model:
        if model in _OVERRIDES:
            return _OVERRIDES[model]
        win = MODEL_CONTEXT_WINDOWS.get(provider_name, {}).get(model)
        if win:
            return win
    return settings.CONTEXT_DEFAULT_WINDOW
