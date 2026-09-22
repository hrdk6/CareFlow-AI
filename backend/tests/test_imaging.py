"""Radiology: DICOM de-identification, the reading queue, access control, reporting and the FHIR export."""
import importlib
import io
from datetime import date, datetime

import numpy as np
import pydicom
import pytest
from sqlalchemy import select

from app.imaging import dicom
from app.models import AuditLog, ImagingStudy, MedicalRecord, MLPrediction, ModelVersion, Patient
from app.services import imaging as service

SENDER = {"PatientName": "PRIOR^ALEX", "PatientID": "RX-100123", "PatientBirthDate": "19710304",
          "AccessionNumber": "ACC2026001", "ReferringPhysicianName": "SHARMA^R",
          "InstitutionName": "Riverside Imaging Centre", "StationName": "CR-2100-1",
          "DeviceSerialNumber": "SN700001", "StudyDescription": "CHEST PA"}


def make_dicom(*, rows: int = 64, columns: int = 64, view: str = "PA", body_part: str = "CHEST",
               modality: str = "DX", study_date: str = "20260901") -> bytes:
    """A small but genuine Part 10 file, with the identifying header a hospital's export would carry."""
    meta = pydicom.dataset.FileMetaDataset()
    meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.1.1"
    meta.MediaStorageSOPInstanceUID = pydicom.uid.generate_uid()
    meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    ds = pydicom.dataset.Dataset()
    ds.file_meta = meta
    ds.SOPClassUID = meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID, ds.SeriesInstanceUID = pydicom.uid.generate_uid(), pydicom.uid.generate_uid()
    for keyword, value in SENDER.items():
        setattr(ds, keyword, value)
    ds.add_new(0x00090010, "LO", "ACME_PRIVATE_BLOCK")
    ds.PatientSex, ds.PatientAge = "M", "055Y"
    ds.Modality, ds.BodyPartExamined, ds.ViewPosition = modality, body_part, view
    ds.StudyDate = ds.SeriesDate = ds.ContentDate = study_date
    ds.StudyTime = "081500"
    ds.PhotometricInterpretation, ds.SamplesPerPixel = "MONOCHROME2", 1
    ds.Rows, ds.Columns = rows, columns
    ds.BitsAllocated = ds.BitsStored = 8
    ds.HighBit, ds.PixelRepresentation = 7, 0
    ds.WindowCenter, ds.WindowWidth = 128.0, 256.0
    gradient = np.tile(np.linspace(0, 255, columns, dtype=np.uint8), (rows, 1))
    ds.PixelData = gradient.tobytes()
    buffer = io.BytesIO()
    ds.save_as(buffer, enforce_file_format=True)
    return buffer.getvalue()


def upload(client, auth, patient_id: int, role: str = "doctor", **fields):
    return client.post(f"/patients/{patient_id}/imaging", headers=auth(role),
                       files={"file": ("study.dcm", make_dicom(**fields.pop("dicom", {})), "application/dicom")},
                       data={"indication": "Cough and fever", **fields})


# ---------------------------------------------------------------- de-identification
def test_ingest_strips_every_identifier_before_the_file_is_stored(client, auth, db, demo_patient):
    r = upload(client, auth, demo_patient.id)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["removed_tags"] >= len(SENDER)

    study = db.scalar(select(ImagingStudy).where(ImagingStudy.study_uid == body["study"]["study_uid"]))
    stored = pydicom.dcmread(service.storage_path(study))
    # X-type attributes are gone; Z-type attributes stay (other software requires them) but carry nothing.
    for keyword in ("InstitutionName", "StationName", "DeviceSerialNumber", "StudyDescription"):
        assert keyword not in stored, f"{keyword} survived ingestion"
    for keyword in ("PatientName", "PatientBirthDate", "AccessionNumber", "ReferringPhysicianName"):
        assert str(stored.get(keyword, "")) == "", f"{keyword} still carries a value"
    assert stored.PatientID != SENDER["PatientID"] and stored.PatientID
    assert stored.PatientIdentityRemoved == "YES"
    assert stored.DeidentificationMethod.startswith("CareFlow")
    assert not [e for e in stored if e.tag.is_private]
    # Clinically meaningful tags are kept on purpose (option 113109), and the film is still readable.
    assert stored.PatientSex == "M" and stored.ViewPosition == "PA" and stored.BodyPartExamined == "CHEST"
    assert stored.pixel_array.shape == (64, 64)
    # The study date is shifted, so no real calendar date survives, but the interval to another film would.
    assert stored.StudyDate != "20260901" and len(stored.StudyDate) == 8
    assert study.deidentification["private_tags_removed"] is True
    assert study.deidentification["uids_regenerated"] is True


