"""PDF parsing via Docling: layout-aware, table-preserving, section-aware.

Converts a PDF into a flat, ordered list of ParsedItem, each tagged with
its page number and the section heading active at that point in the
document. Tables are kept as whole markdown blocks. Pages Docling could
not confidently parse (likely scanned/image-only) fail the whole parse
loudly, naming every affected page, rather than silently producing empty
or garbage content for them.
"""

from __future__ import annotations

from dataclasses import dataclass

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc.document import (
    DocItem,
    SectionHeaderItem,
    TableItem,
    TitleItem,
)

# Below this score on either parse_score or ocr_score, a page is treated
# as likely scanned/unparseable rather than silently accepted.
CONFIDENCE_THRESHOLD = 0.5


class ParseError(Exception):
    """Raised when one or more pages fail the confidence check."""


@dataclass
class ParsedItem:
    text: str
    page_no: int | None
    section_number: str | None
    content_type: str  # 'rule_text' | 'table' | 'procedure'


def _build_converter() -> DocumentConverter:
    pipeline_options = PdfPipelineOptions(do_table_structure=True, do_ocr=True)
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
    )


def _check_page_confidence(confidence) -> None:
    flagged: list[int] = []
    for page_no, scores in confidence.pages.items():
        if scores.parse_score < CONFIDENCE_THRESHOLD or scores.ocr_score < CONFIDENCE_THRESHOLD:
            flagged.append(page_no)
    if flagged:
        flagged.sort()
        raise ParseError(
            f"{len(flagged)} page(s) failed the parse-confidence check "
            f"(likely scanned/image-only, below {CONFIDENCE_THRESHOLD} on "
            f"parse_score or ocr_score): pages {flagged}. "
            "Re-scan these pages or provide a text-layer PDF before ingesting."
        )


def parse_pdf(pdf_path: str, document_type: str) -> list[ParsedItem]:
    """Parse a PDF into ordered ParsedItems.

    document_type is 'rules' or 'form' — controls the default content_type
    for body text that isn't a table (rules docs default to 'rule_text',
    the two operational forms default to 'procedure').
    """
    if document_type not in ("rules", "form"):
        raise ValueError(f"document_type must be 'rules' or 'form', got {document_type!r}")

    converter = _build_converter()
    result = converter.convert(pdf_path)
    _check_page_confidence(result.confidence)

    body_content_type = "rule_text" if document_type == "rules" else "procedure"

    items: list[ParsedItem] = []
    current_section: str | None = None
    saw_heading = False

    for node, _level in result.document.iterate_items():
        if not isinstance(node, DocItem):
            continue  # structural group node, not actual content

        page_no = node.prov[0].page_no if node.prov else None

        if isinstance(node, (SectionHeaderItem, TitleItem)):
            current_section = node.text.strip()
            saw_heading = True
            continue  # heading text itself isn't a retrievable chunk

        if isinstance(node, TableItem):
            table_text = node.export_to_markdown(doc=result.document).strip()
            if table_text:
                items.append(
                    ParsedItem(
                        text=table_text,
                        page_no=page_no,
                        section_number=current_section,
                        content_type="table",
                    )
                )
            continue

        text = getattr(node, "text", None)
        if text and text.strip():
            items.append(
                ParsedItem(
                    text=text.strip(),
                    page_no=page_no,
                    section_number=current_section,
                    content_type=body_content_type,
                )
            )

    if not saw_heading:
        print(
            f"WARNING: no section headings detected in {pdf_path!r}. "
            "All items have section_number=None; chunk.py will fall back "
            "to fixed-size windowing instead of section-aware chunking."
        )

    return items
