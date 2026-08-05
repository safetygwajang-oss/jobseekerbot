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
RETRY_DELAY = 10  # 초

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
    
    # 모든 재시도 실패
    print(f"    ❌ 최종 실패: {url}")
    raise last_error


def parse_first_cell(text):
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
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if is_valid_external_link(href):
            return href
    for iframe in soup.find_all("iframe", src=True):
        src = iframe["src"].strip()
        if is_valid_external_link(src):
            return src
    for tag in soup.find_all(attrs={"onclick": True}):
        onclick = tag["onclick"]
        for url in URL_PATTERN.findall(onclick):
            cleaned = url.rstrip("'\";,)>]}")
            if is_valid_external_link(cleaned):
                return cleaned
    for url in URL_PATTERN.findall(raw_html):
        cleaned = url.rstrip("'\";,)>]}")
        if is_valid_external_link(cleaned):
            return cleaned
    return ""


def fetch_detail(detail_url):
    """상세 페이지 - 실패해도 빈 값 반환 (전체 중단 방지)"""
    try:
        res = safe_get(detail_url, timeout=15)
        raw_html = res.text
        soup = BeautifulSoup(raw_html, "lxml")
        
        body_text = ""
        best = ""
        for c in soup.find_all(["div", "td", "section", "article"]):
            txt = c.get_text("\n", strip=True)
            if any(kw in txt for kw in ["자격요건", "주요업무", "우대사항", "담당업무"]):
                if 50 < len(txt) < 3000 and len(txt) > len(best):
                    best = txt
        body_text = best
        
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


def get_jobs_from_page(page=1, with_detail=True):
    """리스트 페이지 - 실패 시 빈 리스트 반환"""
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
        print(f"   🔗 링크: {j['apply_link'] if j['apply_link'] else '(없음)'}")
