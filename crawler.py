import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://isafety.co.kr"
LIST_URL = "https://isafety.co.kr/is/job"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def fetch_job_list(max_pages=2):
    jobs = []
    seen_ids = set()

    for page in range(1, max_pages + 1):
        url = LIST_URL + "?page=" + str(page)
        print("리스트 수집:", url)

        try:
            res = requests.get(url, headers=HEADERS, timeout=15)
            res.encoding = "utf-8"
        except Exception as e:
            print("요청 실패:", e)
            continue

        soup = BeautifulSoup(res.text, "lxml")
        links = soup.find_all("a", href=True)

        for link in links:
            href = link["href"]
            match = re.search(r"wr_id=(\d+)", href)
            if not match:
                match = re.search(r"/is/job/(\d+)", href)
            if not match:
                continue

            job_id = match.group(1)
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            detail_url = urljoin(BASE_URL, href)
            jobs.append({
                "job_id": job_id,
                "detail_url": detail_url,
                "title_preview": link.get_text(strip=True)[:100]
            })

    print("총", len(jobs), "개 링크 발견")
    return jobs


def fetch_job_detail(job):
    url = job["detail_url"]
    print("상세 수집:", url)

    res = requests.get(url, headers=HEADERS, timeout=15)
    res.encoding = "utf-8"
    soup = BeautifulSoup(res.text, "lxml")

    title_tag = soup.select_one("#bo_v_title, .view_title, h1, h2, title")
    full_title = title_tag.get_text(strip=True) if title_tag else job["title_preview"]

    content_area = soup.select_one("#bo_v_con, .view_content, .board-view, #bo_v_atc")
    if content_area:
        full_text = content_area.get_text("\n", strip=True)
    else:
        full_text = soup.get_text("\n", strip=True)

    category = "기타"
    cat_pattern = r"
\[(건설|제조|공공|서비스|기타)\]
"
    cat_match = re.search(cat_pattern, full_title)
    if cat_match:
        found = cat_match.group(1)
        if found == "서비스":
            category = "기타"
        else:
            category = found

    info = extract_job_info(full_text)
    clean_title = re.sub(r"^\s*
\[[^\]
]+\]
\s*", "", full_title).strip()

    return {
        "job_id": job["job_id"],
        "category": category,
        "company": info.get("기업명", "비공개"),
        "position": info.get("모집분야", clean_title[:50]),
        "duty": info.get("담당업무", "상세내용 참조"),
        "deadline": info.get("마감일", "채용시 마감"),
        "apply_link": info.get("채용링크", ""),
        "raw_title": clean_title[:80],
    }


def extract_job_info(text):
    info = {}

    m = re.search(r"(?:기업\s*명|회사\s*명)\s*[:：]\s*([^\n]+)", text)
    if m:
        info["기업명"] = m.group(1).strip()[:200]

    m = re.search(r"(?:모집\s*분야|모집\s*직종|직종)\s*[:：]\s*([^\n]+)", text)
    if m:
        info["모집분야"] = m.group(1).strip()[:200]

    m = re.search(r"(?:담당\s*업무|주요\s*업무|업무\s*내용)\s*[:：]\s*([^\n]+)", text)
    if m:
        info["담당업무"] = m.group(1).strip()[:200]

    m = re.search(r"(?:마감\s*일|접수\s*마감|마감)\s*[:：]\s*([^\n]+)", text)
    if m:
        info["마감일"] = m.group(1).strip()[:200]

    m = re.search(r"(https?://[^\s]+)", text)
    if m:
        info["채용링크"] = m.group(1).strip()[:200]

    return info


def get_all_jobs(max_pages=2):
    job_list = fetch_job_list(max_pages)
    detailed = []

    for job in job_list:
        try:
            detail = fetch_job_detail(job)
            detailed.append(detail)
        except Exception as e:
            print("파싱 실패:", e)
            continue

    return detailed


if __name__ == "__main__":
    jobs = get_all_jobs(max_pages=1)
    print("총", len(jobs), "건")
    for j in jobs[:3]:
        print(j)
        print("---")
