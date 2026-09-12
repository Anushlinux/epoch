"""Check model recommendations against supplied evidence, never activate them."""

import re

SOURCE_VALIDATION_VERSION = "source-quotes-v2"
OMISSION_MARKER = "[Excerpt: intervening source text omitted]"


def normalized_quote(value):
    """Permit extraction whitespace changes, not invented or rewritten quotations."""
    return " ".join(value.split()) if isinstance(value, str) else ""


def resolve_source_quote(text, quote, *, pdf_layout=False):
    """Return the actual source slice; PDF layout may differ only in word spacing."""
    quoted = normalized_quote(quote)
    if not quoted or "[excerpt:" in quoted.casefold() or not isinstance(text, str):
        return None
    # The snapshot's synthetic separators are not authored by the source. Match
    # within a single actual passage, never within or across an omission marker.
    passages, offset = [], 0
    for passage in text.split(OMISSION_MARKER):
        passages.append((offset, passage))
        offset += len(passage) + len(OMISSION_MARKER)
    pattern = re.compile(r"\s+".join(re.escape(token) for token in quoted.split()))
    for offset, passage in passages:
        match = pattern.search(passage)
        if match:
            original = match.group()
            return {"text": original, "start": offset + match.start(), "end": offset + match.end(),
                    "method": "exact" if original == quote.strip() else "whitespace_normalized"}
    if not pdf_layout:
        return None
    needle = "".join(quoted.split())
    # Tiny fragments cannot establish a reliable PDF layout match.
    if len(needle) < 24:
        return None
    quote_positions = [index for index, char in enumerate(quoted) if not char.isspace()]
    matches = []
    for offset, passage in passages:
        positions = [index for index, char in enumerate(passage) if not char.isspace()]
        compact = "".join(passage[index] for index in positions)
        cursor = 0
        while (found := compact.find(needle, cursor)) >= 0:
            start, end = positions[found], positions[found + len(needle) - 1] + 1
            # Word joins can lose spaces in extraction. Do not reinterpret digit
            # grouping (e.g. "12 34" vs "1 234") as equivalent evidence.
            valid_spacing = all(
                not (needle[index - 1].isdigit() and needle[index].isdigit())
                or ((positions[found + index] > positions[found + index - 1] + 1)
                    == (quote_positions[index] > quote_positions[index - 1] + 1))
                for index in range(1, len(needle)))
            if valid_spacing:
                matches.append({"text": passage[start:end], "start": offset + start,
                                "end": offset + end, "method": "pdf_layout"})
                if len(matches) > 1:
                    return None
            cursor = found + 1
    return matches[0] if matches else None


def source_has_quote(text, quote):
    return resolve_source_quote(text, quote) is not None


def authority_protects(source, labels):
    label = labels.get(source["id"], {})
    if label.get("sha256") != source["sha256"]:
        return False
    return bool(label.get("inherited_metadata_conflict") or label.get("protected")
                or (label.get("approved") and label.get("status") == "current"))


