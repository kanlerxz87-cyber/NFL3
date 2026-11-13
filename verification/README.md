# Independent source-authority audit

This is a separate, offline review artifact. It does not edit the canonical decision-lab code, captured data, or shared site navigation owned by earlier sessions.

- Published review page: [`index.html`](index.html)
- Machine-readable findings: [`report.json`](report.json)
- Checker: [`audit_sources.py`](audit_sources.py)
- Regression tests: [`test_audit_sources.py`](test_audit_sources.py)

## Reproduce

From the repository root:

```bash
python3 -m unittest -v verification/test_audit_sources.py
python3 verification/audit_sources.py --write
python3 verification/audit_sources.py --check
```

The checker is offline and uses only the checked-in snapshot, source catalog, generated HTML, and Python standard library. The static NFL/club host registry is intentionally separate from hosts found in the snapshot. It compares team labels and source hashes as well as HTTPS publisher domains. It does **not** fetch NFL, club, NIST, GitHub, or other external pages.

## Principal finding

A synthetic offline test shows that the existing `decision-lab/scripts/audit.py` dynamically adds hosts from snapshot depth rows to its own allowed-host set and then accepts depth rows when their host is in that set. The same depth-row host check does not require HTTPS. Its broad repository scan also whitelists `github.com` while classifying only two nflverse path prefixes as community sources; an unrelated GitHub repository is therefore eligible to count as an official source.

These are verifier design gaps—not evidence that the current NFL and club URLs are malicious. The current captured snapshot passes the independent fixed host/team/hash checks, while its two unparsed club chart probes remain coverage gaps. No external page contents were re-fetched in this review. The generated report is pinned to the checked-in snapshot; the Pages workflow can capture a newer snapshot at deploy time without updating this independent report. That refresh/link integration is requested, not implemented here.

## Limits and handoff

The repository scan counts each table body row and asks whether it has an HTTPS link to one of the fixed primary-source hosts. It cannot determine whether a linked page substantively supports the exact row, and it flags non-NFL host links more strictly than a source-relevance review might. A SHA-256 digest verifies byte identity only; it does not prove authorship, truth, licensing, or currentness.

A request to the prior canonical-lab owner is recorded in [`../COORDINATION.md`](../COORDINATION.md): replace snapshot-derived trust with a fixed source registry, validate HTTPS and club/team correspondence, validate discovered directory hosts against the known club registry, and stop treating arbitrary GitHub content as NFL authority. A separate integration request asks the final site maintainer to link this audit page from the Overview; this session deliberately did not edit shared navigation.
