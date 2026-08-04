import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://isafety.co.kr"
LIST_URL = "https://isafety.co.kr/is/job"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def parse_first_cell(text):
    """
    '안전(CM) 건설 · 26-08-01 · 139' 형태를 분해
    반환: (모집분야, 분류, 등록일, 조회수)
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


def fetch_detail(detail_url):
    """상세 페이지에서 본문 + 외부 링크(사람인 등) 추출"""
    try:
        res = requests.get(detail_url, headers=HEADERS, timeout=15)
        res.encoding = "utf-8"
        soup = BeautifulSoup(res.text, "lxml")
        
        # 본문 영역 찾기: '자격요건' 또는 '주요업무' 키워드 포함하는 영역
        body_text = ""
        apply_link = ""
        
        # 페이지 전체 텍스트에서 본문 추정
        # 상세 페이지는 보통 큰 div/td 안에 긴 텍스트가 있음
        candidates = soup.find_all(["div", "td", "section", "article"])
        best = ""
        for c in candidates:
            txt = c.get_text("\n", strip=True)
            # 자격요건/주요업무/우대사항 등이 포함되고, 길이가 적당한 것
            if any(kw in txt for kw in ["자격요건", "주요업무", "우대사항", "담당업무"]):
                if 50 < len(txt) < 3000 and len(txt) > len(best):
                    best = txt
        body_text = best
        
        # 외부 지원 링크 추출 (사람인, 잡코리아, 인크루트 등)
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if any(site in href.lower() for site in ["saramin.co.kr", "jobkorea.co.kr", "incruit.com", "wanted.co.kr", "jumpit.co.kr"]):
                apply_link = href
                break
        
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
    
    # 채용공고 테이블 찾기 (헤더로 판별)
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
            "duty": "",           # 상세페이지에서 채움
            "apply_link": "",     # 상세페이지에서 채움
        })
    
    print(f"  ✅ 리스트 파싱: {len(jobs)}건")
    
    # 상세 페이지 방문해서 duty, apply_link 채우기
    if with_detail:
        for j in jobs:
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
    
    print(f"\n📊 총 수집: {len(all_jobs)}건")
    return all_jobs


# 테스트 실행용
if __name__ == "__main__":
    jobs = get_all_jobs(max_pages=1)
    print("\n" + "=" * 60)
    print("샘플 3건:")
    print("=" * 60)
    for j in jobs[:3]:
        print(f"\n📌 [{j['category']}] {j['position']}")
        print(f"   회사: {j['company']}")
        print(f"   경력: {j['career']} | 근무지: {j['location']} | 마감: {j['deadline']}")
        print(f"   지원링크: {j['apply_link'][:80] if j['apply_link'] else '(없음)'}")
        print(f"   담당업무: {j['duty'][:100] if j['duty'] else '(없음)'}...")
