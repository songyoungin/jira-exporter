# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

Jira 티켓을 가져와서 내보내는 Python 스크립트입니다. Jira REST API를 사용하여 JQL 쿼리 기반으로 티켓을 검색하고 결과를 출력합니다.

## 개발 환경

- Python 3.13
- 패키지 관리: uv
- 가상 환경: `.venv`
- 린터/포매터: ruff, mypy (pre-commit으로 실행)

## 환경 변수 설정

`.env` 파일을 생성하고 다음 변수를 설정:

```
JIRA_API_TOKEN=your_api_token_here
```

API 토큰 발급: https://id.atlassian.com/manage-profile/security/api-tokens

## 명령어

```bash
# 의존성 설치
uv sync

# 스크립트 실행
source .venv/bin/activate && python main.py

# pre-commit 실행 (린트/포맷팅)
source .venv/bin/activate && pre-commit run --all-files
```

## 코드 커스터마이징

`main.py`에서 다음 상수를 수정하여 검색 조건 변경 가능:

- `JQL_QUERY`: Jira 검색 쿼리 (JQL 문법)
- `FIELDS`: 가져올 필드 목록
