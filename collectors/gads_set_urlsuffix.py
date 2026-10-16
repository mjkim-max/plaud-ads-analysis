"""캠페인 최종 URL 접미사(final_url_suffix) 설정 — 수동 워크플로 전용.

env:
  GADS_CAMPAIGN_ID  : 대상 캠페인 ID (하이픈 없이)
  GADS_URL_SUFFIX   : 설정할 접미사 (예: utm_source=youtube&utm_medium=demandgen&utm_campaign=x)
"""
from __future__ import annotations

import os

import requests

from collectors import config
from collectors.gads_api import CANDIDATE_VERSIONS, access_token


def main() -> None:
    cid = os.environ["GADS_CAMPAIGN_ID"].replace("-", "")
    suffix = os.environ["GADS_URL_SUFFIX"].strip()
    cust = config.GADS_CUSTOMER_ID
    headers = {
        "Authorization": f"Bearer {access_token()}",
        "developer-token": config.GADS_DEVELOPER_TOKEN,
        "Content-Type": "application/json",
    }
    if config.GADS_LOGIN_CUSTOMER_ID:
        headers["login-customer-id"] = config.GADS_LOGIN_CUSTOMER_ID
    body = {"operations": [{
        "update": {
            "resourceName": f"customers/{cust}/campaigns/{cid}",
            "finalUrlSuffix": suffix,
        },
        "updateMask": "final_url_suffix",
    }]}
    last_err = None
    for ver in CANDIDATE_VERSIONS:
        url = f"https://googleads.googleapis.com/{ver}/customers/{cust}/campaigns:mutate"
        r = requests.post(url, headers=headers, json=body, timeout=120)
        if r.status_code == 404:
            last_err = f"{ver}: 404"
            continue
        if r.status_code != 200:
            raise RuntimeError(f"Google Ads API {r.status_code} (ver {ver}): {r.text[:800]}")
        print(f"[gads] API version {ver} 사용")
        print("RESULT:", r.json())
        return
    raise RuntimeError(f"모든 API 버전 404 ({last_err})")


if __name__ == "__main__":
    main()
