"""Jira 프로젝트의 컨텍스트 정보(커스텀 필드, 상태값, 워크플로우 전이)를 내보내는 스크립트."""

import json
import os
import sys
from collections import defaultdict
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
JIRA_WORKFLOW_NAME = os.getenv("JIRA_WORKFLOW_NAME")  # 워크플로우 테스트용

print(f"JIRA_DOMAIN: {JIRA_DOMAIN}")
print(f"JIRA_EMAIL: {JIRA_EMAIL}")
print(f"JIRA_API_TOKEN: {JIRA_API_TOKEN}")
print(f"JIRA_PROJECT_KEY: {JIRA_PROJECT_KEY}")
print(f"JIRA_WORKFLOW_NAME: {JIRA_WORKFLOW_NAME}")


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
    workflow_name: str | None
    transitions: list["WorkflowTransition"]


class JiraContext(TypedDict):
    """Jira 컨텍스트 정보."""

    custom_fields: dict[str, str]
    statuses: list[IssueTypeStatus]


class WorkflowTransition(TypedDict, total=False):
    """워크플로우 전이(transition) 정보.

    `from_statuses`가 `["*"]`인 경우, Jira UI의 "Any"에 해당하는 전역 전이로 취급한다.
    """

    id: str
    name: str
    from_statuses: list[str]
    to_status: str


class TransitionSummary(TypedDict, total=False):
    """상태별 전이 요약 정보."""

    id: str
    name: str
    to_status: str


def _log_http_failure(
    *,
    url: str,
    params: dict[str, str] | None,
    status_code: int | None,
    response_text: str | None,
    note: str,
) -> None:
    """HTTP 호출 실패 시 디버그 로그를 stderr로 출력한다.

    Args:
        url: 호출한 URL.
        params: 쿼리 파라미터.
        status_code: HTTP 상태 코드(알 수 없으면 None).
        response_text: 응답 본문(알 수 없으면 None).
        note: 로그에 포함할 추가 설명.
    """
    safe_text = (response_text or "").strip()
    if len(safe_text) > 4000:
        safe_text = f"{safe_text[:4000]}\n... (truncated)"

    print("----- Jira API 호출 실패 디버그 -----", file=sys.stderr)
    print(f"note: {note}", file=sys.stderr)
    print(f"url: {url}", file=sys.stderr)
    if params is not None:
        print(f"params: {params}", file=sys.stderr)
    if status_code is not None:
        print(f"status_code: {status_code}", file=sys.stderr)
    if safe_text:
        print("response_text:", file=sys.stderr)
        print(safe_text, file=sys.stderr)
    print("----- end -----", file=sys.stderr)


def _get_json(
    *,
    url: str,
    headers: dict[str, str],
    auth: HTTPBasicAuth,
    params: dict[str, str] | None = None,
) -> object:
    """HTTP GET 호출 후 JSON 본문을 반환한다.

    Args:
        url: 호출할 URL.
        headers: 요청 헤더.
        auth: Jira 기본 인증 정보.
        params: 쿼리 파라미터.

    Returns:
        JSON 응답 본문.

    Raises:
        requests.HTTPError: API 호출 실패 시.
    """
    response = requests.get(url, headers=headers, auth=auth, params=params)
    try:
        response.raise_for_status()
    except requests.HTTPError:
        _log_http_failure(
            url=url,
            params=params,
            status_code=response.status_code,
            response_text=response.text,
            note="HTTP 오류 응답을 받았습니다.",
        )
        raise

    try:
        return response.json()
    except ValueError:
        _log_http_failure(
            url=url,
            params=params,
            status_code=response.status_code,
            response_text=response.text,
            note="JSON 파싱에 실패했습니다. (응답이 JSON이 아닐 수 있습니다.)",
        )
        raise


def _extract_workflow_scheme_id(payload: object) -> str | None:
    """워크플로우 스킴 ID를 다양한 응답 형태에서 추출한다."""
    if isinstance(payload, dict):
        direct = payload.get("workflowSchemeId")
        if isinstance(direct, str) and direct:
            return direct

        workflow_scheme = payload.get("workflowScheme")
        if isinstance(workflow_scheme, dict):
            scheme_id = workflow_scheme.get("id")
            if isinstance(scheme_id, str) and scheme_id:
                return scheme_id

        values = payload.get("values")
        if isinstance(values, list) and values:
            first = values[0]
            if isinstance(first, dict):
                inner = first.get("workflowSchemeId") or first.get("id")
                if isinstance(inner, str) and inner:
                    return inner

        projects = payload.get("projects")
        if isinstance(projects, dict):
            values2 = projects.get("values")
            if isinstance(values2, list) and values2:
                first2 = values2[0]
                if isinstance(first2, dict):
                    inner2 = first2.get("workflowSchemeId") or first2.get("id")
                    if isinstance(inner2, str) and inner2:
                        return inner2

    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, dict):
            inner = first.get("workflowSchemeId") or first.get("id")
            if isinstance(inner, str) and inner:
                return inner

    return None