def test_the_stored_file_cannot_be_traced_back_to_the_sending_system(client, auth, db, demo_patient):
    source = make_dicom()
    original = pydicom.dcmread(io.BytesIO(source))
    r = client.post(f"/patients/{demo_patient.id}/imaging", headers=auth("doctor"),
                    files={"file": ("study.dcm", source, "application/dicom")})
    uids = r.json()["study"]["study_uid"]
    assert uids != str(original.StudyInstanceUID)
    study = db.scalar(select(ImagingStudy).where(ImagingStudy.study_uid == uids))
    stored = pydicom.dcmread(service.storage_path(study))
    assert str(stored.SOPInstanceUID) != str(original.SOPInstanceUID)
    assert str(stored.SeriesInstanceUID) != str(original.SeriesInstanceUID)


def test_the_record_keeps_the_real_date_and_the_file_does_not(client, auth, db, demo_patient):
    """De-identification protects a file that might leave the hospital, not the clinician reading it."""
    first = client.post(f"/patients/{demo_patient.id}/imaging", headers=auth("doctor"),
                        files={"file": ("a.dcm", make_dicom(study_date="20260901"), "application/dicom")})
    second = client.post(f"/patients/{demo_patient.id}/imaging", headers=auth("doctor"),
                         files={"file": ("b.dcm", make_dicom(study_date="20260911"), "application/dicom")})
    a = datetime.fromisoformat(first.json()["study"]["acquired_at"]).date()
    b = datetime.fromisoformat(second.json()["study"]["acquired_at"]).date()
    assert (a, b) == (date(2026, 9, 1), date(2026, 9, 11))    # the record, behind the access policy

    files = [pydicom.dcmread(service.storage_path(
        db.scalar(select(ImagingStudy).where(ImagingStudy.study_uid == r.json()["study"]["study_uid"]))))
        for r in (first, second)]
    stored = [datetime.strptime(f.StudyDate, "%Y%m%d").date() for f in files]
    assert stored[0] != a and stored[1] != b                  # no real date survives in the file
    assert (stored[1] - stored[0]).days == 10                 # but the interval between films does


def test_a_file_that_is_not_a_dicom_image_is_refused(client, auth, demo_patient):
    r = client.post(f"/patients/{demo_patient.id}/imaging", headers=auth("doctor"),
                    files={"file": ("notes.txt", b"not a dicom at all", "text/plain")})
    assert r.status_code == 422 and "DICOM" in r.json()["error"]["message"]


# ---------------------------------------------------------------- windowing
def test_windowing_follows_the_dicom_definition():
    pixels = np.array([[0.0, 64.0, 128.0, 192.0, 255.0]], dtype=np.float32)
    shown = dicom.window(pixels, center=128.0, width=256.0)
    assert shown[0][0] == 0 and shown[0][-1] == 255 and 120 < shown[0][2] < 135
    # A narrow window is a contrast stretch: everything outside it clips.
    narrow = dicom.window(pixels, center=128.0, width=32.0)
    assert narrow[0][1] == 0 and narrow[0][3] == 255
    assert (dicom.window(pixels, 128.0, 256.0, invert=True)[0][0]) == 255


def test_the_rendered_png_is_bounded_and_greyscale(client, auth, db, demo_patient):
    study_id = upload(client, auth, demo_patient.id).json()["study"]["id"]
    r = client.get(f"/imaging/studies/{study_id}/image.png?max_side=64", headers=auth("doctor"))
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    from PIL import Image

    image = Image.open(io.BytesIO(r.content))
    assert image.mode == "L" and max(image.size) == 64
    assert client.get(f"/imaging/studies/{study_id}/image.png?max_side=9999",
                      headers=auth("doctor")).status_code == 422


# ---------------------------------------------------------------- access control
def test_a_study_is_invisible_outside_the_care_relationship(client, auth, db, restricted_patient, demo_patient):
    study_id = upload(client, auth, demo_patient.id).json()["study"]["id"]
    for path in (f"/imaging/studies/{study_id}", f"/imaging/studies/{study_id}/image.png"):
        assert client.get(path, headers=auth("cardio")).status_code == 404  # a different department
    assert client.get(f"/patients/{demo_patient.id}/imaging", headers=auth("cardio")).status_code == 404


def test_reception_cannot_see_or_upload_films(client, auth, demo_patient):
    assert client.get("/imaging/worklist", headers=auth("reception")).status_code == 403
    assert client.get(f"/patients/{demo_patient.id}/imaging", headers=auth("reception")).status_code == 403
    assert upload(client, auth, demo_patient.id, role="reception").status_code == 403


