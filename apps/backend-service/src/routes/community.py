"""
Community Routes - All community endpoints (CRUD, membership, posts)
"""

from fastapi import APIRouter, HTTPException, Request, status

from src.schemas.community import *
from src.schemas.post import (
    CreateCommunityPostRequest, ListCommunityPostsRequest,
    PostResponse, PaginatedPostsResponse
)
from src.services.community import CommunityService
from src.services.post import PostService
from src.utils.community_utils import *
from src.utils.post_utils import (
    get_user_id_from_request as get_post_user_id,
    post_to_response, posts_to_paginated_response
)


router = APIRouter(prefix="/communities", tags=["Communities"])
community_service = CommunityService()
post_service = PostService()


# ============================================================================
# Community CRUD
# ============================================================================

@router.post(
    "",
    response_model=CommunityResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "Not a leader"},
        409: {"description": "Slug already exists"},
        422: {"description": "Validation error"}
    }
)
async def create_community(request_data: CreateCommunityRequest, request: Request):
    """
    Create a new community.

    - Only users with role=leader can create communities
    - Slug must be unique
    """
    try:
        user_id = get_user_id_from_request(request)
        user_role = get_user_role_from_request(request)

        community = await community_service.create_community(
            user_id=user_id,
            user_role=user_role,
            data=request_data.model_dump()
        )
        return community_to_response(community)

    except ValueError as e:
        error_msg = str(e)
        if "only leaders" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "NOT_LEADER", "message": error_msg}}
            )
        elif "slug already exists" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "SLUG_ALREADY_EXISTS", "message": error_msg}}
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
    "/get",
    response_model=CommunityResponse,
    responses={404: {"description": "Community not found"}}
)
async def get_community(request_data: GetCommunityRequest, request: Request):
    """Get community by ID."""
    try:
        user_id = get_user_id_from_request(request)
        is_admin = get_admin_status_from_request(request)

        community = await community_service.get_community_by_id(
            community_id=request_data.community_id,
            user_id=user_id,
            is_admin=is_admin
        )
        return community_to_response(community)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "COMMUNITY_NOT_FOUND", "message": str(e)}}
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )


@router.post(
    "/get-by-slug",
    response_model=CommunityResponse,
    responses={404: {"description": "Community not found"}}
)
async def get_community_by_slug(request_data: GetCommunityBySlugRequest, request: Request):
    """Get community by slug."""
    try:
        user_id = get_user_id_from_request(request)
        is_admin = get_admin_status_from_request(request)

        community = await community_service.get_community_by_slug(
            slug=request_data.slug,
            user_id=user_id,
            is_admin=is_admin
        )
        return community_to_response(community)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "COMMUNITY_NOT_FOUND", "message": str(e)}}
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )


