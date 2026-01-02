# Architecture Design: Complete Authentication & Authorization System

## Title
Complete Auth System with Granular RBAC for DotMac BOS

## Scope
End-to-end authentication, authorization, session management, and granular role-based access control for the DotMac Business Operating System.

## Assumptions
- External identity provider (better-auth) handles primary authentication
- JWT tokens issued by IdP with RS256/ES256 signatures
- PostgreSQL as primary database
- Redis available for session/cache management
- Multi-tenant support required (company isolation)
- API and web UI share authentication infrastructure

---

## Components

### 1. Identity Provider Integration (External)
```
┌─────────────────────────────────────────────────────────────┐
│                    better-auth (IdP)                        │
├─────────────────────────────────────────────────────────────┤
│  - User registration/login                                  │
│  - Password management                                      │
│  - MFA/2FA                                                  │
│  - Social login (Google, Microsoft, etc.)                   │
│  - JWKS endpoint for token verification                     │
│  - Token issuance (JWT with RS256)                          │
└─────────────────────────────────────────────────────────────┘
```

### 2. Authentication Layer
```
┌─────────────────────────────────────────────────────────────┐
│                   Authentication Service                     │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ JWT Verifier │  │ Service Token│  │ API Key      │       │
│  │ (JWKS Cache) │  │ Validator    │  │ Validator    │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│           │                │                │                │
│           └────────────────┼────────────────┘                │
│                            ▼                                 │
│                   ┌──────────────────┐                       │
│                   │ Principal Factory│                       │
│                   └──────────────────┘                       │
│                            │                                 │
│           ┌────────────────┼────────────────┐                │
│           ▼                ▼                ▼                │
│    ┌───────────┐    ┌───────────┐    ┌───────────┐          │
│    │UserPrincipal│  │ServicePrincipal│ │ApiKeyPrincipal│    │
│    └───────────┘    └───────────┘    └───────────┘          │
└─────────────────────────────────────────────────────────────┘
```

### 3. Authorization Layer (Granular RBAC)
```
┌─────────────────────────────────────────────────────────────┐
│                  Authorization Engine                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                 Permission Resolver                  │    │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌────────┐ │    │
│  │  │ Direct  │  │ Role    │  │ Group   │  │Resource│ │    │
│  │  │ Grants  │  │ Grants  │  │ Grants  │  │ Scope  │ │    │
│  │  └─────────┘  └─────────┘  └─────────┘  └────────┘ │    │
│  └─────────────────────────────────────────────────────┘    │
│                            │                                 │
│                            ▼                                 │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Policy Evaluation Engine                │    │
│  │  - Resource-level permissions                        │    │
│  │  - Field-level permissions                           │    │
│  │  - Row-level security (data scoping)                 │    │
│  │  - Time-based access                                 │    │
│  │  - Conditional permissions                           │    │
│  └─────────────────────────────────────────────────────┘    │
│                            │                                 │
│                            ▼                                 │
│                    ┌──────────────┐                          │
│                    │Access Decision│                         │
│                    │   (Allow/Deny)│                         │
│                    └──────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

### 4. Session Management
```
┌─────────────────────────────────────────────────────────────┐
│                   Session Manager                            │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐    ┌──────────────────┐               │
│  │  Cookie Sessions │    │  Token Sessions  │               │
│  │  (Web UI)        │    │  (API clients)   │               │
│  └──────────────────┘    └──────────────────┘               │
│           │                      │                           │
│           └──────────┬───────────┘                           │
│                      ▼                                       │
│            ┌──────────────────┐                              │
│            │  Session Store   │                              │
│            │  (Redis/Memory)  │                              │
│            └──────────────────┘                              │
│                      │                                       │
│           ┌──────────┼───────────┐                           │
│           ▼          ▼           ▼                           │
│    ┌──────────┐ ┌──────────┐ ┌──────────┐                   │
│    │ Creation │ │ Refresh  │ │Revocation│                   │
│    └──────────┘ └──────────┘ └──────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

