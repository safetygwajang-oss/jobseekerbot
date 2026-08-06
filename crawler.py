import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

BASE_URL = "https://isafety.co.kr"
LIST_URL = "https://isafety.co.kr/is/job"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# 재시도 설정
MAX_RETRIES = 3
RETRY_DELAY = 10

# 외부 링크 판별
EXCLUDE_DOMAINS = ["isafety.co.kr"]
EXCLUDE_PATTERNS = [
    "facebook.com/sharer", "twitter.com/intent", "twitter.com/share",
    "plus.google.com", "kakao.com/share", "band.us/share", "pinterest.com/pin",
    ".jpg", ".jpeg", ".png", ".gif", ".webp",
    ".pdf", ".hwp", ".doc", ".docx",
    "javascript:", "mailto:", "tel:",
]

URL_PATTERN = re.compile(r'https?://[^\s\'"<>()]+', re.IGNORECASE)


# ==========================================================
# 🔁 재시도 기능이 있는 requests.get 래퍼
# ==========================================================
def safe_get(url, timeout=15):
    """네트워크 오류 시 자동 재시도"""
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            res = requests.get(url, headers=HEADERS, timeout=timeout)
            res.encoding = "utf-8"
            return res
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.RequestException) as e:
            last_error = e
            print(f"    ⚠️ 요청 실패 (시도 {attempt}/{MAX_RETRIES}): {type(e).__name__}")
            if attempt < MAX_RETRIES:
                print(f"    ⏳ {RETRY_DELAY}초 후 재시도...")
                time.sleep(RETRY_DELAY)

    print(f"    ❌ 최종 실패: {url}")
    raise last_error


# ==========================================================
# 리스트 페이지 파싱 유틸
# ==========================================================
def parse_first_cell(text):
    """'안전(CM) 건설 · 26-08-01 · 139' 형태 분해"""
    parts = [p.strip() for p in text.split("·")]

    if len(parts) >= 3:
        first = parts[0]
        tokens = first.rsplit(" ", 1)
        if len(tokens) == 2:
            position, category = tokens[0].strip(), tokens[1].strip()
        else:
            position, category = first, ""
        return position, category, parts[1], parts[2]
    elif len(parts) == 2:
        return parts[0], "", parts[1], ""
    else:
        return text.strip(), "", "", ""


def extract_job_id(href):
    """URL에서 게시글 ID 추출"""
    if "wr_id=" in href:
        m = re.search(r"wr_id=(\d+)", href)
        if m:
            return m.group(1)
    if "/is/job/" in href:
        part = href.split("/is/job/")[1]
        if part.startswith("p"):
            return None
        m = re.match(r"(\d+)", part)
        if m:
            return m.group(1)
    return None


# ==========================================================
# 외부 지원 링크 추출
# ==========================================================
def is_valid_external_link(url):
    """iSAFETY 자체 도메인이 아닌 유효한 외부 링크인지 판별"""
    if not url:
        return False

    url_lower = url.lower().strip()

    if not (url_lower.startswith("http://") or url_lower.startswith("https://")):
        return False

    for domain in EXCLUDE_DOMAINS:
        if domain in url_lower:
            return False

    for pattern in EXCLUDE_PATTERNS:
        if pattern in url_lower:
            return False

    return True


def extract_apply_link(soup, raw_html):
    """상세 페이지에서 외부 지원 링크 추출"""
    # 1) <a href>
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if is_valid_external_link(href):
            return href

    # 2) <iframe src>
    for iframe in soup.find_all("iframe", src=True):
        src = iframe["src"].strip()
        if is_valid_external_link(src):
            return src

    # 3) onclick 내부
    for tag in soup.find_all(attrs={"onclick": True}):
        onclick = tag["onclick"]
        for url in URL_PATTERN.findall(onclick):
            cleaned = url.rstrip("'\";,)>]}")
            if is_valid_external_link(cleaned):
                return cleaned

    # 4) 전체 HTML 정규식 스캔
    for url in URL_PATTERN.findall(raw_html):
        cleaned = url.rstrip("'\";,)>]}")
        if is_valid_external_link(cleaned):
            return cleaned

    return ""


