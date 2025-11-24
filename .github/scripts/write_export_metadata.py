#!/usr/bin/env python3
"""Write export metadata JSON combining export outputs and prepare_icf results."""

from __future__ import annotations

import json
import os
from base64 import b64decode
from pathlib import Path
from typing import Any


def get_env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def resolved_path(dest_dir: Path, output_value: str, fallback_name: str) -> str:
    if not output_value:
        return str(dest_dir / fallback_name)
    candidate = Path(output_value)
    return str(dest_dir / candidate.name)


def parse_json_string(value: str, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def decode_overrides_present(encoded: str) -> bool:
    if not encoded:
        return False
    try:
        raw = b64decode(encoded).decode("utf-8")
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return bool(parsed)
        if isinstance(parsed, list):
            return bool(parsed)
        return bool(parsed)
    except (ValueError, json.JSONDecodeError):
        return False


def main() -> int:
    dest_dir = Path(get_env("DEST"))
    metadata_path = dest_dir / "export-metadata.json"

    artifact_name = get_env("ARTIFACT_NAME")
    artifact_path_output = get_env("ARTIFACT_PATH")
    artifact_zip_name = (
        Path(artifact_path_output).name if artifact_path_output else f"{artifact_name}.zip"
    )

    database_scripts = parse_json_string(get_env("DATABASE_SCRIPTS_JSON"), [])
    downloaded_files = parse_json_string(get_env("DOWNLOADED_FILES_JSON"), [])

    icf_template_status = get_env("ICF_TEMPLATE_STATUS", "missing")
    icf_template_file = get_env("ICF_TEMPLATE_FILE")
    icf_overrides_present = decode_overrides_present(
        get_env("ICF_OVERRIDES_JSON_B64")
    )

    data = {
        "artifact_name": artifact_name,
        "artifact_path": str(dest_dir / artifact_zip_name),
        "artifact_dir": str(dest_dir),
        "manifest_path": resolved_path(
            dest_dir, get_env("MANIFEST_PATH"), "export-manifest.json"
        ),
        "raw_response_path": resolved_path(
            dest_dir, get_env("RAW_RESPONSE_PATH"), "export-response.json"
        ),
        "deployment_uuid": get_env("DEPLOYMENT_UUID"),
        "deployment_status": get_env("DEPLOYMENT_STATUS"),
        "database_scripts": database_scripts,
        "plugins_zip": get_env("PLUGINS_ZIP"),
        "customization_file": get_env("CUSTOMIZATION_FILE"),
        "customization_template": get_env("CUSTOMIZATION_TEMPLATE"),
        "downloaded_files": downloaded_files,
        "icf_template_status": icf_template_status or "missing",
        "icf_template_file": icf_template_file or "",
        "icf_overrides_present": icf_overrides_present,
        "database_scripts_present": bool(database_scripts),
    }

    dest_dir.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
