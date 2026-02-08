"""
Admin Routes - Admin endpoints for promotion, post, and community management
"""

from fastapi import APIRouter, HTTPException, Request, status, Query
from typing import Optional

from src.schemas.promotion import *
from src.schemas.post import *
from src.schemas.community import *
from src.services.promotion import PromotionService
from src.services.post import PostService
from src.services.community import CommunityService
from src.utils.promotion_utils import (
    get_admin_id_from_request,
    promotion_to_response
)
from src.utils.post_utils import (
    post_to_response, posts_to_paginated_response,
    change_request_to_response, change_requests_to_paginated_response
)
from src.utils.community_utils import (
    community_to_response, communities_to_paginated_response
)


router = APIRouter(prefix="/admin", tags=["Admin"])
promotion_service = PromotionService()
post_service = PostService()
community_service = CommunityService()


# ============================================================================
# Promotion Admin Endpoints
# ============================================================================

@router.post(
    "/promos/get",
    response_model=PromotionResponse,
    responses={404: {"model": ErrorResponse}}
)
async def get_promotion(request_data: GetPromotionRequest):
    """Get promotion by ID (admin access)"""
    try:
        promotion = await promotion_service.get_promotion_by_id(request_data.promotion_id)
        return promotion_to_response(promotion)

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "PROMOTION_NOT_FOUND", "message": "Promotion not found"}}
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )


# ============================================================================
# Post Admin Endpoints
# ============================================================================

@router.post(
    "/posts",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
    responses={422: {"description": "Validation error"}}
)
async def create_global_post(request_data: CreateGlobalPostRequest, request: Request):
    """
    Create a global-only post (admin only).

    - Post is immediately visible in global feed
    - No community association
    """
    try:
        admin_id, _ = get_admin_id_from_request(request)

        post = await post_service.create_global_post(
            admin_id=admin_id,
            post_type=request_data.post_type,
            text_content=request_data.text_content,
            media=[m.model_dump() for m in request_data.media] if request_data.media else None,
            link_preview=request_data.link_preview.model_dump() if request_data.link_preview else None,
            poll=request_data.poll.model_dump() if request_data.poll else None,
            tags=request_data.tags,
            mentions=[m.model_dump() for m in request_data.mentions] if request_data.mentions else None
        )
        return post_to_response(post)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_REQUEST", "message": str(e)}}
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )


@router.get(
    "/posts/pending-distribution",
    response_model=PaginatedPostsResponse,
    responses={400: {"description": "Invalid request"}}
)
async def list_pending_distribution(
    request: Request,
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=100, description="Number of posts to return")
):
    """
    List posts pending global distribution approval.
    """
    try:
        # Verify admin access
        get_admin_id_from_request(request)

        posts, has_more = await post_service.get_pending_distribution_posts(
            cursor=cursor,
            limit=limit
        )
        return posts_to_paginated_response(posts, limit, has_more)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_REQUEST", "message": str(e)}}
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )


@router.post(
    "/posts/global-distribution/approve",
    response_model=PostResponse,
    responses={
        404: {"description": "Post not found"},
        409: {"description": "Invalid distribution state"}
    }
)
async def approve_global_distribution(request_data: ApproveGlobalDistributionRequest, request: Request):
    """
    Approve global distribution for a post.
    """
    try:
        admin_id, _ = get_admin_id_from_request(request)

        post = await post_service.approve_global_distribution(
            post_id=request_data.post_id,
            admin_id=admin_id
        )
        return post_to_response(post)

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "POST_NOT_FOUND", "message": error_msg}}
            )
        elif "not pending" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "INVALID_DISTRIBUTION_STATE", "message": error_msg}}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "INVALID_REQUEST", "message": error_msg}}
            )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )


