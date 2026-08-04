import os
import requests

CAFE_ID = "31767633"
MENU_ID = "10"
DETAIL_BASE_URL = "https://isafety.co.kr/is/job/"


def get_access_token():
    CLIENT_ID = os.environ["NAVER_CLIENT_ID"]
    CLIENT_SECRET = os.environ["NAVER_CLIENT_SECRET"]
    REFRESH_TOKEN = os.environ["NAVER_REFRESH_TOKEN"]

    res = requests.get(
        "https://nid.naver.com/oauth2.0/token",
        params={
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": REFRESH_TOKEN,
        },
        timeout=10
    )
    data = res.json()
    if "access_token" not in data:
        raise RuntimeError("토큰 재발급 실패: " + str(data))
    return data["access_token"]


def to_html_entity(text):
    """비-ASCII 문자를 HTML 엔티티로 변환 (네이버 API 한글 처리용)"""
    result = ""
    for ch in text:
        if ord(ch) < 128:
            result += ch
        else:
            result += "&#" + str(ord(ch)) + ";"
    return result


def build_subject(job):
    """제목 생성: [카테고리] 회사명 - 모집분야"""
    category = job.get("category", "기타")
    company = job.get("company", "비공개")
    position = job.get("position", "")

    # 회사명이 있으면 우선 사용
    if company and company != "비공개":
        title = "[" + category + "] " + company
        if position and position != job.get("raw_title", "")[:50]:
            title += " - " + position
    else:
        # 회사명 없으면 원본 제목 활용
        title = "[" + category + "] " + job.get("raw_title", "채용공고")

    # 네이버 카페 제목 길이 제한 (약 80자)
    if len(title) > 80:
        title = title[:77] + "..."
    return title


def build_content(job):
    """본문 생성: 값이 있는 정보만 표시 (모르는 건 안 씀)"""
    lines = []
    lines.append("📌 채용 정보")
    lines.append("")

    # 회사명 (비공개면 스킵)
    company = job.get("company", "")
    if company and company != "비공개":
        lines.append("🏢 회사명: " + company)

    # 모집분야
    position = job.get("position", "")
    if position and position != "상세내용 참조":
        lines.append("👔 모집분야: " + position)

    # 담당업무
    duty = job.get("duty", "")
    if duty and duty != "상세내용 참조":
        # 담당업무는 길 수 있으니 300자 제한
        if len(duty) > 300:
            duty = duty[:297] + "..."
        lines.append("📝 담당업무: " + duty)

    # 마감일
    deadline = job.get("deadline", "")
    if deadline and deadline != "채용시 마감":
        lines.append("📅 마감일: " + deadline)
    elif deadline == "채용시 마감":
        lines.append("📅 마감일: 채용시 마감")

    # 카테고리
    category = job.get("category", "")
    if category:
        lines.append("🏷️ 분류: " + category)

    lines.append("")
    lines.append("─────────────────────────")
    lines.append("")

    # 지원 링크 (본문에서 찾은 외부 링크)
    apply_link = job.get("apply_link", "")
    if apply_link:
        lines.append("🔗 지원/상세 링크")
        lines.append(apply_link)
        lines.append("")

    # 원문 링크 (iSAFETY 상세 페이지)
    job_id = job.get("job_id", "")
    if job_id:
        lines.append("📄 원문 보기 (iSAFETY)")
        lines.append(DETAIL_BASE_URL + job_id)
        lines.append("")

    lines.append("─────────────────────────")
    lines.append("※ 본 공고는 iSAFETY에서 자동 수집된 정보입니다.")
    lines.append("※ 지원 전 반드시 원문을 확인해주세요.")

    return "\n".join(lines)


def post_to_cafe(job, access_token):
    subject = build_subject(job)
    content = build_content(job)

    encoded_subject = to_html_entity(subject)
    encoded_content = to_html_entity(content)

    url = "https://openapi.naver.com/v1/cafe/" + CAFE_ID + "/menu/" + MENU_ID + "/articles"
    headers = {
        "Authorization": "Bearer " + access_token,
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
    }

    res = requests.post(
        url,
        headers=headers,
        data={
            "subject": encoded_subject,
            "content": encoded_content,
            "openyn": "true",
        },
        timeout=15
    )

    print("  📨 상태코드:", res.status_code)
    print("  📨 응답:", res.text[:300])

    try:
        result = res.json()
    except Exception:
        print("  ❌ JSON 파싱 실패")
        return None

    status = result.get("message", {}).get("status")
    if status != "200":
        print("  ❌ 실패")
        return None

    article_url = result["message"]["result"]["articleUrl"]
    print("  ✅ 성공:", article_url)
    return article_url