def test_every_view_of_a_film_is_audited(client, auth, db, demo_patient):
    study_id = upload(client, auth, demo_patient.id).json()["study"]["id"]
    client.get(f"/imaging/studies/{study_id}/image.png", headers=auth("doctor"))
    actions = set(db.scalars(select(AuditLog.action).where(AuditLog.resource_type == "imaging_study",
                                                           AuditLog.resource_id == str(study_id))))
    assert {"imaging.ingest", "imaging.image_view"} <= actions


# ---------------------------------------------------------------- the reading queue
def _fake_triage(db, study: ImagingStudy, probability: float, label: str, findings: list[str]) -> MLPrediction:
    """A prediction row exactly as the model would write, without needing the model in an offline run."""
    version = db.scalar(select(ModelVersion).limit(1))
    row = MLPrediction(
        model_version_id=version.id, patient_id=study.patient_id, prediction_type="cxr_triage",
        value=probability, label=label, features={"study_uid": study.study_uid, "backbone": "test"},
        explanation={"findings": [
            {"finding": f, "label": f, "probability": probability, "threshold": 0.2, "flagged": True,
             "priority": label == "priority", "roc_auc": 0.74, "roc_auc_ci": [0.7, 0.78],
             "sensitivity": 0.92, "specificity": 0.42, "prevalence": 0.12, "attention": []} for f in findings],
        "operating_point": "test", "inference_ms": 1})
    db.add(row)
    db.flush()
    study.triage_prediction_id = row.id
    db.flush()
    return row


def test_the_queue_puts_the_most_likely_finding_first_and_says_what_was_not_scored(client, auth, db, demo_patient):
    high = db.get(ImagingStudy, upload(client, auth, demo_patient.id).json()["study"]["id"])
    low = db.get(ImagingStudy, upload(client, auth, demo_patient.id).json()["study"]["id"])
    unscored = db.get(ImagingStudy, upload(client, auth, demo_patient.id).json()["study"]["id"])
    _fake_triage(db, high, 0.81, "priority", ["Effusion"])
    _fake_triage(db, low, 0.10, "routine", [])
    db.commit()

    queue = client.get("/imaging/worklist", headers=auth("doctor")).json()
    mine = [i for i in queue["items"] if i["study_id"] in {high.id, low.id, unscored.id}]
    assert [i["study_id"] for i in mine] == [high.id, low.id, unscored.id]
    assert mine[0]["priority"] == "priority" and mine[0]["flagged"] == ["Effusion"]
    assert mine[2]["priority"] is None and mine[2]["priority_score"] is None
    assert queue["counts"]["not_scored"] >= 1 and queue["counts"]["waiting"] >= 3
    assert "not a diagnosis" in queue["disclaimer"]


def test_a_film_that_is_not_a_frontal_chest_is_stored_but_not_scored(client, auth, db, demo_patient):
    r = upload(client, auth, demo_patient.id, dicom={"body_part": "KNEE", "view": "LAT"})
    assert r.status_code == 201
    assert r.json()["study"]["triage"] is None
    assert not service.triageable(db.get(ImagingStudy, r.json()["study"]["id"]))
    assert "frontal chest films only" in r.json()["message"]


# ---------------------------------------------------------------- reporting
def test_a_report_is_a_draft_until_a_clinician_signs_it(client, auth, db, demo_patient):
    study_id = upload(client, auth, demo_patient.id).json()["study"]["id"]
    body = {"findings": "Clear lung fields. No pneumothorax.", "impression": "Normal chest radiograph.",
            "model_agreement": "agreed"}
    draft = client.put(f"/imaging/studies/{study_id}/report", headers=auth("doctor"), json=body)
    assert draft.status_code == 200 and draft.json()["status"] == "draft"
    assert draft.json()["record_id"] is None
    assert not db.scalars(select(MedicalRecord).where(MedicalRecord.record_type == "radiology_report")).all()

    signed = client.put(f"/imaging/studies/{study_id}/report", headers=auth("doctor"),
                        json={**body, "sign": True})
    assert signed.status_code == 200 and signed.json()["status"] == "final"
    record = db.get(MedicalRecord, signed.json()["record_id"])
    assert record.record_type == "radiology_report" and record.notes == body["findings"]
    assert record.diagnosis_summary == body["impression"]
    # The model did not write any of it: the provenance records what the reader was shown, and their verdict.
    assert record.ai_provenance["kind"] == "radiology_triage_shown"
    assert record.ai_provenance["model_agreement"] == "agreed"
    assert client.put(f"/imaging/studies/{study_id}/report", headers=auth("doctor"),
                      json={**body, "sign": True}).status_code == 409