### 5. Audit & Compliance
```
┌─────────────────────────────────────────────────────────────┐
│                    Audit System                              │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ Auth Events  │  │ Access Log   │  │ Admin Actions│       │
│  │ (login/out)  │  │ (who/what)   │  │ (changes)    │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│           │                │                │                │
│           └────────────────┼────────────────┘                │
│                            ▼                                 │
│                   ┌──────────────────┐                       │
│                   │ Audit Log Store  │                       │
│                   │ (immutable)      │                       │
│                   └──────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### 1. User Authentication Flow (SSO)
```
┌──────┐     ┌─────────┐     ┌──────────┐     ┌──────────┐
│Client│────▶│ /login  │────▶│ IdP      │────▶│ /callback│
└──────┘     └─────────┘     │(better-  │     └──────────┘
                             │ auth)    │           │
                             └──────────┘           ▼
                                            ┌──────────────┐
                                            │Verify JWT    │
                                            │Create/Update │
                                            │User          │
                                            │Set Cookie    │
                                            └──────────────┘
                                                   │
                                                   ▼
                                            ┌──────────────┐
                                            │ Dashboard    │
                                            └──────────────┘
```

### 2. API Request Authorization Flow
```
┌──────────┐     ┌──────────────┐     ┌──────────────┐
│API Request│───▶│Extract Token │───▶│Verify Token  │
│(Bearer)   │    │(Header/Cookie)│    │(JWT/Service) │
└──────────┘     └──────────────┘     └──────────────┘
                                             │
                                             ▼
                                      ┌──────────────┐
                                      │Create        │
                                      │Principal     │
                                      └──────────────┘
                                             │
                                             ▼
                                      ┌──────────────┐
                                      │Resolve       │
                                      │Permissions   │
                                      │(Roles+Direct)│
                                      └──────────────┘
                                             │
                                             ▼
                                      ┌──────────────┐
                                      │Check Required│
                                      │Scope         │
                                      └──────────────┘
                                             │
                              ┌──────────────┴──────────────┐
                              ▼                              ▼
                       ┌──────────┐                   ┌──────────┐
                       │ ALLOWED  │                   │ DENIED   │
                       │ (200)    │                   │ (403)    │
                       └──────────┘                   └──────────┘
```

### 3. Granular Permission Resolution Flow
```
Request: GET /api/customers/123

1. Extract Principal
   └─▶ User: john@example.com

2. Load User's Effective Permissions
   ├─▶ Direct Grants: [customers:read]
   ├─▶ Role Grants:
   │   ├─▶ "sales_rep" role: [customers:read, customers:update:own]
   │   └─▶ "viewer" role: [*:read]
   └─▶ Group Grants:
       └─▶ "Sales Team" group: [opportunities:*, quotes:*]

3. Merge & Deduplicate
   └─▶ Effective: [customers:read, customers:update:own, *:read, ...]

4. Apply Resource Scope
   └─▶ Check: customers:update:own
       └─▶ Is user owner of customer 123?
           ├─▶ Yes: Allow
           └─▶ No: Check next permission

5. Apply Data Filters (Row-Level Security)
   └─▶ User assigned_to customers only
   └─▶ SQL: WHERE assigned_to_id = :user_id OR is_public = true
```

---

## Data Model Changes

### Core Auth Tables (Existing - Enhanced)

```sql
-- Users (enhanced)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id VARCHAR(255) UNIQUE NOT NULL,  -- IdP subject
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    picture VARCHAR(500),

    -- Status
    is_active BOOLEAN DEFAULT true,
    is_superuser BOOLEAN DEFAULT false,
    is_verified BOOLEAN DEFAULT false,

    -- Multi-tenant
    company_id UUID REFERENCES companies(id),

    -- Metadata
    preferences JSONB DEFAULT '{}',
    last_login_at TIMESTAMPTZ,
    last_active_at TIMESTAMPTZ,
    login_count INTEGER DEFAULT 0,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by_id UUID REFERENCES users(id),

    -- Indexes
    CONSTRAINT users_email_lower_idx UNIQUE (LOWER(email))
);

CREATE INDEX idx_users_company ON users(company_id);
CREATE INDEX idx_users_external_id ON users(external_id);
CREATE INDEX idx_users_active ON users(is_active) WHERE is_active = true;
```

### Granular RBAC Tables (New)

```sql
-- Permission Categories (for UI organization)
CREATE TABLE permission_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    icon VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Permissions (enhanced for granularity)
CREATE TABLE permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Scope definition: resource:action or resource:sub-resource:action
    scope VARCHAR(255) NOT NULL UNIQUE,

    -- Hierarchy
    category_id UUID REFERENCES permission_categories(id),
    parent_scope VARCHAR(255),  -- For inheritance (customers:* parent of customers:read)

    -- Metadata
    display_name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Flags
    is_system BOOLEAN DEFAULT false,      -- Cannot be deleted
    is_dangerous BOOLEAN DEFAULT false,   -- Requires confirmation
    requires_mfa BOOLEAN DEFAULT false,   -- Requires MFA to use

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT permissions_scope_format CHECK (
        scope ~ '^[a-z][a-z0-9_]*(\:[a-z][a-z0-9_]*)*$' OR scope = '*'
    )
);

