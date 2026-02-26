import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import LLMCall, Project, ProviderApiKeyQuota, ProviderQuota, ProviderToggle, Run
from app.services import llm_router, pipeline, quota as quota_service


os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_llm_call_token_usage.db"

def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()
    db_session = get_session_factory()()
    try:
        db_session.query(ProviderToggle).delete()
        db_session.commit()
    finally:
        db_session.close()


def teardown_module() -> None:
    reset_engine()
    clear_settings_cache()

    db_file = Path("test_nipe_llm_call_token_usage.db")
    if db_file.exists():
        db_file.unlink()


def _new_session():
    return get_session_factory()()


def test_pipeline_llm_probe_persists_token_usage_estimate(monkeypatch: object) -> None:
    session = _new_session()
    try:
        timestamp = datetime.now(timezone.utc)

        project = Project(title="Token Usage Probe Project")
        session.add(project)
        session.flush()

        run = Run(
            project_id=project.id,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        session.add(run)
        session.flush()

        class _FakeLLMRouter:
            def __init__(self, openrouter_base_url: str) -> None:
                self.openrouter_base_url = openrouter_base_url

            def call(
                self,
                request: llm_router.LLMRequest,
                provider_name: str,
                model_identifier: str,
                api_key: str | None,
            ) -> llm_router.LLMResponse:
                return llm_router.LLMResponse(
                    provider_used=provider_name,
                    model_identifier=model_identifier,
                    raw_output="ok",
                    parsed_output={"raw": "ok"},
                    confidence=None,
                    token_usage_estimate=512,
                    success_flag=True,
                    error_code=None,
                    rate_limit_reset_at=None,
                    timestamp=timestamp.isoformat(),
                )

        monkeypatch.setattr(
            pipeline,
            "get_provider_runtime_settings",
            lambda **kwargs: ("https://api.example.com", "gpt-test", "api-key"),
        )
        monkeypatch.setattr(pipeline, "LLMRouter", _FakeLLMRouter)

        pipeline._run_llm_probe(
            session=session,
            project=project,
            run=run,
            run_config={"provider_name": "openrouter", "max_calls_per_day": 10},
            input_text="The wind turned calm and the rain stopped.",
        )

        quota = session.query(ProviderQuota).filter(ProviderQuota.provider == "openrouter").one()
        call = session.query(LLMCall).filter(LLMCall.run_id == run.id).one()
        assert call.token_usage_estimate == 512
        assert call.model_identifier == "gpt-test"
        assert call.called_at is not None
        assert int(call.called_at.replace(tzinfo=timezone.utc).timestamp()) == int(timestamp.timestamp())
        assert call.success is True
        assert quota.last_successful_call_at is not None
    finally:
        session.close()


def test_pipeline_rate_limit_updates_provider_quota_status(monkeypatch: object) -> None:
    session = _new_session()
    try:
        project = Project(title="Provider Rate Limit Project")
        session.add(project)
        session.flush()

        run = Run(
            project_id=project.id,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        session.add(run)
        session.flush()

        class _RateLimitedLLMRouter:
            def __init__(self, openrouter_base_url: str) -> None:
                self.openrouter_base_url = openrouter_base_url

            def call(
                self,
                request: llm_router.LLMRequest,
                provider_name: str,
                model_identifier: str,
                api_key: str | None,
            ) -> llm_router.LLMResponse:
                return llm_router.LLMResponse(
                    provider_used=provider_name,
                    model_identifier=model_identifier,
                    raw_output="",
                    parsed_output={},
                    confidence=None,
                    token_usage_estimate=None,
                    success_flag=False,
                    error_code="rate_limit",
                    rate_limit_reset_at=None,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

        monkeypatch.setattr(
            pipeline,
            "get_provider_runtime_settings",
            lambda **kwargs: ("https://api.example.com", "gpt-test", "api-key"),
        )
        monkeypatch.setattr(
            pipeline,
            "get_provider_priority_order",
            lambda **kwargs: [],
        )
        monkeypatch.setattr(
            pipeline,
            "get_provider_api_keys",
            lambda **kwargs: ["openrouter-key-a"] if kwargs["provider_name"] == "openrouter" else [],
        )
        monkeypatch.setattr(pipeline, "LLMRouter", _RateLimitedLLMRouter)

        pipeline._run_llm_probe(
            session=session,
            project=project,
            run=run,
            run_config={"provider_name": "siliconflow", "max_calls_per_day": 10},
            input_text="The storm arrived before the dawn.",
        )

        session.flush()
        quota = session.query(ProviderQuota).filter(ProviderQuota.provider == "siliconflow").one()
        assert quota.last_rate_limit_status == "temporarily_unavailable"
        assert quota.last_rate_limit_status_at is not None
        assert quota.blocked is True
        assert quota.last_successful_call_at is None
        assert quota.last_rate_limit_reset_at is None
    finally:
        session.close()


def test_pipeline_rate_limit_reset_timestamp_is_saved_when_available(monkeypatch: object) -> None:
    session = _new_session()
    try:
        project = Project(title="Provider Rate Limit Reset Project")
        session.add(project)
        session.flush()

        run = Run(
            project_id=project.id,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        session.add(run)
        session.flush()

        reset_at = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(minutes=1)

        class _RateLimitedLLMRouterWithReset:
            def __init__(self, openrouter_base_url: str) -> None:
                self.openrouter_base_url = openrouter_base_url

            def call(
                self,
                request: llm_router.LLMRequest,
                provider_name: str,
                model_identifier: str,
                api_key: str | None,
            ) -> llm_router.LLMResponse:
                return llm_router.LLMResponse(
                    provider_used=provider_name,
                    model_identifier=model_identifier,
                    raw_output="",
                    parsed_output={},
                    confidence=None,
                    token_usage_estimate=None,
                    success_flag=False,
                    error_code="rate_limit",
                    rate_limit_reset_at=reset_at,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

        monkeypatch.setattr(
            pipeline,
            "get_provider_runtime_settings",
            lambda **kwargs: ("https://api.example.com", "gpt-test", "api-key"),
        )
        monkeypatch.setattr(pipeline, "LLMRouter", _RateLimitedLLMRouterWithReset)

        pipeline._run_llm_probe(
            session=session,
            project=project,
            run=run,
            run_config={"provider_name": "openrouter", "max_calls_per_day": 10},
            input_text="The storm arrived before the dawn.",
        )

        quota = session.query(ProviderQuota).filter(ProviderQuota.provider == "openrouter").one()
        assert int(quota.last_rate_limit_reset_at.replace(tzinfo=timezone.utc).timestamp()) == int(reset_at.timestamp())
    finally:
        session.close()


def test_pipeline_rejects_unknown_provider_without_invoking_router(monkeypatch: object) -> None:
    session = _new_session()
    try:
        project = Project(title="Unknown Provider Guardrail Project")
        session.add(project)
        session.flush()

        run = Run(
            project_id=project.id,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        session.add(run)
        session.flush()

        call_count = {"value": 0}

        class _UnexpectedLLMRouter:
            def __init__(self, openrouter_base_url: str) -> None:
                self.openrouter_base_url = openrouter_base_url

            def call(
                self,
                request: llm_router.LLMRequest,
                provider_name: str,
                model_identifier: str,
                api_key: str | None,
            ) -> llm_router.LLMResponse:
                call_count["value"] += 1
                return llm_router.LLMResponse(
                    provider_used=provider_name,
                    model_identifier=model_identifier,
                    raw_output="",
                    parsed_output={},
                    confidence=None,
                    token_usage_estimate=None,
                    success_flag=True,
                    error_code=None,
                    rate_limit_reset_at=None,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

        monkeypatch.setattr(
            pipeline,
            "LLMRouter",
            _UnexpectedLLMRouter,
        )
        monkeypatch.setattr(
            pipeline,
            "get_provider_runtime_settings",
            lambda **kwargs: ("https://api.example.com", "gpt-test", "api-key"),
        )

        pipeline._run_llm_probe(
            session=session,
            project=project,
            run=run,
            run_config={"provider_name": "  not-a-real-provider  ", "max_calls_per_day": 10},
            input_text="This provider should never be called.",
        )

        assert call_count["value"] == 0

        calls = session.query(LLMCall).filter(LLMCall.run_id == run.id).all()
        assert len(calls) == 1
        assert calls[0].detail == "unsupported_provider"
        assert calls[0].request_count == 0
        assert calls[0].provider == "not-a-real-provider"
        assert session.query(ProviderQuota).filter(ProviderQuota.provider == "not-a-real-provider").one_or_none() is None
    finally:
        session.close()


def test_pipeline_normalizes_provider_name_before_quota_tracking(monkeypatch: object) -> None:
    session = _new_session()
    try:
        project = Project(title="Provider Normalization Guardrail Project")
        session.add(project)
        session.flush()

        run = Run(
            project_id=project.id,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        session.add(run)
        session.flush()

        class _FakeLLMRouter:
            def __init__(self, openrouter_base_url: str) -> None:
                self.openrouter_base_url = openrouter_base_url

            def call(
                self,
                request: llm_router.LLMRequest,
                provider_name: str,
                model_identifier: str,
                api_key: str | None,
            ) -> llm_router.LLMResponse:
                return llm_router.LLMResponse(
                    provider_used=provider_name,
                    model_identifier=model_identifier,
                    raw_output="ok",
                    parsed_output={"raw": "ok"},
                    confidence=None,
                    token_usage_estimate=128,
                    success_flag=True,
                    error_code=None,
                    rate_limit_reset_at=None,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

        monkeypatch.setattr(
            pipeline,
            "get_provider_runtime_settings",
            lambda **kwargs: ("https://api.example.com", "gpt-test", "api-key"),
        )
        monkeypatch.setattr(pipeline, "LLMRouter", _FakeLLMRouter)

        pipeline._run_llm_probe(
            session=session,
            project=project,
            run=run,
            run_config={"provider_name": " OpenRouter ", "max_calls_per_day": 10},
            input_text="Normalization should prevent provider bypass.",
        )

        quota = session.query(ProviderQuota).filter(ProviderQuota.provider == "openrouter").one_or_none()
        assert quota is not None
        assert quota.provider == "openrouter"
    finally:
        session.close()


def test_pipeline_stops_additional_llm_calls_after_provider_error(monkeypatch: object) -> None:
    session = _new_session()
    try:
        project = Project(title="Provider Rate Limit Stops Subsequent Calls")
        session.add(project)
        session.flush()

        run = Run(
            project_id=project.id,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        session.add(run)
        session.flush()

        call_count = {"value": 0}

        class _RateLimitedLLMRouter:
            def __init__(self, openrouter_base_url: str) -> None:
                self.openrouter_base_url = openrouter_base_url

            def call(
                self,
                request: llm_router.LLMRequest,
                provider_name: str,
                model_identifier: str,
                api_key: str | None,
            ) -> llm_router.LLMResponse:
                call_count["value"] += 1
                return llm_router.LLMResponse(
                    provider_used=provider_name,
                    model_identifier=model_identifier,
                    raw_output="",
                    parsed_output={},
                    confidence=None,
                    token_usage_estimate=None,
                    success_flag=False,
                    error_code="rate_limit",
                    rate_limit_reset_at=None,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

        monkeypatch.setattr(
            pipeline,
            "get_provider_runtime_settings",
            lambda **kwargs: ("https://api.example.com", "gpt-test", "api-key"),
        )
        monkeypatch.setattr(
            pipeline,
            "get_provider_priority_order",
            lambda **kwargs: [],
        )
        monkeypatch.setattr(
            pipeline,
            "get_provider_api_keys",
            lambda **kwargs: ["openrouter-key-a"] if kwargs["provider_name"] == "openrouter" else [],
        )
        monkeypatch.setattr(pipeline, "LLMRouter", _RateLimitedLLMRouter)

        pipeline._run_llm_probe(
            session=session,
            project=project,
            run=run,
            run_config={"provider_name": "openrouter", "max_calls_per_day": 10},
            input_text="The wind arrived before the storm.",
        )

        pipeline._run_llm_probe(
            session=session,
            project=project,
            run=run,
            run_config={"provider_name": "openrouter", "max_calls_per_day": 10},
            input_text="The storm arrived before the wind.",
        )

        assert call_count["value"] == 1

        calls = (
            session.query(LLMCall)
            .filter(LLMCall.run_id == run.id)
            .order_by(LLMCall.id.asc())
            .all()
        )
        assert len(calls) == 2
        assert calls[0].success is False
        assert calls[0].detail == "rate_limit"
        assert calls[1].detail == "quota_reached"

        quota = session.query(ProviderQuota).filter(ProviderQuota.provider == "openrouter").one()
        assert quota.blocked is True
    finally:
        session.close()


def test_pipeline_rotates_provider_keys_before_fallback(monkeypatch: object) -> None:
    session = _new_session()
    try:
        project = Project(title="Provider Key Rotation Project")
        session.add(project)
        session.flush()

        run = Run(
            project_id=project.id,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        session.add(run)
        session.flush()

        calls: list[str | None] = []

        class _RotatingLLMRouter:
            def __init__(self, openrouter_base_url: str) -> None:
                self.openrouter_base_url = openrouter_base_url

            def call(
                self,
                request: llm_router.LLMRequest,
                provider_name: str,
                model_identifier: str,
                api_key: str | None,
            ) -> llm_router.LLMResponse:
                calls.append(api_key)
                if api_key == "openrouter-key-a":
                    return llm_router.LLMResponse(
                        provider_used=provider_name,
                        model_identifier=model_identifier,
                        raw_output="",
                        parsed_output={},
                        confidence=None,
                        token_usage_estimate=20,
                        success_flag=False,
                        error_code="rate_limit",
                        rate_limit_reset_at=None,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    )

                return llm_router.LLMResponse(
                    provider_used=provider_name,
                    model_identifier=model_identifier,
                    raw_output="ok",
                    parsed_output={"raw": "ok"},
                    confidence=None,
                    token_usage_estimate=32,
                    success_flag=True,
                    error_code=None,
                    rate_limit_reset_at=None,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

        def _fake_provider_api_keys(*, settings: object, provider_name: str) -> list[str]:
            if provider_name == "openrouter":
                return ["openrouter-key-a", "openrouter-key-b"]
            return []

        monkeypatch.setattr(pipeline, "get_provider_api_keys", _fake_provider_api_keys)
        monkeypatch.setattr(
            pipeline,
            "get_provider_runtime_settings",
            lambda **kwargs: ("https://api.example.com", "gpt-test", "fallback-key"),
        )
        monkeypatch.setattr(pipeline, "LLMRouter", _RotatingLLMRouter)

        pipeline._run_llm_probe(
            session=session,
            project=project,
            run=run,
            run_config={"provider_name": "openrouter", "max_calls_per_day": 10},
            input_text="Probe should rotate keys on rate limit.",
        )

        call = session.query(LLMCall).filter(LLMCall.run_id == run.id).one()
        assert call.success is True
        assert call.provider == "openrouter"
        assert calls == ["openrouter-key-a", "openrouter-key-b"]

        provider_quotas = (
            session.query(ProviderQuota)
            .filter(ProviderQuota.provider == "openrouter")
            .order_by(ProviderQuota.id.asc())
            .all()
        )
        assert len(provider_quotas) == 1
        assert provider_quotas[0].calls_used == 2

        key_quotas = (
            session.query(ProviderApiKeyQuota)
            .filter(ProviderApiKeyQuota.provider == "openrouter")
            .order_by(ProviderApiKeyQuota.id.asc())
            .all()
        )
        assert len(key_quotas) == 2
        assert {row.provider_api_key for row in key_quotas} == {"openrouter-key-a", "openrouter-key-b"}
    finally:
        session.close()


def test_pipeline_falls_back_to_next_provider_after_all_keys_exhausted(monkeypatch: object) -> None:
    session = _new_session()
    try:
        project = Project(title="Provider Fallback Project")
        session.add(project)
        session.flush()

        run = Run(
            project_id=project.id,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        session.add(run)
        session.flush()

        calls: list[tuple[str, str | None]] = []

        class _ProviderFallbackLLMRouter:
            def __init__(self, openrouter_base_url: str) -> None:
                self.openrouter_base_url = openrouter_base_url

            def call(
                self,
                request: llm_router.LLMRequest,
                provider_name: str,
                model_identifier: str,
                api_key: str | None,
            ) -> llm_router.LLMResponse:
                calls.append((provider_name, api_key))
                if provider_name == "openrouter":
                    return llm_router.LLMResponse(
                        provider_used=provider_name,
                        model_identifier=model_identifier,
                        raw_output="",
                        parsed_output={},
                        confidence=None,
                        token_usage_estimate=None,
                        success_flag=False,
                        error_code="rate_limit",
                        rate_limit_reset_at=None,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    )

                return llm_router.LLMResponse(
                    provider_used=provider_name,
                    model_identifier=model_identifier,
                    raw_output="ok",
                    parsed_output={"raw": "ok"},
                    confidence=None,
                    token_usage_estimate=16,
                    success_flag=True,
                    error_code=None,
                    rate_limit_reset_at=None,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

        def _fake_provider_api_keys(*, settings: object, provider_name: str) -> list[str]:
            if provider_name == "openrouter":
                return ["openrouter-key-a", "openrouter-key-b"]
            if provider_name == "siliconflow":
                return ["siliconflow-key"]
            return []

        monkeypatch.setattr(pipeline, "get_provider_api_keys", _fake_provider_api_keys)
        monkeypatch.setattr(
            pipeline,
            "get_provider_runtime_settings",
            lambda **kwargs: ("https://api.example.com", "gpt-test", "fallback-key"),
        )
        monkeypatch.setattr(pipeline, "LLMRouter", _ProviderFallbackLLMRouter)

        pipeline._run_llm_probe(
            session=session,
            project=project,
            run=run,
            run_config={"provider_name": "openrouter", "max_calls_per_day": 10},
            input_text="Probe should fallback to the next provider.",
        )

        call = session.query(LLMCall).filter(LLMCall.run_id == run.id).one()
        assert call.success is True
        assert call.provider == "siliconflow"
        assert calls == [
            ("openrouter", "openrouter-key-a"),
            ("openrouter", "openrouter-key-b"),
            ("siliconflow", "siliconflow-key"),
        ]

        openrouter_quota = session.query(ProviderQuota).filter(ProviderQuota.provider == "openrouter").one()
        assert openrouter_quota.blocked is True
        assert openrouter_quota.last_rate_limit_status == "temporarily_unavailable"
        siliconflow_quota = session.query(ProviderQuota).filter(ProviderQuota.provider == "siliconflow").one_or_none()
        assert siliconflow_quota is not None
        assert siliconflow_quota.blocked is False
    finally:
        session.close()


def test_run_detail_and_export_expose_token_usage_estimate() -> None:
    session = _new_session()
    try:
        project = Project(title="Token Usage Surface Project")
        session.add(project)
        session.flush()

        run = Run(
            project_id=project.id,
            status="completed",
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )
        session.add(run)
        session.flush()

        session.add(
            LLMCall(
                run_id=run.id,
                provider="openrouter",
                task_type="sentiment_probe",
                success=True,
                request_count=3,
                token_usage_estimate=777,
                model_identifier="gpt-test",
                called_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                detail="probe_detail",
            )
        )
        session.commit()

        with TestClient(app) as client:
            detail_resp = client.get(f"/api/projects/{project.id}/runs/{run.id}")
            assert detail_resp.status_code == 200
            detail_calls = detail_resp.json()["llm_calls"]
            assert len(detail_calls) == 1
            assert detail_calls[0]["token_usage_estimate"] == 777

            manifest_resp = client.get(f"/api/projects/{project.id}/exports/{run.id}.json")
            assert manifest_resp.status_code == 200
            manifest = manifest_resp.json()["manifest"]
            manifest_calls = manifest["logs"]["llm_calls"]
            assert len(manifest_calls) == 1
            assert manifest_calls[0]["token_usage_estimate"] == 777
            assert manifest_calls[0]["model_identifier"] == "gpt-test"
            assert manifest_calls[0]["called_at"] == "2024-01-01T00:00:00+00:00"

            detail_calls = detail_resp.json()["llm_calls"]
            assert detail_calls[0]["model_identifier"] == "gpt-test"
            assert detail_calls[0]["called_at"] == "2024-01-01T00:00:00+00:00"
    finally:
        session.close()


def test_pipeline_stops_after_provider_quota_reached_and_recovers_next_day(monkeypatch: object) -> None:
    session = _new_session()
    try:
        project = Project(title="Provider Quota Exhaustion Recovery Project")
        session.add(project)
        session.flush()

        run = Run(
            project_id=project.id,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        session.add(run)
        session.flush()

        calls: list[str | None] = []

        class _SimpleLLMRouter:
            def __init__(self, openrouter_base_url: str) -> None:
                self.openrouter_base_url = openrouter_base_url

            def call(
                self,
                request: llm_router.LLMRequest,
                provider_name: str,
                model_identifier: str,
                api_key: str | None,
            ) -> llm_router.LLMResponse:
                calls.append(api_key)
                return llm_router.LLMResponse(
                    provider_used=provider_name,
                    model_identifier=model_identifier,
                    raw_output="ok",
                    parsed_output={"raw": "ok"},
                    confidence=None,
                    token_usage_estimate=5,
                    success_flag=True,
                    error_code=None,
                    rate_limit_reset_at=None,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

        fixed_day = datetime(2024, 1, 1, tzinfo=timezone.utc).date()

        class _TestDate:
            @staticmethod
            def today() -> object:
                return fixed_day

        monkeypatch.setattr(quota_service, "date", _TestDate)
        monkeypatch.setattr(
            pipeline,
            "get_provider_runtime_settings",
            lambda **kwargs: ("https://api.example.com", "gpt-test", "openrouter-key-a"),
        )
        monkeypatch.setattr(
            pipeline,
            "get_provider_priority_order",
            lambda **kwargs: [],
        )
        monkeypatch.setattr(
            pipeline,
            "get_provider_api_keys",
            lambda **kwargs: [],
        )
        monkeypatch.setattr(pipeline, "LLMRouter", _SimpleLLMRouter)

        pipeline._run_llm_probe(
            session=session,
            project=project,
            run=run,
            run_config={"provider_name": "openrouter", "max_calls_per_day": 1},
            input_text="The tide rolled in.",
        )

        assert calls == ["openrouter-key-a"]

        quota_rows = session.query(ProviderQuota).filter(ProviderQuota.provider == "openrouter").all()
        assert len(quota_rows) == 1
        assert quota_rows[0].calls_used == 1

        pipeline._run_llm_probe(
            session=session,
            project=project,
            run=run,
            run_config={"provider_name": "openrouter", "max_calls_per_day": 1},
            input_text="The tide rolled out.",
        )

        assert calls == ["openrouter-key-a"]

        call_records = (
            session.query(LLMCall)
            .filter(LLMCall.run_id == run.id)
            .order_by(LLMCall.id.asc())
            .all()
        )
        assert len(call_records) == 2
        assert call_records[0].success is True
        assert call_records[1].success is False
        assert call_records[1].detail == "quota_reached"

        class _NextDayDate:
            @staticmethod
            def today() -> object:
                return fixed_day + timedelta(days=1)

        monkeypatch.setattr(quota_service, "date", _NextDayDate)
        calls.clear()

        pipeline._run_llm_probe(
            session=session,
            project=project,
            run=run,
            run_config={"provider_name": "openrouter", "max_calls_per_day": 1},
            input_text="The tide rolled again.",
        )

        assert calls == ["openrouter-key-a"]
        call_records = (
            session.query(LLMCall)
            .filter(LLMCall.run_id == run.id)
            .order_by(LLMCall.id.asc())
            .all()
        )
        assert len(call_records) == 3
        assert call_records[2].success is True
        assert call_records[2].detail is None
    finally:
        session.close()
