import os
import requests
from datetime import datetime, timezone, timedelta
from urllib.parse import quote, urlencode

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
    print(f"✅ Access Token 발급 완료\n")
    return data["access_token"]


def try_method(name, access_token, headers_extra, data):
    """다양한 방식을 시도하고 결과 로그"""
    url = f"https://openapi.naver.com/v1/cafe/{CAFE_ID}/menu/{MENU_ID}/articles"
    headers = {"Authorization": f"Bearer {access_token}"}
    headers.update(headers_extra)
    
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"🧪 방식: {name}")
    print(f"   헤더: {headers_extra}")
    if isinstance(data, bytes):
        print(f"   data(앞 80바이트): {data[:80]}")
    else:
        print(f"   data(앞 80자): {str(data)[:80]}")
    
    try:
        res = requests.post(url, headers=headers, data=data, timeout=15)
        result = res.json()
        status = result.get("message", {}).get("status")
        print(f"   응답: status={status}, 본문={res.text[:200]}")
        
        if status == "200":
            article_url = result["message"]["result"]["articleUrl"]
            print(f"   ✅ 성공! URL: {article_url}\n")
            return article_url
        else:
            print(f"   ❌ 실패\n")
            return None
    except Exception as e:
        print(f"   ⚠️ 예외: {e}\n")
        return None


if __name__ == "__main__":
    today = datetime.now(KST).strftime("%H:%M:%S")
    token = get_access_token()
    
    # 각 방식마다 제목을 다르게 해서 카페에서 구분 가능
    subject_base = f"한글테스트 {today}"
    content_base = "안녕하세요. 한글 인코딩 테스트입니다."
    
    # ═══════════════════════════════════════════
    # 방법 1: 순수 UTF-8 (requests 기본 방식)
    # ═══════════════════════════════════════════
    try_method(
        "1_기본_UTF8_dict",
        token,
        {"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"},
        {"subject": f"[방법1] {subject_base}", "content": content_base, "openyn": "true"}
    )
    
    # ═══════════════════════════════════════════
    # 방법 2: charset 없이 dict 전송
    # ═══════════════════════════════════════════
    try_method(
        "2_charset없음_dict",
        token,
        {},  # Content-Type 아예 없음 (requests 자동)
        {"subject": f"[방법2] {subject_base}", "content": content_base, "openyn": "true"}
    )
    
    # ═══════════════════════════════════════════
    # 방법 3: UTF-8 bytes로 미리 인코딩
    # ═══════════════════════════════════════════
    body3 = urlencode({
        "subject": f"[방법3] {subject_base}",
        "content": content_base,
        "openyn": "true"
    }).encode("utf-8")
    try_method(
        "3_urlencode_utf8_bytes",
        token,
        {"Content-Type": "application/x-www-form-urlencoded"},
        body3
    )
    
    # ═══════════════════════════════════════════
    # 방법 4: quote 1회 + 수동 body 조립
    # ═══════════════════════════════════════════
    s4 = quote(f"[방법4] {subject_base}", encoding='utf-8')
    c4 = quote(content_base, encoding='utf-8')
    body4 = f"subject={s4}&content={c4}&openyn=true".encode("utf-8")
    try_method(
        "4_quote1회_수동조립",
        token,
        {"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"},
        body4
    )
    
    # ═══════════════════════════════════════════
    # 방법 5: charset=ms949 명시
    # ═══════════════════════════════════════════
    try_method(
        "5_ms949_charset명시",
        token,
        {"Content-Type": "application/x-www-form-urlencoded; charset=ms949"},
        {"subject": f"[방법5] {subject_base}", "content": content_base, "openyn": "true"}
    )
    
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🏁 모든 방식 시도 완료!")
    print("👉 카페에서 어떤 방법의 글이 정상 표시되는지 확인해주세요!")
    print(f"👉 https://cafe.naver.com/safetygwajang")
