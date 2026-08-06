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
    """출처 노출 방지"""
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
# 🎯 제목 영문화 - PC 리스트 한글 깨짐 방지
# ==========================================================

# 카테고리 → 영문 매핑
CATEGORY_MAP = {
    "제조": "MFG",
    "건설": "CONST",
    "화학": "CHEM",
    "물류": "LOGI",
    "서비스": "SVC",
    "IT": "IT",
    "연구": "R&D",
    "기타": "ETC",
    "공기업": "PUB",
    "공공기관": "PUB",
    "대기업": "BIG",
    "중견기업": "MID",
    "중소기업": "SMB",
}


def make_short_id(job):
    """회사명+모집분야 기반 4자리 고유 ID"""
    company = job.get("company", "")
    position = job.get("position", "")
    seed = (company + "|" + position).encode("utf-8")
    h = hashlib.md5(seed).hexdigest().upper()
    return h[:4]


def build_subject(job):
    """
    제목: ASCII만 사용 (PC 리스트 깨짐 방지)
    형식: [MFG] JOB #A1B2 (~26-08-18)
    """
    category = job.get("category", "기타")
    deadline = job.get("deadline", "")

    # 카테고리 영문 변환
    eng_cat = CATEGORY_MAP.get(category, "JOB")
    if not eng_cat.isascii():
        eng_cat = "JOB"

    # 고유 ID
    short_id = make_short_id(job)
    
    subject = "[" + eng_cat + "] JOB #" + short_id

    # 마감일 (ASCII만 통과)
    if deadline:
        if "채용시" in deadline or "상시" in deadline:
            subject += " (OPEN)"
        else:
            safe_deadline = "".join(
                c for c in deadline if c.isascii() and (c.isdigit() or c in "-./")
            )
            if safe_deadline:
                subject += " (~" + safe_deadline + ")"

    return subject


def build_content(job):
    """본문 - 헤드라인 박스 + 정제된 정보"""
    lines = []
    
    company = clean_forbidden_words(job.get("company", ""))
    position = clean_forbidden_words(job.get("position", ""))
    category = job.get("category", "")
    deadline = job.get("deadline", "")
    career = job.get("career", "")
    location = job.get("location", "")

    # ========== 헤드라인 박스 (진짜 제목 역할) ==========
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
    lines.append("")

    # ========== 채용 정보 요약 ==========
    lines.append("📌 채용 정보")
    lines.append("")

    if company and company != "비공개":
        lines.append("🏢 회사명: " + company)
    if position and position != "상세내용 참조":
        lines.append("👔 모집분야: " + position)
    if career:
        lines.append("💼 경력구분: " + career)
    if location:
        lines.append("📍 근무지: " + location)
    if deadline:
        lines.append("📅 마감일: " + deadline)
    if category:
        lines.append("🏷️ 분류: " + category)

    # ========== 담당업무 (정제된 본문만) ==========
    duty = clean_forbidden_words(job.get("duty", ""))
    duty = clean_duty_text(duty)  # 추가 정제
    
    if duty and len(duty) > 20:
        if len(duty) > 500:
            duty = duty[:497] + "..."
        lines.append("")
        lines.append("📝 담당업무")
        lines.append(duty)

    lines.append("")
    lines.append("─────────────────────────")
    lines.append("")

    # ========== 지원 링크 ==========
    apply_link = job.get("apply_link", "")
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


def clean_duty_text(text):
    """
    담당업무 텍스트 추가 정제
    - 이미 다른 필드에 있는 정보 제거 (회사명, 마감일 등)
    - 불필요한 라벨 제거
    """
    if not text:
        return ""
    
    # BOM 제거
    text = text.replace("\ufeff", "")
    
    # 라인 단위로 처리
    lines = text.split("\n")
    cleaned = []
    
    # 스킵할 라벨 라인 (완전 일치)
    skip_exact = {
        "구인정보", "페이지 정보", "관련링크", "첨부파일",
        "작성일", "조회수", "본문", "채용내용", "상세내용",
        "경력", "경력.", "신입", "신입.", "신입/경력",
        "근무지", "마감일", "회사명", "회사", "기업명"
    }
    
    # 스킵할 라인 (접두어로 시작)
    skip_prefix = [
        "작성일 ", "조회 ", "추천 ", "관련링크",
    ]
    
    prev_line = ""
    for line in lines:
        line = line.strip()
        if not line:
            if prev_line:  # 연속 빈 줄 방지
                cleaned.append("")
                prev_line = ""
            continue
        
        # 완전 일치 스킵
        if line in skip_exact:
            continue
        
        # 접두어 스킵
        if any(line.startswith(p) for p in skip_prefix):
            continue
        
        # 시간 정보만 있는 라인 (예: "1시간 전", "32")
        if line.endswith("전") and len(line) < 10:
            continue
        if line.isdigit() and len(line) < 5:
            continue
        
        # 날짜만 있는 라인 (예: "26-08-18")
        if len(line) < 12 and all(c.isdigit() or c == "-" for c in line):
            continue
        
        cleaned.append(line)
        prev_line = line
    
    result = "\n".join(cleaned).strip()
    
    # 연속 공백 정리
    while "\n\n\n" in result:
        result = result.replace("\n\n\n", "\n\n")
    
    return result


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
