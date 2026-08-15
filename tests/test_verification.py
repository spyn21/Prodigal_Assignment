import pytest

from src.verification import verify_identity


def test_correct_name_plus_correct_dob_verifies():
    account = {"full_name": "Rahul Mehta", "dob": "1988-02-29", "aadhaar_last4": "1357", "pincode": "400004"}
    candidate = {"full_name": "Rahul Mehta", "dob": "1988-02-29"}
    result = verify_identity(account, candidate)
    assert result.verified is True
    assert result.exact_full_name_match is True
    assert result.exact_dob_match is True


def test_correct_name_plus_correct_aadhaar_verifies():
    account = {"full_name": "Nithin Jain", "dob": "1990-05-14", "aadhaar_last4": "4321", "pincode": "400001"}
    candidate = {"full_name": "Nithin Jain", "aadhaar_last4": "4321"}
    result = verify_identity(account, candidate)
    assert result.verified is True
    assert result.exact_aadhaar_last4_match is True


def test_correct_name_plus_correct_pincode_verifies():
    account = {"full_name": "Nithin Jain", "dob": "1990-05-14", "aadhaar_last4": "4321", "pincode": "400001"}
    candidate = {"full_name": "Nithin Jain", "pincode": "400001"}
    result = verify_identity(account, candidate)
    assert result.verified is True
    assert result.exact_pincode_match is True


def test_wrong_name_plus_correct_dob_fails():
    account = {"full_name": "Nithin Jain", "dob": "1990-05-14", "aadhaar_last4": "4321", "pincode": "400001"}
    candidate = {"full_name": "Nithin J", "dob": "1990-05-14"}
    result = verify_identity(account, candidate)
    assert result.verified is False
    assert result.exact_full_name_match is False


def test_name_capitalization_difference_is_not_accepted():
    account = {"full_name": "Nithin Jain", "dob": "1990-05-14", "aadhaar_last4": "4321", "pincode": "400001"}
    candidate = {"full_name": "nithin jain", "dob": "1990-05-14"}
    result = verify_identity(account, candidate)
    assert result.verified is False
    assert result.exact_full_name_match is False


def test_correct_name_with_wrong_dob_fails():
    account = {"full_name": "Nithin Jain", "dob": "1990-05-14", "aadhaar_last4": "4321", "pincode": "400001"}
    candidate = {"full_name": "Nithin Jain", "dob": "1990-05-15"}
    result = verify_identity(account, candidate)
    assert result.verified is False


def test_correct_name_without_secondary_is_incomplete():
    account = {"full_name": "Nithin Jain", "dob": "1990-05-14", "aadhaar_last4": "4321", "pincode": "400001"}
    candidate = {"full_name": "Nithin Jain"}
    result = verify_identity(account, candidate)
    assert result.verified is False
    assert result.reason == "incomplete_identity"


def test_secondary_without_name_is_incomplete():
    account = {"full_name": "Nithin Jain", "dob": "1990-05-14", "aadhaar_last4": "4321", "pincode": "400001"}
    candidate = {"dob": "1990-05-14"}
    result = verify_identity(account, candidate)
    assert result.verified is False
    assert result.reason == "name_required"


def test_verification_accepts_leap_day_date_for_account_1004():
    account = {"full_name": "Rahul Mehta", "dob": "1988-02-29", "aadhaar_last4": "1357", "pincode": "400004"}
    candidate = {"full_name": "Rahul Mehta", "dob": "1988-02-29"}
    result = verify_identity(account, candidate)
    assert result.verified is True
