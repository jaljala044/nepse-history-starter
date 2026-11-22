"""Write the prepared NEPSE summaries to one Excel workbook with bounded memory."""
import argparse
import json
from pathlib import Path
from datetime import datetime, timedelta
import xlsxwriter

HEADERS = {
    "Stock by Date": ["Symbol", "Date", "Quantity", "Amount (NPR)"],
    "Buyer Brokers by Date": ["Buyer Broker", "Date", "Buy Quantity", "Buy Amount (NPR)"],
    "Seller Brokers by Date": ["Seller Broker", "Date", "Sell Quantity", "Sell Amount (NPR)"],
    "Broker Buy and Sell": ["Broker", "Date", "Buy Quantity", "Buy Amount (NPR)", "Sell Quantity", "Sell Amount (NPR)"],
}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    data = json.loads((args.folder / "floorsheet_summary.json").read_text())
    output = args.folder / "NEPSE_Floorsheet_Summaries.xlsx"
    temporary = output.with_suffix(".tmp.xlsx")
    with xlsxwriter.Workbook(temporary, {"constant_memory": True, "strings_to_formulas": False}) as wb:
        heading = wb.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": "#173751"})
        quantity = wb.add_format({"num_format": "#,##0"})
        rupees = wb.add_format({"num_format": "#,##0.00"})
        day = wb.add_format({"num_format": "yyyy-mm-dd"})
        epoch = datetime(1899, 12, 30)
        for name, columns in HEADERS.items():
            rows = data["sheets"][name]
            if len(rows) >= 1_048_576:
                raise ValueError(f"{name} exceeds Excel's worksheet row limit")
            ws = wb.add_worksheet(name)
            ws.write_row(0, 0, columns, heading)
            ws.set_column(0, 0, 18)
            ws.set_column(1, 1, 14)
            ws.set_column(2, len(columns)-1, 22)
            ws.freeze_panes(1, 0)
            ws.autofilter(0, 0, len(rows), len(columns)-1)
            for idx, (key, serial, *values) in enumerate(rows, 1):
                ws.write_string(idx, 0, key)
                ws.write_datetime(idx, 1, epoch + timedelta(days=serial), day)
                for col, value in enumerate(values, 2):
                    ws.write_number(idx, col, value, quantity if col % 2 == 0 else rupees)
        ws = wb.add_worksheet("Coverage")
        ws.set_column(0, 0, 26)
        ws.set_column(1, 1, 90)
        ws.write_row(0, 0, ["Metric", "Value"], heading)
        ws.write_row(1, 0, ["First and last trade dates", f"{data['start']} through {data['end']}"])
        for row, (label, key, fmt) in enumerate((
            ("Trading sessions", "sessions", quantity), ("Validated contracts", "contracts", quantity),
            ("Traded quantity", "quantity", quantity), ("Turnover (NPR)", "amount", rupees)), 2):
            ws.write(row, 0, label)
            ws.write_number(row, 1, float(data[key]), fmt)
        notes = [
            ("Archive scope", "Validated multi-source NEPSE floorsheet archive"),
            ("Turnover difference", "July 29, 2026 was open. ShareHub reported 48,072 trades, the market archive 48,077."),
            ("Source exception", "Two reported zero-price records were excluded."),
            ("Transaction detail", "The sorted yearly CSV files contain the individual trades."),
        ]
        for row, item in enumerate(notes, 6):
            ws.write_row(row, 0, item)
    temporary.replace(output)

if __name__ == "__main__":
    main()
