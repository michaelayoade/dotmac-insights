# UI Scheme by Module

This document defines the UI design scheme for each module in Dotmac Insights, following the established design system.

---

## Design System Foundation

### Color Accents by Module

| Module | Primary Accent | Secondary | Status |
|--------|---------------|-----------|--------|
| **CRM** | `teal` | `purple` | Lead lifecycle colors |
| **Support** | `coral` | `amber` | Priority-based |
| **Field Service** | `indigo` | `emerald` | Status-based |
| **Sales** | `emerald` | `teal` | Revenue focus |
| **Books/Accounting** | `blue` | `slate` | Financial precision |
| **HR** | `purple` | `rose` | People-focused |
| **Projects** | `amber` | `cyan` | Progress tracking |
| **Inbox** | `cyan` | `teal` | Communication |
| **Inventory** | `emerald` | `amber` | Stock levels |
| **Performance** | `indigo` | `emerald` | Achievement |
| **Expenses** | `rose` | `amber` | Cost tracking |
| **Assets** | `slate` | `emerald` | Asset health |

### Standard Variants

- `success` - Completed, Paid, Active, Won
- `warning` - Pending, Due Soon, At Risk
- `danger` - Overdue, Failed, Churned, Lost
- `info` - In Progress, Scheduled, New

---

## 1. CRM Module

### Accent: `teal` | Icon: `Users`

### Navigation Structure
```
CRM
├── Dashboard (overview)
├── Contacts
│   ├── All Contacts
│   ├── People
│   ├── Organizations
│   └── Import/Export
├── Lifecycle
│   ├── Leads
│   ├── Prospects
│   ├── Customers
│   └── Churned
├── Pipeline
│   ├── Kanban Board
│   ├── Opportunities
│   └── Forecasting
├── Activities
│   ├── Calls
│   ├── Meetings
│   ├── Tasks
│   └── Notes
├── Analytics
│   ├── Conversion Funnel
│   ├── Lead Sources
│   └── Rep Performance
└── Tools
    ├── Segments
    ├── Duplicate Detection
    └── Data Quality
```

### Page Schemes

#### Dashboard
```
┌─────────────────────────────────────────────────────────────┐
│ PageHeader: "CRM" | Icon: Users | Actions: [+ Contact]     │
├─────────────────────────────────────────────────────────────┤
│ StatGrid (4 cols):                                          │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│ │ Total    │ │ New This │ │ Pipeline │ │ Conversion│        │
│ │ Contacts │ │ Month    │ │ Value    │ │ Rate      │        │
│ │ [teal]   │ │ [emerald]│ │ [purple] │ │ [indigo]  │        │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
├─────────────────────────────────────────────────────────────┤
│ 2-Column Layout:                                            │
│ ┌─────────────────────┐ ┌─────────────────────────────────┐│
│ │ Lead Funnel Chart   │ │ Recent Activities Timeline      ││
│ │ (Sankey/Funnel)     │ │ [Call] [Meeting] [Task] [Note]  ││
│ └─────────────────────┘ └─────────────────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│ DataTable: "Hot Leads" - Score, Name, Company, Last Touch  │
└─────────────────────────────────────────────────────────────┘
```

#### Pipeline (Kanban)
```
┌─────────────────────────────────────────────────────────────┐
│ PageHeader: "Pipeline" | Filter: [Stage] [Owner] [Value]   │
├─────────────────────────────────────────────────────────────┤
│ Kanban Columns (horizontal scroll):                         │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐│
│ │QUALIFIED│ │PROPOSAL │ │NEGOTIAT.│ │CLOSED   │ │LOST     ││
│ │ $50K    │ │ $120K   │ │ $80K    │ │ $200K   │ │ $30K    ││
│ ├─────────┤ ├─────────┤ ├─────────┤ ├─────────┤ ├─────────┤│
│ │┌───────┐│ │┌───────┐│ │┌───────┐│ │┌───────┐│ │┌───────┐││
│ ││ Card  ││ ││ Card  ││ ││ Card  ││ ││ Card  ││ ││ Card  │││
│ │└───────┘│ │└───────┘│ │└───────┘│ │└───────┘│ │└───────┘││
│ │┌───────┐│ │         │ │         │ │         │ │         ││
│ ││ Card  ││ │         │ │         │ │         │ │         ││
│ │└───────┘│ │         │ │         │ │         │ │         ││
│ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘│
└─────────────────────────────────────────────────────────────┘

Opportunity Card:
┌─────────────────────────────┐
│ [Company Logo] Company Name │
│ Deal: $25,000               │
│ ────────────────────────    │
│ Contact: John Doe           │
│ Close Date: Jan 15          │
│ [avatar] Owner   [75%] Prob │
└─────────────────────────────┘
```

#### Contact Detail
```
┌─────────────────────────────────────────────────────────────┐
│ PageHeader: "John Doe" | Badge: [Customer] | Actions: [Edit]│
├─────────────────────────────────────────────────────────────┤
│ 3-Column Layout:                                            │
│ ┌───────────────┐ ┌─────────────────────────────────────────┤
│ │ Contact Card  │ │ Tabs: [Activity] [Deals] [Tickets] [...]│
│ │ ─────────────│ │ ┌───────────────────────────────────────┤│
│ │ [Avatar]      │ │ │ Timeline View                        ││
│ │ Email         │ │ │ ┌─────────────────────────────────┐  ││
│ │ Phone         │ │ │ │ [Call] Discussed renewal - 2h   │  ││
│ │ Company       │ │ │ └─────────────────────────────────┘  ││
│ │ Lifecycle:    │ │ │ ┌─────────────────────────────────┐  ││
│ │ [Customer]    │ │ │ │ [Email] Sent proposal - 1d      │  ││
│ │ ─────────────│ │ │ └─────────────────────────────────┘  ││
│ │ Tags          │ │ │ ┌─────────────────────────────────┐  ││
│ │ [VIP] [ISP]   │ │ │ │ [Meeting] Initial call - 3d     │  ││
│ │ ─────────────│ │ │ └─────────────────────────────────┘  ││
│ │ Custom Fields │ │ └───────────────────────────────────────┤│
│ └───────────────┘ └─────────────────────────────────────────┤
└─────────────────────────────────────────────────────────────┘
```

### Key Components
- `ContactCard` - Profile display with lifecycle badge
- `OpportunityCard` - Kanban card with deal info
- `ActivityTimeline` - Chronological activity feed
- `LeadScoreBadge` - Numeric score with color gradient
- `LifecycleIndicator` - Visual pipeline position

---

## 2. Support/Ticketing Module

### Accent: `coral` | Icon: `Headphones`

