"""
Post utility functions for converting models to response schemas
"""

from fastapi import Request
from typing import  List
import base64
import json

from src.schemas.post import (
    PostResponse, PostListItemResponse, AuthorResponse, MediaResponse,
    LinkPreviewResponse, PollOptionResponse, PollResponse, StatsResponse,
    GlobalDistributionResponse, CommunityResponse, ChangeRequestResponse,
    PaginatedPostsResponse, PaginatedChangeRequestsResponse
)
from shared.models.post import Post
from shared.models.post_change_request import PostChangeRequest


def get_user_id_from_request(request: Request) -> str:
    """Extract user ID from JWT token (placeholder)"""
    # TODO: Implement proper JWT authentication
    return request.headers.get("X-User-ID", "test_user_id")


def get_admin_status_from_request(request: Request) -> bool:
    """Check if user is admin (placeholder)"""
    # TODO: Implement proper role checking
    return request.headers.get("X-Is-Admin", "false").lower() == "true"


def encode_cursor(published_at: str, post_id: str) -> str:
    """Encode pagination cursor"""
    cursor_data = {"published_at": published_at, "id": post_id}
    return base64.urlsafe_b64encode(json.dumps(cursor_data).encode()).decode()


def decode_cursor(cursor: str) -> dict:
    """Decode pagination cursor"""
    try:
        return json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
    except Exception:
        raise ValueError("Invalid cursor format")


def post_to_response(post: Post) -> PostResponse:
    """Convert Post model to full response schema"""
    return PostResponse(
        id=str(post.id),
        post_type=post.post_type.value,
        author=AuthorResponse(
            user_id=str(post.author.user_id),
            display_name=post.author.display_name,
            avatar=post.author.avatar,
            author_type=post.author.author_type.value,
            is_verified=post.author.is_verified
        ),
        text_content=post.text_content,
        media=[
            MediaResponse(
                media_type=media.media_type,
                media_url=str(media.media_url),
                thumbnail_url=str(media.thumbnail_url) if media.thumbnail_url else None,
                width=media.width,
                height=media.height
            )
            for media in post.media
        ],
        link_preview=LinkPreviewResponse(
            url=str(post.link_preview.url),
            title=post.link_preview.title,
            description=post.link_preview.description,
            image=str(post.link_preview.image) if post.link_preview.image else None
        ) if post.link_preview else None,
        poll=PollResponse(
            question=post.poll.question,
            options=[
                PollOptionResponse(
                    option_id=opt.option_id,
                    option_text=opt.option_text,
                    vote_count=opt.vote_count,
                    percentage=round((opt.vote_count / post.poll.total_votes * 100), 1) if post.poll.total_votes > 0 else 0
                )
                for opt in post.poll.options
            ],
            total_votes=post.poll.total_votes,
            ends_at=post.poll.ends_at.isoformat() if post.poll.ends_at else None,
            allows_multiple_votes=post.poll.allows_multiple_votes
        ) if post.poll else None,
        community=CommunityResponse(
            community_id=str(post.community_id),
            community_name=post.community_name
        ) if post.community_id else None,
        tags=post.tags,
        stats=StatsResponse(
            view_count=post.stats.view_count,
            like_count=post.stats.like_count,
            comment_count=post.stats.comment_count,
            share_count=post.stats.share_count,
            save_count=post.stats.save_count,
            engagement_rate=round(post.stats.engagement_rate, 2)
        ),
        status=post.status.value,
        global_distribution=GlobalDistributionResponse(
            requested=post.global_distribution.requested,
            status=post.global_distribution.status.value,
            requested_at=post.global_distribution.requested_at.isoformat() if post.global_distribution.requested_at else None,
            reviewed_at=post.global_distribution.reviewed_at.isoformat() if post.global_distribution.reviewed_at else None,
            rejection_reason=post.global_distribution.rejection_reason
        ),
        is_pinned=post.is_pinned,
        version=post.version,
        published_at=post.published_at.isoformat() if post.published_at else None,
        created_at=post.created_at.isoformat(),
        updated_at=post.updated_at.isoformat()
    )


def post_to_list_item(post: Post) -> PostListItemResponse:
    """Convert Post model to list item (summary) response"""
    return PostListItemResponse(
        id=str(post.id),
        post_type=post.post_type.value,
        author=AuthorResponse(
            user_id=str(post.author.user_id),
            display_name=post.author.display_name,
            avatar=post.author.avatar,
            author_type=post.author.author_type.value,
            is_verified=post.author.is_verified
        ),
        text_preview=post.get_preview_text(200),
        primary_image=post.get_primary_image(),
        community=CommunityResponse(
            community_id=str(post.community_id),
            community_name=post.community_name
        ) if post.community_id else None,
        stats=StatsResponse(
            view_count=post.stats.view_count,
            like_count=post.stats.like_count,
            comment_count=post.stats.comment_count,
            share_count=post.stats.share_count,
            save_count=post.stats.save_count,
            engagement_rate=round(post.stats.engagement_rate, 2)
        ),
        status=post.status.value,
        global_distribution_status=post.global_distribution.status.value,
        is_pinned=post.is_pinned,
        published_at=post.published_at.isoformat() if post.published_at else None,
        created_at=post.created_at.isoformat()
    )


def posts_to_paginated_response(
    posts: List[Post],
    limit: int,
    has_more: bool
) -> PaginatedPostsResponse:
    """Convert list of posts to paginated response"""
    next_cursor = None
    if has_more and posts:
        last_post = posts[-1]
        next_cursor = encode_cursor(
            last_post.published_at.isoformat() if last_post.published_at else last_post.created_at.isoformat(),
            str(last_post.id)
        )

    return PaginatedPostsResponse(
        posts=[post_to_list_item(post) for post in posts],
        next_cursor=next_cursor,
        has_more=has_more
    )


def change_request_to_response(request: PostChangeRequest) -> ChangeRequestResponse:
    """Convert PostChangeRequest model to response schema"""
    return ChangeRequestResponse(
        id=str(request.id),
        post_id=str(request.post_id),
        author_id=str(request.author_id),
        requested_changes=request.requested_changes,
        reason=request.reason,
        status=request.status.value,
        reviewed_at=request.reviewed_at.isoformat() if request.reviewed_at else None,
        reviewed_by=str(request.reviewed_by) if request.reviewed_by else None,
        review_notes=request.review_notes,
        applied_at=request.applied_at.isoformat() if request.applied_at else None,
        created_at=request.created_at.isoformat()
    )


def change_requests_to_paginated_response(
    requests: List[PostChangeRequest],
    limit: int,
    has_more: bool
) -> PaginatedChangeRequestsResponse:
    """Convert list of change requests to paginated response"""
    next_cursor = None
    if has_more and requests:
        last_request = requests[-1]
        next_cursor = encode_cursor(
            last_request.created_at.isoformat(),
            str(last_request.id)
        )

    return PaginatedChangeRequestsResponse(
        change_requests=[change_request_to_response(req) for req in requests],
        next_cursor=next_cursor,
        has_more=has_more
    )
