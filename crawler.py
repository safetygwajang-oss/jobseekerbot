import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://isafety.co.kr"
LIST_URL = "https://isafety.co.kr/is/job"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

CATEGORIES = ["건설", "제조", "공공", "서비스", "기타"]

LABELS_COMPANY = ["기업명", "회사명", "기업 명", "회사 명"]
LABELS_POSITION = ["모집분야", "모집 분야", "모집직종", "직종"]
LABELS_DUTY = ["담당업무", "담당 업무", "주요업무", "업무내용"]
LABELS_DEADLINE = ["마감일", "마감 일", "접수마감", "마감"]


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
            job_id = extract_job_id(href)
            if not job_id:
                continue
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


def extract_job_id(href):
    """href에서 숫자 ID 추출 (정규식 없이)"""
    # wr_id= 패턴
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
        num = ""
        for ch in part:
            if ch.isdigit():
                num += ch
            else:
                break
        if num:
            return num
    return None


def fetch_job_detail(job):
    url = job["detail_url"]
    print("상세 수집:", url)

    res = requests.get(url, headers=HEADERS, timeout=15)
    res.encoding = "utf-8"
    soup = BeautifulSoup(res.text, "lxml")

    title_tag = soup.select_one("#bo_v_title, .view_title, h1, h2, title")
    if title_tag:
        full_title = title_tag.get_text(strip=True)
    else:
        full_title = job["title_preview"]

    content_area = soup.select_one("#bo_v_con, .view_content, .board-view, #bo_v_atc")
    if content_area:
        full_text = content_area.get_text("\n", strip=True)
    else:
        full_text = soup.get_text("\n", strip=True)

    # 카테고리 추출 (정규식 없이)
    category = detect_category(full_title)

    # 정보 추출 (라벨 기반)
    info = extract_job_info(full_text)

    # 제목 정리 (앞의 대괄호 태그 제거)
    clean_title = remove_bracket_prefix(full_title)

    return {
        "job_id": job["job_id"],
        "category": category,
        "company": info.get("company", "비공개"),
        "position": info.get("position", clean_title[:50]),
        "duty": info.get("duty", "상세내용 참조"),
        "deadline": info.get("deadline", "채용시 마감"),
        "apply_link": info.get("link", ""),
        "raw_title": clean_title[:80],
    }


def detect_category(title):
    """제목에서 카테고리 추출"""
    for cat in CATEGORIES:
        if cat in title:
            if cat == "서비스":
                return "기타"
            return cat
    return "기타"


def remove_bracket_prefix(title):
    """제목 앞의 [xxx] 제거"""
    t = title.strip()
    while t.startswith("["):
        idx = t.find("]")
        if idx == -1:
            break
        t = t[idx + 1:].strip()
    return t


def find_value_by_labels(text, labels):
    """라벨 뒤의 값 추출"""
    lines = text.split("\n")
    for line in lines:
        for label in labels:
            if label in line:
                # 라벨 뒤의 : 또는 ： 이후 텍스트 추출
                for sep in [":", "："]:
                    if sep in line:
                        parts = line.split(sep, 1)
                        if len(parts) == 2:
                            value = parts[1].strip()
                            if value:
                                return value[:200]
    return None


def find_http_link(text):
    """본문에서 http 링크 추출"""
    for word in text.split():
        if word.startswith("http://") or word.startswith("https://"):
            return word[:200]
    return None


def extract_job_info(text):
    info = {}
    v = find_value_by_labels(text, LABELS_COMPANY)
    if v:
        info["company"] = v
    v = find_value_by_labels(text, LABELS_POSITION)
    if v:
        info["position"] = v
    v = find_value_by_labels(text, LABELS_DUTY)
    if v:
        info["duty"] = v
    v = find_value_by_labels(text, LABELS_DEADLINE)
    if v:
        info["deadline"] = v
    v = find_http_link(text)
    if v:
        info["link"] = v
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
