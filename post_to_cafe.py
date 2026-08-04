import os
import requests
from datetime import datetime

# GitHub Secrets에서 자동으로 가져옴
CLIENT_ID = os.environ["NAVER_CLIENT_ID"]
CLIENT_SECRET = os.environ["NAVER_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["NAVER_REFRESH_TOKEN"]

CAFE_ID = "31767633"
MENU_ID = "10"

# 1. Access Token 재발급
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

# 2. 카페 게시글 작성
def post_article(access_token, subject, content):
    res = requests.post(
        f"https://openapi.naver.com/v1/cafe/{CAFE_ID}/menu/{MENU_ID}/articles",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        },
        data={
            "subject": subject,
            "content": content,
            "openyn": "true",
        },
        timeout=15
    )
    result = res.json()
    print(f"📨 응답: {result}")
    
    status = result.get("message", {}).get("status")
    if status != "200":
        raise RuntimeError(f"게시글 등록 실패: {result}")
    
    article_url = result["message"]["result"]["articleUrl"]
    print(f"✅ 게시글 등록 성공!")
    print(f"🔗 URL: {article_url}")
    return article_url

# 실행
if __name__ == "__main__":
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    subject = f"[자동] {today} 안전 브리핑"
    content = f"""
    <p>안녕하세요, 안전과장입니다.</p>
    <p><b>일시:</b> {today}</p>
    <p>GitHub Actions로 자동 게시된 한글 테스트 글입니다. 🎉</p>
    <ul>
      <li>안전수칙 1</li>
      <li>안전수칙 2</li>
    </ul>
    """
    
    token = get_access_token()
    post_article(token, subject, content)
