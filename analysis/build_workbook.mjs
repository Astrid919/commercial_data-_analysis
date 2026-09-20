import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [resultsPath, monthlyCsvPath, outputPath, previewDir] = process.argv.slice(2);
if (!resultsPath || !monthlyCsvPath || !outputPath || !previewDir) {
  throw new Error("Usage: node build_workbook.mjs <results.json> <monthly.csv> <output.xlsx> <preview_dir>");
}

const results = JSON.parse(await fs.readFile(resultsPath, "utf8"));
const monthlyCsv = await fs.readFile(monthlyCsvPath, "utf8");
const monthlyBook = await Workbook.fromCSV(monthlyCsv, { sheetName: "Monthly_INN" });
const monthlyValues = monthlyBook.worksheets.getItem("Monthly_INN").getUsedRange().values;
for (let i = 1; i < monthlyValues.length; i++) monthlyValues[i][2] = Number(monthlyValues[i][2]);
const workbook = Workbook.create();
const executiveSheet = workbook.worksheets.add("Executive_Summary");
await fs.mkdir(path.dirname(outputPath), { recursive: true });
await fs.mkdir(previewDir, { recursive: true });

const C = {
  navy: "#15324B", blue: "#2F6B8A", teal: "#1C8A87", gold: "#D5A021",
  red: "#B54A4A", green: "#4F8A5B", gray: "#687780", light: "#EAF0F3",
  paleBlue: "#DCEAF1", paleGold: "#F7EBCB", paleRed: "#F5DEDE", white: "#FFFFFF",
};

function colName(n) {
  let s = "";
  while (n > 0) { n--; s = String.fromCharCode(65 + (n % 26)) + s; n = Math.floor(n / 26); }
  return s;
}

function title(sheet, text, subtitle, endCol = "N") {
  sheet.mergeCells(`A1:${endCol}2`);
  sheet.getRange("A1").values = [[text]];
  sheet.getRange(`A1:${endCol}2`).format = {
    fill: C.navy, font: { bold: true, color: C.white, size: 20 },
    verticalAlignment: "center", horizontalAlignment: "left",
  };
  sheet.mergeCells(`A3:${endCol}3`);
  sheet.getRange("A3").values = [[subtitle]];
  sheet.getRange(`A3:${endCol}3`).format = {
    fill: C.paleBlue, font: { color: C.navy, size: 10 }, verticalAlignment: "center",
  };
  sheet.getRange("1:3").format.rowHeight = 24;
  sheet.getRange("1:2").format.rowHeight = 30;
  sheet.showGridLines = false;
}

function header(range) {
  range.format = {
    fill: C.blue, font: { bold: true, color: C.white },
    verticalAlignment: "center", horizontalAlignment: "center", wrapText: true,
    borders: { preset: "outside", style: "thin", color: C.navy },
  };
  range.format.rowHeight = 30;
}

function body(range) {
  range.format = {
    font: { color: "#1F2933", size: 10 }, verticalAlignment: "center",
    borders: { insideHorizontal: { style: "thin", color: "#D9E1E5" } },
  };
}

function section(sheet, range, text) {
  sheet.mergeCells(range);
  const cell = range.split(":")[0];
  sheet.getRange(cell).values = [[text]];
  sheet.getRange(range).format = { fill: C.paleBlue, font: { bold: true, color: C.navy, size: 12 }, verticalAlignment: "center" };
}

function pct(v) { return v == null ? null : Number(v); }

function setWidths(sheet, widths) {
  for (const [col, px] of Object.entries(widths)) sheet.getRange(`${col}:${col}`).format.columnWidthPx = px;
}

function addTable(sheet, range, name) {
  const t = sheet.tables.add(range, true, name);
  t.style = "TableStyleMedium2";
  t.showBandedRows = true;
  return t;
}

// Monthly source sheet imported from CSV.
const monthly = workbook.worksheets.add("Monthly_INN");
monthly.getRangeByIndexes(0, 0, monthlyValues.length, monthlyValues[0].length).values = monthlyValues;
monthly.showGridLines = false;
monthly.freezePanes.freezeRows(1);
header(monthly.getRange("A1:C1"));
body(monthly.getRange("A2:C1201"));
monthly.getRange("A2:A1201").format.numberFormat = "@";
monthly.getRange("C2:C1201").format.numberFormat = "#,##0";
setWidths(monthly, { A: 215, B: 105, C: 125 });
addTable(monthly, "A1:C1201", "MonthlyINNTable");

