"""
Community utility functions for converting models to response schemas
"""

from fastapi import Request
from typing import List
import base64
import json
from datetime import date

from src.schemas.community import (
    CommunityResponse, CommunityListItemResponse, OwnerResponse, StatsResponse,
    SettingsResponse, PurposeResponse, BrandingResponse, BusinessAddressResponse,
    RuleResponse, LinksResponse, PaginatedCommunitiesResponse,
    ModerationLogResponse, PaginatedModerationLogsResponse
)
from shared.models.community import Community
from shared.models.community_moderation_log import CommunityModerationLog


def get_user_id_from_request(request: Request) -> str:
    """Extract user ID from JWT token (placeholder)"""
    return request.headers.get("X-User-ID", "test_user_id")


def get_admin_status_from_request(request: Request) -> bool:
    """Check if user is admin (placeholder)"""
    return request.headers.get("X-Is-Admin", "false").lower() == "true"


def get_user_role_from_request(request: Request) -> str:
    """Get user role from request (placeholder)"""
    return request.headers.get("X-User-Role", "user")


def get_user_country_from_request(request: Request) -> str:
    """Get user country from request (placeholder)"""
    return request.headers.get("X-User-Country", "US")


def get_user_dob_from_request(request: Request) -> date:
    """Get user date of birth from request (placeholder)"""
    dob_str = request.headers.get("X-User-DOB")
    if dob_str:
        return date.fromisoformat(dob_str)
    return None


def calculate_age(dob: date) -> int:
    """Calculate age from date of birth"""
    from datetime import date as d
    today = d.today()
    age = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        age -= 1
    return age


def encode_cursor(sort_value: str, item_id: str) -> str:
    """Encode pagination cursor"""
    cursor_data = {"sort_value": sort_value, "id": item_id}
    return base64.urlsafe_b64encode(json.dumps(cursor_data).encode()).decode()


def decode_cursor(cursor: str) -> dict:
    """Decode pagination cursor"""
    try:
        return json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
    except Exception:
        raise ValueError("Invalid cursor format")


def community_to_response(community: Community) -> CommunityResponse:
    """Convert Community model to full response schema"""
    rules = None
    if community.rules:
        rules = [
            RuleResponse(title=r.rule_title, description=r.rule_description)
            for r in sorted(community.rules, key=lambda x: x.display_order)
        ]

    links = None
    if community.links:
        links = LinksResponse(
            website=str(community.links.website) if community.links.website else None,
            instagram=community.links.instagram,
            twitter=community.links.twitter,
            youtube=community.links.youtube,
            discord=community.links.discord
        )

    return CommunityResponse(
        id=str(community.id),
        name=community.name,
        slug=community.slug,
        description=community.description,
        tagline=community.tagline,
        category=community.category.value,
        tags=community.tags,
        purpose=PurposeResponse(
            mission=community.purpose.mission_statement,
            goals=community.purpose.goals,
            target_audience=community.purpose.target_audience
        ),
        business_address=BusinessAddressResponse(
            country=community.business_address.country,
            city=community.business_address.city,
            zip_code=community.business_address.zip_code
        ),
        branding=BrandingResponse(
            cover_image=community.branding.cover_image,
            logo=community.branding.logo,
            primary_color=community.branding.primary_color,
            secondary_color=community.branding.secondary_color
        ),
        owner=OwnerResponse(
            id=str(community.owner.user_id),
            display_name=community.owner.display_name,
            avatar=community.owner.avatar,
            is_verified=community.owner.is_verified
        ),
        stats=StatsResponse(
            member_count=community.stats.member_count,
            post_count=community.stats.post_count,
            promotion_count=community.stats.promotion_count,
            total_likes=community.stats.total_likes
        ),
        settings=SettingsResponse(
            visibility=community.settings.visibility.value,
            is_full=community.is_full(),
            requires_approval=community.settings.requires_approval
        ),
        rules=rules,
        links=links,
        status=community.status.value,
        is_verified=community.is_verified,
        is_featured=community.is_featured,
        version=community.version,
        created_at=community.created_at.isoformat(),
        updated_at=community.updated_at.isoformat()
    )


def community_to_list_item(community: Community) -> CommunityListItemResponse:
    """Convert Community model to list item response"""
    return CommunityListItemResponse(
        id=str(community.id),
        name=community.name,
        slug=community.slug,
        tagline=community.tagline,
        category=community.category.value,
        owner=OwnerResponse(
            id=str(community.owner.user_id),
            display_name=community.owner.display_name,
            avatar=community.owner.avatar,
            is_verified=community.owner.is_verified
        ),
        stats=StatsResponse(
            member_count=community.stats.member_count,
            post_count=community.stats.post_count,
            promotion_count=community.stats.promotion_count,
            total_likes=community.stats.total_likes
        ),
        settings=SettingsResponse(
            visibility=community.settings.visibility.value,
            is_full=community.is_full(),
            requires_approval=community.settings.requires_approval
        ),
        branding=BrandingResponse(
            cover_image=community.branding.cover_image,
            logo=community.branding.logo,
            primary_color=community.branding.primary_color,
            secondary_color=community.branding.secondary_color
        ),
        is_verified=community.is_verified,
        is_featured=community.is_featured,
        created_at=community.created_at.isoformat()
    )


def communities_to_paginated_response(
    communities: List[Community],
    limit: int,
    has_more: bool
) -> PaginatedCommunitiesResponse:
    """Convert list of communities to paginated response"""
    next_cursor = None
    if has_more and communities:
        last = communities[-1]
        next_cursor = encode_cursor(str(last.stats.member_count), str(last.id))

    return PaginatedCommunitiesResponse(
        communities=[community_to_list_item(c) for c in communities],
        next_cursor=next_cursor,
        has_more=has_more
    )


def moderation_log_to_response(log: CommunityModerationLog) -> ModerationLogResponse:
    """Convert CommunityModerationLog to response"""
    return ModerationLogResponse(
        id=str(log.id),
        community_id=str(log.community_id),
        action=log.action.value,
        reason=log.reason,
        actor_id=str(log.actor_id),
        previous_status=log.previous_status,
        new_status=log.new_status,
        created_at=log.created_at.isoformat()
    )


def moderation_logs_to_paginated_response(
    logs: List[CommunityModerationLog],
    limit: int,
    has_more: bool
) -> PaginatedModerationLogsResponse:
    """Convert list of moderation logs to paginated response"""
    next_cursor = None
    if has_more and logs:
        last = logs[-1]
        next_cursor = encode_cursor(last.created_at.isoformat(), str(last.id))

    return PaginatedModerationLogsResponse(
        logs=[moderation_log_to_response(l) for l in logs],
        next_cursor=next_cursor,
        has_more=has_more
    )
