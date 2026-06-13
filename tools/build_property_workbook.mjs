import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";


const root = path.resolve(import.meta.dirname, "..");
const sourcePath = path.join(root, "data", "inbox", "property_prices.csv");
const outputPath = path.join(root, "outputs", "property_prices_demo.xlsx");
const previewDir = path.join(root, "outputs", "previews");
const csvText = await fs.readFile(sourcePath, "utf8");
const workbook = await Workbook.fromCSV(csvText, { sheetName: "Dados" });
const dataSheet = workbook.worksheets.getItem("Dados");
const dashboard = workbook.worksheets.add("Dashboard");
const rowCount = csvText.trim().split(/\r?\n/).length;

dataSheet.showGridLines = false;
dataSheet.freezePanes.freezeRows(1);
dataSheet.getRange(`A1:U${rowCount}`).format.font = { name: "Aptos", size: 10 };
dataSheet.getRange("A1:U1").format = {
  fill: "#0F766E",
  font: { bold: true, color: "#FFFFFF", size: 10 },
  wrapText: true,
  verticalAlignment: "center",
};
dataSheet.getRange("A1:U1").format.rowHeightPx = 34;
dataSheet.getRange(`B2:B${rowCount}`).format.numberFormat = "yyyy-mm-dd";
dataSheet.getRange(`G2:G${rowCount}`).format.numberFormat = "0.0";
dataSheet.getRange(`N2:O${rowCount}`).format.numberFormat = 'R$ #,##0';
dataSheet.getRange(`R2:S${rowCount}`).format.numberFormat = 'R$ #,##0.00';
dataSheet.getRange(`P2:Q${rowCount}`).format.numberFormat = "0.000000";
dataSheet.getRange("A:A").format.columnWidth = 13;
dataSheet.getRange("B:B").format.columnWidth = 13;
dataSheet.getRange("C:F").format.columnWidth = 17;
dataSheet.getRange("G:M").format.columnWidth = 12;
dataSheet.getRange("N:O").format.columnWidth = 16;
dataSheet.getRange("P:Q").format.columnWidth = 13;
dataSheet.getRange("R:S").format.columnWidth = 17;
dataSheet.getRange("T:U").format.columnWidth = 16;
const dataTable = dataSheet.tables.add(`A1:U${rowCount}`, true, "TabelaImoveis");
dataTable.style = "TableStyleMedium4";
dataTable.showFilterButton = true;

dashboard.showGridLines = false;
dashboard.getRange("A1:L2").merge();
dashboard.getRange("A1").values = [["PROPERTY PRICES | Painel Executivo"]];
dashboard.getRange("A1:L2").format = {
  fill: "#0F172A",
  font: { bold: true, color: "#FFFFFF", size: 22 },
  verticalAlignment: "center",
};
dashboard.getRange("A3:L3").merge();
dashboard.getRange("A3").values = [[
  "Base sintetica para demonstracao do Hermes Analytics | Atualizacao automatica via pasta monitorada",
]];
dashboard.getRange("A3:L3").format = {
  fill: "#E2E8F0",
  font: { color: "#334155", italic: true, size: 10 },
};

dashboard.getRange("A5:B5").merge();
dashboard.getRange("D5:E5").merge();
dashboard.getRange("G5:H5").merge();
dashboard.getRange("J5:K5").merge();
dashboard.getRange("A5").values = [["IMOVEIS"]];
dashboard.getRange("D5").values = [["PRECO MEDIANO"]];
dashboard.getRange("G5").values = [["PRECO MEDIO / M2"]];
dashboard.getRange("J5").values = [["AREA MEDIA"]];
dashboard.getRange("A6:B7").merge();
dashboard.getRange("D6:E7").merge();
dashboard.getRange("G6:H7").merge();
dashboard.getRange("J6:K7").merge();
dashboard.getRange("A6").formulas = [[`=COUNTA(Dados!A2:A${rowCount})`]];
dashboard.getRange("D6").formulas = [[`=MEDIAN(Dados!R2:R${rowCount})`]];
dashboard.getRange("G6").formulas = [[`=ROUND(AVERAGE(Dados!S2:S${rowCount}),0)`]];
dashboard.getRange("J6").formulas = [[`=AVERAGE(Dados!G2:G${rowCount})`]];
for (const range of ["A5:B7", "D5:E7", "G5:H7", "J5:K7"]) {
  dashboard.getRange(range).format = {
    fill: "#F8FAFC",
    borders: { preset: "outside", style: "thin", color: "#CBD5E1" },
  };
}
dashboard.getRange("A5:K5").format.font = { bold: true, color: "#64748B", size: 9 };
dashboard.getRange("A6:K7").format.font = { bold: true, color: "#0F172A", size: 18 };
dashboard.getRange("A6:K7").format.verticalAlignment = "center";
dashboard.getRange("D6").setNumberFormat('R$ #,##0');
dashboard.getRange("G6").setNumberFormat('R$ #,##0');
dashboard.getRange("J6").setNumberFormat('0.0 "m2"');