### Navigation Structure
```
Support
├── Dashboard
├── Tickets
│   ├── All Tickets
│   ├── My Queue
│   ├── Unassigned
│   └── Escalated
├── Agents
│   ├── Agent List
│   ├── Teams
│   └── Workload
├── Knowledge Base
│   ├── Articles
│   ├── Categories
│   └── Analytics
├── Automation
│   ├── Rules
│   ├── Triggers
│   └── Macros
├── SLA
│   ├── Policies
│   └── Breaches
├── CSAT
│   └── Surveys
└── Analytics
    ├── Overview
    ├── Agent Performance
    └── Resolution Times
```

### Page Schemes

#### Dashboard
```
┌─────────────────────────────────────────────────────────────┐
│ PageHeader: "Support Dashboard" | Actions: [+ Ticket]       │
├─────────────────────────────────────────────────────────────┤
│ Alert Banner (if SLA breaches):                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ⚠️ 3 tickets breaching SLA | [View Now]                  │ │
│ └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ StatGrid (5 cols):                                          │
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐     │
│ │ Open   │ │ Pending│ │ Today  │ │ Avg    │ │ CSAT   │     │
│ │ 47     │ │ 12     │ │ +23    │ │ 2.4h   │ │ 4.2★   │     │
│ │[coral] │ │[amber] │ │[teal]  │ │[info]  │ │[emerald]│    │
│ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘     │
├─────────────────────────────────────────────────────────────┤
│ 2-Column:                                                   │
│ ┌──────────────────────┐ ┌────────────────────────────────┐│
│ │ Tickets by Priority  │ │ Resolution Time Trend          ││
│ │ [Donut Chart]        │ │ [Line Chart - 7 days]          ││
│ │ ● Critical: 5        │ │                                ││
│ │ ● High: 12           │ │                                ││
│ │ ● Medium: 20         │ │                                ││
│ │ ● Low: 10            │ │                                ││
│ └──────────────────────┘ └────────────────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│ DataTable: "My Queue" - Priority indicator, Subject, SLA   │
└─────────────────────────────────────────────────────────────┘
```

#### Ticket Detail
```
┌─────────────────────────────────────────────────────────────┐
│ PageHeader: "#1234 Cannot login" | [Critical] [SLA: 1h 23m] │
│ Actions: [Assign] [Escalate] [Resolve] [...]                │
├─────────────────────────────────────────────────────────────┤
│ 2-Column Layout (70/30):                                    │
│ ┌───────────────────────────────────┐ ┌───────────────────┐│
│ │ Conversation Thread               │ │ Ticket Properties ││
│ │ ┌───────────────────────────────┐│ │ ─────────────────││
│ │ │ [Customer Avatar]             ││ │ Status: [Open]   ││
│ │ │ John Doe - 2 hours ago        ││ │ Priority: [High] ││
│ │ │ ─────────────────────────────││ │ Type: [Bug]      ││
│ │ │ I can't login to my account  ││ │ ─────────────────││
│ │ │ since this morning...        ││ │ Assignee:        ││
│ │ └───────────────────────────────┘│ │ [avatar] Sarah   ││
│ │ ┌───────────────────────────────┐│ │ ─────────────────││
│ │ │ [Agent Avatar]                ││ │ SLA Policy:      ││
│ │ │ Sarah - 1 hour ago            ││ │ Premium Support  ││
│ │ │ [Internal Note]               ││ │ Response: ✓      ││
│ │ │ Checking auth logs...         ││ │ Resolution: 1h   ││
│ │ └───────────────────────────────┘│ │ ─────────────────││
│ ├───────────────────────────────────┤ │ Contact:         ││
│ │ Reply Box                        │ │ [Link to CRM]    ││
│ │ ┌───────────────────────────────┐│ │ ─────────────────││
│ │ │ [Rich Text Editor]            ││ │ Related:         ││
│ │ │                               ││ │ • Ticket #1230   ││
│ │ │ [Attach] [Canned] [Internal]  ││ │ • FSO #456       ││
│ │ └───────────────────────────────┘│ └───────────────────┘│
│ └───────────────────────────────────┘                      │
└─────────────────────────────────────────────────────────────┘
```

### Key Components
- `TicketCard` - Compact ticket preview with priority stripe
- `SLATimer` - Countdown with color transition (green→amber→red)
- `ConversationThread` - Message bubbles with internal notes
- `PriorityBadge` - Critical/High/Medium/Low with icons
- `AgentAvatar` - Online status indicator
- `CannedResponsePicker` - Quick reply insertion

---

## 3. Field Service Module

### Accent: `indigo` | Icon: `Truck`

### Navigation Structure
```
Field Service
├── Dashboard
├── Orders
│   ├── All Orders
│   ├── Scheduled
│   ├── In Progress
│   └── Completed
├── Schedule
│   ├── Calendar View
│   ├── Map View
│   └── Timeline
├── Teams
│   ├── Technicians
│   ├── Team Groups
│   └── Availability
└── Analytics
    ├── Completion Rates
    ├── Response Times
    └── Technician Performance
```

### Page Schemes

#### Dashboard
```
┌─────────────────────────────────────────────────────────────┐
│ PageHeader: "Field Service" | Actions: [+ Order] [Dispatch] │
├─────────────────────────────────────────────────────────────┤
│ StatGrid (4 cols):                                          │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│ │ Today's  │ │ In       │ │ Completed│ │ Avg Time │        │
│ │ Orders   │ │ Progress │ │ Today    │ │ On-Site  │        │
│ │ 24       │ │ 8        │ │ 14       │ │ 45 min   │        │
│ │[indigo]  │ │[amber]   │ │[emerald] │ │[teal]    │        │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
├─────────────────────────────────────────────────────────────┤
│ 2-Column (60/40):                                           │
│ ┌───────────────────────────┐ ┌───────────────────────────┐│
│ │ Today's Schedule          │ │ Map View                  ││
│ │ ┌───────────────────────┐│ │ ┌───────────────────────┐ ││
│ │ │ 08:00 │ FSO-001      ││ │ │ [Interactive Map]     │ ││
│ │ │       │ Install       ││ │ │  📍 Active techs      │ ││
│ │ │       │ [Tech: John]  ││ │ │  📍 Pending orders    │ ││
│ │ ├───────────────────────┤│ │ │                       │ ││
│ │ │ 09:30 │ FSO-002      ││ │ │                       │ ││
│ │ │       │ Repair        ││ │ └───────────────────────┘ ││
│ │ └───────────────────────┘│ └───────────────────────────┘│
│ └───────────────────────────┘                              │
├─────────────────────────────────────────────────────────────┤
│ Technician Status Cards:                                    │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│ │[avatar]  │ │[avatar]  │ │[avatar]  │ │[avatar]  │        │
│ │ John     │ │ Sarah    │ │ Mike     │ │ Lisa     │        │
│ │ 🟢 Active│ │ 🟡 Travel│ │ 🔵 Break │ │ 🟢 Active│        │
│ │ FSO-001  │ │ → FSO-003│ │          │ │ FSO-005  │        │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
└─────────────────────────────────────────────────────────────┘
```

