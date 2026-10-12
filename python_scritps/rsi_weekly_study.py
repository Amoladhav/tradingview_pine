#!/usr/bin/env python3
"""Explicit cached/public-data weekly RSI study; no trading decisions."""
from __future__ import annotations

import argparse
import hashlib
import re
from importlib.metadata import PackageNotFoundError, version
from datetime import date
from pathlib import Path
import tarfile

import pandas as pd

from research_core.errors import ResearchError, safe_error_code
from research_core.fetching import add_source_arguments, source_from_args
from research_core.runtime import RunLog
from research_core.io import atomic_path, validate_symbol
from rsi_research import build_study, write_study

SECTOR_GROUPS = {
    "XLK": "AAPL AMZN MSFT GOOGL META NVDA AVGO NFLX TSLA AMD CRM ORCL ADBE QCOM INTC IBM NOW PANW MU AMAT INTU",
    "XLF": "JPM BAC WFC GS MS C BLK SCHW AXP USB PNC TFC COF CME ICE",
    "XLI": "CAT DE HON GE RTX LMT UPS FDX UNP BA ETN EMR ITW GD NOC WM",
    "XLV": "LLY UNH JNJ MRK ABBV AMGN GILD ISRG TMO MDT ABT DHR BMY PFE CVS",
    "XLY": "HD LOW NKE MCD SBUX TGT BKNG MAR GM F",
    "XLP": "WMT COST PG KO PEP CL KMB MDLZ GIS KR",
    "XLE": "XOM CVX COP SLB EOG OXY MPC PSX",
    "XLB": "FCX NEM LIN APD SHW DOW NUE",
    "XLU": "NEE DUK SO AEP EXC SRE D",
    "XLC": "VZ T DIS CMCSA TMUS",
    "IYR": "PLD AMT EQIX O",
}
# Descriptive sector comparators only; classifications are a reviewed study input,
# not provider classifications. Correct cross-sector names explicitly below.
SECTORS = {symbol: sector for sector, values in SECTOR_GROUPS.items() for symbol in values.split()}
SECTORS.update({"AMZN":"XLY", "TSLA":"XLY", "GOOGL":"XLC", "META":"XLC", "NFLX":"XLC"})
ETFS = "SPY QQQ IWM DIA RSP XLK XLF XLE XLV XLI XLY XLP XLU XLB XLC SMH IYR".split()
UNIVERSE = list(dict.fromkeys([*SECTORS, *ETFS]))


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    add_source_arguments(p)
    p.add_argument("--symbols", nargs="+", default=UNIVERSE)
    p.add_argument("--start", default="2005-01-01")
    p.add_argument("--as-of", default=date.today().isoformat(), help="Exclusive date cutoff; Friday bars qualify from Saturday onward.")
    p.add_argument("--output-dir", type=Path, required=True, help="New run directory; existing directories are never overwritten.")
    p.add_argument("--show-samples", action="store_true", help="Write public sample events to a research CSV for owner manual checks.")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if not all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) for value in (args.start, args.as_of)):
            raise ResearchError("INVALID_STUDY_DATES")
        start, cutoff = pd.Timestamp(date.fromisoformat(args.start)), pd.Timestamp(date.fromisoformat(args.as_of))
        if start >= cutoff or cutoff > pd.Timestamp(date.today()) or args.output_dir.exists():
            raise ResearchError("INVALID_STUDY_SETTINGS")
        source = source_from_args(args)
        symbols = list(dict.fromkeys(validate_symbol(s) for s in args.symbols))
        daily, failed = {}, {}
        # Logs are adjacent to the run outputs, and packaged by exact path.
        with RunLog("rsi_weekly_study", root=args.output_dir.parent, total=len(symbols)) as log:
            for symbol in symbols:
                try:
                    frame = source.history(symbol, start=args.start, end=args.as_of, interval="1d", auto_adjust=False, actions=True)
                    if isinstance(frame.columns, pd.MultiIndex):
                        if "Ticker" in frame.columns.names:
                            frame = frame.xs(symbol, axis=1, level="Ticker")
                        elif len(frame.columns.get_level_values(-1).unique()) == 1:
                            frame.columns = frame.columns.get_level_values(0)
                        else:
                            raise ResearchError("UNEXPECTED_HISTORY_SCHEMA")
                    daily[symbol] = frame
                    log.progress(success=True)
                except (ResearchError, ValueError, KeyError) as exc:
                    failed[symbol] = safe_error_code(exc)
                    log.error(exc)
                    log.progress(success=False)
            log.message("Generating completed-week predictors and separate future outcomes")
            tables, metadata = build_study(daily, args.as_of, SECTORS, progress=lambda completed, total: log.message(f"Features {completed}/{total}"))
            try:
                metadata["versions"]["yfinance"] = version("yfinance")
            except PackageNotFoundError:
                metadata["versions"]["yfinance"] = "not installed"
            source_root = Path(__file__).resolve().parent
            source_files = [Path(__file__), *sorted((source_root/"rsi_research").glob("*.py")), *sorted((source_root/"research_core").glob("*.py"))]
            metadata["code_version"] = "rsi14-sma14-v1"
            metadata["source_sha256"] = {str(path.relative_to(source_root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_files}
            metadata["requested_universe"] = symbols
            quarantined_count = len(metadata["failures"])
            if quarantined_count:
                log.counts["succeeded"] -= quarantined_count
                log.counts["failed"] += quarantined_count
                log.error(ResearchError("STUDY_SYMBOLS_QUARANTINED"))
            metadata["failures"].update(failed)
            metadata["source"] = "yfinance decoded daily DataFrames; auto_adjust=False, actions=True"
            metadata["start_requested"] = args.start
            metadata["mode"] = "refresh" if getattr(args, "refresh", False) else "fetch" if args.fetch else "cache"
            metadata["archive_log_boundary"] = "snapshot immediately before archive completion; final status remains in external run log and sanitized review report"
            if not metadata["successful_symbols"]:
                raise ResearchError("NO_USABLE_STUDY_DATA")
            log.message("Writing study tables, dictionary, metadata and summary")
            written = write_study(tables, metadata, args.output_dir)
            if args.show_samples:
                events = tables["rsi_cross_events"]
                samples = events.loc[events.symbol.isin(("AMZN", "AAPL", "MSFT", "JPM", "XOM", "SPY")), ["symbol", "week", "cross_direction", "rsi_14", "rsi_sma_14"]].groupby("symbol").head(3)
                sample_path = args.output_dir / "rsi_manual_verification_samples.csv"
                samples.to_csv(sample_path, index=False)
                written.append(sample_path)
            partial = bool(metadata["failures"])
            root = Path(__file__).resolve().parent
            sources = [Path(__file__), *sorted((root/"rsi_research").glob("*.py")), *sorted((root/"research_core").glob("*.py"))]
            manifests = [root.parent/"docs"/"RSI_STUDY.md"]
            requirements = args.output_dir / "rsi_requirements.txt"
            package_lines = [f"{package}=={metadata['versions'][package]}" for package in ("numpy", "pandas", "yfinance") if metadata["versions"].get(package) not in (None, "not installed")]
            requirements.write_text("\n".join(package_lines) + "\n", encoding="utf-8")
            written.append(requirements)
            readme = args.output_dir / "RSI_ARCHIVE_README.txt"
            readme.write_text("Python >=3.12. Install with: python -m pip install -r rsi_requirements.txt\nRun from extracted archive: python source/rsi_weekly_study.py --help\nSource cache is intentionally excluded; replay requires separately retained captures via --cache-dir.\nUse --fetch explicitly to download; install yfinance separately if unavailable in recorded environment.\nsource/docs/RSI_STUDY.md documents formulas when included from a source checkout; the data dictionary is always included.\n", encoding="utf-8")
            written.append(readme)
            archive = args.output_dir / "rsi_sma_weekly_study.tar.gz"
            with atomic_path(archive) as temporary, tarfile.open(temporary, "w:gz") as tar:
                for path in written:
                    tar.add(path, arcname=path.name)
                for path in sources:
                    tar.add(path, arcname=str(Path("source") / path.relative_to(root)))
                for path in manifests:
                    if path.exists():
                        tar.add(path, arcname=str(Path("source")/"docs"/path.name))
                for path in (log.events_path, log.errors_path):
                    tar.add(path, arcname=str(Path("logs")/path.name))
            log.finish("partial" if partial else "completed")
        for path in [*written, archive]:
            print(f"{path}: {path.stat().st_size} bytes")
        print("STUDY PARTIAL" if partial else "STUDY COMPLETE")
        print(f"{archive}: {archive.stat().st_size} bytes")
        return 2 if partial else 0
    except KeyboardInterrupt:
        print("STUDY CANCELLED")
        return 130
    except Exception as exc:
        print(safe_error_code(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
