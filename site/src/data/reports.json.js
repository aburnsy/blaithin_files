// Data loader: reads all reports/<date>.jsonl files and emits a JSON array.
// Observable Framework runs data loaders with CWD = site/, so ../reports/ resolves
// to the repo's reports/ directory.
// If the directory is absent (no scrape runs yet) an empty array is emitted.
import {readFile, readdir} from "node:fs/promises";
import path from "node:path";

const REPORTS_DIR = "../reports";
const all = [];
try {
  const files = await readdir(REPORTS_DIR);
  for (const f of files.filter(x => x.endsWith(".jsonl"))) {
    const content = await readFile(path.join(REPORTS_DIR, f), "utf8");
    for (const line of content.trim().split("\n").filter(Boolean)) {
      all.push(JSON.parse(line));
    }
  }
} catch {
  // No reports yet — first run
}
process.stdout.write(JSON.stringify(all, null, 2));
