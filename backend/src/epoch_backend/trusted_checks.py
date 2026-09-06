"""Developer-owned release criteria; never registered as executor tools.

Checks inspect committed simulated state, not claims in executor responses.
Runtime repair does not exist yet; filesystem isolation is a later requirement.
"""

import json
import re
from hashlib import sha256

EVALUATOR_VERSION = "release-state-v2"


def release_criteria(project_id: str, release: str, scenario: str) -> dict:
    items = ["Smoke tests pass", "Rollback plan reviewed", "Release notes approved"]
    if project_id != "demo":
        items = [
            f"{project_id} integration tests pass",
            f"{project_id} recovery drill reviewed",
            f"Release {release} change log approved",
        ]
    return {
        "expected_items": items,
        "qa_channel": f"#qa-{project_id}",
        "qa_owner": "Avery Shah" if project_id == "demo" else "Morgan Chen",
        "ticket_title": f"Release {project_id} {release}",
        "checklist_title": f"Release checklist {release}",
        "require_qa_owner": scenario == "missing_lookup",
        "evaluator_version": EVALUATOR_VERSION,
    }


def evaluate_release(metadata: dict, snapshot: dict, state_event_ids: list[str]) -> dict:
    """Require one coherent ticket/checklist/message chain for the requested release."""
    project = metadata["project_id"]
    release = metadata["release"]
    tickets = [
        ticket
        for ticket in snapshot["tickets"]
        if ticket["project_id"] == project
        and ticket["release"] == release
        and ticket["title"] == metadata["ticket_title"]
    ]
    ticket_ids = {ticket["id"] for ticket in tickets}
    checklists = [
        checklist
        for checklist in snapshot["checklists"]
        if checklist["project_id"] == project
        and checklist["ticket_id"] in ticket_ids
        and checklist["title"] == metadata["checklist_title"]
        and len(checklist["items"]) == len(metadata["expected_items"])
        and set(checklist["items"]) == set(metadata["expected_items"])
    ]
    linked_pairs = {
        (ticket["url"], checklist["url"])
        for ticket in tickets
        for checklist in checklists
        if checklist["ticket_id"] == ticket["id"]
    }
    messages = [
        message
        for message in snapshot["messages"]
        if message["channel"] == metadata["qa_channel"]
        and message["project_id"] == project
        and re.search(
            r"(?<![A-Za-z0-9.])" + re.escape(release) + r"(?![A-Za-z0-9]|\.[A-Za-z0-9])",
            message["text"],
        )
        and any(set(pair) <= set(message["links"]) for pair in linked_pairs)
    ]
    definitions = [
        (
            "release_ticket",
            "Requested release ticket exists",
            bool(tickets),
            {"matching_object_ids": [item["id"] for item in tickets]},
        ),
        (
            "release_checklist",
            "Correct checklist is linked to that ticket",
            bool(checklists),
            {"matching_object_ids": [item["id"] for item in checklists]},
        ),
        (
            "qa_notification",
            "QA receives the release notice with both matching links",
            bool(messages),
            {"matching_object_ids": [item["id"] for item in messages]},
        ),
    ]
    if metadata["require_qa_owner"]:
        matching = [item for item in messages if metadata["qa_owner"] in item["text"]]
        definitions.append(
            (
                "qa_owner",
                "QA notification identifies the directory owner",
                bool(matching),
                {"matching_object_ids": [item["id"] for item in matching]},
            )
        )
    checks = [
        {
            "id": check_id,
            "name": name,
            "passed": passed,
            "evidence_ids": state_event_ids,
            "details": details,
        }
        for check_id, name, passed, details in definitions
    ]
    return {
        "simulated": True,
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
        "evaluator_version": EVALUATOR_VERSION,
        "criteria_sha256": metadata["criteria_sha256"],
        "state_sha256": sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest(),
        "missing_evidence": [] if state_event_ids else ["No state mutation events recorded."],
    }