@router.post(
    "/discover",
    response_model=PaginatedCommunitiesResponse,
    responses={400: {"description": "Invalid request"}}
)
async def discover_communities(request_data: DiscoverCommunitiesRequest, request: Request):
    """
    Discover communities with filters.

    - Only shows active, public communities
    - Admins can see all communities
    """
    try:
        user_id = get_user_id_from_request(request)
        is_admin = get_admin_status_from_request(request)

        communities, has_more = await community_service.discover_communities(
            user_id=user_id,
            is_admin=is_admin,
            category=request_data.category,
            tags=request_data.tags,
            country=request_data.country,
            city=request_data.city,
            is_featured=request_data.is_featured,
            is_verified=request_data.is_verified,
            cursor=request_data.cursor,
            limit=request_data.limit
        )
        return communities_to_paginated_response(communities, request_data.limit, has_more)

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
    "/update",
    response_model=CommunityResponse,
    responses={
        403: {"description": "Not authorized"},
        404: {"description": "Community not found"},
        409: {"description": "Version conflict or slug exists"}
    }
)
async def update_community(request_data: UpdateCommunityRequest, request: Request):
    """
    Update community settings.

    - Only owner or admin can update
    - Requires expected_version for optimistic locking
    """
    try:
        user_id = get_user_id_from_request(request)
        is_admin = get_admin_status_from_request(request)

        # Extract updates from request
        updates = request_data.model_dump(exclude={"community_id", "expected_version"}, exclude_none=True)

        community = await community_service.update_community(
            community_id=request_data.community_id,
            user_id=user_id,
            expected_version=request_data.expected_version,
            is_admin=is_admin,
            **updates
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
        elif "slug already exists" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "SLUG_ALREADY_EXISTS", "message": error_msg}}
            )
        elif "not authorized" in error_msg.lower() or "suspended" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "NOT_AUTHORIZED", "message": error_msg}}
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
    "/delete",
    response_model=CommunityResponse,
    responses={
        403: {"description": "Not authorized"},
        404: {"description": "Community not found"},
        409: {"description": "Version conflict or already deleted"}
    }
)
async def delete_community(request_data: DeleteCommunityRequest, request: Request):
    """
    Soft delete a community.

    - Only owner or admin can delete
    - Requires expected_version for optimistic locking
    """
    try:
        user_id = get_user_id_from_request(request)
        is_admin = get_admin_status_from_request(request)

        community = await community_service.delete_community(
            community_id=request_data.community_id,
            user_id=user_id,
            expected_version=request_data.expected_version,
            is_admin=is_admin
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
        elif "already deleted" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "ALREADY_DELETED", "message": error_msg}}
            )
        elif "not authorized" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "NOT_OWNER", "message": error_msg}}
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
    "/archive",
    response_model=CommunityResponse,
    responses={
        403: {"description": "Not authorized"},
        404: {"description": "Community not found"},
        409: {"description": "Version conflict or invalid status"}
    }
)
async def archive_community(request_data: ArchiveCommunityRequest, request: Request):
    """Archive a community (owner or admin)."""
    try:
        user_id = get_user_id_from_request(request)
        is_admin = get_admin_status_from_request(request)

        community = await community_service.archive_community(
            community_id=request_data.community_id,
            user_id=user_id,
            expected_version=request_data.expected_version,
            is_admin=is_admin
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
        elif "cannot archive" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "INVALID_STATUS_TRANSITION", "message": error_msg}}
            )
        elif "not authorized" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "NOT_OWNER", "message": error_msg}}
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
    "/unarchive",
    response_model=CommunityResponse,
    responses={
        403: {"description": "Not authorized"},
        404: {"description": "Community not found"},
        409: {"description": "Version conflict or invalid status"}
    }
)
async def unarchive_community(request_data: ArchiveCommunityRequest, request: Request):
    """Unarchive a community (owner or admin)."""
    try:
        user_id = get_user_id_from_request(request)
        is_admin = get_admin_status_from_request(request)

        community = await community_service.unarchive_community(
            community_id=request_data.community_id,
            user_id=user_id,
            expected_version=request_data.expected_version,
            is_admin=is_admin
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
        elif "cannot unarchive" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "INVALID_STATUS_TRANSITION", "message": error_msg}}
            )
        elif "not authorized" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "NOT_OWNER", "message": error_msg}}
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
# Membership
# ============================================================================

@router.post(
    "/join",
    response_model=JoinResultResponse,
    responses={
        404: {"description": "Community not found"},
        409: {"description": "Community full or suspended"}
    }
)
async def join_community(request_data: JoinCommunityRequest, request: Request):
    """
    Join a community.

    - Any user or leader can join instantly
    - Checks if community is full or suspended
    """
    try:
        user_id = get_user_id_from_request(request)

        result = await community_service.join_community(
            community_id=request_data.community_id,
            user_id=user_id
        )

        return JoinResultResponse(
            success=result["success"],
            community_id=result.get("community_id", request_data.community_id),
            member_count=result.get("member_count"),
            already_member=result.get("already_member"),
            message=result.get("message")
        )

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "COMMUNITY_NOT_FOUND", "message": error_msg}}
            )
        elif "suspended" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "COMMUNITY_SUSPENDED", "message": error_msg}}
            )
        elif "maximum capacity" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "COMMUNITY_FULL", "message": error_msg}}
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
    "/leave",
    response_model=JoinResultResponse,
    responses={
        404: {"description": "Community not found"},
        409: {"description": "Owner cannot leave"}
    }
)
async def leave_community(request_data: LeaveCommunityRequest, request: Request):
    """Leave a community."""
    try:
        user_id = get_user_id_from_request(request)

        result = await community_service.leave_community(
            community_id=request_data.community_id,
            user_id=user_id
        )

        return JoinResultResponse(
            success=result["success"],
            community_id=request_data.community_id,
            member_count=result.get("member_count")
        )

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "COMMUNITY_NOT_FOUND", "message": error_msg}}
            )
        elif "owner cannot leave" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "OWNER_CANNOT_LEAVE", "message": error_msg}}
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
    "/check-membership",
    response_model=MembershipResponse,
    responses={404: {"description": "Community not found"}}
)
async def check_membership(request_data: CheckMembershipRequest, request: Request):
    """Check if current user is a member of a community."""
    try:
        user_id = get_user_id_from_request(request)

        result = await community_service.check_membership(
            community_id=request_data.community_id,
            user_id=user_id
        )

        return MembershipResponse(
            community_id=result["community_id"],
            is_member=result["is_member"],
            is_owner=result["is_owner"]
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "COMMUNITY_NOT_FOUND", "message": str(e)}}
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )


