# Data Model: Auth & Route Protection

## Entities

### User

Represents authentication credentials for a user in the system. Stored in TinyDB.

**Attributes:**
- `id` (UUID): Unique identifier for the user. Used as `user_uuid` in other systems.
- `email` (String): Unique email address used for login.
- `hashed_password` (String): The bcrypt-hashed password.
- `is_active` (Boolean): Whether the user account is active. Inactive users are rejected during authentication (login or token validation). Default: true.
- `role` (Enum): The user's role. Allowed values: `admin`, `manager`, `user`. Default: `user`.
- `created_at` (DateTime): Timestamp of account creation.

**Relationships:**
- **Profile**: 1-to-1 relationship. One User has one Profile.

### Profile

Represents the contact information and display details of a user. Stored in TinyDB.

**Attributes:**
- `id` (UUID): Unique identifier for the profile.
- `user_id` (UUID): Foreign key linking to the User `id`.
- `name` (String, Optional): The display name of the user.
- `phone` (String, Optional): Contact phone number.
- `address` (String, Optional): Contact address.

**Relationships:**
- **User**: 1-to-1 relationship. Linked via `user_id`.

## Validation Rules

- **User.email**: Must be a valid email format. Must be unique across all users.
- **User.role**: Must be strictly one of `admin`, `manager`, or `user`. Invalid roles must be rejected.
- **User.password** (input): Passwords must be at least 8 characters long (no special character requirements). Passwords must be hashed using `bcrypt` before storage. Plain-text passwords must never be stored.

## State Transitions

- **Registration**: User is created with `role` = `user` and `is_active` = `true`. Profile is created simultaneously if profile data is provided.
- **Deletion**: When a User is deleted, the corresponding Profile must also be deleted.
