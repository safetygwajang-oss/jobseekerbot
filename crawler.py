import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

BASE_URL = "https://isafety.co.kr"
LIST_URL = "https://isafety.co.kr/is/job"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# 카테고리 매핑 (iSafety 표기 → 우리 태그)
CATEGORY_MAP = {
    "건설": "건설",
    "제조": "제조",
    "공공": "공공",
    "기타": "기타",
    "서비스": "기타",
}


def fetch_job_list(max_pages=2):
    """구인정보 리스트 페이지에서 채용공고 목록 추출"""
    jobs = []
    
    for page in range(1, max_pages + 1):
        url = f"{LIST_URL}?page={page}"
        print(f"📥 리스트 페이지 수집: {url}")
        
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'lxml')
        
        # ⚠️ 실제 HTML 구조에 맞게 셀렉터 조정 필요
        # iSafety는 테이블 기반 리스트일 가능성 높음
        rows = soup.select("table tr")  # 실제 확인 후 조정
        
        for row in rows:
            link_tag = row.find('a', href=re.compile(r'/is/job/\d+|wr_id='))
            if not link_tag:
                continue
            
            detail_url = urljoin(BASE_URL, link_tag['href'])
            
            # 게시글 고유 ID 추출 (중복 방지용)
            job_id_match = re.search(r'(?:wr_id=|/)(\d+)', detail_url)
            if not job_id_match:
                continue
            job_id = job_id_match.group(1)
            
            jobs.append({
                'job_id': job_id,
                'detail_url': detail_url,
                'title_preview': link_tag.get_text(strip=True)
            })
    
    print(f"✅ 총 {len(jobs)}개 공고 발견")
    return jobs


def fetch_job_detail(job):
    """공고 상세 페이지에서 세부 정보 추출"""
    url = job['detail_url']
    print(f"  🔍 상세 수집: {url}")
    
    res = requests.get(url, headers=HEADERS, timeout=15)
    res.encoding = 'utf-8'
    soup = BeautifulSoup(res.text, 'lxml')
    
    # ⚠️ 실제 HTML 구조 확인 후 셀렉터 정확히 지정 필요
    # 일반적인 패턴으로 시도
    content_area = soup.select_one('#bo_v_con, .view_content, .board-view')
    full_text = content_area.get_text('\n', strip=True) if content_area else ""
    
    title_tag = soup.select_one('#bo_v_title, .view_title, h1, h2')
    full_title = title_tag.get_text(strip=True) if title_tag else job['title_preview']
    
    # 카테고리 추출 (제목이나 본문에서 [건설] [제조] 패턴 찾기)
    category = "기타"
    cat_match = re.search(r'
\[(건설|제조|공공|서비스|기타)\]
', full_title)
    if cat_match:
        category = CATEGORY_MAP.get(cat_match.group(1), "기타")
    
    # 정보 추출 (라벨 기반 파싱)
    info = extract_job_info(full_text)
    
    # 제목 정리 ([건설] 등 태그 제거)
    clean_title = re.sub(r'^\s*
\[[^\]
]+\]
\s*', '', full_title).strip()
    
    return {
        'job_id': job['job_id'],
        'category': category,
        'company': info.get('기업명', '비공개'),
        'position': info.get('모집분야', clean_title),
        'duty': info.get('담당업무', '상세내용 참조'),
        'deadline': info.get('마감일', '채용시 마감'),
        'apply_link': info.get('채용링크', ''),
        'raw_title': clean_title,
        'full_text': full_text[:500],  # 백업용
    }


def extract_job_info(text):
    """본문 텍스트에서 라벨 기반으로 정보 추출"""
    info = {}
    
    patterns = {
        '기업명': r'(?:기업\s*명|회사\s*명|기업)\s*[:：]\s*([^\n]+)',
        '모집분야': r'(?:모집\s*분야|모집\s*직종|직종)\s*[:：]\s*([^\n]+)',
        '담당업무': r'(?:담당\s*업무|주요\s*업무|업무\s*내용)\s*[:：]\s*([^\n]+(?:\n(?!\S+\s*[:：])[^\n]+)*)',
        '마감일': r'(?:마감\s*일|접수\s*마감|마감)\s*[:：]\s*([^\n]+)',
        '채용링크': r'(?:채용\s*링크|지원\s*링크|URL|링크)\s*[:：]\s*(https?://[^\s]+)',
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            info[key] = match.group(1).strip()[:200]  # 길이 제한
    
    return info


def get_all_jobs(max_pages=2):
    """전체 프로세스: 리스트 → 상세 정보"""
    job_list = fetch_job_list(max_pages)
    detailed_jobs = []
    
    for job in job_list:
        try:
            detail = fetch_job_detail(job)
            detailed_jobs.append(detail)
        except Exception as e:
            print(f"  ⚠️ 상세 파싱 실패: {e}")
            continue
    
    return detailed_jobs


if __name__ == "__main__":
    # 테스트
    jobs = get_all_jobs(max_pages=1)
    for job in jobs[:3]:
        print(job)
        print("---")
