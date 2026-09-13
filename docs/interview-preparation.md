# Interview Preparation — CareFlow AI

Use this as a study guide. Each answer ties a general concept to a concrete decision in this project,
because "here is what I built and why" is more convincing than a textbook definition.

---

## 0. The two-minute pitch

> CareFlow AI is a hospital information platform where PostgreSQL is the source of truth, ML models
> produce readmission-risk and length-of-stay estimates, a hybrid RAG pipeline answers questions from
> hospital documents with verifiable citations, and an LLM layer ties them together — but only over data
> the user is authorized to see. A deterministic router decides whether a question needs SQL, documents,
> models or similarity search; tools run with the caller's permissions; retrieved text is treated as
> untrusted data; and every citation is checked against what was actually retrieved. I trained the models
> on the public UCI diabetes readmission dataset with patient-grouped splits and calibration, measured
> leakage explicitly, and evaluated retrieval with a 48-question benchmark comparing vector, BM25, hybrid
> and reranked retrieval. It runs with a local model through Ollama, with Claude, or with no LLM at all.

Likely follow-ups: *Why not just give the LLM SQL access?* (§4.3) · *How do you know the citations are
real?* (§1.8) · *What were the model metrics and are they good?* (§2.7) · *What breaks at scale?* (§5).

---

## 1. RAG

### 1.1 RAG vs fine-tuning
RAG supplies knowledge at query time; fine-tuning changes model weights. Use RAG when knowledge changes
(policies are versioned), must be cited, or must respect per-user access — all true here. Fine-tuning
suits style, format or domain language, not facts that change or need provenance. They combine: a model
fine-tuned for citation discipline can still retrieve. *In CareFlow:* a new guideline version is live the
moment it indexes; with fine-tuning it would need retraining and could not be cited or access-controlled.

### 1.2 Embeddings
Dense vectors where semantic similarity ≈ geometric closeness, produced by a bi-encoder trained
contrastively. Key choices: dimension/cost, max input length, symmetric vs asymmetric models (BGE adds a
query instruction), domain fit. *In CareFlow:* `bge-small-en-v1.5` (384-d) via ONNX — small, CPU-friendly,
strong on retrieval benchmarks; behind an `EmbeddingService` interface so it can be swapped (changing the
dimension requires a migration and re-index, which `app.rag.reindex` does).

### 1.3 Vector databases
An ANN index (HNSW, IVF) plus storage and filtering. HNSW = navigable small-world graph: fast, high
recall, memory-hungry; tune `m`, `ef_construction`, `ef_search`. *Why pgvector here:* one transactional
store; access predicates and metadata filters are ordinary SQL joins with the vector query; no dual-write
consistency problem. Known issue: filtered HNSW can return fewer than k results (post-filtering) — mitigated
with a larger `ef_search`; pgvector 0.8 adds iterative scans. A dedicated vector DB becomes attractive at
hundreds of millions of vectors or heavy multi-tenant filtering.

