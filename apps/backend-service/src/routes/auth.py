"""
Authentication Routes
"""

from fastapi import APIRouter, HTTPException, Request, status

from src.schemas.auth import *
from src.services.auth import AuthService


router = APIRouter(tags=["Authentication"])
auth_service = AuthService()


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }
)
async def register_consumer(request_data: RegisterConsumerRequest):
    """Register a new consumer user"""
    try:
        result = await auth_service.register_consumer(
            email=request_data.email,
            password=request_data.password,
            display_name=request_data.display_name
        )

        return RegisterResponse(
            user=UserResponse(**result["user"]),
            message=f"Registration successful. Verification email sent to {request_data.email}",
            verification_token=result.get("verification_token")
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during registration"
        )


@router.post(
    "/register/leader",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }
)
async def register_leader(request_data: RegisterLeaderRequest):
    """Register a new leader user (requires admin approval)"""
    try:
        result = await auth_service.register_leader(
            email=request_data.email,
            password=request_data.password,
            display_name=request_data.display_name,
            company_name=request_data.company_name,
            business_type=request_data.business_type,
            country=request_data.country,
            city=request_data.city,
            zip_code=request_data.zip_code,
            website=request_data.website,
            state=request_data.state,
            street_address=request_data.street_address
        )

        return RegisterResponse(
            user=UserResponse(**result["user"]),
            message=f"Leader registration submitted. Verification email sent to {request_data.email}. Your application will be reviewed by our team.",
            verification_token=result.get("verification_token")
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during leader registration"
        )


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }
)
async def login(request_data: LoginRequest, request: Request):
    """Authenticate user and return user data"""
    try:
        # Get IP address from request
        ip_address = request.client.host

        result = await auth_service.login(
            email=request_data.email,
            password=request_data.password,
            ip_address=ip_address
        )

        return LoginResponse(
            user=UserResponse(**result)
        )

    except ValueError as e:
        error_msg = str(e)

        # Handle specific error cases with appropriate status codes
        if "locked" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_msg
            )
        elif "not verified" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_msg
            )
        elif "suspended" in error_msg.lower() or "no longer exists" in error_msg.lower() or "pending" in error_msg.lower():
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
            detail="An error occurred during login"
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
    """Verify user email address"""
    try:
        result = await auth_service.verify_email(request_data.token)

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
    """Request password reset"""
    try:
        reset_token = await auth_service.request_password_reset(request_data.email)

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
    """Reset user password with token"""
    try:
        result = await auth_service.reset_password(
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