const neighborhoods = [
  "Moema", "Pinheiros", "Copacabana", "Botafogo", "Vila Mariana",
  "Barra da Tijuca", "Batel", "Tatuape", "Santana", "Cabral",
];
dashboard.getRange("A10:C10").values = [["Bairro", "Preco medio / m2", "Anuncios"]];
dashboard.getRange("A11:A20").values = neighborhoods.map((name) => [name]);
dashboard.getRange("B11").formulas = [[
  `=ROUND(AVERAGEIF(Dados!E$2:E$${rowCount},A11,Dados!S$2:S$${rowCount}),0)`,
]];
dashboard.getRange("B11:B20").fillDown();
dashboard.getRange("C11").formulas = [[`=COUNTIF(Dados!E$2:E$${rowCount},A11)`]];
dashboard.getRange("C11:C20").fillDown();
dashboard.getRange("A10:C20").format.borders = {
  preset: "all",
  style: "thin",
  color: "#E2E8F0",
};
dashboard.getRange("A10:C10").format = {
  fill: "#0F766E",
  font: { bold: true, color: "#FFFFFF" },
};
dashboard.getRange("B11:B20").setNumberFormat('R$ #,##0');

dashboard.getRange("E10:G10").values = [["Tipo", "Preco medio", "Anuncios"]];
dashboard.getRange("E11:E14").values = [
  ["Apartamento"], ["Casa"], ["Studio"], ["Cobertura"],
];
dashboard.getRange("F11").formulas = [[
  `=ROUND(AVERAGEIF(Dados!F$2:F$${rowCount},E11,Dados!R$2:R$${rowCount}),0)`,
]];
dashboard.getRange("F11:F14").fillDown();
dashboard.getRange("G11").formulas = [[`=COUNTIF(Dados!F$2:F$${rowCount},E11)`]];
dashboard.getRange("G11:G14").fillDown();
dashboard.getRange("E10:G14").format.borders = {
  preset: "all",
  style: "thin",
  color: "#E2E8F0",
};
dashboard.getRange("E10:G10").format = {
  fill: "#0369A1",
  font: { bold: true, color: "#FFFFFF" },
};
dashboard.getRange("F11:F14").setNumberFormat('R$ #,##0');

const neighborhoodChart = dashboard.charts.add("bar", dashboard.getRange("A10:B20"));
neighborhoodChart.title = "Preco medio por m2";
neighborhoodChart.hasLegend = false;
neighborhoodChart.xAxis = { numberFormatCode: 'R$ #,##0' };
neighborhoodChart.setPosition("I10", "P25");

const typeChart = dashboard.charts.add("bar", dashboard.getRange("E10:F14"));
typeChart.title = "Preco medio por tipo";
typeChart.hasLegend = false;
typeChart.yAxis = { numberFormatCode: 'R$ #,##0' };
typeChart.setPosition("A23", "H38");

dashboard.getRange("A40:L41").merge();
dashboard.getRange("A40").values = [[
  "Uso no Power BI: conecte a pasta outputs/powerbi ou importe fato_imoveis.parquet.",
]];
dashboard.getRange("A40:L41").format = {
  fill: "#FEF3C7",
  font: { bold: true, color: "#92400E", size: 11 },
  verticalAlignment: "center",
};
dashboard.getRange("A:L").format.columnWidth = 13;
dashboard.getRange("A:A").format.columnWidth = 18;
dashboard.getRange("B:B").format.columnWidth = 20;
dashboard.getRange("E:E").format.columnWidth = 18;
dashboard.getRange("F:F").format.columnWidth = 20;
dashboard.getRange("G:G").format.columnWidth = 14;

await fs.mkdir(path.dirname(outputPath), { recursive: true });
await fs.mkdir(previewDir, { recursive: true });
const dashboardPreview = await workbook.render({
  sheetName: "Dashboard",
  range: "A1:P42",
  scale: 1,
  format: "png",
});
await fs.writeFile(
  path.join(previewDir, "dashboard.png"),
  new Uint8Array(await dashboardPreview.arrayBuffer()),
);
const dataPreview = await workbook.render({
  sheetName: "Dados",
  range: "A1:U24",
  scale: 0.8,
  format: "png",
});
await fs.writeFile(
  path.join(previewDir, "dados.png"),
  new Uint8Array(await dataPreview.arrayBuffer()),
);

const inspection = await workbook.inspect({
  kind: "table",
  range: "Dashboard!A1:G20",
  include: "values,formulas",
  tableMaxRows: 20,
  tableMaxCols: 7,
});
console.log(inspection.ndjson);
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "formula error scan",
});
console.log(errors.ndjson);

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(outputPath);
