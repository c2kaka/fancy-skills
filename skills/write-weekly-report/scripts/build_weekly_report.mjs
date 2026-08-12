import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!key?.startsWith("--") || value === undefined) {
      throw new Error("参数必须使用 --input <json> --output <xlsx> [--preview <png>] 格式");
    }
    args[key.slice(2)] = value;
  }
  if (!args.input || !args.output) {
    throw new Error("缺少必需参数：--input 和 --output");
  }
  return args;
}

function decimalParts(value, label) {
  const text = String(value).trim();
  const match = text.match(/^(0|[1-9]\d*)(?:\.(\d+))?$/);
  if (!match) {
    throw new Error(`${label} 必须是非负十进制数，不能使用指数、单位或其他字符`);
  }
  const fraction = match[2] ?? "";
  return {
    numerator: BigInt(`${match[1]}${fraction}`),
    decimals: fraction.length,
  };
}

function pow10(exponent) {
  return 10n ** BigInt(exponent);
}

function toCommonScale(parts, decimals) {
  return parts.numerator * pow10(decimals - parts.decimals);
}

function allocateHours(totalHours, precision, tasks) {
  const total = decimalParts(totalHours, "总工时");
  const step = decimalParts(precision, "工时精度");
  if (step.numerator === 0n) {
    throw new Error("工时精度必须大于 0");
  }

  const hourDecimals = Math.max(total.decimals, step.decimals);
  const totalScaled = toCommonScale(total, hourDecimals);
  const stepScaled = toCommonScale(step, hourDecimals);
  if (totalScaled % stepScaled !== 0n) {
    throw new Error("总工时必须能够被工时精度整除");
  }

  const totalUnits = totalScaled / stepScaled;
  if (totalUnits > BigInt(Number.MAX_SAFE_INTEGER)) {
    throw new Error("总工时过大，无法安全分配");
  }

  const weightParts = tasks.map((task, index) => {
    const parsed = decimalParts(task.weight, `第 ${index + 1} 项权重`);
    if (parsed.numerator === 0n) {
      throw new Error(`第 ${index + 1} 项权重必须大于 0`);
    }
    return parsed;
  });
  const weightDecimals = Math.max(...weightParts.map((item) => item.decimals));
  const weights = weightParts.map((item) => toCommonScale(item, weightDecimals));
  const weightSum = weights.reduce((sum, weight) => sum + weight, 0n);

  const shares = weights.map((weight, index) => {
    const numerator = totalUnits * weight;
    return {
      index,
      weight,
      units: numerator / weightSum,
      remainder: numerator % weightSum,
    };
  });
  let remaining = totalUnits - shares.reduce((sum, item) => sum + item.units, 0n);
  const ranked = [...shares].sort((left, right) => {
    if (left.remainder !== right.remainder) {
      return left.remainder > right.remainder ? -1 : 1;
    }
    if (left.weight !== right.weight) {
      return left.weight > right.weight ? -1 : 1;
    }
    return left.index - right.index;
  });
  for (let index = 0; remaining > 0n; index += 1) {
    ranked[index].units += 1n;
    remaining -= 1n;
  }

  const scale = Number(pow10(hourDecimals));
  const stepNumber = Number(stepScaled) / scale;
  const hours = shares.map((item) => Number(item.units) * stepNumber);
  const allocated = hours.reduce((sum, value) => sum + value, 0);
  const totalNumber = Number(totalScaled) / scale;
  if (Math.abs(allocated - totalNumber) > 1 / scale / 10) {
    throw new Error("工时分配校验失败：分配合计与总工时不一致");
  }

  return {
    hours,
    totalHours: totalNumber,
    precision: stepNumber,
    decimals: step.decimals,
    zeroHourTasks: hours.filter((value) => value === 0).length,
  };
}

function validateInput(input) {
  if (!Array.isArray(input.tasks) || input.tasks.length === 0) {
    throw new Error("tasks 必须是非空数组");
  }
  for (const [index, task] of input.tasks.entries()) {
    for (const field of ["project", "title", "description", "weight"]) {
      if (task[field] === undefined || String(task[field]).trim() === "") {
        throw new Error(`第 ${index + 1} 项缺少 ${field}`);
      }
    }
  }
  for (const field of ["periodStart", "periodEnd", "author", "totalHours"]) {
    if (input[field] === undefined || String(input[field]).trim() === "") {
      throw new Error(`缺少 ${field}`);
    }
  }
}

function mergeContiguous(sheet, tasks, field, column, startRow, projectScoped = false) {
  let groupStart = 0;
  const flush = (endExclusive) => {
    if (endExclusive - groupStart > 1 && String(tasks[groupStart][field] ?? "").trim() !== "") {
      sheet.getRange(`${column}${startRow + groupStart}:${column}${startRow + endExclusive - 1}`).merge();
    }
  };

  for (let index = 1; index <= tasks.length; index += 1) {
    const previous = tasks[index - 1];
    const current = tasks[index];
    const boundary =
      index === tasks.length ||
      current[field] !== previous[field] ||
      (projectScoped && current.project !== previous.project);
    if (boundary) {
      flush(index);
      groupStart = index;
    }
  }
}

function numberFormatFor(decimals) {
  return decimals === 0 ? "0" : `0.${"0".repeat(decimals)}`;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const input = JSON.parse(await fs.readFile(args.input, "utf8"));
  validateInput(input);
  const allocation = allocateHours(input.totalHours, input.precision ?? "0.5", input.tasks);

  const workbook = Workbook.create();
  const sheet = workbook.worksheets.add("周报");
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);

  sheet.getRange("A1:E1").values = [["项目", "模块", "任务内容", "任务内容描述", "本周投入工作量"]];
  const rows = input.tasks.map((task, index) => [
    String(task.project),
    String(task.module ?? ""),
    String(task.title),
    String(task.description),
    allocation.hours[index],
  ]);
  const lastRow = rows.length + 1;
  sheet.getRange(`A2:E${lastRow}`).values = rows;

  mergeContiguous(sheet, input.tasks, "project", "A", 2);
  mergeContiguous(sheet, input.tasks, "module", "B", 2, true);

  const tableRange = sheet.getRange(`A1:E${lastRow}`);
  tableRange.format = {
    font: { name: "Microsoft YaHei", size: 11, color: "#1F2937" },
    verticalAlignment: "center",
    borders: { preset: "all", style: "thin", color: "#374151" },
  };
  sheet.getRange("A1:D1").format = {
    fill: "#95D5F3",
    font: { name: "Microsoft YaHei", size: 12, bold: true, color: "#164E73" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
  };
  sheet.getRange("E1").format = {
    fill: "#FDBA74",
    font: { name: "Microsoft YaHei", size: 12, bold: true, color: "#164E73" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
  };
  sheet.getRange(`A2:D${lastRow}`).format.wrapText = true;
  sheet.getRange(`A2:D${lastRow}`).format.horizontalAlignment = "left";
  sheet.getRange(`E2:E${lastRow}`).format = {
    horizontalAlignment: "right",
    verticalAlignment: "center",
    numberFormat: numberFormatFor(allocation.decimals),
  };

  sheet.getRange("A:A").format.columnWidthPx = 170;
  sheet.getRange("B:B").format.columnWidthPx = 150;
  sheet.getRange("C:C").format.columnWidthPx = 340;
  sheet.getRange("D:D").format.columnWidthPx = 560;
  sheet.getRange("E:E").format.columnWidthPx = 135;
  sheet.getRange("1:1").format.rowHeightPx = 36;
  input.tasks.forEach((task, index) => {
    const titleLines = Math.ceil(String(task.title).length / 24);
    const descriptionLines = Math.ceil(String(task.description).length / 44);
    const height = Math.min(180, Math.max(44, Math.max(titleLines, descriptionLines) * 23));
    sheet.getRange(`${index + 2}:${index + 2}`).format.rowHeightPx = height;
  });

  const inspected = await workbook.inspect({
    kind: "table",
    range: `周报!A1:E${lastRow}`,
    include: "values,formulas",
    tableMaxRows: Math.min(lastRow, 20),
    tableMaxCols: 5,
    maxChars: 5000,
  });
  const errors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 100 },
    summary: "weekly report formula error scan",
  });

  if (args.preview) {
    await fs.mkdir(path.dirname(args.preview), { recursive: true });
    const preview = await workbook.render({ sheetName: "周报", autoCrop: "all", scale: 1.3, format: "png" });
    await fs.writeFile(args.preview, new Uint8Array(await preview.arrayBuffer()));
  }

  await fs.mkdir(path.dirname(args.output), { recursive: true });
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(args.output);

  const formulaErrors = errors.ndjson.match(/#REF!|#DIV\/0!|#VALUE!|#NAME\?|#N\/A/g) ?? [];
  process.stdout.write(
    `${JSON.stringify({
      output: path.resolve(args.output),
      preview: args.preview ? path.resolve(args.preview) : null,
      taskCount: input.tasks.length,
      totalHours: allocation.totalHours,
      allocatedHours: allocation.hours.reduce((sum, value) => sum + value, 0),
      precision: allocation.precision,
      zeroHourTasks: allocation.zeroHourTasks,
      formulaErrors,
      inspect: inspected.ndjson,
    })}\n`,
  );
}

main().catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