// Data audit.
const audit = workbook.worksheets.add("Data_Audit");
title(audit, "Data audit and readiness", "Completeness, extraction quality and peer-market coverage", "F");
audit.getRange("A5:D5").values = [["Metric", "Value", "Unit", "Interpretation"]];
header(audit.getRange("A5:D5"));
const auditRows = results.audit.map(r => [r.metric, r.value, r.unit, r.note]);
audit.getRange(`A6:D${5 + auditRows.length}`).values = auditRows;
body(audit.getRange(`A6:D${5 + auditRows.length}`));
audit.getRange(`B6:B${5 + auditRows.length}`).format.numberFormat = "#,##0.0";
const zeroRow = 6 + results.audit.findIndex(r => r.metric === "Zero sales ratio");
const strengthRow = 6 + results.audit.findIndex(r => r.metric === "Strength extraction rate");
const packRow = 6 + results.audit.findIndex(r => r.metric === "Pack-size extraction rate");
for (const r of [zeroRow, strengthRow, packRow]) audit.getRange(`B${r}`).format.numberFormat = "0.0%";
section(audit, "A19:F19", "Critical interpretation");
audit.mergeCells("A20:F22");
audit.getRange("A20").values = [["The 20-INN file is a development sample, not a complete market census. Competitive share is therefore reported only for ATC4 or fallback ATC3 groups with at least two sampled INNs. Portfolio-share metrics are explicitly labeled as sample shares."]];
audit.getRange("A20:F22").format = { fill: C.paleGold, font: { color: C.navy, italic: true }, wrapText: true, verticalAlignment: "center" };
section(audit, "A24:F24", "Sources");
audit.getRange("A25:B27").values = results.sources.map(s => [s.name, s.url]);
body(audit.getRange("A25:B27"));
audit.getRange("B25:B27").format.font = { color: "#1155CC", underline: true };
setWidths(audit, { A: 220, B: 155, C: 145, D: 410, E: 40, F: 40 });

// Portfolio annual.
const annual = workbook.worksheets.add("Portfolio_Annual");
title(annual, "Portfolio performance", "Annual pack-equivalent units; not revenue", "H");
annual.getRange("A5:C5").values = [["Year", "Unit Sales", "YoY Growth"]];
header(annual.getRange("A5:C5"));
const annualRows = results.portfolio_annual.map((r, i) => [r.year, r.sales, i === 0 ? null : null]);
annual.getRange("A6:C10").values = annualRows;
annual.getRange("C7").formulas = [["=B7/B6-1"]];
annual.getRange("C7:C10").fillDown();
body(annual.getRange("A6:C10"));
annual.getRange("B6:B10").format.numberFormat = "#,##0";
annual.getRange("C6:C10").format.numberFormat = "0.0%";
setWidths(annual, { A: 95, B: 145, C: 125, D: 40, E: 120, F: 120, G: 120, H: 120 });
const annualChart = annual.charts.add("line", annual.getRange("A5:B10"));
annualChart.title = "Annual portfolio unit sales";
annualChart.hasLegend = false;
annualChart.xAxis = { axisType: "textAxis", textStyle: { fontSize: 10 } };
annualChart.yAxis = { numberFormatCode: "0.0,,\"M\"" };
annualChart.setPosition("E5", "H18");

