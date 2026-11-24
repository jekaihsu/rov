"""Wave 4 B2B Enterprise Instructor & Multi-Trainee Roster Module (ROV-01).

Provides multi-trainee cohort tracking across the 4 standard SOP modules:
  - M1_POOL_6DOF       (Mission 1: Pool 6DoF & Stick Calibration)
  - M2_HULL_UT         (Mission 2: Harbor Hull Inspection & UT Gauging SOP)
  - M3_T3_FAULT_RETURN (Mission 3: Deep Current SAR & T3 Fault Reallocation RTH)
  - M4_PIPELINE_TRIAL  (Mission 4: Subsea Pipeline Corridor Time Trial)

Includes deterministic HMAC-SHA256 tamper-evident certificate signing,
automatic safety invariant enforcement (hull_integrity == 0% -> Failed_Retry & 0 score),
cohort pass rate / UT thickness error / hazard deduction analytics, and
UTF-8-BOM CSV, JSON, and ISO-13628-6 print-ready HTML certificate exports.
"""
from __future__ import annotations

import collections
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import html
import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

from .input_shaping import _clamp, _num

TZ_TAIPEI = timezone(timedelta(hours=8))

STANDARD_SOP_MODULES: tuple[str, ...] = (
    "M1_POOL_6DOF",
    "M2_HULL_UT",
    "M3_T3_FAULT_RETURN",
    "M4_PIPELINE_TRIAL",
)

MISSION_ID_TO_SOP_MODULE: dict[str, str] = {
    "mission_1_pool": "M1_POOL_6DOF",
    "m1": "M1_POOL_6DOF",
    "m1_pool_6dof": "M1_POOL_6DOF",
    "mission_2_hull_ut": "M2_HULL_UT",
    "m2": "M2_HULL_UT",
    "m2_hull_ut": "M2_HULL_UT",
    "mission_3_sar_fault": "M3_T3_FAULT_RETURN",
    "m3": "M3_T3_FAULT_RETURN",
    "m3_t3_fault_return": "M3_T3_FAULT_RETURN",
    "mission_4_pipeline": "M4_PIPELINE_TRIAL",
    "m4": "M4_PIPELINE_TRIAL",
    "m4_pipeline_trial": "M4_PIPELINE_TRIAL",
}

SOP_MODULE_TITLES: dict[str, str] = {
    "M1_POOL_6DOF": "M1 · 訓練水池 6DoF 與搖桿曲線校準",
    "M2_HULL_UT": "M2 · 港灣船體巡檢與 3 秒穩定 UT 測厚 SOP",
    "M3_T3_FAULT_RETURN": "M3 · 暗流搜救與 T3 單推進器失效向量重分配返航",
    "M4_PIPELINE_TRIAL": "M4 · 海底雙管線防撞廊道與臍帶纜張力控制",
}

VALID_GRADES: tuple[str, ...] = ("A+", "A", "B", "C", "F")
VALID_CERT_STATUSES: tuple[str, ...] = ("Certified_Pass", "Conditional_Retest", "Failed_Retry")

_SIGNING_SECRET = b"ROV-01-B2B-ISO13628-6-TAMPER-SEAL-2026-V4"

CANONICAL_SIGNATURE_FIELDS: tuple[str, ...] = (
    "trainee_id",
    "trainee_name",
    "department",
    "mission_id",
    "timestamp",
    "hull_integrity_pct",
    "ut_checkpoints_completed",
    "ut_max_tilt_deg",
    "t3_fault_survived",
    "tether_snag_count",
    "elapsed_sec",
    "total_score",
    "grade",
    "cert_status",
)


def now_utc8_str() -> str:
    """Return current timestamp formatted in Asia/Taipei (UTC+8)."""
    return datetime.now(TZ_TAIPEI).strftime("%Y-%m-%d %H:%M:%S UTC+8")


def normalize_mission_id(mission_id: str | None) -> str:
    raw = str(mission_id or "M1_POOL_6DOF").strip()
    if raw in STANDARD_SOP_MODULES:
        return raw
    mapped = MISSION_ID_TO_SOP_MODULE.get(raw.lower())
    return mapped if mapped is not None else raw


def normalize_grade(grade: str | None, total_score: float, hull_integrity_pct: float) -> str:
    if hull_integrity_pct <= 0.0:
        return "F"
    if grade:
        g = str(grade).strip().upper()
        for tok in VALID_GRADES:
            if g == tok or g.startswith(tok + " ") or g.startswith(tok + "("):
                if hull_integrity_pct < 80.0 and tok in ("A+", "A"):
                    return "B" if total_score >= 70.0 else ("C" if total_score >= 60.0 else "F")
                return tok
    if hull_integrity_pct < 80.0:
        if total_score >= 70.0:
            return "B"
        if total_score >= 60.0:
            return "C"
        return "F"
    if total_score >= 90.0:
        return "A+"
    if total_score >= 80.0:
        return "A"
    if total_score >= 70.0:
        return "B"
    if total_score >= 60.0:
        return "C"
    return "F"