#### Schedule View (Calendar)
```
┌─────────────────────────────────────────────────────────────┐
│ PageHeader: "Schedule" | View: [Day] [Week] [Month] [Map]   │
│ Filter: [Team ▼] [Tech ▼] [Type ▼]                          │
├─────────────────────────────────────────────────────────────┤
│ Calendar Grid (Week View):                                  │
│         │ Mon 15  │ Tue 16  │ Wed 17  │ Thu 18  │ Fri 19  │
│ ────────┼─────────┼─────────┼─────────┼─────────┼─────────│
│ John    │░░░░░░░░░│         │░░░░░    │         │░░░░░░░░░│
│         │ Install │         │ Repair  │         │ Install │
│ ────────┼─────────┼─────────┼─────────┼─────────┼─────────│
│ Sarah   │         │░░░░░░░░░│░░░░░░░░░│         │         │
│         │         │ Maint.  │ Install │         │         │
│ ────────┼─────────┼─────────┼─────────┼─────────┼─────────│
│ Mike    │░░░░░    │░░░░░    │         │░░░░░░░░░│░░░░░    │
│         │ Survey  │ Survey  │         │ Install │ Repair  │
└─────────────────────────────────────────────────────────────┘
```

#### Order Detail
```
┌─────────────────────────────────────────────────────────────┐
│ PageHeader: "FSO-001234" | [Installation] [In Progress]     │
│ Actions: [Assign] [Reschedule] [Complete] [Cancel]          │
├─────────────────────────────────────────────────────────────┤
│ WorkflowIndicator:                                          │
│ [Created] ─── [Scheduled] ─── [Dispatched] ─── [Completed]  │
│     ✓             ✓              ●                          │
├─────────────────────────────────────────────────────────────┤
│ 2-Column Layout:                                            │
│ ┌─────────────────────────────┐ ┌─────────────────────────┐│
│ │ Order Details               │ │ Technician              ││
│ │ ─────────────────────────── │ │ ┌───────────────────┐   ││
│ │ Customer: Acme Corp         │ │ │ [Photo] John Doe  │   ││
│ │ Contact: Jane Smith         │ │ │ ☎ 0712 345 678    │   ││
│ │ Phone: 0722 123 456         │ │ │ 🚗 En route       │   ││
│ │ ─────────────────────────── │ │ │ ETA: 15 min       │   ││
│ │ Address:                    │ │ └───────────────────┘   ││
│ │ 123 Moi Avenue, Nairobi     │ │                         ││
│ │ [View on Map]               │ ├─────────────────────────┤│
│ │ ─────────────────────────── │ │ Equipment Required      ││
│ │ Scheduled: Jan 15, 09:00    │ │ ☑ Router Model X        ││
│ │ Duration: 2 hours           │ │ ☑ Cable (50m)           ││
│ │ Priority: [High]            │ │ ☐ Mounting Kit          ││
│ └─────────────────────────────┘ └─────────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│ Activity Log:                                               │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ 09:15 │ John checked in at location                     ││
│ │ 09:00 │ John en route (ETA 15 min)                      ││
│ │ 08:45 │ Order dispatched to John                        ││
│ │ 08:30 │ Order scheduled by Admin                        ││
│ └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### Key Components
- `OrderCard` - Compact order preview with type icon
- `TechnicianCard` - Status indicator with current assignment
- `ScheduleCalendar` - Drag-drop calendar with resource rows
- `MapView` - Interactive map with technician/order pins
- `WorkflowStepper` - Horizontal progress indicator
- `ChecklistWidget` - Equipment/task checklist
- `ETAIndicator` - Real-time arrival estimate

---

## 4. Sales Module

### Accent: `emerald` | Icon: `TrendingUp`

### Navigation Structure
```
Sales
├── Dashboard
├── CRM
│   ├── Leads
│   ├── Opportunities
│   └── Pipeline
├── Orders
│   ├── Quotations
│   ├── Sales Orders
│   └── Deliveries
├── AR (Accounts Receivable)
│   ├── Invoices
│   ├── Payments
│   └── Credit Notes
├── Customers
│   ├── Customer List
│   └── Customer Groups
├── Analytics
│   ├── Revenue
│   ├── Trends
│   └── Forecasting
└── Settings
    ├── Territories
    ├── Sales Persons
    └── Commission Rules