// INN KPI.
const kpi = workbook.worksheets.add("INN_KPI");
title(kpi, "INN commercial KPI table", "Historical performance, sample-share momentum, forecast and action segment", "T");
const kHeaders = ["INN", "2019 Sales", "2022 Sales", "2023 Sales", "2023 YoY", "2019-23 CAGR", "2023 Portfolio Share", "Share Change (pp)", "Relative Growth", "CV", "Seasonality", "Lag-12 ACF", "SKUs", "Strengths", "Pack Sizes", "Forms", "2024 Forecast", "2024 Growth", "Action Segment", "Cluster"];
kpi.getRange("A5:T5").values = [kHeaders]; header(kpi.getRange("A5:T5"));
const kRows = results.inn_kpi.map(r => [r.INN, r.sales_2019, r.sales_2022, r.sales_2023, r.yoy_growth_2023, r.cagr_2019_2023, r.portfolio_share_2023, r.portfolio_share_change_2023, r.relative_growth_2023, r.cv_monthly, r.seasonality_strength, r.lag12_acf, r.sku_count, r.strength_count, r.pack_count, r.dosage_form_count, r.forecast_2024, null, r.action_segment, r.cluster_label]);
kpi.getRange("A6:T25").values = kRows;
kpi.getRange("R6").formulas = [["=Q6/D6-1"]]; kpi.getRange("R6:R25").fillDown();
body(kpi.getRange("A6:T25"));
kpi.freezePanes.freezeRows(5); kpi.freezePanes.freezeColumns(1);
kpi.getRange("B6:D25").format.numberFormat = "#,##0";
kpi.getRange("E6:I25").format.numberFormat = "0.0%";
kpi.getRange("J6:L25").format.numberFormat = "0.00";
kpi.getRange("M6:P25").format.numberFormat = "#,##0";
kpi.getRange("Q6:Q25").format.numberFormat = "#,##0";
kpi.getRange("R6:R25").format.numberFormat = "0.0%";
kpi.getRange("E6:I25").conditionalFormats.add("colorScale", { thresholds: ["min", "50%", "max"], colors: [C.red, "#FFF4D6", C.green] });
kpi.getRange("R6:R25").conditionalFormats.add("colorScale", { thresholds: ["min", "50%", "max"], colors: [C.red, "#FFF4D6", C.green] });
kpi.getRange("S6:S25").conditionalFormats.add("containsText", { text: "At Risk", format: { fill: C.paleRed, font: { color: C.red, bold: true } } });
kpi.getRange("S6:S25").conditionalFormats.add("containsText", { text: "Growth Leader", format: { fill: "#DCECDD", font: { color: C.green, bold: true } } });
kpi.getRange("S6:S25").conditionalFormats.add("containsText", { text: "Emerging", format: { fill: "#D9EFEE", font: { color: C.teal, bold: true } } });
setWidths(kpi, { A: 230, B: 105, C: 105, D: 105, E: 90, F: 90, G: 105, H: 105, I: 95, J: 70, K: 85, L: 80, M: 65, N: 75, O: 75, P: 65, Q: 115, R: 90, S: 150, T: 145 });
addTable(kpi, "A5:T25", "INNKPITable");

// Peer markets.
const peers = workbook.worksheets.add("Market_Peers");
title(peers, "Sampled competitive dynamics", "ATC4 where possible; ATC3 fallback; groups require at least two sampled INNs", "O");
const pHeaders = ["Market Level", "Market", "Peer INNs", "INN", "2022 Sales", "2023 Sales", "Market Growth", "2022 Share", "2023 Share", "Share Change (pp)", "Product Growth", "Relative Growth", "Market Expansion Effect", "Share Effect", "2023 HHI"];
peers.getRange("A5:O5").values = [pHeaders]; header(peers.getRange("A5:O5"));
const pRows = results.peer_analysis.map(r => [r.market_level, r.market_name, r.peer_INN_count, r.INN, r.sales_2022, r.sales_2023, r.market_growth_2023, r.share_2022, r.share_2023, r.share_change_pp, r.product_growth_2023, r.relative_growth_2023, r.market_expansion_effect, r.share_effect, r.HHI_2023]);
peers.getRange(`A6:O${5+pRows.length}`).values = pRows; body(peers.getRange(`A6:O${5+pRows.length}`));
peers.freezePanes.freezeRows(5); peers.freezePanes.freezeColumns(2);
peers.getRange(`E6:F${5+pRows.length}`).format.numberFormat = "#,##0";
peers.getRange(`G6:L${5+pRows.length}`).format.numberFormat = "0.0%";
peers.getRange(`M6:N${5+pRows.length}`).format.numberFormat = "#,##0";
peers.getRange(`O6:O${5+pRows.length}`).format.numberFormat = "0.000";
peers.getRange(`J6:J${5+pRows.length}`).conditionalFormats.add("colorScale", { thresholds: ["min", "50%", "max"], colors: [C.red, "#FFF4D6", C.green] });
setWidths(peers, { A: 90, B: 350, C: 75, D: 205, E: 105, F: 105, G: 95, H: 85, I: 85, J: 105, K: 95, L: 95, M: 125, N: 115, O: 80 });
addTable(peers, `A5:O${5+pRows.length}`, "PeerMarketTable");

