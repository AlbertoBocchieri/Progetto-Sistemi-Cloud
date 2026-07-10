import json
import os
import urllib.error
import urllib.request

import boto3


def _env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def _github_token():
    ssm = boto3.client("ssm")
    response = ssm.get_parameter(
        Name=_env("GITHUB_TOKEN_PARAMETER"),
        WithDecryption=True,
    )
    return response["Parameter"]["Value"]


def handler(event, _context):
    owner = _env("GITHUB_OWNER")
    repo = _env("GITHUB_REPO")
    workflow = _env("GITHUB_WORKFLOW")
    ref = _env("GITHUB_REF")

    body = json.dumps(
        {
            "ref": ref,
            "inputs": {
                "confirm": "destroy-parcheggia-dev",
            },
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches",
        data=body,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {_github_token()}",
            "Content-Type": "application/json",
            "User-Agent": "parcheggia-auto-down",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return {
                "ok": True,
                "github_status": response.status,
                "event": event,
            }
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")
        raise RuntimeError(f"GitHub dispatch failed: {error.code} {detail}") from error
