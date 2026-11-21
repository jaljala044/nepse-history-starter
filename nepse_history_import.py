#!/usr/bin/env python3
"""Preview or prepare historical NEPSE CSVs in a local Git checkout."""
import argparse
import csv
import hashlib
import io
import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from tempfile import NamedTemporaryFile

CHARTS = Path("03_stock_charts_ohlcv")
FLOORSHEETS = Path("02_floorsheet_daily")
OHLCV = ("Date", "Open", "High", "Low", "Close", "Volume")
TRADE = ("Trading_Date", "Transaction", "Symbol", "Buyer", "Seller", "Quantity", "Rate", "Amount")
ALIASES = {
    "Date": ("tradingdate", "businessdate", "datetime"),
    "Symbol": ("stocksymbol", "scrip", "ticker"),
    "Volume": ("vol", "qty", "quantity", "tradedquantity"),
    "Transaction": ("contractno", "contractnumber", "contractid", "transactionid"),
    "Buyer": ("buyerbroker", "buyerbrokerid"),
    "Seller": ("sellerbroker", "sellerbrokerid"),
    "Quantity": ("qty", "tradequantity"),
    "Rate": ("price", "tradeprice"),
    "Amount": ("turnover", "tradeamount"),
    "TotalTrades": ("totaltransactions", "rowcount"),
}
NPT = timezone(timedelta(hours=5, minutes=45))
DECIMAL = re.compile(r"[+-]?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]+)?")
FILE_DATE = re.compile(r"(?:^|[^0-9])(20[0-9]{2})[-_]([0-9]{2})[-_]([0-9]{2})(?:$|[^0-9])")
MAX_BYTES = 100 * 1024 * 1024


def heading(value):
    return re.sub(r"[^a-z0-9]", "", value.lower())


def field(row, name, default=None):
    keys = (heading(name), *ALIASES.get(name, ()))
    present = [key for key in keys if key in row]
    if len(present) > 1:
        # A full daily market-price export may include both Volume and other quantities.
        if keys[0] in present:
            return row[keys[0]]
        raise ValueError(f"ambiguous {name} columns")
    if present:
        return row[present[0]]
    if default is not None:
        return default
    raise ValueError(f"missing {name} column")


def read_rows(raw, path):
    reader = csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
    header = [heading(value) for value in next(reader, [])]
    if not header or "" in header or len(set(header)) != len(header):
        raise ValueError(f"{path}: missing, blank or duplicate CSV headers")
    for cells in reader:
        if not cells or not any(cell.strip() for cell in cells):
            continue
        if len(cells) != len(header):
            raise ValueError(f"{path}:{reader.line_num}: wrong number of CSV fields")
        yield reader.line_num, dict(zip(header, (cell.strip() for cell in cells)))


def session(value):
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError(f"expected a Gregorian YYYY-MM-DD date, got {value!r}")
    day = date.fromisoformat(value)
    if not date(1993, 1, 1) <= day <= datetime.now(NPT).date():
        raise ValueError(f"date outside supported NEPSE history: {value}")
    return value


def input_date(row, path):
    match = FILE_DATE.search(path.stem)
    inferred = "-".join(match.groups()) if match else ""
    value = session(field(row, "Date", inferred))
    if inferred and value != inferred:
        raise ValueError(f"date {value} disagrees with filename date {inferred}")
    return value


def number(value):
    if not DECIMAL.fullmatch(value):
        raise ValueError(f"expected a full numeric value, got {value!r}")
    return Decimal(value.replace(",", ""))


def whole(value, minimum, name):
    amount = number(value)
    if amount < minimum or amount != amount.to_integral_value():
        raise ValueError(f"{name} must be a whole number of at least {minimum}")
    return amount


def symbol(value, chart=False):
    value = value.upper()
    pattern = r"[A-Z0-9][A-Z0-9._-]{0,29}" if chart else r"[A-Z0-9][A-Z0-9._/-]{0,29}"
    if not re.fullmatch(pattern, value):
        raise ValueError(f"invalid or unsupported stock symbol {value!r}")
    return value


def ohlcv_record(row):
    prices = tuple(number(field(row, name)) for name in OHLCV[1:5])
    opened, high, low, closed = prices
    if low <= 0 or not low <= min(opened, closed) <= max(opened, closed) <= high:
        raise ValueError("OHLC values are outside the candle's high/low range")
    return (*prices, whole(field(row, "Volume"), 0, "volume"))


