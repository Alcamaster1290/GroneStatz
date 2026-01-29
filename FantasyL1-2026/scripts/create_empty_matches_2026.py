from __future__ import annotations

from pathlib import Path

import duckdb


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    data_root = root.parent / "gronestats" / "data" / "Liga 1 Peru"
    source = data_root / "2025" / "parquets" / "normalized" / "matches.parquet"
    target_dir = data_root / "2026" / "parquets" / "normalized"
    target = target_dir / "matches.parquet"

    if not source.exists():
        raise FileNotFoundError(f"source_matches_not_found: {source}")

    target_dir.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()

    con = duckdb.connect()
    try:
        source_path = source.as_posix().replace("'", "''")
        target_path = target.as_posix().replace("'", "''")
        con.execute(
            f"CREATE OR REPLACE TABLE tmp_matches AS "
            f"SELECT * FROM read_parquet('{source_path}') WHERE 1=0"
        )
        con.execute(f"COPY tmp_matches TO '{target_path}' (FORMAT 'parquet')")
    finally:
        con.close()

    print(f"empty_matches_2026_ok {target}")


if __name__ == "__main__":
    main()
