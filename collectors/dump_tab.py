"""임의 시트 탭을 CSV로 로그에 출력 (읽기 전용). env: DUMP_TAB=탭이름"""
import csv, io, os, sys
from collectors import sheets_io

def main() -> None:
    tab = os.environ.get("DUMP_TAB", "").strip()
    if not tab:
        sys.exit("ERROR: DUMP_TAB 환경변수 없음")
    df = sheets_io.read_tab(tab, [])
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    print("===CSV_BEGIN===")
    sys.stdout.write(buf.getvalue())
    print("===CSV_END===")

if __name__ == "__main__":
    main()
