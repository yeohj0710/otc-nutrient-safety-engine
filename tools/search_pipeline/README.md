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
python -m tools.search_pipeline.cli embase --target anticoag --query "warfarin AND omega-3 AND bleeding" --max-records 500
python -m tools.search_pipeline.cli dedup
```

PubMed uses NCBI E-utilities. Embase uses a persistent Playwright browser profile and exports RIS into `data/systematic_search/raw/embase`.