def floor_record(row):
    contract = field(row, "Transaction")
    buyer, seller = field(row, "Buyer"), field(row, "Seller")
    if not all(re.fullmatch(r"[0-9]+", value) for value in (contract, buyer, seller)):
        raise ValueError("contract and broker identifiers must be text containing digits only")
    stock = symbol(field(row, "Symbol"))
    quantity = whole(field(row, "Quantity"), 1, "quantity")
    rate, amount = number(field(row, "Rate")), number(field(row, "Amount"))
    if rate <= 0 or amount <= 0 or amount != (quantity * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP):
        raise ValueError("amount differs from quantity × rate, rounded to cents")
    return contract, (stock, buyer, seller, quantity, rate, amount)


def csv_rows(raw, path, parse):
    results = []
    for line, row in read_rows(raw, path):
        try:
            results.append(parse(row))
        except (ValueError, ArithmeticError) as error:
            raise ValueError(f"{path}:{line}: {error}") from error
    if not results:
        raise ValueError(f"{path}: no data rows")
    return results


def read_input(path, args, grouped):
    raw = path.read_bytes()
    chart_match = re.fullmatch(r"(.+)_OHLCV", path.stem, re.IGNORECASE)
    chart_symbol = chart_match.group(1).upper() if chart_match else ""
    fallback = args.symbol or chart_symbol

    def parse(row):
        day = input_date(row, path)
        if args.kind == "floorsheet":
            contract, trade = floor_record(row)
            return day, contract, trade
        ticker = symbol(field(row, "Symbol", fallback), chart=True)
        if fallback and ticker != fallback:
            raise ValueError(f"symbol {ticker} disagrees with expected symbol {fallback}")
        return ticker, day, ohlcv_record(row)

    for group, key, payload in csv_rows(raw, path, parse):
        prior = grouped[group].setdefault(key, payload)
        if prior != payload:
            raise ValueError(f"{path}: conflicting input rows for {group} / {key}")
    return {"file": path.name, "sha256": hashlib.sha256(raw).hexdigest()}


def read_counts(path):
    raw = path.read_bytes()

    def parse(row):
        return session(field(row, "Date")), int(whole(field(row, "TotalTrades"), 1, "trade count"))

    pairs = csv_rows(raw, path, parse)
    counts = dict(pairs)
    if len(counts) != len(pairs):
        raise ValueError(f"{path}: duplicate date in trade counts")
    return counts, {"file": path.name, "sha256": hashlib.sha256(raw).hexdigest()}


def render_csv(headers, rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow(format(value, "f") if isinstance(value, Decimal) else value for value in row)
    return stream.getvalue().encode("utf-8")


def existing_chart(path, raw):
    header = next(csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline="")), [])
    if tuple(map(heading, header)) != tuple(map(heading, OHLCV)):
        raise ValueError(f"{path}: unexpected chart archive headers. Review its schema before merging.")

    def parse(row):
        day = session(field(row, "Date"))
        cells = tuple(field(row, name) for name in OHLCV[1:])
        try:
            return day, cells, ohlcv_record(row), True
        except ValueError:
            # Preserve legacy rows and refuse incoming rows that overlap them.
            return day, cells, None, False

    records = {}
    for day, cells, values, valid in csv_rows(raw, path, parse):
        if day in records:
            raise ValueError(f"{path}: duplicate archived date {day}")
        records[day] = (cells, values, valid)
    return records


def chart_plan(path, incoming, old, args):
    existing = {} if old is None else existing_chart(path, old)
    legacy = sum(not record[2] for record in existing.values())
    if legacy:
        print(f"NOTICE {path.name}: {legacy} legacy bar(s) failed validation and will be preserved.")
    for day in incoming.keys() & existing.keys():
        if incoming[day] != existing[day][1]:
            raise ValueError(f"{path.name}: existing bar differs or is invalid on {day}")
    additions = incoming.keys() - existing.keys()
    if not additions:
        return None, 0
    if old is not None and not args.merge_existing_ohlcv:
        raise ValueError(f"{path.name}: verify the same price basis, then use --merge-existing-ohlcv")
    combined = {day: record[0] for day, record in existing.items()}
    combined.update((day, incoming[day]) for day in additions)
    return render_csv(OHLCV, ((day, *combined[day]) for day in sorted(combined))), len(additions)


def floor_plan(path, day, incoming, old, expected):
    if len(incoming) != expected:
        raise ValueError(f"{day}: {len(incoming):,} unique trades, expected {expected:,}")
    if old is not None:
        try:
            archived = csv_rows(old, path, lambda row: (input_date(row, path), *floor_record(row)))
        except ValueError as error:
            raise ValueError(f"{path}: an existing archive needs review ({error})") from error
        if len(archived) != expected or any(d != day for d, _, _ in archived):
            raise ValueError(f"{path}: existing archive has a different session or row count")
        if {key: trade for _, key, trade in archived} != incoming:
            raise ValueError(f"{path}: existing trades differ. Review before replacing.")
        return None, 0
    data = render_csv(TRADE, ((day, key, *incoming[key]) for key in sorted(incoming, key=int)))
    return data, len(incoming)


