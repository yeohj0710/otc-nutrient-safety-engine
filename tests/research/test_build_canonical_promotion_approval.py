import json
import re

from scripts.research.otc.build_canonical_promotion_approval import build


def test_approval_is_one_click_and_keeps_claim_boundary():
    page = build()
    payload = json.loads(re.search(r'<script id="payload" type="application/json">(.*?)</script>', page, re.S).group(1))
    assert payload["authorize_canonical_document_promotion"] is True
    assert payload["accept_blinded_independent_evaluation_not_completed"] is True
    assert payload["authorize_production_deployment"] is False
    assert len(payload["files"]) == 4
    assert all(len(item["source_sha256"]) == 64 for item in payload["files"])