```

### Page Schemes

#### Dashboard
```
┌─────────────────────────────────────────────────────────────┐
│ PageHeader: "Sales Dashboard" | Period: [This Month ▼]      │
├─────────────────────────────────────────────────────────────┤
│ Revenue Hero Card:                                          │
│ ┌─────────────────────────────────────────────────────────┐│
│ │          KES 12,450,000                                 ││
│ │          ▲ 15.2% vs last month                          ││
│ │  ████████████████████████░░░░░░░░  78% of target        ││
│ └─────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│ StatGrid (4 cols):                                          │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│ │ Orders   │ │ Invoiced │ │ Collected│ │ Outstand.│        │
│ │ 156      │ │ 8.2M     │ │ 6.8M     │ │ 4.1M     │        │
│ │[teal]    │ │[emerald] │ │[emerald] │ │[amber]   │        │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
├─────────────────────────────────────────────────────────────┤
│ 2-Column:                                                   │
│ ┌──────────────────────────┐ ┌────────────────────────────┐│
│ │ Revenue Trend            │ │ Top Products               ││
│ │ [Area Chart - 12 months] │ │ 1. Fiber 50Mbps   KES 2.1M ││
│ │                          │ │ 2. Fiber 100Mbps  KES 1.8M ││
│ │                          │ │ 3. Enterprise     KES 1.2M ││
│ └──────────────────────────┘ └────────────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│ DataTable: "Recent Invoices" - Customer, Amount, Status    │
└─────────────────────────────────────────────────────────────┘
```

#### Invoice List
```
┌─────────────────────────────────────────────────────────────┐
│ PageHeader: "Invoices" | Actions: [+ Invoice] [Export]      │
├─────────────────────────────────────────────────────────────┤
│ Summary Cards:                                              │
│ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐│
│ │ Total      │ │ Paid       │ │ Unpaid     │ │ Overdue    ││
│ │ KES 15.2M  │ │ KES 10.1M  │ │ KES 3.8M   │ │ KES 1.3M   ││
│ │ 234 inv    │ │ 189 inv    │ │ 32 inv     │ │ 13 inv     ││
│ └────────────┘ └────────────┘ └────────────┘ └────────────┘│
├─────────────────────────────────────────────────────────────┤
│ FilterCard: [Status ▼] [Date Range] [Customer] [Search]     │
├─────────────────────────────────────────────────────────────┤
│ DataTable:                                                  │
│ ┌───────┬────────────┬───────────┬──────────┬─────────────┐│
│ │ Inv # │ Customer   │ Amount    │ Due Date │ Status      ││
│ ├───────┼────────────┼───────────┼──────────┼─────────────┤│
│ │ 1234  │ Acme Corp  │ KES 45,000│ Jan 15   │ [Paid] ✓    ││
│ │ 1235  │ Tech Ltd   │ KES 78,000│ Jan 20   │ [Unpaid]    ││
│ │ 1236  │ Mega Inc   │ KES 23,000│ Jan 10   │ [Overdue] ! ││
│ └───────┴────────────┴───────────┴──────────┴─────────────┘│
│ Pagination: [< 1 2 3 4 5 >] | Showing 1-20 of 234          │
└─────────────────────────────────────────────────────────────┘
```

### Key Components
- `RevenueCard` - Large hero stat with progress bar
- `InvoiceRow` - Table row with status pill and actions
- `PaymentBadge` - Paid/Unpaid/Overdue/Partial
- `CustomerSelect` - Searchable customer dropdown
- `AmountDisplay` - Currency-formatted with trend indicator
- `AgingChart` - AR aging visualization

---

## 5. Books/Accounting Module

### Accent: `blue` | Icon: `BookOpen`

### Navigation Structure
```
Books
├── Dashboard
├── Accounting
│   ├── Chart of Accounts
│   ├── Journal Entries
│   ├── General Ledger
│   └── Controls
├── AR (Accounts Receivable)
│   ├── Invoices
│   ├── Payments
│   └── Credit Notes
├── AP (Accounts Payable)
│   ├── Bills
│   ├── Payments
│   └── Debit Notes
├── Banking
│   ├── Bank Accounts
│   ├── Transactions
│   ├── Reconciliation
│   └── Gateway
├── Reports
│   ├── Trial Balance
│   ├── Balance Sheet
│   ├── Income Statement
│   ├── Cash Flow
│   └── Equity Statement
├── Tax
│   ├── Tax Rules
│   └── Tax Reports
└── Settings
```

### Page Schemes

#### Dashboard
```
┌─────────────────────────────────────────────────────────────┐
│ PageHeader: "Books" | Period: [Q4 2024 ▼] | [Close Period]  │
├─────────────────────────────────────────────────────────────┤
│ Financial Summary Cards:                                    │
│ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐│
│ │ Assets          │ │ Liabilities     │ │ Equity          ││
│ │ KES 45,230,000  │ │ KES 12,450,000  │ │ KES 32,780,000  ││
│ │ ▲ 5.2%          │ │ ▼ 2.1%          │ │ ▲ 8.3%          ││
│ └─────────────────┘ └─────────────────┘ └─────────────────┘│
├─────────────────────────────────────────────────────────────┤
│ 2-Column:                                                   │
│ ┌──────────────────────────┐ ┌────────────────────────────┐│
│ │ Income vs Expenses       │ │ Cash Position              ││
│ │ [Stacked Bar Chart]      │ │ [Line Chart]               ││
│ │                          │ │ Current: KES 8.2M          ││
│ │ Revenue:  KES 15.2M      │ │                            ││
│ │ Expenses: KES 11.8M      │ │                            ││
│ │ Net:      KES 3.4M       │ │                            ││
│ └──────────────────────────┘ └────────────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│ Quick Actions:                                              │
│ [+ Journal Entry] [Reconcile] [Run Reports] [Period Close]  │
├─────────────────────────────────────────────────────────────┤
│ Recent Journal Entries:                                     │
│ ┌──────────┬──────────────────────────┬─────────┬─────────┐│
│ │ JE-0045  │ Salary Payment Dec 2024  │ 2.3M    │ [Posted]││
│ │ JE-0044  │ Utility Bills            │ 45,000  │ [Draft] ││
│ └──────────┴──────────────────────────┴─────────┴─────────┘│
└─────────────────────────────────────────────────────────────┘
```

#### Chart of Accounts
```
┌─────────────────────────────────────────────────────────────┐
│ PageHeader: "Chart of Accounts" | Actions: [+ Account]      │
├─────────────────────────────────────────────────────────────┤
│ Tree View with Balances:                                    │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ ▼ 1000 Assets                              KES 45,230,000││
│ │   ▼ 1100 Current Assets                    KES 12,450,000││
│ │     ├─ 1110 Cash                           KES  2,340,000││
│ │     ├─ 1120 Bank Accounts                  KES  5,670,000││
│ │     └─ 1130 Accounts Receivable            KES  4,440,000││
│ │   ▶ 1200 Fixed Assets                      KES 32,780,000││
│ │ ▼ 2000 Liabilities                         KES 12,450,000││
│ │   ▼ 2100 Current Liabilities               KES  8,230,000││
│ │     ├─ 2110 Accounts Payable               KES  3,450,000││
│ │     └─ 2120 Accrued Expenses               KES  4,780,000││
│ │ ▶ 3000 Equity                              KES 32,780,000││
│ │ ▶ 4000 Revenue                             KES 15,230,000││
│ │ ▶ 5000 Expenses                            KES 11,820,000││
│ └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

#### Journal Entry Form
```
┌─────────────────────────────────────────────────────────────┐
│ PageHeader: "New Journal Entry" | [Save Draft] [Post]       │
├─────────────────────────────────────────────────────────────┤
│ Header:                                                     │
│ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐│
│ │ Entry Date      │ │ Reference       │ │ Memo            ││
│ │ [Jan 15, 2025]  │ │ [JE-0046]       │ │ [Description...] ││
│ └─────────────────┘ └─────────────────┘ └─────────────────┘│
├─────────────────────────────────────────────────────────────┤
│ Line Items:                                                 │
│ ┌──────────────────────┬───────────┬───────────┬──────────┐│
│ │ Account              │ Debit     │ Credit    │ Memo     ││
│ ├──────────────────────┼───────────┼───────────┼──────────┤│
│ │ [1110 Cash ▼]        │ 50,000    │           │          ││
│ │ [4100 Sales Rev ▼]   │           │ 50,000    │ Invoice  ││
│ │ [+ Add Line]         │           │           │          ││
│ ├──────────────────────┼───────────┼───────────┼──────────┤│
│ │ TOTALS               │ 50,000    │ 50,000    │ ✓ Balanced│
│ └──────────────────────┴───────────┴───────────┴──────────┘│
├─────────────────────────────────────────────────────────────┤
│ Attachments: [+ Upload] | supporting_doc.pdf               │
└─────────────────────────────────────────────────────────────┘
```

