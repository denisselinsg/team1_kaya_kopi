import json

import pytest

from etl.documents.audit_traps import audit


def test_aggregate_audit_excludes_personal_content(tmp_path):
    path = tmp_path / "chat.txt"
    path.write_text(
        "05/02/26, 13:14 - Private Name (AMK): AMK-03 fridge spoil again\n"
        "13/09/25, 15:21 - Other Person (TPY): AMK-03 fridge spoil again",
        encoding="utf-8",
    )
    result = audit(path)
    assert result["messages"] == 2
    assert result["backward_pairs"] == 1
    assert result["templates"] == 1
    assert result["prefix_mismatches"] == 1
    assert result["latest_named_supplier_message"] is None
    assert result["trailing_newline"] is False
    assert "Private Name" not in json.dumps(result)
    assert "fridge spoil again" not in json.dumps(result)


@pytest.mark.parametrize("text", ["", "invalid chat"])
def test_audit_rejects_empty_or_invalid_input(tmp_path, text):
    path = tmp_path / "chat.txt"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="parsing issues"):
        audit(path)
