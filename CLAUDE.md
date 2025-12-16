# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

Jira REST API를 사용하여 티켓과 프로젝트 설정을 내보내는 Python CLI 스크립트 모음입니다.

## 개발 환경

- Python 3.13
- 패키지 관리: uv
- 가상 환경: `.venv`
- 린터/포매터: ruff, mypy (pre-commit으로 실행)

## 환경 변수 설정

`.env` 파일을 생성하고 다음 변수를 설정 (`.env.example` 참고):

```
JIRA_DOMAIN=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-jira-api-token
JIRA_PROJECT_KEY=YOUR_PROJECT_KEY
```

API 토큰 발급: https://id.atlassian.com/manage-profile/security/api-tokens

## 명령어

```bash
# 의존성 설치
uv sync

# 티켓 내보내기 실행
source .venv/bin/activate && python export_jira_tickets.py

# 프로젝트 설정 내보내기 실행
source .venv/bin/activate && python export_jira_space_settings.py

# pre-commit 실행 (린트/포맷팅)
source .venv/bin/activate && pre-commit run --all-files
```

## 스크립트 구조

- `export_jira_tickets.py`: JQL 쿼리 기반 티켓 검색 및 출력 (페이지네이션 지원)
  - `JQL_QUERY`, `FIELDS` 상수로 검색 조건 커스터마이징
- `export_jira_space_settings.py`: 프로젝트 컨텍스트 정보(커스텀 필드, 이슈 타입별 상태) 조회
  - `JIRA_PROJECT_KEY` 환경 변수 필요
