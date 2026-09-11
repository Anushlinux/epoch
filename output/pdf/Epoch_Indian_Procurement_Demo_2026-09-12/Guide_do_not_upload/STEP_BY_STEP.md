# Epoch: Indian procurement data-noise walkthrough

These are realistic **fictional demonstration documents**, with Indian names and locations. They are not quotations from real suppliers. Keep this guide outside the agent's uploads: it contains the expected answers. All four PDF pages were rendered and visually reviewed, and their text was extracted successfully. No Epoch application tests, server runs or model calls were performed while preparing the pack.

## 1. Understand the documents and expected answer

Kaveri Analytics Private Limited, Pune, needs 100 standard stackable visitor chairs. Priya Deshmukh's budget is **INR 145,000 including taxes and delivery**, with delivery within 10 calendar days and a 12-month warranty. Evaluate on **12 September 2026**.

| File | Contents | Delivered total |
|---|---|---:|
| `01_Purchase_Brief_Kaveri_Analytics.pdf` | Business task and requirements | Budget INR 145,000 |
| `02_Sahyadri_Current_Quotation_v2.pdf` | Arun Patil, Sahyadri Office Furnishings, Pune; quote SOF/KA/2026/091 v2, issued 10 September | INR 150,000 |
| `03_Malhar_Current_Quotation_v1.pdf` | Nikhil Rao, Malhar Workspace Solutions, Bengaluru; quote MWS/2026/214 v1, issued 9 September | INR 130,000 |
| `04_Sahyadri_Previous_Quotation_v1.pdf` | Sahyadri's older quote SOF/KA/2026/091 v1, issued 1 September; superseded by v2 | INR 110,000 |

Sahyadri's current amount is 100 × INR 1,400 + INR 10,000 delivery. Malhar's is 100 × INR 1,250 + INR 5,000 delivery. Taxes are included; do not add another tax amount. **Malhar qualifies; current Sahyadri exceeds budget by INR 5,000.** The obsolete INR 110,000 offer is the noise. Its original validity date does not override a later superseding quotation.

## 2. Upload and run in the existing UI

Use your normal backend and frontend, with your existing settings. In Epoch:

1. Click **New chat**. Open the **+** beside Hermes in the message composer.
2. Set **Tools → Documents**. Set **Project** to a new name, such as `kaveri-procurement-01`, **before uploading**. Remember it for later chats. A fresh project avoids an existing policy affecting this demonstration.
3. Click **Upload PDF** and select file 01. Uploading creates the conversation without running Hermes.
4. Expand **Files** below the conversation. Use **Upload PDF** three more times for files 02, 03 and 04. Check that all four appear. Do not press **Try Northstar example** or upload this guide.
5. Click **Conversation traces** at the top right. No completed message is needed to edit source metadata. Scroll to **Investigate noise and prevent recurrence → Source versions and approvals**. An empty execution list is normal at this point.

Set these annotations, clicking **Save source metadata** separately for each source before editing the next. They express your reviewed source authority; approval is not inferred merely from a filename.

| File | Version family | Version | Status | Approved by me | Always retain this source |
|---|---|---|---|---|---|
| 01 | `kaveri-purchase-2026-017` | `1` | current | Yes | Yes |
| 02 | `sahyadri-sof-ka-2026-091` | `2` | current | Yes | No |
| 03 | `malhar-mws-2026-214` | `1` | current | Yes | No |
| 04 | `sahyadri-sof-ka-2026-091` | `1` | superseded | No | No |

Leave Topics blank. The Sahyadri files must share a family; Malhar has its own. These annotations are established before either run; without an active policy, they do not automatically hide the old quotation. Saving metadata later deactivates an active policy.

Click **Back to conversation** and send:

> Evaluate these documents as of 12 September 2026. Call documents.list with purpose current, then use documents.read to read each returned source. Follow Kaveri Analytics' purchase brief: 100 standard stackable visitor chairs, maximum INR 145,000 including taxes and delivery to Pune, delivery within 10 calendar days, and a 12-month warranty. Compare the current approved quotations, calculate delivered totals, and recommend the cheapest qualifying supplier, or explain why none qualifies. Cite the PDF filename, source ID and quotation version supporting each supplier's figures. Show the decision and comparison in chat. Do not create a PDF, place an order or contact suppliers.