def write_file(path, data, previous):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as output:
        temporary = Path(output.name)
        try:
            output.write(data)
            output.close()
            if previous is None:
                path.hardlink_to(temporary)
            else:
                if path.read_bytes() != previous:
                    raise ValueError(f"{path} changed since validation")
                temporary.chmod(path.stat().st_mode & 0o777)
                temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def run(args):
    repo = args.repo.resolve()
    if not (repo / ".git").exists():
        raise ValueError("--repo must point to the root of a local Git checkout")
    if not args.source.strip():
        raise ValueError("--source must identify the dataset or publisher")
    if args.kind == "ohlcv" and args.counts:
        raise ValueError("--counts is only used for floorsheets")
    if args.kind == "floorsheet" and (not args.counts or args.symbol or args.merge_existing_ohlcv):
        raise ValueError("Floorsheets require --counts and accept neither --symbol nor --merge-existing-ohlcv")
    if args.symbol:
        args.symbol = symbol(args.symbol, chart=True)

    source = args.input
    paths = sorted(source.glob("*.csv")) if source.is_dir() else [source]
    paths = [path for path in paths if not args.counts or path.resolve() != args.counts.resolve()]
    if not paths or any(path.suffix.lower() != ".csv" for path in paths):
        raise ValueError("--input must be a CSV or a directory with CSVs at its top level")
    grouped = defaultdict(dict)
    origins = [read_input(path, args, grouped) for path in paths]
    counts, count_origin = read_counts(args.counts) if args.counts else ({}, None)

    root = CHARTS if args.kind == "ohlcv" else FLOORSHEETS
    if (repo / root).is_symlink() or (repo / "historical_imports").is_symlink():
        raise ValueError("archive or manifest directory is a symbolic link")
    plans = []
    for group, incoming in sorted(grouped.items()):
        name = f"{group}_OHLCV.csv" if args.kind == "ohlcv" else f"floorsheet_{group}.csv"
        path = repo / root / name
        if path.is_symlink():
            raise ValueError(f"{path} is a symbolic link")
        old = path.read_bytes() if path.exists() else None
        if args.kind == "ohlcv":
            data, added = chart_plan(path, incoming, old, args)
        else:
            if group not in counts:
                raise ValueError(f"{group}: trade count is missing from --counts")
            legacy_path = repo / "floorsheet" / name
            if old is None and legacy_path.exists():
                raise ValueError(f"{legacy_path}: legacy archive already contains this date. Review it first.")
            data, added = floor_plan(path, group, incoming, old, counts[group])
        print(f"{root / name}: {added:,} new / {len(incoming):,} unique input rows")
        if data is not None:
            if len(data) > MAX_BYTES:
                raise ValueError(f"{name} exceeds the 100 MiB GitHub file limit")
            plans.append((path, data, old, added))

    if not plans:
        print("No new rows. Nothing was written.")
        return

    manifest = {
        "kind": args.kind,
        "source": args.source.strip(),
        "input_files": origins,
        "trade_counts_file": count_origin,
        "price_basis": "unadjusted" if args.kind == "ohlcv" else None,
        "files": [
            {"path": path.relative_to(repo).as_posix(), "new_rows": added,
             "sha256": hashlib.sha256(data).hexdigest()}
            for path, data, _, added in plans
        ],
    }
    manifest_bytes = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    manifest_path = repo / "historical_imports" / (hashlib.sha256(manifest_bytes).hexdigest()[:24] + ".json")
    if manifest_path.is_symlink():
        raise ValueError(f"{manifest_path} is a symbolic link")
    if args.write:
        for path, data, old, _ in plans:
            write_file(path, data, old)
        if not manifest_path.exists():
            write_file(manifest_path, manifest_bytes, None)
        print(f"Wrote {len(plans)} archive file(s) and {manifest_path.relative_to(repo)}. Review with git status.")
    else:
        print(f"Preview only. Run the same command with --write to prepare {len(plans)} file(s).")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True, help="root of the local Git clone")
    parser.add_argument("--input", type=Path, required=True, help="CSV file or directory of CSV files")
    parser.add_argument("--kind", choices=("ohlcv", "floorsheet"), default="ohlcv")
    parser.add_argument("--source", required=True, help="publisher URL or description of your export")
    parser.add_argument("--symbol", help="one stock ticker for a chart CSV without a Symbol column")
    parser.add_argument("--counts", type=Path, help="floorsheet control CSV with Date,TotalTrades")
    parser.add_argument("--merge-existing-ohlcv", action="store_true", help="confirm matching unadjusted price basis")
    parser.add_argument("--write", action="store_true", help="write to the clone after validating the entire batch")
    try:
        run(parser.parse_args())
    except (OSError, ValueError, csv.Error, ArithmeticError) as error:
        print(f"Import error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
