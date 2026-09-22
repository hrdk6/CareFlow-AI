"""Reading, de-identifying and rendering DICOM.

A DICOM file carries the patient's identity in its header, and a file that leaves a hospital with those
tags intact is the classic imaging data breach. CareFlow therefore de-identifies on the way IN: the file
written to storage keeps the pixels and the clinically meaningful tags and carries no identifier from
wherever it came from. The link between a study and a patient lives in the database, behind the same
row-level policy as everything else, so who may see a film is decided by the access policy and not by
whatever the file happens to say.

Profile: DICOM PS3.15 Annex E Basic Application Level Confidentiality Profile with the options
    113107 Retain Longitudinal Temporal Information Modified Dates  (dates shifted by one offset per study)
    113109 Retain Patient Characteristics                           (age, sex and view position are clinical)
Instance, series and study UIDs are regenerated, private tags are dropped, and the result is stamped
PatientIdentityRemoved = YES with the method codes above (E.1.1: cleaned files must say so).
"""
import io
import logging
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from app.core.errors import ValidationFailedError

logger = logging.getLogger("careflow.imaging")

CAREFLOW_ROOT = "1.2.826.0.1.3680043.10.1337"  # UID root for identifiers this system mints
MAX_PIXELS = 6000 * 6000

# PS3.15 E.1-1 gives each attribute an action. The two that matter here are Z (the attribute is required
# to be present, so it is kept with a zero-length value) and X (the attribute is removed entirely).
# Getting this the wrong way round produces files that either leak or will not open.
BLANK_TAGS = [       # Z: present, empty
    "PatientName", "PatientBirthDate", "PatientBirthTime", "AccessionNumber", "StudyID",
    "ReferringPhysicianName", "ContentCreatorName",
]
REMOVE_TAGS = [      # X: gone
    "OtherPatientIDs", "OtherPatientNames", "OtherPatientIDsSequence", "PatientAddress",
    "PatientTelephoneNumbers", "PatientMotherBirthName", "IssuerOfPatientID",
    "PatientInsurancePlanCodeSequence", "MilitaryRank", "BranchOfService", "MedicalRecordLocator",
    "EthnicGroup", "Occupation", "PatientComments", "ResponsiblePerson", "ReferringPhysicianAddress",
    "ReferringPhysicianTelephoneNumbers", "PhysiciansOfRecord", "PerformingPhysicianName",
    "NameOfPhysiciansReadingStudy", "OperatorsName", "RequestingPhysician", "RequestedProcedureID",
    "ScheduledPerformingPhysicianName", "InstitutionName", "InstitutionAddress",
    "InstitutionalDepartmentName", "StationName", "DeviceSerialNumber", "PlateID", "DetectorID",
    "StudyDescription", "SeriesDescription", "ImageComments", "AdditionalPatientHistory",
]
# Dates and times: shifted by one offset per study so intervals survive but the calendar does not.
DATE_TAGS = ["StudyDate", "SeriesDate", "ContentDate", "AcquisitionDate", "InstanceCreationDate"]
TIME_TAGS = ["StudyTime", "SeriesTime", "ContentTime", "AcquisitionTime", "InstanceCreationTime"]
DEIDENTIFICATION_METHOD = "CareFlow AI: PS3.15 Basic Profile, options 113107 and 113109"


@dataclass(frozen=True)
class Film:
    """One de-identified radiograph, ready to store, score and display."""

    pixels: np.ndarray          # 2-D, as stored (after any rescale and MONOCHROME1 inversion)
    rows: int
    columns: int
    bits_stored: int
    window_center: float
    window_width: float
    modality: str
    body_part: str | None
    view_position: str | None
    patient_sex: str | None
    patient_age: int | None
    study_uid: str
    series_uid: str
    sop_uid: str
    acquired_on: date | None
    manufacturer: str | None


def new_uid() -> str:
    from pydicom.uid import generate_uid

    return generate_uid(prefix=CAREFLOW_ROOT + ".")


def _age(raw: object) -> int | None:
    """DICOM ages are four characters: 057Y, 018M, 003D."""
    text = str(raw or "").strip()
    if len(text) != 4 or not text[:3].isdigit():
        return None
    value, unit = int(text[:3]), text[3].upper()
    return value if unit == "Y" else 0 if unit in ("M", "W", "D") else None


def _date(raw: object) -> date | None:
    text = str(raw or "")
    return date(int(text[:4]), int(text[4:6]), int(text[6:])) if len(text) == 8 and text.isdigit() else None


def _first(value, default: float) -> float:
    """WindowCenter and WindowWidth may be multi-valued; take the first, as viewers do."""
    if value is None:
        return default
    if isinstance(value, (list, tuple)) or type(value).__name__ == "MultiValue":
        return float(value[0]) if len(value) else default
    return float(value)


