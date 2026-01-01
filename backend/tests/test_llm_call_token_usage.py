import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import clear_settings_cache
from app.database import get_session_factory, init_db, reset_engine
from app.main import app
from app.models import LLMCall, Project, ProviderQuota, Run
from app.services import llm_router, pipeline


os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_llm_call_token_usage.db"

def setup_module() -> None:
    clear_settings_cache()
    reset_engine()
    init_db()


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
            run_config={"provider_name": "openrouter", "max_calls_per_day": 10},
            input_text="The wind turned calm and the rain stopped.",
        )

        quota = session.query(ProviderQuota).filter(ProviderQuota.provider == "openrouter").one()
        call = session.query(LLMCall).filter(LLMCall.run_id == run.id).one()
        assert call.token_usage_estimate == 512
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
        assert quota.last_rate_limit_status == "provider_rate_limited"
        assert quota.last_rate_limit_status_at is not None
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
    finally:
        session.close()
