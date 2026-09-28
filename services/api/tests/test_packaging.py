"""Every jidoka package a service imports must be declared, and installable by `make setup`.

Regression: services/api imported jidoka_knowledge, declared it nowhere, and `make setup` did not
install it. CI listed every package by hand, so CI stayed green while a fresh clone died on the
first import. A dependency that only exists in a CI step is not a declared dependency.

Lives here rather than in a package because it is the seam between the two services and the
Makefile, and no package owns that.
"""
import pathlib
import re
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[3]
SERVICES = ("services/api", "services/agent")
IMPORT = re.compile(r"^\s*(?:from|import)\s+(jidoka_\w+)", re.M)


def _declared(service: str) -> set[str]:
    data = tomllib.loads((ROOT / service / "pyproject.toml").read_text())
    return {re.split(r"[\[><=!]", d)[0].strip() for d in data["project"]["dependencies"]}


def _imported(service: str) -> set[str]:
    src = ROOT / service / "src"
    return {m.replace("_", "-")
            for f in src.rglob("*.py") for m in IMPORT.findall(f.read_text())}


def test_services_declare_every_jidoka_package_they_import():
    for service in SERVICES:
        undeclared = _imported(service) - _declared(service) - {f"jidoka-{service.split('/')[-1]}"}
        assert not undeclared, (
            f"{service} imports {sorted(undeclared)} but does not declare it — a fresh install "
            f"will fail on first import.")


def test_make_setup_installs_every_declared_jidoka_package():
    setup = next(line for line in (ROOT / "Makefile").read_text().splitlines()
                 if "pip install" in line)
    for service in SERVICES:
        for dep in sorted(d for d in _declared(service) if d.startswith("jidoka-")):
            assert f"packages/{dep}" in setup, (
                f"{dep} is a dependency of {service} but `make setup` does not install it; "
                f"pip cannot resolve a sibling editable package from PyPI.")
