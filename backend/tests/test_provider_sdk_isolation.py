import ast
from pathlib import Path


FORBIDDEN_PROVIDER_IMPORTS = (
    "openai",
    "groq",
    "anthropic",
    "cohere",
    "litellm",
    "google.generativeai",
    "llama_cpp",
    "ollama",
    "langchain",
    "vertexai",
)


def _is_forbidden_import(module: str) -> bool:
    normalized = module.strip().lower()
    return any(
        normalized == forbidden
        or normalized.startswith(f"{forbidden}.")
        for forbidden in FORBIDDEN_PROVIDER_IMPORTS
    )


def _iter_backend_app_files() -> list[Path]:
    app_dir = Path(__file__).resolve().parent.parent / "app"
    return [
        path
        for path in app_dir.rglob("*.py")
        if not path.name.startswith(".") and "__pycache__" not in path.parts
    ]


def test_core_modules_do_not_import_provider_sdks_directly() -> None:
    violations: list[tuple[Path, str]] = []

    for file_path in _iter_backend_app_files():
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name and _is_forbidden_import(alias.name):
                        violations.append((file_path, f"import {alias.name}"))
            elif isinstance(node, ast.ImportFrom):
                module = node.module
                if module and _is_forbidden_import(module):
                    violations.append((file_path, f"from {module} import ..."))

    assert not violations, f"Forbidden direct provider imports found: {violations}"