def _extract_scheme_workflow_mapping(
    scheme_detail: object,
) -> tuple[str | None, dict[str, str]]:
    """워크플로우 스킴 상세에서 기본 워크플로우와 이슈 타입별 워크플로우 매핑을 추출한다."""
    if not isinstance(scheme_detail, dict):
        return None, {}

    default_workflow = scheme_detail.get("defaultWorkflow")
    default_name: str | None = (
        default_workflow if isinstance(default_workflow, str) else None
    )

    mapping_raw = scheme_detail.get("issueTypeMappings")
    if isinstance(mapping_raw, dict):
        mapping: dict[str, str] = {}
        for k, v in mapping_raw.items():
            if isinstance(k, str) and isinstance(v, str) and k and v:
                mapping[k] = v
        return default_name, mapping

    # 일부 응답은 리스트 형태일 수 있으므로 방어적으로 처리한다.
    if isinstance(mapping_raw, list):
        mapping2: dict[str, str] = {}
        for item in mapping_raw:
            if not isinstance(item, dict):
                continue
            issue_type_id = item.get("issueTypeId") or item.get("issueType")
            workflow_name = item.get("workflow") or item.get("workflowName")
            if (
                isinstance(issue_type_id, str)
                and issue_type_id
                and isinstance(workflow_name, str)
                and workflow_name
            ):
                mapping2[issue_type_id] = workflow_name
        return default_name, mapping2

    return default_name, {}


def _extract_workflow_transitions(payload: object) -> list[WorkflowTransition]:
    """워크플로우 검색 응답에서 전이 정보를 추출한다."""
    workflow: object = payload
    if isinstance(payload, dict):
        # v3/v2 모두 values 배열을 반환할 수 있다.
        values = payload.get("values")
        if isinstance(values, list) and values:
            workflow = values[0]
        else:
            workflows = payload.get("workflows")
            if isinstance(workflows, list) and workflows:
                workflow = workflows[0]

    if not isinstance(workflow, dict):
        return []

    transitions_raw = workflow.get("transitions")
    if not isinstance(transitions_raw, list):
        return []

    transitions: list[WorkflowTransition] = []
    for tr in transitions_raw:
        if not isinstance(tr, dict):
            continue

        name = tr.get("name")
        if not isinstance(name, str) or not name:
            continue

        to_obj = tr.get("to")
        to_status: str | None = None
        if isinstance(to_obj, dict):
            to_name = to_obj.get("name")
            if isinstance(to_name, str) and to_name:
                to_status = to_name
        if to_status is None:
            end = tr.get("end")
            if isinstance(end, str) and end:
                to_status = end
        if to_status is None:
            continue

        from_statuses: list[str] = []
        from_obj = tr.get("from")
        if isinstance(from_obj, dict):
            from_name = from_obj.get("name")
            if isinstance(from_name, str) and from_name:
                from_statuses = [from_name]
        elif isinstance(from_obj, list):
            from_names: list[str] = []
            for f in from_obj:
                if isinstance(f, dict):
                    f_name = f.get("name")
                    if isinstance(f_name, str) and f_name:
                        from_names.append(f_name)
            from_statuses = from_names
        elif isinstance(from_obj, str) and from_obj:
            from_statuses = [from_obj]

        if not from_statuses:
            from_statuses = ["*"]

        transition: WorkflowTransition = {
            "name": name,
            "to_status": to_status,
            "from_statuses": from_statuses,
        }
        tr_id = tr.get("id")
        if isinstance(tr_id, str) and tr_id:
            transition["id"] = tr_id

        transitions.append(transition)

    return transitions


