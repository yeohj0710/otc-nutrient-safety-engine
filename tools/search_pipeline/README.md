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
python -m tools.search_pipeline.cli pubmed --target anticoag --query "(warfarin OR anticoagulant) AND omega-3 AND bleeding" --max-records 500
python -m tools.search_pipeline.cli pubmed --target anticoag --query "(warfarin OR anticoagulant) AND omega-3 AND bleeding" --max-records 100 --sort relevance
python -m tools.search_pipeline.cli embase --target anticoag --query "warfarin AND omega-3 AND bleeding" --max-records 500
python -m tools.search_pipeline.cli dedup
python -m tools.search_pipeline.cli classify --profile otc_nutrients --date-tag 20260603
python -m tools.search_pipeline.cli seed-rules --profile otc_nutrients --date-tag 20260603
```

PubMed uses NCBI E-utilities. Embase uses a persistent Playwright browser profile and exports RIS into `data/systematic_search/raw/embase`.

The `classify` command is a first-pass title/abstract keyword classifier. It creates or updates `screening_log.csv`, `evidence_extraction.csv`, and `screening_priority_<date>.csv`. The output is not final evidence; it is a reproducible triage layer for human review.
