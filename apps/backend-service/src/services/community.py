"""
Community Service - Business logic for community operations
"""

from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime

from beanie import PydanticObjectId

from shared.models.community import *
from shared.models.community_moderation_log import (
    CommunityModerationLog, ModerationAction, log_moderation_action
)
from shared.models.user import User
from src.kafka.producer import get_kafka_producer
from shared.kafka.topics import Topic
from src.utils.datetime_utils import utc_now
from src.utils.community_utils import decode_cursor
from src.utils.serialization import oid_to_str


class CommunityService:
    """Service class for community operations"""

    def __init__(self):
        self.default_page_size = 20
        self.max_page_size = 100
        self._kafka = get_kafka_producer()

    # ============================================================
    # Helper Methods
    # ============================================================

    async def _get_user(self, user_id: str) -> User:
        """Get user by ID"""
        try:
            user = await User.get(PydanticObjectId(user_id))
        except Exception:
            raise ValueError("Invalid user ID")

        if not user or user.deleted_at:
            raise ValueError("User not found")

        return user

    async def _get_community(self, community_id: str) -> Community:
        """Get community by ID"""
        try:
            community = await Community.get(PydanticObjectId(community_id))
        except Exception:
            raise ValueError("Invalid community ID")

        if not community or community.deleted_at:
            raise ValueError("Community not found")

        return community

    async def _get_community_for_user(
        self,
        community_id: str,
        user_id: str,
        is_admin: bool = False
    ) -> Community:
        """Get community ensuring user has access (anti-enumeration)"""
        community = await self._get_community(community_id)

        # Deleted communities are not found for anyone except admin
        if community.status == CommunityStatus.DELETED:
            if not is_admin:
                raise ValueError("Community not found")
            return community

        # Suspended communities visible only to owner and admin
        if community.status == CommunityStatus.SUSPENDED:
            if not is_admin and str(community.owner.user_id) != user_id:
                raise ValueError("Community not found")
            return community

        # Private communities visible only to members, owner, admin
        if community.settings.visibility == CommunityVisibility.PRIVATE:
            user_oid = PydanticObjectId(user_id)
            if not is_admin and not community.is_user_owner(user_oid) and not community.is_user_member(user_oid):
                raise ValueError("Community not found")

        return community

    def _validate_version(self, community: Community, expected_version: int) -> None:
        """Validate optimistic locking version"""
        if community.version != expected_version:
            raise ValueError(f"Version conflict - expected {expected_version}, got {community.version}")

    async def _check_slug_unique(self, slug: str, exclude_id: Optional[PydanticObjectId] = None) -> None:
        """Check if slug is unique"""
        query = {"slug": slug.lower()}
        if exclude_id:
            query["_id"] = {"$ne": exclude_id}

        existing = await Community.find_one(query)
        if existing:
            raise ValueError("Slug already exists")

    def _build_owner(self, user: User) -> CommunityOwner:
        """Build CommunityOwner from User"""
        return CommunityOwner(
            user_id=user.id,
            display_name=user.profile.display_name or user.contact_info.primary_email.split("@")[0],
            avatar=user.profile.avatar or "https://example.com/default-avatar.png",
            is_verified=user.contact_info.email_verified,
            business_email=user.contact_info.primary_email
        )

    # ============================================================
    # Community CRUD
    # ============================================================

    async def create_community(
        self,
        user_id: str,
        user_role: str,
        data: Dict[str, Any]
    ) -> Community:
        """Create a new community (leader only)"""
        # Verify user is a leader
        if user_role != "leader":
            raise ValueError("Only leaders can create communities")

        user = await self._get_user(user_id)

        # Check slug uniqueness
        await self._check_slug_unique(data["slug"])

        # Validate category
        try:
            category = CommunityCategory(data["category"])
        except ValueError:
            raise ValueError(f"Invalid category: {data['category']}")

        # Build settings
        settings_data = data.get("settings") or {}
        visibility = CommunityVisibility(settings_data.get("visibility", "public"))
        settings = CommunitySettings(
            visibility=visibility,
            requires_approval=settings_data.get("requires_approval", False),
            allow_member_posts=settings_data.get("allow_member_posts", False),
            moderate_posts=settings_data.get("moderate_posts", True),
            max_members=settings_data.get("max_members"),
            min_age=settings_data.get("min_age"),
            allowed_countries=settings_data.get("allowed_countries") or [],
            blocked_countries=settings_data.get("blocked_countries") or []
        )

        # Build rules
        rules = []
        if data.get("rules"):
            rules = [
                CommunityRules(
                    rule_title=r["rule_title"],
                    rule_description=r["rule_description"],
                    display_order=r.get("display_order", i)
                )
                for i, r in enumerate(data["rules"])
            ]

        # Build links
        links = None
        if data.get("links"):
            links_data = data["links"]
            links = CommunityLinks(
                website=links_data.get("website"),
                instagram=links_data.get("instagram"),
                twitter=links_data.get("twitter"),
                youtube=links_data.get("youtube"),
                discord=links_data.get("discord")
            )

        # Create community
        community = Community(
            name=data["name"],
            slug=data["slug"].lower(),
            description=data["description"],
            tagline=data.get("tagline"),
            category=category,
            tags=data.get("tags") or [],
            purpose=CommunityPurpose(
                mission_statement=data["purpose"]["mission_statement"],
                goals=data["purpose"].get("goals") or [],
                target_audience=data["purpose"].get("target_audience")
            ),
            business_address=BusinessAddress(
                country=data["business_address"]["country"].upper(),
                city=data["business_address"]["city"],
                zip_code=data["business_address"]["zip_code"]
            ),
            branding=CommunityBranding(
                cover_image=data["branding"]["cover_image"],
                logo=data["branding"].get("logo"),
                primary_color=data["branding"].get("primary_color"),
                secondary_color=data["branding"].get("secondary_color")
            ),
            owner=self._build_owner(user),
            member_ids=[user.id],  # Owner is first member
            settings=settings,
            rules=rules,
            links=links,
            stats=CommunityStats(member_count=1)  # Owner counts
        )

        await community.insert()

        # Emit community.created event
        self._kafka.emit(
            topic=Topic.COMMUNITY,
            action="created",
            entity_id=oid_to_str(community.id),
            data=community.model_dump(mode="json"),
        )

        return community

    async def get_community_by_id(
        self,
        community_id: str,
        user_id: str,
        is_admin: bool = False
    ) -> Community:
        """Get community by ID with access control"""
        return await self._get_community_for_user(community_id, user_id, is_admin)

    async def get_community_by_slug(
        self,
        slug: str,
        user_id: str,
        is_admin: bool = False
    ) -> Community:
        """Get community by slug with access control"""
        community = await Community.find_one({"slug": slug.lower(), "deleted_at": None})
        if not community:
            raise ValueError("Community not found")

        # Apply same access control
        return await self._get_community_for_user(str(community.id), user_id, is_admin)

    async def discover_communities(
        self,
        user_id: str,
        is_admin: bool = False,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        country: Optional[str] = None,
        city: Optional[str] = None,
        is_featured: Optional[bool] = None,
        is_verified: Optional[bool] = None,
        cursor: Optional[str] = None,
        limit: int = 20
    ) -> Tuple[List[Community], bool]:
        """Discover communities with filters"""
        # Base query - only active, public, non-deleted
        query: Dict[str, Any] = {
            "status": CommunityStatus.ACTIVE.value,
            "deleted_at": None
        }

        # Admin can see all statuses
        if not is_admin:
            query["settings.visibility"] = CommunityVisibility.PUBLIC.value

        # Apply filters
        if category:
            query["category"] = category

        if tags:
            query["tags"] = {"$in": [t.lower() for t in tags]}

        if country:
            query["business_address.country"] = country.upper()

        if city:
            query["business_address.city"] = city

        if is_featured is True:
            query["is_featured"] = True
            query["featured_until"] = {"$gt": utc_now()}

        if is_verified is True:
            query["is_verified"] = True

        # Cursor pagination
        if cursor:
            cursor_data = decode_cursor(cursor)
            query["$or"] = [
                {"stats.member_count": {"$lt": int(cursor_data["sort_value"])}},
                {
                    "stats.member_count": int(cursor_data["sort_value"]),
                    "_id": {"$lt": PydanticObjectId(cursor_data["id"])}
                }
            ]

        # Fetch
        limit = min(limit, self.max_page_size)
        communities = await Community.find(query).sort(
            [("stats.member_count", -1), ("_id", -1)]
        ).limit(limit + 1).to_list()

        has_more = len(communities) > limit
        if has_more:
            communities = communities[:limit]

        return communities, has_more

    async def update_community(
        self,
        community_id: str,
        user_id: str,
        expected_version: int,
        is_admin: bool = False,
        **updates
    ) -> Community:
        """Update community (owner or admin)"""
        community = await self._get_community(community_id)

        # Check deleted
        if community.status == CommunityStatus.DELETED:
            raise ValueError("Community not found")

        # Check suspended (only admin can update suspended)
        if community.status == CommunityStatus.SUSPENDED and not is_admin:
            raise ValueError("Community is suspended")

        # Check ownership
        if not is_admin and str(community.owner.user_id) != user_id:
            raise ValueError("Not authorized to update this community")

        # Check version
        self._validate_version(community, expected_version)

        # Check slug uniqueness if changing
        if "slug" in updates and updates["slug"]:
            new_slug = updates["slug"].lower()
            if new_slug != community.slug:
                await self._check_slug_unique(new_slug, community.id)
                community.slug = new_slug

        # Apply updates
        if "name" in updates and updates["name"]:
            community.name = updates["name"]

        if "description" in updates and updates["description"]:
            community.description = updates["description"]

        if "tagline" in updates:
            community.tagline = updates["tagline"]

        if "category" in updates and updates["category"]:
            try:
                community.category = CommunityCategory(updates["category"])
            except ValueError:
                raise ValueError(f"Invalid category: {updates['category']}")

        if "tags" in updates:
            community.tags = updates["tags"] or []

        if "purpose" in updates and updates["purpose"]:
            p = updates["purpose"]
            community.purpose = CommunityPurpose(
                mission_statement=p.get("mission_statement", community.purpose.mission_statement),
                goals=p.get("goals", community.purpose.goals),
                target_audience=p.get("target_audience", community.purpose.target_audience)
            )

        if "branding" in updates and updates["branding"]:
            b = updates["branding"]
            community.branding = CommunityBranding(
                cover_image=b.get("cover_image", community.branding.cover_image),
                logo=b.get("logo", community.branding.logo),
                primary_color=b.get("primary_color", community.branding.primary_color),
                secondary_color=b.get("secondary_color", community.branding.secondary_color)
            )

        if "settings" in updates and updates["settings"]:
            s = updates["settings"]
            community.settings = CommunitySettings(
                visibility=CommunityVisibility(s.get("visibility", community.settings.visibility.value)),
                requires_approval=s.get("requires_approval", community.settings.requires_approval),
                allow_member_posts=s.get("allow_member_posts", community.settings.allow_member_posts),
                moderate_posts=s.get("moderate_posts", community.settings.moderate_posts),
                max_members=s.get("max_members", community.settings.max_members),
                min_age=s.get("min_age", community.settings.min_age),
                allowed_countries=s.get("allowed_countries", community.settings.allowed_countries),
                blocked_countries=s.get("blocked_countries", community.settings.blocked_countries)
            )

        if "rules" in updates:
            if updates["rules"]:
                community.rules = [
                    CommunityRules(
                        rule_title=r["rule_title"],
                        rule_description=r["rule_description"],
                        display_order=r.get("display_order", i)
                    )
                    for i, r in enumerate(updates["rules"])
                ]
            else:
                community.rules = []

        if "links" in updates:
            if updates["links"]:
                l = updates["links"]
                community.links = CommunityLinks(
                    website=l.get("website"),
                    instagram=l.get("instagram"),
                    twitter=l.get("twitter"),
                    youtube=l.get("youtube"),
                    discord=l.get("discord")
                )
            else:
                community.links = None

        community.updated_at = utc_now()
        community.version += 1
        await community.save()

        return community

    async def delete_community(
        self,
        community_id: str,
        user_id: str,
        expected_version: int,
        is_admin: bool = False
    ) -> Community:
        """Soft delete community (owner or admin)"""
        community = await self._get_community(community_id)

        # Check already deleted
        if community.status == CommunityStatus.DELETED:
            raise ValueError("Community already deleted")

        # Check ownership
        if not is_admin and str(community.owner.user_id) != user_id:
            raise ValueError("Not authorized to delete this community")

        # Check version
        self._validate_version(community, expected_version)

        # Soft delete
        await community.soft_delete()

        return community

    async def archive_community(
        self,
        community_id: str,
        user_id: str,
        expected_version: int,
        is_admin: bool = False
    ) -> Community:
        """Archive community"""
        community = await self._get_community(community_id)

        # Only active can be archived
        if community.status != CommunityStatus.ACTIVE:
            raise ValueError(f"Cannot archive community with status '{community.status.value}'")

        # Check ownership
        if not is_admin and str(community.owner.user_id) != user_id:
            raise ValueError("Not authorized to archive this community")

        # Check version
        self._validate_version(community, expected_version)

        await community.archive_community()
        return community

    async def unarchive_community(
        self,
        community_id: str,
        user_id: str,
        expected_version: int,
        is_admin: bool = False
    ) -> Community:
        """Unarchive community"""
        community = await self._get_community(community_id)

        # Only archived can be unarchived
        if community.status != CommunityStatus.ARCHIVED:
            raise ValueError(f"Cannot unarchive community with status '{community.status.value}'")

        # Check ownership
        if not is_admin and str(community.owner.user_id) != user_id:
            raise ValueError("Not authorized to unarchive this community")

        # Check version
        self._validate_version(community, expected_version)

        community.status = CommunityStatus.ACTIVE
        community.updated_at = utc_now()
        community.version += 1
        await community.save()

        return community

    # ============================================================
    # Membership
    # ============================================================

    async def join_community(
        self,
        community_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """Join a community (instant join for any user or leader)"""
        community = await self._get_community(community_id)
        user_oid = PydanticObjectId(user_id)

        # Check status
        if community.status == CommunityStatus.SUSPENDED:
            raise ValueError("Community is suspended and cannot accept new members")

        if community.status != CommunityStatus.ACTIVE:
            raise ValueError("Community is not accepting new members")

        # Check if already member (idempotent)
        if community.is_user_member(user_oid):
            return {
                "success": True,
                "community_id": str(community.id),
                "member_count": community.stats.member_count,
                "already_member": True
            }

        # Check capacity
        if not community.can_accept_members():
            raise ValueError("Community has reached maximum capacity")

        # Instant join
        await community.add_member(user_oid)

        # Emit community.member_joined event
        self._kafka.emit(
            topic=Topic.COMMUNITY,
            action="member_joined",
            entity_id=oid_to_str(community.id),
            data={
                "user_id": user_id,
                "community_name": community.name,
                "member_count": community.stats.member_count,
            },
        )

        return {
            "success": True,
            "community_id": str(community.id),
            "member_count": community.stats.member_count,
            "already_member": False
        }

    async def leave_community(
        self,
        community_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """Leave a community"""
        community = await self._get_community(community_id)
        user_oid = PydanticObjectId(user_id)

        # Check if owner
        if community.is_user_owner(user_oid):
            raise ValueError("Owner cannot leave the community. Transfer ownership or delete the community instead.")

        # Check if member (idempotent - not being member is OK)
        if not community.is_user_member(user_oid):
            return {
                "success": True,
                "member_count": community.stats.member_count,
                "was_member": False
            }

        # Remove member
        await community.remove_member(user_oid)

        # Emit community.member_left event
        self._kafka.emit(
            topic=Topic.COMMUNITY,
            action="member_left",
            entity_id=oid_to_str(community.id),
            data={
                "user_id": user_id,
                "community_name": community.name,
                "member_count": community.stats.member_count,
            },
        )

        return {
            "success": True,
            "member_count": community.stats.member_count,
            "was_member": True
        }

    async def check_membership(
        self,
        community_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """Check membership status"""
        community = await self._get_community(community_id)
        user_oid = PydanticObjectId(user_id)

        return {
            "community_id": str(community.id),
            "is_member": community.is_user_member(user_oid),
            "is_owner": community.is_user_owner(user_oid)
        }

    async def list_members(
        self,
        community_id: str,
        user_id: str,
        is_admin: bool = False,
        cursor: Optional[str] = None,
        limit: int = 20
    ) -> Tuple[List[PydanticObjectId], int, bool]:
        """List community members"""
        community = await self._get_community_for_user(community_id, user_id, is_admin)

        # Pagination on member_ids array
        offset = 0
        if cursor:
            cursor_data = decode_cursor(cursor)
            offset = int(cursor_data["sort_value"])

        limit = min(limit, self.max_page_size)
        members = community.member_ids[offset:offset + limit + 1]

        has_more = len(members) > limit
        if has_more:
            members = members[:limit]

        return members, community.stats.member_count, has_more

    async def remove_member(
        self,
        community_id: str,
        user_id: str,  # Actor
        member_user_id: str,  # Member to remove
        expected_version: int,
        is_admin: bool = False
    ) -> Community:
        """Remove member from community (owner or admin)"""
        community = await self._get_community(community_id)

        # Check ownership
        if not is_admin and str(community.owner.user_id) != user_id:
            raise ValueError("Not authorized to remove members")

        # Check version
        self._validate_version(community, expected_version)

        member_oid = PydanticObjectId(member_user_id)

        # Cannot remove owner
        if community.is_user_owner(member_oid):
            raise ValueError("Cannot remove the community owner")

        # Check if member
        if not community.is_user_member(member_oid):
            raise ValueError("User is not a member of this community")

        await community.remove_member(member_oid)
        return community

    # ============================================================
    # Admin Operations
    # ============================================================

    async def suspend_community(
        self,
        community_id: str,
        admin_id: str,
        reason: str,
        expected_version: int
    ) -> Community:
        """Suspend a community (admin only)"""
        community = await self._get_community(community_id)

        # Only active can be suspended
        if community.status != CommunityStatus.ACTIVE:
            raise ValueError(f"Cannot suspend community with status '{community.status.value}'")

        # Check version
        self._validate_version(community, expected_version)

        previous_status = community.status.value

        await community.suspend_community()

        # Emit community.suspended event
        self._kafka.emit(
            topic=Topic.COMMUNITY,
            action="suspended",
            entity_id=oid_to_str(community.id),
            data={
                "community_name": community.name,
                "admin_id": admin_id,
                "reason": reason,
            },
        )

        # Log action
        await log_moderation_action(
            community_id=community.id,
            action=ModerationAction.SUSPEND,
            actor_id=PydanticObjectId(admin_id),
            reason=reason,
            previous_status=previous_status,
            new_status=community.status.value
        )

        return community

    async def unsuspend_community(
        self,
        community_id: str,
        admin_id: str,
        reason: str,
        expected_version: int
    ) -> Community:
        """Unsuspend a community (admin only)"""
        community = await self._get_community(community_id)

        # Only suspended can be unsuspended
        if community.status != CommunityStatus.SUSPENDED:
            raise ValueError(f"Cannot unsuspend community with status '{community.status.value}'")

        # Check version
        self._validate_version(community, expected_version)

        previous_status = community.status.value

        community.status = CommunityStatus.ACTIVE
        community.updated_at = utc_now()
        community.version += 1
        await community.save()

        # Log action
        await log_moderation_action(
            community_id=community.id,
            action=ModerationAction.UNSUSPEND,
            actor_id=PydanticObjectId(admin_id),
            reason=reason,
            previous_status=previous_status,
            new_status=community.status.value
        )

        return community

    async def verify_community(
        self,
        community_id: str,
        admin_id: str
    ) -> Community:
        """Verify a community (admin only)"""
        community = await self._get_community(community_id)

        if community.is_verified:
            raise ValueError("Community is already verified")

        await community.verify_community()

        # Emit community.verified event
        self._kafka.emit(
            topic=Topic.COMMUNITY,
            action="verified",
            entity_id=oid_to_str(community.id),
            data={
                "community_name": community.name,
                "admin_id": admin_id,
            },
        )

        # Log action
        await log_moderation_action(
            community_id=community.id,
            action=ModerationAction.VERIFY,
            actor_id=PydanticObjectId(admin_id),
            reason="Community verified by admin"
        )

        return community

    async def unverify_community(
        self,
        community_id: str,
        admin_id: str
    ) -> Community:
        """Remove verification (admin only)"""
        community = await self._get_community(community_id)

        if not community.is_verified:
            raise ValueError("Community is not verified")

        community.is_verified = False
        community.verified_at = None
        community.updated_at = utc_now()
        community.version += 1
        await community.save()

        # Log action
        await log_moderation_action(
            community_id=community.id,
            action=ModerationAction.UNVERIFY,
            actor_id=PydanticObjectId(admin_id),
            reason="Verification removed by admin"
        )

        return community

    async def feature_community(
        self,
        community_id: str,
        admin_id: str,
        duration_days: int = 7
    ) -> Community:
        """Feature a community (admin only)"""
        community = await self._get_community(community_id)

        if community.status != CommunityStatus.ACTIVE:
            raise ValueError("Only active communities can be featured")

        await community.feature_community(duration_days)

        # Log action
        await log_moderation_action(
            community_id=community.id,
            action=ModerationAction.FEATURE,
            actor_id=PydanticObjectId(admin_id),
            reason=f"Featured for {duration_days} days",
            metadata={"duration_days": duration_days, "featured_until": community.featured_until.isoformat()}
        )

        return community

    async def unfeature_community(
        self,
        community_id: str,
        admin_id: str
    ) -> Community:
        """Unfeature a community (admin only)"""
        community = await self._get_community(community_id)

        if not community.is_featured:
            raise ValueError("Community is not featured")

        await community.unfeature_community()

        # Log action
        await log_moderation_action(
            community_id=community.id,
            action=ModerationAction.UNFEATURE,
            actor_id=PydanticObjectId(admin_id),
            reason="Removed from featured"
        )

        return community

    async def list_suspended_communities(
        self,
        cursor: Optional[str] = None,
        limit: int = 20
    ) -> Tuple[List[Community], bool]:
        """List suspended communities (admin only)"""
        query: Dict[str, Any] = {"status": CommunityStatus.SUSPENDED.value}

        if cursor:
            cursor_data = decode_cursor(cursor)
            query["$or"] = [
                {"updated_at": {"$lt": datetime.fromisoformat(cursor_data["sort_value"])}},
                {
                    "updated_at": datetime.fromisoformat(cursor_data["sort_value"]),
                    "_id": {"$lt": PydanticObjectId(cursor_data["id"])}
                }
            ]

        limit = min(limit, self.max_page_size)
        communities = await Community.find(query).sort(
            [("updated_at", -1), ("_id", -1)]
        ).limit(limit + 1).to_list()

        has_more = len(communities) > limit
        if has_more:
            communities = communities[:limit]

        return communities, has_more

    async def get_moderation_log(
        self,
        community_id: str,
        cursor: Optional[str] = None,
        limit: int = 20
    ) -> Tuple[List[CommunityModerationLog], bool]:
        """Get moderation history for a community (admin only)"""
        query: Dict[str, Any] = {"community_id": PydanticObjectId(community_id)}

        if cursor:
            cursor_data = decode_cursor(cursor)
            query["$or"] = [
                {"created_at": {"$lt": datetime.fromisoformat(cursor_data["sort_value"])}},
                {
                    "created_at": datetime.fromisoformat(cursor_data["sort_value"]),
                    "_id": {"$lt": PydanticObjectId(cursor_data["id"])}
                }
            ]

        limit = min(limit, self.max_page_size)
        logs = await CommunityModerationLog.find(query).sort(
            [("created_at", -1), ("_id", -1)]
        ).limit(limit + 1).to_list()

        has_more = len(logs) > limit
        if has_more:
            logs = logs[:limit]

        return logs, has_more
