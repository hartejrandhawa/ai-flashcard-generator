// Cells starting with these characters are run as formulas by Excel and
// Sheets. Card text can originate from an uploaded document, so a leading
// apostrophe makes the spreadsheet treat the cell as plain text.
const FORMULA_START = /^[=+\-@\t\r]/;

function cell(value) {
  let text = String(value ?? "");
  if (FORMULA_START.test(text)) text = `'${text}`;
  return `"${text.replace(/"/g, '""')}"`;
}

// Two columns (front, back): the format Anki's "Import File" and most
// flashcard apps accept.
export function cardsToCsv(cards) {
  return (
    cards.map((c) => `${cell(c.front)},${cell(c.back)}`).join("\r\n") + "\r\n"
  );
}

export function downloadCsv(filename, csv) {
  const url = URL.createObjectURL(
    new Blob([csv], { type: "text/csv;charset=utf-8" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  // Revoking in the same tick can cancel the download in some browsers.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function safeFilename(name) {
  return (
    (name
      .replace(/[^\w\- ]+/g, "")
      .trim()
      .replace(/\s+/g, "-") || "deck") + ".csv"
  );
}
