"""Download the UCI Diabetes 130-US hospitals dataset (CC BY 4.0) into ml/data/raw/.

    uv run --project backend python -m ml.data.download
"""
import io
import urllib.request
import zipfile
from pathlib import Path

URL = "https://archive.ics.uci.edu/static/public/296/diabetes+130-us+hospitals+for+years+1999-2008.zip"
RAW = Path(__file__).resolve().parent / "raw"


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    target = RAW / "diabetic_data.csv"
    if target.exists():
        print(f"Already present: {target}")
        return
    print(f"Downloading {URL} ...")
    with urllib.request.urlopen(URL, timeout=120) as resp:
        payload = resp.read()
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        for name in zf.namelist():
            if name.endswith(".csv"):
                (RAW / Path(name).name).write_bytes(zf.read(name))
    print(f"Saved to {RAW}")


if __name__ == "__main__":
    main()