CREATE INDEX idx_permissions_category ON permissions(category_id);
CREATE INDEX idx_permissions_parent ON permissions(parent_scope);
CREATE INDEX idx_permissions_scope_prefix ON permissions(scope varchar_pattern_ops);

-- Roles (enhanced)
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Hierarchy
    parent_role_id UUID REFERENCES roles(id),  -- Role inheritance

    -- Scope
    company_id UUID REFERENCES companies(id),  -- NULL = global role

    -- Flags
    is_system BOOLEAN DEFAULT false,
    is_default BOOLEAN DEFAULT false,  -- Auto-assign to new users
    max_users INTEGER,                 -- License limit

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by_id UUID REFERENCES users(id),

    CONSTRAINT roles_name_company_unique UNIQUE (name, company_id)
);

CREATE INDEX idx_roles_company ON roles(company_id);
CREATE INDEX idx_roles_parent ON roles(parent_role_id);

-- Role Permissions (junction)
CREATE TABLE role_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,

    -- Conditions (JSON for complex rules)
    conditions JSONB DEFAULT '{}',
    -- Examples:
    -- {"own_only": true}  -- Only own records
    -- {"departments": ["sales", "support"]}  -- Specific departments
    -- {"time_range": {"start": "09:00", "end": "17:00"}}  -- Time-based

    -- Audit
    granted_at TIMESTAMPTZ DEFAULT NOW(),
    granted_by_id UUID REFERENCES users(id),
    expires_at TIMESTAMPTZ,

    CONSTRAINT role_permissions_unique UNIQUE (role_id, permission_id)
);

CREATE INDEX idx_role_permissions_role ON role_permissions(role_id);
CREATE INDEX idx_role_permissions_permission ON role_permissions(permission_id);
CREATE INDEX idx_role_permissions_expires ON role_permissions(expires_at) WHERE expires_at IS NOT NULL;

-- User Roles (junction - enhanced)
CREATE TABLE user_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,

    -- Scope limitation
    scope_type VARCHAR(50),  -- 'global', 'company', 'department', 'team'
    scope_id UUID,           -- ID of scoped entity

    -- Validity
    valid_from TIMESTAMPTZ DEFAULT NOW(),
    valid_until TIMESTAMPTZ,

    -- Audit
    assigned_at TIMESTAMPTZ DEFAULT NOW(),
    assigned_by_id UUID REFERENCES users(id),

    CONSTRAINT user_roles_unique UNIQUE (user_id, role_id, scope_type, scope_id)
);

CREATE INDEX idx_user_roles_user ON user_roles(user_id);
CREATE INDEX idx_user_roles_role ON user_roles(role_id);
CREATE INDEX idx_user_roles_validity ON user_roles(valid_from, valid_until);

-- Direct User Permissions (bypass roles for exceptions)
CREATE TABLE user_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,

    -- Grant type
    grant_type VARCHAR(20) NOT NULL DEFAULT 'allow',  -- 'allow' or 'deny'

    -- Conditions (same as role_permissions)
    conditions JSONB DEFAULT '{}',

    -- Validity
    valid_from TIMESTAMPTZ DEFAULT NOW(),
    valid_until TIMESTAMPTZ,

    -- Audit
    reason TEXT,  -- Why was this exception granted?
    granted_at TIMESTAMPTZ DEFAULT NOW(),
    granted_by_id UUID REFERENCES users(id),

    CONSTRAINT user_permissions_unique UNIQUE (user_id, permission_id)
);

CREATE INDEX idx_user_permissions_user ON user_permissions(user_id);
CREATE INDEX idx_user_permissions_permission ON user_permissions(permission_id);

-- Groups (for team-based permissions)
CREATE TABLE groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Scope
    company_id UUID REFERENCES companies(id),

    -- Hierarchy
    parent_group_id UUID REFERENCES groups(id),

    -- Flags
    is_system BOOLEAN DEFAULT false,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by_id UUID REFERENCES users(id),

    CONSTRAINT groups_name_company_unique UNIQUE (name, company_id)
);

CREATE INDEX idx_groups_company ON groups(company_id);
CREATE INDEX idx_groups_parent ON groups(parent_group_id);

