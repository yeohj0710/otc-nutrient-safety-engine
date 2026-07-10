# Systematic Search Pipeline

Python pipeline for reproducible PubMed and Embase literature search.

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

Create `.env` with:

```text
NCBI_EMAIL=your.email@example.com
NCBI_API_KEY=optional
```

## Commands

```bash
python -m tools.search_pipeline.cli init
python -m tools.search_pipeline.cli pubmed --target K1 --query "vitamin D AND hypercalcemia"
python -m tools.search_pipeline.cli pubmed --target K2 --query "vitamin B6 AND neuropathy"
python -m tools.search_pipeline.cli parse-ris --path "exports/K1_embase_full.ris" --target K1 --source embase --search-run-id K1-EMBASE-001
python -m tools.search_pipeline.cli dedup
python -m tools.search_pipeline.cli classify --profile otc_nutrients --date-tag 20260603
python -m tools.search_pipeline.cli seed-rules --profile otc_nutrients --date-tag 20260603
```

PubMed uses NCBI E-utilities. The automated Embase adapter remains follow-up code; Gate 2 uses a human-exported full RIS file until the adapter can prove hit/export/import reconciliation.

PubMed retrieval is full by default. If a query exceeds the ESearch 10,000-UID limit, the command records `requires_segmentation` and stops without importing a partial set. Segment the query into non-overlapping date ranges or use EDirect, then reconcile the combined exports. `--max-records` is retained only for capped debugging and cannot support a Gate 2 search.

The `classify` command is a first-pass title/abstract keyword classifier. It creates or updates `screening_log.csv`, `evidence_extraction.csv`, and `screening_priority_<date>.csv`. The output is not final evidence; it is a reproducible triage layer for human review.
