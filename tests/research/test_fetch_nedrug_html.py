from scripts.research.otc.fetch_nedrug_html import RowParser, embedded_ingredients, normalize


HTML = b'''<html><table>
<tr><th>\xec\xa0\x9c\xed\x92\x88\xeb\xaa\x85</th><td>\xed\x85\x8c\xec\x8a\xa4\xed\x8a\xb8\xec\xa0\x95</td></tr>
<tr><th>\xec\x97\x85\xec\xb2\xb4\xeb\xaa\x85</th><td>\xed\x85\x8c\xec\x8a\xa4\xed\x8a\xb8\xec\xa0\x9c\xec\x95\xbd</td></tr>
<tr><th>\xec\xa0\x84\xeb\xac\xb8/\xec\x9d\xbc\xeb\xb0\x98</th><td>\xec\x9d\xbc\xeb\xb0\x98\xec\x9d\x98\xec\x95\xbd\xed\x92\x88</td></tr>
<tr><th>\xed\x97\x88\xea\xb0\x80\xec\x9d\xbc</th><td>2026-01-01</td></tr></table>
<script>var aasda = {"ingrName":"\xec\x95\x84\xec\x84\xb8\xed\x8a\xb8\xec\x95\x84\xeb\xaf\xb8\xeb\x85\xb8\xed\x8e\x9c","ingrTotqy":"500","ingrUnitName":"\xeb\xb0\x80\xeb\xa6\xac\xea\xb7\xb8\xeb\x9e\xa8","totqyCont":"1\xec\xa0\x95 \xec\xa4\x91","ingrCode":"M1"};</script>
</html>'''


def test_row_parser_extracts_label_value_pairs():
    parser = RowParser()
    parser.feed(HTML.decode())
    assert ("제품명", "테스트정") in parser.rows


def test_embedded_ingredients_extracts_amount_and_basis():
    ingredients = embedded_ingredients(HTML.decode())
    assert ingredients == [{"source_name": "아세트아미노펜", "quantity": "500", "unit": "밀리그램", "quantity_basis": "1정 중", "ingredient_code": "M1", "source_locator": "의약품상세정보 > 원료약품 및 분량"}]


def test_active_otc_is_verified():
    product = normalize("SAFE-OTC-TEST", "202600001", HTML, "2026-07-14T00:00:00+00:00")
    assert product["status"] == "verified_from_source"
    assert product["authorization_status"] == "active"
