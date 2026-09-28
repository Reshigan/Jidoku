"""Reading the tables out of a Word document, with the standard library and nothing else.

The design authority does not write only spreadsheets. On a real pack the Solution Design Document,
the Business Requirements Specification and the Plan of Record carry a hundred and fifty-seven
tables between them, and some of them are the registers the programme actually runs on: sixty-two
requirements with a fit assessment and a control reference, fifteen J-SOX control objectives with
an owner and a frequency, eleven ordering constraints, thirteen alignment rules, and decision points
that appear in no workbook at all.

A `.docx` is a zip with an XML document inside it, and a table in that XML is `w:tbl` → `w:tr` →
`w:tc`. That is the whole of what this module knows. It is deliberately stdlib: a document reader
is the easiest place in a platform to acquire a dependency for a feature nobody needs, and the hard
part here was never the parsing.

Two things it does not do, because they are somebody's judgement rather than a parse:

  **It does not guess which table is which.** A caller declares the header it wants. A reader that
  matched on shape would swallow the revision history the first time somebody added a column.

  **It does not read prose.** A paragraph is returned as a paragraph. What a document states only in
  sentences — and a design document states a great deal that way — is not in the platform, and the
  absorber says so rather than implying a document was understood.
"""
import zipfile
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class DocxError(Exception): ...


def _text(el) -> str:
    """Every run of text under an element, joined. Word splits a sentence across runs wherever
    formatting changes, so reading only the first `w:t` returns half a requirement."""
    return "".join(t.text or "" for t in el.iter(W + "t")).strip()


def _document(path):
    try:
        with zipfile.ZipFile(path) as z:
            return ET.fromstring(z.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError) as ex:
        raise DocxError(f"{path}: not a readable .docx ({type(ex).__name__}). A .doc, a password-"
                        f"protected file and a renamed PDF all arrive looking like this.") from None


def tables(path) -> list[list[list[str]]]:
    """Every table, as rows of cell text, in document order."""
    return [[[_text(tc) for tc in tr.findall(W + "tc")] for tr in tbl.findall(W + "tr")]
            for tbl in _document(path).iter(W + "tbl")]


def paragraphs(path) -> list[str]:
    """Every non-empty paragraph. The prose, which nothing here interprets."""
    return [t for t in (_text(p) for p in _document(path).iter(W + "p")) if t]


def headings(path) -> list[str]:
    """Paragraphs Word marks as headings — the document's own outline, used to say what was in a
    document that no profile read."""
    out = []
    for p in _document(path).iter(W + "p"):
        style = p.find(f"{W}pPr/{W}pStyle")
        if style is not None and "Heading" in (style.get(W + "val") or ""):
            if text := _text(p):
                out.append(text)
    return out


def rows(path, header: tuple[str, ...]) -> list[dict]:
    """Rows of every table whose first row starts with `header`, keyed by that header.

    Every table, not the first: a BRS writes its sixty-two requirements as seventeen tables under
    one heading each, and taking the first would report a sixth of a specification as the whole.
    """
    out = []
    for table in tables(path):
        if not table or tuple(table[0][:len(header)]) != header:
            continue
        names = table[0]
        for row in table[1:]:
            rec = {name: (row[i] if i < len(row) else "") for i, name in enumerate(names)}
            if any(rec.values()):
                out.append(rec)
    return out


def unread(path, headers: list[tuple[str, ...]]) -> list[tuple[str, int]]:
    """The tables no declared header matched, as (first cell, row count).

    This is the module's most important function and it returns what was *missed*. A document reader
    that reports what it found is telling you about itself; a person signing a bundle needs to know
    what it did not.
    """
    wanted = {h for h in headers}
    out = []
    for table in tables(path):
        if not table or not table[0]:
            continue
        if any(tuple(table[0][:len(h)]) == h for h in wanted):
            continue
        out.append((table[0][0][:60] or "(unlabelled)", len(table) - 1))
    return out