### Key Components
- `AccountTree` - Hierarchical COA display
- `JournalEntryForm` - Debit/credit line editor
- `BalanceIndicator` - Debit = Credit validation
- `FinancialStatement` - Report renderer
- `ReconciliationPanel` - Bank statement matching
- `PeriodSelector` - Fiscal period dropdown

---

## 6. HR Module

### Accent: `purple` | Icon: `Users2`

### Navigation Structure
```
HR
├── Dashboard
├── Employees
│   ├── Directory
│   ├── Org Chart
│   └── Lifecycle
├── Attendance
│   ├── Time Tracking
│   ├── Shifts
│   └── Reports
├── Leave
│   ├── Requests
│   ├── Calendar
│   ├── Balances
│   └── Policies
├── Payroll
│   ├── Pay Runs
│   ├── Payslips
│   └── Statutory
├── Recruitment
│   ├── Job Postings
│   ├── Applications
│   └── Pipeline
├── Training
│   ├── Programs
│   ├── Enrollments
│   └── Certificates
├── Appraisals
│   ├── Cycles
│   └── Reviews
└── Settings
    ├── Departments
    ├── Designations
    └── Policies
```

### Page Schemes

#### Dashboard
```
┌─────────────────────────────────────────────────────────────┐
│ PageHeader: "HR Dashboard" | Actions: [+ Employee]          │
├─────────────────────────────────────────────────────────────┤
│ StatGrid (5 cols):                                          │
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐     │
│ │ Total  │ │ Present│ │ On     │ │ Open   │ │ Payroll│     │
│ │ Staff  │ │ Today  │ │ Leave  │ │ Roles  │ │ Due    │     │
│ │ 156    │ │ 142    │ │ 8      │ │ 5      │ │ Jan 25 │     │
│ │[purple]│ │[emerald]│ │[amber] │ │[teal]  │ │[coral] │     │
│ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘     │
├─────────────────────────────────────────────────────────────┤
│ 3-Column Layout:                                            │
│ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐│
│ │ Leave Requests  │ │ Birthdays       │ │ Anniversaries   ││
│ │ ───────────────│ │ ───────────────│ │ ───────────────││
│ │ [Pending: 3]    │ │ 🎂 John - Today │ │ 🎉 Sarah - 5yrs ││
│ │ • Jane - 2 days │ │ 🎂 Mike - Jan 18│ │ 🎉 Tom - 3yrs   ││
│ │ • Tom - 5 days  │ │ 🎂 Lisa - Jan 20│ │                 ││
│ │ [View All]      │ │                 │ │                 ││
│ └─────────────────┘ └─────────────────┘ └─────────────────┘│
├─────────────────────────────────────────────────────────────┤
│ Department Headcount:                                       │
│ [Horizontal Bar Chart - Departments by employee count]      │
└─────────────────────────────────────────────────────────────┘
```

#### Employee Directory
```
┌─────────────────────────────────────────────────────────────┐
│ PageHeader: "Employees" | View: [Grid] [List] [Org Chart]   │
│ Filter: [Dept ▼] [Status ▼] [Search...]                     │
├─────────────────────────────────────────────────────────────┤
│ Grid View:                                                  │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────┐│
│ │   [Photo]   │ │   [Photo]   │ │   [Photo]   │ │  [Photo] ││
│ │  John Doe   │ │  Jane Smith │ │  Mike Chen  │ │ Lisa Wu  ││
│ │  Engineer   │ │  Designer   │ │  Manager    │ │ Analyst  ││
│ │  ──────────│ │  ──────────│ │  ──────────│ │ ─────────││
│ │  Tech Dept  │ │  Design     │ │  Operations │ │ Finance  ││
│ │  📧 📱      │ │  📧 📱      │ │  📧 📱      │ │ 📧 📱    ││
│ └─────────────┘ └─────────────┘ └─────────────┘ └──────────┘│
└─────────────────────────────────────────────────────────────┘
```

#### Leave Calendar
```
┌─────────────────────────────────────────────────────────────┐
│ PageHeader: "Leave Calendar" | [+ Request] | [< Jan 2025 >] │
├─────────────────────────────────────────────────────────────┤
│ Calendar Grid (Month View):                                 │
│         │ Mon │ Tue │ Wed │ Thu │ Fri │ Sat │ Sun │         │
│ ────────┼─────┼─────┼─────┼─────┼─────┼─────┼─────│         │
│ Week 1  │  1  │  2  │  3  │  4  │  5  │  6  │  7  │         │
│         │     │░░░░░│░░░░░│░░░░░│     │     │     │         │
│         │     │Jane │Jane │Jane │     │     │     │         │
│ ────────┼─────┼─────┼─────┼─────┼─────┼─────┼─────│         │
│ Week 2  │  8  │  9  │ 10  │ 11  │ 12  │ 13  │ 14  │         │
│         │░░░░░│░░░░░│     │     │     │     │     │         │
│         │Mike │Mike │     │     │     │     │     │         │
│                                                             │
│ Legend: [Annual] [Sick] [Maternity] [Unpaid]               │
└─────────────────────────────────────────────────────────────┘
```

### Key Components
- `EmployeeCard` - Photo, name, role, department
- `OrgChart` - Interactive organizational hierarchy
- `LeaveBalanceCard` - Leave type with days remaining
- `AttendanceTimeline` - Daily check-in/out visualization
- `PayslipViewer` - PDF-style payslip display
- `RecruitmentPipeline` - Candidate funnel

---

## 7. Projects Module

### Accent: `amber` | Icon: `FolderKanban`

### Navigation Structure
```
Projects
├── Dashboard
├── Projects
│   ├── All Projects
│   ├── Active
│   ├── Completed
│   └── Templates
├── Tasks
│   ├── My Tasks
│   ├── Kanban Board
│   └── Timeline
├── Analytics
│   ├── Progress
│   ├── Resource Utilization
│   └── Profitability
└── Settings
```

### Page Schemes

