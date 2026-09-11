import fs from "node:fs/promises";
import { Workbook, SpreadsheetFile } from "@oai/artifact-tool";

const root = "C:/Users/TUF/Desktop/CobraQ";
const reviewCsvPath = `${root}/outputs/cobraq_teacher_review_60/CobraQ_Independent_Review_60.csv`;
const goldCsvPath = `${root}/research/datasets/retrieval_gold.csv`;
const outputDir = `${root}/outputs/cobraq_teacher_review_60`;
const outputPath = `${outputDir}/CobraQ_Independent_Review_60.xlsx`;

function parseCsv(text) {
  const rows = [];
  let row = [], cell = "", quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') { cell += '"'; i += 1; }
      else if (ch === '"') quoted = false;
      else cell += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") { row.push(cell); cell = ""; }
    else if (ch === "\n") { row.push(cell.replace(/\r$/, "")); rows.push(row); row = []; cell = ""; }
    else cell += ch;
  }
  if (cell.length || row.length) { row.push(cell); rows.push(row); }
  return rows;
}

function styleSheet(sheet, header, bodyRows, widths) {
  sheet.showGridLines = false;
  const lastCol = String.fromCharCode(64 + Math.min(widths.length, 26));
  const lastRow = bodyRows + 1;
  sheet.getRange(`A1:${lastCol}${lastRow}`).format = {
    font: { name: "Arial", size: 10, color: "#172033" },
    verticalAlignment: "center",
    wrapText: true,
  };
  sheet.getRange(`A1:${lastCol}1`).format = {
    fill: "#5B21B6",
    font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "bottom", style: "medium", color: "#3B0764" },
  };
  sheet.getRange(`A1:${lastCol}1`).format.rowHeight = 34;
  sheet.getRange(`A2:${lastCol}${lastRow}`).format.rowHeight = 58;
  sheet.freezePanes.freezeRows(1);
  widths.forEach((width, index) => {
    const col = index < 26 ? String.fromCharCode(65 + index) : `A${String.fromCharCode(65 + index - 26)}`;
    sheet.getRange(`${col}:${col}`).format.columnWidth = width;
  });
}

const reviewCsv = await fs.readFile(reviewCsvPath, "utf8");
const goldCsv = await fs.readFile(goldCsvPath, "utf8");
const workbook = await Workbook.fromCSV(reviewCsv, { sheetName: "Câu hỏi 60" });
const reviewSheet = workbook.worksheets.getItem("Câu hỏi 60");
styleSheet(reviewSheet, true, 60, [12,12,23,11,12,34,12,18,10,13,50,34,34,34,34,14,52,30,10,52,56,28,14,14,14,12,12,12,12,12,12,12,12,14,18,12,36,14]);
reviewSheet.getRange("A1:AL61").format.borders = { preset: "insideHorizontal", style: "thin", color: "#E5E7EB" };
reviewSheet.getRange("W2:AK61").format.fill = "#FFFDF4";

const goldRows = parseCsv(goldCsv);
const goldSheet = workbook.worksheets.add("Retrieval Gold");
goldSheet.getRangeByIndexes(0, 0, goldRows.length, goldRows[0].length).values = goldRows;
styleSheet(goldSheet, true, goldRows.length - 1, [12,54,11,12,34,12,18,10,10,30,60,60,26,14,24,50]);
goldSheet.getRange(`A1:P${goldRows.length}`).format.borders = { preset: "insideHorizontal", style: "thin", color: "#E5E7EB" };
goldSheet.getRange(`M2:P${goldRows.length}`).format.fill = "#FFFDF4";

const guide = workbook.worksheets.add("Hướng dẫn");
guide.showGridLines = false;
guide.getRange("A1:B9").values = [
  ["CobraQ · Hồ sơ duyệt độc lập", ""],
  ["Mục đích", "Kiểm tra lại 60 câu đã duyệt bằng một người chấm độc lập, không xem điểm 5/5 trước đó."],
  ["Nguồn câu hỏi", "AQG v2 train + validation; loại trừ toàn bộ test held-out 60 câu."],
  ["Phân bố", "60 câu / 17 bài / 42 trắc nghiệm + 18 tự luận / độ khó 23 mức 1, 19 mức 2, 18 mức 3."],
  ["Cách chấm", "Điền reviewer_id, review_date, các tiêu chí 1–5, factual_error_found, teacher_decision, editing_minutes và teacher_comment."],
  ["Tự luận", "Để trống unique_correct_answer và distractor_quality; đánh giá đáp án mẫu, căn cứ SGK và khả năng lập luận."],
  ["Cờ ưu tiên", "repeated_stem_pattern: khuôn câu dẫn lặp; essay_answer_placeholder: lời nhắc cần hoàn thiện đáp án/thang điểm."],
  ["Retrieval Gold", "Giáo viên điền relevant_chunk_ids bằng các chunk thực sự đủ bằng chứng, reviewer_id và đổi review_status thành teacher_approved."],
  ["Sau khi duyệt", "Không sửa các cột nội dung gốc. Nếu cần sửa, ghi quyết định/comment trước và tăng revision_version."],
];
guide.getRange("A1:B9").format = { font: { name: "Arial", size: 11, color: "#172033" }, wrapText: true, verticalAlignment: "center" };
guide.getRange("A1:B1").format = { fill: "#5B21B6", font: { name: "Arial", size: 13, bold: true, color: "#FFFFFF" } };
guide.getRange("A2:A9").format = { fill: "#EDE9FE", font: { name: "Arial", size: 10, bold: true, color: "#3B0764" } };
guide.getRange("A1:B9").format.borders = { preset: "all", style: "thin", color: "#D9D4E8" };
guide.getRange("A:A").format.columnWidth = 22;
guide.getRange("B:B").format.columnWidth = 105;
guide.getRange("A1:B1").format.rowHeight = 30;
guide.getRange("A2:B9").format.rowHeight = 44;

workbook.recalculate();
const preview = await workbook.render({ sheetName: "Câu hỏi 60", range: "A1:K8", scale: 1, format: "png" });
await fs.writeFile(`${outputDir}/_review_preview.png`, new Uint8Array(await preview.arrayBuffer()));
await fs.mkdir(outputDir, { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, reviewRows: 60, goldRows: goldRows.length - 1, preview: `${outputDir}/_review_preview.png` }));
