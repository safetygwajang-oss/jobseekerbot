import os
import re
import requests
from urllib.parse import quote

CAFE_ID = "31767633"
MENU_ID = "10"


# ==========================================================
# 네이버 API 토큰
# ==========================================================
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


# ==========================================================
# 텍스트 유틸
# ==========================================================
def clean_forbidden_words(text):
    """출처(iSAFETY) 노출 방지"""
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


def clean_company_for_title(company):
    """제목용 회사명 정리"""
    if not company:
        return ""
    company = re.sub(r"\(주\)|\(유\)|\(재\)|\(사\)|\(합\)|\(합자\)|\(사단법인\)|\(재단법인\)", "", company)
    company = company.replace("주식회사", "").replace("유한회사", "").replace("㈜", "")
    return company.strip()


# ==========================================================
# 🎯 제목 생성
# ==========================================================
def build_subject(job):
    """제목: [경력] [회사명] (~26-08-28)"""
    career = job.get("career", "").strip()
    company = job.get("company", "").strip()
    deadline = job.get("deadline", "").strip()

    career_clean = career.rstrip(".").strip()
    if not career_clean:
        career_clean = "채용"

    company_clean = clean_forbidden_words(company)
    company_clean = clean_company_for_title(company_clean)
    if not company_clean:
        company_clean = "채용공고"

    subject = "[" + career_clean + "] [" + company_clean + "]"

    if deadline:
        if "채용시" in deadline or "상시" in deadline:
            subject += " (상시)"
        else:
            subject += " (~" + deadline + ")"

    if len(subject) > 60:
        subject = subject[:57] + "..."

    return subject


# ==========================================================
# 📝 본문 생성
# ==========================================================
def strip_urls_from_duty(duty, apply_link):
    """담당업무에서 URL 라인 제거"""
    if not duty:
        return duty

    lines = duty.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("http://") or stripped.startswith("https://"):
            continue
        if "http" in stripped and len(stripped) < 200:
            no_url = re.sub(r'https?://[^\s]+', '', stripped).strip()
            if len(no_url) > 15:
                cleaned.append(no_url)
            continue
        cleaned.append(line)

    result = "\n".join(cleaned)
    while "\n\n\n" in result:
        result = result.replace("\n\n\n", "\n\n")
    return result.strip()


def build_content(job):
    """본문 생성 - 이모지 포함"""
    lines = []

    company = clean_forbidden_words(job.get("company", ""))
    position = clean_forbidden_words(job.get("position", ""))
    category = job.get("category", "")
    deadline = job.get("deadline", "")
    career = job.get("career", "")
    location = job.get("location", "")
    apply_link = job.get("apply_link", "")

    # 헤드라인
    main_title = "[" + (category or "채용") + "]"
    if company and company != "비공개":
        main_title += " " + company
    if position and position != "상세내용 참조":
        main_title += " - " + position

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("📢 " + main_title)
    if deadline:
        if "채용시" in deadline or "상시" in deadline:
            lines.append("     🕐 상시채용")
        else:
            lines.append("     🕐 마감: ~" + deadline)
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")

    # 채용 정보
    lines.append("📌 채용 정보")
    lines.append("")

    if company and company != "비공개":
        lines.append("🏢 회사명: " + company)
    if position and position != "상세내용 참조":
        lines.append("👔 모집분야: " + position)
    if career:
        lines.append("💼 경력구분: " + career.rstrip(".").strip())
    if location:
        lines.append("📍 근무지: " + location)
    if deadline:
        lines.append("📅 마감일: " + deadline)
    if category:
        lines.append("🏷️ 분류: " + category)

    # 담당업무
    duty = clean_forbidden_words(job.get("duty", ""))
    duty = strip_urls_from_duty(duty, apply_link)

    if duty and len(duty) > 20:
        if len(duty) > 600:
            duty = duty[:597] + "..."
        lines.append("")
        lines.append("📝 담당업무")
        lines.append(duty)

    lines.append("")
    lines.append("─────────────────────────")
    lines.append("")

    # 지원 링크
    if apply_link and "isafety" not in apply_link.lower():
        lines.append("🔗 지원/상세 링크")
        lines.append(apply_link)
        lines.append("")
    else:
        if company and company != "비공개":
            lines.append("🔗 지원 방법")
            lines.append("→ 채용사이트에서 '" + company + "' 검색")
            lines.append("→ 또는 회사 공식 홈페이지 채용페이지 확인")
            lines.append("")

    lines.append("─────────────────────────")
    lines.append("※ 지원 전 반드시 채용공고 원문을 확인해주세요.")
    lines.append("※ 본 정보는 참고용이며, 채용 조건은 변경될 수 있습니다.")

    return "\n".join(lines)


# ==========================================================
# 🚀 게시 - 네이버 공식 이중 인코딩 방식
# ==========================================================
def naver_double_encode(text):
    """네이버 카페 API 전용 이중 URL 인코딩"""
    if not text:
        return ""
    first = quote(text, safe='')
    second = quote(first, safe='')
    return second


def convert_newlines_to_br(text):
    """
    ⭐ 본문 줄바꿈을 HTML <br> 태그로 변환
    - 네이버 카페 API는 \n을 무시하고 다 붙여버림
    - <br> 태그로 바꿔야 줄바꿈이 유지됨
    """
    if not text:
        return text
    # \r\n, \r, \n 모두 <br>로 변환
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\n", "<br>")
    return text


def post_to_cafe(job, access_token):
    """네이버 카페 API 이중 인코딩 방식으로 게시"""
    subject = build_subject(job)
    content = build_content(job)

    print("  📝 제목:", subject)

    url = "https://openapi.naver.com/v1/cafe/" + CAFE_ID + "/menu/" + MENU_ID + "/articles"
    headers = {
        "Authorization": "Bearer " + access_token,
        "Content-Type": "application/x-www-form-urlencoded",
    }

    # ⭐ 본문 줄바꿈을 <br>로 변환 (핵심 수정!)
    content_html = convert_newlines_to_br(content)

    # 네이버 이중 인코딩
    subject_encoded = naver_double_encode(subject)
    content_encoded = naver_double_encode(content_html)

    body = "subject=" + subject_encoded + "&content=" + content_encoded + "&openyn=true"

    try:
        res = requests.post(
            url,
            headers=headers,
            data=body.encode("ascii"),
            timeout=15
        )
    except Exception as e:
        print("  ❌ 요청 예외:", type(e).__name__, str(e)[:100])
        return None

    print("  📨 상태코드:", res.status_code)
    print("  📨 응답:", res.text[:300])

    try:
        result = res.json()
    except Exception:
        print("  ❌ JSON 파싱 실패")
        return None

    status = result.get("message", {}).get("status")
    if status != "200":
        print("  ❌ 실패 - status:", status)
        return None

    article_url = result["message"]["result"]["articleUrl"]
    print("  ✅ 성공:", article_url)
    return article_url
