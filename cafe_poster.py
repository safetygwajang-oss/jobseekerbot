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
 
 
def to_html_entity(text):
    """비-ASCII 문자를 HTML 엔티티로 변환 (본문 전용)"""
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
    forbidden = ["iSAFETY", "isafety", "ISAFETY", "iSafety"]
    for word in forbidden:
        text = text.replace(word, "")
    text = text.replace("  ", " ").strip()
    while text and text[0] in ">/<|- ":
        text = text[1:].strip()
    while text and text[-1] in ">/<|- ":
        text = text[:-1].strip()
    return text
 
 
def clean_path_title(title):
    """경로형 제목 정리: 'A > B > C' → 마지막 유의미한 부분 추출"""
    if not title:
        return title
    if ">" in title:
        parts = [p.strip() for p in title.split(">")]
        parts = [clean_forbidden_words(p) for p in parts]
        skip_words = ["구인정보", "채용정보", "채용", "구인", ""]
        meaningful = [p for p in parts if p and p not in skip_words]
        if meaningful:
            return meaningful[0]
    return title
 
 
# ── 제목 템플릿용 추가 함수 ────────────────────────────────
 
def detect_experience(text):
    """텍스트에서 경력구분 추출: 신입 / 경력 / 신입경력"""
    if not text:
        return "경력무관"
    has_new = "신입" in text
    has_exp = any(k in text for k in ["경력", "년이상", "년 이상", "년차"])
    # '경력무관' 이라는 표현 자체는 경력 요구가 아님
    if "경력무관" in text or "무관" in text:
        has_exp = False if not has_exp else has_exp
 
    if has_new and has_exp:
        return "신입경력"
    if has_new:
        return "신입"
    if has_exp:
        return "경력"
    return "경력무관"
 
 
def normalize_category(category_raw, fallback_text=""):
    """카테고리를 [건설/제조/공공/기타] 중 하나로 정규화"""
    target = {"건설", "제조", "공공", "기타"}
    if category_raw and category_raw.strip() in target:
        return category_raw.strip()
 
    text = (category_raw or "") + " " + (fallback_text or "")
    if any(k in text for k in ["건설", "토목", "건축", "시공", "현장"]):
        return "건설"
    if any(k in text for k in ["제조", "생산", "공장", "화학", "플랜트"]):
        return "제조"
    if any(k in text for k in ["공공", "관공서", "지자체", "공기업", "공사", "공단"]):
        return "공공"
    return "기타"
 
 
def extract_duty_part(job):
    """담당업무/모집분야에서 제목에 넣을 핵심 텍스트 추출"""
    position = clean_forbidden_words(job.get("position", ""))
    duty = clean_forbidden_words(job.get("duty", ""))
    raw_title = clean_forbidden_words(job.get("raw_title", ""))
 
    if position and position != "상세내용 참조":
        part = clean_path_title(position)
        if part:
            return part
    if duty and duty != "상세내용 참조":
        part = clean_path_title(duty)
        if part:
            return part[:40] + "..." if len(part) > 40 else part
    if raw_title:
        part = clean_path_title(raw_title)
        if part:
            return part
    return ""
 
 
# ── 제목/본문 생성 ────────────────────────────────
 
def build_subject(job):
    """
    제목 템플릿: [신입/경력/신입경력] [건설/제조/공공/기타] [회사명] [담당업무]
    엔티티 인코딩은 하지 않음 (제목 깨짐 방지 → post_to_cafe에서 UTF-8 그대로 전송)
    """
    company = clean_forbidden_words(job.get("company", "")) or "비공개"
    position = clean_forbidden_words(job.get("position", ""))
    duty = clean_forbidden_words(job.get("duty", ""))
    raw_title = clean_forbidden_words(job.get("raw_title", ""))
    category_raw = job.get("category", "")
 
    combined_text = " ".join([position or "", duty or "", raw_title or "", category_raw or ""])
 
    exp = detect_experience(combined_text)
    category = normalize_category(category_raw, combined_text)
    duty_part = extract_duty_part(job)
 
    parts = ["[" + exp + "]", "[" + category + "]"]
    parts.append("[" + company + "]")
    if duty_part:
        parts.append("[" + duty_part + "]")
 
    title = " ".join(parts)
 
    # 길이 제한 (엔티티 변환 전이므로 단순 문자수 기준으로 안전하게 자름)
    if len(title) > 80:
        title = title[:77] + "..."
    return title
 
 
def build_content(job):
    """본문 생성 - 출처 노출 없이"""
    lines = []
    lines.append("📌 채용 정보")
    lines.append("")
 
    company = clean_forbidden_words(job.get("company", ""))
    if company and company != "비공개":
        lines.append("🏢 회사명: " + company)
 
    position = clean_forbidden_words(job.get("position", ""))
    if position and position != "상세내용 참조":
        position = clean_path_title(position)
        if position:
            lines.append("👔 모집분야: " + position)
 
    duty = clean_forbidden_words(job.get("duty", ""))
    if duty and duty != "상세내용 참조":
        if len(duty) > 300:
            duty = duty[:297] + "..."
        lines.append("📝 담당업무: " + duty)
 
    deadline = job.get("deadline", "")
    if deadline:
        lines.append("📅 마감일: " + deadline)
 
    category = job.get("category", "")
    if category:
        lines.append("🏷️ 분류: " + category)
 
    lines.append("")
    lines.append("─────────────────────────")
    lines.append("")
 
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
 
    # ⭐ 변경점: 제목(subject)은 엔티티 인코딩 없이 UTF-8 그대로 전송
    #    (requests가 form data 전송 시 UTF-8 기준으로 자동 percent-encoding 처리)
    # 본문(content)은 기존처럼 엔티티 인코딩 유지 (정상 동작 중이므로 그대로)
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
            "subject": subject,
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
