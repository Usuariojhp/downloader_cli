"""Tests de higiene del empaquetado.

Estos fallos no los detecta la suite normal: solo aparecen al instalar en un
entorno limpio. Comprueban que las dependencias declaradas en pyproject.toml
se corresponden con lo que el código importa de verdad.
"""

import ast
import re
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "media_dl"


def _module_name(distribution: str) -> str:
    """'pydantic-settings>=2.1.0' -> 'pydantic_settings' (nombre de importación)."""
    return re.split(r"[<>=!~\[; ]", distribution, maxsplit=1)[0].replace("-", "_").lower()


def _declared_dependencies() -> dict[str, str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    return {
        _module_name(re.split(r"[><=!\[]", dep)[0].strip()): dep
        for dep in data["project"]["dependencies"]
    }


def _top_level_imports() -> set[str]:
    """Módulos de primer nivel importados por el paquete (runtime y lazy)."""
    found: set[str] = set()
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                found.add(node.module.split(".")[0])
    return found


def _optional_extras() -> set[str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    extras = data["project"].get("optional-dependencies", {})
    return {
        _module_name(re.split(r"[><=!\[ ]", dep)[0]) for deps in extras.values() for dep in deps
    }


def _stdlib() -> set[str]:
    return set(sys.stdlib_module_names)


class TestDependencies:
    def test_no_missing_dependency(self):
        """Regresión: `httpx` se borró de las deps y el CLI no arrancaba.

        'import httpx' vive en tiktok_tikwn.py, así que hace falta en core.
        """
        declared = set(_declared_dependencies())
        optional = _optional_extras()
        missing = {
            module
            for module in _top_level_imports()
            if module not in declared
            and module not in optional
            and module not in _stdlib()
            and module != "media_dl"
        }

        assert not missing, f"Importados pero no declarados en pyproject: {sorted(missing)}"

    def test_declared_dependencies_are_imported(self):
        """Ninguna dependencia declarada debe estar sin usar."""
        imported = _top_level_imports()
        unused = {module for module in _declared_dependencies() if module not in imported}

        assert not unused, f"Declaradas pero nunca importadas: {sorted(unused)}"

    def test_httpx_is_available(self):
        """Si esto falla, falta httpx en el entorno de instalación."""
        import httpx  # noqa: F401


class TestPackagingMetadata:
    def test_license_expression_without_classifier(self):
        """PEP 639: un clasificador 'License ::' rompe la instalación."""
        data = tomllib.loads((ROOT / "pyproject.toml").read_text())
        classifiers = data["project"].get("classifiers", [])

        assert data["project"].get("license") == "MIT"
        assert not [c for c in classifiers if c.startswith("License ::")], (
            "Los clasificadores de licencia están obsoletos con PEP 639"
        )

    def test_py_typed_marker_exists(self):
        """Sin py.typed, mypy trata el propio paquete como sin tipos."""
        assert (SRC / "py.typed").is_file()

    def test_py_typed_is_packaged(self):
        data = (ROOT / "pyproject.toml").read_text()
        assert "[tool.setuptools.package-data]" in data
        assert "py.typed" in data

    def test_console_script_points_to_wrapper(self):
        """El entry point debe usar cli_main para manejar errores con elegancia."""
        data = tomllib.loads((ROOT / "pyproject.toml").read_text())
        target = data["project"]["scripts"]["media-dl"]

        assert target.endswith(":cli_main")

    def test_optional_extras_are_not_core_dependencies(self):
        """spotdl y scdl son extras: no pueden ser dependencias obligatorias."""
        declared = set(_declared_dependencies())
        optional = _optional_extras()

        assert not (declared & optional), f"Extras olan en core: {declared & optional}"


class TestCIWorkflow:
    def test_workflow_exists_and_is_valid(self):
        import yaml

        path = ROOT / ".github" / "workflows" / "ci.yml"
        assert path.is_file(), "Falta el workflow de CI"

        workflow = yaml.safe_load(path.read_text())
        # PyYAML interpreta la clave 'on' como True (booleano YAML 1.1)
        triggers = workflow.get("on", workflow.get(True))

        assert "push" in triggers
        assert "pull_request" in triggers
        assert {"quality", "build"} <= set(workflow["jobs"])

    def test_workflow_runs_the_quality_gates(self):
        import yaml

        workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text())
        steps = workflow["jobs"]["quality"]["steps"]
        commands = "\n".join(s.get("run", "") for s in steps)

        for gate in ("pytest", "ruff check", "ruff format --check", "mypy src/"):
            assert gate in commands, f"CI no ejecuta {gate}"

    def test_coverage_threshold_is_reachable(self):
        """El umbral declarado no puede ser mayor que la cobertura real."""
        import xml.etree.ElementTree as ET

        report = ROOT / "coverage.xml"
        if not report.is_file():
            pytest.skip("Ejecuta pytest --cov antes de este test")

        rate = float(ET.parse(report).getroot().get("line-rate", 0)) * 100
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
        threshold = int(re.search(r"rate >= (\d+)", workflow).group(1))

        assert rate >= threshold, f"Cobertura {rate:.1f}% < umbral {threshold}%"


class TestPyInstallerSpec:
    """El spec es la única fuente de verdad de qué entra en el binario."""

    @pytest.fixture
    def excludes(self) -> list[str]:
        """Se lee el spec como Python de verdad, no con regex: si no, los
        nombres citados dentro de comentarios cuentan como exclusiones."""
        tree = ast.parse((ROOT / "build" / "media_dl.spec").read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "excludes":
                return list(ast.literal_eval(node.value))
        pytest.fail("El spec ya no tiene excludes=[...]")

    def test_excludes_a_real_dependency(self, excludes):
        """No se puede excluir algo que pyproject declara como dependencia.

        Excluir 'mutagen' rompía el binario entero: yt-dlp deja de reconocer
        los formatos de audio de YouTube Music y toda descarga de Spotify
        moría con un "known to use DRM protection" que no era cierto.
        """
        declared = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["dependencies"]
        names = {_module_name(dep) for dep in declared}

        clash = set(excludes) & names
        assert not clash, f"El spec excluye dependencias declaradas: {sorted(clash)}"

    def test_ci_build_installs_the_optional_extras(self):
        """El binario de la CI se construye con los extras, no solo con lo básico.

        Compilar con 'pip install -e .' deja fuera spotdl, así que el
        artefacto de cada push era un binario que no podía descargar de
        Spotify mientras el README lo daba por soportado.
        """
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert ".[spotify" in workflow, "La CI compila el binario sin el extra de Spotify"
        assert "media_dl.spec" in workflow

    def test_ci_checks_the_built_binary_in_strict_mode(self):
        """Con --strict, doctor falla si al binario le falta una extensión."""
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert "doctor --strict" in workflow

    def test_spec_collects_mutagen_explicitly(self):
        """mutagen se recoge a mano aunque su import sea estático.

        PyInstaller solo detecta sentencias de import. Si alguien cambia el
        de cover.py por un importlib.import_module para callar a mypy, el
        módulo desaparece del binario y las carátulas dejan de incrustarse
        sin ningún error visible. collect_all lo blinda.
        """
        spec = (ROOT / "build" / "media_dl.spec").read_text()
        assert '"mutagen"' in spec, "El spec debe recoger mutagen a mano"

    def test_entry_point_exists_on_disk(self):
        """La ruta que empaqueta el spec tiene que existir de verdad.

        ENTRY es os.path.join(ROOT, ...) y ROOT es la carpeta del propio spec,
        porque PyInstaller inyecta SPECPATH. Se resuelve igual aquí para poder
        comprobar el fichero sin lanzar PyInstaller.
        """
        tree = ast.parse((ROOT / "build" / "media_dl.spec").read_text())
        call = next(
            node.value
            for node in tree.body
            if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "ENTRY"
        )
        assert isinstance(call, ast.Call), "ENTRY ya no es una llamada a os.path.join"

        parts = [
            str(ROOT) if isinstance(arg, ast.Name) else ast.literal_eval(arg) for arg in call.args
        ]
        assert (Path(*parts)).is_file(), f"Entry point inexistente: {parts}"