def test_a_nurse_may_draft_a_report_but_not_sign_one(client, auth, db, demo_patient, users):
    study_id = upload(client, auth, demo_patient.id).json()["study"]["id"]
    # nurse.kim is on the demo patient's care team, so the study is visible to them.
    body = {"findings": "Film reviewed.", "impression": "Discussed with the on-call team.",
            "model_agreement": "not_used"}
    assert client.put(f"/imaging/studies/{study_id}/report", headers=auth("nurse"), json=body).status_code == 200
    refused = client.put(f"/imaging/studies/{study_id}/report", headers=auth("nurse"),
                         json={**body, "sign": True})
    assert refused.status_code == 403 and "doctor profile" in refused.json()["error"]["message"]


def test_the_reader_verdict_is_kept_for_later_evaluation(client, auth, db, demo_patient):
    study = db.get(ImagingStudy, upload(client, auth, demo_patient.id).json()["study"]["id"])
    _fake_triage(db, study, 0.77, "priority", ["Effusion"])
    db.commit()
    client.put(f"/imaging/studies/{study.id}/report", headers=auth("doctor"),
               json={"findings": "No effusion seen.", "impression": "Normal.", "model_agreement": "disagreed",
                     "sign": True})
    db.expire_all()
    report = db.get(ImagingStudy, study.id).report
    assert report.model_agreement == "disagreed"
    assert report.model_snapshot["flagged"] == ["Effusion"]     # what was on screen when they disagreed
    assert report.model_snapshot["priority_score"] == 0.77


# ---------------------------------------------------------------- FHIR
def test_the_study_and_its_report_export_as_valid_fhir(client, auth, db, demo_patient):
    uploaded = upload(client, auth, demo_patient.id).json()["study"]
    study_id, accession = uploaded["id"], uploaded["accession"]
    client.put(f"/imaging/studies/{study_id}/report", headers=auth("doctor"),
               json={"findings": "Small left pleural effusion.", "impression": "Left pleural effusion.",
                     "model_agreement": "agreed", "sign": True})
    bundle = client.get(f"/fhir/Patient/{demo_patient.mrn}/$everything", headers=auth("doctor")).json()
    entries = [e["resource"] for e in bundle["entry"]]

    def validate(resource):
        rt = resource["resourceType"]
        model = getattr(importlib.import_module(f"fhir.resources.R4B.{rt.lower()}"), rt)
        model.model_validate(resource)

    studies = [x for x in entries if x["resourceType"] == "ImagingStudy"]
    reports = [x for x in entries if x["resourceType"] == "DiagnosticReport"]
    assert studies and reports
    for resource in studies + reports:
        validate(resource)
    imaging = next(x for x in studies
                   if any(i["value"] == accession for i in x["identifier"]))
    assert imaging["modality"][0]["code"] == "DX"
    assert imaging["series"][0]["bodySite"]["code"] == "51185008"      # SNOMED thoracic structure
    assert imaging["identifier"][0]["system"] == "urn:dicom:uid"
    report = next(x for x in reports
                  if x["imagingStudy"][0]["reference"] == f"ImagingStudy/{imaging['id']}")
    assert report["category"][0]["coding"][0]["code"] == "RAD"
    assert report["conclusion"] == "Left pleural effusion."
    # The Provenance for a radiology record names a human author and no machine author.
    provenance = [x for x in entries if x["resourceType"] == "Provenance"
                  and "Read and signed by" in x["text"]["div"]]
    assert provenance and [a["type"]["coding"][0]["code"] for a in provenance[-1]["agent"]] == ["author"]


# ---------------------------------------------------------------- the model itself
@pytest.mark.models
def test_the_triage_model_scores_a_film_and_says_where_it_looked(db, demo_patient):
    from app.imaging import triage

    patient = db.scalar(select(Patient).where(Patient.mrn == demo_patient.mrn))
    study = service.ingest(db, None, patient, make_dicom(rows=256, columns=256), source="seed", score=True)
    db.flush()
    assert study.triage_prediction_id is not None
    result = service.triage_out(study.triage)
    assert result.priority in triage.PRIORITY_BANDS
    assert 0.0 <= result.priority_score <= 1.0
    overall = next(f for f in result.findings if f.finding == triage.ANY_FINDING)
    assert overall.probability == result.priority_score
    # Every reported finding carries the numbers that justify reporting it at all.
    for finding in result.findings:
        assert finding.roc_auc >= 0.70 and finding.roc_auc_ci[0] >= 0.65
        assert len(finding.attention) == 7 and len(finding.attention[0]) == 7
        assert min(min(row) for row in finding.attention) >= 0.0 and max(max(row) for row in finding.attention) <= 1.0
    assert any("not a diagnosis" in limitation for limitation in result.limitations)
