#!/usr/bin/env python3
"""Create or update a GitHub Release summarising a deployment run."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from urllib import error, request


PLAN_LABELS = {
    "dev-to-qa": "Dev → QA",
    "dev-qa-prod": "Dev → QA → Prod",
    "qa-to-prod": "QA → Prod",
}

PLAN_TARGETS = {
    "dev-to-qa": ["qa"],
    "dev-qa-prod": ["qa", "prod"],
    "qa-to-prod": ["prod"],
}


def get_env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def sanitize(text: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", text)
    clean = re.sub(r"-+", "-", clean).strip("-")
    return clean or "run"


def status_icon(result: str) -> str:
    table = {
        "success": "✅",
        "skipped": "⚪",
        "cancelled": "⏭️",
        "failure": "❌",
    }
    return f"{table.get(result, 'ℹ️')} {result or 'unknown'}"


def github_request(
    method: str,
    endpoint: str,
    token: str,
    payload: dict | None = None,
    raise_on_404: bool = True,
) -> dict | None:
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    url = f"{api_url}{endpoint}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req) as resp:
            body = resp.read()
            return json.loads(body.decode("utf-8")) if body else {}
    except error.HTTPError as http_err:
        if http_err.code == 404 and not raise_on_404:
            return None
        detail = http_err.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub API {method} {endpoint} failed: {http_err.code} {http_err.reason} – {detail}"
        ) from http_err


def build_release_payload() -> tuple[str, str, str, dict]:
    token = get_env("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required")

    repository = get_env("GITHUB_REPOSITORY", get_env("REPOSITORY"))
    if not repository or "/" not in repository:
        raise RuntimeError("GITHUB_REPOSITORY is not set")

    deploy_kind = get_env("DEPLOY_KIND", "app")
    plan = get_env("PLAN")
    plan_label = PLAN_LABELS.get(plan, plan or "unknown plan")
    run_id = get_env("RUN_ID")
    run_number = get_env("RUN_NUMBER")
    run_url = get_env("RUN_URL")
    git_ref = get_env("GIT_REF")
    git_sha = get_env("GIT_SHA")
    git_ref_name = get_env("GIT_REF_NAME")

    app_name = get_env("APP_NAME")
    package_name = get_env("PACKAGE_NAME")

    artifact_name = get_env("ARTIFACT_NAME")
    artifact_dir = get_env("ARTIFACT_DIR")
    metadata_path = get_env("METADATA_PATH")
    package_artifact_name = get_env("PACKAGE_ARTIFACT_NAME")
    package_file_name = get_env("PACKAGE_FILE_NAME")
    package_status = get_env("PACKAGE_STATUS")
    icf_status = get_env("ICF_TEMPLATE_STATUS")
    icf_file = get_env("ICF_TEMPLATE_FILE")

    promote_qa = get_env("PROMOTE_QA_RESULT", "")
    promote_prod_after_qa = get_env("PROMOTE_PROD_AFTER_QA_RESULT", "")
    promote_prod_from_qa = get_env("PROMOTE_PROD_FROM_QA_RESULT", "")

    targets = PLAN_TARGETS.get(plan, [])
    env_status = []
    for target in targets:
        if target == "qa":
            env_status.append(f"- QA: {status_icon(promote_qa)}")
        elif target == "prod":
            prod_result = promote_prod_after_qa or promote_prod_from_qa
            env_status.append(f"- Prod: {status_icon(prod_result)}")

    tag_root = "deploy-app"
    name_suffix = plan_label
    if deploy_kind == "package":
        slug = sanitize(package_name or "package")
        tag_root = f"deploy-package-{slug}"
        name_prefix = f"Deploy Package · {package_name or 'unknown package'}"
    else:
        slug = sanitize(app_name or "app")
        tag_root = f"deploy-app-{slug}"
        name_prefix = "Deploy App"

    tag_name = f"{tag_root}-{run_id or run_number or 'run'}"
    release_name = f"{name_prefix} · {name_suffix}"

    summary_lines = [
        f"- Run: [{run_number or run_id}]({run_url})" if run_url else f"- Run: {run_number or run_id}",
        f"- Plan: `{plan or 'unknown'}` ({plan_label})",
        f"- Tipo: {deploy_kind}",
    ]
    trigger_actor = get_env("TRIGGERING_ACTOR") or get_env("TRIGGER_ACTOR") or get_env("INITIATED_BY")
    run_started_at_raw = get_env("RUN_STARTED_AT")

    def format_runtime(value: str) -> str:
        if not value:
            return ""
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
        local_dt = dt.astimezone()
        return local_dt.strftime("%Y-%m-%d %H:%M:%S %Z")

    if trigger_actor:
        summary_lines.append(f"- Triggered by: @{trigger_actor}")
    started_at_fmt = format_runtime(run_started_at_raw)
    if started_at_fmt:
        summary_lines.append(f"- Started at: {started_at_fmt}")

    if app_name:
        summary_lines.append(f"- App: {app_name}")
    if deploy_kind == "package" and package_name:
        summary_lines.append(f"- Package: {package_name}")
    if git_ref:
        summary_lines.append(f"- Ref: `{git_ref}` @ {git_sha[:7] if git_sha else ''}")

    def derive_branch(ref_name: str, ref: str) -> str:
        if ref_name:
            return ref_name
        if ref.startswith("refs/heads/"):
            return ref.split("/", 2)[-1]
        return ref or "main"

    branch_name = derive_branch(git_ref_name, git_ref)
    repo_url = f"https://github.com/{repository}"

    def tree_link(path: str) -> str:
        cleaned = path.lstrip("./")
        return f"[{path}]({repo_url}/tree/{branch_name}/{cleaned})"

    def blob_link(path: str) -> str:
        cleaned = path.lstrip("./")
        return f"[{path}]({repo_url}/blob/{branch_name}/{cleaned})"

    artifacts_lines = []
    if artifact_name:
        artifacts_lines.append(
            f"- Export artifact: `{artifact_name}`"
        )
    if artifact_dir:
        artifacts_lines.append(
            f"- Sandbox dir: {tree_link(artifact_dir)}"
        )
    if metadata_path:
        artifacts_lines.append(
            f"- Metadata JSON: {blob_link(metadata_path)}"
        )
    if package_artifact_name:
        artifacts_lines.append(
            f"- Package artifact: `{package_artifact_name}`"
        )
    if package_file_name:
        package_path = (
            f"{artifact_dir}/{package_file_name}"
            if artifact_dir and package_file_name
            else package_file_name
        )
        if artifact_dir and package_file_name:
            artifacts_lines.append(
                f"- Package file: {blob_link(package_path)}"
            )
        else:
            artifacts_lines.append(f"- Package file: `{package_file_name}`")
    if package_status:
        artifacts_lines.append(f"- Package status: {package_status}")
    if icf_status:
        detail = icf_file if icf_file else "(sin archivo)"
        if icf_file and artifact_dir:
            icf_path = f"{artifact_dir}/{icf_file}"
            artifacts_lines.append(
                f"- ICF template: {icf_status} {blob_link(icf_path)}"
            )
        else:
            artifacts_lines.append(f"- ICF template: {icf_status} {detail}")

    if run_url:
        artifacts_lines.append(
            f"- Artifacts (run): [ver en GitHub Actions]({run_url}#artifacts)"
        )

    approvals = fetch_run_approvals(token, repository, run_id)
    approvals_lines = [
        f"- @{item['user']} ({item['state']})"
        for item in approvals
    ]

    body_sections = [
        "## Resumen",
        "\n".join(summary_lines),
    ]
    if env_status:
        body_sections.extend(["\n## Resultado por entorno", "\n".join(env_status)])
    if artifacts_lines:
        body_sections.extend(["\n## Artefactos", "\n".join(artifacts_lines)])
    body_sections.extend([
        "\n## Aprobaciones",
        "\n".join(approvals_lines) if approvals_lines else "_Sin aprobaciones registradas_",
    ])
    body_sections.extend(
        [
            "\n## Resumen de cambios (completar)",
            "_Editar este release y documentar los cambios promovidos._",
        ]
    )

    body_sections.append(
        "\n---\n_Generado automáticamente por GitHub Actions._"
    )
    body = "\n\n".join(body_sections)

    payload = {
        "tag_name": tag_name,
        "name": release_name,
        "body": body,
        "draft": False,
        "prerelease": False,
        "target_commitish": git_sha or git_ref or "main",
    }

    meta = {
        "repository": repository,
        "token": token,
        "tag_name": tag_name,
    }
    return release_name, body, tag_name, {"payload": payload, "meta": meta}


def ensure_release(meta: dict) -> None:
    payload = meta["payload"]
    repository = meta["meta"]["repository"]
    token = meta["meta"]["token"]
    tag_name = meta["meta"]["tag_name"]

    existing = github_request(
        "GET",
        f"/repos/{repository}/releases/tags/{tag_name}",
        token,
        raise_on_404=False,
    )

    if existing:
        github_request(
            "PATCH",
            f"/repos/{repository}/releases/{existing['id']}",
            token,
            {
                "name": payload["name"],
                "body": payload["body"],
                "draft": payload["draft"],
                "prerelease": payload["prerelease"],
                "target_commitish": payload["target_commitish"],
            },
        )
        return

    github_request("POST", f"/repos/{repository}/releases", token, payload)


def fetch_run_approvals(token: str, repository: str, run_id: str) -> list[dict[str, str]]:
    if not run_id:
        return []
    response = github_request(
        "GET",
        f"/repos/{repository}/actions/runs/{run_id}/approvals",
        token,
        raise_on_404=False,
    )
    if not response:
        return []
    if isinstance(response, dict) and "approvals" in response:
        data = response.get("approvals") or []
    else:
        data = response

    approvals: list[dict[str, str]] = []
    for item in data or []:
        if not isinstance(item, dict):
            continue
        user = item.get("user") or {}
        login = user.get("login") if isinstance(user, dict) else None
        if not login:
            continue
        approvals.append(
            {
                "user": login,
                "state": (item.get("state") or "approved").lower(),
            }
        )
    return approvals


def main() -> int:
    try:
        _, _, _, meta = build_release_payload()
        ensure_release(meta)
    except Exception as exc:  # noqa: BLE001
        print(f"::error::No se pudo crear el release: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
