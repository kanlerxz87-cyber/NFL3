# Immutable price snapshots (append-only)

This directory is the price-snapshot store required by the project brief. It holds one JSONL file per
capture run, named `YYYY-MM-DDTHHMMSSZ-<source_id>.jsonl`. Each line is one row validating against
`../schema.json` (`price_snapshot_row`).

Rules (from [`../PRICE_DATA_POLICY.md`](../PRICE_DATA_POLICY.md)):

1. **Append-only.** A corrected quote is a new row with `supersedes` pointing at the old row. Files
   are never rewritten; `capture_hash` (SHA-256 of the raw captured payload) is retained beside the
   row so any capture can be replayed byte for byte.
2. **Fail-closed ingestion.** `../ingest.py` refuses a payload without source, licence, capture clock
   time and hash. There is no partial row.
3. **Empty by design.** The store currently holds **0 files and 0 rows** because 0 price sources are
   licensed (see the policy's source register). No number has been invented to fill it.

The published flat view of the store is [`../prices.csv`](../prices.csv).
