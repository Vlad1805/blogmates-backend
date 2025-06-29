from django.shortcuts import render
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ..serializers import SignupSerializer, SearchUserSerializer
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from ..models import BlogEntry, FriendRequest, Friendship, BlogComment, BlogLike, CommentLike
from ..serializers import BlogEntrySerializer, BlogCommentSerializer, BlogLikeSerializer, CommentLikeSerializer
from django.db import models
from django.contrib.auth.models import User
from django.db.utils import IntegrityError
from ..authentication import CookieJWTAuthentication
import logging

logger = logging.getLogger('api')

class BlogEntryAPIView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = BlogEntrySerializer

    def get_queryset(self):
        return BlogEntry.objects.filter(author=self.request.user)

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

class BlogEntryQueryAPIView(APIView):
    permission_classes = [AllowAny]  # Allow public access to view public posts

    def post(self, request):
        """
        Get all blog entries for a specific user that the requesting user can see.
        If no user is logged in, returns only public posts.
        
        Request Body:
        {
            "username": "username_to_query"
        }

        Query Parameters:
        - page: Page number (default: 1)
        - page_size: Number of items per page (default: 3, max: 100)
        """
        username = request.data.get('username')
        if not username:
            return Response(
                {"error": "Username is required in request body"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Get pagination parameters
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 3)), 100)  # Cap at 100 items per page

            target_user = User.objects.get(username=username)
            
            blog_entries = BlogEntry.objects.filter(author=target_user)

            # Filter based on visibility and authentication
            if request.user.is_authenticated:
                if request.user == target_user:
                    pass
                else:
                    blog_entries = blog_entries.filter(
                        models.Q(visibility='public') |
                        models.Q(visibility='friends', author__friendships__follower=request.user)
                    )
            else:
                blog_entries = blog_entries.filter(visibility='public')

            blog_entries = blog_entries.order_by('-created_at')
            
            # Calculate pagination
            total_count = blog_entries.count()
            start = (page - 1) * page_size
            end = start + page_size
            paginated_entries = blog_entries[start:end]

            serializer = BlogEntrySerializer(paginated_entries, many=True)
            
            return Response({
                'count': total_count,
                'total_pages': (total_count + page_size - 1) // page_size,
                'current_page': page,
                'page_size': page_size,
                'results': serializer.data
            })

        except User.DoesNotExist:
            return Response(
                {"error": f"User with username '{username}' not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Error retrieving blog entries: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class VisibleBlogEntriesView(APIView):
    permission_classes = [AllowAny]  # Allow both authenticated and unauthenticated users
    authentication_classes = [CookieJWTAuthentication]

    def get(self, request):
        # Get pagination parameters
        page = int(request.query_params.get('page', 1))
        page_size = min(int(request.query_params.get('page_size', 10)), 100)

        if request.user.is_authenticated:
            # For authenticated users
            blog_entries = BlogEntry.objects.filter(
                models.Q(author=request.user) |  # Own entries
                models.Q(visibility='public') |  # Public entries
                models.Q(visibility='friends', author__friendships__follower=request.user)  # Friend's entries
            ).distinct().order_by('-created_at')
        else:
            # For unauthenticated users
            blog_entries = BlogEntry.objects.filter(visibility='public').order_by('-created_at')

        # Calculate pagination
        total_count = blog_entries.count()
        start = (page - 1) * page_size
        end = start + page_size
        paginated_entries = blog_entries[start:end]

        serializer = BlogEntrySerializer(paginated_entries, many=True)
        
        return Response({
            'count': total_count,
            'total_pages': (total_count + page_size - 1) // page_size,
            'current_page': page,
            'page_size': page_size,
            'results': serializer.data
        })

class CreateBlogEntryView(APIView):
    permission_classes = [IsAuthenticated]  # Only authenticated users can create blog entries

    def post(self, request):
        """
        Create a new blog entry.
        
        Request Body:
        {
            "title": "Blog Title",
            "content": "Blog Content",
            "visibility": "public" | "friends" | "private"
        }
        """
        try:
            logger.info('Blog entry creation initiated', extra={
                'user_id': request.user.id,
                'title': request.data.get('title'),
                'visibility': request.data.get('visibility')
            })

            serializer = BlogEntrySerializer(data=request.data, context={'request': request})
            if serializer.is_valid():
                blog_entry = serializer.save()
                logger.info('Blog entry created successfully', extra={
                    'user_id': request.user.id,
                    'blog_entry_id': blog_entry.id,
                    'title': blog_entry.title,
                    'visibility': blog_entry.visibility
                })
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            
            logger.warning('Blog entry creation failed - validation error', extra={
                'user_id': request.user.id,
                'errors': serializer.errors
            })
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except IntegrityError as e:
            if 'api_blogentry_title_author_id' in str(e):
                logger.warning('Blog entry creation failed - duplicate title', extra={
                    'user_id': request.user.id,
                    'title': request.data.get('title')
                })
                return Response(
                    {"error": "You already have a blog post with this title. Please choose a different title."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            logger.error('Blog entry creation failed - integrity error', extra={
                'user_id': request.user.id,
                'error': str(e)
            }, exc_info=True)
            return Response(
                {"error": "An error occurred while creating the blog post."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class BlogCommentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, blog_entry_id):
        """
        Create a new comment on a blog entry.
        
        URL Parameters:
        - blog_entry_id: ID of the blog entry to comment on
        
        Request Body:
        {
            "content": "Comment content"
        }
        """
        try:
            logger.info('Comment creation initiated', extra={
                'user_id': request.user.id,
                'blog_entry_id': blog_entry_id
            })

            blog_entry = BlogEntry.objects.get(id=blog_entry_id)
            
            # Check if user has permission to comment
            if blog_entry.visibility == 'journal':
                logger.warning('Comment creation failed - private journal entry', extra={
                    'user_id': request.user.id,
                    'blog_entry_id': blog_entry_id
                })
                return Response(
                    {"error": "Cannot comment on private journal entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if blog_entry.visibility == 'friends' and not Friendship.objects.filter(
                user=blog_entry.author,
                follower=request.user
            ).exists():
                logger.warning('Comment creation failed - not friends with author', extra={
                    'user_id': request.user.id,
                    'blog_entry_id': blog_entry_id,
                    'author_id': blog_entry.author.id
                })
                return Response(
                    {"error": "Cannot comment on friends-only entries unless you are friends with the author"},
                    status=status.HTTP_403_FORBIDDEN
                )

            serializer = BlogCommentSerializer(data=request.data, context={'request': request})
            if serializer.is_valid():
                comment = serializer.save(
                    author=request.user,
                    blog_entry=blog_entry
                )
                logger.info('Comment created successfully', extra={
                    'user_id': request.user.id,
                    'blog_entry_id': blog_entry_id,
                    'comment_id': comment.id
                })
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            
            logger.warning('Comment creation failed - validation error', extra={
                'user_id': request.user.id,
                'blog_entry_id': blog_entry_id,
                'errors': serializer.errors
            })
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except BlogEntry.DoesNotExist:
            logger.warning('Comment creation failed - blog entry not found', extra={
                'user_id': request.user.id,
                'blog_entry_id': blog_entry_id
            })
            return Response(
                {"error": "Blog entry not found"},
                status=status.HTTP_404_NOT_FOUND
            )

    def delete(self, request, blog_entry_id, comment_id):
        """
        Delete a comment.
        
        URL Parameters:
        - blog_entry_id: ID of the blog entry
        - comment_id: ID of the comment to delete
        
        Note: Users can only delete their own comments or comments on their own blog entries
        """
        try:
            logger.info('Comment deletion initiated', extra={
                'user_id': request.user.id,
                'blog_entry_id': blog_entry_id,
                'comment_id': comment_id
            })

            comment = BlogComment.objects.get(id=comment_id, blog_entry_id=blog_entry_id)
            
            # Check if user has permission to delete the comment
            if request.user != comment.author and request.user != comment.blog_entry.author:
                logger.warning('Comment deletion failed - insufficient permissions', extra={
                    'user_id': request.user.id,
                    'blog_entry_id': blog_entry_id,
                    'comment_id': comment_id,
                    'comment_author_id': comment.author.id,
                    'blog_author_id': comment.blog_entry.author.id
                })
                return Response(
                    {"error": "You can only delete your own comments or comments on your own blog entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            comment.delete()
            logger.info('Comment deleted successfully', extra={
                'user_id': request.user.id,
                'blog_entry_id': blog_entry_id,
                'comment_id': comment_id
            })
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except BlogComment.DoesNotExist:
            logger.warning('Comment deletion failed - comment not found', extra={
                'user_id': request.user.id,
                'blog_entry_id': blog_entry_id,
                'comment_id': comment_id
            })
            return Response(
                {"error": "Comment not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class GetBlogCommentsView(APIView):
    permission_classes = [AllowAny]  # Allow both authenticated and unauthenticated users
    authentication_classes = [CookieJWTAuthentication]  # Use our custom authentication

    def get(self, request, blog_entry_id):
        """
        Get all comments for a specific blog entry.
        
        URL Parameters:
        - blog_entry_id: ID of the blog entry
        
        Query Parameters:
        - page: Page number (default: 1)
        - page_size: Number of items per page (default: 10, max: 100)
        """
        try:
            logger.info('Blog comments retrieval initiated', extra={
                'user_id': request.user.id if request.user.is_authenticated else None,
                'blog_entry_id': blog_entry_id,
                'page': request.query_params.get('page', 1),
                'page_size': request.query_params.get('page_size', 10)
            })

            blog_entry = BlogEntry.objects.get(id=blog_entry_id)
            
            # Check if user has permission to view the blog entry
            if blog_entry.visibility == 'journal' and request.user != blog_entry.author:
                logger.warning('Blog comments retrieval failed - private journal entry', extra={
                    'user_id': request.user.id if request.user.is_authenticated else None,
                    'blog_entry_id': blog_entry_id,
                    'author_id': blog_entry.author.id
                })
                return Response(
                    {"error": "Cannot view private journal entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if blog_entry.visibility == 'friends':
                if not request.user.is_authenticated:
                    logger.warning('Blog comments retrieval failed - not authenticated for friends-only entry', extra={
                        'blog_entry_id': blog_entry_id,
                        'author_id': blog_entry.author.id
                    })
                    return Response(
                        {"error": "Must be logged in to view friends-only entries"},
                        status=status.HTTP_403_FORBIDDEN
                    )
                if request.user != blog_entry.author:
                    if not Friendship.objects.filter(
                        user=blog_entry.author,
                        follower=request.user
                    ).exists():
                        logger.warning('Blog comments retrieval failed - not friends with author', extra={
                            'user_id': request.user.id,
                            'blog_entry_id': blog_entry_id,
                            'author_id': blog_entry.author.id
                        })
                        return Response(
                            {"error": "Cannot view friends-only entries unless you are friends with the author"},
                            status=status.HTTP_403_FORBIDDEN
                        )

            # Get pagination parameters
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 10)), 100)  # Cap at 100 items per page

            # Get comments ordered by newest first
            comments = BlogComment.objects.filter(blog_entry=blog_entry).order_by('-created_at')
            
            # Calculate pagination
            total_count = comments.count()
            start = (page - 1) * page_size
            end = start + page_size
            paginated_comments = comments[start:end]

            serializer = BlogCommentSerializer(paginated_comments, many=True)
            
            logger.info('Blog comments retrieved successfully', extra={
                'user_id': request.user.id if request.user.is_authenticated else None,
                'blog_entry_id': blog_entry_id,
                'total_comments': total_count,
                'page': page,
                'page_size': page_size
            })
            
            return Response({
                'count': total_count,
                'total_pages': (total_count + page_size - 1) // page_size,
                'current_page': page,
                'page_size': page_size,
                'results': serializer.data
            })
            
        except BlogEntry.DoesNotExist:
            logger.warning('Blog comments retrieval failed - blog entry not found', extra={
                'user_id': request.user.id if request.user.is_authenticated else None,
                'blog_entry_id': blog_entry_id
            })
            return Response(
                {"error": "Blog entry not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class BlogLikeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, blog_entry_id):
        """
        Like a blog entry.
        
        URL Parameters:
        - blog_entry_id: ID of the blog entry to like
        """
        try:
            logger.info('Blog like creation initiated', extra={
                'user_id': request.user.id,
                'blog_entry_id': blog_entry_id
            })

            blog_entry = BlogEntry.objects.get(id=blog_entry_id)
            
            # Check if user has permission to like
            if blog_entry.visibility == 'journal' and request.user != blog_entry.author:
                logger.warning('Blog like creation failed - private journal entry', extra={
                    'user_id': request.user.id,
                    'blog_entry_id': blog_entry_id,
                    'author_id': blog_entry.author.id
                })
                return Response(
                    {"error": "Cannot like private journal entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if blog_entry.visibility == 'friends' and not Friendship.objects.filter(
                user=blog_entry.author,
                follower=request.user
            ).exists():
                logger.warning('Blog like creation failed - not friends with author', extra={
                    'user_id': request.user.id,
                    'blog_entry_id': blog_entry_id,
                    'author_id': blog_entry.author.id
                })
                return Response(
                    {"error": "Cannot like friends-only entries unless you are friends with the author"},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Check if user already liked this blog
            if BlogLike.objects.filter(blog_entry=blog_entry, user=request.user).exists():
                logger.warning('Blog like creation failed - already liked', extra={
                    'user_id': request.user.id,
                    'blog_entry_id': blog_entry_id
                })
                return Response(
                    {"error": "You have already liked this blog entry"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create the like
            like = BlogLike.objects.create(
                blog_entry=blog_entry,
                user=request.user
            )
            
            logger.info('Blog like created successfully', extra={
                'user_id': request.user.id,
                'blog_entry_id': blog_entry_id,
                'like_id': like.id
            })
            
            serializer = BlogLikeSerializer(like)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except BlogEntry.DoesNotExist:
            logger.warning('Blog like creation failed - blog entry not found', extra={
                'user_id': request.user.id,
                'blog_entry_id': blog_entry_id
            })
            return Response(
                {"error": "Blog entry not found"},
                status=status.HTTP_404_NOT_FOUND
            )

    def delete(self, request, blog_entry_id):
        """
        Unlike a blog entry.
        
        URL Parameters:
        - blog_entry_id: ID of the blog entry to unlike
        """
        try:
            logger.info('Blog unlike initiated', extra={
                'user_id': request.user.id,
                'blog_entry_id': blog_entry_id
            })

            blog_entry = BlogEntry.objects.get(id=blog_entry_id)
            
            # Find and delete the like
            like = BlogLike.objects.filter(blog_entry=blog_entry, user=request.user).first()
            if not like:
                logger.warning('Blog unlike failed - like not found', extra={
                    'user_id': request.user.id,
                    'blog_entry_id': blog_entry_id
                })
                return Response(
                    {"error": "You have not liked this blog entry"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            like.delete()
            logger.info('Blog unlike successful', extra={
                'user_id': request.user.id,
                'blog_entry_id': blog_entry_id
            })
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except BlogEntry.DoesNotExist:
            logger.warning('Blog unlike failed - blog entry not found', extra={
                'user_id': request.user.id,
                'blog_entry_id': blog_entry_id
            })
            return Response(
                {"error": "Blog entry not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class GetBlogLikesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, blog_entry_id):
        """
        Get all likes for a specific blog entry.
        
        URL Parameters:
        - blog_entry_id: ID of the blog entry to get likes for
        """
        try:
            blog_entry = BlogEntry.objects.get(id=blog_entry_id)
            
            # Check if user has permission to view likes
            if blog_entry.visibility == 'journal' and request.user != blog_entry.author:
                return Response(
                    {"error": "Cannot view likes on private journal entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if blog_entry.visibility == 'friends' and not request.user.is_authenticated:
                return Response(
                    {"error": "Must be logged in to view likes on friends-only entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if blog_entry.visibility == 'friends' and request.user != blog_entry.author:
                if not Friendship.objects.filter(
                    user=blog_entry.author,
                    follower=request.user
                ).exists():
                    return Response(
                        {"error": "Cannot view likes on friends-only entries unless you are friends with the author"},
                        status=status.HTTP_403_FORBIDDEN
                    )

            likes = BlogLike.objects.filter(blog_entry=blog_entry).order_by('-created_at')
            serializer = BlogLikeSerializer(likes, many=True)
            return Response(serializer.data)
            
        except BlogEntry.DoesNotExist:
            return Response(
                {"error": "Blog entry not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class GetBlogLikeCountView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, blog_entry_id):
        """
        Get the number of likes for a specific blog entry.
        
        URL Parameters:
        - blog_entry_id: ID of the blog entry to get like count for
        """
        try:
            logger.info('Blog like count retrieval initiated', extra={
                'user_id': request.user.id if request.user.is_authenticated else None,
                'blog_entry_id': blog_entry_id
            })

            blog_entry = BlogEntry.objects.get(id=blog_entry_id)
            
            # Check if user has permission to view like count
            if blog_entry.visibility == 'journal' and request.user != blog_entry.author:
                logger.warning('Blog like count retrieval failed - private journal entry', extra={
                    'user_id': request.user.id if request.user.is_authenticated else None,
                    'blog_entry_id': blog_entry_id,
                    'author_id': blog_entry.author.id
                })
                return Response(
                    {"error": "Cannot view like count on private journal entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if blog_entry.visibility == 'friends' and not request.user.is_authenticated:
                logger.warning('Blog like count retrieval failed - not authenticated for friends-only entry', extra={
                    'blog_entry_id': blog_entry_id,
                    'author_id': blog_entry.author.id
                })
                return Response(
                    {"error": "Must be logged in to view like count on friends-only entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if blog_entry.visibility == 'friends' and request.user != blog_entry.author:
                if not Friendship.objects.filter(
                    user=blog_entry.author,
                    follower=request.user
                ).exists():
                    logger.warning('Blog like count retrieval failed - not friends with author', extra={
                        'user_id': request.user.id,
                        'blog_entry_id': blog_entry_id,
                        'author_id': blog_entry.author.id
                    })
                    return Response(
                        {"error": "Cannot view like count on friends-only entries unless you are friends with the author"},
                        status=status.HTTP_403_FORBIDDEN
                    )

            like_count = BlogLike.objects.filter(blog_entry=blog_entry).count()
            logger.info('Blog like count retrieved successfully', extra={
                'user_id': request.user.id if request.user.is_authenticated else None,
                'blog_entry_id': blog_entry_id,
                'like_count': like_count
            })
            return Response({"like_count": like_count})
            
        except BlogEntry.DoesNotExist:
            logger.warning('Blog like count retrieval failed - blog entry not found', extra={
                'user_id': request.user.id if request.user.is_authenticated else None,
                'blog_entry_id': blog_entry_id
            })
            return Response(
                {"error": "Blog entry not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class CommentLikeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, comment_id):
        """
        Like a comment.
        
        URL Parameters:
        - comment_id: ID of the comment to like
        """
        try:
            logger.info('Comment like creation initiated', extra={
                'user_id': request.user.id,
                'comment_id': comment_id
            })

            comment = BlogComment.objects.get(id=comment_id)
            
            # Check if user has permission to like
            if comment.blog_entry.visibility == 'journal' and request.user != comment.blog_entry.author:
                logger.warning('Comment like creation failed - private journal entry', extra={
                    'user_id': request.user.id,
                    'comment_id': comment_id,
                    'blog_entry_id': comment.blog_entry.id,
                    'author_id': comment.blog_entry.author.id
                })
                return Response(
                    {"error": "Cannot like comments on private journal entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if comment.blog_entry.visibility == 'friends' and not Friendship.objects.filter(
                user=comment.blog_entry.author,
                follower=request.user
            ).exists():
                logger.warning('Comment like creation failed - not friends with author', extra={
                    'user_id': request.user.id,
                    'comment_id': comment_id,
                    'blog_entry_id': comment.blog_entry.id,
                    'author_id': comment.blog_entry.author.id
                })
                return Response(
                    {"error": "Cannot like comments on friends-only entries unless you are friends with the author"},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Check if user already liked this comment
            if CommentLike.objects.filter(comment=comment, user=request.user).exists():
                logger.warning('Comment like creation failed - already liked', extra={
                    'user_id': request.user.id,
                    'comment_id': comment_id
                })
                return Response(
                    {"error": "You have already liked this comment"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create the like
            like = CommentLike.objects.create(
                comment=comment,
                user=request.user
            )
            
            logger.info('Comment like created successfully', extra={
                'user_id': request.user.id,
                'comment_id': comment_id,
                'like_id': like.id
            })
            
            serializer = CommentLikeSerializer(like)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except BlogComment.DoesNotExist:
            logger.warning('Comment like creation failed - comment not found', extra={
                'user_id': request.user.id,
                'comment_id': comment_id
            })
            return Response(
                {"error": "Comment not found"},
                status=status.HTTP_404_NOT_FOUND
            )

    def delete(self, request, comment_id):
        """
        Unlike a comment.
        
        URL Parameters:
        - comment_id: ID of the comment to unlike
        """
        try:
            logger.info('Comment unlike initiated', extra={
                'user_id': request.user.id,
                'comment_id': comment_id
            })

            comment = BlogComment.objects.get(id=comment_id)
            
            # Find and delete the like
            like = CommentLike.objects.filter(comment=comment, user=request.user).first()
            if not like:
                logger.warning('Comment unlike failed - like not found', extra={
                    'user_id': request.user.id,
                    'comment_id': comment_id
                })
                return Response(
                    {"error": "You have not liked this comment"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            like.delete()
            logger.info('Comment unlike successful', extra={
                'user_id': request.user.id,
                'comment_id': comment_id
            })
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except BlogComment.DoesNotExist:
            logger.warning('Comment unlike failed - comment not found', extra={
                'user_id': request.user.id,
                'comment_id': comment_id
            })
            return Response(
                {"error": "Comment not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class GetCommentLikesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, comment_id):
        """
        Get all likes for a specific comment.
        
        URL Parameters:
        - comment_id: ID of the comment to get likes for
        """
        try:
            comment = BlogComment.objects.get(id=comment_id)
            
            # Check if user has permission to view likes
            if comment.blog_entry.visibility == 'journal' and request.user != comment.blog_entry.author:
                return Response(
                    {"error": "Cannot view likes on comments in private journal entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if comment.blog_entry.visibility == 'friends' and not request.user.is_authenticated:
                return Response(
                    {"error": "Must be logged in to view likes on comments in friends-only entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if comment.blog_entry.visibility == 'friends' and request.user != comment.blog_entry.author:
                if not Friendship.objects.filter(
                    user=comment.blog_entry.author,
                    follower=request.user
                ).exists():
                    return Response(
                        {"error": "Cannot view likes on comments in friends-only entries unless you are friends with the author"},
                        status=status.HTTP_403_FORBIDDEN
                    )

            likes = CommentLike.objects.filter(comment=comment).order_by('-created_at')
            serializer = CommentLikeSerializer(likes, many=True)
            return Response(serializer.data)
            
        except BlogComment.DoesNotExist:
            return Response(
                {"error": "Comment not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class GetCommentLikeCountView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, comment_id):
        """
        Get the number of likes for a specific comment.
        
        URL Parameters:
        - comment_id: ID of the comment to get like count for
        """
        try:
            logger.info('Comment like count retrieval initiated', extra={
                'user_id': request.user.id if request.user.is_authenticated else None,
                'comment_id': comment_id
            })

            comment = BlogComment.objects.get(id=comment_id)
            
            # Check if user has permission to view like count
            if comment.blog_entry.visibility == 'journal' and request.user != comment.blog_entry.author:
                logger.warning('Comment like count retrieval failed - private journal entry', extra={
                    'user_id': request.user.id if request.user.is_authenticated else None,
                    'comment_id': comment_id,
                    'blog_entry_id': comment.blog_entry.id,
                    'author_id': comment.blog_entry.author.id
                })
                return Response(
                    {"error": "Cannot view like count on comments in private journal entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if comment.blog_entry.visibility == 'friends' and not request.user.is_authenticated:
                logger.warning('Comment like count retrieval failed - not authenticated for friends-only entry', extra={
                    'comment_id': comment_id,
                    'blog_entry_id': comment.blog_entry.id,
                    'author_id': comment.blog_entry.author.id
                })
                return Response(
                    {"error": "Must be logged in to view like count on comments in friends-only entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if comment.blog_entry.visibility == 'friends' and request.user != comment.blog_entry.author:
                if not Friendship.objects.filter(
                    user=comment.blog_entry.author,
                    follower=request.user
                ).exists():
                    logger.warning('Comment like count retrieval failed - not friends with author', extra={
                        'user_id': request.user.id,
                        'comment_id': comment_id,
                        'blog_entry_id': comment.blog_entry.id,
                        'author_id': comment.blog_entry.author.id
                    })
                    return Response(
                        {"error": "Cannot view like count on comments in friends-only entries unless you are friends with the author"},
                        status=status.HTTP_403_FORBIDDEN
                    )

            like_count = CommentLike.objects.filter(comment=comment).count()
            logger.info('Comment like count retrieved successfully', extra={
                'user_id': request.user.id if request.user.is_authenticated else None,
                'comment_id': comment_id,
                'like_count': like_count
            })
            return Response({"like_count": like_count})
            
        except BlogComment.DoesNotExist:
            logger.warning('Comment like count retrieval failed - comment not found', extra={
                'user_id': request.user.id if request.user.is_authenticated else None,
                'comment_id': comment_id
            })
            return Response(
                {"error": "Comment not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class GetBlogCommentCountView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, blog_entry_id):
        """
        Get the number of comments for a specific blog entry.
        
        URL Parameters:
        - blog_entry_id: ID of the blog entry to get comment count for
        """
        try:
            logger.info('Blog comment count retrieval initiated', extra={
                'user_id': request.user.id if request.user.is_authenticated else None,
                'blog_entry_id': blog_entry_id
            })

            blog_entry = BlogEntry.objects.get(id=blog_entry_id)
            
            # Check if user has permission to view comment count
            if blog_entry.visibility == 'journal' and request.user != blog_entry.author:
                logger.warning('Blog comment count retrieval failed - private journal entry', extra={
                    'user_id': request.user.id if request.user.is_authenticated else None,
                    'blog_entry_id': blog_entry_id,
                    'author_id': blog_entry.author.id
                })
                return Response(
                    {"error": "Cannot view comment count on private journal entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if blog_entry.visibility == 'friends' and not request.user.is_authenticated:
                logger.warning('Blog comment count retrieval failed - not authenticated for friends-only entry', extra={
                    'blog_entry_id': blog_entry_id,
                    'author_id': blog_entry.author.id
                })
                return Response(
                    {"error": "Must be logged in to view comment count on friends-only entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if blog_entry.visibility == 'friends' and request.user != blog_entry.author:
                if not Friendship.objects.filter(
                    user=blog_entry.author,
                    follower=request.user
                ).exists():
                    logger.warning('Blog comment count retrieval failed - not friends with author', extra={
                        'user_id': request.user.id,
                        'blog_entry_id': blog_entry_id,
                        'author_id': blog_entry.author.id
                    })
                    return Response(
                        {"error": "Cannot view comment count on friends-only entries unless you are friends with the author"},
                        status=status.HTTP_403_FORBIDDEN
                    )

            comment_count = BlogComment.objects.filter(blog_entry=blog_entry).count()
            logger.info('Blog comment count retrieved successfully', extra={
                'user_id': request.user.id if request.user.is_authenticated else None,
                'blog_entry_id': blog_entry_id,
                'comment_count': comment_count
            })
            return Response({"comment_count": comment_count})
            
        except BlogEntry.DoesNotExist:
            logger.warning('Blog comment count retrieval failed - blog entry not found', extra={
                'user_id': request.user.id if request.user.is_authenticated else None,
                'blog_entry_id': blog_entry_id
            })
            return Response(
                {"error": "Blog entry not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class GetBlogEntryView(APIView):
    permission_classes = [AllowAny]  # Allow both authenticated and unauthenticated users
    authentication_classes = [CookieJWTAuthentication]  # Use our custom authentication

    def get(self, request, blog_entry_id):
        """
        Get a specific blog entry by ID.
        
        URL Parameters:
        - blog_entry_id: ID of the blog entry to retrieve
        """
        try:
            logger.info('Blog entry retrieval initiated', extra={
                'user_id': request.user.id if request.user.is_authenticated else None,
                'blog_entry_id': blog_entry_id
            })

            blog_entry = BlogEntry.objects.get(id=blog_entry_id)
            
            # Check if user has permission to view the blog entry
            if blog_entry.visibility == 'journal' and request.user != blog_entry.author:
                logger.warning('Blog entry retrieval failed - private journal entry', extra={
                    'user_id': request.user.id if request.user.is_authenticated else None,
                    'blog_entry_id': blog_entry_id,
                    'author_id': blog_entry.author.id
                })
                return Response(
                    {"error": "Cannot view private journal entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if blog_entry.visibility == 'friends':
                if not request.user.is_authenticated:
                    logger.warning('Blog entry retrieval failed - not authenticated for friends-only entry', extra={
                        'blog_entry_id': blog_entry_id,
                        'author_id': blog_entry.author.id
                    })
                    return Response(
                        {"error": "Must be logged in to view friends-only entries"},
                        status=status.HTTP_403_FORBIDDEN
                    )
                if request.user != blog_entry.author:
                    if not Friendship.objects.filter(
                        user=blog_entry.author,
                        follower=request.user
                    ).exists():
                        logger.warning('Blog entry retrieval failed - not friends with author', extra={
                            'user_id': request.user.id,
                            'blog_entry_id': blog_entry_id,
                            'author_id': blog_entry.author.id
                        })
                        return Response(
                            {"error": "Cannot view friends-only entries unless you are friends with the author"},
                            status=status.HTTP_403_FORBIDDEN
                        )

            serializer = BlogEntrySerializer(blog_entry)
            logger.info('Blog entry retrieved successfully', extra={
                'user_id': request.user.id if request.user.is_authenticated else None,
                'blog_entry_id': blog_entry_id,
                'author_id': blog_entry.author.id,
                'visibility': blog_entry.visibility
            })
            return Response(serializer.data)
            
        except BlogEntry.DoesNotExist:
            logger.warning('Blog entry retrieval failed - not found', extra={
                'user_id': request.user.id if request.user.is_authenticated else None,
                'blog_entry_id': blog_entry_id
            })
            return Response(
                {"error": "Blog entry not found"},
                status=status.HTTP_404_NOT_FOUND
            )

    def delete(self, request, blog_entry_id):
        """
        Delete a blog entry.
        
        URL Parameters:
        - blog_entry_id: ID of the blog entry to delete
        """
        try:
            logger.info('Blog entry deletion initiated', extra={
                'user_id': request.user.id,
                'blog_entry_id': blog_entry_id
            })

            blog_entry = BlogEntry.objects.get(id=blog_entry_id)
            
            # Check if user is the author of the blog entry
            if request.user != blog_entry.author:
                logger.warning('Blog entry deletion failed - not author', extra={
                    'user_id': request.user.id,
                    'blog_entry_id': blog_entry_id,
                    'author_id': blog_entry.author.id
                })
                return Response(
                    {"error": "You can only delete your own blog entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            blog_entry.delete()
            logger.info('Blog entry deleted successfully', extra={
                'user_id': request.user.id,
                'blog_entry_id': blog_entry_id
            })
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except BlogEntry.DoesNotExist:
            logger.warning('Blog entry deletion failed - not found', extra={
                'user_id': request.user.id,
                'blog_entry_id': blog_entry_id
            })
            return Response(
                {"error": "Blog entry not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class SearchView(APIView):
    permission_classes = [AllowAny]  # Allow both authenticated and unauthenticated users
    authentication_classes = [CookieJWTAuthentication]  # Use our custom authentication

    def get(self, request):
        """
        Search across users and blog entries.
        
        Query Parameters:
        - q: Search query string
        - user_page: Page number for users (default: 1)
        - user_page_size: Number of users per page (default: 3, max: 100)
        - blog_page: Page number for blog entries (default: 1)
        - blog_page_size: Number of blog entries per page (default: 3, max: 100)
        """
        search_query = request.query_params.get('q', '').strip()
        if not search_query:
            logger.warning('Search attempted without query parameter', extra={
                'user_id': request.user.id if request.user.is_authenticated else None,
                'ip': request.META.get('REMOTE_ADDR')
            })
            return Response(
                {"error": "Search query is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Get pagination parameters for users
            user_page = int(request.query_params.get('user_page', 1))
            user_page_size = min(int(request.query_params.get('user_page_size', 3)), 100)

            # Get pagination parameters for blog entries
            blog_page = int(request.query_params.get('blog_page', 1))
            blog_page_size = min(int(request.query_params.get('blog_page_size', 3)), 100)

            logger.info('Search initiated', extra={
                'query': search_query,
                'user_id': request.user.id if request.user.is_authenticated else None,
                'user_page': user_page,
                'user_page_size': user_page_size,
                'blog_page': blog_page,
                'blog_page_size': blog_page_size
            })

            # Search in users
            users = User.objects.filter(
                models.Q(username__icontains=search_query) |
                models.Q(first_name__icontains=search_query) |
                models.Q(last_name__icontains=search_query)
            )

            # Search in blog entries
            blog_entries = BlogEntry.objects.filter(
                models.Q(title__icontains=search_query) |
                models.Q(content__icontains=search_query)
            )

            # Filter blog entries based on visibility and authentication
            if request.user.is_authenticated:
                blog_entries = blog_entries.filter(
                    models.Q(author=request.user) |
                    models.Q(visibility='public') |
                    models.Q(visibility='friends', author__friendships__follower=request.user)
                ).distinct()
            else:
                blog_entries = blog_entries.filter(visibility='public')

            users = users.order_by('username')
            blog_entries = blog_entries.order_by('-created_at')

            # Calculate pagination for users
            total_users = users.count()
            start_users = (user_page - 1) * user_page_size
            end_users = start_users + user_page_size
            paginated_users = users[start_users:end_users]

            # Calculate pagination for blog entries
            total_entries = blog_entries.count()
            start_entries = (blog_page - 1) * blog_page_size
            end_entries = start_entries + blog_page_size
            paginated_entries = blog_entries[start_entries:end_entries]

            # Serialize results
            user_serializer = SearchUserSerializer(paginated_users, many=True, context={'request': request})
            blog_serializer = BlogEntrySerializer(paginated_entries, many=True)

            logger.info('Search completed successfully', extra={
                'query': search_query,
                'user_id': request.user.id if request.user.is_authenticated else None,
                'total_users': total_users,
                'total_entries': total_entries,
                'user_page': user_page,
                'blog_page': blog_page
            })

            return Response({
                'users': {
                    'count': total_users,
                    'total_pages': (total_users + user_page_size - 1) // user_page_size,
                    'current_page': user_page,
                    'page_size': user_page_size,
                    'results': user_serializer.data
                },
                'blog_entries': {
                    'count': total_entries,
                    'total_pages': (total_entries + blog_page_size - 1) // blog_page_size,
                    'current_page': blog_page,
                    'page_size': blog_page_size,
                    'results': blog_serializer.data
                }
            })

        except Exception as e:
            logger.error('Search failed', extra={
                'query': search_query,
                'user_id': request.user.id if request.user.is_authenticated else None,
                'error': str(e),
                'error_type': type(e).__name__
            }, exc_info=True)
            return Response(
                {"error": f"Error performing search: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )