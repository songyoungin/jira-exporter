# jira-exporter

Jira REST API를 사용하여 티켓과 프로젝트 설정을 내보내는 Python CLI 스크립트 모음입니다.

## 요구 사항

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) 패키지 매니저

## 설치

```bash
uv sync
```

## 환경 변수 설정

`.env.example`을 복사하여 `.env` 파일을 생성하고 값을 설정합니다:

```bash
cp .env.example .env
```

```
JIRA_DOMAIN=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-jira-api-token
JIRA_PROJECT_KEY=YOUR_PROJECT_KEY
```

API 토큰은 [Atlassian API 토큰 관리](https://id.atlassian.com/manage-profile/security/api-tokens)에서 발급받을 수 있습니다.

## 사용법

### 티켓 내보내기

JQL 쿼리 기반으로 티켓을 검색하고 결과를 출력합니다.

```bash
source .venv/bin/activate && python export_jira_tickets.py
```

`export_jira_tickets.py`에서 다음 상수를 수정하여 검색 조건을 변경할 수 있습니다:

- `JQL_QUERY`: Jira 검색 쿼리 (JQL 문법)
- `FIELDS`: 가져올 필드 목록

### 프로젝트 설정 내보내기

프로젝트의 커스텀 필드 목록과 이슈 타입별 상태를 JSON으로 출력합니다.

```bash
source .venv/bin/activate && python export_jira_space_settings.py
```

`JIRA_PROJECT_KEY` 환경 변수가 필요합니다.