// Segmentation.
const seg = workbook.worksheets.add("Segmentation");
title(seg, "Portfolio segmentation", "K-means on standardized commercial, demand and complexity features", "L");
seg.getRange("A5:H5").values = [["Cluster", "Archetype", "INNs", "2023 Sales", "Avg 2023 Growth", "Avg Share Change", "Avg 2024 Forecast Growth", "Avg CV"]]; header(seg.getRange("A5:H5"));
const sRows = results.cluster_summary.map(r => [r.cluster_id, r.cluster_label, r.INN_count, r.sales_2023, r.avg_yoy_growth, r.avg_share_change, r.avg_forecast_growth, r.avg_cv]);
seg.getRange(`A6:H${5+sRows.length}`).values = sRows; body(seg.getRange(`A6:H${5+sRows.length}`));
seg.getRange(`D6:D${5+sRows.length}`).format.numberFormat = "#,##0"; seg.getRange(`E6:G${5+sRows.length}`).format.numberFormat = "0.0%"; seg.getRange(`H6:H${5+sRows.length}`).format.numberFormat = "0.00";
section(seg, "A12:D12", "Cluster validation");
seg.getRange("A13:C13").values = [["K", "Silhouette", "Within-cluster SS"]]; header(seg.getRange("A13:C13"));
const sv = results.cluster_validation.map(r => [r.k, r.silhouette, r.WSS]); seg.getRange(`A14:C${13+sv.length}`).values = sv; body(seg.getRange(`A14:C${13+sv.length}`));
seg.getRange(`B14:B${13+sv.length}`).format.numberFormat = "0.000"; seg.getRange(`C14:C${13+sv.length}`).format.numberFormat = "0.0";
section(seg, "F12:L12", "Interpretation note");
seg.mergeCells("F13:L16"); seg.getRange("F13").values = [["Clusters are descriptive archetypes, not recommendations by themselves. Forward-looking action segments use transparent rules combining 2023 sample-share momentum, current scale and the 2024 forecast."]]; seg.getRange("F13:L16").format = { fill: C.paleGold, wrapText: true, verticalAlignment: "center", font: { color: C.navy } };
setWidths(seg, { A: 75, B: 190, C: 75, D: 125, E: 110, F: 110, G: 130, H: 90, I: 80, J: 80, K: 80, L: 80 });

// Classification results.
const ml = workbook.worksheets.add("ML_Results");
title(ml, "Future share-winner model", "Six-month-ahead top-quartile portfolio share gain; temporal validation only", "N");
ml.getRange("A5:L5").values = [["Model", "Parameters", "Val ROC-AUC", "Val PR-AUC", "Val P@20", "Val Lift@20", "Test ROC-AUC", "Test PR-AUC", "Test Precision", "Test Recall", "Test P@20", "Test Lift@20"]]; header(ml.getRange("A5:L5"));
const mRows = results.classification_results.map(r => [r.model, r.parameters, r.validation_roc_auc, r.validation_pr_auc, r.validation_precision_top20, r.validation_lift_top20, r.test_roc_auc, r.test_pr_auc, r.test_precision, r.test_recall, r.test_precision_top20, r.test_lift_top20]);
ml.getRange(`A6:L${5+mRows.length}`).values = mRows; body(ml.getRange(`A6:L${5+mRows.length}`));
ml.getRange(`C6:E${5+mRows.length}`).format.numberFormat = "0.0%"; ml.getRange(`F6:F${5+mRows.length}`).format.numberFormat = "0.00x"; ml.getRange(`G6:K${5+mRows.length}`).format.numberFormat = "0.0%"; ml.getRange(`L6:L${5+mRows.length}`).format.numberFormat = "0.00x";
section(ml, "A12:F12", "Out-of-time permutation importance");
ml.getRange("A13:B13").values = [["Feature", "PR-AUC Drop"]]; header(ml.getRange("A13:B13"));
const imp = results.classification_importance.map(r => [r.feature, r.pr_auc_drop]); ml.getRange(`A14:B${13+imp.length}`).values = imp; body(ml.getRange(`A14:B${13+imp.length}`)); ml.getRange(`B14:B${13+imp.length}`).format.numberFormat = "0.000";
section(ml, "H12:N12", "Selection discipline"); ml.mergeCells("H13:N17"); ml.getRange("H13").values = [[`Selected on 2022 validation only: ${results.metadata.selected_classification_model}. Test results are reported once, without re-selecting the winner. The test-period lift at top 20% measures how much more concentrated true future winners are in the review shortlist than in the 25% base rate.`]]; ml.getRange("H13:N17").format = { fill: C.paleBlue, wrapText: true, verticalAlignment: "center", font: { color: C.navy } };
setWidths(ml, { A: 145, B: 260, C: 95, D: 95, E: 85, F: 90, G: 95, H: 95, I: 95, J: 85, K: 85, L: 90, M: 80, N: 80 });

