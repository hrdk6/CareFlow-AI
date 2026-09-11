# RAG evaluation (2026-09-11T11:32:06+00:00)

48 questions (44 answerable, 4 unanswerable); top-k = 6. Same extractive answer generator for every mode.

| Mode | R@1 | R@3 | R@5 | MRR | Ctx prec | Answer | Faithful | Cite prec | Cite hit | Abstain | p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| vector | 0.932 | 1.000 | 1.000 | 0.966 | 0.617 | 0.955 | 1.000 | 0.868 | 0.955 | 0.750 | 30 |
| keyword | 0.795 | 0.909 | 0.955 | 0.855 | 0.534 | 0.909 | 1.000 | 0.824 | 0.909 | 1.000 | 5 |
| hybrid | 0.932 | 0.977 | 1.000 | 0.960 | 0.610 | 0.955 | 1.000 | 0.834 | 0.955 | 0.750 | 32 |
| hybrid_rerank | 0.909 | 0.977 | 0.977 | 0.939 | 0.824 | 0.955 | 1.000 | 0.864 | 0.955 | 1.000 | 734 |

## Recall@5 by question category

| Category | vector | keyword | hybrid | hybrid_rerank |
|---|---|---|---|---|
| exact_term (n=28) | 1.00 | 1.00 | 1.00 | 1.00 |
| paraphrase (n=13) | 1.00 | 0.85 | 1.00 | 1.00 |
| patient_doc (n=1) | 1.00 | 1.00 | 1.00 | 1.00 |
| policy_code (n=2) | 1.00 | 1.00 | 1.00 | 0.50 |
