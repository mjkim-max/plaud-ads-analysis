"""Google Sheets 입출력 (gspread). 수집기와 앱이 공유하는 데이터 계층."""
import json

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

from collectors import config

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _client() -> gspread.Client:
    raw = config.GOOGLE_SA_JSON.strip() if config.GOOGLE_SA_JSON else ""
    if raw:
        try:
            info = json.loads(raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"GOOGLE_SERVICE_ACCOUNT_JSON 파싱 실패 "
                f"(길이={len(raw)}, 시작문자={raw[:1]!r}). "
                f"다운받은 JSON 파일의 '{{' 부터 '}}' 까지 전체 내용을 넣어야 합니다. "
                f"원본오류: {e}"
            )
        if info.get("type") != "service_account":
            raise RuntimeError(
                "JSON은 파싱됐지만 서비스계정 키가 아닙니다 "
                f"(type={info.get('type')!r}). 올바른 서비스계정 JSON인지 확인하세요."
            )
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    elif config.GOOGLE_SA_FILE:
        creds = Credentials.from_service_account_file(config.GOOGLE_SA_FILE, scopes=SCOPES)
    else:
        raise RuntimeError(
            "서비스계정 자격증명 없음. GOOGLE_SERVICE_ACCOUNT_JSON 또는 "
            "GOOGLE_APPLICATION_CREDENTIALS 환경변수를 설정하세요."
        )
    return gspread.authorize(creds)


def _worksheet(tab: str, cols: list[str]):
    if not config.SHEET_ID:
        raise RuntimeError("PLAUD_SHEET_ID 환경변수 없음.")
    sh = _client().open_by_key(config.SHEET_ID)
    try:
        ws = sh.worksheet(tab)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=tab, rows=1000, cols=max(26, len(cols)))
        ws.update([cols], "A1")  # 헤더
    return ws


def read_tab(tab: str, cols: list[str]) -> pd.DataFrame:
    ws = _worksheet(tab, cols)
    records = ws.get_all_records()
    df = pd.DataFrame(records)
    return df if not df.empty else pd.DataFrame(columns=cols)


def write_tab(df: pd.DataFrame, tab: str, cols: list[str]) -> int:
    """탭을 헤더+데이터로 전체 교체 (clear 후 write)."""
    ws = _worksheet(tab, cols)
    df = df.reindex(columns=cols).where(pd.notna(df.reindex(columns=cols)), "")
    ws.clear()
    ws.update([cols] + df.astype(object).values.tolist(), "A1")
    return len(df)


def append_rows(rows: list[dict], tab: str, cols: list[str]) -> int:
    """탭 끝에 행 추가 (덮어쓰지 않음). 기존 매핑 보존용."""
    if not rows:
        return 0
    ws = _worksheet(tab, cols)
    values = [["" if r.get(c) is None else r.get(c) for c in cols] for r in rows]
    ws.append_rows(values, value_input_option="RAW")
    return len(rows)


def upsert_by_date(df_new: pd.DataFrame, tab: str, cols: list[str], date_col: str = "date"):
    """df_new에 포함된 date 값들의 기존 행을 지우고 새로 채운 뒤 전체를 다시 쓴다.

    (date, ad_id) 단위 교체가 목적. 최근 N일만 df_new로 오므로 과거 데이터는 보존된다.
    """
    ws = _worksheet(tab, cols)
    existing = read_tab(tab, cols)

    df_new = df_new.reindex(columns=cols)
    incoming_dates = set(df_new[date_col].astype(str))

    if not existing.empty and date_col in existing.columns:
        existing = existing[~existing[date_col].astype(str).isin(incoming_dates)]

    combined = pd.concat([existing, df_new], ignore_index=True)
    combined = combined.reindex(columns=cols)
    combined = combined.sort_values([date_col]).reset_index(drop=True)

    # NaN → '' (Sheets 직렬화 안전)
    combined = combined.where(pd.notna(combined), "")

    ws.clear()
    ws.update([cols] + combined.astype(object).values.tolist(), "A1")
    return len(combined)
