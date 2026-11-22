import fs from "node:fs/promises";
import path from "node:path";
import { Workbook, SpreadsheetFile } from "@oai/artifact-tool";

const folder = process.argv[2];
if (!folder) throw new Error("Pass the directory containing floorsheet_summary.json");
const data = JSON.parse(await fs.readFile(path.join(folder,"floorsheet_summary.json"),"utf8"));
const book = Workbook.create();
const headers = {
  "Stock by Date": ["Symbol", "Date", "Quantity", "Amount (NPR)"],
  "Buyer Brokers by Date": ["Buyer Broker", "Date", "Buy Quantity", "Buy Amount (NPR)"],
  "Seller Brokers by Date": ["Seller Broker", "Date", "Sell Quantity", "Sell Amount (NPR)"],
  "Broker Buy and Sell": ["Broker", "Date", "Buy Quantity", "Buy Amount (NPR)", "Sell Quantity", "Sell Amount (NPR)"],
};
for (const [name, rows] of Object.entries(data.sheets)) {
  const sheet = book.worksheets.add(name);
  const head = headers[name];
  sheet.getRangeByIndexes(0,0,1,head.length).values = [head];
  sheet.getRangeByIndexes(0,0,1,head.length).format.fill = "#173751";
  sheet.getRangeByIndexes(0,0,1,head.length).format.font.color = "#FFFFFF";
  sheet.getRangeByIndexes(0,0,1,head.length).format.font.bold = true;
  for (let offset=0; offset<rows.length; offset+=10000) {
    const batch=rows.slice(offset,offset+10000);
    sheet.getRangeByIndexes(offset+1,0,batch.length,head.length).values=batch;
  }
  sheet.getRange("A:A").format.columnWidth = 18;
  sheet.getRange("B:B").format.columnWidth = 15;
  sheet.getRange("C:F").format.columnWidth = 23;
  sheet.getRangeByIndexes(1,1,rows.length,1).setNumberFormat("yyyy-mm-dd");
  for (let c=2;c<head.length;c++)
    sheet.getRangeByIndexes(1,c,rows.length,1).setNumberFormat(c%2 ? "#,##0.00" : "#,##0");
  sheet.freezePanes.freezeRows(1);
  console.log(name, rows.length);
}
const audit=book.worksheets.add("Coverage");
const info=[
  ["Metric","Value"],
  ["First and last trade dates", data.start+" to "+data.end],
  ["Trading sessions", data.sessions],
  ["Validated contracts", data.contracts],
  ["Traded quantity", data.quantity],
  ["Trade turnover (NPR)", Number(data.amount)],
  ["Archive scope", "Validated multi-source NEPSE floorsheet archive"],
  ["Known difference","July 29, 2026. ShareHub has 48,072 trades and a separate market archive reports 48,077."],
  ["Exclusions","Two source records with zero prices were quarantined."],
  ["Trade CSV","The complete transaction rows are in the separate sorted yearly files."],
];
audit.getRangeByIndexes(0,0,info.length,2).values=info;
audit.getRange("A:A").format.columnWidth=29;
audit.getRange("B:B").format.columnWidth=100;
audit.getRange("A1:B1").format.fill="#173751";
audit.getRange("A1:B1").format.font.color="#FFFFFF";
audit.getRange("A1:B1").format.font.bold=true;
audit.getRange("B3:B5").setNumberFormat("#,##0");
audit.getRange("B6").setNumberFormat("#,##0.00");
book.recalculate();
const check=await book.inspect({kind:"table",range:"Stock by Date!A1:D4",include:"values",tableMaxRows:4,tableMaxCols:4});
console.log(check.ndjson);
const output=await SpreadsheetFile.exportXlsx(book);
await output.save(path.join(folder,"NEPSE_Floorsheet_Summaries.xlsx"));
