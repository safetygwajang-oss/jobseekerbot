import os
import re
import requests

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


# ==========================================================
# 🎯 제목 생성 - 영문 회사명 조합
# ==========================================================
CAREER_MAP = {
    "신입": "NEW",
    "경력": "EXP",
    "신입/경력": "NEW/EXP",
    "무관": "ANY",
    "인턴": "INTERN",
}

# 유명 기업 매핑
FAMOUS_COMPANIES = {
    "삼성전자": "SAMSUNG",
    "삼성물산": "SAMSUNG-CT",
    "삼성디스플레이": "SAMSUNG-DP",
    "삼성SDI": "SAMSUNG-SDI",
    "삼성엔지니어링": "SAMSUNG-ENG",
    "삼성중공업": "SAMSUNG-HI",
    "삼성바이오로직스": "SAMSUNG-BIO",
    "SK하이닉스": "SK-HYNIX",
    "SK이노베이션": "SK-INNO",
    "SK에너지": "SK-ENERGY",
    "SK온": "SK-ON",
    "LG전자": "LG-ELEC",
    "LG화학": "LG-CHEM",
    "LG디스플레이": "LG-DP",
    "LG에너지솔루션": "LG-ES",
    "LG유플러스": "LG-UPLUS",
    "현대자동차": "HYUNDAI-MOTOR",
    "현대차": "HYUNDAI-MOTOR",
    "기아": "KIA",
    "현대모비스": "MOBIS",
    "현대건설": "HYUNDAI-ENC",
    "현대엔지니어링": "HYUNDAI-ENG",
    "현대제철": "HYUNDAI-STEEL",
    "포스코": "POSCO",
    "포스코이앤씨": "POSCO-ENC",
    "포스코퓨처엠": "POSCO-FM",
    "롯데케미칼": "LOTTE-CHEM",
    "롯데건설": "LOTTE-ENC",
    "GS건설": "GS-ENC",
    "GS칼텍스": "GS-CALTEX",
    "대우건설": "DAEWOO-ENC",
    "DL이앤씨": "DL-ENC",
    "SK에코플랜트": "SK-ECO",
    "한화건설": "HANWHA-ENC",
    "한화솔루션": "HANWHA-SOL",
    "두산에너빌리티": "DOOSAN-ENB",
    "HD현대중공업": "HD-HHI",
    "메디톡스": "MEDYTOX",
    "에어퍼스트": "AIRFIRST",
    "금강종합건설": "KUMKANG",
    "CJ제일제당": "CJ-CJ",
    "CJ대한통운": "CJ-LOG",
    "쿠팡": "COUPANG",
    "네이버": "NAVER",
    "카카오": "KAKAO",
}

CHOSUNG = ['G', 'GG', 'N', 'D', 'DD', 'R', 'M', 'B', 'BB', 'S', 'SS', '', 'J', 'JJ', 'CH', 'K', 'T', 'P', 'H']
JUNGSUNG = ['A', 'AE', 'YA', 'YAE', 'EO', 'E', 'YEO', 'YE', 'O', 'WA', 'WAE', 'OE', 'YO', 'U', 'WO', 'WE', 'WI', 'YU', 'EU', 'YI', 'I']
JONGSUNG = ['', 'G', 'GG', 'GS', 'N', 'NJ', 'NH', 'D', 'L', 'LG', 'LM', 'LB', 'LS', 'LT', 'LP', 'LH', 'M', 'B', 'BS', 'S', 'SS', 'NG', 'J', 'CH', 'K', 'T', 'P', 'H']


def korean_to_roman(text):
    """한글을 간이 로마자로 변환 (식별용)"""
    result = []
    for ch in text:
        code = ord(ch)
        if 0xAC00 <= code <= 0xD7A3:
            base = code - 0xAC00
            cho = base // (21 * 28)
            jung = (base % (21 * 28)) // 28
            jong = base % 28
            result.append(CHOSUNG[cho] + JUNGSUNG[jung] + JONGSUNG[jong])
        elif ch.isascii():
            result.append(ch.upper() if ch.isalpha() else ch)
        elif ch in " -_/":
            result.append("-")

    roman = "".join(result)
    if len(roman) > 20:
        roman = roman[:20]
    return roman if roman else "COMPANY"


def romanize_company(company):
    """회사명을 영문(로마자)로 변환"""
    if not company:
        return "COMPANY"

    # 법인 형태 표기 제거
    company = re.sub(r"\(주\)|\(유\)|\(재\)|\(사\)|\(합\)|\(합자\)|\(사단법인\)|\(재단법인\)", "", company)
    company = company.replace("주식회사", "").replace("유한회사", "").replace("㈜", "")
    company = company.strip()

    if company in FAMOUS_COMPANIES:
        return FAMOUS_COMPANIES[company]

    return korean_to_roman(company)


def build_subject(job):
    """
    제목: [EXP] [KUMKANG] (~26-08-28)
    - 완전 ASCII: PC 리스트에서 안 깨짐
    - 신입/경력 + 영문 회사명 + 마감일
    """
    career = job.get("career", "").strip()
    company = job.get("company", "").strip()
    deadline = job.get("deadline", "").strip()

    career_clean = career.rstrip(".").strip()
    career_eng = CAREER_MAP.get(career_clean, "JOB")

    company_clean = clean_forbidden_words(company)
    company_eng = romanize_company(company_clean) if company_clean else "COMPANY"

    subject = "[" + career_eng + "] [" + company_eng + "]"

    if deadline:
        if "채용시" in deadline or "상시" in deadline:
            subject += " (OPEN)"
        else:
            safe_deadline = "".join(
                c for c in deadline if c.isascii() and (c.isdigit() or c in "-./")
            )
            if safe_deadline:
                subject += " (~" + safe_deadline + ")"

    if len(subject) > 80:
        subject = subject[:77] + "..."

    return subject


# ==========================================================
# 📝 본문 생성
# ==========================================================
def strip_urls_from_duty(duty, apply_link):
    """담당업무 텍스트에서 URL 라인 제거 (하단 지원링크와 중복 방지)"""
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
    """본문 생성"""
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

    # 담당업무 (URL 제거)
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

    # 지원 링크 (한 번만)
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
# 게시
# ==========================================================
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