-- User Groups (junction)
CREATE TABLE user_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,

    -- Role within group
    is_admin BOOLEAN DEFAULT false,

    -- Audit
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    added_by_id UUID REFERENCES users(id),

    CONSTRAINT user_groups_unique UNIQUE (user_id, group_id)
);

CREATE INDEX idx_user_groups_user ON user_groups(user_id);
CREATE INDEX idx_user_groups_group ON user_groups(group_id);

-- Group Roles (groups can have roles)
CREATE TABLE group_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,

    -- Audit
    assigned_at TIMESTAMPTZ DEFAULT NOW(),
    assigned_by_id UUID REFERENCES users(id),

    CONSTRAINT group_roles_unique UNIQUE (group_id, role_id)
);

CREATE INDEX idx_group_roles_group ON group_roles(group_id);
CREATE INDEX idx_group_roles_role ON group_roles(role_id);

-- Resource-Level Permissions (for specific records)
CREATE TABLE resource_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Principal (who)
    principal_type VARCHAR(20) NOT NULL,  -- 'user', 'role', 'group'
    principal_id UUID NOT NULL,

    -- Resource (what)
    resource_type VARCHAR(100) NOT NULL,  -- 'customer', 'ticket', 'invoice'
    resource_id UUID NOT NULL,

    -- Permission
    permission_id UUID NOT NULL REFERENCES permissions(id),

    -- Grant type
    grant_type VARCHAR(20) NOT NULL DEFAULT 'allow',

    -- Validity
    valid_from TIMESTAMPTZ DEFAULT NOW(),
    valid_until TIMESTAMPTZ,

    -- Audit
    granted_at TIMESTAMPTZ DEFAULT NOW(),
    granted_by_id UUID REFERENCES users(id),

    CONSTRAINT resource_permissions_unique UNIQUE (
        principal_type, principal_id, resource_type, resource_id, permission_id
    )
);

CREATE INDEX idx_resource_permissions_principal ON resource_permissions(principal_type, principal_id);
CREATE INDEX idx_resource_permissions_resource ON resource_permissions(resource_type, resource_id);
```

### Session & Token Tables

```sql
-- Sessions (for active session tracking)
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Session info
    token_hash VARCHAR(64) NOT NULL UNIQUE,  -- SHA256 of session token

    -- Context
    ip_address INET,
    user_agent TEXT,
    device_fingerprint VARCHAR(64),

    -- Location (optional)
    country_code CHAR(2),
    city VARCHAR(100),

    -- Status
    is_active BOOLEAN DEFAULT true,
    last_active_at TIMESTAMPTZ DEFAULT NOW(),

    -- Validity
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    revoked_reason VARCHAR(100),

    -- MFA
    mfa_verified BOOLEAN DEFAULT false,
    mfa_verified_at TIMESTAMPTZ
);

CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_token ON sessions(token_hash);
CREATE INDEX idx_sessions_active ON sessions(is_active, expires_at) WHERE is_active = true;
CREATE INDEX idx_sessions_user_active ON sessions(user_id, is_active) WHERE is_active = true;

-- Service Tokens (enhanced)
CREATE TABLE service_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    name VARCHAR(255) NOT NULL,
    description TEXT,
    prefix VARCHAR(12) NOT NULL UNIQUE,  -- For quick lookup
    token_hash VARCHAR(255) NOT NULL,     -- bcrypt hash

    -- Ownership
    company_id UUID REFERENCES companies(id),
    created_by_id UUID NOT NULL REFERENCES users(id),

    -- Permissions (can reference roles or direct scopes)
    role_id UUID REFERENCES roles(id),
    scopes TEXT,  -- Comma-separated if not using role

    -- Rate limiting
    rate_limit_per_minute INTEGER,
    rate_limit_per_hour INTEGER,

    -- IP restrictions
    allowed_ips INET[],

    -- Status
    is_active BOOLEAN DEFAULT true,

    -- Validity
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    use_count INTEGER DEFAULT 0,

    -- Revocation
    revoked_at TIMESTAMPTZ,
    revoked_by_id UUID REFERENCES users(id),
    revoke_reason TEXT
);

CREATE INDEX idx_service_tokens_prefix ON service_tokens(prefix);
CREATE INDEX idx_service_tokens_company ON service_tokens(company_id);
CREATE INDEX idx_service_tokens_active ON service_tokens(is_active) WHERE is_active = true;

