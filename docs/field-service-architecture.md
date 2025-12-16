# Field Service Module - Architecture Plan

## Overview

The Field Service module manages technician deployment for:
- Project installations (new customer setups, network deployments)
- Support ticket field visits (on-site repairs, troubleshooting)
- Preventive maintenance schedules
- Asset installation and tracking

This module integrates with existing Projects, Support, HR (Employees), and Inventory modules.

---

## Data Models

### 1. Service Order (Core Entity)
```python
# app/models/service_order.py

class ServiceOrderType(enum.Enum):
    INSTALLATION = "installation"      # New project/customer setup
    REPAIR = "repair"                  # Support ticket field visit
    MAINTENANCE = "maintenance"        # Scheduled preventive maintenance
    INSPECTION = "inspection"          # Site survey/assessment
    RELOCATION = "relocation"          # Equipment move/upgrade

class ServiceOrderStatus(enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    DISPATCHED = "dispatched"
    EN_ROUTE = "en_route"
    ON_SITE = "on_site"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    RESCHEDULED = "rescheduled"

class ServiceOrderPriority(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"
    EMERGENCY = "emergency"

class ServiceOrder(Base):
    __tablename__ = "service_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_number: Mapped[str] = mapped_column(String(50), unique=True)

    # Type and status
    order_type: Mapped[ServiceOrderType]
    status: Mapped[ServiceOrderStatus]
    priority: Mapped[ServiceOrderPriority]

    # Linked entities
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id"))
    task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tasks.id"))
    ticket_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tickets.id"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))

    # Assignment
    assigned_technician_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"))
    assigned_team_id: Mapped[Optional[int]] = mapped_column(ForeignKey("field_teams.id"))

    # Location
    service_address: Mapped[str] = mapped_column(Text)
    city: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[Optional[str]] = mapped_column(String(100))
    latitude: Mapped[Optional[Decimal]] = mapped_column()
    longitude: Mapped[Optional[Decimal]] = mapped_column()

    # Scheduling
    scheduled_date: Mapped[date]
    scheduled_start_time: Mapped[Optional[time]]
    scheduled_end_time: Mapped[Optional[time]]
    estimated_duration_hours: Mapped[Decimal] = mapped_column(default=Decimal("1"))

    # Actual times
    actual_start_time: Mapped[Optional[datetime]]
    actual_end_time: Mapped[Optional[datetime]]
    travel_start_time: Mapped[Optional[datetime]]
    arrival_time: Mapped[Optional[datetime]]

    # Work details
    description: Mapped[Optional[str]] = mapped_column(Text)
    work_performed: Mapped[Optional[str]] = mapped_column(Text)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text)

    # Customer interaction
    customer_contact_name: Mapped[Optional[str]] = mapped_column(String(255))
    customer_contact_phone: Mapped[Optional[str]] = mapped_column(String(50))
    customer_signature: Mapped[Optional[str]] = mapped_column(Text)  # Base64 signature
    customer_rating: Mapped[Optional[int]]  # 1-5
    customer_feedback: Mapped[Optional[str]] = mapped_column(Text)

    # Costing
    labor_cost: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    parts_cost: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    travel_cost: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    total_cost: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    billable_amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    # Metadata
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    created_by: Mapped[Optional[str]] = mapped_column(String(255))

    # Relationships
    customer: Mapped["Customer"] = relationship()
    project: Mapped[Optional["Project"]] = relationship()
    task: Mapped[Optional["Task"]] = relationship()
    ticket: Mapped[Optional["Ticket"]] = relationship()
    technician: Mapped[Optional["Employee"]] = relationship()
    team: Mapped[Optional["FieldTeam"]] = relationship()
    items_used: Mapped[List["ServiceOrderItem"]] = relationship()
    checklist_items: Mapped[List["ServiceChecklist"]] = relationship()
    photos: Mapped[List["ServicePhoto"]] = relationship()
    time_entries: Mapped[List["ServiceTimeEntry"]] = relationship()
```