// Forecast results.
const fc = workbook.worksheets.add("Forecast_Results");
title(fc, "Demand forecasting", "2022 validation selects the production model; 2023 remains a final holdout", "N");
fc.getRange("A5:K5").values = [["Model", "Val WAPE", "Val MAE", "Val RMSE", "Val MASE", "Val Bias", "Test WAPE", "Test MAE", "Test RMSE", "Test MASE", "Test Bias"]]; header(fc.getRange("A5:K5"));
const fRows = results.forecast_results.map(r => [r.model, r.validation_WAPE, r.validation_MAE, r.validation_RMSE, r.validation_MASE, r.validation_Bias, r.test_WAPE, r.test_MAE, r.test_RMSE, r.test_MASE, r.test_Bias]);
fc.getRange(`A6:K${5+fRows.length}`).values = fRows; body(fc.getRange(`A6:K${5+fRows.length}`));
for (const c of ["B", "F", "G", "K"]) fc.getRange(`${c}6:${c}${5+fRows.length}`).format.numberFormat = "0.0%";
for (const c of ["C", "D", "H", "I"]) fc.getRange(`${c}6:${c}${5+fRows.length}`).format.numberFormat = "#,##0";
for (const c of ["E", "J"]) fc.getRange(`${c}6:${c}${5+fRows.length}`).format.numberFormat = "0.00";
section(fc, "A13:F13", "2023 portfolio monthly actual vs selected forecast");
const fp = results.forecast_2023_portfolio; const selF = results.metadata.selected_forecast_model;
fc.getRange("A14:D14").values = [["Month", "Actual", selF, "Seasonal Naive"]]; header(fc.getRange("A14:D14"));
const monthRows = fp.month.map((m, i) => [m, fp.actual[i], fp[selF][i], fp["Seasonal Naive"][i]]); fc.getRange("A15:D26").values = monthRows; body(fc.getRange("A15:D26")); fc.getRange("B15:D26").format.numberFormat = "#,##0";
const fchart = fc.charts.add("line", fc.getRange("A14:D26")); fchart.title = "2023 portfolio demand"; fchart.hasLegend = true; fchart.xAxis = { axisType: "textAxis" }; fchart.yAxis = { numberFormatCode: "0.0,,\"M\"" }; fchart.setPosition("F13", "N28");
setWidths(fc, { A: 200, B: 100, C: 110, D: 110, E: 80, F: 95, G: 100, H: 110, I: 110, J: 80, K: 95, L: 80, M: 80, N: 80 });

