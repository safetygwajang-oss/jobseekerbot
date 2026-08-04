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
    """출처가 드러나는 단어 제거"""
    if not text:
        return text
    # 금칙어 리스트 (대소문자 구분 없이)
    forbidden = ["iSAFETY", "isafety", "ISAFETY", "iSafety"]
    for word in forbidden:
        text = text.replace(word, "")
    # 정리: 연속 공백, 앞뒤 특수문자 제거
    text = text.replace("  ", " ").strip()
    # 앞뒤에 남은 > < / | 등 제거
    while text and text[0] in ">/<|- ":
        text = text[1:].strip()
    while text and text[-1] in ">/<|- ":
        text = text[:-1].strip()
    return text


def clean_path_title(title):
    """경로형 제목 정리: 'A > B > C' → 마지막 유의미한 부분 추출"""
    if ">" in title:
        parts = [p.strip() for p in title.split(">")]
        # 각 부분에서 금칙어 제거
        parts = [clean_forbidden_words(p) for p in parts]
        # 빈 값과 일반 카테고리 단어 제거
        skip_words = ["구인정보", "채용정보", "채용", "구인", ""]
        meaningful = [p for p in parts if p and p not in skip_words]
        if meaningful:
            # 가장 구체적인 정보(보통 첫 번째)를 선택
            return meaningful[0]
    return title


def build_headline(job):
    """본문 최상단에 표시할 '진짜 제목' 생성
    
    PC 리스트에서 한글이 깨져 보이는 문제를 우회하기 위해,
    실제 정보는 본문 최상단에 크게 표시함.
    """
    category = job.get("category", "기타")
    company = job.get("company", "비공개")
    position = job.get("position", "")
    raw_title = job.get("raw_title", "")

    # 금칙어 제거
    company = clean_forbidden_words(company)
    position = clean_forbidden_words(position)
    raw_title = clean_forbidden_words(raw_title)

    # 회사명이 있으면 우선 사용
    if company and company != "비공개":
        headline = "[" + category + "] " + company
        if position and position != "상세내용 참조":
            clean_pos = clean_path_title(position)
            if clean_pos and clean_pos != company:
                headline += " - " + clean_pos
    else:
        clean_title = clean_path_title(raw_title) if raw_title else ""
        if not clean_title:
            clean_title = clean_path_title(position) if position else "채용공고"
        headline = "[" + category + "] " + clean_title

    return headline


def build_subject(job):
    """제목 생성 - PC 리스트에서 깨져도 알아볼 수 있는 최소 형태
    
    한글이 HTML 엔티티(&#숫자;)로 노출되어도 카테고리는 알아볼 수 있도록
    분류만 한글로 넣고, 나머지는 영문/기호로 처리.
    상세 정보는 본문 최상단 headline에서 확인.
    """
    category = job.get("category", "기타")

    # 카테고리별 영문 태그 매핑 (PC 리스트에서 깨져도 알아볼 수 있게)
    category_tag_map = {
        "건설": "CONSTRUCTION",
        "제조": "MANUFACTURING",
        "화학": "CHEMICAL",
        "기타": "ETC",
    }
    eng_tag = category_tag_map.get(category, "JOB")

    # 형식: [CONSTRUCTION|건설] NEW JOB POST
    # → 한글 부분이 깨져도 영문으로 카테고리 파악 가능
    subject = "[" + eng_tag + "] NEW JOB - " + category

    return subject


def build_content(job):
    """본문 생성 - 최상단에 '진짜 제목' 크게 표시"""
    lines = []

    # ========================================
    # 🎯 본문 최상단: 진짜 제목 역할 (강조 박스)
    # ========================================
    headline = build_headline(job)
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("📢 " + headline)
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append("")

    # ========================================
    # 상세 정보
    # ========================================
    lines.append("📌 채용 상세 정보")
    lines.append("")

    # 회사명
    company = clean_forbidden_words(job.get("company", ""))
    if company and company != "비공개":
        lines.append("🏢 회사명: " + company)

    # 모집분야
    position = clean_forbidden_words(job.get("position", ""))
    if position and position != "상세내용 참조":
        position = clean_path_title(position)
        if position:
            lines.append("👔 모집분야: " + position)

    # 담당업무
    duty = clean_forbidden_words(job.get("duty", ""))
    if duty and duty != "상세내용 참조":
        if len(duty) > 300:
            duty = duty[:297] + "..."
        lines.append("📝 담당업무: " + duty)

    # 마감일
    deadline = job.get("deadline", "")
    if deadline:
        lines.append("📅 마감일: " + deadline)

    # 카테고리
    category = job.get("category", "")
    if category:
        lines.append("🏷️ 분류: " + category)

    lines.append("")
    lines.append("─────────────────────────")
    lines.append("")

    # 지원 링크
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
    print("  📢 본문 헤드라인:", build_headline(job))

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