### 2. Field Teams
```python
class FieldTeam(Base):
    __tablename__ = "field_teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Coverage area
    coverage_zones: Mapped[Optional[str]] = mapped_column(Text)  # JSON array of zone IDs
    max_daily_orders: Mapped[int] = mapped_column(default=10)

    # Contact
    supervisor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"))
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50))

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)

    # Relationships
    members: Mapped[List["FieldTeamMember"]] = relationship()
    supervisor: Mapped[Optional["Employee"]] = relationship()

class FieldTeamMember(Base):
    __tablename__ = "field_team_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("field_teams.id"))
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    role: Mapped[str] = mapped_column(String(50))  # lead, technician, helper
    is_active: Mapped[bool] = mapped_column(default=True)
    joined_date: Mapped[date]
```

### 3. Technician Skills & Certifications
```python
class TechnicianSkill(Base):
    __tablename__ = "technician_skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    skill_type: Mapped[str] = mapped_column(String(100))  # fiber, wireless, networking, electrical
    proficiency_level: Mapped[str] = mapped_column(String(50))  # basic, intermediate, expert
    certification: Mapped[Optional[str]] = mapped_column(String(255))
    certification_expiry: Mapped[Optional[date]]
    is_active: Mapped[bool] = mapped_column(default=True)
```

### 4. Service Checklist Templates
```python
class ChecklistTemplate(Base):
    __tablename__ = "checklist_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    order_type: Mapped[ServiceOrderType]
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True)
    items: Mapped[List["ChecklistTemplateItem"]] = relationship()

class ChecklistTemplateItem(Base):
    __tablename__ = "checklist_template_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("checklist_templates.id"))
    idx: Mapped[int]
    item_text: Mapped[str] = mapped_column(String(500))
    is_required: Mapped[bool] = mapped_column(default=True)
    requires_photo: Mapped[bool] = mapped_column(default=False)
    requires_measurement: Mapped[bool] = mapped_column(default=False)
    measurement_unit: Mapped[Optional[str]] = mapped_column(String(50))

class ServiceChecklist(Base):
    __tablename__ = "service_checklists"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_order_id: Mapped[int] = mapped_column(ForeignKey("service_orders.id"))
    template_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("checklist_template_items.id"))
    item_text: Mapped[str] = mapped_column(String(500))
    is_completed: Mapped[bool] = mapped_column(default=False)
    completed_at: Mapped[Optional[datetime]]
    notes: Mapped[Optional[str]] = mapped_column(Text)
    measurement_value: Mapped[Optional[str]] = mapped_column(String(100))
    photo_id: Mapped[Optional[int]]
```

### 5. Service Photos & Attachments
```python
class ServicePhoto(Base):
    __tablename__ = "service_photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_order_id: Mapped[int] = mapped_column(ForeignKey("service_orders.id"))
    photo_type: Mapped[str] = mapped_column(String(50))  # before, after, issue, equipment
    file_path: Mapped[str] = mapped_column(String(500))
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(500))
    caption: Mapped[Optional[str]] = mapped_column(String(255))
    latitude: Mapped[Optional[Decimal]]
    longitude: Mapped[Optional[Decimal]]
    captured_at: Mapped[datetime]
    uploaded_at: Mapped[datetime]
```

### 6. Service Time Entries
```python
class ServiceTimeEntry(Base):
    __tablename__ = "service_time_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_order_id: Mapped[int] = mapped_column(ForeignKey("service_orders.id"))
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))

    entry_type: Mapped[str] = mapped_column(String(50))  # travel, work, break
    start_time: Mapped[datetime]
    end_time: Mapped[Optional[datetime]]
    duration_hours: Mapped[Optional[Decimal]]
    notes: Mapped[Optional[str]] = mapped_column(Text)
    is_billable: Mapped[bool] = mapped_column(default=True)
```

