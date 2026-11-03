from datetime import datetime
from pathlib import Path

import pytest

from etl.documents.document_parser import canonical_outlet, parse_email, parse_whatsapp

EMAIL = (
    "From: support@example.invalid\nTo: ops@example.invalid\n"
    "Date: Mon, 18 May 2026 09:03:44 +0800\nSubject: Outlet rename\n\n"
    "AMK-03 became AMK-3A on 1 Jan 2026.\n\nSupport\n"
)
CHAT = (
    "[Kaya Kopi Ops] WhatsApp Chat Export - test\n\n"
    "05/02/26, 13:14 - Person A (Ops): AMK-03 milk delivery short\n"
    "Additional context\n"
    "13/09/25, 15:21 - Person B: AMK-3A milk delivery short\n"
)


def test_email_preserves_body_not_routing_headers():
    result = parse_email(EMAIL)
    assert not result.issues
    record = result.records[0]
    assert record.timestamp == datetime(2026, 5, 18, 9, 3, 44)
    assert record.offset_minutes == 480
    assert record.sender is None
    assert "example.invalid" not in record.body
    assert record.body.endswith("\n\nSupport")
    assert record.outlets == ["AMK-03", "AMK-3A"]
    assert record.line_start == 1 and record.line_end == 8


@pytest.mark.parametrize("text,code", [
    ("Date: nonsense", "missing_header_separator"),
    (EMAIL.replace("Mon, 18 May 2026 09:03:44 +0800", "invalid"), "invalid_email_date"),
    (EMAIL.replace("Subject: Outlet rename\n", ""), "invalid_email_headers"),
    (EMAIL.replace("Subject: Outlet rename", "Subject: First\nSubject: Second"),
     "invalid_email_headers"),
    (EMAIL.split("\n\n")[0] + "\n\n", "empty_email_body"),
])
def test_email_rejects_invalid_records(text, code):
    result = parse_email(text)
    assert not result.records
    assert result.issues[0].code == code


def test_chat_dates_continuations_and_original_order():
    result = parse_whatsapp(CHAT)
    assert not result.issues
    assert len(result.records) == 2
    first, second = result.records
    assert first.timestamp == datetime(2026, 2, 5, 13, 14)
    assert second.timestamp == datetime(2025, 9, 13, 15, 21)
    assert first.body.endswith("\nAdditional context")
    assert first.line_start == 3 and first.line_end == 4
    assert first.sender == "Person A (Ops)"
    assert first.offset_minutes is None


def test_invalid_message_does_not_contaminate_previous_record():
    text = CHAT + "31/02/26, 10:00 - Person C: broken\ncontinuation of rejected record\n"
    result = parse_whatsapp(text)
    assert len(result.records) == 2
    assert result.issues[0].code == "invalid_message_date"
    assert "broken" not in result.records[-1].body
    assert "rejected" not in result.records[-1].body


def test_malformed_header_and_orphan_text_are_reported():
    result = parse_whatsapp("unexpected preamble\n1/02/2026, 9:00 - malformed\n")
    assert [issue.code for issue in result.issues] == ["orphan_text", "invalid_message_header"]


def test_repeated_messages_are_not_deduplicated():
    line = "05/02/26, 13:14 - Person: same content\n"
    assert len(parse_whatsapp(line + line).records) == 2


def test_empty_message_rejected():
    result = parse_whatsapp("05/02/26, 13:14 - Person: \n")
    assert not result.records
    assert result.issues[0].code == "empty_message_body"


def test_reviewed_alias_rule():
    assert canonical_outlet("AMK-03") == canonical_outlet("AMK-3A") == "AMK-3A"
    assert canonical_outlet("BDK-01") == "BDK-01"


def test_local_raw_inventory_if_available():
    root = Path(__file__).resolve().parents[2] / "data" / "docs"
    if not root.is_dir():
        pytest.skip("Local client files are intentionally absent from Docker images")
    emails = [parse_email(path.read_text(encoding="utf-8-sig"))
              for path in (root / "emails").glob("*.txt")]
    chat = parse_whatsapp(
        (root / "whatsapp_exports" / "ops_chat_export.txt").read_text(encoding="utf-8-sig"))
    assert len(emails) == 2
    assert all(len(result.records) == 1 and not result.issues for result in emails)
    assert not chat.issues
    assert len(chat.records) == 160
    timestamps = [record.timestamp for record in chat.records]
    assert min(timestamps) == datetime(2025, 7, 2, 8, 53)
    assert max(timestamps) == datetime(2026, 6, 29, 7, 26)
