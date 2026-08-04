"""
제목 인코딩 진단용 테스트 스크립트
- 같은 한글 텍스트를 4가지 다른 방식으로 인코딩해서 테스트 게시글 4개를 올립니다.
- 실행 후 카페에서 어떤 제목이 정상적으로 한글로 보이는지 확인해서 알려주세요.
- 확인 후에는 이 테스트 게시글 4개는 삭제하셔도 됩니다.
"""
 
import os
import requests
from urllib.parse import quote
 
CAFE_ID = "31767633"
MENU_ID = "10"
 
 
def get_access_token():
    CLIENT_ID = os.environ["NAVER_CLIENT_ID"]
    CLIENT_SECRET = os.environ["NAVER_CLIENT_SECRET"]
    REFRESH_TOKEN = os.environ["NAVER_REFRESH_TOKEN"]
 
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
        raise RuntimeError("토큰 재발급 실패: " + str(data))
    return data["access_token"]
 
 
def to_html_entity(text):
    result = ""
    for ch in text:
        if ord(ch) < 128:
            result += ch
        else:
            result += "&#" + str(ord(ch)) + ";"
    return result
 
 
def post_test(access_token, label, subject_encoded_str, body_note):
    """subject_encoded_str: 이미 percent-encoding까지 끝난 ASCII 문자열"""
    content_text = "[인코딩 테스트] " + label + "\n\n" + body_note + "\n\n확인 후 삭제해주세요."
    content_encoded = quote(to_html_entity(content_text).encode("utf-8"), safe="")
 
    url = "https://openapi.naver.com/v1/cafe/" + CAFE_ID + "/menu/" + MENU_ID + "/articles"
    headers = {
        "Authorization": "Bearer " + access_token,
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
    }
    body = "subject=" + subject_encoded_str + "&content=" + content_encoded + "&openyn=false"
 
    res = requests.post(url, headers=headers, data=body.encode("utf-8"), timeout=15)
    print(f"  [{label}] 상태코드:", res.status_code)
    try:
        result = res.json()
        status = result.get("message", {}).get("status")
        if status == "200":
            print(f"  [{label}] ✅ 성공:", result["message"]["result"]["articleUrl"])
        else:
            print(f"  [{label}] ❌ 실패:", res.text[:200])
    except Exception:
        print(f"  [{label}] ❌ 응답 파싱 실패:", res.text[:200])
 
 
def main():
    token = get_access_token()
    print("✅ Access Token 발급")
 
    test_text = "테스트제목 한글확인 니프코코리아 안전보건관리"
 
    # A) UTF-8 그대로 percent-encoding
    subject_a = quote(test_text.encode("utf-8"), safe="")
    post_test(token, "A_UTF8", subject_a, "subject를 UTF-8 bytes로 percent-encoding")
 
    # B) CP949(EUC-KR 확장)로 인코딩 후 percent-encoding
    subject_b = quote(test_text.encode("cp949", errors="replace"), safe="")
    post_test(token, "B_CP949", subject_b, "subject를 CP949 bytes로 percent-encoding")
 
    # C) 본문과 동일하게 HTML 숫자 엔티티로 변환 후 UTF-8 percent-encoding
    subject_c = quote(to_html_entity(test_text).encode("utf-8"), safe="")
    post_test(token, "C_HTML엔티티", subject_c, "subject를 본문과 동일하게 HTML 엔티티 변환")
 
    # D) UTF-8 percent-encoding을 한번 더 percent-encoding (이중 인코딩)
    once = quote(test_text.encode("utf-8"), safe="")
    subject_d = quote(once, safe="")
    post_test(token, "D_이중인코딩", subject_d, "subject를 UTF-8 percent-encoding 후 한번 더 percent-encoding")
 
    print("\n📌 카페에서 A/B/C/D 중 어떤 제목이 정상적으로 한글로 보이는지 확인해주세요.")
 
 
if __name__ == "__main__":
    main()