def _build_transition_index(
    transitions: list[WorkflowTransition],
) -> tuple[dict[str, list[TransitionSummary]], list[TransitionSummary]]:
    """전이 목록을 상태별/전역 전이로 인덱싱한다."""
    by_from: dict[str, list[TransitionSummary]] = defaultdict(list)
    global_transitions: list[TransitionSummary] = []

    for tr in transitions:
        name = tr.get("name")
        to_status = tr.get("to_status")
        from_statuses = tr.get("from_statuses")
        if (
            not isinstance(name, str)
            or not isinstance(to_status, str)
            or not isinstance(from_statuses, list)
        ):
            continue

        summary: TransitionSummary = {"name": name, "to_status": to_status}
        tr_id = tr.get("id")
        if isinstance(tr_id, str) and tr_id:
            summary["id"] = tr_id

        if from_statuses == ["*"] or "*" in from_statuses:
            global_transitions.append(summary)
            continue

        for from_status in from_statuses:
            if isinstance(from_status, str) and from_status:
                by_from[from_status].append(summary)

    return dict(by_from), global_transitions


def _fetch_project_id(auth: HTTPBasicAuth, headers: dict[str, str]) -> str:
    """프로젝트 키로 프로젝트 ID를 조회한다."""
    payload = _get_json(
        url=f"{JIRA_DOMAIN}/rest/api/3/project/{JIRA_PROJECT_KEY}",
        headers=headers,
        auth=auth,
    )
    if not isinstance(payload, dict) or not isinstance(payload.get("id"), str):
        raise ValueError("프로젝트 ID를 조회할 수 없습니다. (응답 형식 오류)")
    return payload["id"]


def _fetch_workflow_scheme_id(
    auth: HTTPBasicAuth, headers: dict[str, str], project_id: str
) -> str:
    """프로젝트에 연결된 워크플로우 스킴 ID를 조회한다(폴백 포함)."""
    candidates: list[tuple[str, dict[str, str] | None]] = [
        (f"{JIRA_DOMAIN}/rest/api/3/workflowscheme/project", {"projectId": project_id}),
        (f"{JIRA_DOMAIN}/rest/api/2/workflowscheme/project", {"projectId": project_id}),
        (f"{JIRA_DOMAIN}/rest/projectconfig/1/workflowscheme/{JIRA_PROJECT_KEY}", None),
    ]

    last_error: Exception | None = None
    for url, params in candidates:
        try:
            payload = _get_json(url=url, headers=headers, auth=auth, params=params)
            scheme_id = _extract_workflow_scheme_id(payload)
            if scheme_id:
                return scheme_id
            _log_http_failure(
                url=url,
                params=params,
                status_code=None,
                response_text=None,
                note="응답은 성공했지만 워크플로우 스킴 ID를 추출하지 못했습니다. (응답 형식 확인 필요)",
            )
        except Exception as e:  # noqa: BLE001 - 폴백 시나리오에서 예외를 보관한다.
            last_error = e
            continue

    raise requests.HTTPError(
        "워크플로우 스킴 ID 조회에 실패했습니다. (권한/프로젝트 유형/API 차이 가능)"
    ) from last_error


def _fetch_workflow_scheme_detail(
    auth: HTTPBasicAuth, headers: dict[str, str], scheme_id: str
) -> object:
    """워크플로우 스킴 상세를 조회한다(폴백 포함)."""
    candidates = [
        f"{JIRA_DOMAIN}/rest/api/3/workflowscheme/{scheme_id}",
        f"{JIRA_DOMAIN}/rest/api/2/workflowscheme/{scheme_id}",
    ]
    last_error: Exception | None = None
    for url in candidates:
        try:
            return _get_json(url=url, headers=headers, auth=auth)
        except Exception as e:  # noqa: BLE001
            last_error = e
            continue
    raise requests.HTTPError(
        "워크플로우 스킴 상세 조회에 실패했습니다."
    ) from last_error


