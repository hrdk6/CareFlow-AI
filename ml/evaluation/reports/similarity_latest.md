# Patient similarity evaluation (2026-09-11T11:32:07+00:00)

240 synthetic patients, k = 5, representation sim-v1 (32 dims). Overall 30-day readmission rate: 0.163.

| Variant | Dept agreement@k | Diagnosis Jaccard | Neighbour readmit rate (patient readmitted) | Neighbour readmit rate (not readmitted) |
|---|---|---|---|---|
| weighted_cosine (deployed) | 0.870 | 0.913 | 0.3077 | 0.1085 |
| unweighted_cosine | 0.780 | 0.782 | 0.4256 | 0.1005 |
| weighted_euclidean | 0.877 | 0.918 | 0.2513 | 0.0915 |
| random_baseline | 0.305 | 0.350 | 0.1385 | 0.1522 |

Synthetic demo data; proxies for similarity quality, not clinical validation.