// 2024 forecast.
const f24 = workbook.worksheets.add("Forecast_2024");
title(f24, "2024 demand outlook and commercial actions", `Production model: ${results.metadata.selected_forecast_model}; empirical 80% ranges`, "K");
f24.getRange("A5:H5").values = [["INN", "2023 Actual", "2024 Forecast", "Forecast Growth", "Lower 80%", "Upper 80%", "Action Segment", "Cluster"]]; header(f24.getRange("A5:H5"));
const sortedK = [...results.inn_kpi].sort((a,b) => b.forecast_growth_2024-a.forecast_growth_2024);
const f24Rows = sortedK.map(r => [r.INN, r.sales_2023, r.forecast_2024, null, r.forecast_2024_lower80, r.forecast_2024_upper80, r.action_segment, r.cluster_label]);
f24.getRange("A6:H25").values = f24Rows; f24.getRange("D6").formulas = [["=C6/B6-1"]]; f24.getRange("D6:D25").fillDown(); body(f24.getRange("A6:H25"));
f24.getRange("B6:C25").format.numberFormat = "#,##0"; f24.getRange("D6:D25").format.numberFormat = "0.0%"; f24.getRange("E6:F25").format.numberFormat = "#,##0";
f24.getRange("D6:D25").conditionalFormats.add("colorScale", { thresholds: ["min", "50%", "max"], colors: [C.red, "#FFF4D6", C.green] });
f24.freezePanes.freezeRows(5); setWidths(f24, { A: 225, B: 110, C: 115, D: 100, E: 110, F: 110, G: 165, H: 150, I: 40, J: 110, K: 110 });
addTable(f24, "A5:H25", "Forecast2024Table");
const topChart = f24.charts.add("bar", { chartType: "bar", title: "Highest 2024 forecast growth", hasLegend: false });
const topSeries = topChart.series.add("Forecast Growth");
topSeries.categoryFormula = "'Forecast_2024'!$A$6:$A$15";
topSeries.formula = "'Forecast_2024'!$D$6:$D$15";
topSeries.fill = C.teal;
topChart.xAxis = { axisType: "textAxis", textStyle: { fontSize: 9 } };
topChart.yAxis = { numberFormatCode: "0%" };
topChart.setPosition("J5", "Q22");

// Methodology.
const meth = workbook.worksheets.add("Methodology");
title(meth, "Methodology, definitions and limitations", "Designed for auditability and interview discussion", "J");
section(meth, "A5:J5", "Analysis flow");
meth.mergeCells("A6:J8"); meth.getRange("A6").values = [["Raw SKU sales → long format → regex product attributes → INN/month aggregation → peer-market analytics → portfolio segmentation → six-month share-winner model → 12-month demand forecast → rule-based commercial actions"]]; meth.getRange("A6:J8").format = { fill: C.paleBlue, wrapText: true, verticalAlignment: "center", horizontalAlignment: "center", font: { bold: true, color: C.navy } };
section(meth, "A10:J10", "Key definitions");
const defs = [
  ["Market share", "INN sales divided by sampled peer-market sales; only reported when the peer group contains at least two sampled INNs."],
  ["Portfolio share", "INN sales divided by total sales across the 20-INN development sample."],
  ["Share effect", "Actual 2023 sales minus 2023 market sales multiplied by 2022 share."],
  ["Future share winner", "Top quartile of six-month-ahead portfolio share change within each anchor month."],
  ["WAPE", "Sum of absolute forecast errors divided by sum of actual demand."],
  ["Bias", "Sum of forecast minus actual divided by sum of actual; positive means over-forecast."],
  ["Lift@20%", "Precision among the top 20% model-ranked records divided by the overall winner rate."],
];
meth.getRange("A11:B17").values = defs; body(meth.getRange("A11:B17")); meth.getRange("A11:A17").format.font = { bold: true, color: C.navy };
section(meth, "A19:J19", "Model governance and limitations");
const notes = results.methodology_notes.map((x, i) => [`${i+1}.`, x]); meth.getRange(`A20:B${19+notes.length}`).values = notes; body(meth.getRange(`A20:B${19+notes.length}`)); meth.getRange(`B20:B${19+notes.length}`).format.wrapText = true;
section(meth, "A29:J29", "What this case does not support");
meth.mergeCells("A30:J33"); meth.getRange("A30").values = [["No price, revenue, rebate, payer, patient, HCP, promotion-spend or manufacturing-cost fields are available. The analysis therefore supports unit-demand planning and sampled portfolio prioritization—not pricing elasticity, promotion ROI, targeting, market access conclusions, profitability decisions or product discontinuation."]]; meth.getRange("A30:J33").format = { fill: C.paleRed, wrapText: true, verticalAlignment: "center", font: { color: C.red, bold: true } };
setWidths(meth, { A: 145, B: 690, C: 30, D: 30, E: 30, F: 30, G: 30, H: 30, I: 30, J: 30 });

