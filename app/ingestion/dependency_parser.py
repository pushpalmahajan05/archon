"""
Dependency Parser
Extracts package dependencies from manifests:
  - requirements.txt
  - package.json
  - pom.xml
  - build.gradle
  - go.mod
  - Pipfile
  - pyproject.toml
  - docker-compose.yml / docker-compose.yaml
"""
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def parse_dependencies(repo_path: Path) -> Dict[str, Any]:
    """
    Scan the repository root for dependency manifests and extract packages.
    Returns a dict with keys for each manifest type found.
    """
    result: Dict[str, Any] = {
        "python": [],
        "nodejs": [],
        "java": [],
        "go": [],
        "docker_services": [],
        "docker_images": [],
    }

    # Python: requirements.txt, Pipfile, pyproject.toml
    for req_file in repo_path.rglob("requirements*.txt"):
        result["python"].extend(_parse_requirements_txt(req_file))

    pyproject = repo_path / "pyproject.toml"
    if pyproject.exists():
        result["python"].extend(_parse_pyproject_toml(pyproject))

    # Node.js: package.json
    for pkg_file in repo_path.rglob("package.json"):
        if "node_modules" not in str(pkg_file):
            result["nodejs"].extend(_parse_package_json(pkg_file))

    # Java: pom.xml
    for pom in repo_path.rglob("pom.xml"):
        result["java"].extend(_parse_pom_xml(pom))

    # Go: go.mod
    for gomod in repo_path.rglob("go.mod"):
        result["go"].extend(_parse_go_mod(gomod))

    # Docker Compose
    for compose in repo_path.rglob("docker-compose*.yml"):
        svc, imgs = _parse_docker_compose(compose)
        result["docker_services"].extend(svc)
        result["docker_images"].extend(imgs)
    for compose in repo_path.rglob("docker-compose*.yaml"):
        svc, imgs = _parse_docker_compose(compose)
        result["docker_services"].extend(svc)
        result["docker_images"].extend(imgs)

    return result


def _parse_requirements_txt(path: Path) -> List[Dict]:
    deps = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("-"):
                # Strip version specifiers
                name = re.split(r"[>=<!~\[]", line)[0].strip()
                version = line[len(name):].strip() or "*"
                if name:
                    deps.append({"name": name, "version": version, "source": str(path.name)})
    except Exception as e:
        logger.debug("Failed to parse %s: %s", path, e)
    return deps


def _parse_pyproject_toml(path: Path) -> List[Dict]:
    deps = []
    try:
        content = path.read_text(encoding="utf-8")
        # Extract [tool.poetry.dependencies] or [project.dependencies]
        for m in re.finditer(r'^\s*(\w[\w\-\.]+)\s*=', content, re.MULTILINE):
            name = m.group(1)
            if name not in ("python", "name", "version", "description"):
                deps.append({"name": name, "version": "*", "source": "pyproject.toml"})
    except Exception as e:
        logger.debug("Failed to parse pyproject.toml: %s", e)
    return deps


def _parse_package_json(path: Path) -> List[Dict]:
    deps = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        for section in ("dependencies", "devDependencies"):
            for name, version in data.get(section, {}).items():
                deps.append({"name": name, "version": version, "source": str(path.name)})
    except Exception as e:
        logger.debug("Failed to parse %s: %s", path, e)
    return deps


def _parse_pom_xml(path: Path) -> List[Dict]:
    deps = []
    try:
        content = path.read_text(encoding="utf-8")
        for m in re.finditer(
            r"<artifactId>(.*?)</artifactId>.*?<version>(.*?)</version>",
            content,
            re.DOTALL,
        ):
            deps.append({"name": m.group(1).strip(), "version": m.group(2).strip(), "source": "pom.xml"})
    except Exception as e:
        logger.debug("Failed to parse pom.xml: %s", e)
    return deps


def _parse_go_mod(path: Path) -> List[Dict]:
    deps = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s+([\w./\-]+)\s+(v[\d.]+)", line)
            if m:
                deps.append({"name": m.group(1), "version": m.group(2), "source": "go.mod"})
    except Exception as e:
        logger.debug("Failed to parse go.mod: %s", e)
    return deps


def _parse_docker_compose(path: Path):
    services, images = [], []
    try:
        import yaml  # optional
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        for svc_name, svc_conf in (data or {}).get("services", {}).items():
            services.append(svc_name)
            if svc_conf and "image" in svc_conf:
                images.append(svc_conf["image"])
    except Exception:
        # Fallback: regex
        try:
            content = path.read_text(encoding="utf-8")
            for m in re.finditer(r"^\s{2}(\w[\w\-]+):\s*$", content, re.MULTILINE):
                services.append(m.group(1))
            for m in re.finditer(r"image:\s*(.+)", content):
                images.append(m.group(1).strip())
        except Exception as e:
            logger.debug("Failed to parse docker-compose: %s", e)
    return services, images
