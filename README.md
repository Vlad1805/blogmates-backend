# API Documentation

This document provides an overview of all available API endpoints for managing blog entries, friend requests, followers, and following.

## Authentication

### 1. Obtain JWT Tokens
**Endpoint:** `POST /api/token/`  
**Description:** Authenticates a user and provides access and refresh tokens.

**Request Body:**
```json
{
    "username": "testuser",
    "password": "securepassword123"
}
```

**Response:**
```json
{
    "access": "<access_token>",
    "refresh": "<refresh_token>"
}
```

## Blog Entry Endpoints

### 1. Add a Blog Entry
**Endpoint:** `POST /api/blog/`  
**Description:** Creates a new blog entry for the authenticated user.

**Request Body:**
```json
{
    "title": "My Blog Post",
    "content": "This is my blog post.",
    "visibility": "public"
}
```

### 2. Get User's Blog Entries
**Endpoint:** `GET /api/blog/`  
**Description:** Retrieves all blog entries authored by the authenticated user.

### 3. Get a Specific Blog Entry
**Endpoint:** `GET /api/blog/<id>/`  
**Description:** Retrieves the blog entry with the given ID. If `id` is `all`, retrieves all blog entries the user has access to.

## Friend Request Endpoints

### 1. Send a Friend Request
**Endpoint:** `POST /api/friend-requests/send/`  
**Description:** Sends a friend request to another user.

**Request Body:**
```json
{
    "receiver_id": 2
}
```

### 2. Get Pending Friend Requests
**Endpoint:** `GET /api/friend-requests/pending/`  
**Description:** Retrieves all pending friend requests sent to the authenticated user.

### 3. Accept a Friend Request
**Endpoint:** `POST /api/friend-requests/accept/<request_id>/`  
**Description:** Accepts a pending friend request.

### 4. Remove a Friend Request
**Endpoint:** `DELETE /api/friend-requests/remove/<request_id>/`  
**Description:** Deletes a friend request sent by or received by the authenticated user.

## Follower/Following Endpoints

### 1. Get All Followers
**Endpoint:** `GET /api/followers/`  
**Description:** Retrieves all users following the authenticated user.

### 2. Get All Users the User is Following
**Endpoint:** `GET /api/following/`  
**Description:** Retrieves all users the authenticated user is following.

### 3. Unfollow a User
**Endpoint:** `DELETE /api/unfollow/<user_id>/`  
**Description:** Unfollows the specified user.

### 4. Remove a Follower
**Endpoint:** `DELETE /api/remove-follower/<user_id>/`  
**Description:** Removes the specified user from the list of followers of the authenticated user.

## Visibility Levels for Blog Entries

Blog entries can have the following visibility levels:
- **public**: Visible to everyone.
- **friends**: Visible to the author’s friends.
- **journal**: Visible only to the author.

## Notes
- **Authentication:** All endpoints (except for public blog entries) require JWT-based authentication. Include the token in the `Authorization` header:
  ```
  Authorization: Bearer <access_token>
  ```

