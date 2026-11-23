# NEPSE floorsheet Excel summaries

The workbook provides one row per stock and trading date, separate buyer and seller daily broker summaries, and a combined daily broker view. Turnover is in NPR. The trade CSV exports preserve the detail sorted by date, symbol and contract ID. Read contract IDs as text.

Run the Python step against a directory of validated `floorsheet_YYYY.parquet` files. The [NEPSE floorsheet toolkit](https://chatgpt.com/library?file_id=libfile_f984829307208191a17ebe7a7971830e&account_id=personal) includes a normalizer for source CSVs and records the data provenance.

```bash
python -m pip install duckdb
python tools/floorsheet_excel/prepare_floorsheet.py /path/to/archive /path/to/output --raw-csv
node tools/floorsheet_excel/build_workbook.mjs /path/to/output
```

The Node step requires the `@oai/artifact-tool` runtime. The Python step compares quantities and turnover across the stock, buyer and seller totals before exporting. One Excel worksheet can hold up to 1,048,576 rows, so the full trade detail is distributed as compressed yearly CSVs.

Archive sources include [Socrate AI NEPSE Open Data](https://github.com/socrateai-official/nepse-open-data), [NEPSE Floorsheet and Indices](https://huggingface.co/datasets/urekmazino69/Nepse-floorsheet-and-indices), and [NEPSE Market Data](https://huggingface.co/datasets/AnkitSanjyal/nepse-market-data). The archive also excludes two reported zero-price rows.

## July 29 reconciliation

NEPSE traded on both dates. The ShareHub figures of **48,072 trades**, **9,777,512 shares**, and **NPR 4,029,390,351** in displayed turnover belong to **July 29, 2026**.

| Trading date | Source | Trades | Shares | Turnover (NPR) |
| --- | --- | ---: | ---: | ---: |
| 2025-07-29 | [ShareSansar closing report](https://www.sharesansar.com/newsdetail/with-3076-points-gain-nepse-index-soars-above-the-psychological-benchmark-of-3000-overall-volume-stood-at-rs-1852-arba-2025-07-29) | 157,525 | 41,808,966 | Approximately 18.52 billion |
| 2026-07-29 | [ShareHub historical floorsheet](https://sharehubnepal.com/nepse/floorsheet), date selected in the UI | 48,072 | 9,777,512 | 4,029,390,351, displayed to the rupee |
| 2026-07-29 | [Archived market summary](https://github.com/shawinCreates/Nepse-Market-Data/blob/main/Data/csv/overview/2026-07-29/market_summary.csv) | 48,077 | 9,777,562 | 4,029,457,701.28 |
| 2026-07-29 | [ShareSansar closing report](https://www.sharesansar.com/newsdetail/nepse-index-loses-for-third-consecutive-day-to-close-at-268888-level-2026-07-29) | 48,071 | 9,777,442 | Approximately 4.02 billion |

The saved floorsheet count and quantity match ShareHub. The five-trade difference versus the archived market summary remains an unresolved discrepancy between sources. The available evidence does not establish that any five specific trades are missing from ShareHub.
