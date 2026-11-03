"""Deterministic document parsers; content is never executed or sent externally."""

from dataclasses import dataclass, field
from datetime import datetime
from email import policy
from email.parser import Parser
from email.utils import parsedate_to_datetime
import re

PROCESSING_VERSION = "text-original-v1-alias-v1"
OUTLET_PATTERN = re.compile(r"\b[A-Z]{3}-[0-9][A-Z0-9]\b")
MESSAGE_PATTERN = re.compile(
    r"^(\d{2}/\d{2}/\d{2}), (\d{2}:\d{2}) - ([^:]+): ?(.*)$"
)
MESSAGE_START = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4},")
ALIAS_PROVENANCE = "docs/emails/2026-05-18_outlet_rename.txt"


def canonical_outlet(code: str) -> str:
    return "AMK-3A" if code in {"AMK-03", "AMK-3A"} else code


@dataclass
class Record:
    line_start: int
    line_end: int
    timestamp: datetime
    offset_minutes: int | None
    subject: str
    sender: str | None
    body: str

    @property
    def outlets(self) -> list[str]:
        return sorted(set(OUTLET_PATTERN.findall(f"{self.subject}\n{self.body}")))


@dataclass
class ParseIssue:
    line: int
    code: str


@dataclass
class ParseResult:
    records: list[Record] = field(default_factory=list)
    issues: list[ParseIssue] = field(default_factory=list)


def parse_email(text: str) -> ParseResult:
    lines = text.splitlines()
    try:
        separator = lines.index("")
    except ValueError:
        return ParseResult(issues=[ParseIssue(1, "missing_header_separator")])
    message = Parser(policy=policy.default).parsestr(text)
    if message.defects or any(len(message.get_all(key, [])) != 1 for key in
                              ("From", "To", "Date", "Subject")):
        return ParseResult(issues=[ParseIssue(1, "invalid_email_headers")])
    try:
        timestamp = parsedate_to_datetime(str(message["Date"]))
    except (ValueError, TypeError, OverflowError):
        return ParseResult(issues=[ParseIssue(1, "invalid_email_date")])
    body = "\n".join(lines[separator + 1:])
    if not body.strip():
        return ParseResult(issues=[ParseIssue(separator + 2, "empty_email_body")])
    offset = timestamp.utcoffset()
    return ParseResult(records=[Record(
        1, len(lines), timestamp.replace(tzinfo=None),
        int(offset.total_seconds() // 60) if offset is not None else None,
        str(message["Subject"]), None, body,
    )])


def parse_whatsapp(text: str) -> ParseResult:
    result = ParseResult()
    current: Record | None = None
    rejected_message = False
    for number, line in enumerate(text.splitlines(), 1):
        match = MESSAGE_PATTERN.fullmatch(line)
        if match or MESSAGE_START.match(line):
            if current is not None:
                result.records.append(current)
            current = None
            rejected_message = True
            if match is None:
                result.issues.append(ParseIssue(number, "invalid_message_header"))
                continue
            try:
                timestamp = datetime.strptime(
                    f"{match[1]} {match[2]}", "%d/%m/%y %H:%M")
            except ValueError:
                result.issues.append(ParseIssue(number, "invalid_message_date"))
                continue
            current = Record(number, number, timestamp, None, "", match[3], match[4])
            rejected_message = False
        elif current is not None:
            current.body += "\n" + line
            current.line_end = number
        elif not line.strip():
            continue
        elif number == 1 and line.startswith("[Kaya Kopi Ops] WhatsApp Chat Export"):
            continue
        elif not rejected_message:
            result.issues.append(ParseIssue(number, "orphan_text"))
    if current is not None:
        result.records.append(current)
    valid = []
    for record in result.records:
        if record.body.strip():
            valid.append(record)
        else:
            result.issues.append(ParseIssue(record.line_start, "empty_message_body"))
    result.records = valid
    return result