def derive_cert_status(
    cert_status: str | None,
    *,
    total_score: float,
    hull_integrity_pct: float,
    grade: str,
    ut_max_tilt_deg: float = 0.0,
    mission_id: str = "M1_POOL_6DOF",
    ut_checkpoints_completed: int = 4,
    t3_fault_survived: bool = True,
) -> str:
    """Enforce B2B safety invariants on qualification status."""
    if hull_integrity_pct <= 0.0 or total_score < 60.0 or grade == "F":
        return "Failed_Retry"
    if hull_integrity_pct < 80.0:
        if cert_status == "Failed_Retry" or total_score < 70.0:
            return "Failed_Retry"
        return "Conditional_Retest"
    if mission_id == "M2_HULL_UT" and (ut_max_tilt_deg >= 3.0 or ut_checkpoints_completed < 4):
        return "Conditional_Retest" if total_score >= 70.0 else "Failed_Retry"
    if mission_id == "M3_T3_FAULT_RETURN" and not t3_fault_survived:
        return "Failed_Retry"
    if cert_status in VALID_CERT_STATUSES:
        if cert_status == "Certified_Pass" and total_score < 85.0:
            return "Conditional_Retest" if total_score >= 70.0 else "Failed_Retry"
        return cert_status
    if total_score >= 85.0:
        return "Certified_Pass"
    if total_score >= 70.0:
        return "Conditional_Retest"
    return "Failed_Retry"


def _canonical_payload_string(data: dict[str, Any]) -> str:
    canonical: dict[str, Any] = {
        "trainee_id": str(data.get("trainee_id", "")).strip(),
        "trainee_name": str(data.get("trainee_name", data.get("name", data.get("handle", "")))).strip(),
        "department": str(data.get("department", data.get("cohort", ""))).strip(),
        "mission_id": normalize_mission_id(data.get("mission_id", "M1_POOL_6DOF")),
        "timestamp": str(data.get("timestamp", "")).strip(),
        "hull_integrity_pct": round(float(_num(data.get("hull_integrity_pct", data.get("hull_integrity", 100.0)), 100.0)), 1),
        "ut_checkpoints_completed": int(_num(data.get("ut_checkpoints_completed", 0), 0)),
        "ut_max_tilt_deg": round(float(_num(data.get("ut_max_tilt_deg", 0.0), 0.0)), 2),
        "t3_fault_survived": bool(data.get("t3_fault_survived", True)),
        "tether_snag_count": int(_num(data.get("tether_snag_count", 0), 0)),
        "elapsed_sec": round(float(_num(data.get("elapsed_sec", 0.0), 0.0)), 2),
        "total_score": round(float(_num(data.get("total_score", 0.0), 0.0)), 1),
        "grade": str(data.get("grade", "F")).strip(),
        "cert_status": str(data.get("cert_status", "Failed_Retry")).strip(),
    }
    return json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def compute_signature_for_dict(data: dict[str, Any]) -> str:
    payload = _canonical_payload_string(data).encode("utf-8")
    return hmac.new(_SIGNING_SECRET, payload, hashlib.sha256).hexdigest()


def verify_certificate_signature(record_or_dict: TraineeSessionRecord | dict[str, Any]) -> bool:
    """Verify the deterministic HMAC-SHA256 signature and B2B safety invariants."""
    if isinstance(record_or_dict, TraineeSessionRecord):
        d = record_or_dict.to_dict()
    elif isinstance(record_or_dict, dict):
        d = dict(record_or_dict)
    else:
        return False

    provided_hash = str(d.get("verification_hash", "")).strip()
    if not provided_hash or len(provided_hash) != 64:
        return False

    hull_pct = round(float(_num(d.get("hull_integrity_pct", d.get("hull_integrity", 100.0)), 100.0)), 1)
    score = round(float(_num(d.get("total_score", 0.0), 0.0)), 1)
    grade = str(d.get("grade", "")).strip()
    cert_status = str(d.get("cert_status", "")).strip()

    # Safety invariant check: 0% hull integrity must never be Certified_Pass or positive score
    if hull_pct <= 0.0 and (cert_status != "Failed_Retry" or grade != "F" or score > 0.0):
        return False
    if cert_status == "Certified_Pass" and (hull_pct < 80.0 or score < 85.0):
        return False

    expected_hash = compute_signature_for_dict(d)
    return hmac.compare_digest(expected_hash, provided_hash)


