#!/usr/bin/env python3
"""Identify and prepare ICF templates from exported artifacts."""

import base64
import json
import os
import sys
import zipfile
from collections import deque
from pathlib import Path


def log(message: str) -> None:
    print(message, flush=True)


def is_text_file(path: Path) -> bool:
    try:
        chunk = path.read_bytes()
        chunk.decode("utf-8")
        return True
    except (UnicodeDecodeError, OSError):
        return False


def prefer_key(path: Path) -> tuple[int, int, str]:
    suffix = path.suffix.lower()
    if suffix == ".properties":
        priority = 0
    elif suffix in {".txt", ".cfg"}:
        priority = 1
    else:
        priority = 2
    return priority, len(path.name), path.name


def emit_output(name: str, value: str | None) -> None:
    if not value:
        return
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def collect_candidates(root: Path) -> list[Path]:
    candidates: list[Path] = []

    if not root.exists():
        return candidates

    queue: deque[Path] = deque([root])
    seen_dirs: set[Path] = set()

    while queue:
        current = queue.popleft()
        if current in seen_dirs or not current.exists():
            continue
        seen_dirs.add(current)

        if current.is_file():
            continue

        for entry in current.iterdir():
            if entry.is_dir():
                queue.append(entry)
                continue

            if not entry.is_file():
                continue

            if zipfile.is_zipfile(entry):
                if entry.suffix:
                    target_dir = entry.with_suffix("")
                else:
                    target_dir = entry.parent / f"{entry.name}_extracted"
                if not target_dir.exists():
                    log(f"Extrayendo ZIP {entry} en {target_dir}")
                    target_dir.mkdir(parents=True, exist_ok=True)
                    with zipfile.ZipFile(entry) as archive:
                        archive.extractall(target_dir)
                queue.append(target_dir)
                continue

            candidates.append(entry)

    return candidates


def main() -> int:
    artifact_dir = os.environ.get("ARTIFACT_DIR", "")
    fallback_template = os.environ.get("FALLBACK_TEMPLATE_PATH", "")

    if not artifact_dir:
        log("::notice::ARTIFACT_DIR no definido; no se buscará plantilla.")
        artifact_root = None
    else:
        artifact_root = Path(artifact_dir)
        log(f"Buscando plantillas en {artifact_root}")

    candidates: list[Path] = []
    search_roots: list[Path] = []
    if artifact_root:
        search_roots.extend(
            [
                artifact_root / "customization-template",
                artifact_root / "customization",
                artifact_root,
            ]
        )

    for root in search_roots:
        candidates.extend(collect_candidates(root))

    allowed_suffixes = {
        ".properties",
        ".cfg",
        ".conf",
        ".ini",
        ".env",
        ".txt",
    }
    chosen: Path | None = None
    candidates = [
        path for path in candidates if path.is_file() and is_text_file(path)
    ]
    prioritized = [
        path for path in candidates if path.suffix.lower() in allowed_suffixes
    ]
    if prioritized:
        candidates = prioritized
    else:
        candidates = []
    status = "missing"
    if candidates:
        chosen = sorted(candidates, key=prefer_key)[0]
        log(f"Plantilla encontrada: {chosen}")
        status = "ready"
    else:
        log(
            "::notice::No se encontró plantilla en los artefactos descargados;"
            " el despliegue continuará sin overrides ICF."
        )

    content: str | None = None
    source_path: str | None = None
    if chosen:
        try:
            content = chosen.read_text(encoding="utf-8")
            source_path = str(chosen)
        except OSError as exc:
            log(f"::notice::No se pudo leer la plantilla {chosen}: {exc}")

    if content is None and fallback_template:
        fallback = Path(fallback_template)
        if fallback.is_file():
            log(f"Usando plantilla de fallback {fallback}")
            content = fallback.read_text(encoding="utf-8")
            source_path = str(fallback)
            if status == "missing":
                status = "fallback"

    if content is None:
        # Ya registramos un notice arriba explicando el motivo.
        emit_output("icf_template_status", status)
        return 0

    lines = content.splitlines()
    overrides: dict[str, str] = {}
    start_idx = 0
    for idx, line in enumerate(lines):
        if line.strip().startswith("##") and "----" in line:
            start_idx = idx + 1
            break
    for raw_line in lines[start_idx:]:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("##"):
            continue
        if stripped.startswith("#"):
            stripped = stripped.lstrip("#").strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        overrides[key.strip()] = value.strip()

    overrides_json = json.dumps(overrides, indent=2, ensure_ascii=False)

    if not overrides:
        if status == "ready":
            status = "empty"
        log(
            "::notice::La plantilla analizada"
            f" ({source_path}) no contiene pares clave=valor."
            " No se generarán overrides automáticos; completa la plantilla"
            " con entradas 'clave=valor' si deseas sugerir overrides."
        )
    else:
        log(
            "::notice::Se generaron overrides ICF a partir de la plantilla."
            " Revisa la issue automática para completar los pasos."
        )

    encoded_content = base64.b64encode(content.encode("utf-8")).decode("ascii")
    encoded_overrides = base64.b64encode(overrides_json.encode("utf-8")).decode(
        "ascii"
    )

    emit_output("icf_template_path", source_path)
    emit_output("icf_template_source", source_path)
    if source_path:
        emit_output("icf_template_file", Path(source_path).name)
    emit_output("icf_template_content_b64", encoded_content)
    emit_output("icf_overrides_json_b64", encoded_overrides)
    emit_output("icf_overrides_qa_json_b64", encoded_overrides)
    emit_output("icf_overrides_prod_json_b64", encoded_overrides)
    emit_output("icf_template_status", status)

    return 0


if __name__ == "__main__":
    sys.exit(main())
