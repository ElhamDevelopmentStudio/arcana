import os
from pathlib import Path

from app.performance_benchmarks import (
    PERFORMANCE_BENCHMARK_CORPUS_SET,
    get_default_large_scale_benchmark,
    get_large_scale_benchmark_profiles,
    resolve_benchmark_corpus_path,
)

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_benchmark_set.db"


def test_performance_benchmark_set_includes_large_scale_profile() -> None:
    large_profiles = get_large_scale_benchmark_profiles()
    assert large_profiles
    assert any(profile.scale_profile == "large" for profile in PERFORMANCE_BENCHMARK_CORPUS_SET)

    default_large = get_default_large_scale_benchmark()
    assert default_large.scale_profile == "large"
    assert default_large.corpus_path


def test_performance_benchmark_set_paths_exist() -> None:
    corpus_paths = [resolve_benchmark_corpus_path(profile.corpus_path) for profile in PERFORMANCE_BENCHMARK_CORPUS_SET]
    assert corpus_paths

    for path in corpus_paths:
        assert path.is_file()

    payload = [path.name for path in corpus_paths]
    assert {"novels_extra_chapter_0_to_22.txt"}.issubset(set(payload))
