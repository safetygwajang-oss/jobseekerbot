import json
import os
from datetime import datetime, timezone, timedelta
from crawler import get_all_jobs
from cafe_poster import get_access_token, post_to_cafe

KST = timezone(timedelta(hours=9))
STATE_FILE = "posted_jobs.json"


def load_posted():
    """이미 게시한 공고 ID 목록"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"posted_ids": [], "last_run": None}


def save_posted(state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def main():
    print(f"🚀 시작: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. 기존 게시 이력 로드
    state = load_posted()
    posted_ids = set(state["posted_ids"])
    print(f"📚 기존 게시 이력: {len(posted_ids)}건")
    
    # 2. iSafety 크롤링
    jobs = get_all_jobs(max_pages=2)  # 최근 2페이지만
    
    # 3. 신규 공고만 필터링
    new_jobs = [j for j in jobs if j['job_id'] not in posted_ids]
    print(f"🆕 신규 공고: {len(new_jobs)}건")
    
    if not new_jobs:
        print("📭 새로운 공고가 없습니다.")
        return
    
    # 4. 네이버 카페 게시
    token = get_access_token()
    print(f"✅ Access Token 발급 완료")
    
    success_count = 0
    for i, job in enumerate(new_jobs[:10], 1):  # 한 번에 최대 10개
        print(f"\n[{i}/{min(len(new_jobs), 10)}] {job['raw_title']}")
        try:
            article_url = post_to_cafe(job, token)
            if article_url:
                posted_ids.add(job['job_id'])
                success_count += 1
        except Exception as e:
            print(f"  ❌ 오류: {e}")
    
    # 5. 상태 저장
    state["posted_ids"] = list(posted_ids)
    state["last_run"] = datetime.now(KST).isoformat()
    save_posted(state)
    
    print(f"\n🎉 완료: {success_count}건 게시 성공")


if __name__ == "__main__":
    main()
