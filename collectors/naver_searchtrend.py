"""NAVER API HUB 검색어 트렌드 → Google Sheets 적재.

데이터랩 검색어 트렌드(일 단위, 최근 2년 롤링)를 매일 스냅샷으로 덮어쓴다.
ratio는 요청 내 상대값(최대=100)이므로 반드시 같은 요청 구성의 스냅샷 안에서만 비교할 것.

env: NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, PLAUD_SHEET_ID, GOOGLE_SERVICE_ACCOUNT_JSON
"""
import json
import os
from datetime import date, timedelta

import pandas as pd
import requests

from collectors import config, sheets_io

API_URL = "https://naverapihub.apigw.ntruss.com/search-trend/v1/search"
TAB = "naver_검색트렌드"
COLUMNS = ["date", "group", "ratio"]

# 키워드 그룹 (그룹 최대 5개 · 그룹당 키워드 최대 20개)
KEYWORD_GROUPS = [
    {"groupName": "플라우드", "keywords": [
        "플라우드노트프로", "노트프로", "플라우드프로", "plaudnotepro", "notepro",
        "plaudpro", "플라우드노트pro", "plaudnote프로", "플라우드노트핀", "플라우드",
        "plaud", "pladunotepin", "notepin", "플라우드노트", "plaudnote"]},
    {"groupName": "AI녹음기", "keywords": ["AI녹음기", "AI 녹음기", "인공지능 녹음기"]},
    {"groupName": "클로바노트", "keywords": ["클로바노트", "클로바 노트", "clovanote"]},
]


def fetch(since: str, until: str) -> list[dict]:
    cid = os.environ.get("NAVER_CLIENT_ID", "")
    sec = os.environ.get("NAVER_CLIENT_SECRET", "")
    if not (cid and sec):
        raise RuntimeError("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수 없음.")
    r = requests.post(API_URL, headers={
        "X-NCP-APIGW-API-KEY-ID": cid,
        "X-NCP-APIGW-API-KEY": sec,
        "Content-Type": "application/json",
    }, json={
        "startDate": since, "endDate": until, "timeUnit": "date",
        "keywordGroups": KEYWORD_GROUPS,
    }, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"NAVER API {r.status_code}: {r.text[:500]}")
    return r.json().get("results", [])


def run() -> int:
    until = (date.today() - timedelta(days=1)).isoformat()   # 어제까지 (당일은 미집계)
    since = (date.today() - timedelta(days=730)).isoformat() # 2년 롤링
    print(f"[naver] 검색어 트렌드 수집: {since} ~ {until} (그룹 {len(KEYWORD_GROUPS)}개)")
    rows = []
    for res in fetch(since, until):
        g = res.get("title", "")
        for d in res.get("data", []):
            rows.append({"date": d.get("period"), "group": g, "ratio": d.get("ratio")})
    df = pd.DataFrame(rows, columns=COLUMNS)
    print(f"[naver] {len(df)}행")
    n = sheets_io.write_tab(df, TAB, COLUMNS)
    print(f"[naver] 시트 '{TAB}' {n}행 기록 (스냅샷 덮어쓰기)")
    return len(df)


if __name__ == "__main__":
    run()