-- Token Denylist (for immediate revocation)
CREATE TABLE token_denylist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Token identifier
    jti VARCHAR(255) NOT NULL UNIQUE,  -- JWT ID or token prefix
    token_type VARCHAR(20) NOT NULL,   -- 'jwt', 'service', 'session'

    -- Reason
    reason VARCHAR(255),

    -- Validity
    denylisted_at TIMESTAMPTZ DEFAULT NOW(),
    denylisted_by_id UUID REFERENCES users(id),
    expires_at TIMESTAMPTZ NOT NULL  -- Auto-cleanup after token would expire
);

CREATE INDEX idx_token_denylist_jti ON token_denylist(jti);
CREATE INDEX idx_token_denylist_expires ON token_denylist(expires_at);

-- API Keys (for external integrations)
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    name VARCHAR(255) NOT NULL,
    key_prefix VARCHAR(12) NOT NULL UNIQUE,
    key_hash VARCHAR(255) NOT NULL,

    -- Ownership
    company_id UUID REFERENCES companies(id),
    user_id UUID REFERENCES users(id),  -- Optional owner

    -- Permissions
    role_id UUID REFERENCES roles(id),
    scopes TEXT,

    -- Restrictions
    allowed_origins TEXT[],
    allowed_ips INET[],

    -- Rate limiting
    rate_limit_per_minute INTEGER DEFAULT 60,
    rate_limit_per_day INTEGER DEFAULT 10000,

    -- Status
    is_active BOOLEAN DEFAULT true,

    -- Validity
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    use_count BIGINT DEFAULT 0,

    -- Audit
    created_by_id UUID REFERENCES users(id)
);

CREATE INDEX idx_api_keys_prefix ON api_keys(key_prefix);
CREATE INDEX idx_api_keys_company ON api_keys(company_id);
```

### Audit Tables

```sql
-- Auth Audit Log (immutable)
CREATE TABLE auth_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Event
    event_type VARCHAR(50) NOT NULL,
    -- Types: login_success, login_failure, logout, password_change,
    --        mfa_enabled, mfa_disabled, session_created, session_revoked,
    --        permission_granted, permission_revoked, role_assigned, etc.

    -- Principal
    user_id UUID REFERENCES users(id),
    principal_type VARCHAR(20),  -- 'user', 'service_token', 'api_key'
    principal_id UUID,

    -- Target (for admin actions)
    target_type VARCHAR(50),
    target_id UUID,

    -- Context
    ip_address INET,
    user_agent TEXT,

    -- Details
    details JSONB DEFAULT '{}',

    -- Result
    success BOOLEAN NOT NULL,
    failure_reason VARCHAR(255),

    -- Timestamp
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Partitioned by month for performance
CREATE INDEX idx_auth_audit_user ON auth_audit_log(user_id, created_at);
CREATE INDEX idx_auth_audit_type ON auth_audit_log(event_type, created_at);
CREATE INDEX idx_auth_audit_created ON auth_audit_log(created_at);

-- Permission Change Log (for compliance)
CREATE TABLE permission_change_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Change type
    change_type VARCHAR(20) NOT NULL,  -- 'grant', 'revoke', 'modify'

    -- What changed
    entity_type VARCHAR(50) NOT NULL,  -- 'user', 'role', 'group'
    entity_id UUID NOT NULL,
    permission_scope VARCHAR(255) NOT NULL,

    -- Before/After (for modify)
    old_value JSONB,
    new_value JSONB,

    -- Who made the change
    changed_by_id UUID REFERENCES users(id),

    -- Why
    reason TEXT,
    ticket_reference VARCHAR(100),  -- Link to change request

    -- When
    changed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_permission_change_entity ON permission_change_log(entity_type, entity_id);
CREATE INDEX idx_permission_change_scope ON permission_change_log(permission_scope);
CREATE INDEX idx_permission_change_time ON permission_change_log(changed_at);
```

---

## Permission Scope Convention

### Format
```
{resource}:{action}
{resource}:{sub-resource}:{action}
```

### Standard Actions
| Action | Description |
|--------|-------------|
| `read` | View records |
| `create` | Create new records |
| `update` | Modify existing records |
| `delete` | Remove records |
| `export` | Export/download data |
| `import` | Import/upload data |
| `approve` | Approve workflows |
| `assign` | Assign to others |
| `manage` | Full control |
| `*` | All actions on resource |

### Scope Modifiers (in conditions)
| Modifier | Description |
|----------|-------------|
| `:own` | Only records created by user |
| `:assigned` | Only records assigned to user |
| `:team` | Only records in user's team |
| `:department` | Only records in user's department |

### Example Permission Scopes
```
# Customer Management
customers:read              # View all customers
customers:create            # Create customers
customers:update            # Update any customer
customers:delete            # Delete customers
customers:export            # Export customer data
customers:contacts:read     # View customer contacts
customers:contacts:manage   # Full control over contacts

