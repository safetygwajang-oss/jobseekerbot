import os
import requests


def to_html_entity(text):
    """한글을 HTML 엔티티로 변환 (본문 정상 표시)"""
    return "".join(
        ch if ord(ch) < 128 else f"&#{ord(ch)};" 
        for ch in text
    )


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
        raise RuntimeError(f"토큰 재발급 실패: {data}")
    return data["access_token"]


def build_post_content(job):
    """채용공고 → 카페 게시글 HTML"""
    html = f"""<div style="font-family: 'Malgun Gothic', sans-serif; line-height: 1.8;">

<h3>📢 [{job['category']}] {job['raw_title']}</h3>

<table border="1" cellpadding="8" style="border-collapse: collapse; width: 100%; margin: 15px 0;">
<tr style="background-color: #f0f0f0;">
  <th style="width: 25%;">항목</th>
  <th>내용</th>
</tr>
<tr>
  <td><strong>🏢 기업명</strong></td>
  <td>{job['company']}</td>
</tr>
<tr>
  <td><strong>💼 모집분야</strong></td>
  <td>{job['position']}</td>
</tr>
<tr>
  <td><strong>📋 담당업무</strong></td>
  <td>{job['duty']}</td>
</tr>
<tr>
  <td><strong>⏰ 마감일</strong></td>
  <td style="color: #d9534f;"><strong>{job['deadline']}</strong></td>
</tr>
</table>

<hr>

<p><strong>🔗 채용 지원:</strong> 
{'<a href="' + job['apply_link'] + '" target="_blank">지원하러 가기</a>' if job['apply_link'] else '상세 문의는 댓글 부탁드립니다.'}
</p>

<p style="color: #888; font-size: 12px; margin-top: 30px;">
※ 본 채용정보는 안전과장 카페에서 자동 수집·정리하여 제공합니다.<br>
※ 지원 전 반드시 채용 조건을 재확인하시기 바랍니다.
</p>

</div>"""
    return html


def post_to_cafe(job, access_token):
    """네이버 카페에 게시"""
    CAFE_ID = "31767633"
    MENU_ID = "10"
    
    # 제목: [건설] 회사명 - 모집분야 (~마감일)
    company_short = job['company'][:15] if job['company'] != '비공개' else ''
    position_short = job['position'][:20]
    subject = f"[{job['category']}] {company_short} {position_short} (~{job['deadline'][:10]})"
    subject = re.sub(r'\s+', ' ', subject).strip()
    
    content = build_post_content(job)
    encoded_content = to_html_entity(content)
    
    url = f"https://openapi.naver.com/v1/cafe/{CAFE_ID}/menu/{MENU_ID}/articles"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
    }
    
    res = requests.post(
        url,
        headers=headers,
        data={
            "subject": subject,      # 제목은 한글 일부 포함 (테스트 필요)
            "content": encoded_content,
            "openyn": "true",
        },
        timeout=15
    )
    
    result = res.json()
    status = result.get("message", {}).get("status")
    if status != "200":
        print(f"❌ 게시 실패: {result}")
        return None
    
    article_url = result["message"]["result"]["articleUrl"]
    print(f"  ✅ 게시 완료: {article_url}")
    return article_url


import re  # 파일 상단으로 옮겨주세요
