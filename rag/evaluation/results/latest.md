# RAG evaluation (2026-09-11T18:30:33+00:00)

48 questions (44 answerable, 4 unanswerable); top-k = 6. Same extractive answer generator for every mode.

| Mode | R@1 | R@3 | R@5 | MRR | Ctx prec | Answer | Faithful | Cite prec | Cite hit | Abstain | p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| vector | 0.932 | 1.000 | 1.000 | 0.958 | 0.614 | 0.955 | 1.000 | 0.860 | 0.955 | 0.750 | 44 |
| keyword | 0.841 | 0.955 | 0.955 | 0.890 | 0.553 | 0.909 | 1.000 | 0.843 | 0.909 | 1.000 | 5 |
| hybrid | 0.909 | 0.977 | 1.000 | 0.945 | 0.621 | 0.955 | 1.000 | 0.828 | 0.955 | 0.750 | 36 |
| hybrid_rerank | 0.955 | 1.000 | 1.000 | 0.977 | 0.835 | 0.955 | 1.000 | 0.869 | 0.955 | 1.000 | 865 |

## Recall@5 by question category

| Category | vector | keyword | hybrid | hybrid_rerank |
|---|---|---|---|---|
| exact_term (n=28) | 1.00 | 1.00 | 1.00 | 1.00 |
| paraphrase (n=13) | 1.00 | 0.85 | 1.00 | 1.00 |
| patient_doc (n=1) | 1.00 | 1.00 | 1.00 | 1.00 |
| policy_code (n=2) | 1.00 | 1.00 | 1.00 | 1.00 |
