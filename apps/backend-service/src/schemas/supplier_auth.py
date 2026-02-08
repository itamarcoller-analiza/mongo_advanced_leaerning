"""
Supplier Authentication Request/Response Schemas
"""

from pydantic import BaseModel, EmailStr, Field, HttpUrl
from typing import Optional, Dict, List


# Request Schemas
class RegisterSupplierRequest(BaseModel):
    """Supplier registration request"""
    # Contact Information
    primary_email: EmailStr = Field(..., description="Primary business email")
    phone: str = Field(..., min_length=10, max_length=20, description="Business phone (E.164 format)")
    contact_person_name: str = Field(..., min_length=2, max_length=100, description="Contact person full name")
    contact_person_title: Optional[str] = Field(None, max_length=100, description="Contact person job title")

    # Company Information
    legal_name: str = Field(..., min_length=2, max_length=200, description="Legal company name")
    company_type: str = Field(..., description="Company type: corporation, llc, partnership, or sole_proprietorship")
    tax_id: str = Field(..., min_length=1, description="Tax ID / EIN / VAT number")
    tax_id_country: str = Field(..., min_length=2, max_length=2, description="2-letter ISO country code for tax ID")

    # Business Address
    street_address: str = Field(..., min_length=1, max_length=200, description="Street address")
    city: str = Field(..., min_length=1, max_length=100, description="City")
    state: Optional[str] = Field(None, max_length=100, description="State/Province")
    zip_code: str = Field(..., min_length=1, max_length=20, description="Postal/ZIP code")
    country: str = Field(..., min_length=2, max_length=2, description="2-letter ISO country code")

    # Business Information
    industry_category: str = Field(..., description="Industry category")
    description: str = Field(..., min_length=20, max_length=2000, description="Business description")
    website: Optional[HttpUrl] = Field(None, description="Company website URL")

    # Authentication
    password: str = Field(..., min_length=10, max_length=128, description="Secure password")

    # Terms Acceptance
    terms_accepted: bool = Field(..., description="Terms of Service acceptance")
    privacy_policy_accepted: bool = Field(..., description="Privacy Policy acceptance")


class LoginSupplierRequest(BaseModel):
    """Supplier login request"""
    email: EmailStr = Field(..., description="Supplier email address")
    password: str = Field(..., description="Supplier password")


class ForgotPasswordRequest(BaseModel):
    """Forgot password request"""
    email: EmailStr = Field(..., description="Supplier email address")


class ResetPasswordRequest(BaseModel):
    """Reset password request"""
    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=10, max_length=128, description="New password")


# Response Schemas
class SupplierResponse(BaseModel):
    """Supplier data response"""
    id: str = Field(..., description="Supplier ID")
    email: str = Field(..., description="Primary email")
    company_name: str = Field(..., description="Legal company name")
    status: str = Field(..., description="Account status")


class RegisterSupplierResponse(BaseModel):
    """Supplier registration response"""
    supplier: SupplierResponse = Field(..., description="Supplier data")
    message: str = Field(..., description="Success message")
    next_steps: List[str] = Field(..., description="Next steps to complete")


class LoginSupplierResponse(BaseModel):
    """Supplier login response"""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(default=1800, description="Access token expiry in seconds")
    supplier: SupplierResponse = Field(..., description="Supplier data")


class MessageResponse(BaseModel):
    """Generic message response"""
    message: str = Field(..., description="Response message")


class ErrorResponse(BaseModel):
    """Error response"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Error details")
