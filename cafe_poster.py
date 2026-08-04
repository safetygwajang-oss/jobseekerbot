import os
import hashlib
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


# ==========================================================
# 🎯 핵심: PC 리스트에서 한글이 깨지는 문제 해결
# → 제목을 ASCII 문자로만 구성 (한글 완전 제거)
# → 진짜 정보(회사명/직무)는 본문 최상단 헤드라인 박스에 표시
# ==========================================================

# 경력구분 → 영문 태그 매핑 (제목용)
CAREER_TAG_MAP = {
    "신입": "ENTRY",
    "경력": "CAREER",
    "신입/경력": "ALL",
    "경력무관": "ANY",
    "인턴": "INTERN",
    "계약직": "CONTRACT",
}


def make_short_id(job):
    """회사명+모집분야 기반 4자리 고유 ID 생성 (예: A1B2)
    
    PC 리스트에서 각 글을 구분하기 위한 식별자.
    같은 회사의 다른 공고도 구분 가능.
    """
    company = job.get("company", "")
    position = job.get("position", "")
    seed = (company + "|" + position).encode("utf-8")
    h = hashlib.md5(seed).hexdigest().upper()
    return h[:4]


def build_subject(job):
    """
    제목: ASCII 문자로만 구성 (PC 리스트에서 안 깨지게)
    형식: [CAREER] JOB #A1B2 (~26-10-03)
    """
    career_tag = job.get("career_tag", "경력무관")
    deadline = job.get("deadline", "")

    # 경력구분 영문 변환
    eng_tag = CAREER_TAG_MAP.get(career_tag, "JOB")

    # 고유 ID
    short_id = make_short_id(job)

    # 기본: [태그] JOB #ID
    subject = "[" + eng_tag + "] JOB #" + short_id

    # 마감일 추가 (숫자/기호만이라 안전)
    if deadline:
        if "채용시" in deadline or "상시" in deadline:
            subject += " (OPEN)"
        else:
            # 26-10-03 형태는 숫자+하이픈이라 ASCII
            # 혹시 다른 형태면 숫자/하이픈/점/슬래시만 추출
            safe_deadline = "".join(
                c for c in deadline if c.isascii() and (c.isdigit() or c in "-./")
            )
            if safe_deadline:
                subject += " (~" + safe_deadline + ")"

    return subject


def build_headline_box(job):
    """본문 최상단 헤드라인 박스 - '진짜 제목' 역할"""
    lines = []
    
    career_tag = job.get("career_tag", "경력무관")
    company = clean_forbidden_words(job.get("company", ""))
    position = clean_forbidden_words(job.get("position", ""))
    deadline = job.get("deadline", "")

    # 메인 제목 라인 구성
    main_title = "[" + career_tag + "]"
    if company and company != "비공개":
        main_title += " " + company
    if position and position != "채용공고":
        if company and company != "비공개":
            main_title += " - " + position
        else:
            main_title += " " + position

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("📢 " + main_title)
    if deadline:
        if "채용시" in deadline or "상시" in deadline:
            lines.append("     🕐 상시채용")
        else:
            lines.append("     🕐 마감: ~" + deadline)
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    
    return lines


def build_content(job):
    """본문 - 최상단에 헤드라인 박스로 진짜 제목 표시"""
    lines = []

    # ========== 🎯 헤드라인 박스 (진짜 제목) ==========
    lines.extend(build_headline_box(job))
    lines.append("")
    lines.append("")

    # ========== 상세 정보 ==========
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