def validate_source_actions(answer, snapshot, source_snapshot):
    """Return reviewable, hash-bound suggestions and reasons for rejected suggestions.

    Exact quotes establish that the proposed evidence was supplied. They do not prove
    the model's interpretation, a causal failure or authority to change retrieval.
    Semantic supersession remains a recommendation requiring the user's source review.
    """
    value = answer.model_dump() if hasattr(answer, "model_dump") else answer
    actions = value.get("source_actions", [])
    if not actions:
        return [], []
    if value.get("outcome") != "context_noise":
        return [], ["Document exclusions require a context-noise finding; no document suggestion was accepted."]
    catalog = {source["id"]: source for source in source_snapshot.get("sources", [])}
    labels = source_snapshot.get("labels", {})
    supplied = {}
    ambiguous = set()
    for document in snapshot.get("source_documents", []):
        identity = document.get("source_id")
        if identity in supplied:
            ambiguous.add(identity)
        supplied[identity] = document
    exposed = set(snapshot.get("exposed_source_ids", []))
    evidence = {item["id"] for item in snapshot.get("evidence", [])}
    proposals, warnings = [], []
    for index, action in enumerate(actions[:8], 1):
        prefix = f"Document suggestion {index} was not offered: "
        source = catalog.get(action.get("source_id"))
        replacement = catalog.get(action.get("replacement_id"))
        if not source or not replacement:
            warnings.append(prefix + "both documents must belong to this conversation's authorized sources.")
            continue
        if source["id"] == replacement["id"]:
            warnings.append(prefix + "a document cannot replace itself.")
            continue
        if source["id"] not in exposed:
            warnings.append(prefix + "the excluded document was not observed in this trace's delivered context.")
            continue
        documents = [supplied.get(item["id"]) for item in (source, replacement)]
        if any(item["id"] in ambiguous for item in (source, replacement)) or any(not item for item in documents):
            warnings.append(prefix + "unambiguous content for both documents was not supplied to the investigator.")
            continue
        if any(document.get("sha256") != item["sha256"] or document.get("kind") != item["kind"]
               for document, item in zip(documents, (source, replacement))):
            warnings.append(prefix + "document identities changed or do not match the supplied evidence.")
            continue
        if source["kind"] != replacement["kind"]:
            warnings.append(prefix + "the replacement is a different source kind.")
            continue
        source_label = labels.get(source["id"], {})
        replacement_label = labels.get(replacement["id"], {})
        source_label = source_label if source_label.get("sha256") == source["sha256"] else {}
        replacement_label = replacement_label if replacement_label.get("sha256") == replacement["sha256"] else {}
        if source_label.get("inherited_metadata_conflict") or replacement_label.get("inherited_metadata_conflict"):
            warnings.append(prefix + "inherited annotations for one of these documents conflict; no authority was guessed.")
            continue
        if authority_protects(source, labels):
            warnings.append(prefix + "the document is explicitly protected or approved as current.")
            continue
        if (replacement_label.get("status") == "superseded" or
                (source_label.get("family") and replacement_label.get("family")
                 and source_label["family"] != replacement_label["family"])):
            warnings.append(prefix + "the replacement conflicts with reviewed document metadata.")
            continue
        reason = action.get("reason")
        equal_content = source["sha256"] == replacement["sha256"]
        if reason not in {"superseded", "duplicate"} or (reason == "duplicate") != equal_content:
            warnings.append(prefix + "the claimed relationship does not match the document content identities.")
            continue
        if reason == "duplicate" and source_label and replacement_label and any(
                source_label.get(key) != replacement_label.get(key)
                for key in ("family", "version", "status", "approved", "topics")):
            warnings.append(prefix + "identical content has conflicting reviewed authority or topic metadata.")
            continue
        citations = set(action.get("evidence_ids", []))
        if not citations or citations - evidence or any(document.get("evidence_id") not in citations for document in documents):
            warnings.append(prefix + "the suggestion must cite the supplied content evidence for both documents.")
            continue
        quotes = [action.get("source_quote"), action.get("replacement_quote")]
        matches = [resolve_source_quote(document.get("text"), quote, pdf_layout=document.get("kind") == "pdf")
                   for quote, document in zip(quotes, documents)]
        if any(match is None for match in matches):
            warnings.append(prefix + "a quote could not be matched to a source passage, including PDF word spacing; changed text, ambiguous matches and omission markers are not accepted.")
            continue
        proposals.append({"id": f"P{index}", "source_id": source["id"],
            "source_sha256": source["sha256"], "source_kind": source["kind"], "source_name": source["name"],
            "replacement_id": replacement["id"], "replacement_sha256": replacement["sha256"],
            "replacement_kind": replacement["kind"], "replacement_name": replacement["name"],
            "reason": reason, "explanation": action["explanation"], "evidence_ids": sorted(citations),
            "source_quote": matches[0]["text"], "replacement_quote": matches[1]["text"],
            "model_source_quote": quotes[0], "model_replacement_quote": quotes[1],
            "quote_matches": {name: {key: match[key] for key in ("method", "start", "end")}
                              for name, match in zip(("source", "replacement"), matches)},
            "source_validation_version": SOURCE_VALIDATION_VERSION})
    # Evaluate the whole set before accepting any member. Reject both ends of a
    # chain/cycle rather than allowing response order to choose the surviving file.
    targets = {item["source_id"] for item in proposals}
    replacements = {item["replacement_id"] for item in proposals}
    counts = {}
    for item in proposals:
        counts[item["source_id"]] = counts.get(item["source_id"], 0) + 1
    accepted = []
    for item in proposals:
        if counts[item["source_id"]] != 1 or item["replacement_id"] in targets or item["source_id"] in replacements:
            warnings.append(f"Document suggestion {item['id']} was not offered: its replacement conflicts with another suggestion or forms a replacement chain.")
        else:
            accepted.append(item)
    return accepted, warnings
