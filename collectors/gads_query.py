"""Google Ads 임의 GAQL 조회 → CSV 출력 (읽기 전용).

GitHub Actions `gads-query` workflow_dispatch 로 실행: GAQL을 입력하면
결과를 평탄화해 CSV로 로그에 출력한다. 시트·계정을 변경하지 않는다.

실행: GADS_QUERY='SELECT ...' python -m collectors.gads_query
"""
import csv
import io
import os
import sys

from collectors import gads_api


def _flatten(obj, prefix="", out=None):
    if out is None:
        out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            _flatten(v, f"{prefix}.{k}" if prefix else k, out)
    else:
        out[prefix] = obj
    return out


def main() -> None:
    query = os.environ.get("GADS_QUERY", "").strip()
    if not query:
        sys.exit("ERROR: GADS_QUERY 환경변수(GAQL) 없음")
    if not query.lower().startswith("select"):
        sys.exit("ERROR: SELECT 쿼리만 허용")
    rows = [_flatten(r) for r in gads_api.search(query)]
    print(f"[gads-query] {len(rows)}행")
    if not rows:
        return
    cols = sorted({k for r in rows for k in r})
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)
    print("===CSV_BEGIN===")
    print(buf.getvalue())
    print("===CSV_END===")


if __name__ == "__main__":
    main()
