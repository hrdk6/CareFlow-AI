"""Download a slice of NIH ChestX-ray14 (the parquet mirror) into ml/data/raw/cxr/.

    uv run --project backend python -m ml.data.download_cxr

The full release is 112,120 films and about 42 GB. Eleven shards - roughly 13,000 films - are enough to
fit linear heads on frozen features and to hold out a patient-disjoint test set with usable positive
counts, and they download in a few minutes. Pass --train/--test to take more.

Dataset: Wang et al., "ChestX-ray8: Hospital-scale Chest X-ray Database and Benchmarks on Weakly-Supervised
Classification and Localization of Common Thorax Diseases", CVPR 2017. Released by the NIH Clinical Center
for research use; the labels are NLP-mined from radiology reports, not radiologist re-reads.
"""
import argparse
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = "BahaaEldin0/NIH-Chest-Xray-14"
RAW = Path(__file__).resolve().parent / "raw" / "cxr"
TRAIN_SHARDS, TEST_SHARDS = 73, 10


def _download(name: str) -> Path:
    from huggingface_hub import hf_hub_download

    for attempt in range(6):
        try:
            return Path(hf_hub_download(repo_id=REPO, filename=name, repo_type="dataset", cache_dir=str(RAW)))
        except PermissionError:  # several threads racing for the same refs/ file on Windows
            time.sleep(1 + attempt)
    raise RuntimeError(f"could not download {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=int, default=8, help=f"train shards to fetch (max {TRAIN_SHARDS})")
    parser.add_argument("--test", type=int, default=3, help=f"test shards to fetch (max {TEST_SHARDS})")
    args = parser.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    names = [f"data/train-{i:05d}-of-{TRAIN_SHARDS:05d}.parquet" for i in range(min(args.train, TRAIN_SHARDS))]
    names += [f"data/test-{i:05d}-of-{TEST_SHARDS:05d}.parquet" for i in range(min(args.test, TEST_SHARDS))]
    _download("README.md")  # resolves the revision once, so the parallel downloads below cannot race
    print(f"Downloading {len(names)} shards (~{len(names) * 0.48:.1f} GB) into {RAW} ...")
    with ThreadPoolExecutor(max_workers=4) as pool:
        for path in pool.map(_download, names):
            print(f"  {path.name}")
    print("Done. Next: python -m ml.preprocessing.nih_cxr")


if __name__ == "__main__":
    main()
