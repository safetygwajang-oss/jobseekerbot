import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

BASE_URL = "https://isafety.co.kr"
LIST_URL = "https://isafety.co.kr/is/job"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ==========================================================
# 🎯 링크 판별 로직 (블랙리스트 방식)
# → iSAFETY 자체 도메인만 제외하고, 나머지 외부 링크는 모두 허용
# → 사람인, SK career, 삼성 recruit, 회사 자체 홈페이지 등 모두 커버
# ==========================================================

# 제외할 도메인 (iSAFETY 자기 자신 + 흔한 무의미 링크)
EXCLUDE_DOMAINS = [
    "isafety.co.kr",
]

# 제외할 URL 패턴 (SNS 공유, 이미지 등)
EXCLUDE_PATTERNS = [
    "facebook.com/sharer",
    "twitter.com/intent",
    "twitter.com/share",
    "plus.google.com",
    "kakao.com/share",
    "band.us/share",
    "pinterest.com/pin",
    ".jpg", ".jpeg", ".png", ".gif", ".webp",  # 이미지 파일
    ".pdf", ".hwp", ".doc", ".docx",  # 문서는 별도 처리 (아래 참고)
    "javascript:",
    "mailto:",
    "tel:",
]

URL_PATTERN = re.compile(
    r'https?://[^\s\'"<>()]+',
    re.IGNORECASE
)


def parse_first_cell(text):
    """
    '안전(CM) 건설 · 26-08-01 · 139' 형태를 분해
    """
    parts = [p.strip() for p in text.split("·")]
    
    if len(parts) >= 3:
        first = parts[0]
        tokens = first.rsplit(" ", 1)
        if len(tokens) == 2:
            position, category = tokens[0].strip(), tokens[1].strip()
        else:
            position, category = first, ""
        reg_date = parts[1]
        views = parts[2]
        return position, category, reg_date, views
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


def is_valid_external_link(url):
    """
    외부 지원 링크로 인정할지 판별
    - http/https 로 시작해야 함
    - iSAFETY 자체 도메인이 아니어야 함
    - SNS 공유/이미지/문서가 아니어야 함
    """
    if not url:
        return False
    
    url_lower = url.lower().strip()
    
    # http/https 만 허용
    if not (url_lower.startswith("http://") or url_lower.startswith("https://")):
        return False
    
    # 제외 도메인 체크
    for domain in EXCLUDE_DOMAINS:
        if domain in url_lower:
            return False
    
    # 제외 패턴 체크
    for pattern in EXCLUDE_PATTERNS:
        if pattern in url_lower:
            return False
    
    return True


def extract_apply_link(soup, raw_html):
    """
    상세 페이지에서 외부 지원 링크 추출
    우선순위:
      1) <a href="..."> 태그 (가장 신뢰도 높음)
      2) <iframe src="..."> 태그
      3) onclick 속성 내부 URL
      4) 페이지 전체 HTML에서 정규식 매칭
    """
    # 1) <a href> 스캔
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if is_valid_external_link(href):
            return href

    # 2) <iframe src> 스캔
    for iframe in soup.find_all("iframe", src=True):
        src = iframe["src"].strip()
        if is_valid_external_link(src):
            return src

    # 3) onclick 속성 스캔
    for tag in soup.find_all(attrs={"onclick": True}):
        onclick = tag["onclick"]
        urls_in_onclick = URL_PATTERN.findall(onclick)
        for url in urls_in_onclick:
            cleaned = url.rstrip("'\";,)>]}")
            if is_valid_external_link(cleaned):
                return cleaned

    # 4) 페이지 전체 HTML에서 정규식으로 스캔
    all_urls = URL_PATTERN.findall(raw_html)
    for url in all_urls:
        cleaned = url.rstrip("'\";,)>]}")
        if is_valid_external_link(cleaned):
            return cleaned

    return ""


def fetch_detail(detail_url):
    """상세 페이지에서 본문 + 외부 링크 추출"""
    try:
        res = requests.get(detail_url, headers=HEADERS, timeout=15)
        res.encoding = "utf-8"
        raw_html = res.text
        soup = BeautifulSoup(raw_html, "lxml")
        
        # ==== 본문 텍스트 추출 ====
        body_text = ""
        candidates = soup.find_all(["div", "td", "section", "article"])
        best = ""
        for c in candidates:
            txt = c.get_text("\n", strip=True)
            if any(kw in txt for kw in ["자격요건", "주요업무", "우대사항", "담당업무"]):
                if 50 < len(txt) < 3000 and len(txt) > len(best):
                    best = txt
        body_text = best
        
        # ==== 외부 지원 링크 추출 ====
        apply_link = extract_apply_link(soup, raw_html)
        
        if apply_link:
            # 어떤 사이트인지 로그로 표시
            try:
                domain = urlparse(apply_link).netloc
            except Exception:
                domain = "?"
            print(f"    🔗 지원링크 발견 [{domain}]: {apply_link[:70]}")
        else:
            print(f"    ⚠️ 외부 지원링크 없음")
        
        return body_text, apply_link
    except Exception as e:
        print(f"    ⚠️ 상세페이지 오류: {e}")
        return "", ""


def get_jobs_from_page(page=1, with_detail=True):
    """리스트 페이지에서 채용공고 파싱"""
    url = f"{LIST_URL}/p{page}" if page > 1 else LIST_URL
    print(f"📄 페이지 접근: {url}")
    
    res = requests.get(url, headers=HEADERS, timeout=15)
    res.encoding = "utf-8"
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
        jobs = get_jobs_from_page(page, with_detail=True)
        for j in jobs:
            if j["job_id"] not in seen_ids:
                seen_ids.add(j["job_id"])
                all_jobs.append(j)
    
    with_link = sum(1 for j in all_jobs if j.get("apply_link"))
    print(f"\n📊 총 수집: {len(all_jobs)}건")
    print(f"🔗 지원링크 확보: {with_link}건 / {len(all_jobs)}건 ({with_link*100//max(len(all_jobs),1)}%)")
    
    return all_jobs


if __name__ == "__main__":
    jobs = get_all_jobs(max_pages=1)
    print("\n" + "=" * 60)
    print("샘플 5건 (지원링크 위주):")
    print("=" * 60)
    for j in jobs[:5]:
        print(f"\n📌 [{j['category']}] {j['position']}")
        print(f"   회사: {j['company']}")
        print(f"   경력: {j['career']} | 마감: {j['deadline']}")
        print(f"   🔗 링크: {j['apply_link'] if j['apply_link'] else '(없음)'}")
