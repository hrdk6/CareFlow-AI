# End-to-end demo script

This walks through the complete demonstration from the specification. Every step uses the real system:
real database queries, trained models, the hybrid retrieval pipeline and (if configured) a real LLM.
All patients and documents are synthetic.

**Accounts** (password = `CAREFLOW_DEMO_PASSWORD`, default `CareFlow-Demo-2026`):
`admin@careflow.demo`, `dr.rao@careflow.demo` (General Medicine), `dr.mensah@careflow.demo` (Cardiology),
`nurse.kim@careflow.demo`, `reception@careflow.demo`.

**Demo patient:** **Sunita Deshpande, P1024** — 67-year-old woman with type 2 diabetes, hypertension,
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

## Part 2 — the ward, the discharge and what leaves the building

These steps need no preparation beyond the seeded hospital. Steps 26-28 are the two-window demo: sign in as
the nurse in one window and the doctor in another.

| # | Step | Where / what to do | What proves it works |
|---|---|---|---|
| 24 | Privacy of prompts | After any assistant answer, open **Privacy** under the answer | "Before this question went to Groq, 1 name, 1 record number and 1 date of birth were replaced…", and *Show exactly what Groq received* prints the prompt with `PATIENT_1`, `MRN_1`, `DOB_1` highlighted. In extractive mode the panel is absent: nothing left the server |
| 25 | The ward at a glance | **Inpatients** (doctor or nurse) | Patients worst-NEWS2-first; each parameter shows the points it contributed; the sickest patient carries the rapid-response criteria from the Patient Safety Guidelines and the escalation the chart asks for; overdue observations are called out. A patient under 16 shows values but no risk band |
| 26 | Nurse records observations | As **nurse.kim**, *Record* on a patient → change respiration rate to 26, saturations to 91 %, tick oxygen | The NEWS2 panel updates **from the server** as you type: per-parameter points, band, and the response the chart requires |
| 27 | The board reacts | Keep **Inpatients** open as Dr. Rao in a second window while the nurse saves | The row updates within a second (server-sent events; "Live" in the header), the patient jumps to the top, and a line reports the new score |
| 28 | Access applies to the live feed | Do the same with **dr.mensah** (Cardiology) watching | No event arrives for a General Medicine patient: the stream is filtered per viewer |
| 29 | Prepare a discharge | As Dr. Rao, open an admitted patient → **Prepare discharge** | A draft in a few seconds: reconciliation (continued / changed / started / stopped / held, each with its reason), diagnoses, results, and the prose with `[R#]` chips |
| 30 | The checks are the hospital's own | Right-hand panels | Readmission screening (four criteria from the discharge policy, with the model estimate as one of them) and the pre-discharge checklist, each linked to the policy section — click `[S#]` to read the passage |
| 31 | The checker catches the model | Look for highlighted sentences | e.g. *"46-year-old female"* flagged because 46 is not in the records that sentence cites; *"day 8 of the stay"* flagged for having no source at all |
| 32 | Only a clinician writes to the record | **Review and sign** | Signing is blocked until each flagged sentence is edited, removed or confirmed; then *Records* shows the summary with "AI-assisted", who signed, how much was changed, and the sources behind each marker |
| 33 | Export as FHIR | Patient header → **Export as FHIR** | 300+ resources, the codes they carry (ICD-10-CM, LOINC, UCUM, WHO ATC, SNOMED CT), and the raw Patient resource. As reception, `/api/fhir/Patient/P1024/$everything` returns a FHIR `OperationOutcome` with `forbidden` |

## Part 3 — radiology

The seeded hospital ships 24 chest films. They are real DICOM objects built from held-out films of the
public NIH release, with invented identities in their headers so that ingestion has something to strip.

| # | Step | Where / what to do | What proves it works |
|---|---|---|---|
| 34 | The reading queue | **Radiology** (doctor or nurse) | Films ordered by the model's probability that the film shows anything, with what it raised, how long each has waited, and which patients are inpatients. A film the model did not score says so rather than looking normal |
| 35 | Read a film | *Read* on the first row | A real viewer: drag to window and level, scroll to zoom, shift-drag to pan, invert. The footer shows the window values, as a PACS would |
| 36 | What the model says, and how much to trust it | Right-hand panel | Each finding with its probability, its cut-off, the base rate, ROC-AUC with a 95% interval, and what the cut-off catches and clears. Note the wording: "not ruled out" at the 90%-sensitivity cut-off, "for attention" only above the higher one |
| 37 | Where it was looking | Click a finding | The class activation map appears over the film. It is exact, not an approximation: the head is linear on pooled features, so the map uses the same weights as the probability |
| 38 | What ingestion removed | **De-identified on arrival**, below the report | "9 identifying tags removed and 5 emptied…", and *Which tags* lists them. The file on disk has no patient name, accession, institution or device tag, and its dates are shifted |
| 39 | The radiologist writes the report | Type findings and an impression, answer *Did the model's flags match your read?*, **Sign report** | The report enters the medical record. Open **Records**: it is marked *Model shown* — not *AI-assisted* — because the model wrote none of the text, and the provenance records what it had flagged and that the reader agreed, partly agreed or disagreed |
| 40 | It is in the export too | Patient header → **Export as FHIR** | `ImagingStudy` (DICOM UIDs, SNOMED CT body site), `DiagnosticReport` with the impression as its conclusion, and a `RiskAssessment` carrying one prediction per finding |
| 41 | Upload one yourself | Patient → **Imaging** → *Add study* with any single-frame DICOM | The answer names how many identifying tags were removed before the file was written. A film that is not a frontal chest is stored and displayed, and explicitly not scored |
| 42 | The model card | **Model performance** → *Chest radiograph triage* | All fourteen findings with their intervals, including the six that are **not shown in the product** because they missed the bar, accuracy by sex, age band and view, and the age/sex/view-only baseline that shows the model is reading the chest and not the camera |

## Timing expectations

* Structured and ML endpoints: 15–350 ms. Retrieval with reranking: ~1 s on CPU.
* Ward board: ~15 ms of queries for a dozen inpatients (one windowed query covers every trend). A recorded
  observation reaches an open board in well under a second.
* Discharge draft: ~1.5 s with Groq (records 30 ms, policy 10 ms, readmission model 500 ms, prose ~900 ms);
  ~0.2 s once the model is warm with no language model at all, since the prose is then assembled from templates.
* FHIR `$everything` for the demo patient: ~270 ms for 341 resources.
* Scoring a chest film: ~60 ms once the backbone is loaded (about a second on the first film of a
  process). The name-finding pass adds a few hundred milliseconds to a prompt with free text in it.
* **Extractive mode** (no LLM): whole AI answers in 0.1–2 s.
* **Local LLM through Ollama on a CPU-only laptop**: measured 80 s (`llama3:8b`) to 143 s (`gemma4:12b`,
  thinking disabled) for a document question; patient summaries with larger evidence take longer. Use a GPU, a smaller model, or the Anthropic provider for a responsive demo; if the LLM
  times out, the assistant shows the extractive answer with a warning instead of failing.
