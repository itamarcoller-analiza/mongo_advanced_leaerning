"""
Supplier Authentication Routes
"""

from fastapi import APIRouter, HTTPException, Request, status

from src.schemas.supplier_auth import *
from src.services.supplier_auth import SupplierAuthService


router = APIRouter(prefix="/supplier", tags=["Supplier Authentication"])
supplier_auth_service = SupplierAuthService()


@router.post(
    "/register",
    response_model=RegisterSupplierResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }
)
async def register_supplier(request_data: RegisterSupplierRequest):
    """Register a new supplier"""
    try:
        result = await supplier_auth_service.register_supplier(
            primary_email=request_data.primary_email,
            phone=request_data.phone,
            contact_person_name=request_data.contact_person_name,
            contact_person_title=request_data.contact_person_title,
            legal_name=request_data.legal_name,
            company_type=request_data.company_type,
            tax_id=request_data.tax_id,
            tax_id_country=request_data.tax_id_country,
            street_address=request_data.street_address,
            city=request_data.city,
            state=request_data.state,
            zip_code=request_data.zip_code,
            country=request_data.country,
            industry_category=request_data.industry_category,
            description=request_data.description,
            website=request_data.website,
            password=request_data.password,
            terms_accepted=request_data.terms_accepted,
            privacy_policy_accepted=request_data.privacy_policy_accepted
        )

        return RegisterSupplierResponse(
            supplier=SupplierResponse(**result["supplier"]),
            message=f"Registration successful. Verification email sent to {request_data.primary_email}",
            next_steps=[
                "Verify your email address",
                "Upload business verification documents",
                "Wait for admin approval (2-5 business days)"
            ]
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during supplier registration"
        )


@router.post(
    "/login",
    response_model=LoginSupplierResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }
)
async def login_supplier(request_data: LoginSupplierRequest, request: Request):
    """Authenticate supplier and return tokens"""
    try:
        # Get IP address from request
        ip_address = request.client.host

        result = await supplier_auth_service.login(
            email=request_data.email,
            password=request_data.password,
            ip_address=ip_address
        )

        return LoginSupplierResponse(**result)

    except ValueError as e:
        error_msg = str(e)

        # Handle specific error cases with appropriate status codes
        if "locked" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_msg
            )
        elif "suspended" in error_msg.lower() or "no longer exists" in error_msg.lower() or "deleted" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_msg
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error_msg
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during supplier login"
        )


@router.post(
    "/verify-email",
    response_model=VerifyEmailResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }
)
async def verify_email(request_data: VerifyEmailRequest):
    """Verify supplier email address"""
    try:
        result = await supplier_auth_service.verify_email(request_data.token)

        return VerifyEmailResponse(**result)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during email verification"
        )


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    responses={
        500: {"model": ErrorResponse}
    }
)
async def forgot_password(request_data: ForgotPasswordRequest):
    """Request password reset for supplier"""
    try:
        reset_token = await supplier_auth_service.request_password_reset(request_data.email)

        # Always return success to prevent email enumeration
        # TODO: Send reset email if reset_token is not None
        return MessageResponse(
            message="If the email exists, a password reset link has been sent"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing password reset request"
        )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }
)
async def reset_password(request_data: ResetPasswordRequest):
    """Reset supplier password with token"""
    try:
        result = await supplier_auth_service.reset_password(
            token=request_data.token,
            new_password=request_data.new_password
        )

        return MessageResponse(**result)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during password reset"
        )


@router.post(
    "/submit-documents",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }
)
async def submit_verification_documents(
    request_data: SubmitDocumentsRequest,
    # TODO: Add authentication dependency to get current supplier_id
    # For now, supplier_id would come from authenticated session
):
    """Submit verification documents for supplier approval"""
    try:
        # TODO: Extract supplier_id from authenticated session
        # supplier_id = get_current_supplier_id()
        supplier_id = "temp_supplier_id"  # Placeholder

        result = await supplier_auth_service.submit_verification_documents(
            supplier_id=supplier_id,
            documents=request_data.documents
        )

        return MessageResponse(**result)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while submitting documents"
        )
