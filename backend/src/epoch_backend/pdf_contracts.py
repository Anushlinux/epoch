"""Host-owned PDF tool contracts and verification requirements."""

import re
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(min_length=1, max_length=12000)]
Name = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,119}\.pdf$")]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Block(Strict):
    kind: Literal["heading", "paragraph", "bullets", "table"]
    text: str = Field(default="", max_length=12000)
    items: list[Text] = Field(default_factory=list, max_length=100)
    rows: list[list[Text]] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def content(self):
        if self.kind in {"heading", "paragraph"} and (not self.text or self.items or self.rows):
            raise ValueError("Text blocks require text only")
        if self.kind == "bullets" and (not self.items or self.text or self.rows):
            raise ValueError("Bullet blocks require items only")
        if self.kind == "table" and (
            not self.rows
            or self.text
            or self.items
            or not 1 <= len(self.rows[0]) <= 6
            or any(len(r) != len(self.rows[0]) for r in self.rows)
        ):
            raise ValueError("Tables require rectangular rows with 1-6 columns")
        return self


class Document(Strict):
    title: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    blocks: list[Block] = Field(min_length=1, max_length=150)

    @model_validator(mode="after")
    def size(self):
        if len(self.model_dump_json()) > 100000:
            raise ValueError("Document content exceeds 100,000 characters")
        return self


class CreatePdf(Strict):
    document: Document
    output_name: Name
    idempotency_key: Annotated[str, StringConstraints(min_length=1, max_length=200)]


class MergePdf(Strict):
    asset_ids: list[UUID] = Field(min_length=2, max_length=5)
    output_name: Name
    idempotency_key: Annotated[str, StringConstraints(min_length=1, max_length=200)]


class CapabilityRequest(MergePdf):
    capability: Literal["pdf.merge"]
    reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ReadAsset(Strict):
    asset_id: UUID


class NoArguments(Strict):
    pass


class EnvironmentAction(Strict):
    client_request_id: UUID
    action: Literal["repair_tool", "create_tool"]
    evidence_id: UUID
    expected_version: str = Field(min_length=1, max_length=100)


class PdfProposal(Strict):
    outcome: Literal["repair", "unsupported"]
    diagnosis: str = Field(min_length=1, max_length=4000)
    evidence_ids: list[UUID] = Field(min_length=1, max_length=10)
    target: Literal["render_pdf", "merge_pdfs"]
    source: str = Field(max_length=20000)
    description: str = Field(min_length=1, max_length=1500)
    input_schema_json: str
    input_schema: dict | None = None
    uncertainty: str


def literal_schema(value):
    """Constrain generated contract metadata without embedding quoted JSON literals."""
    if isinstance(value, dict):
        return {
            "type": "object",
            "properties": {k: literal_schema(v) for k, v in value.items()},
            "required": list(value),
            "additionalProperties": False,
        }
    if isinstance(value, list):
        return {
            "type": "array",
            "items": {"type": "string", "enum": value},
            "minItems": len(value),
            "maxItems": len(value),
        }
    kind = (
        "boolean" if isinstance(value, bool) else "integer" if isinstance(value, int) else "string"
    )
    return {"type": kind, "enum": [value]}


def document_parts(document):
    parts = [document["title"]]
    for block in document["blocks"]:
        if block["kind"] in {"heading", "paragraph"}:
            parts.append(block["text"])
        elif block["kind"] == "bullets":
            parts.extend(block["items"])
        else:
            parts.extend(cell for row in block["rows"] for cell in row)
    return parts


def normalized(text):
    return re.sub(r"\s+", "", text)


def verify_document(document, info):
    pages = info["pages"]
    text = normalized("".join(p["text"] for p in pages))
    cursor = 0
    missing = []
    for part in document_parts(document):
        found = text.find(normalized(part), cursor)
        if found < 0:
            missing.append(part[:160])
        else:
            cursor = found + len(normalized(part))
    checks = [
        {"name": "all_content_in_order", "passed": not missing, "missing": missing},
        {"name": "within_page_bounds", "passed": all(p["outside_chars"] == 0 for p in pages)},
        {"name": "readable_text", "passed": all(p["small_chars"] == 0 for p in pages)},
        {
            "name": "a4_pages",
            "passed": all(
                abs(p["width"] - 595.276) < 1 and abs(p["height"] - 841.89) < 1 for p in pages
            ),
        },
        {"name": "complete_inspection", "passed": all(not p["text_truncated"] for p in pages)},
    ]
    return {"passed": all(c["passed"] for c in checks), "checks": checks}


def verify_merge(inputs, output):
    expected = [p for info in inputs for p in info["pages"]]
    actual = output["pages"]
    keys = ("width", "height", "rotation", "text", "render_sha256")
    checks = [
        {
            "name": "all_pages_preserved_in_order",
            "passed": len(expected) == len(actual)
            and all(all(a[k] == b[k] for k in keys) for a, b in zip(expected, actual, strict=True)),
        }
    ]
    return {"passed": all(c["passed"] for c in checks), "checks": checks}
