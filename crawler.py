import os
import requests

CAFE_ID = "31767633"
MENU_ID = "10"


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
    """비-ASCII 문자를 HTML 엔티티로 변환"""
    result = ""
    for ch in text:
        if ord(ch) < 128:
            result += ch
        else:
            result += "&#" + str(ord(ch)) + ";"
    return result


def clean_forbidden_words(text):
    """출처 노출 방지 - iSAFETY 관련 단어 제거"""
    if not text:
        return text
    forbidden = ["iSAFETY", "isafety", "ISAFETY", "iSafety", "아이세이프티", "아이세이프"]
    for word in forbidden:
        text = text.replace(word, "")
    text = text.replace("  ", " ").strip()
    while text and text[0] in ">/<|- ":
        text = text[1:].strip()
    while text and text[-1] in ">/<|- ":
        text = text[:-1].strip()
    return text


def build_subject(job):
    """
    제목 포맷: [경력태그] 회사명 - 모집분야 (~마감일)
    예: [경력] 코웨이엔텍 - 본사 안전보건 (~26-10-03)
    """
    career_tag = job.get("career_tag", "경력무관")
    company = clean_forbidden_words(job.get("company", ""))
    position = clean_forbidden_words(job.get("position", ""))
    deadline = job.get("deadline", "")

    # [태그]
    title = "[" + career_tag + "]"

    # 회사명
    if company and company != "비공개":
        title += " " + company

    # 모집분야
    if position and position != "채용공고":
        if company and company != "비공개":
            title += " - " + position
        else:
            title += " " + position

    # 마감일
    if deadline:
        if "채용시" in deadline or "상시" in deadline:
            title += " (상시채용)"
        else:
            title += " (~" + deadline + ")"

    # 길이 제한
    if len(title) > 80:
        title = title[:77] + "..."
    
    return title


def build_content(job):
    """본문 - iSAFETY 흔적 없이"""
    lines = []
    lines.append("📌 채용 정보")
    lines.append("")

    company = clean_forbidden_words(job.get("company", ""))
    if company and company != "비공개":
        lines.append("🏢 회사·기관: " + company)

    position = clean_forbidden_words(job.get("position", ""))
    if position and position != "채용공고":
        lines.append("👔 모집분야: " + position)

    career_tag = job.get("career_tag", "")
    if career_tag:
        lines.append("💼 경력구분: " + career_tag)

    location = job.get("location", "")
    if location:
        lines.append("📍 근무지: " + location)

    deadline = job.get("deadline", "")
    if deadline:
        lines.append("📅 마감일: " + deadline)

    category = job.get("category", "")
    if category:
        lines.append("🏷️ 분류: " + category)

    # 담당업무 (있을 경우만)
    duty = clean_forbidden_words(job.get("duty", ""))
    if duty and duty != "상세내용 참조" and len(duty) > 10:
        if len(duty) > 300:
            duty = duty[:297] + "..."
        lines.append("")
        lines.append("📝 담당업무")
        lines.append(duty)

    lines.append("")
    lines.append("─────────────────────────")
    lines.append("")

    # 외부 지원 링크 (iSAFETY 아닌 경우만)
    apply_link = job.get("apply_link", "")
    if apply_link and "isafety" not in apply_link.lower():
        lines.append("🔗 지원/상세 링크")
        lines.append(apply_link)
        lines.append("")
        lines.append("─────────────────────────")

    lines.append("※ 지원 전 반드시 채용공고 원문을 확인해주세요.")
    lines.append("※ 본 정보는 참고용이며, 채용 조건은 변경될 수 있습니다.")

    return "\n".join(lines)


def post_to_cafe(job, access_token):
    subject = build_subject(job)
    content = build_content(job)

    print("  📝 제목:", subject)

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
