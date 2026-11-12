// Minimal RFC-4180 CSV reader (quotes, escaped quotes, CRLF). No dependencies.
import { readFileSync } from 'node:fs';
export function parseCSV(text) {
  const rows = []; let row = []; let field = ''; let i = 0; let q = false;
  while (i < text.length) {
    const c = text[i];
    if (q) {
      if (c === '"') { if (text[i + 1] === '"') { field += '"'; i += 2; continue; } q = false; i++; continue; }
      field += c; i++; continue;
    }
    if (c === '"') { q = true; i++; continue; }
    if (c === ',') { row.push(field); field = ''; i++; continue; }
    if (c === '\r') { i++; continue; }
    if (c === '\n') { row.push(field); rows.push(row); row = []; field = ''; i++; continue; }
    field += c; i++;
  }
  if (field.length || row.length) { row.push(field); rows.push(row); }
  const [head, ...body] = rows;
  return body.filter(r => r.some(x => x !== '')).map(r => Object.fromEntries(head.map((h, j) => [h, r[j] ?? ''])));
}
export function loadCSV(path) { return parseCSV(readFileSync(path, 'utf8')); }
