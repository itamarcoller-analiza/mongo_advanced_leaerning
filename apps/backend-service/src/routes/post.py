"""
Post Routes - User-facing post endpoints
"""

from fastapi import APIRouter, HTTPException, Request, status

from src.schemas.post import *
from src.services.post import PostService
from src.utils.post_utils import *

router = APIRouter(prefix="/posts", tags=["Posts"])
post_service = PostService()


# ============================================================================
# Home Feed
# ============================================================================

@router.post(
    "/feed",
    response_model=PaginatedPostsResponse,
    responses={400: {"description": "Invalid request"}}
)
async def get_home_feed(request_data: GetHomeFeedRequest, request: Request):
    """
    Get personalized home feed.

    Returns posts from:
    - User's joined communities
    - Globally approved posts
    """
    try:
        user_id = get_user_id_from_request(request)

        posts, has_more = await post_service.get_home_feed(
            user_id=user_id,
            cursor=request_data.cursor,
            limit=request_data.limit
        )
        return posts_to_paginated_response(posts, request_data.limit, has_more)

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


# ============================================================================
# Get Single Post
# ============================================================================

@router.post(
    "/get",
    response_model=PostResponse,
    responses={404: {"description": "Post not found"}}
)
async def get_post(request_data: GetPostRequest, request: Request):
    """
    Get a single post by ID.
    """
    try:
        user_id = get_user_id_from_request(request)

        post = await post_service.get_post(
            post_id=request_data.post_id,
            user_id=user_id
        )
        return post_to_response(post)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "POST_NOT_FOUND", "message": str(e)}}
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )


# ============================================================================
# Update Post
# ============================================================================

@router.post(
    "/update",
    response_model=PostResponse,
    responses={
        403: {"description": "Cannot edit globally-tagged posts"},
        404: {"description": "Post not found"},
        409: {"description": "Version conflict"}
    }
)
async def update_post(request_data: UpdatePostRequest, request: Request):
    """
    Update a post.

    - Only author or community leader can update
    - Cannot directly update globally-tagged posts (use change request)
    - Requires version for optimistic locking
    """
    try:
        user_id = get_user_id_from_request(request)

        post = await post_service.update_post(
            post_id=request_data.post_id,
            user_id=user_id,
            version=request_data.version,
            text_content=request_data.text_content,
            media=[m.model_dump() for m in request_data.media] if request_data.media else None,
            link_preview=request_data.link_preview.model_dump() if request_data.link_preview else None,
            tags=request_data.tags
        )
        return post_to_response(post)

    except ValueError as e:
        error_msg = str(e)
        if "globally-tagged" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "GLOBAL_EDIT_REQUIRES_REQUEST", "message": error_msg}}
            )
        elif "version conflict" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "VERSION_CONFLICT", "message": error_msg}}
            )
        elif "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "POST_NOT_FOUND", "message": error_msg}}
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
# Delete Post
# ============================================================================

@router.post(
    "/delete",
    response_model=PostResponse,
    responses={
        403: {"description": "Admin required for global posts"},
        404: {"description": "Post not found"},
        409: {"description": "Version conflict"}
    }
)
async def delete_post(request_data: DeletePostRequest, request: Request):
    """
    Soft delete a post.

    - Draft posts: only author can delete
    - Published posts: only leader/admin can delete
    - Globally-distributed posts: only admin can delete
    """
    try:
        user_id = get_user_id_from_request(request)
        is_admin = get_admin_status_from_request(request)

        post = await post_service.delete_post(
            post_id=request_data.post_id,
            user_id=user_id,
            version=request_data.version,
            is_admin=is_admin
        )
        return post_to_response(post)

    except ValueError as e:
        error_msg = str(e)
        if "only admins" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "ADMIN_REQUIRED_FOR_GLOBAL_DELETE", "message": error_msg}}
            )
        elif "version conflict" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "VERSION_CONFLICT", "message": error_msg}}
            )
        elif "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "POST_NOT_FOUND", "message": error_msg}}
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
# Publish Draft Post
# ============================================================================