# ==========================================================
# 본문 텍스트 정제
# ==========================================================
def extract_clean_body(soup):
    """
    iSAFETY 상세페이지에서 진짜 본문만 추출
    구조:
      - 상단: 카테고리, 회사명, 조회수
      - 중단: 경력/근무지/마감일 테이블
      - 하단: (주)XXX 로 시작하는 본문 ← 여기만!
    """
    full_text = soup.get_text("\n", strip=True)
    lines = [ln.strip() for ln in full_text.split("\n") if ln.strip()]

    body_start_idx = -1

    # 전략 1: 회사명 시작 패턴
    body_start_patterns = [
        "(주)", "㈜", "주식회사", "[주식회사]",
        "회사소개", "채용안내", "모집안내"
    ]
    for i, line in enumerate(lines):
        for pattern in body_start_patterns:
            if line.startswith(pattern):
                body_start_idx = i
                break
        if body_start_idx != -1:
            break

    # 전략 2: '본문' 라벨 이후
    if body_start_idx == -1:
        for i, line in enumerate(lines):
            if line in ("본문", "상세내용", "채용내용"):
                body_start_idx = i + 1
                break

    # 전략 3: 채용/모집 키워드 포함 긴 라인
    if body_start_idx == -1:
        for i, line in enumerate(lines):
            if len(line) > 20 and ("채용" in line or "모집" in line):
                body_start_idx = i
                break

    if body_start_idx == -1:
        body_start_idx = 0

    body_lines = lines[body_start_idx:]

    # 끝 지점 찾기
    end_markers = [
        "이전글", "다음글", "목록", "댓글",
        "관련 채용정보", "관련채용정보", "이 채용정보와 유사한",
        "Copyright", "COPYRIGHT", "이용약관", "개인정보처리방침",
        "SNS 공유", "공유하기", "카카오톡으로 공유", "페이스북으로 공유"
    ]

    end_idx = len(body_lines)
    for i, line in enumerate(body_lines):
        matched = False
        for marker in end_markers:
            if marker in line:
                end_idx = i
                matched = True
                break
        if matched:
            break

    body_lines = body_lines[:end_idx]

    # 라인 필터링
    skip_exact = {
        "구인정보", "페이지 정보", "관련링크", "첨부파일",
        "작성일", "조회수", "본문", "채용내용", "상세내용",
        "경력", "경력.", "신입", "신입.", "신입/경력", "무관",
        "근무지", "마감일", "회사명", "회사", "기업명", "채용시",
    }

    cleaned = []
    for line in body_lines:
        line = line.replace("\ufeff", "").strip()
        if not line:
            continue

        if line in skip_exact:
            continue

        if len(line) < 12 and (line.endswith("전") or line.endswith("초 전")):
            continue

        if line.isdigit() and len(line) < 6:
            continue

        if len(line) < 12 and all(c.isdigit() or c in "-." for c in line):
            continue

        cleaned.append(line)

    return "\n".join(cleaned).strip()


# ==========================================================
# 상세 페이지 fetch
# ==========================================================
def fetch_detail(detail_url):
    """상세 페이지 - 본문 + 외부 링크 추출 (실패해도 빈 값)"""
    try:
        res = safe_get(detail_url, timeout=15)
        raw_html = res.text
        soup = BeautifulSoup(raw_html, "lxml")

        body_text = extract_clean_body(soup)
        apply_link = extract_apply_link(soup, raw_html)

        if apply_link:
            try:
                domain = urlparse(apply_link).netloc
            except Exception:
                domain = "?"
            print(f"    🔗 지원링크 [{domain}]: {apply_link[:70]}")
        else:
            print(f"    ⚠️ 외부 지원링크 없음")

        return body_text, apply_link
    except Exception as e:
        print(f"    ⚠️ 상세페이지 스킵: {type(e).__name__}")
        return "", ""