### 7. Inventory Items Used
```python
class ServiceOrderItem(Base):
    __tablename__ = "service_order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_order_id: Mapped[int] = mapped_column(ForeignKey("service_orders.id"))
    item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("stock_items.id"))
    item_name: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[Decimal]
    unit: Mapped[str] = mapped_column(String(50))
    unit_cost: Mapped[Decimal]
    total_cost: Mapped[Decimal]
    serial_numbers: Mapped[Optional[str]] = mapped_column(Text)  # JSON array
    is_returned: Mapped[bool] = mapped_column(default=False)
```

### 8. Service Zones/Areas
```python
class ServiceZone(Base):
    __tablename__ = "service_zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    code: Mapped[str] = mapped_column(String(50), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Geographic bounds (for routing)
    boundary_geojson: Mapped[Optional[str]] = mapped_column(Text)
    center_latitude: Mapped[Optional[Decimal]]
    center_longitude: Mapped[Optional[Decimal]]

    # Assignment
    default_team_id: Mapped[Optional[int]] = mapped_column(ForeignKey("field_teams.id"))

    is_active: Mapped[bool] = mapped_column(default=True)
```

---

## API Endpoints

### Service Orders API (`app/api/field_service/orders.py`)
```
GET    /api/field-service/dashboard         - Dashboard metrics
GET    /api/field-service/orders            - List orders (filterable)
GET    /api/field-service/orders/{id}       - Order detail
POST   /api/field-service/orders            - Create order
PATCH  /api/field-service/orders/{id}       - Update order
DELETE /api/field-service/orders/{id}       - Cancel order

POST   /api/field-service/orders/{id}/dispatch    - Dispatch to technician
POST   /api/field-service/orders/{id}/start       - Start work
POST   /api/field-service/orders/{id}/complete    - Complete order
POST   /api/field-service/orders/{id}/reschedule  - Reschedule

POST   /api/field-service/orders/{id}/checklist/{item_id}/complete
POST   /api/field-service/orders/{id}/photos      - Upload photo
POST   /api/field-service/orders/{id}/items       - Add inventory item
POST   /api/field-service/orders/{id}/time-entry  - Log time
POST   /api/field-service/orders/{id}/signature   - Capture signature
```

### Teams & Scheduling API (`app/api/field_service/scheduling.py`)
```
GET    /api/field-service/teams                   - List teams
GET    /api/field-service/teams/{id}              - Team detail
POST   /api/field-service/teams                   - Create team
PATCH  /api/field-service/teams/{id}              - Update team

GET    /api/field-service/technicians             - List available technicians
GET    /api/field-service/technicians/{id}/schedule - Technician schedule
GET    /api/field-service/technicians/{id}/availability - Check availability

GET    /api/field-service/schedule/calendar       - Calendar view
GET    /api/field-service/schedule/optimize       - Route optimization suggestions
POST   /api/field-service/schedule/bulk-assign    - Bulk assign orders
```

### Configuration API (`app/api/field_service/config.py`)
```
GET    /api/field-service/zones                   - List service zones
POST   /api/field-service/zones                   - Create zone
PATCH  /api/field-service/zones/{id}              - Update zone

GET    /api/field-service/checklists              - List checklist templates
POST   /api/field-service/checklists              - Create template
PATCH  /api/field-service/checklists/{id}         - Update template

GET    /api/field-service/skills                  - List skill types
```

### Analytics API (`app/api/field_service/analytics.py`)
```
GET    /api/field-service/analytics/performance   - Team/technician performance
GET    /api/field-service/analytics/completion    - Completion rates, SLA
GET    /api/field-service/analytics/costs         - Cost analysis
GET    /api/field-service/analytics/utilization   - Resource utilization
```

---

## Frontend Structure