Save the answer and that message's trace. The old offer might cause a wrong recommendation, or Hermes might correctly ignore it. **A correct result despite noise demonstrates resilience; do not claim a failure occurred.** Either way, inspect which sources actually reached Hermes.

Optional clean baseline: before this main run, use a separate chat/project with files 01–03 and the same task. This costs an additional model run and is not required.

## 3. Investigate and approve a retrieval repair

Click the completed message's **View trace**. Under **Investigate noise and prevent recurrence → What went wrong?**, paste:

> Investigate obsolete quotation context in this run. Compare Sahyadri quotation SOF/KA/2026/091 versions 1 and 2, the recorded documents.list/documents.read results, the source annotations and Hermes' recommendation. Was the superseded INR 110,000 offer supplied or used? Cite the evidence. Distinguish obsolete-source exposure from a proven wrong recommendation; do not claim causation if Hermes ignored it correctly. If supported, propose preferring the approved current version for current procurement requests while preserving historical access and the purchase brief. This is a source-selection investigation, not a PDF-renderer investigation.

Click **Investigate with local model**. If it proposes **Prefer approved current versions**:

1. Select that suggestion and click **Review cleanup**.
2. Confirm the preview retains files **01, 02 and 03**, and excludes **only 04**, with file 02 as its replacement.
3. Check the displayed project and Documents scope; press **Apply filter**.

If there is no supported suggestion, stop and inspect the cited evidence and metadata. The button is conditional; do not manufacture a finding or apply unrelated deduplication. These versions have different contents.

## 4. Prove the change in a fresh conversation

1. Click **New chat → + → Tools: Documents** and set the **same project** `kaveri-procurement-01` before uploading.
2. Upload the same four unchanged PDF files. Metadata can carry across chats by matching content hashes in this scope. Do not resave annotations after activation. Check that the active policy and inherited labels are present when opening conversation traces.
3. Send the **identical task from section 2**. This fresh chat excludes the previous answer from its history.
4. Open **View trace → Actual context delivered · recent decisions → documents.list → Load supplied context and selection**. Confirm current retrieval retained three sources, excluded 04 as superseded, and recorded the active policy. Check subsequent reads and the answer: Malhar, INR 130,000.
5. Send a variation:

> For this request only, override the brief's budget with INR 125,000 inclusive of taxes and delivery. Call documents.list with purpose current again and read the returned current quotations. Keep every other requirement unchanged. Does any supplier qualify? Cite the current totals. Do not create a PDF or place an order.

Expected: **neither supplier qualifies**. This checks reusable selection rather than a memorized recommendation.

For history, send:

> Call documents.list with purpose historical. Read Sahyadri quotation SOF/KA/2026/091 version 1 and report its original delivered total and how it differs from version 2. This is a historical comparison, not permission to buy at the old price.

Expected: the old INR 110,000 offer remains accessible. Finally, use **Undo filter** in the trace workspace and request a fresh `documents.list` with `purpose current`; all four sources should reappear.

Acceptance checklist: observed source selection changed; required sources remained; arithmetic and citations were correct; the changed-budget answer was correct; history and Undo worked. Save before/after traces as evidence. Files are never deleted, and prior messages/direct source reads remain available. This is user-approved retrieval repair; PDF generation and any renderer repair are separate demonstrations. There is no automatic clean-rerun or generic task-correctness checker in this flow.


## 5. Optional PDF-output stage

Only after checking the comparison and recommendation, ask:

> Create a purchase recommendation PDF from the current approved quotations and the original INR 145,000 budget. Include the comparison, arithmetic, selected supplier, delivery, warranty, budget headroom, and filename/quotation/version citations. Preserve every section in the output. Do not place an order or contact a supplier.

Inspect the actual saved PDF. If the comparison is correct but sections are missing
from the PDF, capture that tool's trace and use the existing PDF Debugger workflow.
Context filtering does not repair rendering. Do not label a PDF-output defect as data
noise. Tool repair retains its own authorization and verification requirements.

Pack layout: upload only the four files inside `PDFs_to_upload`. Keep everything in
`Guide_do_not_upload` outside the agent's document collection. The JSON reference contains
expected results and original content hashes for your review, not agent input.