### 1.4 Hybrid retrieval
Run dense and sparse (BM25) retrieval and fuse. Dense handles paraphrase ("how often do people on insulin
check their sugar?"); sparse handles exact tokens (MED-POL-004, HbA1c, P1024). **RRF** fuses by rank
(`1/(k+rank)`), avoiding calibration of incomparable scores. *Evidence here:* BM25-only recall@5 on
paraphrase questions was 0.85 versus 1.0 for vector/hybrid.

### 1.5 Reranking
A cross-encoder scores (query, passage) jointly with full attention — much more accurate than cosine
similarity of independent embeddings, but O(n) model calls, so apply it to a shortlist (30 → 6). It also
yields an absolute relevance score, which enables abstention. *Evidence here:* context precision 0.62 →
0.84 and abstention 0.75 → 1.00, at ~0.8 s CPU latency.

### 1.6 Chunking
Trade-off between retrieval precision and context. Options: fixed windows, recursive splitting,
structure-aware (headings), semantic. Overlap preserves statements that straddle boundaries. *Here:*
section-aware chunks ≤ 220 words, 40-word sentence overlap, never crossing sections, plus a contextual
header (title + document code + section path) that fixed a policy-code retrieval miss.

### 1.7 Metadata filtering
Filters (doc type, department, version, patient, access scope) must be applied **inside** retrieval so
top-k is computed over allowed documents only. Post-filtering both leaks (the model or logs saw the text)
and hurts recall (top-k gets emptied). *Here:* the same SQL predicate gates vector search, the BM25
candidate set, reranking and source inspection.

### 1.8 Grounding & citations
Give the model evidence with stable ids, require inline citations, then **verify** them: every cited id
must exist in the evidence store, otherwise it is removed and a warning shown. Also let users open the
exact passage (document, version, section, page). Ask the model to say "insufficient information" and
detect that phrase.

### 1.9 Hallucination
Causes: missing/irrelevant context, over-eager generation, conflicting sources, long contexts.
Mitigations used here: abstain when nothing relevant is retrieved (don't call the LLM at all), reranker
relevance threshold, strict grounding rules, citation validation, typed evidence blocks (facts vs
predictions vs documents), low temperature, and an extractive fallback that cannot hallucinate.

### 1.10 RAG evaluation
Separate **retrieval** (recall@k, MRR, context precision) from **generation** (faithfulness, answer
correctness, citation correctness), include **unanswerable** questions, hold the generator fixed when
comparing retrievers, report latency, and avoid tuning on your test questions (I disclose that the
document-code header change was motivated by a benchmark miss). Scale up with LLM-as-judge on a sample,
spot-checked by humans.

---

## 2. Machine learning

### 2.1 Classification (readmission)
Predict P(readmitted ≤ 30 days | encounter). Pipeline: contract features → imputation/scaling/one-hot in
an sklearn `Pipeline` → candidate models → calibrated probability → threshold → risk band + SHAP factors.

### 2.2 Regression (LOS)
Predict days at admission. Metrics: MAE (interpretable in days), RMSE (penalises large errors), R²
(variance explained vs mean). Add an uncertainty interval — here from empirical residual quantiles, 79.9%
coverage for an 80% target.

### 2.3 Feature engineering
Translate raw data into signals that are *available at prediction time*: prior-year utilisation counts
(windowed at admission), ICD chapter grouping, lab result categories, medication-change flags. The
feature contract guarantees the DB→feature code produces the same columns and vocabularies as training.

### 2.4 Class imbalance
11.4% positives. Options: class weights, resampling (SMOTE), threshold moving, focal loss, better metrics.
I compared weighted vs unweighted models (little difference in ranking metrics), kept the unweighted one
for calibration, selected by PR-AUC and moved the threshold on validation. Accuracy would be meaningless
(always predicting "no" scores 88.6%).

### 2.5 Leakage
Information unavailable at prediction time or shared between train and test. Examples here: repeat
patients across splits (→ grouped split), labels fixed by death/hospice (→ excluded), and stay-time
features in an admission-time LOS model (ablation: R² 0.078 → 0.413 — too good to be true, and useless
in practice). Also: fit preprocessing on train only (the Pipeline does), never pick thresholds on test.

### 2.6 Model selection
Baseline first (prevalence / median). Compare a transparent model (logistic regression), bagging (random
forest) and boosting (XGBoost) on **validation**, then evaluate the chosen one **once** on test. Here RF
won PR-AUC by ~0.003 over XGBoost — within noise — so interpretability, latency or simplicity could
reasonably break the tie.

### 2.7 Precision / recall (and are the results good?)
Precision = of flagged, how many are true; recall = of true, how many flagged. At threshold 0.149 the
model has precision 0.237, recall 0.427, F1 0.305; ROC-AUC 0.685, PR-AUC 0.242 (baseline 0.12). That is
typical for this dataset — useful for *prioritising* follow-up calls, not for decisions. The threshold
should be set with clinicians from the relative costs of a missed readmission and an unnecessary call.

### 2.8 ROC-AUC vs PR-AUC
ROC-AUC = probability a random positive outranks a random negative; insensitive to prevalence and
flattered by many easy negatives. PR-AUC (average precision) focuses on the positive class and drops
sharply with false positives — the relevant view when positives are rare and alerts cost clinician time.

### 2.9 SHAP
Shapley values allocate a prediction's deviation from the base value across features additively and
consistently. TreeSHAP computes them exactly for tree ensembles in polynomial time. Caveats: they explain
the *model*, correlated features share credit arbitrarily, and they are not causal (here, a measured high
HbA1c *lowers* predicted risk — an association in the data, not a treatment effect). I sum one-hot
contributions back to the original feature and test additivity.

### 2.10 Similarity
Define a representation (weighted blocks of z-scored numerics, multi-hot diagnoses and medication
groups), a metric (cosine), an index (pgvector HNSW) and — hardest — a validation strategy without labels:
agreement on department/diagnoses vs random, and outcome concordance on a variable *not* in the vector.
Always restrict candidates to authorized patients and state that similarity ≠ same outcome.

---

## 3. LLMs

### 3.1 Tool calling
The model emits a structured call (name + JSON arguments); the application executes it and returns the
result; loop until a final answer. Principles here: offer only the tools the role may use; validate
arguments with Pydantic; authorize every call server-side against the real user; return errors as tool
results (malformed JSON → error message, not a crash); bound the loop (4 rounds); log names/status, not
data. The Anthropic provider replays assistant turns with their original content blocks (thinking +
tool_use), as the API requires.

### 3.2 Prompt construction
Stable system prompt (rules, citation format, safety, untrusted-data policy) → typed evidence blocks
(`<database_facts>`, `<ml_predictions>`, `<retrieved_documents trust="untrusted">`) → the user question in
`<user_query>`. Keeping trust levels in separate, labelled blocks makes the rules enforceable and makes
the stable prefix cacheable.

### 3.3 Context windows
Bigger windows do not remove the need for retrieval: cost and latency scale with tokens, and models
attend unevenly to long contexts. Budget the context: top-6 reranked chunks, capped record lists,
truncated notes. Put the most relevant evidence first; keep the question last.

### 3.4 Structured output
Use JSON schemas / constrained decoding when a program consumes the output (tool arguments here). For
prose answers I keep Markdown with citation tokens and post-validate, because clinicians read prose and
the validation layer enforces the contract that matters (citations exist).

### 3.5 Hallucination (LLM-side)
Grounding rules, low temperature, abstention phrase, citation validation, no-LLM path when evidence is
empty, and separation of predictions from facts in both the prompt and the UI.

### 3.6 Prompt injection
Any text the model reads can carry instructions (documents, tool output, user-uploaded files). Defence in
depth: (1) scan and quarantine suspicious chunks at ingestion; (2) neutralise delimiters and label
retrieved text as untrusted data; (3) system rules forbid following embedded instructions; (4) the
decisive control — **authorization outside the model**, so an obeyed injection still cannot reach
unauthorized data (there is a test where a scripted model "obeys" and is blocked); (5) validate outputs.
Detection alone is never sufficient.

---

## 4. Architecture

### 4.1 SQL vs RAG
Structured facts (ages, lab values, appointments) come from SQL — exact, current, joinable, auditable.
RAG is for unstructured text. Embedding structured records and "retrieving" them would lose precision,
freshness and access control.

### 4.2 Query routing
Deterministic rules first (instant, free, testable, injection-proof), LLM tool selection only for
unrecognised questions. Each route maps to a fixed tool plan, so "compare treatment with guideline" always
fetches the patient, their labs and guideline passages. Routes and latency per stage are logged.

### 4.3 Authorization
Authorization happens **before** data reaches the AI layer: RBAC permissions for capabilities,
row-level SQL predicates for which patients/documents. The LLM never gets SQL or unrestricted tools.
Non-accessible patients return the same 404 as missing ones (no enumeration); denials are audited.

### 4.4 ML/RAG integration
They answer different questions and meet in the evidence store: "Why is her risk high, and what does the
discharge policy say for high-risk patients?" runs SQL + ML (prediction + SHAP) + RAG (policy passages),
and the LLM synthesises with separate headings for record facts, model output and documents.

### 4.5 Scalability
Stateless API instances behind a load balancer; move ingestion to a queue; replace in-process BM25 with a
search engine; async/streaming LLM calls; prompt caching; read replicas and partitioned log tables;
precompute risk scores in batch for dashboards.

### 4.6 Model versioning
Artifacts are immutable and versioned with model cards (dataset hash, features, metrics, environment);
the active version is configuration; every prediction row references its model version; old versions
stay loadable for rollback and for explaining past predictions.

---

## 5. Production

* **Monitoring:** request latency by route, AI stage latency (retrieval, rerank, LLM, ML), token usage, degraded-component counters, denied-access events; ML drift monitoring (input distributions vs training, calibration over time) is the next addition.
* **Logging:** structured JSON with request ids; no bodies, no PHI; audit logs separate from application logs and written even when the request fails.
* **Latency:** measured per stage (reranking ~0.8 s CPU, local 12B LLM tens of seconds, everything else ~10–100 ms). Levers: fewer rerank candidates, GPU, smaller/faster LLM, streaming, caching.
* **Failures:** each dependency degrades independently — no embeddings → keyword search; no reranker → fused order + lexical gate; LLM down/timeout → extractive answer with a warning; missing model → 503 with guidance; ingestion error → document `failed` with a safe message.
* **Security:** Argon2id, JWT in httpOnly SameSite cookie + CSRF header, rate limiting, RBAC + row-level policy, upload validation, safe errors, audit trail, non-root containers.
* **Deployment:** Docker Compose (pgvector, backend with baked-in models and migrations-on-start, Next.js standalone). For production: managed Postgres, secrets manager, HTTPS, Kubernetes or ECS, CI running the 183-test suite and the RAG benchmark as a regression gate.

---

## 6. What I would do next / differently

* A clinician-labelled evaluation set and LLM-as-judge faithfulness scoring for generated answers.
* Fairness analysis of the readmission model across sex and age groups (calibration and error rates).
* Streaming responses and prompt caching; async LLM client.
* A job queue for ingestion; OCR for scanned PDFs.
* Break-glass access with mandatory justification and review.
* Drift monitoring and scheduled re-evaluation of models against newly accrued (synthetic) outcomes.