@router.post(
    "/posts/global-distribution/reject",
    response_model=PostResponse,
    responses={
        404: {"description": "Post not found"},
        409: {"description": "Invalid distribution state"}
    }
)
async def reject_global_distribution(request_data: RejectGlobalDistributionRequest, request: Request):
    """
    Reject global distribution for a post.
    """
    try:
        admin_id, _ = get_admin_id_from_request(request)

        post = await post_service.reject_global_distribution(
            post_id=request_data.post_id,
            admin_id=admin_id,
            reason=request_data.reason
        )
        return post_to_response(post)

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "POST_NOT_FOUND", "message": error_msg}}
            )
        elif "not pending" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "INVALID_DISTRIBUTION_STATE", "message": error_msg}}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "INVALID_REQUEST", "message": error_msg}}
            )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )


@router.post(
    "/posts/global-distribution/revoke",
    response_model=PostResponse,
    responses={
        404: {"description": "Post not found"},
        409: {"description": "Post is not globally approved"}
    }
)
async def revoke_global_distribution(request_data: RevokeGlobalDistributionRequest, request: Request):
    """
    Revoke global distribution for a previously approved post.
    """
    try:
        admin_id, _ = get_admin_id_from_request(request)

        post = await post_service.revoke_global_distribution(
            post_id=request_data.post_id,
            admin_id=admin_id,
            reason=request_data.reason
        )
        return post_to_response(post)

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "POST_NOT_FOUND", "message": error_msg}}
            )
        elif "not globally approved" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "INVALID_DISTRIBUTION_STATE", "message": error_msg}}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "INVALID_REQUEST", "message": error_msg}}
            )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )


# ============================================================================
# Change Request Admin Endpoints
# ============================================================================

@router.get(
    "/change-requests/pending",
    response_model=PaginatedChangeRequestsResponse,
    responses={400: {"description": "Invalid request"}}
)
async def list_pending_change_requests(
    request: Request,
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=100, description="Number of requests to return")
):
    """
    List pending change requests.
    """
    try:
        # Verify admin access
        get_admin_id_from_request(request)

        requests_list, has_more = await post_service.get_pending_change_requests(
            cursor=cursor,
            limit=limit
        )
        return change_requests_to_paginated_response(requests_list, limit, has_more)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_REQUEST", "message": str(e)}}
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )


@router.post(
    "/change-requests/approve",
    response_model=ChangeRequestResponse,
    responses={
        404: {"description": "Change request not found"},
        409: {"description": "Request already processed"}
    }
)
async def approve_change_request(request_data: ApproveChangeRequestRequest, request: Request):
    """
    Approve a change request and apply changes to the post.
    """
    try:
        admin_id, _ = get_admin_id_from_request(request)

        change_request, _ = await post_service.approve_change_request(
            request_id=request_data.request_id,
            admin_id=admin_id,
            notes=request_data.notes
        )
        return change_request_to_response(change_request)

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "CHANGE_REQUEST_NOT_FOUND", "message": error_msg}}
            )
        elif "not pending" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "REQUEST_ALREADY_PROCESSED", "message": error_msg}}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "INVALID_REQUEST", "message": error_msg}}
            )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )


@router.post(
    "/change-requests/reject",
    response_model=ChangeRequestResponse,
    responses={
        404: {"description": "Change request not found"},
        409: {"description": "Request already processed"}
    }
)
async def reject_change_request(request_data: RejectChangeRequestRequest, request: Request):
    """
    Reject a change request.
    """
    try:
        admin_id, _ = get_admin_id_from_request(request)

        change_request = await post_service.reject_change_request(
            request_id=request_data.request_id,
            admin_id=admin_id,
            notes=request_data.notes
        )
        return change_request_to_response(change_request)

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "CHANGE_REQUEST_NOT_FOUND", "message": error_msg}}
            )
        elif "not pending" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "REQUEST_ALREADY_PROCESSED", "message": error_msg}}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "INVALID_REQUEST", "message": error_msg}}
            )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )


# ============================================================================
# Community Admin Endpoints
# ============================================================================

