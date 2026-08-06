import os
import re
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


def clean_forbidden_words(text):
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
# 🎯 제목: 한글 그대로 시도
# ==========================================================
def build_subject(job):
    """
    형식: [경력] [회사명] (~마감일)
    한글 그대로 사용 - requests가 UTF-8 URL 인코딩 자동 처리
    """
    career = job.get("career", "").strip()
    company = job.get("company", "").strip()
    deadline = job.get("deadline", "").strip()

    career_clean = career.rstrip(".").strip()
    if not career_clean:
        career_clean = "채용"

    company_clean = clean_forbidden_words(company)
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
# 📝 본문
# ==========================================================
def strip_urls_from_duty(duty, apply_link):
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
    lines = []

    company = clean_forbidden_words(job.get("company", ""))
    position = clean_forbidden_words(job.get("position", ""))
    category = job.get("category", "")
    deadline = job.get("deadline", "")
    career = job.get("career", "")
    location = job.get("location", "")
    apply_link = job.get("apply_link", "")

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
# 🚀 게시 (한글 그대로 UTF-8 전송)
# ==========================================================
def post_to_cafe(job, access_token):
    subject = build_subject(job)
    content = build_content(job)

    print("  📝 제목:", subject)

    url = "https://openapi.naver.com/v1/cafe/" + CAFE_ID + "/menu/" + MENU_ID + "/articles"
    headers = {
        "Authorization": "Bearer " + access_token,
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
    }

    # ★ HTML 엔티티 변환 없이 한글 그대로!
    payload = {
        "subject": subject,
        "content": content,
        "openyn": "true",
    }

    res = requests.post(url, headers=headers, data=payload, timeout=15)

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