@dataclass
class TraineeSessionRecord:
    """Tamper-evident B2B trainee session record across ROV-01 SOP modules."""

    trainee_id: str
    trainee_name: str = "Pilot Trainee"
    department: str = "永祥水下工程部 (Subsea Ops)"
    mission_id: str = "M1_POOL_6DOF"
    timestamp: str = ""
    hull_integrity_pct: float = 100.0
    ut_checkpoints_completed: int = 4
    ut_max_tilt_deg: float = 1.4
    t3_fault_survived: bool = True
    tether_snag_count: int = 0
    elapsed_sec: float = 120.0
    total_score: float = 90.0
    grade: str = ""
    cert_status: str = ""
    ut_avg_thickness_error_mm: float = 0.15
    hazard_deduction_reason: str = "NONE"
    verification_hash: str = ""

    def __init__(
        self,
        trainee_id: str,
        trainee_name: str | None = None,
        department: str | None = None,
        mission_id: str = "M1_POOL_6DOF",
        timestamp: str | None = None,
        hull_integrity_pct: float | None = None,
        ut_checkpoints_completed: int = 4,
        ut_max_tilt_deg: float = 1.4,
        t3_fault_survived: bool = True,
        tether_snag_count: int = 0,
        elapsed_sec: float = 120.0,
        total_score: float = 90.0,
        grade: str = "",
        cert_status: str = "",
        ut_avg_thickness_error_mm: float = 0.15,
        hazard_deduction_reason: str = "",
        verification_hash: str = "",
        *,
        name: str | None = None,
        handle: str | None = None,
        cohort: str | None = None,
        hull_integrity: float | None = None,
        preserve_unverified: bool = False,
    ):
        self.trainee_id = str(trainee_id).strip()
        resolved_name = trainee_name if trainee_name is not None else (name if name is not None else (handle if handle is not None else "Pilot Trainee"))
        self.trainee_name = str(resolved_name).strip()
        resolved_dept = department if department is not None else (cohort if cohort is not None else "永祥水下工程部 (Subsea Ops)")
        self.department = str(resolved_dept).strip()
        self.mission_id = normalize_mission_id(mission_id)
        self.timestamp = str(timestamp).strip() if timestamp else now_utc8_str()
        if not self.timestamp.endswith("UTC+8"):
            self.timestamp = f"{self.timestamp} UTC+8".strip()

        raw_hull = hull_integrity_pct if hull_integrity_pct is not None else (hull_integrity if hull_integrity is not None else 100.0)
        self.hull_integrity_pct = round(_clamp(_num(raw_hull, 100.0), 0.0, 100.0), 1)
        self.ut_checkpoints_completed = int(max(0, min(10, _num(ut_checkpoints_completed, 0))))
        self.ut_max_tilt_deg = round(_clamp(_num(ut_max_tilt_deg, 0.0), 0.0, 180.0), 2)
        self.t3_fault_survived = bool(t3_fault_survived)
        self.tether_snag_count = int(max(0, _num(tether_snag_count, 0)))
        self.elapsed_sec = round(max(0.0, _num(elapsed_sec, 0.0)), 2)
        self.ut_avg_thickness_error_mm = round(max(0.0, _num(ut_avg_thickness_error_mm, 0.15)), 3)

        raw_score = round(_clamp(_num(total_score, 0.0), 0.0, 100.0), 1)
        if not preserve_unverified:
            if self.hull_integrity_pct <= 0.0:
                self.total_score = 0.0
                self.grade = "F"
                self.cert_status = "Failed_Retry"
            else:
                if self.hull_integrity_pct < 80.0:
                    raw_score = min(raw_score, 78.0)
                self.total_score = raw_score
                self.grade = normalize_grade(grade, self.total_score, self.hull_integrity_pct)
                self.cert_status = derive_cert_status(
                    cert_status,
                    total_score=self.total_score,
                    hull_integrity_pct=self.hull_integrity_pct,
                    grade=self.grade,
                    ut_max_tilt_deg=self.ut_max_tilt_deg,
                    mission_id=self.mission_id,
                    ut_checkpoints_completed=self.ut_checkpoints_completed,
                    t3_fault_survived=self.t3_fault_survived,
                )
        else:
            self.total_score = raw_score
            self.grade = str(grade or "F").strip()
            self.cert_status = str(cert_status or "Failed_Retry").strip()

        if hazard_deduction_reason:
            self.hazard_deduction_reason = str(hazard_deduction_reason).strip()
        else:
            self.hazard_deduction_reason = self._infer_hazard_deduction()

        if verification_hash:
            self.verification_hash = str(verification_hash).strip()
        else:
            self.verification_hash = self.compute_verification_hash()

    def _infer_hazard_deduction(self) -> str:
        if self.hull_integrity_pct <= 0.0:
            return "HULL_COLLISION_CRITICAL_0PCT"
        if self.hull_integrity_pct < 100.0:
            return "HULL_COLLISION_IMPULSE"
        if self.tether_snag_count > 0:
            return "TETHER_SNAG_HIGH_TENSION"
        if self.ut_max_tilt_deg > 3.0:
            return "UT_TILT_EXCEEDED_3DEG"
        if not self.t3_fault_survived:
            return "T3_THRUSTER_FAULT_ABORT"
        return "NONE"

    @property
    def name(self) -> str:
        return self.trainee_name

    @property
    def handle(self) -> str:
        return self.trainee_name

    @property
    def cohort(self) -> str:
        return self.department

    @property
    def hull_integrity(self) -> float:
        return self.hull_integrity_pct

    def compute_verification_hash(self) -> str:
        return compute_signature_for_dict(self.to_dict(include_hash=False))

    def resign(self) -> str:
        self.verification_hash = self.compute_verification_hash()
        return self.verification_hash

    def to_dict(self, *, include_hash: bool = True) -> dict[str, Any]:
        out: dict[str, Any] = {
            "trainee_id": self.trainee_id,
            "trainee_name": self.trainee_name,
            "department": self.department,
            "mission_id": self.mission_id,
            "mission_title": SOP_MODULE_TITLES.get(self.mission_id, self.mission_id),
            "timestamp": self.timestamp,
            "hull_integrity_pct": self.hull_integrity_pct,
            "ut_checkpoints_completed": self.ut_checkpoints_completed,
            "ut_max_tilt_deg": self.ut_max_tilt_deg,
            "ut_avg_thickness_error_mm": self.ut_avg_thickness_error_mm,
            "t3_fault_survived": self.t3_fault_survived,
            "tether_snag_count": self.tether_snag_count,
            "elapsed_sec": self.elapsed_sec,
            "total_score": self.total_score,
            "grade": self.grade,
            "cert_status": self.cert_status,
            "hazard_deduction_reason": self.hazard_deduction_reason,
        }
        if include_hash:
            out["verification_hash"] = self.verification_hash
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, preserve_unverified: bool = True) -> TraineeSessionRecord:
        return cls(
            trainee_id=str(data.get("trainee_id", "TR-000")),
            trainee_name=str(data.get("trainee_name", data.get("name", data.get("handle", "Pilot Trainee")))),
            department=str(data.get("department", data.get("cohort", "永祥水下工程部 (Subsea Ops)"))),
            mission_id=str(data.get("mission_id", "M1_POOL_6DOF")),
            timestamp=str(data.get("timestamp", "")),
            hull_integrity_pct=float(_num(data.get("hull_integrity_pct", data.get("hull_integrity", 100.0)), 100.0)),
            ut_checkpoints_completed=int(_num(data.get("ut_checkpoints_completed", 0), 0)),
            ut_max_tilt_deg=float(_num(data.get("ut_max_tilt_deg", 0.0), 0.0)),
            t3_fault_survived=bool(data.get("t3_fault_survived", True)),
            tether_snag_count=int(_num(data.get("tether_snag_count", 0), 0)),
            elapsed_sec=float(_num(data.get("elapsed_sec", 0.0), 0.0)),
            total_score=float(_num(data.get("total_score", 0.0), 0.0)),
            grade=str(data.get("grade", "")),
            cert_status=str(data.get("cert_status", "")),
            ut_avg_thickness_error_mm=float(_num(data.get("ut_avg_thickness_error_mm", 0.15), 0.15)),
            hazard_deduction_reason=str(data.get("hazard_deduction_reason", "")),
            verification_hash=str(data.get("verification_hash", "")),
            preserve_unverified=preserve_unverified,
        )

    @classmethod
    def from_wave1_evaluation(
        cls,
        wave1_mgr: Any,
        *,
        trainee_id: str,
        trainee_name: str,
        department: str = "永祥水下工程部 (Subsea Ops)",
        timestamp: str | None = None,
    ) -> TraineeSessionRecord:
        eval_report = wave1_mgr.compute_sop_evaluation()
        metrics = eval_report.get("metrics", {})
        ut_cps = eval_report.get("ut_checkpoints", [])
        completed_cps = [c for c in ut_cps if c.get("completed")]
        if completed_cps:
            # Nominal vs measured gauge precision error (simulated sensor repeatability ~0.12-0.22 mm)
            avg_ut_err = round(
                sum(abs(float(c.get("nominal_mm", 16.0)) - float(c.get("measured_mm", 15.8))) * 0.18 for c in completed_cps)
                / len(completed_cps),
                3,
            )
        else:
            avg_ut_err = 0.25

        faults = metrics.get("faulted_thrusters", [])
        t3_survived = True
        if faults:
            t3_survived = bool(
                (not getattr(wave1_mgr, "mission_aborted", False))
                and float(metrics.get("hull_integrity_pct", 100.0)) > 0.0
                and bool(metrics.get("emergency_return_completed", False))
            )

        snag_cnt = int(getattr(wave1_mgr, "tether_snag_recovered_count", 0)) + (1 if metrics.get("tether_snagged") else 0)
        tilt_deg = float(_num(getattr(wave1_mgr, "ut_tilt_deg", 1.4), 1.4))

        return cls(
            trainee_id=trainee_id,
            trainee_name=trainee_name,
            department=department,
            mission_id=normalize_mission_id(eval_report.get("mission_id", getattr(wave1_mgr, "mission_id", "M1_POOL_6DOF"))),
            timestamp=timestamp or str(eval_report.get("generated_at") or now_utc8_str()),
            hull_integrity_pct=float(_num(metrics.get("hull_integrity_pct", getattr(wave1_mgr, "hull_integrity", 100.0)), 100.0)),
            ut_checkpoints_completed=int(_num(metrics.get("ut_completed", 0), 0)),
            ut_max_tilt_deg=tilt_deg,
            t3_fault_survived=t3_survived,
            tether_snag_count=snag_cnt,
            elapsed_sec=float(_num(eval_report.get("elapsed_s", 0.0), 0.0)),
            total_score=float(_num(eval_report.get("total_score", 0.0), 0.0)),
            grade=str(eval_report.get("grade", "")),
            cert_status=(eval_report.get("sop_cert_status")
                         if eval_report.get("sop_cert_status") in VALID_CERT_STATUSES
                         else "Conditional_Retest"),
            ut_avg_thickness_error_mm=avg_ut_err,
        )


