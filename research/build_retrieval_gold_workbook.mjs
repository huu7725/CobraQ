import fs from "node:fs/promises";
import { Workbook, SpreadsheetFile } from "@oai/artifact-tool";

const root = "C:/Users/TUF/Desktop/CobraQ";
const inputPath = `${root}/research/datasets/retrieval_gold.csv`;
const outputDir = `${root}/outputs/retrieval_gold_review`;
const outputPath = `${outputDir}/Retrieval_Gold_Teacher_Review.xlsx`;

const csv = await fs.readFile(inputPath, "utf8");
const workbook = await Workbook.fromCSV(csv, { sheetName: "Retrieval Gold" });
const sheet = workbook.worksheets.getItem("Retrieval Gold");
const used = sheet.getUsedRange();
const rows = 52;
sheet.showGridLines = false;
used.format = {
  font: { name: "Arial", size: 10, color: "#172033" },
  verticalAlignment: "center",
  wrapText: true,
};
sheet.getRange("A1:P1").format = {
  fill: "#5B21B6",
  font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
  verticalAlignment: "center",
  wrapText: true,
};
sheet.getRange("A1:P1").format.rowHeight = 36;
sheet.getRange("A2:P52").format.rowHeight = 64;
sheet.getRange("A1:P52").format.borders = {
  preset: "insideHorizontal",
  style: "thin",
  color: "#E5E7EB",
};
sheet.getRange("M2:P52").format.fill = "#FFFDF4";
sheet.getRange("A:A").format.columnWidth = 12;
sheet.getRange("B:B").format.columnWidth = 58;
sheet.getRange("C:C").format.columnWidth = 12;
sheet.getRange("D:D").format.columnWidth = 12;
sheet.getRange("E:E").format.columnWidth = 34;
sheet.getRange("F:F").format.columnWidth = 12;
sheet.getRange("G:G").format.columnWidth = 18;
sheet.getRange("H:I").format.columnWidth = 11;
sheet.getRange("J:J").format.columnWidth = 30;
sheet.getRange("K:L").format.columnWidth = 60;
sheet.getRange("M:M").format.columnWidth = 28;
sheet.getRange("N:N").format.columnWidth = 15;
sheet.getRange("O:O").format.columnWidth = 25;
sheet.getRange("P:P").format.columnWidth = 50;
sheet.freezePanes.freezeRows(1);

const guide = workbook.worksheets.add("Hướng dẫn");
guide.showGridLines = false;
guide.getRange("A1:B10").values = [
  ["Retrieval Gold · Giáo viên xác nhận", ""],
  ["Mục tiêu", "Xác định chunk SGK thực sự đủ bằng chứng cho từng truy vấn, để đánh giá Recall@5, MRR và nDCG@5."],
  ["Số truy vấn", "51 truy vấn, 3 truy vấn cho mỗi bài trong 17 bài Lịch sử 12."],
  ["candidate_chunk_id", "Gợi ý từ citation của câu đã duyệt. Đây chưa phải nhãn vàng và có thể sai hoặc chưa đủ."],
  ["relevant_chunk_ids", "Giáo viên điền tất cả chunk thực sự đủ bằng chứng, ngăn cách bằng dấu chấm phẩy (;)."],
  ["reviewer_id", "Mã giáo viên xác nhận."],
  ["review_status", "Để pending_teacher_review trong lúc chấm; đổi thành teacher_approved sau khi hoàn tất."],
  ["comment", "Ghi lý do nếu candidate không đủ, nếu có nhiều chunk cùng cần thiết hoặc nếu truy vấn mơ hồ."],
  ["Không làm", "Không chọn chunk chỉ vì hệ thống xếp hạng cao; không suy ra relevance từ citation đầu ra của model."],
  ["Sau khi duyệt", "Chạy evaluate_retrieval.py riêng ở keyword, dense và hybrid; giữ nguyên file gold và lưu báo cáo theo mode."],
];
guide.getRange("A1:B10").format = {
  font: { name: "Arial", size: 11, color: "#172033" },
  verticalAlignment: "center",
  wrapText: true,
};
guide.getRange("A1:B1").format = {
  fill: "#5B21B6",
  font: { name: "Arial", size: 13, bold: true, color: "#FFFFFF" },
};
guide.getRange("A2:A10").format = {
  fill: "#EDE9FE",
  font: { name: "Arial", size: 10, bold: true, color: "#3B0764" },
};
guide.getRange("A1:B10").format.borders = {
  preset: "all",
  style: "thin",
  color: "#D9D4E8",
};
guide.getRange("A:A").format.columnWidth = 23;
guide.getRange("B:B").format.columnWidth = 105;
guide.getRange("A1:B1").format.rowHeight = 30;
guide.getRange("A2:B10").format.rowHeight = 46;

workbook.recalculate();
const preview = await workbook.render({
  sheetName: "Retrieval Gold",
  range: "A1:P6",
  scale: 1,
  format: "png",
});
await fs.mkdir(outputDir, { recursive: true });
await fs.writeFile(`${outputDir}/_retrieval_gold_preview.png`, new Uint8Array(await preview.arrayBuffer()));
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, rows: rows - 1, preview: `${outputDir}/_retrieval_gold_preview.png` }));
