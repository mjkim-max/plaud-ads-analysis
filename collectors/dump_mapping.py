"""소재매핑 탭 전체를 CSV로 로그에 출력 (읽기 전용)."""
import csv, io, sys
from collectors import config, sheets_io

def main() -> None:
    df = sheets_io.read_tab(config.TAB_CREATIVE_MAP, config.CREATIVE_MAP_COLUMNS)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["광고이름","소재","분류방식"])
    for _, r in df.iterrows():
        w.writerow([r.get("광고이름",""), r.get("소재",""), r.get("분류방식","")])
    print("===CSV_BEGIN===")
    sys.stdout.write(buf.getvalue())
    print("===CSV_END===")

if __name__ == "__main__":
    main()