class CohortRosterManager:
    """Aggregates multi-trainee B2B SOP runs and exports CSV, JSON, and ISO-13628-6 HTML certificates."""

    CSV_COLUMNS: tuple[str, ...] = (
        "trainee_id",
        "trainee_name",
        "department",
        "mission_id",
        "timestamp",
        "hull_integrity_pct",
        "ut_checkpoints_completed",
        "ut_max_tilt_deg",
        "ut_avg_thickness_error_mm",
        "t3_fault_survived",
        "tether_snag_count",
        "elapsed_sec",
        "total_score",
        "grade",
        "cert_status",
        "hazard_deduction_reason",
        "verification_hash",
    )

    def __init__(
        self,
        cohort_id: str = "YX-B2B-2026Q4-COHORT-01",
        cohort_name: str = "2026 Q4 永祥水下工程與離岸海事承包商 ROV-01 飛手認證梯次",
        instructor_name: str = "張爲斌 (Robin Chang) · 首席 ROV 飛手總教官",
        organization: str = "永祥水下工程企業飛手訓練中心 (Subsea ROV Pilot Training Center)",
        records: list[TraineeSessionRecord] | None = None,
    ):
        self.cohort_id = cohort_id
        self.cohort_name = cohort_name
        self.instructor_name = instructor_name
        self.organization = organization
        self.standard_ref = "ISO 13628-6 / IMCA R004 ROV Pilot Technician Grade II"
        self.records: list[TraineeSessionRecord] = list(records) if records else []

    def add_record(self, record: TraineeSessionRecord | dict[str, Any]) -> TraineeSessionRecord:
        rec = record if isinstance(record, TraineeSessionRecord) else TraineeSessionRecord.from_dict(record, preserve_unverified=False)
        self.records.append(rec)
        return rec

    def record_wave1_run(
        self,
        wave1_mgr: Any,
        *,
        trainee_id: str,
        trainee_name: str,
        department: str = "永祥水下工程部 (Subsea Ops)",
        timestamp: str | None = None,
    ) -> TraineeSessionRecord:
        rec = TraineeSessionRecord.from_wave1_evaluation(
            wave1_mgr,
            trainee_id=trainee_id,
            trainee_name=trainee_name,
            department=department,
            timestamp=timestamp,
        )
        self.records.append(rec)
        return rec

    def compute_cohort_summary(self) -> dict[str, Any]:
        total = len(self.records)
        if total == 0:
            return {
                "cohort_id": self.cohort_id,
                "cohort_name": self.cohort_name,
                "instructor_name": self.instructor_name,
                "organization": self.organization,
                "standard_ref": self.standard_ref,
                "generated_at": now_utc8_str(),
                "total_runs": 0,
                "unique_trainees": 0,
                "certified_pass_count": 0,
                "conditional_retest_count": 0,
                "failed_retry_count": 0,
                "cohort_pass_rate": 0.0,
                "pass_rate_pct": 0.0,
                "average_score": 0.0,
                "average_hull_integrity_pct": 0.0,
                "average_ut_thickness_error_mm": 0.0,
                "most_frequent_hazard_deduction": "NONE",
                "hazard_deduction_counts": {},
                "module_breakdown": {
                    m: {"runs": 0, "pass_count": 0, "pass_rate_pct": 0.0, "avg_score": 0.0}
                    for m in STANDARD_SOP_MODULES
                },
                "all_signatures_valid": True,
            }

        pass_cnt = sum(1 for r in self.records if r.cert_status == "Certified_Pass")
        retest_cnt = sum(1 for r in self.records if r.cert_status == "Conditional_Retest")
        fail_cnt = sum(1 for r in self.records if r.cert_status == "Failed_Retry")
        pass_rate = round(100.0 * pass_cnt / total, 1)
        avg_score = round(sum(r.total_score for r in self.records) / total, 1)
        avg_hull = round(sum(r.hull_integrity_pct for r in self.records) / total, 1)
        avg_ut_err = round(sum(r.ut_avg_thickness_error_mm for r in self.records) / total, 3)

        hazard_counter: collections.Counter[str] = collections.Counter(
            r.hazard_deduction_reason for r in self.records if r.hazard_deduction_reason and r.hazard_deduction_reason != "NONE"
        )
        most_freq_hazard = hazard_counter.most_common(1)[0][0] if hazard_counter else "NONE"

        mod_breakdown: dict[str, dict[str, Any]] = {}
        for m in STANDARD_SOP_MODULES:
            m_recs = [r for r in self.records if r.mission_id == m]
            m_total = len(m_recs)
            m_pass = sum(1 for r in m_recs if r.cert_status == "Certified_Pass")
            mod_breakdown[m] = {
                "title": SOP_MODULE_TITLES.get(m, m),
                "runs": m_total,
                "pass_count": m_pass,
                "pass_rate_pct": round(100.0 * m_pass / m_total, 1) if m_total else 0.0,
                "avg_score": round(sum(r.total_score for r in m_recs) / m_total, 1) if m_total else 0.0,
            }

        all_valid = all(verify_certificate_signature(r) for r in self.records)

        return {
            "cohort_id": self.cohort_id,
            "cohort_name": self.cohort_name,
            "instructor_name": self.instructor_name,
            "organization": self.organization,
            "standard_ref": self.standard_ref,
            "generated_at": now_utc8_str(),
            "total_runs": total,
            "unique_trainees": len({r.trainee_id for r in self.records}),
            "certified_pass_count": pass_cnt,
            "conditional_retest_count": retest_cnt,
            "failed_retry_count": fail_cnt,
            "cohort_pass_rate": pass_rate,
            "pass_rate_pct": pass_rate,
            "average_score": avg_score,
            "average_hull_integrity_pct": avg_hull,
            "average_ut_thickness_error_mm": avg_ut_err,
            "most_frequent_hazard_deduction": most_freq_hazard,
            "hazard_deduction_counts": dict(hazard_counter),
            "module_breakdown": mod_breakdown,
            "all_signatures_valid": all_valid,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.compute_cohort_summary(),
            "records": [r.to_dict() for r in self.records],
        }

    def export_cohort_csv(self, path: str | Path) -> Path:
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(self.CSV_COLUMNS))
            writer.writeheader()
            for r in self.records:
                d = r.to_dict()
                writer.writerow({col: d.get(col, "") for col in self.CSV_COLUMNS})
        return out_path

    def export_cohort_json(self, path: str | Path) -> Path:
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.to_dict()
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return out_path

    def export_printable_certificate_html(
        self,
        path: str | Path,
        *,
        featured_trainee_id: str | None = None,
    ) -> Path:
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        summary = self.compute_cohort_summary()

        featured = None
        if featured_trainee_id:
            featured = next((r for r in self.records if r.trainee_id == featured_trainee_id), None)
        if featured is None and self.records:
            certified = [r for r in self.records if r.cert_status == "Certified_Pass"]
            featured = max(certified or self.records, key=lambda r: r.total_score)

        rows_html = []
        for idx, r in enumerate(self.records, 1):
            sig_ok = verify_certificate_signature(r)
            status_color = (
                "#10B981" if r.cert_status == "Certified_Pass"
                else "#F59E0B" if r.cert_status == "Conditional_Retest"
                else "#EF4444"
            )
            sig_badge = (
                f"<span style='color:#10B981;font-family:monospace;font-size:11px;' title='{html.escape(r.verification_hash)}'>"
                f"✔ SHA256:{html.escape(r.verification_hash[:12])}…</span>"
                if sig_ok
                else "<span style='color:#EF4444;font-weight:700;'>✘ TAMPERED</span>"
            )
            rows_html.append(
                f"<tr style='border-bottom:1px solid #1E293B;'>"
                f"<td style='padding:8px 6px;'>{idx}</td>"
                f"<td style='padding:8px 6px;font-weight:700;color:#E2E8F0;'>{html.escape(r.trainee_id)} · {html.escape(r.trainee_name)}</td>"
                f"<td style='padding:8px 6px;color:#94A3B8;'>{html.escape(r.department)}</td>"
                f"<td style='padding:8px 6px;color:#38BDF8;font-family:monospace;'>{html.escape(r.mission_id)}</td>"
                f"<td style='padding:8px 6px;'>{r.hull_integrity_pct:.1f}%</td>"
                f"<td style='padding:8px 6px;'>{r.ut_checkpoints_completed}/4 ({r.ut_max_tilt_deg:.1f}°)</td>"
                f"<td style='padding:8px 6px;'>{'PASS' if r.t3_fault_survived else 'FAIL'}</td>"
                f"<td style='padding:8px 6px;'>{r.tether_snag_count}</td>"
                f"<td style='padding:8px 6px;font-weight:800;color:#22D3EE;'>{r.total_score:.1f}</td>"
                f"<td style='padding:8px 6px;font-weight:700;'>{html.escape(r.grade)}</td>"
                f"<td style='padding:8px 6px;font-weight:700;color:{status_color};'>{html.escape(r.cert_status)}</td>"
                f"<td style='padding:8px 6px;'>{sig_badge}</td>"
                f"</tr>"
            )

        feat_block = ""
        if featured is not None:
            feat_block = f"""
      <div style="border:2px solid #22D3EE;background:linear-gradient(135deg,#0B192C 0%,#0F2942 100%);border-radius:12px;padding:20px 24px;margin-bottom:20px;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;border-bottom:1px solid #1E3A5F;padding-bottom:12px;margin-bottom:14px;">
          <div>
            <div style="font-size:11px;letter-spacing:1.5px;color:#22D3EE;text-transform:uppercase;">ISO 13628-6 / IMCA R004 ROV Pilot Qualification Certificate</div>
            <div style="font-size:22px;font-weight:800;color:#F8FAFC;margin-top:4px;">水下無人載具 (ROV-01) 企業飛手專業技術認證證書</div>
            <div style="font-size:12px;color:#94A3B8;margin-top:2px;">發證機構：{html.escape(self.organization)} · 梯次代碼：{html.escape(self.cohort_id)}</div>
          </div>
          <div style="text-align:right;">
            <div style="background:#064E3B;color:#10B981;border:1px solid #10B981;padding:4px 10px;border-radius:6px;font-size:12px;font-weight:700;">
              {html.escape(featured.cert_status)} · Grade {html.escape(featured.grade)}
            </div>
            <div style="font-size:11px;color:#94A3B8;margin-top:6px;">簽發時間：{html.escape(featured.timestamp)}</div>
          </div>
        </div>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:14px;font-size:12.5px;">
          <div style="background:#091322;padding:10px 12px;border-radius:8px;border:1px solid #1E293B;">
            <div style="color:#94A3B8;font-size:11px;">受訓飛手 (Pilot Trainee)</div>
            <div style="font-weight:700;color:#F8FAFC;font-size:14px;margin-top:2px;">{html.escape(featured.trainee_name)} ({html.escape(featured.trainee_id)})</div>
            <div style="color:#7DD3FC;font-size:11px;margin-top:2px;">{html.escape(featured.department)}</div>
          </div>
          <div style="background:#091322;padding:10px 12px;border-radius:8px;border:1px solid #1E293B;">
            <div style="color:#94A3B8;font-size:11px;">認證課目 (SOP Module)</div>
            <div style="font-weight:700;color:#22D3EE;font-size:14px;margin-top:2px;">{html.escape(featured.mission_id)}</div>
            <div style="color:#CBD5E1;font-size:11px;margin-top:2px;">耗時 {featured.elapsed_sec:.1f}s · 總分 {featured.total_score:.1f}/100</div>
          </div>
          <div style="background:#091322;padding:10px 12px;border-radius:8px;border:1px solid #1E293B;">
            <div style="color:#94A3B8;font-size:11px;">UT 測厚與姿態精度</div>
            <div style="font-weight:700;color:#10B981;font-size:14px;margin-top:2px;">{featured.ut_checkpoints_completed}/4 點完成 (最大傾角 {featured.ut_max_tilt_deg:.2f}°)</div>
            <div style="color:#CBD5E1;font-size:11px;margin-top:2px;">平均測厚誤差 ±{featured.ut_avg_thickness_error_mm:.2f} mm</div>
          </div>
          <div style="background:#091322;padding:10px 12px;border-radius:8px;border:1px solid #1E293B;">
            <div style="color:#94A3B8;font-size:11px;">機體安全與故障應變</div>
            <div style="font-weight:700;color:#F8FAFC;font-size:14px;margin-top:2px;">機體完整度 {featured.hull_integrity_pct:.1f}%</div>
            <div style="color:#CBD5E1;font-size:11px;margin-top:2px;">T3 失效返航：{'通過' if featured.t3_fault_survived else '未通過'} · 纏繞：{featured.tether_snag_count} 次</div>
          </div>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center;background:#060D18;padding:10px 14px;border-radius:8px;border:1px solid #1E293B;font-size:11.5px;">
          <div>
            <span style="color:#94A3B8;">防竄改簽章 (HMAC-SHA256 Tamper-Evident Seal)：</span>
            <code style="color:#22D3EE;font-weight:700;">{html.escape(featured.verification_hash)}</code>
          </div>
          <div style="color:#E2E8F0;font-weight:700;">
            主考簽核：{html.escape(self.instructor_name)}
          </div>
        </div>
      </div>
"""

        html_doc = f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <title>ROV-01 B2B 企業飛手訓練中心批量考核與防竄改認證證書 ({html.escape(self.cohort_id)})</title>
  <style>
    body {{
      background: #090D16;
      color: #E2E8F0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans TC", monospace;
      margin: 0;
      padding: 24px 32px;
    }}
    @media print {{
      body {{ background: #090D16 !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    }}
  </style>
</head>
<body>
  <div style="max-width:1180px;margin:0 auto;">
    {feat_block}
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px;">
      <div style="background:#0F172A;padding:12px 14px;border-radius:8px;border:1px solid #1E293B;">
        <div style="font-size:11px;color:#94A3B8;">梯次合格率 (Cohort Pass Rate)</div>
        <div style="font-size:24px;font-weight:800;color:#10B981;">{summary['cohort_pass_rate']:.1f}% <span style="font-size:12px;color:#94A3B8;">({summary['certified_pass_count']}/{summary['total_runs']} 合格)</span></div>
      </div>
      <div style="background:#0F172A;padding:12px 14px;border-radius:8px;border:1px solid #1E293B;">
        <div style="font-size:11px;color:#94A3B8;">平均 UT 測厚誤差 (Avg UT Error)</div>
        <div style="font-size:24px;font-weight:800;color:#22D3EE;">±{summary['average_ut_thickness_error_mm']:.3f} mm</div>
      </div>
      <div style="background:#0F172A;padding:12px 14px;border-radius:8px;border:1px solid #1E293B;">
        <div style="font-size:11px;color:#94A3B8;">最常見扣分危害 (Top Hazard Deduction)</div>
        <div style="font-size:15px;font-weight:700;color:#F59E0B;margin-top:4px;">{html.escape(summary['most_frequent_hazard_deduction'])}</div>
      </div>
      <div style="background:#0F172A;padding:12px 14px;border-radius:8px;border:1px solid #1E293B;">
        <div style="font-size:11px;color:#94A3B8;">全梯次 SHA-256 簽章驗證</div>
        <div style="font-size:16px;font-weight:800;color:{'#10B981' if summary['all_signatures_valid'] else '#EF4444'};margin-top:4px;">
          {'✔ 100% VALID SEAL' if summary['all_signatures_valid'] else '✘ SIGNATURE MISMATCH'}
        </div>
      </div>
    </div>

    <div style="background:#0F172A;border:1px solid #1E293B;border-radius:10px;padding:16px;margin-bottom:18px;">
      <div style="font-size:14px;font-weight:700;color:#F8FAFC;margin-bottom:10px;">
        B2B 飛手批量考核成績名冊 ({html.escape(self.cohort_name)})
      </div>
      <table style="width:100%;border-collapse:collapse;font-size:12px;">
        <thead>
          <tr style="border-bottom:2px solid #334155;color:#94A3B8;text-align:left;">
            <th style="padding:8px 6px;">#</th>
            <th style="padding:8px 6px;">飛手編號與姓名</th>
            <th style="padding:8px 6px;">部門 / 單位</th>
            <th style="padding:8px 6px;">SOP 課目</th>
            <th style="padding:8px 6px;">機體完整度</th>
            <th style="padding:8px 6px;">UT 測厚 (最大傾角)</th>
            <th style="padding:8px 6px;">T3 失效返航</th>
            <th style="padding:8px 6px;">纏繞次數</th>
            <th style="padding:8px 6px;">總分</th>
            <th style="padding:8px 6px;">評等</th>
            <th style="padding:8px 6px;">認證狀態</th>
            <th style="padding:8px 6px;">HMAC-SHA256 簽章</th>
          </tr>
        </thead>
        <tbody>
          {''.join(rows_html)}
        </tbody>
      </table>
    </div>

    <div style="display:flex;justify-content:space-between;align-items:center;border-top:1px solid #1E293B;padding-top:14px;font-size:12px;color:#94A3B8;">
      <div>
        載具型號：<b>ROV-01 (6-Thruster Open-Frame Industrial)</b> · 認證規範：<b>{html.escape(self.standard_ref)}</b>
      </div>
      <div>
        首席飛手教官簽章：<b>{html.escape(self.instructor_name)}</b> · 產出時間：<b>{html.escape(summary['generated_at'])}</b>
      </div>
    </div>
  </div>
</body>
</html>
"""
        out_path.write_text(html_doc, encoding="utf-8")
        return out_path

    @classmethod
    def create_tuesday_demo_cohort(cls) -> CohortRosterManager:
        """Create a pre-populated realistic Tuesday (10/27) B2B demo cohort across M1..M4."""
        mgr = cls(
            cohort_id="YX-B2B-20261027-DEMO",
            cohort_name="2026-10-27 週二企業客戶展示梯次 · 水下工程飛手 SOP 四課目認證考核",
            instructor_name="張爲斌 (Robin Chang) · 首席 ROV 飛手總教官",
            organization="永祥水下工程企業飛手訓練中心 (Subsea ROV Pilot Training Center)",
        )
        demo_runs = [
            TraineeSessionRecord(
                trainee_id="YX-PILOT-001",
                trainee_name="張爲斌 (Robin Chang)",
                department="永祥水下工程部 · 首席飛手組",
                mission_id="M2_HULL_UT",
                timestamp="2026-10-25 10:15:00 UTC+8",
                hull_integrity_pct=100.0,
                ut_checkpoints_completed=4,
                ut_max_tilt_deg=1.1,
                t3_fault_survived=True,
                tether_snag_count=0,
                elapsed_sec=94.5,
                total_score=98.4,
                grade="A+",
                cert_status="Certified_Pass",
                ut_avg_thickness_error_mm=0.09,
            ),
            TraineeSessionRecord(
                trainee_id="YX-PILOT-002",
                trainee_name="林承翰 (Hank Lin)",
                department="永祥水下工程部 · 巡檢一組",
                mission_id="M1_POOL_6DOF",
                timestamp="2026-10-25 10:28:12 UTC+8",
                hull_integrity_pct=100.0,
                ut_checkpoints_completed=4,
                ut_max_tilt_deg=1.5,
                t3_fault_survived=True,
                tether_snag_count=0,
                elapsed_sec=78.2,
                total_score=94.6,
                grade="A+",
                cert_status="Certified_Pass",
                ut_avg_thickness_error_mm=0.11,
            ),
            TraineeSessionRecord(
                trainee_id="YX-PILOT-003",
                trainee_name="陳冠宇 (Eric Chen)",
                department="離岸風電海事工程承包商 · 甲班",
                mission_id="M3_T3_FAULT_RETURN",
                timestamp="2026-10-25 10:42:35 UTC+8",
                hull_integrity_pct=92.0,
                ut_checkpoints_completed=4,
                ut_max_tilt_deg=1.8,
                t3_fault_survived=True,
                tether_snag_count=0,
                elapsed_sec=132.4,
                total_score=87.2,
                grade="A",
                cert_status="Certified_Pass",
                ut_avg_thickness_error_mm=0.14,
            ),
            TraineeSessionRecord(
                trainee_id="YX-PILOT-004",
                trainee_name="黃柏鈞 (kevin_h)",
                department="離岸風電海事工程承包商 · 甲班",
                mission_id="M4_PIPELINE_TRIAL",
                timestamp="2026-10-25 10:56:10 UTC+8",
                hull_integrity_pct=88.5,
                ut_checkpoints_completed=4,
                ut_max_tilt_deg=2.1,
                t3_fault_survived=True,
                tether_snag_count=1,
                elapsed_sec=115.8,
                total_score=83.5,
                grade="A",
                cert_status="Certified_Pass",
                ut_avg_thickness_error_mm=0.16,
            ),
            TraineeSessionRecord(
                trainee_id="YX-PILOT-005",
                trainee_name="吳宗憲 (Sam Wu)",
                department="港灣防蝕檢測外包商 · 乙班",
                mission_id="M2_HULL_UT",
                timestamp="2026-10-25 11:10:44 UTC+8",
                hull_integrity_pct=76.5,
                ut_checkpoints_completed=3,
                ut_max_tilt_deg=3.8,
                t3_fault_survived=True,
                tether_snag_count=1,
                elapsed_sec=164.0,
                total_score=74.2,
                grade="B",
                cert_status="Conditional_Retest",
                ut_avg_thickness_error_mm=0.28,
            ),
            TraineeSessionRecord(
                trainee_id="YX-PILOT-006",
                trainee_name="蔡明哲 (Alex Tsai)",
                department="港灣防蝕檢測外包商 · 乙班",
                mission_id="M3_T3_FAULT_RETURN",
                timestamp="2026-10-25 11:24:19 UTC+8",
                hull_integrity_pct=0.0,
                ut_checkpoints_completed=1,
                ut_max_tilt_deg=6.4,
                t3_fault_survived=False,
                tether_snag_count=2,
                elapsed_sec=68.5,
                total_score=0.0,
                grade="F",
                cert_status="Failed_Retry",
                ut_avg_thickness_error_mm=0.45,
            ),
        ]
        for r in demo_runs:
            mgr.add_record(r)
        return mgr
