#!/usr/bin/env python3
"""
Convert the adaptive-range Parquet datasets to compact gzip CSV files.

INPUT DIRECTORIES
-----------------
adaptive_range_anchors/
adaptive_range_outcomes/

OUTPUT
------
adaptive_range_anchors.csv.gz
adaptive_range_outcomes.csv.gz

The conversion is STREAMING by symbol/file:
- reads one Parquet file
- appends it to gzip CSV
- releases memory
- moves to the next file

Size choices
------------
* gzip level 9 for smallest practical gzip CSV
* float_format="%.7g" removes unnecessary decimal text while retaining
  adequate precision for statistical modeling features
* ISO-style dates
* no index column

Install:
    python3 -m pip install -U pandas pyarrow

Run:
    python3 parquet_to_compact_csv.py
"""

from pathlib import Path
import gzip
import shutil
import pandas as pd

ANCHOR_DIR = Path("adaptive_range_anchors")
OUTCOME_DIR = Path("adaptive_range_outcomes")

ANCHOR_OUT = Path("adaptive_range_anchors.csv.gz")
OUTCOME_OUT = Path("adaptive_range_outcomes.csv.gz")

FLOAT_FORMAT = "%.7g"
GZIP_LEVEL = 9


def parquet_files(root: Path):
    files = sorted(root.glob("*.parquet"))
    if not files:
        raise SystemExit(f"No .parquet files found in {root}/")
    return files


def convert_directory(root: Path, output: Path):
    files = parquet_files(root)

    if output.exists():
        output.unlink()

    total_rows = 0
    header_written = False

    # text mode through gzip lets pandas append each symbol without ever
    # assembling the complete dataset in memory.
    with gzip.open(
        output,
        mode="wt",
        compresslevel=GZIP_LEVEL,
        encoding="utf-8",
        newline="",
    ) as gz:
        for i, path in enumerate(files, 1):
            df = pd.read_parquet(path, engine="pyarrow")

            # Stable ordering helps compression and later auditing.
            sort_cols = [
                c for c in ("symbol", "anchor_dt", "x_days")
                if c in df.columns
            ]
            if sort_cols:
                df = df.sort_values(sort_cols, kind="stable")

            df.to_csv(
                gz,
                index=False,
                header=not header_written,
                float_format=FLOAT_FORMAT,
                date_format="%Y-%m-%d",
                lineterminator="\n",
            )

            header_written = True
            total_rows += len(df)

            print(
                f"[{i:02d}/{len(files):02d}] "
                f"{path.name:18s} "
                f"{len(df):,} rows"
            )

            del df

    size_mb = output.stat().st_size / (1024 * 1024)
    print(
        f"\nWrote {output}: "
        f"{total_rows:,} rows, {size_mb:.1f} MiB"
    )


def main():
    print("Converting anchor features...")
    convert_directory(ANCHOR_DIR, ANCHOR_OUT)

    print("\nConverting forward outcomes...")
    convert_directory(OUTCOME_DIR, OUTCOME_OUT)

    print("\nDONE")
    print(f"Upload: {ANCHOR_OUT}")
    print(f"Upload: {OUTCOME_OUT}")
    print("Also upload adaptive_range_symbols.csv if available.")


if __name__ == "__main__":
    main()
