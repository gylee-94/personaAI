# Literature corpus provenance and count units

The available records describe two counts. They have not been reconciled by a
per-document manifest and must not be used interchangeably.

| Record | Count | Unit and verification status |
|---|---:|---|
| Historical public corpus description | 566,157 | Approximately this many XML documents; no file-level snapshot is bundled |
| Final manuscript / author collection tally | 565,634 | Reported publications, including nine with unknown year; unique indexed publication count not independently established here |
| Difference | 523 | Unresolved difference in counts/snapshots/units; not demonstrated to be duplicates or failed indexing |

The author-reported dated breakdown is:

| Period | PMC | PubMed | Total |
|---|---:|---:|---:|
| 1900–2020 | 121,266 | 308,663 | 429,929 |
| 2021 onward | 90,775 | 44,921 | 135,696 |
| Dated subtotal | | | 565,625 |
| Unknown year | | | 9 |

This table is a collection tally, not evidence that every item was embedded or
retrievable. Exact original queries, extraction timestamps, the historical date
field and inclusive boundary rule, a complete PMID/PMCID deduplication mapping,
and the nine undated records' membership in each index are unavailable in the
public records. The intended 2020 upper limit should not be mistaken for an
audited first-online-publication cutoff. `run_full_indexing.py` preserves
available PMID/PMCID metadata but cannot recreate the missing collection log.

For a new reproducible build, record separate counts for retrieved records,
unique publications after identifier reconciliation, source files, successfully
parsed documents, embedded chunks, and indexed points. Freeze the selected
corpus and collection name, export document identifiers and the chosen date
field, and state the inclusive period and handling of missing dates. This is a
requirement for new builds, not a claim that these records exist for the paper.

Corpus-only mode now prevents optional web/general-purpose tool use in the
application. Sparse retrieval remains sparse; it does not fall back to an
unrestricted web source. A date-selected collection must still be supplied
and verified by the operator. This implementation does not blind the LLM's
parametric knowledge, prove historical access restrictions, or establish
prospective prediction.
