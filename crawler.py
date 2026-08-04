import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://isafety.co.kr"
LIST_URL = "https://isafety.co.kr/is/job"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def debug_detail_page():
    """상세 페이지 1건 진단"""
    # 1. 리스트에서 첫 번째 링크 가져오기
    print("=" * 60)
    print("🔍 리스트 페이지 접근")
    print("=" * 60)
    
    res = requests.get(LIST_URL, headers=HEADERS, timeout=15)
    res.encoding = "utf-8"
    soup = BeautifulSoup(res.text, "lxml")
    
    detail_url = None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/is/job/" in href and any(c.isdigit() for c in href.split("/is/job/")[-1][:8]):
            detail_url = urljoin(BASE_URL, href)
            break
    
    if not detail_url:
        print("❌ 상세 링크 못 찾음")
        return
    
    print("상세 URL:", detail_url)
    
    # 2. 상세 페이지 가져오기
    print("\n" + "=" * 60)
    print("🔍 상세 페이지 진단")
    print("=" * 60)
    
    res = requests.get(detail_url, headers=HEADERS, timeout=15)
    res.encoding = "utf-8"
    soup = BeautifulSoup(res.text, "lxml")
    
    # [A] 제목 후보
    print("\n[A] 제목 후보:")
    for sel in ["h1", "h2", "h3", ".title", ".view_title", "#bo_v_title"]:
        tags = soup.select(sel)
        for t in tags[:3]:
            txt = t.get_text(" ", strip=True)[:100]
            if txt:
                print(f"  {sel}: {txt}")
    
    # [B] 테이블 확인
    print("\n[B] 테이블(<table>) 확인:")
    tables = soup.find_all("table")
    print(f"  개수: {len(tables)}")
    for i, t in enumerate(tables):
        cells = t.find_all(["td", "th"])
        texts = [c.get_text(" ", strip=True) for c in cells]
        print(f"  table[{i}] 셀 {len(cells)}개:")
        print(f"    {texts[:12]}")
    
    # [C] dl/dt/dd 구조 확인
    print("\n[C] <dl>/<dt>/<dd> 확인:")
    dls = soup.find_all("dl")
    print(f"  dl 개수: {len(dls)}")
    for dl in dls[:3]:
        dts = [d.get_text(strip=True) for d in dl.find_all("dt")]
        dds = [d.get_text(strip=True) for d in dl.find_all("dd")]
        print(f"    dt: {dts}")
        print(f"    dd: {dds}")
    
    # [D] "경력", "근무지", "마감일" 텍스트 주변 탐색
    print("\n[D] 주요 라벨 주변 요소:")
    for label in ["경력", "근무지", "마감일"]:
        # 라벨을 정확히 포함하는 요소들 찾기
        found = soup.find_all(string=lambda s: s and s.strip() == label)
        print(f"  '{label}' 정확 매칭: {len(found)}개")
        for f in found[:2]:
            parent = f.parent
            # 부모 태그 정보
            p_info = f"<{parent.name}"
            if parent.get("class"):
                p_info += f" class='{' '.join(parent.get('class'))}'"
            p_info += ">"
            print(f"    부모: {p_info}")
            # 다음 형제 요소
            next_sib = parent.find_next_sibling()
            if next_sib:
                print(f"    다음 형제: <{next_sib.name}> = '{next_sib.get_text(' ', strip=True)[:50]}'")
    
    # [E] 회사명 후보 (건물 아이콘 근처)
    print("\n[E] 회사명 후보:")
    # ico, icon, building, company 클래스 검색
    for cls_keyword in ["company", "corp", "biz", "info"]:
        elems = soup.find_all(class_=lambda c: c and cls_keyword in " ".join(c).lower())
        for e in elems[:3]:
            txt = e.get_text(" ", strip=True)[:80]
            if txt and len(txt) < 100:
                print(f"  class~{cls_keyword}: {txt}")
    
    # [F] 본문 영역
    print("\n[F] 본문 영역:")
    for sel in ["#bo_v_con", ".view_content", ".board-view", "#bo_v_atc", ".content"]:
        area = soup.select_one(sel)
        if area:
            txt = area.get_text(" ", strip=True)[:200]
            print(f"  {sel}: {txt}")
    
    # [G] 전체 HTML 중 정보박스 추정 부분
    print("\n[G] '마감일' 텍스트 주변 HTML (300자):")
    if soup.find(string=lambda s: s and "마감일" in s):
        target = soup.find(string=lambda s: s and s.strip() == "마감일")
        if target:
            # 상위 3단계까지 올라간 후 HTML 출력
            container = target.parent
            for _ in range(3):
                if container.parent:
                    container = container.parent
            print(str(container)[:800])
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    debug_detail_page()
