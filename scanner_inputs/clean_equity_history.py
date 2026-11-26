"""Build separate research candidates; never overwrite raw archives.
Run: python3 scanner_inputs/clean_equity_history.py
Repeated records are quarantined, not independently verified as false.
"""
import csv, datetime as dt, json, math, hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
S = ROOT / "scanner_inputs"
OUT = S / "research_cleaning" / "universe_candidate"
def read(p):
    with p.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))
def write(p, fields, rows):
    with p.open("x", newline="", encoding="utf-8") as f:
        w=csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
def valid(r):
    try:
        o,h,l,c,v = (float(r[k]) for k in ("open","high","low","close","volume"))
        dt.date.fromisoformat(r["date"])
        return all(map(math.isfinite,(o,h,l,c,v))) and 0 < l <= min(o,c) <= max(o,c) <= h and v >= 0 and v.is_integer()
    except (ValueError,KeyError,TypeError):
        return False
def main():
    symbols=sorted({r["symbol"] for r in read(S/"sectors.csv")})
    known_open={r["date"] for r in read(S/"market_summary_daily.csv")}
    excluded={(r["symbol"],r["date"]) for r in read(S/"audit"/"price_gap_exclusions_2026-07-24.csv")}
    fills={}
    for r in read(S/"price_gap_fills"/"2026-07-24.csv"):
        fills.setdefault(r["symbol"],[]).append(r)
    fields=["symbol","date","open","high","low","close","volume","provenance"]
    candidate=[]; quarantine=[]; manifest=[]
    for sym in symbols:
        p=ROOT/"03_stock_charts_ohlcv"/(sym+"_OHLCV.csv")
        if not p.is_file():
            manifest.append({"symbol":sym,"status":"MISSING_FILE"})
            continue
        raw=[{k.strip().lower():v.strip() for k,v in r.items() if k is not None and v is not None} for r in read(p)]
        bydate={}
        for r in raw:
            bydate.setdefault(r.get("date",""),[]).append(r)
        prev=None; accepted=0; rejected=0; recovered=0
        for date, group in sorted(bydate.items()):
            for r in group:
                row={k:r.get(k,"") for k in fields}
                row["symbol"]=sym
                values=tuple(r.get(k) for k in fields[2:7])
                reason=None
                if len(group)>1: reason="duplicate_date"
                elif not valid(r): reason="invalid_ohlcv"
                elif (sym,date) in excluded: reason="existing_disputed_record"
                else:
                    d=dt.date.fromisoformat(date)
                    weekly=d.weekday()==5 or (d.weekday()==4 if date<"2026-04-06" else d.weekday()==6)
                    if weekly and date not in known_open: reason="regular_closure_candidate"
                    elif values==prev: reason="repeat_on_known_open" if date in known_open else "repeat_unverified_session"
                if reason:
                    quarantine.append(dict(row,provenance=reason)); rejected+=1
                else:
                    candidate.append(dict(row,provenance="raw_nonrepeated_unverified")); accepted+=1
                prev=values if valid(r) and len(group)==1 else None
        for r in fills.get(sym,[]):
            date=r["date"]
            if len([x for x in fills[sym] if x["date"]==date])!=1 or date in bydate or (sym,date) in excluded or not valid(r): continue
            candidate.append(dict({k:r.get(k,"") for k in fields},provenance="existing_reconciled_gap_fill"))
            recovered+=1
        manifest.append({"symbol":sym,"status":"RESEARCH_ONLY","raw_rows":len(raw),"accepted":accepted,"quarantined":rejected,"recovered":recovered,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
    assert len({(r["symbol"],r["date"]) for r in candidate})==len(candidate)
    OUT.mkdir(parents=True,exist_ok=False)
    write(OUT/"candidate.csv",fields,sorted(candidate,key=lambda r:(r["symbol"],r["date"])))
    write(OUT/"quarantine.csv",fields,quarantine)
    (OUT/"manifest.json").write_text(json.dumps({"universe":len(symbols),"candidate_rows":len(candidate),"quarantine_rows":len(quarantine),"independent_validation":False,"stocks":manifest},indent=2))
if __name__=="__main__":
    main()
