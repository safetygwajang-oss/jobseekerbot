import os
import requests
from datetime import datetime, timezone, timedelta

CLIENT_ID = os.environ["NAVER_CLIENT_ID"]
CLIENT_SECRET = os.environ["NAVER_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["NAVER_REFRESH_TOKEN"]

CAFE_ID = "31767633"
MENU_ID = "10"

KST = timezone(timedelta(hours=9))

def get_access_token():
    res = requests.get(
        "https://nid.naver.com/oauth2.0/token",
        params={
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": REFRESH_TOKEN,
        },
        timeout=10
    )
    data = res.json()
    if "access_token" not in data:
        raise RuntimeError(f"토큰 재발급 실패: {data}")
    print(f"✅ Access Token 발급 완료")
    return data["access_token"]

def post_article(access_token, subject, content):
    url = f"https://openapi.naver.com/v1/cafe/{CAFE_ID}/menu/{MENU_ID}/articles"
    
    # ⭐ 핵심: dict를 직접 넘기고, requests가 자동 처리하도록 함
    # 단, Session을 사용해서 인코딩을 명시적으로 제어
    
    session = requests.Session()
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept-Charset": "UTF-8",
        "Accept": "application/json",
    }
    
    # ⭐ 방법 1: files 파라미터로 multipart/form-data 전송 시도
    # 네이버 카페 API가 multipart도 지원하는지 확인
    
    # 우선 params 방식으로 시도 (URL 쿼리스트링 방식)
    res = session.post(
        url,
        headers=headers,
        params={  # ⭐ data가 아닌 params로!
            "subject": subject,
            "content": content,
            "openyn": "true",
        },
        timeout=15
    )
    
    print(f"📨 요청 URL: {res.request.url[:200]}")
    print(f"📨 응답 상태: {res.status_code}")
    print(f"📨 응답 본문: {res.text}")
    
    result = res.json()
    
    status = result.get("message", {}).get("status")
    if status != "200":
        raise RuntimeError(f"게시글 등록 실패: {result}")
    
    article_url = result["message"]["result"]["articleUrl"]
    print(f"✅ 게시글 등록 성공!")
    print(f"🔗 URL: {article_url}")
    return article_url

if __name__ == "__main__":
    today = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    
    subject = f"[테스트] {today} 한글"
    content = f"""<p>안녕하세요</p>
<p>일시: {today}</p>
<p>한글 인코딩 테스트입니다.</p>
<ul>
<li>테스트 1</li>
<li>테스트 2</li>
</ul>"""
    
    print(f"📝 제목: {subject}")
    
    token = get_access_token()
    post_article(token, subject, content)