@router.post(
    "/publish",
    response_model=PostResponse,
    responses={
        404: {"description": "Post not found"},
        409: {"description": "Version conflict"},
        422: {"description": "Post is not a draft"}
    }
)
async def publish_post(request_data: PublishPostRequest, request: Request):
    """
    Publish a draft post.

    - Only author can publish
    - Set request_global_distribution=true to request global visibility
    """
    try:
        user_id = get_user_id_from_request(request)

        post = await post_service.publish_post(
            post_id=request_data.post_id,
            user_id=user_id,
            version=request_data.version,
            request_global_distribution=request_data.request_global_distribution
        )
        return post_to_response(post)

    except ValueError as e:
        error_msg = str(e)
        if "version conflict" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "VERSION_CONFLICT", "message": error_msg}}
            )
        elif "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "POST_NOT_FOUND", "message": error_msg}}
            )
        elif "draft" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "POST_NOT_DRAFT", "message": error_msg}}
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
# Global Distribution
# ============================================================================

@router.post(
    "/global-distribution/request",
    response_model=PostResponse,
    responses={
        404: {"description": "Post not found"},
        409: {"description": "Already requested or version conflict"},
        422: {"description": "Cannot request distribution"}
    }
)
async def request_global_distribution(request_data: RequestGlobalDistributionRequest, request: Request):
    """
    Request global distribution for a published post.

    - Only author can request
    - Post must be published and in a community
    - Cannot request if already pending/approved
    """
    try:
        user_id = get_user_id_from_request(request)

        post = await post_service.request_global_distribution(
            post_id=request_data.post_id,
            user_id=user_id,
            version=request_data.version
        )
        return post_to_response(post)

    except ValueError as e:
        error_msg = str(e)
        if "version conflict" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "VERSION_CONFLICT", "message": error_msg}}
            )
        elif "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "POST_NOT_FOUND", "message": error_msg}}
            )
        elif "cannot request" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "DISTRIBUTION_NOT_ALLOWED", "message": error_msg}}
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
# Change Requests
# ============================================================================

@router.post(
    "/change-requests",
    response_model=ChangeRequestResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Post not found"},
        409: {"description": "Pending request already exists"},
        422: {"description": "Post is not globally tagged"}
    }
)
async def create_change_request(request_data: CreateChangeRequestRequest, request: Request):
    """
    Create a change request for a globally-tagged post.

    - Required for posts with pending/approved global distribution
    - Only one pending request per post allowed
    """
    try:
        user_id = get_user_id_from_request(request)

        change_request = await post_service.create_change_request(
            post_id=request_data.post_id,
            user_id=user_id,
            requested_changes=request_data.requested_changes,
            reason=request_data.reason
        )
        return change_request_to_response(change_request)

    except ValueError as e:
        error_msg = str(e)
        if "pending change request already exists" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "PENDING_REQUEST_EXISTS", "message": error_msg}}
            )
        elif "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "POST_NOT_FOUND", "message": error_msg}}
            )
        elif "not globally tagged" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "NOT_GLOBALLY_TAGGED", "message": error_msg}}
            )
        elif "cannot change" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "INVALID_CHANGE_FIELDS", "message": error_msg}}
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
    "/change-requests/list",
    response_model=PaginatedChangeRequestsResponse,
    responses={404: {"description": "Post not found"}}
)
async def list_change_requests(request_data: ListChangeRequestsRequest, request: Request):
    """
    List change requests for a post.
    """
    try:
        user_id = get_user_id_from_request(request)

        requests_list, has_more = await post_service.list_change_requests(
            post_id=request_data.post_id,
            user_id=user_id,
            cursor=request_data.cursor,
            limit=request_data.limit,
            status_filter=request_data.status
        )
        return change_requests_to_paginated_response(requests_list, request_data.limit, has_more)

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "POST_NOT_FOUND", "message": error_msg}}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "INVALID_REQUEST", "message": error_msg}}
            )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )


