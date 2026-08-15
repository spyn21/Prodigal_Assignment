from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from src.validators import normalize_date


@dataclass(frozen=True)
class VerificationResult:
    verified: bool
    exact_full_name_match: bool
    exact_dob_match: bool
    exact_aadhaar_last4_match: bool
    exact_pincode_match: bool
    reason: str
    name_provided: bool
    secondary_provided: bool


def verify_identity(account: Optional[Mapping[str, Any]], candidate: Optional[Mapping[str, Any]]) -> VerificationResult:
    if not account:
        return VerificationResult(False, False, False, False, False, "missing_account", False, False)
    if not candidate:
        return VerificationResult(False, False, False, False, False, "missing_candidate", False, False)

    expected_name = account.get("full_name")
    provided_name = candidate.get("full_name")
    has_name = provided_name is not None and str(provided_name).strip() != ""
    name_match = bool(has_name and str(provided_name) == str(expected_name))

    account_dob = account.get("dob")
    candidate_dob = candidate.get("dob")
    dob_match = False
    if account_dob is not None and candidate_dob is not None:
        canonical_dob = normalize_date(candidate_dob)
        dob_match = canonical_dob is not None and canonical_dob == str(account_dob)

    account_aadhaar = account.get("aadhaar_last4")
    candidate_aadhaar = candidate.get("aadhaar_last4")
    aadhaar_match = (
        account_aadhaar is not None and candidate_aadhaar is not None and str(candidate_aadhaar) == str(account_aadhaar)
    )

    account_pincode = account.get("pincode")
    candidate_pincode = candidate.get("pincode")
    pincode_match = (
        account_pincode is not None and candidate_pincode is not None and str(candidate_pincode) == str(account_pincode)
    )

    secondary_provided = bool(candidate_dob is not None or candidate_aadhaar is not None or candidate_pincode is not None)
    if not has_name:
        return VerificationResult(False, False, dob_match, aadhaar_match, pincode_match, "name_required", False, secondary_provided)

    if not name_match:
        return VerificationResult(False, False, dob_match, aadhaar_match, pincode_match, "name_mismatch", True, secondary_provided)

    if not secondary_provided:
        return VerificationResult(False, False, False, False, False, "incomplete_identity", True, False)

    verified = bool(dob_match or aadhaar_match or pincode_match)
    if verified:
        return VerificationResult(
            True,
            True,
            dob_match,
            aadhaar_match,
            pincode_match,
            "verified",
            True,
            True,
        )

    return VerificationResult(
        False,
        True,
        dob_match,
        aadhaar_match,
        pincode_match,
        "identity_mismatch",
        True,
        True,
    )


__all__ = ["VerificationResult", "verify_identity"]
