# NEPSE floorsheet Excel summaries

The workbook provides one row per stock and trading date, separate buyer and seller daily broker summaries, and a combined daily broker view. Turnover is in NPR. The trade CSV exports preserve the detail sorted by date, symbol and contract ID. Read contract IDs as text.

Run the Python step against a directory of validated `floorsheet_YYYY.parquet` files. The [NEPSE floorsheet toolkit](https://chatgpt.com/library?file_id=libfile_f984829307208191a17ebe7a7971830e&account_id=personal) includes a normalizer for source CSVs and records the data provenance.

```bash
python -m pip install duckdb
python tools/floorsheet_excel/prepare_floorsheet.py /path/to/archive /path/to/output --raw-csv
node tools/floorsheet_excel/build_workbook.mjs /path/to/output
```

The Node step requires the `@oai/artifact-tool` runtime. The Python step compares quantities and turnover across the stock, buyer and seller totals before exporting. One Excel worksheet can hold up to 1,048,576 rows, so the full trade detail is distributed as compressed yearly CSVs.

Archive sources include [Socrate AI NEPSE Open Data](https://github.com/socrateai-official/nepse-open-data), [NEPSE Floorsheet and Indices](https://huggingface.co/datasets/urekmazino69/Nepse-floorsheet-and-indices), and [NEPSE Market Data](https://huggingface.co/datasets/AnkitSanjyal/nepse-market-data). July 29, 2026 is an open trading session with differing totals across sources. The archive also excludes two reported zero-price rows.
