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


def to_html_entity(text):
    """한글 등 ASCII 이외 문자를 HTML 숫자 엔티티로 변환"""
    result = []
    for ch in text:
        code = ord(ch)
        if code < 128:  # ASCII는 그대로
            result.append(ch)
        else:
            result.append(f"&#{code};")
    return "".join(result)


def post_article(access_token, subject, content):
    url = f"https://openapi.naver.com/v1/cafe/{CAFE_ID}/menu/{MENU_ID}/articles"
    
    # ⭐ 한글을 HTML 엔티티로 변환 (서버는 ASCII로 인식 → 인코딩 문제 없음)
    encoded_subject = to_html_entity(subject)
    encoded_content = to_html_entity(content)
    
    print(f"🔍 변환된 제목(앞 100자): {encoded_subject[:100]}")
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
    }
    
    res = requests.post(
        url,
        headers=headers,
        data={
            "subject": encoded_subject,
            "content": encoded_content,
            "openyn": "true",
        },
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
<p>GitHub Actions로 자동 게시된 한글 테스트입니다.</p>
<ul>
<li>안전수칙 1: 보호구 착용</li>
<li>안전수칙 2: 작업 전 점검</li>
</ul>"""
    
    print(f"📝 제목: {subject}")
    token = get_access_token()
    post_article(token, subject, content)
