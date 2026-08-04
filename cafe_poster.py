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
    """비-ASCII 문자를 HTML 엔티티로 변환 (본문용)"""
    if not text:
        return ""
    result = ""
    for ch in text:
        if ord(ch) < 128:
            result += ch
        else:
            result += "&#" + str(ord(ch)) + ";"
    return result

def clean_forbidden_words(text):
    """출처가 드러나는 단어 제거 및 불필요 특수문자/공백 정돈"""
    if not text:
        return ""
    forbidden = ["iSAFETY", "isafety", "ISAFETY", "iSafety"]
    for word in forbidden:
        text = text.replace(word, "")
    
    # 줄바꿈 제거 및 연속 공백 정리
    text = " ".join(text.split())
    
    # 앞뒤 불필요한 특수문자 제거
    while text and text[0] in ">/<|- 癤 ":
        text = text[1:].strip()
    while text and text[-1] in ">/<|- 癤 ":
        text = text[:-1].strip()
    return text

def clean_path_title(title):
    """경로형 텍스트 정리: 구인정보, 기타 등 노이즈 단어 제거 후 핵심 추출"""
    if not title:
        return ""
    
    # '>' 구분자 제거
    parts = [p.strip() for p in title.split(">")]
    parts = [clean_forbidden_words(p) for p in parts]
    
    # 노이즈 단어 리스트
    skip_words = ["구인정보", "채용정보", "채용", "구인", "기타", "페이지 정보", "작성일", "관련링크", ""]
    meaningful = [p for p in parts if p and p not in skip_words]
    
    if meaningful:
        return meaningful[0]
    return title

def build_subject(job):
    """
    제목 템플릿: [신입/경력/신입경력] [건설/제조/공공/기타] [회사명] [담당업무]
    본문에 출력되는 것과 동일한 한글 텍스트를 추출해 조립
    """
    # 1. 고용 형태 [신입 / 경력 / 신입경력]
    exp_raw = str(job.get("experience_type", job.get("type", "")))
    if "신입" in exp_raw and "경력" in exp_raw:
        exp_tag = "신입경력"
    elif "신입" in exp_raw:
        exp_tag = "신입"
    elif "경력" in exp_raw:
        exp_tag = "경력"
    else:
        exp_tag = "신입경력"

    # 2. 카테고리 [건설 / 제조 / 공공 / 기타]
    cat_raw = str(job.get("category", ""))
    if cat_raw in ["건설", "제조", "공공"]:
        cat_tag = cat_raw
    else:
        cat_tag = "기타"

    # 3. 회사명 (본문에 나오는 회사명과 동일)
    company = clean_forbidden_words(job.get("company", ""))
    if not company or company == "비공개":
        company = "비공개"

    # 4. 담당업무 (모집분야 > duty > position 순으로 깨끗한 한글만 파싱)
    position = clean_forbidden_words(job.get("position", ""))
    duty = clean_forbidden_words(job.get("duty", ""))
    
    # 모집분야(position)가 잘 들어와있다면 최우선 사용
    clean_duty = clean_path_title(position) if position and position != "상세내용 참조" else ""
    
    # 모집분야가 없으면 duty 파싱
    if not clean_duty and duty and duty != "상세내용 참조":
        # 본문 전체가 들어오는 케이스 방지 (첫 줄 또는 핵심 키워드만 추출)
        first_line = duty.split("\n")[0]
        clean_duty = clean_path_title(first_line)

    # 그래도 없으면 raw_title 사용
    if not clean_duty:
        raw_title = clean_forbidden_words(job.get("raw_title", ""))
        clean_duty = clean_path_title(raw_title) if raw_title else "채용공고"

    # 포맷 구성
    subject = f"[{exp_tag}] [{cat_tag}] [{company}] [{clean_duty}]"

    # 제목 길이 제한 (네이버 카페 기준 80자)
    if len(subject) > 80:
        subject = subject[:77] + "..."
        
    return subject

def build_content(job):
    """본문 생성"""
    lines = []
    lines.append("📌 채용 정보")
    lines.append("")

    # 회사명
    company = clean_forbidden_words(job.get("company", ""))
    if company and company != "비공개":
        lines.append("🏢 회사명: " + company)

    # 모집분야
    position = clean_forbidden_words(job.get("position", ""))
    if position and position != "상세내용 참조":
        clean_pos = clean_path_title(position)
        if clean_pos:
            lines.append("👔 모집분야: " + clean_pos)

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

    # 지원 링크만 표시
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

    print("  📝 생성된 제목:", subject)

    # 본문은 기존처럼 HTML 엔티티 변환
    encoded_content = to_html_entity(content)

    url = f"https://openapi.naver.com/v1/cafe/{CAFE_ID}/menu/{MENU_ID}/articles"
    headers = {
        "Authorization": f"Bearer {access_token}",
        # UTF-8 인코딩을 명시적으로 헤더에 지정
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
    }

    # 💡 [핵심 해결책] 
    # requests가 파이썬 서버 환경 인코딩을 타지 않도록 subject와 content를 
    # UTF-8 바이트로 명시적 변환 전송합니다.
    payload = {
        "subject": subject.encode("utf-8"),
        "content": encoded_content.encode("utf-8"),
        "openyn": "true",
    }

    res = requests.post(
        url,
        headers=headers,
        data=payload,
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