#### Dashboard
```
┌─────────────────────────────────────────────────────────────┐
│ PageHeader: "Projects" | Actions: [+ Project]               │
├─────────────────────────────────────────────────────────────┤
│ StatGrid (4 cols):                                          │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│ │ Active   │ │ On Track │ │ At Risk  │ │ Overdue  │        │
│ │ Projects │ │          │ │          │ │          │        │
│ │ 12       │ │ 8        │ │ 3        │ │ 1        │        │
│ │[amber]   │ │[emerald] │ │[amber]   │ │[coral]   │        │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
├─────────────────────────────────────────────────────────────┤
│ Project Cards (Grid):                                       │
│ ┌─────────────────────────┐ ┌─────────────────────────────┐│
│ │ Website Redesign        │ │ Mobile App v2               ││
│ │ [On Track]              │ │ [At Risk]                   ││
│ │ ████████████░░░░ 75%    │ │ █████████░░░░░░░ 55%        ││
│ │ Due: Feb 15             │ │ Due: Jan 30                 ││
│ │ 👤👤👤 +2               │ │ 👤👤👤👤                    ││
│ │ Tasks: 24/32            │ │ Tasks: 18/35                ││
│ └─────────────────────────┘ └─────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

#### Project Detail
```
┌─────────────────────────────────────────────────────────────┐
│ PageHeader: "Website Redesign" | [On Track]                 │
│ Tabs: [Overview] [Tasks] [Gantt] [Files] [Activity]         │
├─────────────────────────────────────────────────────────────┤
│ Progress Bar:                                               │
│ ████████████████████████████░░░░░░░░░░  75% Complete        │
├─────────────────────────────────────────────────────────────┤
│ 2-Column Layout:                                            │
│ ┌─────────────────────────────┐ ┌─────────────────────────┐│
│ │ Details                     │ │ Team                    ││
│ │ ─────────────────────────── │ │ ┌───────────────────┐   ││
│ │ Client: Acme Corp           │ │ │ 👤 John (PM)      │   ││
│ │ Start: Jan 1, 2025          │ │ │ 👤 Sarah (Dev)    │   ││
│ │ Due: Feb 15, 2025           │ │ │ 👤 Mike (Design)  │   ││
│ │ Budget: KES 500,000         │ │ └───────────────────┘   ││
│ │ Spent: KES 280,000          │ │                         ││
│ └─────────────────────────────┘ └─────────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│ Task Board (Kanban):                                        │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐            │
│ │ To Do   │ │ In Prog │ │ Review  │ │ Done    │            │
│ │ (8)     │ │ (5)     │ │ (3)     │ │ (16)    │            │
│ ├─────────┤ ├─────────┤ ├─────────┤ ├─────────┤            │
│ │ Task 1  │ │ Task 9  │ │ Task 14 │ │ Task 17 │            │
│ │ Task 2  │ │ Task 10 │ │         │ │ Task 18 │            │
│ └─────────┘ └─────────┘ └─────────┘ └─────────┘            │
└─────────────────────────────────────────────────────────────┘
```

#### Gantt View
```
┌─────────────────────────────────────────────────────────────┐
│ PageHeader: "Gantt Chart" | View: [Day] [Week] [Month]      │
├─────────────────────────────────────────────────────────────┤
│ Gantt Timeline:                                             │
│                    │ Jan 1  │ Jan 8  │ Jan 15 │ Jan 22 │    │
│ ───────────────────┼────────┼────────┼────────┼────────│    │
│ ▼ Phase 1: Design  │████████████████ │        │        │    │
│   └ Wireframes     │████████│        │        │        │    │
│   └ Mockups        │        │████████│        │        │    │
│ ▼ Phase 2: Dev     │        │        │████████████████ │    │
│   └ Frontend       │        │        │████████│        │    │
│   └ Backend        │        │        │████████████████ │    │
│ ▼ Phase 3: Test    │        │        │        │████████│    │
└─────────────────────────────────────────────────────────────┘
```

### Key Components
- `ProjectCard` - Progress bar, team avatars, due date
- `TaskKanban` - Drag-drop task board
- `GanttChart` - Interactive timeline with dependencies
- `ProgressRing` - Circular progress indicator
- `MilestoneMarker` - Diamond markers on timeline
- `ResourceChart` - Team utilization bars

---

## 8. Inbox Module

### Accent: `cyan` | Icon: `MessageSquare`

### Navigation Structure
```
Inbox
├── Conversations
│   ├── Unassigned
│   ├── Assigned to Me
│   └── All
├── Contacts
├── Channels
│   ├── WhatsApp
│   ├── Email
│   ├── SMS
│   └── Web Chat
├── Routing
│   ├── Rules
│   └── Teams
├── Analytics
└── Settings
```

### Page Schemes

#### Inbox View (Split Panel)
```
┌─────────────────────────────────────────────────────────────┐
│ PageHeader: "Inbox" | Unread: 12 | [All] [Mine] [Unassigned]│
├──────────────────────┬──────────────────────────────────────┤
│ Conversation List    │ Conversation Detail                  │
│ ┌──────────────────┐ │ ┌──────────────────────────────────┐│
│ │ 🟢 John Doe      │◀│ │ John Doe                         ││
│ │ Hi, I need help  │ │ │ [WhatsApp] [Customer] [VIP]      ││
│ │ 2 min ago        │ │ ├──────────────────────────────────┤│
│ ├──────────────────┤ │ │                                  ││
│ │    Jane Smith    │ │ │ [John] Hi, I need help with my   ││
│ │ Thanks for...    │ │ │ internet connection              ││
│ │ 1 hour ago       │ │ │                      2:30 PM     ││
│ ├──────────────────┤ │ │                                  ││
│ │    Mike Chen     │ │ │ [You] Hi John! I'd be happy to   ││
│ │ When will the... │ │ │ help. Can you describe the issue?││
│ │ 3 hours ago      │ │ │                      2:32 PM     ││
│ ├──────────────────┤ │ │                                  ││
│ │    Lisa Wang     │ │ │ [John] The connection keeps      ││
│ │ Order #12345     │ │ │ dropping every few minutes       ││
│ │ Yesterday        │ │ │                      2:33 PM     ││
│ └──────────────────┘ │ ├──────────────────────────────────┤│
│                      │ │ [Message Input]                  ││
│ Filter: [Channel ▼]  │ │ [Attach] [Canned] [Send]         ││
│         [Status ▼]   │ └──────────────────────────────────┘│
├──────────────────────┼──────────────────────────────────────┤
│                      │ Contact Sidebar:                    │
│                      │ ┌──────────────────────────────────┐│
│                      │ │ 👤 John Doe                      ││
│                      │ │ 📧 john@example.com              ││
│                      │ │ 📱 +254 722 123 456              ││
│                      │ │ ──────────────────────           ││
│                      │ │ Prev Conversations: 3            ││
│                      │ │ Open Tickets: 1                  ││
│                      │ │ [View in CRM]                    ││
│                      │ └──────────────────────────────────┘│
└──────────────────────┴──────────────────────────────────────┘
```

### Key Components
- `ConversationList` - Sidebar with unread indicators
- `MessageBubble` - Chat-style message display
- `ChannelBadge` - WhatsApp/Email/SMS/Chat icons
- `ContactSidebar` - Customer context panel
- `QuickReplyPicker` - Canned response selector
- `TypingIndicator` - Real-time typing status

---

## 9. Inventory Module

### Accent: `emerald` | Icon: `Package`

### Navigation Structure
```
Inventory
├── Dashboard
├── Items
│   ├── Item List
│   ├── Categories
│   └── Variants
├── Stock
│   ├── Stock Ledger
│   ├── Stock Entries
│   ├── Transfers
│   └── Adjustments
├── Warehouses
│   ├── Locations
│   └── Bins
├── Receiving
│   ├── Purchase Receipts
│   └── Landed Cost
├── Issuing
│   └── Sales Issues
├── Serial/Batch
│   ├── Serial Numbers
│   └── Batches
├── Reports
│   ├── Valuation
│   ├── Reorder
│   └── Movement
└── Settings
```

### Page Schemes

#### Dashboard
```
┌─────────────────────────────────────────────────────────────┐
│ PageHeader: "Inventory" | Actions: [+ Item] [Stock Entry]   │
├─────────────────────────────────────────────────────────────┤
│ StatGrid (4 cols):                                          │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│ │ Total    │ │ Total    │ │ Low      │ │ Out of   │        │
│ │ Items    │ │ Value    │ │ Stock    │ │ Stock    │        │
│ │ 1,234    │ │ KES 8.5M │ │ 23       │ │ 5        │        │
│ │[emerald] │ │[teal]    │ │[amber]   │ │[coral]   │        │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
├─────────────────────────────────────────────────────────────┤
│ Alerts:                                                     │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ ⚠️ 23 items below reorder level | [View Reorder Report]  ││
│ └─────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│ 2-Column:                                                   │
│ ┌──────────────────────────┐ ┌────────────────────────────┐│
│ │ Stock by Warehouse       │ │ Recent Movements           ││
│ │ [Horizontal Bar Chart]   │ │ ┌────────────────────────┐ ││
│ │ Main: ████████ 5,230     │ │ │ IN  Router X50  +100   │ ││
│ │ Tech: █████ 2,340        │ │ │ OUT Cable 50m  -25     │ ││
│ │ Mob:  ███ 1,120          │ │ │ TFR Switch Y10 →Main   │ ││
│ └──────────────────────────┘ └────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