```
frontend/app/field-service/
├── page.tsx                    # Dashboard (overview, today's orders, map)
├── layout.tsx                  # Sidebar navigation
├── orders/
│   ├── page.tsx               # Orders list with filters
│   ├── new/page.tsx           # Create service order
│   ├── [id]/page.tsx          # Order detail
│   └── [id]/edit/page.tsx     # Edit order
├── schedule/
│   ├── page.tsx               # Calendar view
│   ├── dispatch/page.tsx      # Dispatch board
│   └── optimize/page.tsx      # Route optimization
├── teams/
│   ├── page.tsx               # Teams list
│   ├── new/page.tsx           # Create team
│   └── [id]/page.tsx          # Team detail
├── technicians/
│   ├── page.tsx               # Technician list & skills
│   └── [id]/page.tsx          # Technician profile & schedule
├── zones/
│   └── page.tsx               # Service zones management
├── analytics/
│   └── page.tsx               # Performance analytics
└── settings/
    └── page.tsx               # Checklists, defaults, etc.
```

---

## Key Features

### 1. Service Order Management
- Create orders from Projects, Tasks, or Support Tickets
- Auto-populate customer and location data
- Order lifecycle: Draft → Scheduled → Dispatched → En Route → On Site → Completed
- Checklist completion with photo requirements
- Customer signature capture
- Time tracking per technician

### 2. Dispatch Board
- Visual board showing orders by status
- Drag-and-drop assignment
- Quick view of technician availability
- Today's workload per technician
- Urgent/overdue highlighting

### 3. Calendar & Scheduling
- Day/Week/Month calendar views
- Color-coded by order type and status
- Technician availability overlay
- Schedule conflicts detection
- Drag to reschedule

### 4. Route Optimization
- Map view of day's orders
- Suggested routing by zone
- Distance/time estimates
- Traffic consideration (via external API)
- Manual route adjustment

### 5. Mobile-First Field App Considerations
- Offline capability for checklists
- GPS location tracking
- Photo capture with geotag
- Signature capture
- Push notifications for new assignments

### 6. Integration Points
- **Projects**: Create installation orders from project tasks
- **Support**: Create repair orders from tickets
- **Inventory**: Track parts used, update stock
- **HR**: Technician skills, time off
- **Accounting**: Job costing, billing

### 7. Analytics & KPIs
- First-time fix rate
- Average response time
- Completion rate
- Technician utilization
- Cost per service call
- Customer satisfaction scores
- SLA compliance

---

## Database Migrations

```
alembic/versions/
├── 20251216_add_field_service_core.py      # Core tables
├── 20251216_add_field_teams.py             # Teams & members
├── 20251216_add_service_zones.py           # Zones & coverage
├── 20251216_add_checklists.py              # Checklist templates
├── 20251216_add_field_service_indexes.py   # Performance indexes
```

---

## RBAC Scopes

```python
# Add to app/auth.py DEFAULT_SCOPES

"field-service:read"     # View orders, teams, schedule
"field-service:write"    # Create/edit orders
"field-service:dispatch" # Assign orders to technicians
"field-service:admin"    # Manage teams, zones, templates
"field-service:mobile"   # Mobile app access (checklist, photos)
```

---

## Implementation Phases

### Phase 1: Core Infrastructure
- Service Order model and CRUD API
- Basic dashboard and order list UI
- Order detail page with status updates
- Link to existing Projects/Tickets

### Phase 2: Teams & Assignment
- Field Teams model
- Technician skills tracking
- Dispatch board UI
- Basic assignment workflow

### Phase 3: Scheduling & Calendar
- Calendar view
- Schedule management
- Availability checking
- Conflict detection

### Phase 4: Field Operations
- Checklist system
- Photo uploads
- Time tracking
- Signature capture
- Inventory items used

### Phase 5: Analytics & Optimization
- Performance dashboards
- Route optimization
- Utilization reports
- Cost analysis

### Phase 6: Mobile App (Future)
- React Native or PWA
- Offline support
- GPS tracking
- Push notifications

---

## ERPNext Integration

If syncing with ERPNext Field Service:
- Map to ERPNext Maintenance Visit / Work Order
- Sync technician assignments
- Pull/push checklist results
- Sync inventory consumption
