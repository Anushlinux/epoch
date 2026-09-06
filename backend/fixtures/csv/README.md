# CSV import sandbox

This is a runnable local simulation. It exposes an actual import adapter, strict
customer service, persisted customers/import attempts and fixed trusted checks.
Hermes discovers four customer tools through the usual MCP facade. There are no
release tools in a CSV conversation.

## Test in the product

1. Restart the backend with your existing configuration and refresh the frontend.
2. Open `/chat` and choose **New chat**.
3. Set **Environment** to **CSV import · broken adapter**.
4. Click **Use sample task**, then **Send message**. Selecting the environment or
   filling the task does not execute anything.
5. Wait for Hermes to call the import tool. Expand the customer evidence panel.
   Expect **Actually saved: 0**, a `missing_email` service rejection, and the
   original-customer check marked failed. Other checks can pass: a rejected batch
   should leave no partial customers or duplicates.
6. Click **Debugger** for that conversation. Ask:

   > Why did this import fail against the original customer requirements? Compare
   > the captured input, outgoing request and service error. Cite the evidence,
   > identify the responsible component, and explain the next change to test.

7. Click **Investigate conversation** for a diagnosis without execution. Then click
   **Verify and apply fix** in **Apply a verified fix**. For the supported sample
   failure, Luna proposes a field mapping from the captured evidence. The host tests it, runs
   Hermes on the unchanged original request and a fresh CSV in separate stores,
   then publishes only a passing mapping. Hermes retries in this conversation.
   The result distinguishes publication from actual customer-import completion.
   Incorrect candidates remain rejected; cancellation before publication leaves
   the current environment unchanged. This can take several minutes.
8. For comparison, start a separate new chat with **CSV import · healthy control**.
   Use the same sample task. Expect exactly three saved customers and all customer
   checks passing. Repeat the import and confirm the saved count remains three.

A conversation's selected scenario is immutable. Verified repairs update the
broken scenario's adapter mapping and tool description without switching to the
healthy control. Start a new broken-scenario chat in the same project to use the
published mapping with an empty customer store. Other projects and healthy
controls are independent. The healthy control remains developer-written.

The sample CSV already has `email`; the faulty adapter emits `emailAddress` to a
service requiring `email`. Repairing the outgoing mapping fixes the actual
defect. No CSV source, service validation, success criterion, or Hermes system
prompt is rewritten. The candidate is a restricted data artifact interpreted by
trusted host code, not generated Python. It supports this field-mapping failure,
not arbitrary CSV headers or arbitrary tool repair.

Triggering remains explicit. Opening Debugger only reads state; Verify and apply fix can
now perform one proposal, two isolated Hermes checks, and one recovery call.
Luna is limited to 60 seconds; each Hermes verification/recovery has 20 turns and
300 seconds (at most 61 model requests including Luna, 960 seconds of inference
allowances). A null proposal or unsupported failure remains diagnosis-only.
This is environment adaptation, not model training.

Old rejected import keys return their original receipts forever. Hermes receives
a separately recorded continuation to rediscover tools and retry with a new key.
Saved customers still deduplicate by email. Publication alone never marks the
original task as completed; the customer checks run against actual stored state.

The fixed checks cover [customers.csv](customers.csv): Asha, Ravi and Meera with
names/emails preserved, no duplicate email identities and no partial writes from
rejected imports. They do not automatically change to certify a different dataset
or new chat instruction. No real CRM, email service or customer file is accessed.

## Verify without models

From `backend/`:

```sh
uv run --frozen python scripts/verify_csv_environment.py
```

This runs both real simulated adapters against temporary databases and checks
exact retries. It prints zero customers for the broken adapter and three for the
healthy control. [local-evidence.json](local-evidence.json) retains an actual run's
source criteria, wire payload, service results, receipts and trusted checks.
It contains synthetic customer data, not model-generated diagnoses.

## Actual repair acceptance

[repair-live-evidence.json](repair-live-evidence.json) records the passing September
6 run with actual Luna and Hermes inference: zero customers before repair, all
nine candidate checks passed, three customers after Hermes recovery, and three
customers in a new conversation using the saved mapping with no debugger action.
Original criteria and rejected receipts were preserved. The fresh verification
used two different customers, including a quoted name and a non-ASCII name.
Business effects remain simulated; this does not establish arbitrary tool repair.

To repeat with your configured model connections, from `backend/`:

```sh
uv run --frozen python scripts/verify_csv_repair.py --live --data-dir data/new-csv-repair-check
```

Choose a directory that does not exist. The harness preserves earlier attempts
and uses a separate project/customer store; it never changes ordinary runtime data.

## API and storage

Create a chat with `environment: csv_broken` or `environment: csv_healthy` on
`POST /api/chats`; omission retains standard tools. The environment is part of
creation idempotency and cannot change on retry. Send and investigate through the
existing chat endpoints. `GET /api/chats/{id}/environment` reads sample CSV,
customers, import history, captured events and host verification.

`POST /api/chats/{id}/debugger` now saves a diagnosis/proposal without applying it.
`POST /api/chats/{id}/csv-repair` starts verification and execution, with the same
`{client_request_id, question}` request shape (question is optional). Its operation
has `kind: debugger` and `action: repair`; exact retries retain the operation ID.
The environment response includes `repair_capability` with eligibility and a
human-readable blocked reason. If this field is absent, the frontend asks for a
backend restart and disables execution rather than assuming the feature exists.

Each CSV conversation has its own SQLite database under the existing
`EPOCH_DATA_DIR/chats/{id}/sandbox.sqlite3`. Old conversations and release databases
retain their data. Published mappings and rejected candidates persist under
`EPOCH_DATA_DIR/csv-repairs/versions.sqlite3`, with isolated verification databases
under each version directory. Existing broken chats select the project version
at their next send; new broken chats select it on creation. Tool discovery and
import receipts identify the version used. Debugger analysis exposes proposal,
verification results, publication, and recovery separately.

For host rollback, `POST /api/chats/{id}/csv-repair/rollback` with JSON
`{"expected_version": "the-active-version-UUID"}` requires idle,
resolved execution and a broken-scenario conversation. It selects the previous
project version (or the original broken adapter). Existing customers and import
receipts remain; other chats adopt the selected version at their next send. All
version records remain available. This endpoint is not an executor tool.

No new environment variables, dependencies, credentials, Docker
setup or manual database migration are required. Live Hermes/Luna inference still
uses your existing backend connections when you explicitly send or investigate.
