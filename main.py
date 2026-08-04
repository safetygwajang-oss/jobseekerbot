import json
import os
import time
from datetime import datetime, timezone, timedelta
from crawler import get_all_jobs
from cafe_poster import get_access_token, post_to_cafe

KST = timezone(timedelta(hours=9))
STATE_FILE = "posted_jobs.json"


def load_posted():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"posted_ids": [], "last_run": None}


def save_posted(state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def main():
    print(f"🚀 시작: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')}")

    state = load_posted()
    posted_ids = set(state["posted_ids"])
    print(f"📚 기존 게시 이력: {len(posted_ids)}건")

    jobs = get_all_jobs(max_pages=2)
    new_jobs = [j for j in jobs if j['job_id'] not in posted_ids]
    print(f"🆕 신규 공고: {len(new_jobs)}건")

    if not new_jobs:
        print("📭 새로운 공고가 없습니다.")
        return

    token = get_access_token()
    print(f"✅ Access Token 발급")

    success = 0
    total = min(len(new_jobs), 5)
    for i, job in enumerate(new_jobs[:5], 1):
        print(f"\n[{i}/{total}] {job['raw_title']}")
        try:
            url = post_to_cafe(job, token)
            if url:
                posted_ids.add(job['job_id'])
                success += 1
        except Exception as e:
            print(f"  ❌ 오류: {e}")
        
        if i < total:
            print(f"  ⏳ 60초 대기 중... (스팸 방지)")
            time.sleep(60)

    state["posted_ids"] = list(posted_ids)
    state["last_run"] = datetime.now(KST).isoformat()
    save_posted(state)

    print(f"\n🎉 완료: {success}건 성공")


if __name__ == "__main__":
    main()
