# NaviDoc AI: Automated Shipping Document Verification & Dashboard

A purpose-built frontend operations dashboard and verification studio engineered for maritime shipping and freight operations teams. This system tackles email triage fatigue, automates document cross-checking between Shipping Instructions (SI) and draft Bills of Lading (BL), normalizes semantic field variations, and escalates exceptions to human operators with complete context.

---

## 🎯 Direct Alignment with the Problem Statement

### 01 Classify
- **Unified Inbox Hub**: Categorizes inbound traffic into 6 message types:
  1. `Compare / Review` (Document checking requests — **only this type enters the checking pipeline**)
  2. `Prepare New SI` (Drafting queue)
  3. `Invoice Queries` (Demurrage disputes, detention charges routed to finance)
  4. `Returns / Equipment` (Depot empty return notices)
  5. `IT Requests`
  6. `Spam` (Quarantined)
- **NLP Confidence Scores**: Highlights classification certainty (e.g., `99.2% NLP Match`).

### 02 Extract
- **Attachment Extraction**: Pulls plain-text or PDF attachments, identifying:
  - **Reference Document (Ground Truth)**: Shipping Instruction (`SI`).
  - **Target Document**: Draft Bill of Lading (`Draft BL`).
- **Raw & Structured View**: Synchronized display of parsed raw lines alongside extracted structured entity models.

### 03 Compare (The 7 Mandatory Fields)
Automated table verification comparing Draft BL against reference SI across seven required fields:
1. **Shipper**: Entity normalization and address verification.
2. **Consignee**: Destination importer verification.
3. **Notify Party**: Normalized resolution of *"Same as Consignee"* vs specific logistics departments.
4. **Port of Loading (POL)**: Semantic alias resolution (e.g. automatically maps `"Load Port"` to `"Port of Loading"`, UN/LOCODE `SGSIN`).
5. **Port of Discharge (POD)**: Normalization of `"Discharge Port"` / `"Port of Discharge"`, UN/LOCODE `NLRTM`.
6. **Container Count**: Exact numerical quantity comparison.
   - *Problem Statement Test Case*: SI lists **2 containers**; BL lists **4 containers**. Flags container count mismatch with explicit badge: `SI: 2 | BL: 4`.
7. **Gross Weight (kg)**: Numeric check in kilograms with tolerance check (e.g. 22,000 kg).

**Report Outputs**:
- **Clean Match**: Displays **`"No mismatch detected"`** in bright green with instant one-click approval.
- **Discrepancy Found**: Flags only mismatched fields with reference values, e.g. `SI: 2 | BL: 4`.
- **Carrier Amendment Email Generator**: Pre-fills an amendment notice with exact diffs to send to the carrier with 1 click.

### 04 Ask for Help (Escalation)
- Never fails silently or guesses when confidence is below threshold or discrepancies are flagged.
- **Escalation Console**: Delivers full context (shipment metadata, original attachments, flagged fields, risk assessment).
- **Actionable Resolutions**:
  - *Enforce SI (Reference)*: Reject BL and require carrier to amend.
  - *Accept Draft BL*: Shipper authorized late booking update.
  - *Query Shipper*: Contact cargo owner for confirmation.
- Preserves complete internal audit log and operator rationale.

---

## 🚀 Running the Project

### Option A: Open the Interactive Generative UI Artifact (Instant, No Install)
Open the standalone, self-contained dashboard directly in any web browser or via the chat artifact viewer:
```
shipping_verification_dashboard.html
```

### Option B: Run the React + TypeScript Application
1. Open terminal in this folder:
   ```bash
   cd C:\Users\adibe\.gemini\antigravity\scratch\shipping-doc-verifier
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm run dev
   ```
4. Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## ⌨️ Productivity Keyboard Shortcuts
- `1`: Switch to Unified Inbox
- `2`: Switch to Verification Studio
- `3`: Switch to Escalation Queue
- `4`: Switch to Ops Analytics
- `E`: Open Escalation Modal (Step 04)
- `C`: Open Carrier Amendment Drafter
- `Hover` over any field in the 7-field table to cross-highlight exact matching lines in both SI and Draft BL documents.

---

## 📊 Operations Metrics & Analytics Included
- **Straight-Through Processing (STP) Rate**: 72.2% automated zero-touch approvals.
- **Discrepancy Breakdown by Field**: Highlighting Container Count (38%) and Gross Weight (27%) as top sources of carrier draft errors.
- **Carrier Draft Accuracy Leaderboard**: Rankings for Maersk, Hapag-Lloyd, MSC, and CMA CGM.