# Support
support:tickets:read        # View tickets
support:tickets:create      # Create tickets
support:tickets:update:own  # Update own tickets only
support:tickets:assign      # Assign tickets
support:tickets:close       # Close tickets

# Accounting
accounting:invoices:read
accounting:invoices:create
accounting:invoices:approve
accounting:payments:read
accounting:payments:create
accounting:reports:read
accounting:reports:export

# HR
hr:employees:read
hr:employees:update
hr:payroll:read
hr:payroll:process
hr:leave:approve

# Admin
admin:users:read
admin:users:manage
admin:roles:read
admin:roles:manage
admin:settings:read
admin:settings:manage

# Wildcard
*                           # Superuser - all permissions
customers:*                 # All customer permissions
accounting:*                # All accounting permissions
```

---

## Default Roles

### System Roles (is_system=true)

```yaml
superadmin:
  display_name: "Super Administrator"
  description: "Full system access - use sparingly"
  permissions:
    - "*"

admin:
  display_name: "Administrator"
  description: "Administrative access to all modules"
  permissions:
    - "admin:*"
    - "customers:*"
    - "accounting:*"
    - "support:*"
    - "hr:*"
    - "inventory:*"
    - "reports:*"

# Module-specific admin roles
customer_admin:
  display_name: "Customer Administrator"
  permissions:
    - "customers:*"
    - "support:tickets:read"

accounting_admin:
  display_name: "Accounting Administrator"
  permissions:
    - "accounting:*"
    - "reports:financial:*"

hr_admin:
  display_name: "HR Administrator"
  permissions:
    - "hr:*"
    - "reports:hr:*"
```

### Standard Roles

```yaml
manager:
  display_name: "Manager"
  description: "Department manager with approval rights"
  permissions:
    - "customers:read"
    - "support:tickets:read"
    - "support:tickets:assign"
    - "accounting:invoices:read"
    - "accounting:invoices:approve"
    - "hr:leave:approve"
    - "reports:read"

operator:
  display_name: "Operator"
  description: "Day-to-day operations"
  permissions:
    - "customers:read"
    - "customers:update"
    - "support:tickets:*"
    - "accounting:invoices:read"
    - "accounting:payments:create"

analyst:
  display_name: "Analyst"
  description: "Read-only access with export"
  permissions:
    - "customers:read"
    - "support:tickets:read"
    - "accounting:read"
    - "reports:read"
    - "reports:export"
    - "analytics:read"
    - "analytics:export"

viewer:
  display_name: "Viewer"
  description: "Basic read-only access"
  permissions:
    - "customers:read"
    - "support:tickets:read"
    - "accounting:invoices:read"