#### Item List
```
┌─────────────────────────────────────────────────────────────┐
│ PageHeader: "Items" | [+ Item] | View: [Grid] [List]        │
│ Filter: [Category ▼] [Warehouse ▼] [Stock Status ▼]         │
├─────────────────────────────────────────────────────────────┤
│ DataTable:                                                  │
│ ┌──────┬────────────────┬────────┬────────┬────────┬──────┐│
│ │ SKU  │ Item Name      │ Qty    │ Reorder│ Value  │Status││
│ ├──────┼────────────────┼────────┼────────┼────────┼──────┤│
│ │ R001 │ Router X50     │ 150    │ 50     │ 75,000 │ ✓    ││
│ │ C001 │ Cable 50m      │ 12     │ 25     │ 6,000  │ ⚠️ Low││
│ │ S001 │ Switch Y10     │ 0      │ 10     │ 0      │ ❌ Out││
│ └──────┴────────────────┴────────┴────────┴────────┴──────┘│
└─────────────────────────────────────────────────────────────┘
```

### Key Components
- `ItemCard` - Item image, stock level, value
- `StockLevelBar` - Visual quantity vs reorder
- `MovementRow` - IN/OUT/TRANSFER badge
- `WarehouseSelector` - Location picker
- `SerialNumberInput` - Serial entry with scan
- `BatchPicker` - Batch selection with expiry

---

## 10. Performance Module

### Accent: `indigo` | Icon: `Target`

### Navigation Structure
```
Performance
├── Dashboard
├── Scorecards
│   ├── My Scorecard
│   └── Team Scorecards
├── KPIs
│   ├── KPI Library
│   └── Assignments
├── KRAs
│   └── Key Result Areas
├── Reviews
│   ├── My Reviews
│   ├── Team Reviews
│   └── Pending
├── Periods
│   └── Review Cycles
├── Reports
│   ├── Performance Trends
│   └── Bonus Calculations
└── Templates
```

### Page Schemes

#### My Scorecard
```
┌─────────────────────────────────────────────────────────────┐
│ PageHeader: "My Scorecard" | Period: [Q4 2024 ▼]            │
├─────────────────────────────────────────────────────────────┤
│ Overall Score:                                              │
│ ┌─────────────────────────────────────────────────────────┐│
│ │        ┌─────┐                                          ││
│ │        │ 87% │  Exceeds Expectations                    ││
│ │        └─────┘                                          ││
│ │   [Circular Progress Ring]                              ││
│ └─────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│ KRA Breakdown:                                              │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ Sales Performance (40%)              92% ████████████░░ ││
│ │ ├─ Revenue Target         KES 5M/5M  100% ████████████ ││
│ │ ├─ New Customers          45/50      90%  █████████░░░ ││
│ │ └─ Upsell Rate            18%/15%    120% ████████████ ││
│ │                                                         ││
│ │ Customer Satisfaction (30%)          85% ██████████░░░ ││
│ │ ├─ CSAT Score             4.2/4.5    93%  ██████████░░ ││
│ │ └─ Response Time          2h/2h      100% ████████████ ││
│ │                                                         ││
│ │ Team Development (30%)               82% █████████░░░░ ││
│ │ ├─ Training Hours         20/25      80%  ████████░░░░ ││
│ │ └─ Mentoring Sessions     8/10       80%  ████████░░░░ ││
│ └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### Key Components
- `ScoreRing` - Circular overall score display
- `KRACard` - Collapsible KRA with KPIs
- `KPIProgress` - Target vs actual with bar
- `ReviewForm` - Self/manager assessment form
- `TrendChart` - Score trend over periods
- `BonusCalculator` - Payout simulation

---

## 11. Expenses Module

### Accent: `rose` | Icon: `Receipt`

### Navigation Structure
```
Expenses
├── Dashboard
├── My Expenses
│   ├── Claims
│   ├── Advances
│   └── Statements
├── Approvals
│   └── Pending Approvals
├── Cards
│   ├── My Cards
│   └── Transactions
├── Reports
│   ├── Expense Reports
│   └── Analytics
└── Settings
    ├── Categories
    ├── Policies
    └── Limits