def _fetch_workflow_transitions_by_name(
    auth: HTTPBasicAuth, headers: dict[str, str], workflow_name: str
) -> list[WorkflowTransition]:
    """워크플로우 이름으로 전이 목록을 조회한다(폴백 포함)."""
    candidates = [
        f"{JIRA_DOMAIN}/rest/api/3/workflow/search",
        f"{JIRA_DOMAIN}/rest/api/2/workflow/search",
    ]
    params = {"workflowName": workflow_name, "expand": "transitions"}
    last_error: Exception | None = None
    for url in candidates:
        try:
            payload = _get_json(url=url, headers=headers, auth=auth, params=params)
            transitions = _extract_workflow_transitions(payload)
            if transitions:
                return transitions
            # 응답은 성공했지만 transitions가 비어있을 수 있으므로 다음 후보도 시도한다.
        except Exception as e:  # noqa: BLE001
            last_error = e
            continue
    raise requests.HTTPError(
        "워크플로우 전이 목록 조회에 실패했습니다."
    ) from last_error


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
    """프로젝트의 이슈 타입별 상태 목록을 조회하고, 워크플로우 전이까지 결합한다."""
    candidates = [
        f"{JIRA_DOMAIN}/rest/api/3/project/{JIRA_PROJECT_KEY}/statuses",
        f"{JIRA_DOMAIN}/rest/api/2/project/{JIRA_PROJECT_KEY}/statuses",
    ]

    statuses_payload: list[object] | None = None
    last_error: Exception | None = None
    for url in candidates:
        try:
            payload = _get_json(url=url, headers=headers, auth=auth)
            if isinstance(payload, list):
                statuses_payload = payload
                break
        except Exception as e:  # noqa: BLE001 - 폴백 시나리오에서 예외를 보관한다.
            last_error = e
            continue

    if statuses_payload is None:
        raise requests.HTTPError(
            "프로젝트 상태 목록 조회에 실패했습니다. (v3/v2 모두 실패)"
        ) from last_error

    project_id = _fetch_project_id(auth, headers)
    scheme_id = _fetch_workflow_scheme_id(auth, headers, project_id)
    scheme_detail = _fetch_workflow_scheme_detail(auth, headers, scheme_id)
    default_workflow, issue_type_to_workflow = _extract_scheme_workflow_mapping(
        scheme_detail
    )

    workflow_cache: dict[str, list[WorkflowTransition]] = {}

    statuses: list[IssueTypeStatus] = []
    for issue_type in statuses_payload:
        if not isinstance(issue_type, dict):
            continue
        issue_type_name_obj = issue_type.get("name")
        if not isinstance(issue_type_name_obj, str) or not issue_type_name_obj:
            continue
        issue_type_id_obj = issue_type.get("id")
        issue_type_id = (
            issue_type_id_obj if isinstance(issue_type_id_obj, str) else None
        )

        workflow_name = None
        if issue_type_id and issue_type_id in issue_type_to_workflow:
            workflow_name = issue_type_to_workflow[issue_type_id]
        elif default_workflow:
            workflow_name = default_workflow

        transitions: list[WorkflowTransition] = []
        if workflow_name:
            if workflow_name not in workflow_cache:
                workflow_cache[workflow_name] = _fetch_workflow_transitions_by_name(
                    auth, headers, workflow_name
                )
            transitions = workflow_cache[workflow_name]

        statuses.append(
            IssueTypeStatus(
                issue_type=issue_type_name_obj,
                available_statuses=[
                    s["name"]
                    for s in issue_type.get("statuses", [])
                    if isinstance(s, dict) and isinstance(s.get("name"), str)
                ],
                workflow_name=workflow_name,
                transitions=transitions,
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


def test_workflow_only() -> None:
    """워크플로우 권한만으로 테스트한다. (read:workflow:jira, read:workflow-scheme:jira)"""
    if not JIRA_DOMAIN or not JIRA_EMAIL or not JIRA_API_TOKEN:
        raise ValueError("JIRA_DOMAIN, JIRA_EMAIL, JIRA_API_TOKEN 환경 변수가 필요합니다.")
    if not JIRA_WORKFLOW_NAME:
        raise ValueError("JIRA_WORKFLOW_NAME 환경 변수가 필요합니다. (테스트할 워크플로우 이름)")

    auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
    headers = {"Accept": "application/json"}

    print(f"\n🔍 워크플로우 '{JIRA_WORKFLOW_NAME}' 검색 중...")
    transitions = _fetch_workflow_transitions_by_name(auth, headers, JIRA_WORKFLOW_NAME)

    result = {
        "workflow_name": JIRA_WORKFLOW_NAME,
        "transitions": transitions,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    # 워크플로우만 테스트하려면 JIRA_WORKFLOW_NAME 환경 변수 설정 후 실행
    if JIRA_WORKFLOW_NAME:
        try:
            test_workflow_only()
        except ValueError as e:
            print(f"❌ 설정 오류: {e}")
        except requests.HTTPError as e:
            print(f"❌ API 호출 실패: {e}")
    else:
        # 기존 전체 컨텍스트 조회 (read:project:jira, read:field:jira 권한 필요)
        try:
            jira_context = get_jira_context()
            print(json.dumps(jira_context, indent=2, ensure_ascii=False))
        except ValueError as e:
            print(f"❌ 설정 오류: {e}")
        except requests.HTTPError as e:
            print(f"❌ API 호출 실패: {e}")
