"""Jira 프로젝트의 컨텍스트 정보(커스텀 필드, 상태값)를 내보내는 스크립트."""

import json
import os
from typing import TypedDict

import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

load_dotenv()

# 환경 변수 로드
JIRA_DOMAIN = os.getenv("JIRA_DOMAIN")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY")


def _validate_env_vars() -> None:
    """필수 환경 변수가 설정되어 있는지 검증한다."""
    if not JIRA_DOMAIN:
        raise ValueError("JIRA_DOMAIN 환경 변수가 설정되지 않았습니다.")
    if not JIRA_EMAIL:
        raise ValueError("JIRA_EMAIL 환경 변수가 설정되지 않았습니다.")
    if not JIRA_API_TOKEN:
        raise ValueError("JIRA_API_TOKEN 환경 변수가 설정되지 않았습니다.")
    if not JIRA_PROJECT_KEY:
        raise ValueError("JIRA_PROJECT_KEY 환경 변수가 설정되지 않았습니다.")


class IssueTypeStatus(TypedDict):
    """이슈 타입별 상태 정보."""

    issue_type: str
    available_statuses: list[str]


class JiraContext(TypedDict):
    """Jira 컨텍스트 정보."""

    custom_fields: dict[str, str]
    statuses: list[IssueTypeStatus]


def _fetch_custom_fields(
    auth: HTTPBasicAuth, headers: dict[str, str]
) -> dict[str, str]:
    """커스텀 필드 목록을 조회하여 이름-ID 매핑을 반환한다."""
    response = requests.get(
        f"{JIRA_DOMAIN}/rest/api/3/field", headers=headers, auth=auth
    )
    response.raise_for_status()

    custom_fields: dict[str, str] = {}
    for field in response.json():
        if field["custom"]:
            custom_fields[field["name"]] = field["id"]

    return custom_fields


def _fetch_project_statuses(
    auth: HTTPBasicAuth, headers: dict[str, str]
) -> list[IssueTypeStatus]:
    """프로젝트의 이슈 타입별 상태 목록을 조회한다."""
    response = requests.get(
        f"{JIRA_DOMAIN}/rest/api/3/project/{JIRA_PROJECT_KEY}/statuses",
        headers=headers,
        auth=auth,
    )
    response.raise_for_status()

    statuses: list[IssueTypeStatus] = []
    for issue_type in response.json():
        statuses.append(
            IssueTypeStatus(
                issue_type=issue_type["name"],
                available_statuses=[s["name"] for s in issue_type["statuses"]],
            )
        )

    return statuses


def get_jira_context() -> JiraContext:
    """Jira 프로젝트의 컨텍스트 정보를 조회한다.

    Returns:
        커스텀 필드 매핑과 이슈 타입별 상태 목록을 포함한 컨텍스트 정보.

    Raises:
        ValueError: 필수 환경 변수가 설정되지 않은 경우.
        requests.HTTPError: API 호출 실패 시.
    """
    _validate_env_vars()

    auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)  # type: ignore[arg-type]
    headers = {"Accept": "application/json"}

    return JiraContext(
        custom_fields=_fetch_custom_fields(auth, headers),
        statuses=_fetch_project_statuses(auth, headers),
    )


if __name__ == "__main__":
    try:
        jira_context = get_jira_context()
        print(json.dumps(jira_context, indent=2, ensure_ascii=False))
    except ValueError as e:
        print(f"❌ 설정 오류: {e}")
    except requests.HTTPError as e:
        print(f"❌ API 호출 실패: {e}")
