import requests
import json
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
import os

load_dotenv()

# Jira 도메인 및 사용자 설정
JIRA_DOMAIN = "https://socarcorp.atlassian.net"
EMAIL = "serena@socar.kr"
# Jira API 토큰 발급: https://id.atlassian.com/manage-profile/security/api-tokens
API_TOKEN = os.getenv("JIRA_API_TOKEN")
if not API_TOKEN:
    raise ValueError("JIRA_API_TOKEN 환경 변수가 설정되지 않았습니다.")

# 검색 조건: 2025년 1월 1일 이후 생성된 티켓 중, 담당자이거나 참여자로 포함된 티켓 조회
JQL_QUERY = (
    'created >= "2025-01-01" AND (assignee = currentUser() OR "참여자" = currentUser())'
)

# 필요한 필드명 선택 -> 필요하면 추가
FIELDS = ["key", "summary", "creator", "created", "status", "priority", "parent"]

# 데이터 수집
url = f"{JIRA_DOMAIN}/rest/api/3/search/jql"
auth = HTTPBasicAuth(EMAIL, API_TOKEN)
headers = {"Accept": "application/json", "Content-Type": "application/json"}

all_issues = []
next_page_token = None  # 시작할 때는 토큰 없음
max_results = 100

print(f"🔄 데이터 수집을 시작합니다... (API: {url})")

while True:
    # payload 구성
    payload_dict = {"jql": JQL_QUERY, "maxResults": max_results, "fields": FIELDS}

    if next_page_token:
        payload_dict["nextPageToken"] = next_page_token

    try:
        response = requests.post(
            url, data=json.dumps(payload_dict), headers=headers, auth=auth
        )

        if response.status_code != 200:
            print(f"❌ 에러 발생: {response.status_code}, 에러 내용: {response.text}")
            break

        data = response.json()
        issues = data.get("issues", [])

        if not issues:
            print("더 이상 가져올 데이터가 없습니다.")
            break

        all_issues.extend(issues)
        print(f"{len(issues)}개 티켓 수집 완료 (누적 {len(all_issues)}개)")

        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break

    except Exception as e:
        print(f"❌ 실행 중 오류 발생: {e}")
        break

# 결과 출력
print("\n" + "=" * 50)
print(f"✅ 총 {len(all_issues)}개의 티켓을 찾았습니다.")
print("=" * 50)

for issue in all_issues:
    key = issue["key"]
    summary = issue["fields"]["summary"]
    status = (
        issue["fields"]["status"]["name"]
        if issue["fields"].get("status")
        else "Unknown"
    )
    created = issue["fields"]["created"][:10]
    parent = issue["fields"].get("parent")
    parent_info = f"[{parent['key']}] {parent['fields']['summary']}" if parent else "-"
    print(f"[{key}] {summary} (상태: {status}, 생성일: {created}, 상위: {parent_info})")
