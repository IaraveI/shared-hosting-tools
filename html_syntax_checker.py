#!/usr/bin/env python3
"""Tiny stdin-only HTML syntax checker.

This checker is intentionally syntax-focused. It checks for:
- UTF-8 decoding failures
- obvious charset declaration mismatches
- malformed comments / declarations
- malformed tag and attribute syntax
- duplicate attributes
- stray / mismatched closing tags
- unclosed non-void elements
- explicit top-level html/head/body structure problems

Behavior notes:
- Tag names are treated generically, including custom names such as <chatgpt>.
- All non-void elements require explicit closing tags.
- Void elements still use the HTML void-element list and must not be closed.
- html/head/body are checked explicitly as special top-level structure.
- Exact <pre><code>...</code></pre> regions are skipped so literal sample
  markup inside code blocks is not parsed as document structure.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass


VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}

RAWTEXT_ELEMENTS = {"script", "style"}

META_CHARSET_RE = re.compile(
    r"<meta\b[^>]*\bcharset\s*=\s*(['\"]?)([^'\"\s/>]+)\1",
    re.IGNORECASE,
)
TAG_NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9:-]*")
ATTR_NAME_RE = re.compile(r"[^\s\"'<>/=]+")


@dataclass
class Issue:
    line: int
    column: int
    message: str


@dataclass
class OpenTag:
    name: str
    line: int
    column: int


@dataclass
class ScanResult:
    top_level_issues: list[Issue]
    general_issues: list[Issue]


class Scanner:
    CASCADE_FOLLOWUP_LIMIT = 1
    TOP_LEVEL_OUTSIDE_ROOT_LIMIT = 3

    def __init__(self, text: str) -> None:
        self.text = text
        self.length = len(text)
        self.pos = 0
        self.top_level_issues: list[Issue] = []
        self.general_issues: list[Issue] = []
        self.open_tags: list[OpenTag] = []
        self.seen_html = False
        self.closed_html = False
        self.seen_head = False
        self.seen_body = False
        self.syntax_cascade_open = False
        self.syntax_followups_remaining = 0
        self.syntax_suppression_noted = False
        self.top_level_outside_root_count = 0
        self.top_level_outside_root_suppressed = False
        self.svg_region_start: int | None = None

    def add_top_level_issue(self, pos: int, message: str) -> None:
        if message == "content outside top-level <html>":
            if self.top_level_outside_root_count >= self.TOP_LEVEL_OUTSIDE_ROOT_LIMIT:
                if not self.top_level_outside_root_suppressed:
                    line, column = self.line_col(pos)
                    self.top_level_issues.append(
                        Issue(line, column, "further outside-root content suppressed")
                    )
                    self.top_level_outside_root_suppressed = True
                return
            self.top_level_outside_root_count += 1

        line, column = self.line_col(pos)
        self.top_level_issues.append(Issue(line, column, message))

    def add_general_issue(self, pos: int, message: str) -> None:
        if self.syntax_cascade_open:
            if self.syntax_followups_remaining <= 0:
                self.note_suppressed(pos)
                return
            self.syntax_followups_remaining -= 1

        line, column = self.line_col(pos)
        self.general_issues.append(Issue(line, column, message))

    def add_general_issue_obj(self, issue: Issue) -> None:
        if self.syntax_cascade_open:
            if self.syntax_followups_remaining <= 0:
                self.note_suppressed_issue(issue)
                return
            self.syntax_followups_remaining -= 1
        self.general_issues.append(issue)

    def start_syntax_cascade(self, pos: int, message: str) -> None:
        line, column = self.line_col(pos)
        self.general_issues.append(Issue(line, column, message))
        self.syntax_cascade_open = True
        self.syntax_followups_remaining = self.CASCADE_FOLLOWUP_LIMIT
        self.syntax_suppression_noted = False

    def note_suppressed(self, pos: int) -> None:
        if self.syntax_suppression_noted:
            return
        line, column = self.line_col(pos)
        self.general_issues.append(Issue(line, column, "further cascading errors suppressed"))
        self.syntax_suppression_noted = True

    def note_suppressed_issue(self, issue: Issue) -> None:
        if self.syntax_suppression_noted:
            return
        self.general_issues.append(
            Issue(issue.line, issue.column, "further cascading errors suppressed")
        )
        self.syntax_suppression_noted = True

    def close_syntax_cascade(self) -> None:
        self.syntax_cascade_open = False
        self.syntax_followups_remaining = 0
        self.syntax_suppression_noted = False

    def line_col(self, pos: int) -> tuple[int, int]:
        line = self.text.count("\n", 0, pos) + 1
        last_newline = self.text.rfind("\n", 0, pos)
        column = pos + 1 if last_newline == -1 else pos - last_newline
        return line, column

    def peek(self, offset: int = 0) -> str:
        idx = self.pos + offset
        if idx >= self.length:
            return ""
        return self.text[idx]

    def startswith(self, value: str, pos: int | None = None) -> bool:
        return self.text.startswith(value, self.pos if pos is None else pos)

    def skip_whitespace(self) -> None:
        while self.pos < self.length and self.text[self.pos].isspace():
            self.pos += 1

    def skip_whitespace_with_flag(self) -> bool:
        start = self.pos
        self.skip_whitespace()
        return self.pos > start

    def current_parent_name(self) -> str | None:
        if not self.open_tags:
            return None
        return self.open_tags[-1].name

    def scan_text(self) -> None:
        text_start = self.pos
        next_tag = self.text.find("<", self.pos)
        if next_tag == -1:
            next_tag = self.length
        segment = self.text[text_start:next_tag]
        if segment.strip() and (not self.seen_html or self.closed_html):
            offset = len(segment) - len(segment.lstrip())
            self.add_top_level_issue(text_start + offset, "content outside top-level <html>")
        self.pos = next_tag

    def find_svg_start_after_xml_prolog(self, prolog_end: int) -> int | None:
        pos = prolog_end
        while pos < self.length and self.text[pos].isspace():
            pos += 1
        if self.startswith("<svg", pos):
            return pos
        return None

    def skip_pre_code_region(self) -> bool:
        if not self.startswith("<pre"):
            return False

        pre_tag_end = self.text.find(">", self.pos + 4)
        if pre_tag_end == -1:
            return False

        pre_tag_text = self.text[self.pos : pre_tag_end + 1]
        if pre_tag_text.rstrip().endswith("/>"):
            return False

        inner_pos = pre_tag_end + 1
        while inner_pos < self.length and self.text[inner_pos].isspace():
            inner_pos += 1

        if not self.startswith("<code", inner_pos):
            return False

        code_tag_end = self.text.find(">", inner_pos + 5)
        if code_tag_end == -1:
            return False

        code_tag_text = self.text[inner_pos : code_tag_end + 1]
        if code_tag_text.rstrip().endswith("/>"):
            return False

        close_match = re.search(r"</code\s*>", self.text[code_tag_end + 1 :], re.IGNORECASE)
        if close_match is None:
            self.add_general_issue(inner_pos, "unclosed <pre><code> region: missing </code>")
            self.pos = self.length
            return True

        code_close_end = code_tag_end + 1 + close_match.end()
        inner_pos = code_close_end
        while inner_pos < self.length and self.text[inner_pos].isspace():
            inner_pos += 1

        pre_close_match = re.match(r"</pre\s*>", self.text[inner_pos:], re.IGNORECASE)
        if pre_close_match is None:
            self.add_general_issue(self.pos, "unclosed <pre><code> region: missing </pre>")
            self.pos = self.length
            return True

        self.pos = inner_pos + pre_close_match.end()
        return True

    def skip_svg_region(self) -> bool:
        region_start = self.pos

        if self.startswith("<?xml"):
            prolog_end = self.text.find("?>", self.pos + 5)
            if prolog_end == -1:
                return False
            svg_start = self.find_svg_start_after_xml_prolog(prolog_end + 2)
            if svg_start is None:
                return False
            self.add_general_issue(
                self.pos,
                "processing-like instruction tolerated before <svg>",
            )
            self.pos = svg_start
        elif not self.startswith("<svg"):
            return False

        depth = 0

        while self.pos < self.length:
            if self.startswith("<!--"):
                self.scan_comment()
                continue

            if self.startswith("<svg"):
                tag_end = self.text.find(">", self.pos + 4)
                if tag_end == -1:
                    self.add_general_issue(region_start, "unclosed <svg> region")
                    self.pos = self.length
                    return True
                tag_text = self.text[self.pos : tag_end + 1]
                if not tag_text.rstrip().endswith("/>"):
                    depth += 1
                self.pos = tag_end + 1
                continue

            if self.startswith("</svg"):
                tag_end = self.text.find(">", self.pos + 5)
                if tag_end == -1:
                    self.add_general_issue(region_start, "unclosed <svg> region")
                    self.pos = self.length
                    return True
                self.pos = tag_end + 1
                depth -= 1
                if depth <= 0:
                    return True
                continue

            next_tag = self.text.find("<", self.pos + 1)
            if next_tag == -1:
                self.add_general_issue(region_start, "unclosed <svg> region")
                self.pos = self.length
                return True
            self.pos = next_tag

        self.add_general_issue(region_start, "unclosed <svg> region")
        return True

    def validate_document_structure(self) -> None:
        if not self.seen_html:
            self.top_level_issues.append(Issue(1, 1, "missing <html>"))
        if not self.seen_head:
            self.top_level_issues.append(Issue(1, 1, "missing <head>"))
        if not self.seen_body:
            self.top_level_issues.append(Issue(1, 1, "missing <body>"))

    def scan(self) -> ScanResult:
        while self.pos < self.length:
            if self.peek() != "<":
                self.scan_text()
                continue

            if self.skip_pre_code_region():
                continue

            if self.skip_svg_region():
                continue

            if self.startswith("<!--"):
                self.scan_comment()
            elif self.startswith("</"):
                self.scan_end_tag()
            elif self.startswith("<!"):
                self.scan_declaration()
            elif self.startswith("<?"):
                self.scan_processing_instruction()
            else:
                self.scan_start_tag()

        for tag in reversed(self.open_tags):
            self.add_general_issue_obj(
                Issue(tag.line, tag.column, f"unclosed tag <{tag.name}>")
            )
        self.validate_document_structure()
        return ScanResult(self.top_level_issues, self.general_issues)

    def scan_comment(self) -> None:
        start = self.pos
        end = self.text.find("-->", self.pos + 4)
        if end == -1:
            self.add_general_issue(start, "unclosed HTML comment")
            self.pos = self.length
            return
        if "--" in self.text[self.pos + 4 : end]:
            self.add_general_issue(start, "comment contains invalid double-hyphen sequence")
        self.pos = end + 3

    def scan_declaration(self) -> None:
        start = self.pos
        if self.text[self.pos : self.pos + 9].lower() == "<!doctype":
            end = self.text.find(">", self.pos + 2)
            if end == -1:
                self.add_general_issue(start, "unclosed doctype declaration")
                self.pos = self.length
                return
            self.pos = end + 1
            return

        end = self.text.find(">", self.pos + 2)
        if end == -1:
            self.add_general_issue(start, "unclosed declaration")
            self.pos = self.length
            return
        self.add_general_issue(start, "unsupported or malformed declaration")
        self.pos = end + 1

    def scan_processing_instruction(self) -> None:
        start = self.pos
        end = self.text.find("?>", self.pos + 2)
        if end == -1:
            self.add_general_issue(start, "unclosed processing-like instruction")
            self.pos = self.length
            return
        self.add_general_issue(start, "processing-like instructions are not valid HTML syntax")
        self.pos = end + 2

    def scan_start_tag(self) -> None:
        tag_start = self.pos
        self.pos += 1
        match = TAG_NAME_RE.match(self.text, self.pos)
        if not match:
            self.add_general_issue(tag_start, "malformed tag opening")
            self.skip_broken_tag()
            return

        name = match.group(0).lower()
        parent_name = self.current_parent_name()
        self.pos = match.end()
        attrs: set[str] = set()
        had_separator = self.skip_whitespace_with_flag()
        self_closed = False

        while self.pos < self.length:
            if self.startswith("/>"):
                self_closed = True
                self.pos += 2
                break
            if self.peek() == ">":
                self.pos += 1
                break

            if attrs and not had_separator:
                self.add_general_issue(self.pos, "missing whitespace between attributes")
                self.skip_broken_tag()
                return

            attr_pos = self.pos
            attr_match = ATTR_NAME_RE.match(self.text, self.pos)
            if not attr_match:
                self.add_general_issue(attr_pos, "malformed attribute syntax")
                self.skip_broken_tag()
                return

            attr_name = attr_match.group(0)
            attr_name_lower = attr_name.lower()
            if attr_name_lower in attrs:
                self.add_general_issue(attr_pos, f"duplicate attribute '{attr_name}'")
            attrs.add(attr_name_lower)
            self.pos = attr_match.end()
            had_separator_after_name = self.skip_whitespace_with_flag()

            if self.peek() != "=":
                if self.peek() in {">", "/"}:
                    pass
                elif had_separator_after_name and ATTR_NAME_RE.match(self.text, self.pos):
                    had_separator = True
                    continue
                else:
                    self.add_general_issue(attr_pos, f"attribute '{attr_name}' missing '='")
                    self.skip_broken_tag()
                    return
            else:
                self.pos += 1
                self.skip_whitespace()
                if self.pos >= self.length:
                    self.add_general_issue(attr_pos, f"attribute '{attr_name}' missing value")
                    return
                quote = self.peek()
                if quote in {"'", '"'}:
                    self.pos += 1
                    value_end = self.text.find(quote, self.pos)
                    if value_end == -1:
                        self.add_general_issue(attr_pos, f"attribute '{attr_name}' has unclosed quote")
                        self.pos = self.length
                        return
                    self.pos = value_end + 1
                else:
                    value_match = re.match(r"[^\s\"'<=`>]+", self.text[self.pos :])
                    if not value_match:
                        self.add_general_issue(attr_pos, f"attribute '{attr_name}' has malformed value")
                        self.skip_broken_tag()
                        return
                    self.pos += value_match.end()
                had_separator = self.skip_whitespace_with_flag()
                continue

            had_separator = self.skip_whitespace_with_flag()

        else:
            self.add_general_issue(tag_start, f"unclosed start tag <{name}>")
            return

        parent_name = self.current_parent_name()

        if name == "html":
            if self.seen_html:
                self.add_top_level_issue(tag_start, "duplicate <html>")
            if parent_name is not None:
                self.add_top_level_issue(tag_start, "<html> must be the top-level root element")
            self.seen_html = True
            self.closed_html = False
        elif not self.seen_html or self.closed_html:
            self.add_top_level_issue(tag_start, "content outside top-level <html>")

        if name == "head":
            if self.seen_head:
                self.add_top_level_issue(tag_start, "duplicate <head>")
            if not self.seen_html:
                self.add_top_level_issue(tag_start, "<head> must appear inside <html>")
            elif parent_name != "html":
                self.add_top_level_issue(tag_start, "<head> must be a direct child of <html>")
            if self.seen_body:
                self.add_top_level_issue(tag_start, "<head> must appear before <body>")
            self.seen_head = True
        elif name == "body":
            if self.seen_body:
                self.add_top_level_issue(tag_start, "duplicate <body>")
            if not self.seen_html:
                self.add_top_level_issue(tag_start, "<body> must appear inside <html>")
            elif parent_name != "html":
                self.add_top_level_issue(tag_start, "<body> must be a direct child of <html>")
            if not self.seen_head:
                self.add_top_level_issue(tag_start, "<body> must appear after <head>")
            self.seen_body = True

        if name in VOID_ELEMENTS:
            return

        if self_closed:
            return

        if name in RAWTEXT_ELEMENTS:
            self.handle_rawtext(name, tag_start)
            return

        self.open_tags.append(OpenTag(name, *self.line_col(tag_start)))

    def handle_rawtext(self, name: str, tag_start: int) -> None:
        search_pos = self.pos
        close_match = re.search(rf"</{re.escape(name)}\s*>", self.text[search_pos:], re.IGNORECASE)
        if close_match is None:
            self.add_general_issue(tag_start, f"unclosed raw-text element <{name}>")
            return
        close_pos = search_pos + close_match.start()
        self.open_tags.append(OpenTag(name, *self.line_col(tag_start)))
        self.pos = close_pos

    def scan_end_tag(self) -> None:
        tag_start = self.pos
        self.pos += 2
        match = TAG_NAME_RE.match(self.text, self.pos)
        if not match:
            self.add_general_issue(tag_start, "malformed closing tag")
            self.skip_broken_tag()
            return

        name = match.group(0).lower()
        self.pos = match.end()
        self.skip_whitespace()
        if self.peek() != ">":
            self.add_general_issue(tag_start, f"closing tag </{name}> has trailing garbage")
            self.skip_broken_tag()
            return
        self.pos += 1

        if name != "html" and (not self.seen_html or self.closed_html):
            self.add_top_level_issue(tag_start, "content outside top-level <html>")

        if name in VOID_ELEMENTS:
            self.add_general_issue(tag_start, f"void element <{name}> must not have a closing tag")
            return

        if not self.open_tags:
            self.start_syntax_cascade(tag_start, f"stray closing tag </{name}>")
            return

        top = self.open_tags[-1]
        if top.name == name:
            self.open_tags.pop()
            if name == "html":
                self.closed_html = True
            self.close_syntax_cascade()
            return

        if name in {"body", "html"}:
            for index in range(len(self.open_tags) - 1, -1, -1):
                if self.open_tags[index].name != name:
                    continue

                for tag in reversed(self.open_tags[index + 1 :]):
                    self.add_general_issue_obj(
                        Issue(tag.line, tag.column, f"unclosed tag <{tag.name}>")
                    )

                del self.open_tags[index:]
                if name == "html":
                    self.closed_html = True
                self.close_syntax_cascade()
                return

        for index in range(len(self.open_tags) - 1, -1, -1):
            if self.open_tags[index].name == name:
                self.start_syntax_cascade(
                    tag_start,
                    f"mismatched closing tag </{name}>; expected </{top.name}>",
                )
                return

        self.start_syntax_cascade(tag_start, f"stray closing tag </{name}>")

    def skip_broken_tag(self) -> None:
        end = self.text.find(">", self.pos)
        self.pos = self.length if end == -1 else end + 1


def detect_encoding(raw: bytes) -> tuple[str | None, list[Issue]]:
    issues: list[Issue] = []
    declared = None

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        prefix = raw[: exc.start].decode("utf-8", errors="ignore")
        line = prefix.count("\n") + 1
        last_newline = prefix.rfind("\n")
        column = len(prefix) + 1 if last_newline == -1 else len(prefix) - last_newline
        issues.append(Issue(line, column, f"invalid UTF-8 sequence: {exc.reason}"))
        return None, issues

    if raw.startswith(b"\xef\xbb\xbf"):
        issues.append(Issue(1, 1, "UTF-8 BOM detected"))

    head = text[:1024]
    match = META_CHARSET_RE.search(head)
    if match:
        declared = match.group(2).strip().lower()
        normalized = declared.replace("_", "-")
        if normalized not in {"utf-8", "utf8"}:
            line = text.count("\n", 0, match.start()) + 1
            last_newline = text.rfind("\n", 0, match.start())
            column = match.start() + 1 if last_newline == -1 else match.start() - last_newline
            issues.append(
                Issue(
                    line,
                    column,
                    f"declared charset '{declared}' does not match UTF-8 input decoding",
                )
            )

    return text, issues


def format_issue(issue: Issue) -> str:
    return f"ERROR:{issue.line}:{issue.column}: {issue.message}"


def print_issue_section(title: str, issues: list[Issue], stream: object) -> None:
    print(f"{title}:", file=stream)
    if not issues:
        print("0 error(s)", file=stream)
        return

    for issue in issues:
        print(format_issue(issue), file=stream)
    print(f"{len(issues)} error(s)", file=stream)


def main() -> int:
    raw = sys.stdin.buffer.read()
    if not raw:
        return 0

    decoded, issues = detect_encoding(raw)
    if decoded is None:
        for issue in issues:
            print(format_issue(issue), file=sys.stderr)
        print(f"{len(issues)} error(s) found", file=sys.stderr)
        return 1

    scanner = Scanner(decoded)
    result = scanner.scan()
    all_issues = issues + result.top_level_issues + result.general_issues

    stream = sys.stdout if not all_issues else sys.stderr
    for issue in issues:
        print(format_issue(issue), file=stream)
    if issues:
        print(f"{len(issues)} encoding error(s)", file=stream)

    print_issue_section("Top-level structure", result.top_level_issues, stream)
    print_issue_section("General syntax", result.general_issues, stream)
    print(f"{len(all_issues)} error(s) found", file=stream)
    return 0 if not all_issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
