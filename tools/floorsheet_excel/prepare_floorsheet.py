"""Prepare NEPSE summaries and sorted trade CSVs from a validated archive."""
import argparse
import json
from datetime import date
from pathlib import Path
import duckdb

def quote(value):
    return "'" + str(value).replace("'", "''") + "'"

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--raw-csv", action="store_true")
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    db = duckdb.connect()
    db.execute("SET threads=4; SET memory_limit='2200MB'; SET preserve_insertion_order=false")
    files = sorted(args.archive.glob("floorsheet_*.parquet"))
    if not files:
        p.error("Expected validated floorsheet_YYYY.parquet files. Normalize raw CSVs with the toolkit first.")
    db.execute(f"CREATE VIEW trades AS SELECT * FROM read_parquet([{','.join(map(quote, files))}])")
    required = {"trade_date","symbol","buyer_broker","seller_broker","quantity","amount_npr","contract_id","price"}
    columns = {r[0] for r in db.sql("DESCRIBE trades").fetchall()}
    if not required <= columns:
        p.error(f"Missing columns: {sorted(required - columns)}")
    start, end, count, days, qty, amount = db.sql(
        "SELECT min(trade_date),max(trade_date),count(*),count(distinct trade_date),sum(quantity),sum(amount_npr) FROM trades"
    ).fetchall()[0]
    queries = {
        "Stock by Date": 'SELECT symbol,trade_date,sum(quantity),sum(amount_npr) FROM trades GROUP BY ALL ORDER BY trade_date,symbol',
        "Buyer Brokers by Date": 'SELECT buyer_broker,trade_date,sum(quantity),sum(amount_npr) FROM trades GROUP BY ALL ORDER BY trade_date,buyer_broker',
        "Seller Brokers by Date": 'SELECT seller_broker,trade_date,sum(quantity),sum(amount_npr) FROM trades GROUP BY ALL ORDER BY trade_date,seller_broker',
    }
    epoch = date(1899, 12, 30)
    sheets = {}
    for name, sql in queries.items():
        rows = db.sql(sql).fetchall()
        assert sum(r[2] for r in rows) == qty
        assert sum(r[3] for r in rows) == amount
        sheets[name] = [[str(k),(d-epoch).days,q,float(a)] for k,d,q,a in rows]
    buy = {(r[0],r[1]):r[2:] for r in sheets["Buyer Brokers by Date"]}
    sell = {(r[0],r[1]):r[2:] for r in sheets["Seller Brokers by Date"]}
    sheets["Broker Buy and Sell"] = [[k,d,*buy.get((k,d),(0,0)),*sell.get((k,d),(0,0))]
        for k,d in sorted(buy.keys() | sell.keys(),key=lambda x:(x[1],int(x[0])))]
    data = {"sheets":sheets,"source":str(args.archive.name),"start":str(start),"end":str(end),
            "contracts":count,"sessions":days,"quantity":qty,"amount":str(amount),"columns":sorted(columns)}
    (args.output/"floorsheet_summary.json").write_text(json.dumps(data,separators=(",",":")))
    if args.raw_csv:
        for year in range(start.year,end.year+1):
            dest = args.output/f"NEPSE_Floorsheet_{year}_Sorted.csv.gz"
            db.execute(f"""COPY (SELECT * FROM trades WHERE year(trade_date)={year}
                ORDER BY trade_date,symbol,contract_id) TO {quote(dest)} (FORMAT CSV, HEADER, COMPRESSION GZIP)""")
    print(count,days,qty,amount, {k:len(v) for k,v in sheets.items()},flush=True)

if __name__ == "__main__":
    main()