def deidentify(ds, *, shift_days: int = 0) -> dict:
    """Strip identity from a dataset in place, following the profile in this module's docstring.

    Returns what was done, so the record can show which tags a file arrived with - "we removed nine
    identifying tags from this study" is checkable, "we de-identify uploads" is a promise.
    """
    removed, blanked, shifted = [], [], []
    had_private = any(element.tag.is_private for element in ds)
    ds.remove_private_tags()
    for keyword in REMOVE_TAGS + TIME_TAGS:
        if keyword in ds:
            removed.append(keyword)
            del ds[keyword]
    for keyword in BLANK_TAGS:
        if keyword in ds:
            blanked.append(keyword)
            setattr(ds, keyword, "")
    for keyword in DATE_TAGS:
        original = _date(ds.get(keyword))
        if original is not None:
            setattr(ds, keyword, (original - timedelta(days=shift_days)).strftime("%Y%m%d"))
            shifted.append(keyword)
    # New identifiers: the source UIDs are identifiers too - they link a film back to the PACS it came from.
    ds.StudyInstanceUID, ds.SeriesInstanceUID, ds.SOPInstanceUID = new_uid(), new_uid(), new_uid()
    if hasattr(ds, "file_meta"):
        ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    ds.PatientIdentityRemoved = "YES"
    ds.DeidentificationMethod = DEIDENTIFICATION_METHOD
    # PatientID gets a dummy value rather than an empty one, because tools index on it; it is derived from
    # the UID minted a moment ago and therefore points at nothing outside this system.
    ds.PatientID = ds.StudyInstanceUID.rsplit(".", 1)[-1]
    if "PatientID" not in blanked:
        blanked.append("PatientID")
    return {"method": DEIDENTIFICATION_METHOD, "removed_tags": removed, "blanked_tags": blanked,
            "date_tags_shifted": shifted, "shift_days": shift_days, "private_tags_removed": had_private,
            "uids_regenerated": True}


def read(data: bytes, *, deidentify_in_place: bool = True, shift_days: int = 0) -> tuple[Film, bytes, dict]:
    """Parse an uploaded DICOM, de-identify it, and return the film, the bytes to store and what was removed."""
    import pydicom

    try:
        ds = pydicom.dcmread(io.BytesIO(data))
    except Exception as exc:
        raise ValidationFailedError("That file is not a readable DICOM image") from exc
    if "PixelData" not in ds:
        raise ValidationFailedError("That DICOM has no image data (it may be a report or a presentation state)")
    if int(getattr(ds, "Rows", 0)) * int(getattr(ds, "Columns", 0)) > MAX_PIXELS:
        raise ValidationFailedError("That image is larger than this server accepts")
    # Read the real acquisition date BEFORE it is shifted: the database keeps it (behind the access policy,
    # where a clinician needs it), the file does not.
    acquired = _date(ds.get("StudyDate"))
    cleaning = deidentify(ds, shift_days=shift_days) if deidentify_in_place else {}

    try:
        pixels = ds.pixel_array
    except Exception as exc:  # compressed transfer syntaxes need codecs this deployment does not carry
        raise ValidationFailedError(
            "That DICOM uses a compressed transfer syntax this server cannot decode") from exc
    if pixels.ndim != 2:
        raise ValidationFailedError("Only single-frame images are supported")
    pixels = pixels.astype(np.float32)
    slope, intercept = float(getattr(ds, "RescaleSlope", 1) or 1), float(getattr(ds, "RescaleIntercept", 0) or 0)
    if (slope, intercept) != (1.0, 0.0):
        pixels = pixels * slope + intercept
    if str(getattr(ds, "PhotometricInterpretation", "MONOCHROME2")).strip() == "MONOCHROME1":
        pixels = pixels.max() - pixels  # MONOCHROME1 stores white low; normalise so bright means dense

    default_width = float(max(1.0, pixels.max() - pixels.min()))
    film = Film(
        pixels=pixels, rows=int(ds.Rows), columns=int(ds.Columns), bits_stored=int(ds.get("BitsStored", 8) or 8),
        window_center=_first(ds.get("WindowCenter"), float(pixels.min()) + default_width / 2),
        window_width=_first(ds.get("WindowWidth"), default_width),
        modality=str(getattr(ds, "Modality", "DX") or "DX"),
        body_part=str(ds.get("BodyPartExamined") or "") or None,
        view_position=str(ds.get("ViewPosition") or "") or None,
        patient_sex=str(ds.get("PatientSex") or "") or None,
        patient_age=_age(ds.get("PatientAge")),
        study_uid=str(ds.StudyInstanceUID), series_uid=str(ds.SeriesInstanceUID), sop_uid=str(ds.SOPInstanceUID),
        acquired_on=acquired, manufacturer=str(ds.get("Manufacturer") or "") or None)

    buffer = io.BytesIO()
    ds.save_as(buffer, enforce_file_format=True)
    return film, buffer.getvalue(), cleaning


def load(path) -> Film:
    """Read a file already in CareFlow's store (de-identified when it was ingested)."""
    with open(path, "rb") as fh:
        film, _, _ = read(fh.read(), deidentify_in_place=False)
    return film


def window(pixels: np.ndarray, center: float, width: float, *, invert: bool = False) -> np.ndarray:
    """Apply a VOI window exactly as PS3.3 C.11.2.1.2 defines it, to 8-bit display values."""
    width = max(width, 2.0)
    low = center - 0.5 - (width - 1) / 2
    scaled = np.clip((pixels - low) / (width - 1), 0.0, 1.0)
    if invert:
        scaled = 1.0 - scaled
    return (scaled * 255).astype(np.uint8)


def to_png(pixels: np.ndarray, center: float, width: float, *, invert: bool = False,
           max_side: int | None = None) -> bytes:
    from PIL import Image

    image = Image.fromarray(window(pixels, center, width, invert=invert), mode="L")
    if max_side and max(image.size) > max_side:
        scale = max_side / max(image.size)
        image = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))),
                             Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
