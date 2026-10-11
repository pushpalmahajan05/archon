"""
Code Parser
Deterministic extraction of classes, functions, and imports from source files.
Uses AST for Python; regex-based for other languages.
"""
import ast
import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def parse_file(file_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse a single file and return extracted symbols.
    """
    lang = file_info.get("language", "unknown")
    content = file_info.get("content", "")
    path = file_info.get("path", "")

    result = {
        "path": path,
        "language": lang,
        "classes": [],
        "functions": [],
        "imports": [],
        "apis": [],
    }

    if lang == "python":
        result.update(_parse_python(content, path))
    elif lang in ("javascript", "typescript"):
        result.update(_parse_js_ts(content, path))
    elif lang == "java":
        result.update(_parse_java(content, path))
    elif lang in ("c", "cpp"):
        result.update(_parse_c(content, path))

    return result


def _parse_python(content: str, path: str) -> Dict:
    classes, functions, imports = [], [], []
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append({"name": node.name, "lineno": node.lineno})
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append({"name": node.name, "lineno": node.lineno})
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({"module": alias.name, "alias": alias.asname})
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imports.append({"module": module, "from": True, "level": node.level})
    except SyntaxError as e:
        logger.debug("Python parse error in %s: %s", path, e)
    return {"classes": classes, "functions": functions, "imports": imports}


def _parse_js_ts(content: str, path: str) -> Dict:
    classes, functions, imports = [], [], []

    # Classes
    for m in re.finditer(r"class\s+(\w+)", content):
        classes.append({"name": m.group(1), "lineno": content[: m.start()].count("\n") + 1})

    # Functions (including arrow functions assigned to const/let/var)
    for m in re.finditer(
        r"(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\()", content
    ):
        name = m.group(1) or m.group(2)
        if name:
            functions.append({"name": name, "lineno": content[: m.start()].count("\n") + 1})

    # Imports
    for m in re.finditer(r'import\s+.*?\s+from\s+["\']([^"\']+)["\']', content):
        imports.append({"module": m.group(1)})
    for m in re.finditer(r'require\s*\(\s*["\']([^"\']+)["\']\s*\)', content):
        imports.append({"module": m.group(1)})

    return {"classes": classes, "functions": functions, "imports": imports}


def _parse_java(content: str, path: str) -> Dict:
    classes, functions, imports = [], [], []

    for m in re.finditer(r"(?:public|private|protected)?\s*(?:abstract\s+)?class\s+(\w+)", content):
        classes.append({"name": m.group(1), "lineno": content[: m.start()].count("\n") + 1})

    for m in re.finditer(
        r"(?:public|private|protected)\s+(?:static\s+)?(?:\w+\s+)+(\w+)\s*\(", content
    ):
        functions.append({"name": m.group(1), "lineno": content[: m.start()].count("\n") + 1})

    for m in re.finditer(r"import\s+([\w.]+);", content):
        imports.append({"module": m.group(1)})

    return {"classes": classes, "functions": functions, "imports": imports}


def _parse_c(content: str, path: str) -> Dict:
    classes, functions, imports = [], [], []

    # Struct definitions (e.g., struct Batch { or typedef struct Batch {)
    for m in re.finditer(r"(?:typedef\s+)?struct\s+(\w+)", content):
        classes.append({"name": m.group(1), "lineno": content[: m.start()].count("\n") + 1})

    # C Function definitions: return_type func_name(params) {
    # Handles pointers and basic return types, ignores control flow keywords
    pattern = r"^[ \t]*(?:[a-zA-Z_][a-zA-Z0-9_* \t]+?\s+)+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^;{}]*\)\s*\{"
    for m in re.finditer(pattern, content, re.MULTILINE):
        name = m.group(1)
        if name not in ("if", "while", "for", "switch", "return"):
            functions.append({"name": name, "lineno": content[: m.start()].count("\n") + 1})

    # Includes: #include <header.h> or #include "header.h"
    for m in re.finditer(r'#include\s*[<"]([^>"]+)[>"]', content):
        imports.append({"module": m.group(1)})

    return {"classes": classes, "functions": functions, "imports": imports}


def chunk_file_content(file_info: Dict[str, Any], chunk_size: int = 400) -> List[Dict[str, Any]]:
    """
    Split a file's content into overlapping chunks for vector indexing.
    """
    content = file_info.get("content", "")
    path = file_info.get("path", "")
    language = file_info.get("language", "unknown")
    repo = file_info.get("repository", "")

    lines = content.split("\n")
    chunks = []
    step = chunk_size - 50  # 50-line overlap

    for start in range(0, max(len(lines), 1), step):
        end = min(start + chunk_size, len(lines))
        chunk_text = "\n".join(lines[start:end])
        if chunk_text.strip():
            chunks.append({
                "text": chunk_text,
                "repository": repo,
                "file": path,
                "type": "code",
                "language": language,
                "line_start": start + 1,
                "line_end": end,
            })
        if end >= len(lines):
            break

    return chunks
