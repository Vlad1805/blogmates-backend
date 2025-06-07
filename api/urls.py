from django.urls import path
from .views.views import sanity, SignupAPIView
from .views.blog_views import (
    BlogEntryAPIView, 
    BlogEntryQueryAPIView, 
    VisibleBlogEntriesView, 
    CreateBlogEntryView,
    BlogCommentAPIView,
    GetBlogCommentsView,
    BlogLikeAPIView,
    GetBlogLikesView,
    GetBlogLikeCountView,
    CommentLikeAPIView,
    GetCommentLikesView,
    GetCommentLikeCountView,
    GetBlogCommentCountView,
    GetBlogEntryView,
    SearchView
)
from .views.social_views import (
    SendFriendRequestAPIView,
    PendingFriendRequestsAPIView,
    PendingSentFriendRequestsAPIView,
    AcceptFriendRequestAPIView,
    RemoveFriendRequestAPIView,
    GetFollowersAPIView,
    GetFollowingAPIView,
    UnfollowUserAPIView,
    RemoveFollowerAPIView,
)

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views.views import CookieTokenRefreshView, CookieTokenObtainPairView, LogoutView, CurrentUserView, UserProfileView

urlpatterns = [
    path('api/sanity/', sanity),
    path('api/signup/', SignupAPIView.as_view(), name='signup'),
    path('api/token/', CookieTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', CookieTokenRefreshView.as_view(), name='token_refresh'),
    path('api/logout/', LogoutView.as_view(), name='logout'),
    path('api/blog/my/', BlogEntryAPIView.as_view(), name='blog'),
    path('api/blog/all/', VisibleBlogEntriesView.as_view(), name='visible-blog-entries'),
    path('api/blog/user/', BlogEntryQueryAPIView.as_view(), name='blog-query'),
    path('api/blog/create/', CreateBlogEntryView.as_view(), name='create-blog'),
    path('api/blog/<int:blog_entry_id>/', GetBlogEntryView.as_view(), name='get-blog'),
    path('api/blog/comment/<int:blog_entry_id>/', BlogCommentAPIView.as_view(), name='create-comment'),
    path('api/blog/comment/<int:blog_entry_id>/<int:comment_id>/', BlogCommentAPIView.as_view(), name='delete-comment'),
    path('api/blog/comments/<int:blog_entry_id>/', GetBlogCommentsView.as_view(), name='get-comments'),
    path('api/blog/like/<int:blog_entry_id>/', BlogLikeAPIView.as_view(), name='blog-like'),
    path('api/blog/likes/<int:blog_entry_id>/', GetBlogLikesView.as_view(), name='get-blog-likes'),
    path('api/blog/like-count/<int:blog_entry_id>/', GetBlogLikeCountView.as_view(), name='get-blog-like-count'),
    path('api/blog/comment-count/<int:blog_entry_id>/', GetBlogCommentCountView.as_view(), name='get-blog-comment-count'),
    path('api/comment/like/<int:comment_id>/', CommentLikeAPIView.as_view(), name='comment-like'),
    path('api/comment/likes/<int:comment_id>/', GetCommentLikesView.as_view(), name='get-comment-likes'),
    path('api/comment/like-count/<int:comment_id>/', GetCommentLikeCountView.as_view(), name='get-comment-like-count'),
    path('api/friend-requests/send/', SendFriendRequestAPIView.as_view(), name='send-friend-request'),
    path('api/friend-requests/pending/', PendingFriendRequestsAPIView.as_view(), name='pending-friend-requests'),
    path('api/friend-requests/pending/sent/', PendingSentFriendRequestsAPIView.as_view(), name='pending-sent-friend-requests'),
    path('api/friend-requests/accept/<int:request_id>/', AcceptFriendRequestAPIView.as_view(), name='accept-friend-request'),
    path('api/friend-requests/remove/<int:request_id>/', RemoveFriendRequestAPIView.as_view(), name='remove-friend-request'),
    path('api/followers/', GetFollowersAPIView.as_view(), name='get-followers'),
    path('api/following/', GetFollowingAPIView.as_view(), name='get-following'),
    path('api/unfollow/<int:user_id>/', UnfollowUserAPIView.as_view(), name='unfollow-user'),
    path('api/remove-follower/<int:user_id>/', RemoveFollowerAPIView.as_view(), name='remove-follower'),
    path("api/user/", CurrentUserView.as_view(), name="current-user"),
    path("api/profile/", UserProfileView.as_view(), name="user-profile"),
    path("api/search/", SearchView.as_view(), name="search"),
]