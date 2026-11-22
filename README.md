# NEPSE History Starter

Use this private repository to check and upload daily Nepal Stock Exchange price history. OHLCV stands for open, high, low, close, and volume. Python validates the CSV and prepares the archive on your Mac. GitHub Desktop uploads the changes after you review them.

## 1. Get Python and clone the repository

1. Open **Terminal** and run `python3 --version`. Use Python 3.10 or later. If needed, install it from [Python for macOS](https://www.python.org/downloads/macos/). The importer uses the Python standard library.
2. Install [GitHub Desktop](https://desktop.github.com/) and sign in as `jaljala044`.
3. In GitHub Desktop, choose **File → Clone Repository**, select `jaljala044/nepse-history-starter`, and click **Clone**. Note the **Local Path**. [GitHub Desktop cloning guide](https://docs.github.com/en/desktop/adding-and-cloning-repositories/cloning-and-forking-repositories-from-github-desktop?platform=mac).
4. In Terminal, go to the clone. If you cloned to a different location, use your **Local Path** in this command.

```bash
cd ~/Documents/GitHub/nepse-history-starter
```

## 2. Preview the practice CSV

```bash
python3 nepse_history_import.py --repo . --input examples/DEMO_OHLCV.csv --source "Synthetic practice data"
```

Expect `3 new / 3 unique input rows` and `Preview only`. The practice CSV uses fictional prices and belongs in `examples/`.

## 3. Preview one real stock CSV

Use one daily, unadjusted export. For example, save an NRN export as `NRN_OHLCV.csv` in **Downloads**. Use your actual filename and replace the source text with the publisher name and export URL.

```bash
python3 nepse_history_import.py --repo . --input ~/Downloads/NRN_OHLCV.csv --source "Publisher name and export URL"
```

Use Gregorian dates in `YYYY-MM-DD` format. A one-stock CSV can use the header `Date,Open,High,Low,Close,Volume`. Use a `SYMBOL_OHLCV.csv` filename, or pass `--symbol SYMBOL` if the symbol is absent from the CSV and filename. A combined CSV can use `Date,Symbol,Open,High,Low,Close,Volume`.

Review the symbol and new-row count. Identical dates are skipped. A date with conflicting prices stops the import for review. To add dates to an existing archive, confirm the same unadjusted price basis and include `--merge-existing-ohlcv`.

## 4. Prepare the files and send the commit to GitHub

After a successful real-data preview, run the same command with `--write` at the end. The importer writes the stock CSV under `03_stock_charts_ohlcv/` and a source record with input and output hashes under `historical_imports/`.

In GitHub Desktop, open **Changes** and review the generated CSV and source record. Make sure your data provider permits storing the export in this repository. Enter a summary such as `Import NRN daily price history`, click **Commit to main**, then click **Push origin**. Refresh the repository page on GitHub to confirm both files appear. [GitHub Desktop commit and push guide](https://docs.github.com/en/desktop/making-changes-in-a-branch/committing-and-reviewing-changes-to-your-project-in-github-desktop?platform=mac).

## Supplemental scanner inputs

The verified broker summaries, price-gap fills, sector inputs, and corporate-action audit are documented in [scanner_inputs](scanner_inputs/README.md).
