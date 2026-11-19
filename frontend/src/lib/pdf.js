// pdfjs is large, so it is loaded only when someone actually picks a PDF
// (dynamic import) instead of being part of every page load.
import { MAX_EXTRACT_CHARS } from "./limits";

export async function extractPdfText(file) {
  const [pdfjs, worker] = await Promise.all([
    import("pdfjs-dist"),
    import("pdfjs-dist/build/pdf.worker.mjs?url"),
  ]);
  pdfjs.GlobalWorkerOptions.workerSrc = worker.default;

  const pdf = await pdfjs.getDocument({ data: await file.arrayBuffer() })
    .promise;
  let text = "";
  for (let i = 1; i <= pdf.numPages; i++) {
    const page = await pdf.getPage(i);
    const content = await page.getTextContent();
    text += content.items.map((item) => item.str).join(" ") + "\n";
    // Stop reading huge documents once there is far more text than we can use.
    if (text.length > MAX_EXTRACT_CHARS) break;
  }
  return text;
}