// Executive summary last so formulas can point to final sheets.
const exec = executiveSheet;
title(exec, "AI-Driven Pharmaceutical Portfolio Analytics", "Market performance, competitive dynamics and demand forecasting | Teva 20-INN development sample", "N");
const cards = [
  {valueRange:"A5:C7", labelRange:"A8:C8", label:"2023 portfolio units", formula:"='Portfolio_Annual'!B10", fmt:"#,##0,,\"M\""},
  {valueRange:"D5:F7", labelRange:"D8:F8", label:"2023 growth", formula:"='Portfolio_Annual'!C10", fmt:"0.0%"},
  {valueRange:"G5:I7", labelRange:"G8:I8", label:"Selected model WAPE", value: results.forecast_results.find(r=>r.model===results.metadata.selected_forecast_model).test_WAPE, fmt:"0.0%"},
  {valueRange:"J5:L7", labelRange:"J8:L8", label:"Classifier Lift@20", value: results.classification_results.find(r=>r.model===results.metadata.selected_classification_model).test_lift_top20, fmt:"0.00\"x\""},
];
for (const c of cards) {
  exec.mergeCells(c.valueRange); const anchor=c.valueRange.split(":")[0];
  if (c.formula) exec.getRange(anchor).formulas=[[c.formula]]; else exec.getRange(anchor).values=[[c.value]];
  exec.getRange(c.valueRange).format={fill:C.light,font:{bold:true,color:C.navy,size:18},horizontalAlignment:"center",verticalAlignment:"center",borders:{preset:"outside",style:"thin",color:C.blue}};
  exec.getRange(anchor).format.numberFormat=c.fmt;
  exec.mergeCells(c.labelRange); const labelAnchor=c.labelRange.split(":")[0];
  exec.getRange(labelAnchor).values=[[c.label]];
  exec.getRange(c.labelRange).format={fill:C.blue,font:{bold:true,color:C.white,size:10},horizontalAlignment:"center",verticalAlignment:"center"};
}
section(exec,"A11:G11","Evidence-backed findings");
const topGrowth = sortedK.slice(0,3).map(r=>r.INN).join(", ");
const selectedFc = results.forecast_results.find(r=>r.model===results.metadata.selected_forecast_model);
const selectedCl = results.classification_results.find(r=>r.model===results.metadata.selected_classification_model);
const f2024 = results.inn_kpi.reduce((s,r)=>s+r.forecast_2024,0), s2023=results.inn_kpi.reduce((s,r)=>s+r.sales_2023,0);
const findings = [
  ["Portfolio reset", `Sales fell from 157.3M in 2021 to 122.2M in 2023; 2023 was down ${(results.portfolio_annual[4].sales/results.portfolio_annual[3].sales-1).toLocaleString(undefined,{style:"percent",maximumFractionDigits:1})} YoY.`],
  ["2024 base case", `${results.metadata.selected_forecast_model} projects ${fmtNum(f2024)} units (${(f2024/s2023-1).toLocaleString(undefined,{style:"percent",maximumFractionDigits:1})} vs 2023).`],
  ["Growth pockets", `${topGrowth} have the strongest 2024 percentage growth outlook.`],
  ["Early warning", `${results.metadata.selected_classification_model} achieved ${(selectedCl.test_precision_top20).toLocaleString(undefined,{style:"percent",maximumFractionDigits:1})} Precision@20 and ${selectedCl.test_lift_top20.toFixed(2)}x lift on the 2023 holdout.`],
  ["Key signal", `${results.classification_importance[0].feature} produced the largest out-of-time PR-AUC drop in permutation testing.`],
];
exec.getRange("A12:B16").values=findings; exec.getRange("B12:G16").merge(true); body(exec.getRange("A12:G16")); exec.getRange("A12:A16").format={fill:C.paleBlue,font:{bold:true,color:C.navy},verticalAlignment:"center"}; exec.getRange("B12:G16").format.wrapText=true;
section(exec,"I11:N11","Commercial actions");
const actions = [
  ["1", "Invest", "Prioritize ibuprofen; validate pregabalin and acetylcysteine uptake drivers before incremental support."],
  ["2", "Defend", "Protect high-volume aspirin, paracetamol and diclofenac where share momentum is negative."],
  ["3", "Plan supply", "Use the validated ETS base case, monitor its under-forecast bias, and test the ensemble prospectively."],
  ["4", "Monitor", "Refresh monthly share momentum, forecast error and action segments; investigate stock-out-like zero gaps."],
];
exec.getRange("I12:K15").values=actions; exec.getRange("K12:N15").merge(true); body(exec.getRange("I12:N15")); exec.getRange("I12:I15").format={fill:C.gold,font:{bold:true,color:C.navy},horizontalAlignment:"center"}; exec.getRange("J12:J15").format.font={bold:true,color:C.navy}; exec.getRange("K12:N15").format.wrapText=true;
section(exec,"A19:G19","Portfolio sales trend");
const exChart1=exec.charts.add("line", annual.getRange("A5:B10")); exChart1.title="2019-2023 portfolio unit sales"; exChart1.hasLegend=false; exChart1.xAxis={axisType:"textAxis"}; exChart1.yAxis={numberFormatCode:"0.0,,\"M\""}; exChart1.setPosition("A20","G35");
section(exec,"H19:N19","Forecast model test WAPE");
const exChart2=exec.charts.add("bar", { chartType:"bar", title:"2023 holdout WAPE", hasLegend:false });
const wapeSeries=exChart2.series.add("Test WAPE");
wapeSeries.categoryFormula=`'Forecast_Results'!$A$6:$A$${5+fRows.length}`;
wapeSeries.formula=`'Forecast_Results'!$G$6:$G$${5+fRows.length}`;
wapeSeries.fill=C.blue;
exChart2.xAxis={axisType:"textAxis",textStyle:{fontSize:9}}; exChart2.yAxis={numberFormatCode:"0%"}; exChart2.setPosition("H20","N35");
exec.mergeCells("A37:N38"); exec.getRange("A37").values=[["Decision caveat: market-share results are sample-relative. Do not infer external market size, revenue, profitability, pricing response or causal promotion impact from this dataset."]]; exec.getRange("A37:N38").format={fill:C.paleGold,font:{bold:true,color:C.navy},wrapText:true,verticalAlignment:"center"};
setWidths(exec,{A:95,B:95,C:95,D:95,E:95,F:95,G:95,H:95,I:80,J:95,K:95,L:95,M:95,N:95});

