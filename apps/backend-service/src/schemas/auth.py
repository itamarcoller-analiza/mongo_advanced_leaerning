"""
Authentication Request/Response Schemas
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict


# Request Schemas
class RegisterConsumerRequest(BaseModel):
    """Consumer registration request"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=128, description="User password")
    display_name: str = Field(..., min_length=3, max_length=50, description="Display name")


class RegisterLeaderRequest(BaseModel):
    """Leader registration request"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=128, description="User password")
    display_name: str = Field(..., min_length=3, max_length=50, description="Display name")
    company_name: str = Field(..., min_length=2, max_length=200, description="Company/brand name")
    business_type: str = Field(..., description="Business type: personal_brand, company, or agency")
    country: str = Field(..., min_length=2, max_length=2, description="2-letter ISO country code")
    city: str = Field(..., min_length=1, max_length=100, description="City")
    zip_code: str = Field(..., min_length=1, max_length=20, description="Postal/ZIP code")
    website: Optional[str] = Field(None, description="Company website URL")
    state: Optional[str] = Field(None, max_length=100, description="State/province")
    street_address: Optional[str] = Field(None, max_length=200, description="Street address")


class LoginRequest(BaseModel):
    """Login request"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class VerifyEmailRequest(BaseModel):
    """Email verification request"""
    token: str = Field(..., description="Email verification token")


class ForgotPasswordRequest(BaseModel):
    """Forgot password request"""
    email: EmailStr = Field(..., description="User email address")


class ResetPasswordRequest(BaseModel):
    """Reset password request"""
    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")


# Response Schemas
class UserResponse(BaseModel):
    """User data response"""
    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    display_name: str = Field(..., description="Display name")
    role: str = Field(..., description="User role")
    status: str = Field(..., description="Account status")
    avatar: Optional[str] = Field(None, description="Avatar URL")
    permissions: Optional[Dict[str, bool]] = Field(None, description="User permissions")


class RegisterResponse(BaseModel):
    """Registration response"""
    user: UserResponse = Field(..., description="User data")
    message: str = Field(..., description="Success message")
    verification_token: Optional[str] = Field(None, description="Email verification token (for testing)")


class LoginResponse(BaseModel):
    """Login response"""
    user: UserResponse = Field(..., description="User data")


class VerifyEmailResponse(BaseModel):
    """Email verification response"""
    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    email_verified: bool = Field(..., description="Email verification status")
    status: str = Field(..., description="Account status")


class MessageResponse(BaseModel):
    """Generic message response"""
    message: str = Field(..., description="Response message")


class ErrorResponse(BaseModel):
    """Error response"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Error details")
