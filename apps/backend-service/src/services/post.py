"""
Post Service - Business logic for post operations
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from beanie import PydanticObjectId

from shared.models.post import (
    Post, PostStatus, PostType, AuthorType, GlobalDistributionStatus,
    PostAuthor, MediaAttachment, LinkPreview, PollOption, PollData,
    GlobalDistribution, PostStats, PostMentions
)
from shared.models.post_change_request import PostChangeRequest, ChangeRequestStatus
from shared.models.user import User
from shared.models.community import Community
from src.kafka.producer import get_kafka_producer
from shared.kafka.topics import Topic
from src.utils.datetime_utils import utc_now
from src.utils.post_utils import decode_cursor
from src.utils.serialization import oid_to_str


class PostService:
    """Service class for post operations"""

    def __init__(self):
        self.default_page_size = 20
        self.max_page_size = 100
        self.max_pinned_posts_per_community = 3
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

    async def _get_post(self, post_id: str) -> Post:
        """Get post by ID"""
        try:
            post = await Post.get(PydanticObjectId(post_id))
        except Exception:
            raise ValueError("Invalid post ID")

        if not post or post.deleted_at:
            raise ValueError("Post not found")

        return post

    async def _get_post_for_user(self, post_id: str, user_id: str) -> Post:
        """Get post ensuring user has access"""
        post = await self._get_post(post_id)

        # User can access if:
        # 1. They are the author
        # 2. Post is published and they are in the community
        # 3. Post is globally distributed
        if str(post.author.user_id) == user_id:
            return post

        if post.status == PostStatus.PUBLISHED:
            if post.is_globally_distributed():
                return post
            # Check community membership
            if post.community_id:
                user = await self._get_user(user_id)
                # TODO: Check community membership properly
                return post

        raise ValueError("Post not found")  # Anti-enumeration

    async def _check_community_membership(self, user_id: str, community_id: str) -> bool:
        """Check if user is a member of the community"""
        # TODO: Implement proper membership check using community_memberships collection
        # For now, return True as placeholder
        return True

    async def _check_community_leader(self, user_id: str, community_id: str) -> bool:
        """Check if user is a leader of the community"""
        try:
            community = await self._get_community(community_id)
            return str(community.leader_id) == user_id
        except Exception:
            return False

    def _validate_version(self, post: Post, expected_version: int) -> None:
        """Validate optimistic locking version"""
        if post.version != expected_version:
            raise ValueError("Version conflict - post has been modified")

    def _build_author(self, user: User, is_leader: bool = False) -> PostAuthor:
        """Build PostAuthor from User"""
        return PostAuthor(
            user_id=user.id,
            display_name=user.display_name or user.email.split("@")[0],
            avatar=user.avatar_url or "https://example.com/default-avatar.png",
            author_type=AuthorType.LEADER if is_leader else AuthorType.USER
        )

    def _build_media_list(self, media_data: Optional[List[Dict]]) -> List[MediaAttachment]:
        """Build MediaAttachment list from request data"""
        if not media_data:
            return []
        return [
            MediaAttachment(
                media_type=m.get("media_type"),
                media_url=m.get("media_url"),
                thumbnail_url=m.get("thumbnail_url"),
                width=m.get("width"),
                height=m.get("height"),
                duration_seconds=m.get("duration_seconds"),
                size_bytes=m.get("size_bytes")
            )
            for m in media_data
        ]

    def _build_link_preview(self, preview_data: Optional[Dict]) -> Optional[LinkPreview]:
        """Build LinkPreview from request data"""
        if not preview_data:
            return None
        return LinkPreview(
            url=preview_data.get("url"),
            title=preview_data.get("title"),
            description=preview_data.get("description"),
            image=preview_data.get("image"),
            site_name=preview_data.get("site_name")
        )

    def _build_poll(self, poll_data: Optional[Dict]) -> Optional[PollData]:
        """Build PollData from request data"""
        if not poll_data:
            return None
        return PollData(
            question=poll_data.get("question"),
            options=[
                PollOption(
                    option_id=opt.get("option_id"),
                    option_text=opt.get("option_text"),
                    vote_count=0
                )
                for opt in poll_data.get("options", [])
            ],
            allows_multiple_votes=poll_data.get("allows_multiple_votes", False),
            ends_at=poll_data.get("ends_at"),
            total_votes=0
        )

    def _build_mentions(self, mentions_data: Optional[List[Dict]]) -> List[PostMentions]:
        """Build PostMentions list from request data"""
        if not mentions_data:
            return []
        return [
            PostMentions(
                user_id=PydanticObjectId(m.get("user_id")),
                display_name=m.get("display_name")
            )
            for m in mentions_data
        ]

    # ============================================================
    # Community Post Operations
    # ============================================================

    async def create_community_post(
        self,
        user_id: str,
        community_id: str,
        post_type: str,
        text_content: str,
        media: Optional[List[Dict]] = None,
        link_preview: Optional[Dict] = None,
        poll: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
        mentions: Optional[List[Dict]] = None,
        is_draft: bool = False,
        request_global_distribution: bool = False
    ) -> Post:
        """Create a post in a community"""
        # Validate user
        user = await self._get_user(user_id)

        # Validate community
        community = await self._get_community(community_id)

        # Check membership
        if not await self._check_community_membership(user_id, community_id):
            raise ValueError("User is not a member of this community")

        # Check if user is leader
        is_leader = await self._check_community_leader(user_id, community_id)

        # Validate post type
        try:
            post_type_enum = PostType(post_type)
        except ValueError:
            raise ValueError(f"Invalid post type: {post_type}")

        # Validate poll for poll posts
        if post_type_enum == PostType.POLL and not poll:
            raise ValueError("Poll posts must have poll data")
        if post_type_enum != PostType.POLL and poll:
            raise ValueError("Only poll posts can have poll data")

        # Build post
        post = Post(
            post_type=post_type_enum,
            author=self._build_author(user, is_leader),
            text_content=text_content,
            media=self._build_media_list(media),
            link_preview=self._build_link_preview(link_preview),
            poll=self._build_poll(poll),
            community_id=community.id,
            community_name=community.name,
            tags=tags or [],
            mentions=self._build_mentions(mentions),
            stats=PostStats(),
            global_distribution=GlobalDistribution()
        )

        # Set status based on draft flag
        if is_draft:
            post.status = PostStatus.DRAFT
        else:
            post.status = PostStatus.PUBLISHED
            post.published_at = utc_now()

            # Handle global distribution request
            if request_global_distribution:
                post.global_distribution.requested = True
                post.global_distribution.status = GlobalDistributionStatus.PENDING
                post.global_distribution.requested_at = utc_now()

        await post.insert()

        # Emit post.created event
        self._kafka.emit(
            topic=Topic.POST,
            action="created",
            entity_id=oid_to_str(post.id),
            data=post.model_dump(mode="json"),
        )

        return post

    async def list_community_posts(
        self,
        user_id: str,
        community_id: str,
        cursor: Optional[str] = None,
        limit: int = 20,
        include_hidden: bool = False
    ) -> Tuple[List[Post], bool]:
        """List posts in a community"""
        # Validate community
        await self._get_community(community_id)

        # Check membership
        if not await self._check_community_membership(user_id, community_id):
            raise ValueError("User is not a member of this community")

        # Check if user is leader (can see hidden posts)
        is_leader = await self._check_community_leader(user_id, community_id)

        # Build query
        query = {
            "community_id": PydanticObjectId(community_id),
            "deleted_at": None
        }

        if include_hidden and is_leader:
            query["status"] = {"$in": [PostStatus.PUBLISHED.value, PostStatus.HIDDEN.value]}
        else:
            query["status"] = PostStatus.PUBLISHED.value

        # Handle cursor pagination
        if cursor:
            cursor_data = decode_cursor(cursor)
            query["$or"] = [
                {"published_at": {"$lt": datetime.fromisoformat(cursor_data["published_at"])}},
                {
                    "published_at": datetime.fromisoformat(cursor_data["published_at"]),
                    "_id": {"$lt": PydanticObjectId(cursor_data["id"])}
                }
            ]

        # Fetch posts
        limit = min(limit, self.max_page_size)
        posts = await Post.find(query).sort([("published_at", -1), ("_id", -1)]).limit(limit + 1).to_list()

        has_more = len(posts) > limit
        if has_more:
            posts = posts[:limit]

        return posts, has_more

    # ============================================================
    # Home Feed
    # ============================================================

    async def get_home_feed(
        self,
        user_id: str,
        cursor: Optional[str] = None,
        limit: int = 20
    ) -> Tuple[List[Post], bool]:
        """Get personalized home feed for user"""
        # Get user's community memberships
        user = await self._get_user(user_id)

        # TODO: Get actual community memberships from membership collection
        community_ids = []  # user.community_memberships

        # Build query for home feed:
        # 1. Posts from user's communities
        # 2. Posts with approved global distribution
        query = {
            "status": PostStatus.PUBLISHED.value,
            "deleted_at": None,
            "$or": [
                {"community_id": {"$in": [PydanticObjectId(c) for c in community_ids]}},
                {"global_distribution.status": GlobalDistributionStatus.APPROVED.value}
            ]
        }

        # Handle cursor pagination
        if cursor:
            cursor_data = decode_cursor(cursor)
            # Combine with $and to preserve the $or
            query = {
                "$and": [
                    query,
                    {
                        "$or": [
                            {"published_at": {"$lt": datetime.fromisoformat(cursor_data["published_at"])}},
                            {
                                "published_at": datetime.fromisoformat(cursor_data["published_at"]),
                                "_id": {"$lt": PydanticObjectId(cursor_data["id"])}
                            }
                        ]
                    }
                ]
            }

        # Fetch posts
        limit = min(limit, self.max_page_size)
        posts = await Post.find(query).sort([("published_at", -1), ("_id", -1)]).limit(limit + 1).to_list()

        has_more = len(posts) > limit
        if has_more:
            posts = posts[:limit]

        return posts, has_more

    # ============================================================
    # Single Post Operations
    # ============================================================

    async def get_post(self, post_id: str, user_id: str) -> Post:
        """Get a single post by ID"""
        return await self._get_post_for_user(post_id, user_id)

    async def update_post(
        self,
        post_id: str,
        user_id: str,
        version: int,
        text_content: Optional[str] = None,
        media: Optional[List[Dict]] = None,
        link_preview: Optional[Dict] = None,
        tags: Optional[List[str]] = None
    ) -> Post:
        """Update a post (only for non-globally-tagged posts)"""
        post = await self._get_post_for_user(post_id, user_id)

        # Check ownership
        if str(post.author.user_id) != user_id:
            # Check if user is community leader
            if post.community_id:
                is_leader = await self._check_community_leader(user_id, str(post.community_id))
                if not is_leader:
                    raise ValueError("Post not found")  # Anti-enumeration
            else:
                raise ValueError("Post not found")

        # Check version
        self._validate_version(post, version)

        # Check if globally tagged
        if post.is_globally_tagged():
            raise ValueError("Cannot directly edit globally-tagged posts. Submit a change request instead.")

        # Apply updates
        if text_content is not None:
            post.text_content = text_content
        if media is not None:
            post.media = self._build_media_list(media)
        if link_preview is not None:
            post.link_preview = self._build_link_preview(link_preview)
        if tags is not None:
            post.tags = tags

        post.updated_at = utc_now()
        post.version += 1
        await post.save()

        return post

    async def delete_post(
        self,
        post_id: str,
        user_id: str,
        version: int,
        is_admin: bool = False
    ) -> Post:
        """Soft delete a post"""
        post = await self._get_post_for_user(post_id, user_id)

        # Check version
        self._validate_version(post, version)

        # Check permissions
        is_author = str(post.author.user_id) == user_id
        is_leader = False
        if post.community_id:
            is_leader = await self._check_community_leader(user_id, str(post.community_id))

        # Globally approved posts can only be deleted by admin
        if post.is_globally_distributed() and not is_admin:
            raise ValueError("Only admins can delete globally-distributed posts")

        # Draft posts can be deleted by author
        if post.status == PostStatus.DRAFT:
            if not is_author:
                raise ValueError("Post not found")
        else:
            # Published posts: author cannot delete, only leader/admin
            if not (is_leader or is_admin):
                raise ValueError("Post not found")

        # Perform soft delete
        await post.soft_delete()

        # Emit post.deleted event
        self._kafka.emit(
            topic=Topic.POST,
            action="deleted",
            entity_id=oid_to_str(post.id),
            data={
                "author_id": oid_to_str(post.author.user_id),
                "community_id": oid_to_str(post.community_id) if post.community_id else None,
                "deleted_by": user_id,
            },
        )

        # If post was globally distributed, revoke it
        if post.global_distribution.status == GlobalDistributionStatus.APPROVED:
            post.global_distribution.status = GlobalDistributionStatus.REVOKED
            post.global_distribution.revoked_at = utc_now()
            await post.save()

        return post

    async def publish_post(
        self,
        post_id: str,
        user_id: str,
        version: int,
        request_global_distribution: bool = False
    ) -> Post:
        """Publish a draft post"""
        post = await self._get_post_for_user(post_id, user_id)

        # Check ownership
        if str(post.author.user_id) != user_id:
            raise ValueError("Post not found")

        # Check version
        self._validate_version(post, version)

        # Must be a draft
        if post.status != PostStatus.DRAFT:
            raise ValueError("Only draft posts can be published")

        # Publish
        await post.publish()

        # Handle global distribution request
        if request_global_distribution and post.can_request_global_distribution():
            await post.request_global_distribution()

        return post

    # ============================================================
    # Global Distribution
    # ============================================================

    async def request_global_distribution(
        self,
        post_id: str,
        user_id: str,
        version: int
    ) -> Post:
        """Request global distribution for a post"""
        post = await self._get_post_for_user(post_id, user_id)

        # Check ownership (only author can request)
        if str(post.author.user_id) != user_id:
            raise ValueError("Post not found")

        # Check version
        self._validate_version(post, version)

        # Request distribution
        if not post.can_request_global_distribution():
            raise ValueError("Cannot request global distribution for this post")

        await post.request_global_distribution()
        return post

    # ============================================================
    # Change Requests
    # ============================================================

    async def create_change_request(
        self,
        post_id: str,
        user_id: str,
        requested_changes: Dict[str, Any],
        reason: str
    ) -> PostChangeRequest:
        """Create a change request for a globally-tagged post"""
        post = await self._get_post_for_user(post_id, user_id)

        # Check if user can edit (author or leader)
        is_author = str(post.author.user_id) == user_id
        is_leader = False
        if post.community_id:
            is_leader = await self._check_community_leader(user_id, str(post.community_id))

        if not (is_author or is_leader):
            raise ValueError("Post not found")

        # Must be globally tagged
        if not post.is_globally_tagged():
            raise ValueError("Post is not globally tagged. Edit directly instead.")

        # Validate requested changes
        PostChangeRequest.validate_requested_changes(requested_changes)

        # Check no pending request exists
        existing = await PostChangeRequest.find_one({
            "post_id": post.id,
            "status": ChangeRequestStatus.PENDING.value
        })
        if existing:
            raise ValueError("A pending change request already exists for this post")

        # Create change request
        change_request = PostChangeRequest(
            post_id=post.id,
            author_id=PydanticObjectId(user_id),
            requested_changes=requested_changes,
            reason=reason
        )

        await change_request.insert()
        return change_request

    async def list_change_requests(
        self,
        post_id: str,
        user_id: str,
        cursor: Optional[str] = None,
        limit: int = 20,
        status_filter: Optional[str] = None
    ) -> Tuple[List[PostChangeRequest], bool]:
        """List change requests for a post"""
        post = await self._get_post_for_user(post_id, user_id)

        # Build query
        query = {"post_id": post.id}
        if status_filter:
            query["status"] = status_filter

        # Handle cursor
        if cursor:
            cursor_data = decode_cursor(cursor)
            query["$or"] = [
                {"created_at": {"$lt": datetime.fromisoformat(cursor_data["published_at"])}},
                {
                    "created_at": datetime.fromisoformat(cursor_data["published_at"]),
                    "_id": {"$lt": PydanticObjectId(cursor_data["id"])}
                }
            ]

        # Fetch
        limit = min(limit, self.max_page_size)
        requests = await PostChangeRequest.find(query).sort([("created_at", -1), ("_id", -1)]).limit(limit + 1).to_list()

        has_more = len(requests) > limit
        if has_more:
            requests = requests[:limit]

        return requests, has_more

    # ============================================================
    # Moderation (Leader/Admin)
    # ============================================================

    async def hide_post(
        self,
        post_id: str,
        user_id: str,
        version: int,
        reason: Optional[str] = None,
        is_admin: bool = False
    ) -> Post:
        """Hide a post (leader/admin only)"""
        post = await self._get_post(post_id)

        # Check permissions
        is_leader = False
        if post.community_id:
            is_leader = await self._check_community_leader(user_id, str(post.community_id))

        if not (is_leader or is_admin):
            raise ValueError("Post not found")

        # Check version
        self._validate_version(post, version)

        await post.hide_post(PydanticObjectId(user_id), reason)

        # Emit post.hidden event
        self._kafka.emit(
            topic=Topic.POST,
            action="hidden",
            entity_id=oid_to_str(post.id),
            data={
                "author_id": oid_to_str(post.author.user_id),
                "community_id": oid_to_str(post.community_id) if post.community_id else None,
                "hidden_by": user_id,
                "reason": reason,
            },
        )

        return post

    async def unhide_post(
        self,
        post_id: str,
        user_id: str,
        version: int,
        is_admin: bool = False
    ) -> Post:
        """Unhide a hidden post (leader/admin only)"""
        post = await self._get_post(post_id)

        # Check permissions
        is_leader = False
        if post.community_id:
            is_leader = await self._check_community_leader(user_id, str(post.community_id))

        if not (is_leader or is_admin):
            raise ValueError("Post not found")

        # Check version
        self._validate_version(post, version)

        await post.unhide_post()
        return post

    async def pin_post(
        self,
        post_id: str,
        user_id: str,
        version: int,
        is_admin: bool = False
    ) -> Post:
        """Pin a post in community (leader only)"""
        post = await self._get_post(post_id)

        if not post.community_id:
            raise ValueError("Only community posts can be pinned")

        # Check permissions
        is_leader = await self._check_community_leader(user_id, str(post.community_id))

        if not (is_leader or is_admin):
            raise ValueError("Post not found")

        # Check version
        self._validate_version(post, version)

        # Check max pinned posts
        pinned_count = await Post.find({
            "community_id": post.community_id,
            "is_pinned": True,
            "deleted_at": None
        }).count()

        if pinned_count >= self.max_pinned_posts_per_community:
            raise ValueError(f"Maximum {self.max_pinned_posts_per_community} posts can be pinned in a community")

        await post.pin_post(PydanticObjectId(user_id))
        return post

    async def unpin_post(
        self,
        post_id: str,
        user_id: str,
        version: int,
        is_admin: bool = False
    ) -> Post:
        """Unpin a post (leader only)"""
        post = await self._get_post(post_id)

        if not post.community_id:
            raise ValueError("Only community posts can be unpinned")

        # Check permissions
        is_leader = await self._check_community_leader(user_id, str(post.community_id))

        if not (is_leader or is_admin):
            raise ValueError("Post not found")

        # Check version
        self._validate_version(post, version)

        await post.unpin_post()
        return post

    # ============================================================
    # Admin Operations
    # ============================================================

    async def create_global_post(
        self,
        admin_id: str,
        post_type: str,
        text_content: str,
        media: Optional[List[Dict]] = None,
        link_preview: Optional[Dict] = None,
        poll: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
        mentions: Optional[List[Dict]] = None
    ) -> Post:
        """Create a global-only post (admin only)"""
        # Validate admin user
        admin = await self._get_user(admin_id)

        # Validate post type
        try:
            post_type_enum = PostType(post_type)
        except ValueError:
            raise ValueError(f"Invalid post type: {post_type}")

        # Validate poll
        if post_type_enum == PostType.POLL and not poll:
            raise ValueError("Poll posts must have poll data")
        if post_type_enum != PostType.POLL and poll:
            raise ValueError("Only poll posts can have poll data")

        # Build post (no community)
        post = Post(
            post_type=post_type_enum,
            author=self._build_author(admin, is_leader=True),  # Admin posts as leader type
            text_content=text_content,
            media=self._build_media_list(media),
            link_preview=self._build_link_preview(link_preview),
            poll=self._build_poll(poll),
            community_id=None,  # Global post - no community
            community_name=None,
            tags=tags or [],
            mentions=self._build_mentions(mentions),
            stats=PostStats(),
            status=PostStatus.PUBLISHED,
            published_at=utc_now(),
            global_distribution=GlobalDistribution(
                requested=True,
                status=GlobalDistributionStatus.APPROVED,
                requested_at=utc_now(),
                reviewed_at=utc_now(),
                reviewed_by=admin.id
            )
        )

        await post.insert()
        return post

    async def get_pending_distribution_posts(
        self,
        cursor: Optional[str] = None,
        limit: int = 20
    ) -> Tuple[List[Post], bool]:
        """Get posts pending global distribution approval (admin only)"""
        query = {
            "global_distribution.status": GlobalDistributionStatus.PENDING.value,
            "deleted_at": None
        }

        if cursor:
            cursor_data = decode_cursor(cursor)
            query["$or"] = [
                {"global_distribution.requested_at": {"$lt": datetime.fromisoformat(cursor_data["published_at"])}},
                {
                    "global_distribution.requested_at": datetime.fromisoformat(cursor_data["published_at"]),
                    "_id": {"$lt": PydanticObjectId(cursor_data["id"])}
                }
            ]

        limit = min(limit, self.max_page_size)
        posts = await Post.find(query).sort([("global_distribution.requested_at", 1), ("_id", 1)]).limit(limit + 1).to_list()

        has_more = len(posts) > limit
        if has_more:
            posts = posts[:limit]

        return posts, has_more

    async def approve_global_distribution(
        self,
        post_id: str,
        admin_id: str
    ) -> Post:
        """Approve global distribution (admin only)"""
        post = await self._get_post(post_id)
        await post.approve_global_distribution(PydanticObjectId(admin_id))

        # Emit post.global_distribution_approved event
        self._kafka.emit(
            topic=Topic.POST,
            action="global_distribution_approved",
            entity_id=oid_to_str(post.id),
            data={
                "author_id": oid_to_str(post.author.user_id),
                "community_id": oid_to_str(post.community_id) if post.community_id else None,
                "admin_id": admin_id,
            },
        )

        return post

    async def reject_global_distribution(
        self,
        post_id: str,
        admin_id: str,
        reason: str
    ) -> Post:
        """Reject global distribution (admin only)"""
        post = await self._get_post(post_id)
        await post.reject_global_distribution(PydanticObjectId(admin_id), reason)
        return post

    async def revoke_global_distribution(
        self,
        post_id: str,
        admin_id: str,
        reason: str
    ) -> Post:
        """Revoke approved global distribution (admin only)"""
        post = await self._get_post(post_id)
        await post.revoke_global_distribution(PydanticObjectId(admin_id), reason)
        return post

    async def get_pending_change_requests(
        self,
        cursor: Optional[str] = None,
        limit: int = 20
    ) -> Tuple[List[PostChangeRequest], bool]:
        """Get pending change requests (admin only)"""
        query = {"status": ChangeRequestStatus.PENDING.value}

        if cursor:
            cursor_data = decode_cursor(cursor)
            query["$or"] = [
                {"created_at": {"$lt": datetime.fromisoformat(cursor_data["published_at"])}},
                {
                    "created_at": datetime.fromisoformat(cursor_data["published_at"]),
                    "_id": {"$lt": PydanticObjectId(cursor_data["id"])}
                }
            ]

        limit = min(limit, self.max_page_size)
        requests = await PostChangeRequest.find(query).sort([("created_at", 1), ("_id", 1)]).limit(limit + 1).to_list()

        has_more = len(requests) > limit
        if has_more:
            requests = requests[:limit]

        return requests, has_more

    async def approve_change_request(
        self,
        request_id: str,
        admin_id: str,
        notes: Optional[str] = None
    ) -> Tuple[PostChangeRequest, Post]:
        """Approve change request and apply changes (admin only)"""
        try:
            change_request = await PostChangeRequest.get(PydanticObjectId(request_id))
        except Exception:
            raise ValueError("Invalid change request ID")

        if not change_request:
            raise ValueError("Change request not found")

        if not change_request.is_pending():
            raise ValueError("Change request is not pending")

        # Get the post
        post = await self._get_post(str(change_request.post_id))

        # Capture original values before applying changes
        original_values = {}
        for field in change_request.requested_changes.keys():
            if hasattr(post, field):
                value = getattr(post, field)
                # Convert complex objects to dict for storage
                if hasattr(value, "model_dump"):
                    original_values[field] = value.model_dump()
                elif isinstance(value, list):
                    original_values[field] = [
                        item.model_dump() if hasattr(item, "model_dump") else item
                        for item in value
                    ]
                else:
                    original_values[field] = value

        # Apply changes to post
        for field, value in change_request.requested_changes.items():
            if field == "media":
                post.media = self._build_media_list(value)
            elif field == "link_preview":
                post.link_preview = self._build_link_preview(value)
            elif field == "tags":
                post.tags = value
            elif field == "text_content":
                post.text_content = value

        post.updated_at = utc_now()
        post.version += 1
        await post.save()

        # Approve and mark as applied
        await change_request.approve(PydanticObjectId(admin_id), notes)
        await change_request.mark_applied(original_values)

        return change_request, post

    async def reject_change_request(
        self,
        request_id: str,
        admin_id: str,
        notes: str
    ) -> PostChangeRequest:
        """Reject change request (admin only)"""
        try:
            change_request = await PostChangeRequest.get(PydanticObjectId(request_id))
        except Exception:
            raise ValueError("Invalid change request ID")

        if not change_request:
            raise ValueError("Change request not found")

        await change_request.reject(PydanticObjectId(admin_id), notes)
        return change_request