```

### Page Schemes

#### Dashboard
```
┌─────────────────────────────────────────────────────────────┐
│ PageHeader: "Expenses" | Actions: [+ Claim] [+ Advance]     │
├─────────────────────────────────────────────────────────────┤
│ StatGrid (4 cols):                                          │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│ │ Pending  │ │ This     │ │ Advances │ │ Card     │        │
│ │ Claims   │ │ Month    │ │ Balance  │ │ Balance  │        │
│ │ 3        │ │ KES 45K  │ │ KES 12K  │ │ KES 8K   │        │
│ │[amber]   │ │[rose]    │ │[indigo]  │ │[teal]    │        │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
├─────────────────────────────────────────────────────────────┤
│ Recent Claims:                                              │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ EXP-001 │ Travel - Client Visit  │ KES 15,000 │ [Pending]││
│ │ EXP-002 │ Meals - Team Lunch     │ KES 3,500  │ [Approved]│
│ │ EXP-003 │ Supplies - Office      │ KES 8,200  │ [Paid] ✓ ││
│ └─────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│ Expense by Category (Pie Chart) | Monthly Trend (Bar Chart)│
└─────────────────────────────────────────────────────────────┘
```

#### Expense Claim Form
```
┌─────────────────────────────────────────────────────────────┐
│ PageHeader: "New Expense Claim" | [Save Draft] [Submit]     │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐│
│ │ Date            │ │ Category        │ │ Amount          ││
│ │ [Jan 15, 2025]  │ │ [Travel ▼]      │ │ [KES 15,000]    ││
│ └─────────────────┘ └─────────────────┘ └─────────────────┘│
│ ┌─────────────────────────────────────────────────────────┐│
│ │ Description                                             ││
│ │ [Client visit to Mombasa for project kickoff...]        ││
│ └─────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│ Receipts:                                                   │
│ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐      │
│ │ [📄 Receipt]  │ │ [📄 Receipt]  │ │ [+ Upload]    │      │
│ │ flight.pdf    │ │ hotel.jpg     │ │               │      │
│ │ KES 8,000     │ │ KES 7,000     │ │               │      │
│ └───────────────┘ └───────────────┘ └───────────────┘      │
├─────────────────────────────────────────────────────────────┤
│ Policy Check: ✓ Within travel budget | ✓ Valid receipts    │
└─────────────────────────────────────────────────────────────┘
```

### Key Components
- `ExpenseCard` - Claim with status and amount
- `ReceiptUpload` - Drag-drop with OCR preview
- `CategoryPicker` - Icon-based category selection
- `ApprovalFlow` - Visual approval chain
- `PolicyChecker` - Real-time policy validation
- `CardWidget` - Virtual card display

---

## 12. Assets Module

### Accent: `slate` | Icon: `HardDrive`

### Navigation Structure
```
Assets
├── Dashboard
├── Asset List
│   ├── All Assets
│   ├── By Category
│   └── By Location
├── Categories
├── Depreciation
│   ├── Schedule
│   └── Pending
├── Maintenance
│   ├── Preventive
│   ├── Warranty
│   └── Insurance
└── Settings
```

### Page Schemes

#### Dashboard
```
┌─────────────────────────────────────────────────────────────┐
│ PageHeader: "Assets" | Actions: [+ Asset]                   │
├─────────────────────────────────────────────────────────────┤
│ StatGrid (4 cols):                                          │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│ │ Total    │ │ Book     │ │ Due for  │ │ Warranty │        │
│ │ Assets   │ │ Value    │ │ Maint.   │ │ Expiring │        │
│ │ 456      │ │ KES 12M  │ │ 8        │ │ 3        │        │
│ │[slate]   │ │[emerald] │ │[amber]   │ │[coral]   │        │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
├─────────────────────────────────────────────────────────────┤
│ Assets by Category:                                         │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ 💻 IT Equipment      234  ████████████████░░░░ KES 5.2M ││
│ │ 🚗 Vehicles          12   ████████░░░░░░░░░░░░ KES 3.8M ││
│ │ 🪑 Furniture         156  ██████░░░░░░░░░░░░░░ KES 1.8M ││
│ │ 🔧 Tools             54   ███░░░░░░░░░░░░░░░░░ KES 1.2M ││
│ └─────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│ Upcoming Maintenance:                                       │
│ ┌───────────┬─────────────────────┬──────────┬────────────┐│
│ │ AST-0012  │ Server Rack A       │ Jan 20   │ [Schedule] ││
│ │ AST-0045  │ Company Vehicle KAB │ Jan 22   │ [Schedule] ││
│ └───────────┴─────────────────────┴──────────┴────────────┘│
└─────────────────────────────────────────────────────────────┘
```

#### Asset Detail
```
┌─────────────────────────────────────────────────────────────┐
│ PageHeader: "AST-0012 - Dell PowerEdge R740"                │
│ Status: [In Use] | Location: [Server Room]                  │
├─────────────────────────────────────────────────────────────┤
│ Tabs: [Details] [Depreciation] [Maintenance] [History]      │
├─────────────────────────────────────────────────────────────┤
│ 2-Column:                                                   │
│ ┌─────────────────────────────┐ ┌─────────────────────────┐│
│ │ Asset Details               │ │ Financial               ││
│ │ ─────────────────────────── │ │ ─────────────────────── ││
│ │ Category: IT Equipment      │ │ Purchase: KES 450,000   ││
│ │ Serial: DELLSRV12345       │ │ Book Value: KES 320,000 ││
│ │ Purchased: Jan 15, 2023     │ │ Depreciation: KES 130K  ││
│ │ Warranty: Jan 15, 2026      │ │ Method: Straight-line   ││
│ │ Assigned: IT Department     │ │ Useful Life: 5 years    ││
│ │ Custodian: John Doe         │ │                         ││
│ └─────────────────────────────┘ └─────────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│ Depreciation Schedule:                                      │
│ [Line chart showing value decline over 5 years]             │
└─────────────────────────────────────────────────────────────┘
```

### Key Components
- `AssetCard` - Photo, serial, status badge
- `DepreciationChart` - Value decline visualization
- `MaintenanceCalendar` - Scheduled maintenance view
- `QRCodeDisplay` - Asset tag generator
- `CustodianSelect` - Employee assignment
- `WarrantyTracker` - Countdown to expiry

---

## Summary: Component Library Extensions

Based on these module designs, the following new shared components are recommended:

### Layout Components
- `SplitPane` - Resizable two-panel layout (Inbox, Tickets)
- `KanbanBoard` - Drag-drop column layout (Pipeline, Projects)
- `CalendarGrid` - Resource/time grid (Schedule, Leave)
- `GanttTimeline` - Project timeline with dependencies
- `TreeView` - Hierarchical list (COA, Org Chart)

### Data Display
- `Timeline` - Vertical activity feed
- `ConversationThread` - Chat-style messages
- `ProgressRing` - Circular progress indicator
- `TrendIndicator` - Up/down arrow with percentage
- `CountdownTimer` - SLA/deadline countdown

### Form Components
- `EntityPicker` - Searchable entity selection
- `MultiStepForm` - Wizard-style forms
- `LineItemEditor` - Tabular line entry (JE, Invoices)
- `FileUploader` - Drag-drop with preview

### Specialized
- `MapView` - Interactive map with markers
- `Scorecard` - KPI breakdown display
- `ApprovalChain` - Workflow visualization
- `PolicyValidator` - Real-time rule checking