function fmtNum(v) {
  if (Math.abs(v)>=1e9) return `${(v/1e9).toFixed(1)}B`;
  if (Math.abs(v)>=1e6) return `${(v/1e6).toFixed(1)}M`;
  if (Math.abs(v)>=1e3) return `${(v/1e3).toFixed(1)}K`;
  return v.toFixed(0);
}

// Compact verification.
const inspect = await workbook.inspect({ kind: "sheet,table", include: "id,name", maxChars: 6000 });
console.log(inspect.ndjson);
const key = await workbook.inspect({ kind: "table", range: "Executive_Summary!A1:N18", include: "values,formulas", tableMaxRows: 18, tableMaxCols: 14, maxChars: 9000 });
console.log(key.ndjson);
const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 300 }, summary: "final formula error scan" });
console.log(errors.ndjson);

const previews = {
  Executive_Summary: "A1:N38", Data_Audit: "A1:F27", Portfolio_Annual: "A1:H18",
  INN_KPI: "A1:T25", Market_Peers: `A1:O${Math.min(5+pRows.length,25)}`, Segmentation: "A1:L17",
  ML_Results: "A1:N28", Forecast_Results: "A1:N28", Forecast_2024: "A1:Q25",
  Monthly_INN: "A1:C28", Methodology: "A1:J33",
};
for (const [sheetName, range] of Object.entries(previews)) {
  const blob = await workbook.render({ sheetName, range, scale: 1.2, format: "png" });
  await fs.writeFile(path.join(previewDir, `${sheetName}.png`), new Uint8Array(await blob.arrayBuffer()));
}
const out = await SpreadsheetFile.exportXlsx(workbook);
await out.save(outputPath);
console.log(JSON.stringify({ outputPath, previews: Object.keys(previews) }));
