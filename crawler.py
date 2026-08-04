import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://isafety.co.kr"
LIST_URL = "https://isafety.co.kr/is/job"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

CATEGORY_MAP = {
    "건설": "건설",
    "제조": "제조",
    "공공": "공공",
    "기타": "기타",
    "서비스": "기타",
}


def fetch_job_list(max_pages=2):
    """구인정보 리스트 페이지에서 채용공고 링크 추출"""
    jobs = []
    seen_ids = set()

    for page in range(1, max_pages + 1):
        url = f"{LIST_URL}?page={page}"
        print(f"📥 리스트 수집: {url}")

        try:
            res = requests.get(url, headers=HEADERS, timeout=15)
            res.encoding = 'utf-8'
        except Exception as e:
            print(f"  ⚠️ 요청 실패: {e}")
            continue

        soup = BeautifulSoup(res.text, 'lxml')

        # 모든 a 태그에서 상세페이지 링크 패턴 탐색
        links = soup.find_all('a', href=True)
        for link in links:
            href = link['href']
            # wr_id= 또는 /is/job/숫자 패턴
            match = re.search(r'wr_id=(\d+)|/is/job/(\d+)', href)
            if not match:
                continue

            job_id = match.group(1) or match.group(2)
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            detail_url = urljoin(BASE_URL, href)
            jobs.append({
                'job_id': job_id,
                'detail_url': detail_url,
                'title_preview': link.get_text(strip=True)[:100]
            })

    print(f"✅ 총 {len(jobs)}개 공고 링크 발견")
    return jobs


def fetch_job_detail(job):
    """공고 상세 페이지 파싱"""
    url = job['detail_url']
    print(f"  🔍 상세 수집: {url}")

    res = requests.get(url, headers=HEADERS, timeout=15)
    res.encoding = 'utf-8'
    soup = BeautifulSoup(res.text, 'lxml')

    # 제목 추출
    title_tag = soup.select_one('#bo_v_title, .view_title, h1, h2, title')
    full_title = title_tag.get_text(strip=True) if title_tag else job['title_preview']

    # 본문 추출
    content_area = soup.select_one('#bo_v_con, .view_content, .board-view, #bo_v_atc')
    full_text = content_area.get_text('\n', strip=True) if content_area else soup.get_text('\n', strip=True)

    # 카테고리 추출
    category = "기타"
    cat_match = re.search(r'
\[(건설|제조|공공|서비스|기타)\]
', full_title)
    if cat_match:
        category = CATEGORY_MAP.get(cat_match.group(1), "기타")

    # 정보 추출
    info = extract_job_info(full_text)

    # 제목 정리
    clean_title = re.sub(r'^\s*
\[[^\]
]+\]
\s*', '', full_title).strip()

    return {
        'job_id': job['job_id'],
        'category': category,
        'company': info.get('기업명', '비공개'),
        'position': info.get('모집분야', clean_title[:50]),
        'duty': info.get('담당업무', '상세내용 참조'),
        'deadline': info.get('마감일', '채용시 마감'),
        'apply_link': info.get('채용링크', ''),
        'raw_title': clean_title[:80],
    }


def extract_job_info(text):
    """본문에서 라벨 기반으로 정보 추출"""
    info = {}

    patterns = {
        '기업명': r'(?:기업\s*명|회사\s*명|기업)\s*[:：]\s*([^\n]+)',
        '모집분야': r'(?:모집\s*분야|모집\s*직종|직종)\s*[:：]\s*([^\n]+)',
        '담당업무': r'(?:담당\s*업무|주요\s*업무|업무\s*내용)\s*[:：]\s*([^\n]+)',
        '마감일': r'(?:마감\s*일|접수\s*마감|마감)\s*[:：]\s*([^\n]+)',
        '채용링크': r'(https?://[^\s]+)',
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            info[key] = match.group(1).strip()[:200]

    return info


def get_all_jobs(max_pages=2):
    job_list = fetch_job_list(max_pages)
    detailed = []

    for job in job_list:
        try:
            detail = fetch_job_detail(job)
            detailed.append(detail)
        except Exception as e:
            print(f"  ⚠️ 파싱 실패: {e}")
            continue

    return detailed


if __name__ == "__main__":
    jobs = get_all_jobs(max_pages=1)
    print(f"\n총 {len(jobs)}건")
    for j in jobs[:3]:
        print(j)
        print("---")
