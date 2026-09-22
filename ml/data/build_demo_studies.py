"""Build the demo radiology studies that ship with the repository.

    uv run --project backend python -m ml.data.build_demo_studies [--count 24]

Films are taken from the HELD-OUT test split of NIH ChestX-ray14 - never from the films the triage heads
were fitted on - and written as real DICOM Part 10 objects so the viewer, the de-identification and the
FHIR ImagingStudy export all work on genuine DICOM rather than on PNGs with a story attached.

The headers are deliberately dirty: each file carries an invented patient name, an invented hospital, a
referring physician, an accession number and a private tag, exactly as a file arriving from another
hospital's PACS would. None of those identities belong to a person; they exist so that ingestion has
something real to strip, and so the demo can show which tags were removed.

Selection is stratified by finding and seeded, and happens before any model runs: the demo set is not
chosen to flatter the model, and the demo script names the films it gets wrong.
"""
import argparse
import io
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from ml.preprocessing.nih_cxr import FINDINGS, build, grouped_split, shard_paths
from ml.training.common import SEED

OUT = Path(__file__).resolve().parent / "demo_studies"
# Invented header identities, so ingestion has real tags to remove. No connection to any person.
HEADER_NAMES = ["PRIOR^ALEX", "VANCE^MORGAN", "HOLLOWAY^SAM", "REDFERN^JODIE", "OKONKWO^CHIKA",
                "BARTLETT^ROWAN", "FENNIMORE^DALE", "IRETON^KIM"]
SENDING_SITES = [("Riverside Imaging Centre", "CR-2100", "SIEMENS"),
                 ("Northgate Chest Clinic", "DX-7", "CARESTREAM"),
                 ("St Elmo Diagnostics", "DRX-Revolution", "GE MEDICAL SYSTEMS")]
# Findings to spread the demo across: the ones a triage tool is plausibly used for, plus normals.
STRATA = ["__normal__", "Effusion", "Cardiomegaly", "Edema", "Consolidation", "Pneumothorax",
          "Atelectasis", "Infiltration", "Mass", "Nodule"]


def _pixels_for(names: set[str]) -> dict[str, bytes]:
    """Fetch the original PNG bytes for the chosen films, one pass over the shards."""
    import pyarrow.parquet as pq

    found: dict[str, bytes] = {}
    for path in shard_paths():
        table = pq.read_table(path, columns=["image"])
        for image in table.column("image").to_pylist():
            name = Path(image.get("path") or "").name
            if name in names and name not in found:
                found[name] = image["bytes"]
        if len(found) == len(names):
            break
    return found


