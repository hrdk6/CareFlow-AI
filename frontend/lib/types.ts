/** TypeScript mirrors of the backend Pydantic schemas (backend/app/schemas). */

export interface Page<T> { items: T[]; total: number; limit: number; offset: number }

export interface User {
  id: number; email: string; full_name: string; role: Role; permissions: string[];
  doctor_id: number | null; department_id: number | null;
}
export type Role = "ADMIN" | "DOCTOR" | "NURSE" | "RECEPTIONIST";

export interface Allergy { substance: string; reaction: string; severity: "mild" | "moderate" | "severe" }

export interface PatientListItem {
  id: number; mrn: string; full_name: string; date_of_birth: string; age: number; sex: string; status: string;
  primary_department: string | null; phone: string | null; is_synthetic: boolean;
}
export interface PatientDemographics extends PatientListItem {
  first_name: string; last_name: string; email: string | null; address: string | null; preferred_language: string;
  emergency_contact_name: string | null; emergency_contact_phone: string | null; emergency_contact_relation: string | null;
  created_at: string;
}
export interface Diagnosis {
  id: number; icd10_code: string; description: string; category: string; is_chronic: boolean; is_primary: boolean;
  status: string; diagnosed_on: string; admission_id: number | null;
}
export interface PatientClinical extends PatientDemographics {
  blood_type: string | null; allergies: Allergy[]; active_diagnoses: Diagnosis[]; current_medications: Prescription[];
  current_admission: Admission | null; admission_count: number;
  care_team: { user_id: number; name: string; care_role: string }[];
}

export interface Department { id: number; code: string; name: string; description: string }
export interface Doctor {
  id: number; staff_code: string; full_name: string; specialty: string; department_id: number; department: string;
  email: string; phone: string; availability: Record<string, [string, string][]>; is_active: boolean;
}
export interface Appointment {
  id: number; patient_id: number; patient_mrn: string; patient_name: string; doctor_id: number; doctor_name: string;
  department_id: number; scheduled_start: string; duration_minutes: number; appointment_type: string; reason: string;
  status: string; notes: string | null; cancellation_reason: string | null;
}
export interface Slot { start: string; end: string }
export interface Admission {
  id: number; patient_id: number; department_id: number; department: string; attending_doctor_id: number | null;
  attending_doctor: string | null; admitted_at: string; discharged_at: string | null; admission_type: string;
  admission_source: string; reason: string; discharge_disposition: string | null; status: string; ward: string | null;
  length_of_stay_days: number | null;
}
export interface MedicalRecord {
  id: number; patient_id: number; patient_mrn: string | null; doctor_id: number | null; doctor_name: string | null;
  admission_id: number | null; visit_date: string; record_type: string; chief_complaint: string; symptoms: string | null;
  diagnosis_summary: string | null; notes: string | null; treatment_plan: string | null;
}
export interface Prescription {
  id: number; patient_id: number; patient_mrn: string | null; medication_id: number; medication: string; drug_class: string;
  is_high_alert: boolean; dosage: string; frequency: string; route: string; duration_days: number | null;
  instructions: string | null; start_date: string; end_date: string | null; status: string; doctor_name: string;
  admission_id: number | null; change_reason: string | null;
}
export interface Medication { id: number; name: string; drug_class: string; is_high_alert: boolean; default_route: string }
export interface LabReport {
  id: number; patient_id: number; patient_mrn: string | null; admission_id: number | null; test_code: string;
  test_name: string; value: number | null; value_text: string | null; unit: string | null; reference_low: number | null;
  reference_high: number | null; flag: "normal" | "low" | "high" | "critical"; collected_at: string; reported_at: string | null;
  document_id: number | null;
}
export interface TimelineEvent {
  id: string; at: string; category: string; title: string; detail: string | null; source_type: string; source_id: number;
  severity: "info" | "warning" | "critical";
}

