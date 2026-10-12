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
    See docs/SETUP.md for the shared dependency installation.

Run:
    python3 parquet_to_compact_csv.py
"""

import argparse
from pathlib import Path
import gzip
from research_core.io import atomic_path
from research_core.runtime import logged_main
from research_core.errors import ResearchError
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


def convert_directory(root: Path, output: Path, log=None):
    files = parquet_files(root)

    total_rows = 0
    header_written = False
    columns = None

    # text mode through gzip lets pandas append each symbol without ever
    # assembling the complete dataset in memory.
    with atomic_path(output) as temporary, gzip.open(
        temporary,
        mode="wt",
        compresslevel=GZIP_LEVEL,
        encoding="utf-8",
        newline="",
    ) as gz:
        for i, path in enumerate(files, 1):
            df = pd.read_parquet(path, engine="pyarrow")

            if columns is None:
                columns = list(df.columns)
            elif list(df.columns) != columns:
                raise ResearchError('PARQUET_SCHEMA_MISMATCH')

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

            if log is not None:
                log.progress(success=True)
            header_written = True
            total_rows += len(df)

            (log.message if log is not None else print)(
                f"[{i:02d}/{len(files):02d}] "
                f"{len(df):,} rows"
            )

            del df

    size_mb = output.stat().st_size / (1024 * 1024)
    (log.message if log is not None else print)(
        f"\nWrote {output}: "
        f"{total_rows:,} rows, {size_mb:.1f} MiB"
    )


@logged_main
def main(log):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--anchor-dir', type=Path, default=ANCHOR_DIR)
    parser.add_argument('--outcome-dir', type=Path, default=OUTCOME_DIR)
    parser.add_argument('--anchor-output', type=Path, default=ANCHOR_OUT)
    parser.add_argument('--outcome-output', type=Path, default=OUTCOME_OUT)
    args = parser.parse_args()
    log.message("Converting anchor features...")
    convert_directory(args.anchor_dir, args.anchor_output, log)

    log.message("\nConverting forward outcomes...")
    convert_directory(args.outcome_dir, args.outcome_output, log)

    log.message("\nDONE")
    log.message(f"Output: {args.anchor_output}")
    log.message(f"Output: {args.outcome_output}")
    log.message("Also upload adaptive_range_symbols.csv if available.")


if __name__ == "__main__":
    raise SystemExit(main())