```

---

## API Endpoints

### Authentication
```
POST   /auth/session              # Create session from JWT
DELETE /auth/session              # End session (logout)
POST   /auth/refresh              # Refresh session
GET    /auth/me                   # Current user info
POST   /auth/mfa/enable           # Enable MFA
POST   /auth/mfa/verify           # Verify MFA code
DELETE /auth/mfa                  # Disable MFA
```

### Session Management
```
GET    /auth/sessions             # List active sessions
DELETE /auth/sessions/{id}        # Revoke specific session
DELETE /auth/sessions             # Revoke all sessions
```

### User Management (Admin)
```
GET    /admin/users               # List users
GET    /admin/users/{id}          # Get user details
PATCH  /admin/users/{id}          # Update user
POST   /admin/users/{id}/activate # Activate user
POST   /admin/users/{id}/deactivate # Deactivate user
GET    /admin/users/{id}/permissions # Get effective permissions
POST   /admin/users/{id}/permissions # Grant direct permission
DELETE /admin/users/{id}/permissions/{perm_id} # Revoke permission
GET    /admin/users/{id}/roles    # Get user's roles
POST   /admin/users/{id}/roles    # Assign role
DELETE /admin/users/{id}/roles/{role_id} # Unassign role
GET    /admin/users/{id}/sessions # Get user's sessions
DELETE /admin/users/{id}/sessions # Revoke all user sessions
```

### Role Management (Admin)
```
GET    /admin/roles               # List roles
POST   /admin/roles               # Create role
GET    /admin/roles/{id}          # Get role details
PATCH  /admin/roles/{id}          # Update role
DELETE /admin/roles/{id}          # Delete role
GET    /admin/roles/{id}/permissions # Get role's permissions
POST   /admin/roles/{id}/permissions # Add permission to role
DELETE /admin/roles/{id}/permissions/{perm_id} # Remove permission
GET    /admin/roles/{id}/users    # List users with role
```

### Permission Management (Admin)
```
GET    /admin/permissions         # List all permissions
GET    /admin/permissions/categories # List categories
POST   /admin/permissions         # Create permission (custom)
GET    /admin/permissions/{id}    # Get permission details
DELETE /admin/permissions/{id}    # Delete permission
```

### Group Management (Admin)
```
GET    /admin/groups              # List groups
POST   /admin/groups              # Create group
GET    /admin/groups/{id}         # Get group details
PATCH  /admin/groups/{id}         # Update group
DELETE /admin/groups/{id}         # Delete group
GET    /admin/groups/{id}/members # List group members
POST   /admin/groups/{id}/members # Add member
DELETE /admin/groups/{id}/members/{user_id} # Remove member
GET    /admin/groups/{id}/roles   # Get group's roles
POST   /admin/groups/{id}/roles   # Assign role to group
DELETE /admin/groups/{id}/roles/{role_id} # Unassign role
```

### Service Tokens (Admin)
```
GET    /admin/tokens              # List service tokens
POST   /admin/tokens              # Create token
GET    /admin/tokens/{id}         # Get token details
PATCH  /admin/tokens/{id}         # Update token
DELETE /admin/tokens/{id}         # Revoke token
POST   /admin/tokens/{id}/rotate  # Rotate token
```

### API Keys
```
GET    /admin/api-keys            # List API keys
POST   /admin/api-keys            # Create API key
GET    /admin/api-keys/{id}       # Get key details
PATCH  /admin/api-keys/{id}       # Update key
DELETE /admin/api-keys/{id}       # Revoke key
POST   /admin/api-keys/{id}/rotate # Rotate key
```

### Audit
```
GET    /admin/audit/auth          # Auth audit log
GET    /admin/audit/permissions   # Permission change log
GET    /admin/audit/export        # Export audit logs
```

---

## Non-Functional Requirements

### Performance
- Permission resolution: < 5ms (cached)
- Token verification: < 10ms (JWKS cached)
- Session lookup: < 2ms (Redis)
- Audit log write: async, non-blocking
- Permission cache TTL: 60 seconds
- JWKS cache TTL: 1 hour

### Availability
- Auth service: 99.9% uptime
- Graceful degradation: stale cache fallback
- Session store: Redis with persistence
- Database: Connection pooling with health checks

### Security
- Passwords: bcrypt with work factor 12
- Tokens: 256-bit entropy
- Sessions: httpOnly, Secure, SameSite=Lax
- CSRF: Double-submit cookie pattern
- Rate limiting: 10 auth attempts/minute, 5-min block
- MFA: TOTP (RFC 6238) support
- IP allowlisting: For service tokens
- Audit: Immutable, tamper-evident logs

### Observability
- Metrics: auth_success_total, auth_failure_total, session_count
- Logs: Structured JSON with correlation IDs
- Alerts: Failed login spikes, privilege escalation attempts
- Dashboard: Active sessions, token usage, permission grants

---

## Tradeoffs

### Permission Model: RBAC vs ABAC

| Aspect | RBAC (Chosen) | ABAC |
|--------|---------------|------|
| Complexity | Lower | Higher |
| Flexibility | Moderate | Very High |
| Performance | Faster | Slower (policy eval) |
| Auditability | Easier | More complex |
| Learning curve | Lower | Higher |

**Decision**: RBAC with conditional permissions provides sufficient flexibility while maintaining simplicity. ABAC can be added later if needed.

### Session Storage: Redis vs Database

| Aspect | Redis (Chosen) | Database |
|--------|----------------|----------|
| Performance | Very fast | Slower |
| Persistence | Configurable | Built-in |
| Scalability | Excellent | Good |
| Complexity | Additional service | Simpler |

**Decision**: Redis for active session lookup with database backup for audit trail.

### Permission Inheritance: Hierarchical vs Flat

| Aspect | Hierarchical (Chosen) | Flat |
|--------|----------------------|------|
| DRY | Better | Repetitive |
| Complexity | Higher | Lower |
| Debugging | Harder | Easier |
| Flexibility | More | Less |

**Decision**: Hierarchical with role inheritance and wildcard permissions. Effective permissions always computed and cached.

---

## Rollout Plan

### Phase 1: Foundation
1. Create database migrations for new tables
2. Implement permission resolver service
3. Update Principal model with new permission logic
4. Add permission caching layer
5. Seed default roles and permissions

### Phase 2: Admin UI
1. Build role management pages
2. Build permission assignment UI
3. Add user permission viewer
4. Create group management
5. Add audit log viewer

### Phase 3: Granular Controls
1. Implement resource-level permissions
2. Add conditional permissions (own, team, etc.)
3. Build row-level security filters
4. Add field-level permissions (if needed)

### Phase 4: Advanced Features
1. Session management UI
2. API key management
3. MFA integration
4. IP restrictions
5. Time-based permissions

### Feature Flags
```python
FEATURE_FLAGS = {
    "auth.granular_rbac": True,
    "auth.resource_permissions": False,  # Phase 3
    "auth.mfa": False,  # Phase 4
    "auth.api_keys": False,  # Phase 4
}
```

---

## Implementation Files

| Component | File Path |
|-----------|-----------|
| Auth Models | `app/models/auth.py` |
| Permission Resolver | `app/services/permission_resolver.py` |
| Auth Service | `app/services/auth_service.py` |
| Session Manager | `app/services/session_manager.py` |
| RBAC Sync | `app/services/rbac_sync.py` |
| Auth Dependencies | `app/auth.py` |
| Web Dependencies | `app/web/dependencies.py` |
| Admin API Routes | `app/api/admin/` |
| Admin Web Routes | `app/modules/settings/admin_routes.py` |
| Migrations | `alembic/versions/YYYYMMDD_auth_*.py` |

---

## Security Considerations

### Privilege Escalation Prevention
- Users cannot assign roles with more permissions than they have
- Role hierarchy prevents circular inheritance
- Admin actions require re-authentication for dangerous operations

### Session Security
- Session tokens rotated on privilege change
- Concurrent session limit per user (configurable)
- Automatic session cleanup on password change
- IP-based session validation (optional)

### Audit Trail
- All permission changes logged with who/what/when/why
- Immutable audit log (append-only)
- Retention policy: 7 years for compliance
- Export capability for external SIEM

### Defense in Depth
- Input validation at all layers
- Parameterized queries (SQLAlchemy ORM)
- Output encoding (Jinja2 auto-escape)
- HTTPS enforced in production
- Security headers (CSP, HSTS, X-Frame-Options)

---

## Appendix: Permission Categories

```yaml
categories:
  - name: customers
    display_name: "Customer Management"
    icon: "users"

  - name: support
    display_name: "Support & Helpdesk"
    icon: "life-buoy"

  - name: accounting
    display_name: "Accounting & Finance"
    icon: "dollar-sign"

  - name: hr
    display_name: "Human Resources"
    icon: "briefcase"

  - name: inventory
    display_name: "Inventory & Assets"
    icon: "package"

  - name: network
    display_name: "Network Management"
    icon: "globe"

  - name: reports
    display_name: "Reports & Analytics"
    icon: "bar-chart"

  - name: admin
    display_name: "Administration"
    icon: "settings"

  - name: sync
    display_name: "Data Synchronization"
    icon: "refresh-cw"
```

---

## ADR: Granular RBAC Implementation

**Date**: 2026-01-01
**Status**: Proposed

### Context
The current auth system uses a basic RBAC model with roles containing permission scopes as strings. As the application grows, we need:
- More granular control over permissions
- Resource-level and row-level security
- Group-based permissions for teams
- Time-limited and conditional permissions
- Better auditability for compliance

### Decision
Implement an enhanced RBAC system with:
1. Hierarchical roles with inheritance
2. Permission categories for organization
3. Direct user permissions for exceptions
4. Groups for team-based access
5. Conditional permissions with JSON rules
6. Resource-level permissions for specific records

### Consequences

**Positive**:
- Fine-grained access control
- Reduced over-permissioning
- Better compliance posture
- Flexible team structures
- Clear audit trail

**Negative**:
- Increased complexity
- Performance overhead (mitigated by caching)
- Learning curve for admins
- Migration effort from current system

### Alternatives Considered

1. **Keep current simple RBAC**: Not sufficient for enterprise needs
2. **Implement full ABAC**: Too complex, overkill for current requirements
3. **Use external authorization service (OPA)**: Additional infrastructure, latency concerns
