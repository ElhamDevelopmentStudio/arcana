#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Iterable

import requests
from dotenv import load_dotenv

DEFAULT_BASE_URL = "https://api.siliconflow.cn/v1"
DEFAULT_MODEL = "deepseek-ai/DeepSeek-V3"


@dataclass(frozen=True)
class LLMAssignment:
    speaker: str
    confidence: float


@dataclass(frozen=True)
class EmotionAssignment:
    label: str
    confidence: float


def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _post_chat(base_url: str, api_key: str, payload: dict, timeout_sec: float) -> dict:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    resp = requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers=headers,
        json=payload,
        timeout=timeout_sec,
    )
    resp.raise_for_status()
    return resp.json()


class OpenAICompatDirector:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        timeout_sec: float = 60.0,
        max_tokens: int = 512,
        temperature: float = 0.2,
        provider_name: str = "generic",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.provider_name = provider_name

    def assign(
        self,
        passage: str,
        quote_ids: list[str],
        candidates: list[str],
    ) -> dict[str, LLMAssignment]:
        if not quote_ids or not candidates:
            return {}

        system = (
            "You are a careful annotator. You must assign a speaker to each quoted span. "
            "Use ONLY the candidate names provided. If uncertain, use UNKNOWN. "
            "Return strict JSON with this schema: "
            "{\"assignments\": {\"Q1\": {\"speaker\": \"Name\", \"confidence\": 0.0}}}"
        )
        candidate_list = ", ".join(candidates)
        user = (
            f"Candidates: {candidate_list}\n"
            f"Quote IDs: {', '.join(quote_ids)}\n"
            "Passage with quotes:\n"
            f"{passage}\n"
            "Return JSON only."
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        data = _post_chat(self.base_url, self.api_key, payload, self.timeout_sec)
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = _extract_json(content) or {}
        assignments = parsed.get("assignments") if isinstance(parsed, dict) else None
        if not isinstance(assignments, dict):
            return {}

        results: dict[str, LLMAssignment] = {}
        for qid, entry in assignments.items():
            if qid not in quote_ids:
                continue
            if not isinstance(entry, dict):
                continue
            speaker = str(entry.get("speaker", "UNKNOWN")).strip()
            conf_raw = entry.get("confidence", 0.0)
            try:
                confidence = float(conf_raw)
            except (TypeError, ValueError):
                confidence = 0.0
            results[qid] = LLMAssignment(speaker=speaker, confidence=confidence)

        return results

    def classify_emotions(
        self,
        items: list[tuple[str, str]],
        labels: Iterable[str],
    ) -> dict[str, EmotionAssignment]:
        if not items:
            return {}
        label_list = ", ".join(labels)
        system = (
            "You are a careful annotator. For each segment id, choose exactly one emotion label "
            "from the provided list. Return strict JSON with this schema: "
            "{\"emotions\": {\"SEG_ID\": {\"label\": \"neutral\", \"confidence\": 0.0}}}."
        )
        user_lines = [f"{seg_id}: {text}" for seg_id, text in items]
        user = (
            f"Labels: {label_list}\n"
            "Segments:\n"
            + "\n".join(user_lines)
            + "\nReturn JSON only."
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        data = _post_chat(self.base_url, self.api_key, payload, self.timeout_sec)
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = _extract_json(content) or {}
        emotions = parsed.get("emotions") if isinstance(parsed, dict) else None
        if not isinstance(emotions, dict):
            return {}

        results: dict[str, EmotionAssignment] = {}
        for seg_id, entry in emotions.items():
            if not isinstance(entry, dict):
                continue
            label = str(entry.get("label", "neutral")).strip()
            conf_raw = entry.get("confidence", 0.0)
            try:
                confidence = float(conf_raw)
            except (TypeError, ValueError):
                confidence = 0.0
            results[str(seg_id)] = EmotionAssignment(label=label, confidence=confidence)
        return results


class LLMRouter:
    def __init__(
        self,
        providers: list[OpenAICompatDirector],
        max_calls: int | None = None,
        token_budgets: dict[str, int] | None = None,
    ) -> None:
        self.providers = providers
        self.max_calls = max_calls if max_calls and max_calls > 0 else None
        self.token_budgets = token_budgets or {}
        self.call_count = 0
        self.token_usage: dict[str, int] = {p.provider_name: 0 for p in providers}
        self.disabled: set[str] = set()

    def _estimate_tokens(self, text: str) -> int:
        return max(1, int(len(text) / 4))

    def _can_use(self, provider: OpenAICompatDirector, estimate: int) -> bool:
        if provider.provider_name in self.disabled:
            return False
        if self.max_calls is not None and self.call_count >= self.max_calls:
            return False
        budget = self.token_budgets.get(provider.provider_name)
        if budget is None:
            return True
        return (self.token_usage.get(provider.provider_name, 0) + estimate) <= budget

    def _record_use(self, provider: OpenAICompatDirector, estimate: int) -> None:
        self.call_count += 1
        self.token_usage[provider.provider_name] = self.token_usage.get(provider.provider_name, 0) + estimate

    def assign(
        self,
        passage: str,
        quote_ids: list[str],
        candidates: list[str],
    ) -> dict[str, LLMAssignment]:
        estimate = self._estimate_tokens(passage)
        for provider in self.providers:
            if not self._can_use(provider, estimate):
                continue
            try:
                result = provider.assign(passage, quote_ids, candidates)
                self._record_use(provider, estimate)
                return result
            except Exception:
                self.disabled.add(provider.provider_name)
                continue
        return {}

    def classify_emotions(
        self,
        items: list[tuple[str, str]],
        labels: Iterable[str],
    ) -> dict[str, EmotionAssignment]:
        joined = "\n".join(text for _sid, text in items)
        estimate = self._estimate_tokens(joined)
        for provider in self.providers:
            if not self._can_use(provider, estimate):
                continue
            try:
                result = provider.classify_emotions(items, labels)
                self._record_use(provider, estimate)
                return result
            except Exception:
                self.disabled.add(provider.provider_name)
                continue
        return {}


class SiliconFlowDirector(OpenAICompatDirector):
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        timeout_sec: float = 60.0,
        max_tokens: int = 512,
        temperature: float = 0.2,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout_sec=timeout_sec,
            max_tokens=max_tokens,
            temperature=temperature,
            provider_name="siliconflow",
        )


def load_siliconflow_from_env() -> SiliconFlowDirector | None:
    load_dotenv()
    api_key = os.getenv("SILICONFLOW_API_KEY") or os.getenv("SILICONCLOUD_API_KEY")
    if not api_key:
        return None
    base_url = os.getenv("SILICONFLOW_BASE_URL", DEFAULT_BASE_URL)
    model = os.getenv("SILICONFLOW_MODEL", DEFAULT_MODEL)
    try:
        max_tokens = int(os.getenv("SILICONFLOW_MAX_TOKENS", "512"))
    except ValueError:
        max_tokens = 512
    try:
        temperature = float(os.getenv("SILICONFLOW_TEMPERATURE", "0.2"))
    except ValueError:
        temperature = 0.2
    return SiliconFlowDirector(
        api_key=api_key,
        model=model,
        base_url=base_url,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def load_llm_router_from_env() -> LLMRouter | None:
    load_dotenv()
    provider_order = os.getenv("LLM_PROVIDER_ORDER", "siliconflow")
    order = [p.strip().lower() for p in provider_order.split(",") if p.strip()]
    providers: list[OpenAICompatDirector] = []

    def _budget_for(name: str) -> int | None:
        key = f"{name.upper()}_TOKEN_BUDGET"
        global_budget = os.getenv("LLM_TOKEN_BUDGET")
        raw = os.getenv(key) or global_budget
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    for name in order:
        if name == "siliconflow":
            api_key = os.getenv("SILICONFLOW_API_KEY") or os.getenv("SILICONCLOUD_API_KEY")
            if not api_key:
                continue
            base_url = os.getenv("SILICONFLOW_BASE_URL", DEFAULT_BASE_URL)
            model = os.getenv("SILICONFLOW_MODEL", DEFAULT_MODEL)
            providers.append(
                OpenAICompatDirector(
                    api_key=api_key,
                    model=model,
                    base_url=base_url,
                    provider_name="siliconflow",
                )
            )
        elif name == "groq":
            api_key = os.getenv("GROQ_API_KEY")
            base_url = os.getenv("GROQ_BASE_URL")
            model = os.getenv("GROQ_MODEL", "")
            if api_key and base_url and model:
                providers.append(
                    OpenAICompatDirector(
                        api_key=api_key,
                        model=model,
                        base_url=base_url,
                        provider_name="groq",
                    )
                )
        elif name == "openrouter":
            api_key = os.getenv("OPENROUTER_API_KEY")
            base_url = os.getenv("OPENROUTER_BASE_URL")
            model = os.getenv("OPENROUTER_MODEL", "")
            if api_key and base_url and model:
                providers.append(
                    OpenAICompatDirector(
                        api_key=api_key,
                        model=model,
                        base_url=base_url,
                        provider_name="openrouter",
                    )
                )

    if not providers:
        return None

    token_budgets = {p.provider_name: _budget_for(p.provider_name) for p in providers}
    token_budgets = {k: v for k, v in token_budgets.items() if v is not None}
    max_calls = None
    raw_max_calls = os.getenv("LLM_MAX_CALLS")
    if raw_max_calls:
        try:
            max_calls = int(raw_max_calls)
        except ValueError:
            max_calls = None

    return LLMRouter(providers=providers, max_calls=max_calls, token_budgets=token_budgets)