# ============================================================================
# Moderation (Leader/Admin)
# ============================================================================

@router.post(
    "/hide",
    response_model=PostResponse,
    responses={
        404: {"description": "Post not found"},
        409: {"description": "Version conflict or cannot hide"}
    }
)
async def hide_post(request_data: HidePostRequest, request: Request):
    """
    Hide a post (leader/admin only).
    """
    try:
        user_id = get_user_id_from_request(request)
        is_admin = get_admin_status_from_request(request)

        post = await post_service.hide_post(
            post_id=request_data.post_id,
            user_id=user_id,
            version=request_data.version,
            reason=request_data.reason,
            is_admin=is_admin
        )
        return post_to_response(post)

    except ValueError as e:
        error_msg = str(e)
        if "version conflict" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "VERSION_CONFLICT", "message": error_msg}}
            )
        elif "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "POST_NOT_FOUND", "message": error_msg}}
            )
        elif "only hide published" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "CANNOT_HIDE_NON_PUBLISHED", "message": error_msg}}
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
    "/unhide",
    response_model=PostResponse,
    responses={
        404: {"description": "Post not found"},
        409: {"description": "Version conflict or post not hidden"}
    }
)
async def unhide_post(request_data: UnhidePostRequest, request: Request):
    """
    Unhide a hidden post (leader/admin only).
    """
    try:
        user_id = get_user_id_from_request(request)
        is_admin = get_admin_status_from_request(request)

        post = await post_service.unhide_post(
            post_id=request_data.post_id,
            user_id=user_id,
            version=request_data.version,
            is_admin=is_admin
        )
        return post_to_response(post)

    except ValueError as e:
        error_msg = str(e)
        if "version conflict" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "VERSION_CONFLICT", "message": error_msg}}
            )
        elif "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "POST_NOT_FOUND", "message": error_msg}}
            )
        elif "not hidden" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "POST_NOT_HIDDEN", "message": error_msg}}
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
    "/pin",
    response_model=PostResponse,
    responses={
        404: {"description": "Post not found"},
        409: {"description": "Version conflict or max pins reached"}
    }
)
async def pin_post(request_data: PinPostRequest, request: Request):
    """
    Pin a post in community (leader only).
    """
    try:
        user_id = get_user_id_from_request(request)
        is_admin = get_admin_status_from_request(request)

        post = await post_service.pin_post(
            post_id=request_data.post_id,
            user_id=user_id,
            version=request_data.version,
            is_admin=is_admin
        )
        return post_to_response(post)

    except ValueError as e:
        error_msg = str(e)
        if "version conflict" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "VERSION_CONFLICT", "message": error_msg}}
            )
        elif "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "POST_NOT_FOUND", "message": error_msg}}
            )
        elif "maximum" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "MAX_PINS_REACHED", "message": error_msg}}
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
    "/unpin",
    response_model=PostResponse,
    responses={
        404: {"description": "Post not found"},
        409: {"description": "Version conflict or post not pinned"}
    }
)
async def unpin_post(request_data: UnpinPostRequest, request: Request):
    """
    Unpin a post (leader only).
    """
    try:
        user_id = get_user_id_from_request(request)
        is_admin = get_admin_status_from_request(request)

        post = await post_service.unpin_post(
            post_id=request_data.post_id,
            user_id=user_id,
            version=request_data.version,
            is_admin=is_admin
        )
        return post_to_response(post)

    except ValueError as e:
        error_msg = str(e)
        if "version conflict" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "VERSION_CONFLICT", "message": error_msg}}
            )
        elif "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "POST_NOT_FOUND", "message": error_msg}}
            )
        elif "not pinned" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "POST_NOT_PINNED", "message": error_msg}}
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