@router.post(
    "/members",
    response_model=PaginatedMembersResponse,
    responses={404: {"description": "Community not found"}}
)
async def list_members(request_data: ListMembersRequest, request: Request):
    """List community members."""
    try:
        user_id = get_user_id_from_request(request)
        is_admin = get_admin_status_from_request(request)

        members, total_count, has_more = await community_service.list_members(
            community_id=request_data.community_id,
            user_id=user_id,
            is_admin=is_admin,
            cursor=request_data.cursor,
            limit=request_data.limit
        )

        # Build cursor
        next_cursor = None
        if has_more:
            offset = 0
            if request_data.cursor:
                cursor_data = decode_cursor(request_data.cursor)
                offset = int(cursor_data["sort_value"])
            next_cursor = encode_cursor(str(offset + len(members)), "0")

        return PaginatedMembersResponse(
            members=[MemberResponse(user_id=str(m)) for m in members],
            next_cursor=next_cursor,
            has_more=has_more,
            total_count=total_count
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "COMMUNITY_NOT_FOUND", "message": str(e)}}
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "An error occurred"}}
        )


@router.post(
    "/remove-member",
    response_model=CommunityResponse,
    responses={
        403: {"description": "Not authorized"},
        404: {"description": "Community not found"},
        409: {"description": "Version conflict"}
    }
)
async def remove_member(request_data: RemoveMemberRequest, request: Request):
    """Remove a member from community (owner or admin)."""
    try:
        user_id = get_user_id_from_request(request)
        is_admin = get_admin_status_from_request(request)

        community = await community_service.remove_member(
            community_id=request_data.community_id,
            user_id=user_id,
            member_user_id=request_data.user_id,
            expected_version=request_data.expected_version,
            is_admin=is_admin
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
        elif "not authorized" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "NOT_OWNER", "message": error_msg}}
            )
        elif "cannot remove" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "CANNOT_REMOVE_OWNER", "message": error_msg}}
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
# Community Posts
# ============================================================================

@router.post(
    "/posts",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "Not a community member"},
        404: {"description": "Community not found"},
        422: {"description": "Validation error"}
    }
)
async def create_community_post(request_data: CreateCommunityPostRequest, request: Request):
    """
    Create a post in a community.

    - User must be a community member
    - Set is_draft=true to create as draft
    - Set request_global_distribution=true to request global visibility on publish
    """
    try:
        user_id = get_post_user_id(request)

        post = await post_service.create_community_post(
            user_id=user_id,
            community_id=request_data.community_id,
            post_type=request_data.post_type,
            text_content=request_data.text_content,
            media=[m.model_dump() for m in request_data.media] if request_data.media else None,
            link_preview=request_data.link_preview.model_dump() if request_data.link_preview else None,
            poll=request_data.poll.model_dump() if request_data.poll else None,
            tags=request_data.tags,
            mentions=[m.model_dump() for m in request_data.mentions] if request_data.mentions else None,
            is_draft=request_data.is_draft,
            request_global_distribution=request_data.request_global_distribution
        )
        return post_to_response(post)

    except ValueError as e:
        error_msg = str(e)
        if "not a member" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "NOT_COMMUNITY_MEMBER", "message": error_msg}}
            )
        elif "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "COMMUNITY_NOT_FOUND", "message": error_msg}}
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
    "/posts/list",
    response_model=PaginatedPostsResponse,
    responses={
        403: {"description": "Not a community member"},
        404: {"description": "Community not found"}
    }
)
async def query_community_posts(request_data: ListCommunityPostsRequest, request: Request):
    """
    Query posts in a community.

    - Paginated with cursor-based pagination
    - Leaders can set include_hidden=true to see hidden posts
    """
    try:
        user_id = get_post_user_id(request)

        posts, has_more = await post_service.list_community_posts(
            user_id=user_id,
            community_id=request_data.community_id,
            cursor=request_data.cursor,
            limit=request_data.limit,
            include_hidden=request_data.include_hidden
        )
        return posts_to_paginated_response(posts, request_data.limit, has_more)

    except ValueError as e:
        error_msg = str(e)
        if "not a member" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "NOT_COMMUNITY_MEMBER", "message": error_msg}}
            )
        elif "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "COMMUNITY_NOT_FOUND", "message": error_msg}}
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
