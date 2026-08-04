import os
import requests
import urllib.parse
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
    print("✅ Access Token 발급 완료")
    return data["access_token"]

def post_article(access_token, subject, content):
    url = f"https://openapi.naver.com/v1/cafe/{CAFE_ID}/menu/{MENU_ID}/articles"
    
    # ⭐ 핵심 해결책: 데이터를 CP949(옛날 한국어 표준)로 강제 변환!
    # 이렇게 하면 네이버 뒷단 서버가 찰떡같이 알아듣습니다.
    payload = urllib.parse.urlencode({
        'subject': subject,
        'content': content,
        'openyn': 'true'
    }, encoding='cp949')
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        # ⭐ 문지기(API 게이트웨이)를 통과하기 위해 겉포장만 utf-8로 위장
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8"
    }
    
    res = requests.post(
        url,
        headers=headers,
        data=payload,
        timeout=15
    )
    
    print(f"📨 응답: {res.text[:300]}")
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
    
    subject = f"[자동] {today} 안전 브리핑"
    content = f"""<p>안녕하세요, 안전과장입니다.</p>
<p>일시: {today}</p>
<p>GitHub Actions로 자동 게시된 완벽한 한글 테스트입니다.</p>
<ul>
<li>안전수칙 1: 보호구 착용</li>
<li>안전수칙 2: 작업 전 점검</li>
</ul>"""
    
    token = get_access_token()
    post_article(token, subject, content)