def _choose(data, test: np.ndarray, count: int) -> list[int]:
    """Stratified, seeded, and blind to the model: pick films per finding and a block of normals."""
    rng = np.random.default_rng(SEED)
    indices = np.flatnonzero(test)
    chosen: list[int] = []
    per_stratum = max(1, count // len(STRATA))
    for stratum in STRATA:
        if stratum == "__normal__":
            pool = indices[data.labels[indices].sum(axis=1) == 0]
            take = count - per_stratum * (len(STRATA) - 1)
        else:
            column = FINDINGS.index(stratum)
            pool = indices[data.labels[indices][:, column] == 1]
            take = per_stratum
        pool = np.array([i for i in pool if i not in set(chosen)])
        if len(pool):
            chosen.extend(rng.choice(pool, size=min(take, len(pool)), replace=False).tolist())
    return chosen[:count]


def _dicom(pixels: np.ndarray, *, index: int, age: int, sex: str, view: str, taken: date):
    """Write one Digital X-Ray Image Storage object, headers and all."""
    from pydicom.dataset import Dataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid

    site, model, manufacturer = SENDING_SITES[index % len(SENDING_SITES)]
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.1.1"  # Digital X-Ray Image Storage - For Presentation
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.ImplementationVersionName = "CAREFLOW_DEMO"

    ds = Dataset()
    ds.file_meta = meta
    ds.SOPClassUID = meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID, ds.SeriesInstanceUID = generate_uid(), generate_uid()
    # --- the identifying header a real export would carry (all invented) ---
    ds.PatientName = HEADER_NAMES[index % len(HEADER_NAMES)]
    ds.PatientID = f"RX-{100000 + index * 37}"
    ds.PatientBirthDate = (taken - timedelta(days=int(age * 365.25))).strftime("%Y%m%d")
    ds.AccessionNumber = f"ACC{2026000 + index}"
    ds.ReferringPhysicianName = "SHARMA^R"
    ds.PerformingPhysicianName = "LOWE^T"
    ds.InstitutionName = site
    ds.InstitutionAddress = "12 Mill Lane, Riverside"
    ds.StationName = f"{model}-{index % 4 + 1}"
    ds.DeviceSerialNumber = f"SN{700000 + index}"
    ds.StudyDescription = "CHEST PA/AP"
    ds.add_new(0x00090010, "LO", "ACME_PRIVATE_BLOCK")  # a private tag, to prove private tags are dropped
    # --- clinical header, which survives de-identification ---
    ds.PatientSex = sex
    ds.PatientAge = f"{age:03d}Y"
    ds.Modality = "DX"
    ds.BodyPartExamined = "CHEST"
    ds.ViewPosition = view
    ds.Manufacturer = manufacturer
    ds.ManufacturerModelName = model
    ds.StudyDate = ds.SeriesDate = ds.ContentDate = taken.strftime("%Y%m%d")
    ds.StudyTime = ds.SeriesTime = ds.ContentTime = "081500"
    ds.SeriesNumber, ds.InstanceNumber = 1, 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.SamplesPerPixel = 1
    ds.Rows, ds.Columns = pixels.shape
    ds.BitsAllocated = ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.WindowCenter, ds.WindowWidth = 128.0, 256.0
    ds.PixelData = pixels.tobytes()
    return ds


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=24)
    args = parser.parse_args()

    from PIL import Image

    data = build()
    _, _, test = grouped_split(data.patient_id, seed=SEED)
    chosen = _choose(data, test, args.count)
    blobs = _pixels_for({str(data.image[i]) for i in chosen})
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("*.dcm"):
        stale.unlink()

    manifest = []
    today = date.today()
    for n, i in enumerate(sorted(chosen, key=lambda i: str(data.image[i])), start=1):
        name = str(data.image[i])
        pixels = np.asarray(Image.open(io.BytesIO(blobs[name])).convert("L"), dtype=np.uint8)
        taken = today - timedelta(days=3 + n % 11)
        ds = _dicom(pixels, index=n, age=int(data.age[i]), sex=str(data.sex[i]), view=str(data.view[i]),
                    taken=taken)
        filename = f"cxr-{n:03d}.dcm"
        ds.save_as(OUT / filename, enforce_file_format=True)
        manifest.append({
            "file": filename, "source_image": name,
            "reference_findings": [f for k, f in enumerate(FINDINGS) if data.labels[i][k]],
            "age": int(data.age[i]), "sex": str(data.sex[i]), "view": str(data.view[i]),
            "header_identity": {"patient_name": str(ds.PatientName), "patient_id": ds.PatientID,
                                "accession": ds.AccessionNumber, "institution": ds.InstitutionName},
        })
    (OUT / "manifest.json").write_text(json.dumps({
        "source": {"dataset": "NIH ChestX-ray14", "citation": "Wang et al., CVPR 2017 (NIH Clinical Center)",
                   "split": "held-out test films only", "selection": f"stratified by finding, seed {SEED}"},
        "note": "Pixel data is from the public NIH release. Every identity in the DICOM headers is invented "
                "so that ingestion has identifying tags to remove; the reference findings are the dataset's "
                "own NLP-mined labels and are demo metadata, not a diagnosis and never shown in the product.",
        "studies": manifest}, indent=2) + "\n")
    total = sum(p.stat().st_size for p in OUT.glob("*.dcm"))
    print(f"Wrote {len(manifest)} studies ({total / 1e6:.0f} MB) to {OUT}")


if __name__ == "__main__":
    main()
