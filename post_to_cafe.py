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
    print("✅ Access Token 발급 완료")
    return data["access_token"]

def post_article(access_token, subject, content):
    url = f"https://openapi.naver.com/v1/cafe/{CAFE_ID}/menu/{MENU_ID}/articles"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        # ⚠️ 주의: Content-Type을 직접 적지 않습니다! 
        # requests 라이브러리가 files 파라미터를 보면 자동으로 완벽한 multipart 헤더를 만들어줍니다.
    }
    
    # ⭐ 30년차 비장의 무기: Multipart/form-data 강제 적용
    # (None, 데이터) 형태로 넣으면 파일이 아닌 '일반 텍스트'로 인식하면서도 인코딩은 완벽하게 보호됩니다.
    multipart_data = {
        'subject': (None, subject),
        'content': (None, content),
        'openyn': (None, 'true')
    }
    
    print(f"🔍 전송할 제목: {subject}")
    
    res = requests.post(
        url,
        headers=headers,
        files=multipart_data,  # data= 대신 files= 를 사용!
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
    
    # 이제 꼼수 없이 순수 한글을 마음껏 쓰셔도 됩니다!
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