# ==========================================================
# 리스트 페이지 fetch
# ==========================================================
def get_jobs_from_page(page=1, with_detail=True):
    """리스트 페이지에서 채용공고 파싱"""
    url = f"{LIST_URL}/p{page}" if page > 1 else LIST_URL
    print(f"📄 페이지 접근: {url}")

    try:
        res = safe_get(url, timeout=15)
    except Exception as e:
        print(f"  ❌ 페이지 접근 최종 실패: {type(e).__name__}")
        return []

    soup = BeautifulSoup(res.text, "lxml")

    target_table = None
    for t in soup.find_all("table"):
        headers = [th.get_text(strip=True) for th in t.find_all("th")]
        if "모집분야" in headers and "마감일" in headers:
            target_table = t
            break

    if not target_table:
        print("  ❌ 채용공고 테이블 못 찾음")
        return []

    jobs = []
    rows = target_table.find_all("tr")

    for row in rows:
        tds = row.find_all("td")
        if len(tds) < 5:
            continue

        first_cell = tds[0]
        link = first_cell.find("a", href=True)
        if not link:
            continue

        href = link["href"]
        job_id = extract_job_id(href)
        if not job_id:
            continue

        detail_url = urljoin(BASE_URL, href)
        first_text = tds[0].get_text(" ", strip=True)
        company = tds[1].get_text(" ", strip=True)
        career = tds[2].get_text(" ", strip=True).rstrip(".")
        location = tds[3].get_text(" ", strip=True)
        deadline = tds[4].get_text(" ", strip=True)

        position, category, reg_date, views = parse_first_cell(first_text)
        raw_title = f"[{category}] {position}" if category else position

        jobs.append({
            "job_id": job_id,
            "detail_url": detail_url,
            "raw_title": raw_title,
            "position": position,
            "category": category,
            "company": company,
            "career": career,
            "location": location,
            "deadline": deadline,
            "reg_date": reg_date,
            "views": views,
            "duty": "",
            "apply_link": "",
        })

    print(f"  ✅ 리스트 파싱: {len(jobs)}건")

    if with_detail:
        for j in jobs:
            print(f"  📖 상세: {j['company']} - {j['position'][:30]}")
            duty, apply_link = fetch_detail(j["detail_url"])
            if duty:
                j["duty"] = duty
            if apply_link:
                j["apply_link"] = apply_link

    return jobs


def get_all_jobs(max_pages=2):
    """여러 페이지에서 공고 수집"""
    all_jobs = []
    seen_ids = set()

    for page in range(1, max_pages + 1):
        try:
            jobs = get_jobs_from_page(page, with_detail=True)
            for j in jobs:
                if j["job_id"] not in seen_ids:
                    seen_ids.add(j["job_id"])
                    all_jobs.append(j)
        except Exception as e:
            print(f"  ⚠️ 페이지 {page} 스킵: {type(e).__name__}")
            continue

    with_link = sum(1 for j in all_jobs if j.get("apply_link"))
    print(f"\n📊 총 수집: {len(all_jobs)}건")
    if len(all_jobs) > 0:
        print(f"🔗 지원링크 확보: {with_link}건 / {len(all_jobs)}건 ({with_link*100//len(all_jobs)}%)")

    return all_jobs


if __name__ == "__main__":
    jobs = get_all_jobs(max_pages=1)
    print("\n" + "=" * 60)
    print("샘플 5건:")
    print("=" * 60)
    for j in jobs[:5]:
        print(f"\n📌 [{j['category']}] {j['position']}")
        print(f"   회사: {j['company']}")
        print(f"   경력: {j['career']} | 마감: {j['deadline']}")
        print(f"   🔗 링크: {j['apply_link'] if j['apply_link'] else '(없음)'}")
        if j['duty']:
            print(f"   📝 본문 미리보기: {j['duty'][:100]}...")