@router.post(
    "/communities/suspend",
    response_model=CommunityResponse,
    responses={
        404: {"description": "Community not found"},
        409: {"description": "Version conflict or invalid status"}
    }
)
async def suspend_community(request_data: SuspendCommunityRequest, request: Request):
    """Suspend a community (admin only)."""
    try:
        admin_id, _ = get_admin_id_from_request(request)

        community = await community_service.suspend_community(
            community_id=request_data.community_id,
            admin_id=admin_id,
            reason=request_data.reason,
            expected_version=request_data.expected_version
        )
        return community_to_response(community)

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "COMMUNITY_NOT_FOUND", "message": error_msg}}
            )
        elif "version conflict" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "VERSION_CONFLICT", "message": error_msg}}
            )
        elif "cannot suspend" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "INVALID_STATUS_TRANSITION", "message": error_msg}}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "INVALID_REQUEST", "message": error_msg}}
            )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )


@router.post(
    "/communities/unsuspend",
    response_model=CommunityResponse,
    responses={
        404: {"description": "Community not found"},
        409: {"description": "Version conflict or invalid status"}
    }
)
async def unsuspend_community(request_data: UnsuspendCommunityRequest, request: Request):
    """Unsuspend a community (admin only)."""
    try:
        admin_id, _ = get_admin_id_from_request(request)

        community = await community_service.unsuspend_community(
            community_id=request_data.community_id,
            admin_id=admin_id,
            reason=request_data.reason,
            expected_version=request_data.expected_version
        )
        return community_to_response(community)

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "COMMUNITY_NOT_FOUND", "message": error_msg}}
            )
        elif "version conflict" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "VERSION_CONFLICT", "message": error_msg}}
            )
        elif "cannot unsuspend" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "INVALID_STATUS_TRANSITION", "message": error_msg}}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "INVALID_REQUEST", "message": error_msg}}
            )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )


@router.post(
    "/communities/feature",
    response_model=CommunityResponse,
    responses={
        404: {"description": "Community not found"},
        409: {"description": "Community not active"}
    }
)
async def feature_community(request_data: FeatureCommunityRequest, request: Request):
    """Feature a community (admin only)."""
    try:
        admin_id, _ = get_admin_id_from_request(request)

        community = await community_service.feature_community(
            community_id=request_data.community_id,
            admin_id=admin_id,
            duration_days=request_data.duration_days
        )
        return community_to_response(community)

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "COMMUNITY_NOT_FOUND", "message": error_msg}}
            )
        elif "only active" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "COMMUNITY_NOT_ACTIVE", "message": error_msg}}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "INVALID_REQUEST", "message": error_msg}}
            )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )


@router.post(
    "/communities/unfeature",
    response_model=CommunityResponse,
    responses={
        404: {"description": "Community not found"},
        409: {"description": "Community not featured"}
    }
)
async def unfeature_community(request_data: UnfeatureCommunityRequest, request: Request):
    """Unfeature a community (admin only)."""
    try:
        admin_id, _ = get_admin_id_from_request(request)

        community = await community_service.unfeature_community(
            community_id=request_data.community_id,
            admin_id=admin_id
        )
        return community_to_response(community)

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "COMMUNITY_NOT_FOUND", "message": error_msg}}
            )
        elif "not featured" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "NOT_FEATURED", "message": error_msg}}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "INVALID_REQUEST", "message": error_msg}}
            )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )


@router.get(
    "/communities/suspended",
    response_model=PaginatedCommunitiesResponse,
    responses={400: {"description": "Invalid request"}}
)
async def list_suspended_communities(
    request: Request,
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=100, description="Results per page")
):
    """List suspended communities (admin only)."""
    try:
        get_admin_id_from_request(request)

        communities, has_more = await community_service.list_suspended_communities(
            cursor=cursor,
            limit=limit
        )
        return communities_to_paginated_response(communities, limit, has_more)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_REQUEST", "message": str(e)}}
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )


@router.get(
    "/communities/moderation-log",
    response_model=PaginatedModerationLogsResponse,
    responses={400: {"description": "Invalid request"}}
)
async def get_moderation_log(
    request: Request,
    community_id: str = Query(..., description="Community ID"),
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=100, description="Results per page")
):
    """Get moderation history for a community (admin only)."""
    try:
        get_admin_id_from_request(request)

        logs, has_more = await community_service.get_moderation_log(
            community_id=community_id,
            cursor=cursor,
            limit=limit
        )
        return moderation_logs_to_paginated_response(logs, limit, has_more)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_REQUEST", "message": str(e)}}
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )