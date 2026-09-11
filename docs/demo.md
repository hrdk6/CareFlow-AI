# End-to-end demo script

This walks through the complete demonstration from the specification. Every step uses the real system:
real database queries, trained models, the hybrid retrieval pipeline and (if configured) a real LLM.
All patients and documents are synthetic.

**Accounts** (password = `CAREFLOW_DEMO_PASSWORD`, default `CareFlow-Demo-2026`):
`admin@careflow.demo`, `dr.rao@careflow.demo` (General Medicine), `dr.mensah@careflow.demo` (Cardiology),
`nurse.kim@careflow.demo`, `reception@careflow.demo`.

**Demo patient:** **Evelyn Hart, P1024** — 67-year-old woman with type 2 diabetes, hypertension,
hyperlipidaemia and CKD stage 3; HbA1c rising 7.2% → 9.4% over 2½ years; eGFR falling 64 → 44 (metformin
reduced to the renal dose); three admissions in the past year; discharged 6 days ago to home health after
a hyperglycaemia admission, with insulin glargine increased from 10 to 16 units.

> To rehearse the "admin uploads documents" steps from an empty knowledge base, seed without documents:
> `python -m app.seed --reset` (omit `--with-documents`).

| # | Step | Where / what to do | What proves it works |
|---|---|---|---|
| 1 | Admin logs in | `/login` → admin | Administrator badge; Administration menu visible |
| 2 | Admin uploads demo documents | **Knowledge base** → *Upload* a file from `rag/corpus/dist/` (e.g. `diabetes_management_guideline.pdf`, doc type *guideline*, scope *clinical*, code `CF-GL-DM-01`) — or *Load demo corpus* for all of them | New row with status **uploading → processing → indexed** (the page polls) |
| 3 | Documents processed and indexed | Click the document | Chunk list with section paths (`4. Monitoring > 4.1 HbA1c monitoring`), page ranges; the Wi-Fi notice shows a **quarantined** chunk with the injection patterns detected |
| 4 | Doctor logs in | Sign out → `dr.rao@careflow.demo` | Dashboard: 118 accessible patients, today's clinic, recent discharges (P1024 first) |
| 5 | Doctor opens a patient | Search "P1024" in the top bar | Profile header with **penicillin / sulfonamide allergy** alerts and care team |
| 6 | History and timeline | *Overview* and *Timeline* tabs | Chronological events: admissions/discharges, metformin dose changes with reasons, critical glucose 435 mg/dL, HbA1c 9.4% |
| 7 | Readmission prediction | Overview right column or *Predictions* | **20.7 %** (1.8× base rate, above the 14.9 % alert threshold), SHAP bars led by "3 inpatient admissions in the prior year", model `readmission_30d@1.0.0`, timestamp |
| 8 | Estimated length of stay | Same | **5.1 days**, 80 % interval 2.2–9.3, actual stay 6.9 days, model version |
| 9 | "Summarize this patient's medical history." | *AI assistant* tab (or `/assistant` with the patient selected) | Route **SQL + LLM** |
| 10 | SQL data retrieved and summarised | Answer | Problems, medications, admissions, HbA1c/eGFR trends, treatment changes — each with **[R#]** record chips (click → record details in *Database records*) |
| 11 | "What does our diabetes guideline say about monitoring?" | Assistant | Route **RAG + LLM** |
| 12 | Hybrid retrieval + reranking | *Trace* panel | `vector + keyword candidates → passages`, reranker `ms-marco-MiniLM-L-6-v2`, stage latencies for vector search, keyword search, fusion, rerank |
| 13–14 | Answer with citations | Answer + *Document sources* | **[S#]** chips; clicking opens the exact passage, section, page, version and retrieval ranks |
| 15 | "Why is this patient's readmission risk high?" | Assistant | Route **SQL + ML + LLM** |
| 16 | ML + patient data + explanation | Answer + *Model output* | Probability, band, threshold, factors phrased as *"contributed toward a higher predicted risk"* (never causal), supporting admissions **[R#]**, model version; the answer notes the risk is *moderate/elevated* rather than "high" |
| 17 | "Compare this patient's treatment with our diabetes guideline." | Assistant | Route **SQL + RAG + LLM** |
| 18 | Combined answer | Answer | Current treatment and results from the record **[R#]** next to guideline passages **[S#]** on metformin renal dosing, SGLT2 inhibitors, basal insulin and monitoring |
| 19 | "Find similar historical patients." | Assistant or *Similar patients* tab | Route **SIMILARITY + SQL** |
| 20 | Authorized similar patients | Result | Neighbours within Dr. Rao's access only ("Searched only patients in your department or care"), similarity scores, shared diagnosis/medication groups |
| 21 | Historical patterns summarised | Answer | Cohort readmission rate, mean stay, common diagnoses and medications — labelled descriptive, not predictive |
| 22 | Unauthorized users cannot access restricted information | a) As Dr. Rao open `/patients/7` (P1007, a cardiology patient) → *"Patient not found or not accessible"*; ask the assistant "Summarize patient P1007" → refused. b) Ask "Is a Watchman left atrial appendage occlusion planned?" → Dr. Rao: insufficient information; **Dr. Mensah**: answer citing the P1007 cardiology letter. c) As **reception**, open P1024 → demographics only; ask "Summarize this patient's history" → tool calls shown as **denied**. d) As admin, *Administration → Audit log*, filter `denied` | Same 404 for missing and forbidden; denials audited |
| 23 | Prompt injection does not override instructions | Ask "What does the visitor facilities notice say about AI assistants?" | Warning: *"1 retrieved passage(s) were withheld because they contain instruction-like text (possible prompt injection): Visitor Facilities and Wi-Fi Notice"*; the answer does not list patients or change behaviour. Automated proof: `backend/tests/test_injection.py` |

## Timing expectations

* Structured and ML endpoints: 15–350 ms. Retrieval with reranking: ~1 s on CPU.
* **Extractive mode** (no LLM): whole AI answers in 0.1–2 s.
* **Local LLM through Ollama on a CPU-only laptop**: measured 80 s (`llama3:8b`) to 143 s (`gemma4:12b`,
  thinking disabled) for a document question; patient summaries with larger evidence take longer. Use a GPU, a smaller model, or the Anthropic provider for a responsive demo; if the LLM
  times out, the assistant shows the extractive answer with a warning instead of failing.