export interface Factor { feature: string; label: string; value: string; contribution: number; direction: "up" | "down"; text: string }
export interface Prediction {
  prediction_type: "readmission_30d" | "length_of_stay"; status: "ok" | "not_applicable"; reason: string | null;
  prediction_id: number | null; value: number | null; label: string | null; unit: string | null; threshold: number | null;
  flagged: boolean | null; interval: [number, number] | null; model_name: string | null; model_version: string | null;
  model_algorithm: string | null; trained_at: string | null; predicted_at: string | null;
  reference: { admission_id: number; admitted_at: string; discharged_at: string | null; status: string; reason: string;
    actual_length_of_stay_days: number | null } | null;
  features: Record<string, unknown>; missing_features: string[]; factors: Factor[]; explanation_space: string | null; explanation_method?: string | null;
  in_training_population: boolean; notes: string[]; context: Record<string, number>; limitations: string[]; disclaimer: string;
}
export interface SimilarPatient {
  patient_id: number; mrn: string; full_name: string; age: number; sex: string; similarity: number;
  shared_diagnosis_categories: string[]; shared_medication_groups: string[]; diagnoses: string[]; admissions_2y: number;
  mean_los_days: number | null; last_hba1c: number | null; last_egfr: number | null;
}
export interface Similarity {
  patient_id: number; representation_version: string; metric: string; query_profile: Record<string, unknown>;
  results: SimilarPatient[]; candidate_scope: string; disclaimer: string;
  cohort_patterns: {
    cohort_size?: number; discharges?: number; readmissions_within_30d?: number; readmission_rate?: number | null;
    mean_length_of_stay_days?: number | null; common_diagnoses?: { description: string; patients: number }[];
    common_active_medications?: { medication: string; patients: number }[];
  };
}

export interface DocumentItem {
  id: number; doc_key: string; title: string; version: number; is_current: boolean; filename: string; content_type: string;
  file_size: number; doc_type: string; department_id: number | null; department: string | null; access_scope: string;
  patient_id: number | null; patient_mrn: string | null; status: "uploading" | "processing" | "indexed" | "failed";
  error_message: string | null; page_count: number | null; chunk_count: number; flagged_chunk_count: number;
  is_synthetic: boolean; uploaded_by_user_id: number | null; created_at: string; indexed_at: string | null;
}
export interface Chunk { id: number; chunk_index: number; text: string; section_path: string; page_start: number | null; page_end: number | null; word_count: number; flags: Record<string, unknown> }
export interface DocumentDetail extends DocumentItem { chunks: Chunk[] }
export interface Source {
  chunk_id: number; document_id: number; document_title: string; version: number; doc_type: string; department: string | null;
  page_start: number | null; page_end: number | null; section_path: string; text: string; flags: Record<string, unknown>;
  is_synthetic: boolean;
}

export interface Citation {
  id: string; chunk_id: number; document_id: number; document_title: string; version: number; page_start: number | null;
  page_end: number | null; section_path: string; excerpt: string; retrieval: Record<string, number | null>;
}
export interface RecordRef { id: string; source_type: string; source_id: number; label: string; date: string | null }
export interface ToolCall { name: string; arguments: Record<string, unknown>; status: string; summary: string; ms: number | null }
export interface AIResponse {
  answer: string; route: string[]; routing_method: string; intents: string[]; patient_id: number | null;
  citations: Citation[]; record_refs: RecordRef[]; predictions: Prediction[]; similarity: Similarity | null;
  tool_calls: ToolCall[]; warnings: string[]; limitations: string[]; insufficient_context: boolean; provider: string;
  model: string | null; stage_ms: Record<string, number>; retrieval: Record<string, unknown>; request_id: string | null;
  created_at: string; disclaimer: string;
}

export interface ModelCard {
  model_name: string; version: string; is_active: boolean; task: string; algorithm: string; trained_at: string;
  dataset: Record<string, unknown>; features: { numeric: string[]; categorical: string[]; labels: Record<string, string> };
  metrics: Record<string, Record<string, unknown>>; candidates: Record<string, unknown>[];
  global_importance: Record<string, number>; leakage_ablation: Record<string, unknown>; limitations: string[];
  intended_use: string; extra: Record<string, unknown>;
}
export interface AuditLog {
  id: number; occurred_at: string; user_id: number | null; user_role: string | null; action: string;
  resource_type: string | null; resource_id: string | null; patient_id: number | null; outcome: string;
  ip_address: string | null; request_id: string | null; details: Record<string, unknown>;
}
export interface AITrace {
  id: number; created_at: string; user_id: number | null; request_id: string | null; query_length: number; route: string;
  routing_method: string; provider: string; llm_model: string | null; status: string; error_code: string | null;
  total_ms: number; stage_ms: Record<string, number>; retrieved_chunk_ids: number[]; cited_source_ids: number[];
  tool_calls: { name: string; status: string; ms: number }[]; model_versions: string[];
  prompt_tokens: number | null; completion_tokens: number | null;
}
export interface AdminUser {
  id: number; email: string; full_name: string; role: Role; is_active: boolean; doctor_id: number | null;
  department_id: number | null; last_login_at: string | null;
}
