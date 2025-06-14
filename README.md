# API Documentation

docker buildx build --platform linux/amd64 -t vladstanciu/blogmates-backend:0.1.0 --push .

This document provides an overview of all available API endpoints for managing blog entries, friend requests, followers, and following.

## Table of Contents
- [Authentication](#authentication)
- [User Profile Endpoints](#user-profile-endpoints)
- [Blog Entry Endpoints](#blog-entry-endpoints)
- [Friend Request Endpoints](#friend-request-endpoints)
- [Follower/Following Endpoints](#followerfollowing-endpoints)
- [Visibility Levels for Blog Entries](#visibility-levels-for-blog-entries)
- [Notes](#notes)
- [Local Development Guide](#local-development-guide)

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

## User Profile Endpoints

### 1. Get User Profile by ID
**Endpoint:** `GET /api/profile/`  
**Description:** Retrieves a user's profile by their ID.

**Query Parameters:**
```
user_id: The ID of the user whose profile to retrieve
```

**Response:**
```json
{
    "id": 1,
    "username": "testuser",
    "email": "test@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "profile_picture": "base64_encoded_image_data",
    "profile_picture_content_type": "image/jpeg",
    "follower_count": 10,
    "following_count": 5,
    "friendship_status": "following",
    "biography": "Hello! I'm a software developer passionate about web technologies."
}
```

### 2. Get User Profile by Username
**Endpoint:** `POST /api/profile/`  
**Description:** Retrieves a user's profile by username.

**Request Body:**
```json
{
    "username": "testuser"
}
```

**Response:**
```json
{
    "id": 1,
    "username": "testuser",
    "email": "test@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "profile_picture": "base64_encoded_image_data",
    "profile_picture_content_type": "image/jpeg",
    "follower_count": 10,
    "following_count": 5,
    "friendship_status": "following",
    "biography": "Hello! I'm a software developer passionate about web technologies."
}
```

### 2. Update User Profile
**Endpoint:** `PATCH /api/profile/`  
**Description:** Updates the authenticated user's profile.

**Request Body:**
```json
{
    "username": "newusername",
    "first_name": "John",
    "last_name": "Doe",
    "profile_picture": "base64_encoded_image_data",
    "profile_picture_content_type": "image/jpeg",
    "biography": "Hello! I'm a software developer passionate about web technologies."
}
```

**Response:**
```json
{
    "id": 1,
    "username": "newusername",
    "email": "test@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "profile_picture": "base64_encoded_image_data",
    "profile_picture_content_type": "image/jpeg",
    "follower_count": 10,
    "following_count": 5,
    "friendship_status": "following",
    "biography": "Hello! I'm a software developer passionate about web technologies."
}
```

**Notes:**
- All fields are optional
- `profile_picture` is stored as binary data in the database and should be sent as a base64 encoded string
- `profile_picture_content_type` should be the MIME type of the image (e.g., 'image/jpeg', 'image/png')
- `biography` is a text field with a maximum length of 500 characters
- Only the authenticated user can update their own profile
- The response includes all profile fields, including those that were not updated
- When receiving the profile data, the `profile_picture` will be returned as a base64 encoded string for JSON compatibility
- `friendship_status` can be one of:
  - `null`: No relationship exists
  - `"request_sent"`: The logged-in user has sent a friend request
  - `"following"`: The logged-in user is following this user

## Blog Entry Endpoints

### 1. Get All Visible Blog Entries
**Endpoint:** `GET /api/blog/visible/`  
**Description:** Retrieves all blog entries that the user can see based on their authentication status and relationships.

**Response for Authenticated Users:**
```json
[
    {
        "id": 1,
        "title": "My Blog Post",
        "content": "This is my blog post content",
        "visibility": "public",
        "author": 1,
        "author_name": "testuser",
        "created_at": "2024-03-20T10:00:00Z",
        "updated_at": "2024-03-20T10:00:00Z"
    }
]
```

**Notes:**
- For authenticated users, returns:
  - Their own entries (all visibility levels)
  - Public entries from others
  - Friends-only entries from their friends
- For unauthenticated users, returns only public entries
- Entries are ordered by newest first

### 2. Add a Blog Entry
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

### 3. Get User's Blog Entries
**Endpoint:** `GET /api/blog/`  
**Description:** Retrieves all blog entries authored by the authenticated user.

### 4. Get a Specific Blog Entry
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