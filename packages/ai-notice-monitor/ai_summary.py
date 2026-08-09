"""
ai_summary.py - AI 摘要模块（与爬虫解耦）

统一接口 summarize(title, content) -> NoticeSummary
通过 AI_PROVIDER 配置切换提供方：
    ollama   → 本地 Ollama（默认）
    deepseek → DeepSeek API
    openai   → OpenAI API

三者均走 OpenAI 兼容的 /chat/completions 接口，切换只改 .env 配置。
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

import requests

from config import AISummaryConfig

logger = logging.getLogger(__name__)

# 合法的 category / importance 取值
CATEGORIES = ("竞赛", "科研", "教务", "奖学金", "活动", "其他")
IMPORTANCE = ("high", "medium", "low")

# 默认摘要（AI 失败时兜底，保证邮件不中断）
_EMPTY_SUMMARY = {
    "title": "",
    "category": "其他",
    "importance": "medium",
    "deadline": "",
    "summary": "",
    "action": "",
}

_SYSTEM_PROMPT = """你是校园通知摘要助手。请分析用户提供的校园通知，输出 JSON。
要求：
- 只输出 JSON，不要任何其他文字
- category 只能是：竞赛 / 科研 / 教务 / 奖学金 / 活动 / 其他
- importance 只能是：high / medium / low
- deadline：通知中的截止时间，没有则留空
- summary：50字以内中文摘要
- action：作为学生应做的下一步动作（如"报名""关注""无需操作"）

JSON 格式：
{"title":"","category":"","importance":"","deadline":"","summary":"","action":""}"""


@dataclass(frozen=True)
class NoticeSummary:
    """AI 摘要结果。"""

    title: str
    category: str
    importance: str
    deadline: str
    summary: str
    action: str

    def to_dict(self) -> dict[str, str]:
        return {
            "title": self.title,
            "category": self.category,
            "importance": self.importance,
            "deadline": self.deadline,
            "summary": self.summary,
            "action": self.action,
        }


class SummaryError(Exception):
    """AI 摘要失败统一异常。"""


class AISummarizer:
    """通知摘要器，统一入口。"""

    def __init__(self, config: AISummaryConfig) -> None:
        self.config = config

    def summarize(self, title: str, content: str) -> NoticeSummary:
        """
        对通知生成摘要。AI 失败时抛 SummaryError（由上层决定降级处理）。
        """
        content = content[: self.config.max_content_chars]
        user_prompt = f"通知标题：{title}\n通知正文：\n{content or '（无正文）'}"
        try:
            raw = self._chat([{"role": "system", "content": _SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}])
        except SummaryError:
            raise
        except Exception as e:  # 网络/JSON 等意外
            raise SummaryError(f"AI 摘要异常: {e}") from e
        data = self._parse_json(raw)
        return self._to_summary(data, fallback_title=title)

    # ---------- 提供方调用 ----------

    def _chat(self, messages: list[dict[str, str]]) -> str:
        """
        调用摘要提供方。
        provider=aiapi   → 本平台 ai-service（统一 AI 网关，无需 api_key）
        provider=ollama  → 本地 Ollama（兼容端点优先，失败回退原生 /api/chat）
        provider=deepseek/openai → 各自官方 OpenAI 兼容端点
        """
        if self.config.provider == "aiapi":
            return self._chat_aiapi(messages)
        if self.config.provider == "ollama" and "/v1" in self.config.api_base:
            # 优先尝试 OpenAI 兼容端点（现代 Ollama 已内置）
            try:
                return self._chat_openai(messages)
            except SummaryError:
                # 兼容端点失败 → 回退原生 /api/chat
                return self._chat_ollama_native(messages)
        if self.config.provider in ("ollama", "deepseek", "openai"):
            return self._chat_openai(messages)
        raise SummaryError(f"未知 AI_PROVIDER: {self.config.provider}")

    def _chat_aiapi(self, messages: list[dict[str, str]]) -> str:
        """调用本平台 ai-service 的 /api/chat 接口（system+user 合并为单条消息）。"""
        system = messages[0]["content"] if messages and messages[0]["role"] == "system" else ""
        user_msg = messages[-1]["content"] if messages else ""
        full_prompt = f"{system}\n\n{user_msg}" if system else user_msg
        url = self.config.api_base.rstrip("/") + "/api/chat"
        headers = {
            "Content-Type": "application/json",
            "X-User-Id": "0",
            "X-Username": "system",
            "X-Role": "admin",
        }
        resp = requests.post(
            url, json={"message": full_prompt}, headers=headers, timeout=self.config.timeout
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise SummaryError(f"ai-service 返回错误: {data.get('error')}")
        answer = data.get("answer") or ""
        if not answer.strip():
            raise SummaryError("ai-service 返回空 answer")
        return answer

    def _chat_openai(self, messages: list[dict[str, str]]) -> str:
        """OpenAI 兼容 /chat/completions 接口。"""
        url = self.config.api_base.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": 0.2,
            "stream": False,
            "response_format": {"type": "json_object"},  # 部分模型支持，不支持则忽略
        }
        headers = {"Authorization": f"Bearer {self.config.api_key}"}
        resp = requests.post(url, json=payload, headers=headers, timeout=self.config.timeout)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def _chat_ollama_native(self, messages: list[dict[str, str]]) -> str:
        """Ollama 原生 /api/chat 接口（兼容端点不可用时的回退）。"""
        base = self.config.api_base.replace("/v1", "").rstrip("/")
        url = base + "/api/chat"
        payload = {"model": self.config.model, "messages": messages, "stream": False, "options": {"temperature": 0.2}}
        resp = requests.post(url, json=payload, timeout=self.config.timeout)
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"]

    # ---------- 结果解析 ----------

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any]:
        """从模型输出中提取 JSON（容忍多余文字、markdown 代码块）。"""
        text = raw.strip()
        # 去掉 markdown 代码块围栏
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        # 提取第一个 { ... } 块
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise SummaryError(f"AI 输出无 JSON: {raw[:200]}")
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as e:
            raise SummaryError(f"AI 输出 JSON 解析失败: {e}") from e

    @staticmethod
    def _to_summary(data: dict[str, Any], fallback_title: str) -> NoticeSummary:
        """规范化字段值，非法取值回落默认。"""
        category = data.get("category", "") if isinstance(data.get("category"), str) else ""
        importance = data.get("importance", "") if isinstance(data.get("importance"), str) else ""
        return NoticeSummary(
            title=str(data.get("title") or fallback_title),
            category=category if category in CATEGORIES else _EMPTY_SUMMARY["category"],
            importance=importance if importance in IMPORTANCE else _EMPTY_SUMMARY["importance"],
            deadline=str(data.get("deadline") or ""),
            summary=str(data.get("summary") or ""),
            action=str(data.get("action") or ""),
        )
