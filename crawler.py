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
        # 앞부분: "안전(CM) 건설" → 모집분야 + 분류(마지막 단어)
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
        part = href.split("wr_id=")[1]
        num = ""
        for ch in part:
            if ch.isdigit():
                num += ch
            else:
                break
        if num:
            return num
    # /is/job/숫자 패턴
    if "/is/job/" in href:
        part = href.split("/is/job/")[1]
        # p1 같은 페이지 URL 제외
        if part.startswith("p"):
            return None
        num = ""
        for ch in part:
            if ch.isdigit():
                num += ch
            else:
                break
        if num:
            return num
    return None


def get_jobs_from_page(page=1):
    """리스트 페이지에서 채용공고 파싱"""
    url = f"{LIST_URL}/p{page}" if page > 1 else LIST_URL
    print(f"📄 페이지 접근: {url}")
    
    res = requests.get(url, headers=HEADERS, timeout=15)
    res.encoding = "utf-8"
    soup = BeautifulSoup(res.text, "lxml")
    
    # 모든 테이블 중 채용공고 리스트 찾기 (헤더로 판별)
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
            continue  # 헤더 행 등 스킵
        
        # 첫 번째 셀에 링크가 있음
        first_cell = tds[0]
        link = first_cell.find("a", href=True)
        if not link:
            continue
        
        href = link["href"]
        job_id = extract_job_id(href)
        if not job_id:
            continue
        
        detail_url = urljoin(BASE_URL, href)
        
        # 5개 셀 텍스트 추출
        first_text = tds[0].get_text(" ", strip=True)
        company = tds[1].get_text(" ", strip=True)
        career = tds[2].get_text(" ", strip=True).rstrip(".")  # '경력.' → '경력'
        location = tds[3].get_text(" ", strip=True)
        deadline = tds[4].get_text(" ", strip=True)
        
        # 첫 셀 분해
        position, category, reg_date, views = parse_first_cell(first_text)
        
        # raw_title 만들기 (main.py에서 사용됨)
        raw_title = f"[{category}] {position}" if category else position
        
        jobs.append({
            "job_id": job_id,
            "detail_url": detail_url,
            "raw_title": raw_title,
            "position": position,      # 모집분야
            "category": category,       # 분류 (건설/제조 등)
            "company": company,         # 회사명
            "career": career,           # 경력
            "location": location,       # 근무지
            "deadline": deadline,       # 마감일
            "reg_date": reg_date,       # 등록일
            "views": views,             # 조회수
        })
    
    print(f"  ✅ {len(jobs)}건 파싱")
    return jobs


def get_all_jobs(max_pages=2):
    """여러 페이지에서 공고 수집"""
    all_jobs = []
    seen_ids = set()
    
    for page in range(1, max_pages + 1):
        jobs = get_jobs_from_page(page)
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
        print(f"   경력: {j['career']}")
        print(f"   근무지: {j['location']}")
        print(f"   마감일: {j['deadline']}")
        print(f"   상세: {j['detail_url']}")
