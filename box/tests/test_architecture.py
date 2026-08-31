"""Guards the one structural rule this codebase has.

`box.api` is the interface: HTTP, auth, the dashboard. Everything else is the
box — scheduling, rendering, hardware — and must stay importable without a web
framework present. That keeps the core testable in isolation and makes it
possible to drive the box from something other than HTTP later.

The rule: **api may import the core; the core may never import api.**
"""

import ast
import pathlib
import subprocess
import sys
import textwrap

import pytest

PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "src" / "box"

#: Modules allowed to depend on the web framework.
INTERFACE = PACKAGE / "api"

WEB_FRAMEWORKS = {"fastapi", "starlette", "uvicorn"}


def core_modules() -> list[pathlib.Path]:
    return sorted(
        p
        for p in PACKAGE.rglob("*.py")
        if INTERFACE not in p.parents
        # __main__ boots the server, so it is allowed to know about uvicorn.
        and p.name != "__main__.py"
    )


def imported_roots(path: pathlib.Path) -> set[str]:
    """Top-level names imported by a module, absolute imports only."""
    tree = ast.parse(path.read_text(), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_there_are_core_modules_to_check():
    assert len(core_modules()) > 10, "sanity: the scan found the package"


@pytest.mark.parametrize("module", core_modules(), ids=lambda p: p.name)
def test_core_does_not_import_a_web_framework(module):
    leaked = imported_roots(module) & WEB_FRAMEWORKS
    assert not leaked, (
        f"{module.relative_to(PACKAGE)} imports {sorted(leaked)}. "
        "HTTP concerns belong in box.api."
    )


@pytest.mark.parametrize("module", core_modules(), ids=lambda p: p.name)
def test_core_does_not_import_the_api_package(module):
    """A relative `from ..api import ...` would invert the dependency."""
    source = module.read_text()
    assert "from box.api" not in source
    assert "import box.api" not in source
    assert ".api import" not in source, "relative import of the interface layer"


def test_the_interface_layer_actually_uses_a_framework():
    """If this fails, the rule above is passing vacuously."""
    found = set()
    for path in INTERFACE.rglob("*.py"):
        found |= imported_roots(path) & WEB_FRAMEWORKS
    assert found, "expected box.api to import a web framework"


def test_core_imports_with_no_web_framework_available():
    """Prove the rule in a clean interpreter, not just by reading imports.

    Runs in a subprocess with fastapi and starlette blocked at import time. Doing
    this in-process would mean reloading modules, which rebuilds the pydantic
    classes that `build_scene` matches on by identity and corrupts every test
    that runs afterwards.
    """
    program = textwrap.dedent(
        """
        import sys

        BLOCKED = {"fastapi", "starlette", "uvicorn"}

        class Blocker:
            def find_spec(self, name, path=None, target=None):
                if name.split(".")[0] in BLOCKED:
                    raise ImportError(f"blocked for this test: {name}")
                return None

        sys.meta_path.insert(0, Blocker())

        import box.events
        import box.render
        import box.scheduler
        import box.sources
        import box.state

        assert not BLOCKED & set(sys.modules), "a web framework was imported"
        print("core imported cleanly")
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", program], capture_output=True, text=True
    )
    assert result.returncode == 0, (
        f"core failed to import without a web framework:\n{result.stderr}"
    )
    assert "core imported cleanly" in result.stdout
