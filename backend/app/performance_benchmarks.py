from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

BenchmarkScale = Literal["small", "medium", "large", "extra_large"]


@dataclass(frozen=True)
class BenchmarkCorpusProfile:
    corpus_id: str
    corpus_path: str
    scale_profile: BenchmarkScale
    description: str


_PROJECT_ROOT = Path(__file__).resolve().parents[2]


PERFORMANCE_BENCHMARK_CORPUS_SET: tuple[BenchmarkCorpusProfile, ...] = (
    BenchmarkCorpusProfile(
        corpus_id="shadow_slave_small",
        corpus_path="shadow_slave_chapter_1_to_95.txt",
        scale_profile="medium",
        description="Smoke and correctness baseline across a moderate corpus size.",
    ),
    BenchmarkCorpusProfile(
        corpus_id="novels_extra_large",
        corpus_path="novels_extra_chapter_0_to_22.txt",
        scale_profile="large",
        description="Large-scale profile used for optional traceability and future perf benchmarking.",
    ),
)


def resolve_benchmark_corpus_path(corpus_path: str | Path) -> Path:
    candidate = Path(corpus_path)
    if candidate.is_absolute():
        return candidate
    return (_PROJECT_ROOT / candidate).resolve()


def get_large_scale_benchmark_profiles() -> tuple[BenchmarkCorpusProfile, ...]:
    return tuple(
        profile for profile in PERFORMANCE_BENCHMARK_CORPUS_SET if profile.scale_profile == "large"
    )


def get_default_large_scale_benchmark() -> BenchmarkCorpusProfile:
    large_profiles = get_large_scale_benchmark_profiles()
    if not large_profiles:
        raise RuntimeError("No large-scale benchmark corpus profile is configured.")
    return large_profiles[0]
