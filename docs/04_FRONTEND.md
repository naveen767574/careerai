# Frontend Implementation Guide
## AI-Powered Internship & Career Recommendation System

> Phase-by-phase frontend development reference.
> Stack: React · TypeScript · Tailwind CSS · Vite · React Router · Axios

---

## Project Setup

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install axios react-router-dom tailwindcss @tailwindcss/forms
npx tailwindcss init
```

### Project Structure

```
frontend/
├── src/
│   ├── main.tsx
│   ├── App.tsx                  # Router setup
│   ├── components/              # Reusable UI components
│   │   ├── common/              # Button, Card, Badge, Toast, Modal, Spinner
│   │   ├── layout/              # Navbar, Sidebar, Footer, Layout wrapper
│   │   └── bolt/                # Bolt AI chat widget
│   ├── pages/                   # Route-level page components
│   ├── services/                # API communication (Axios)
│   │   └── api.ts               # Base Axios instance + all API calls
│   ├── hooks/                   # Custom React hooks
│   │   ├── useAuth.ts
│   │   ├── useResume.ts
│   │   └── useNotifications.ts
│   ├── store/                   # Auth state (React context or Zustand)
│   ├── utils/                   # Formatters, validators, helpers
│   └── types/                   # TypeScript type definitions
├── public/
├── vercel.json
└── vite.config.ts
```

### Axios Base Config

```typescript
// src/services/api.ts
import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  timeout: 30000,
});

// Attach JWT token from memory (never localStorage)
let authToken: string | null = null;
export const setAuthToken = (token: string | null) => { authToken = token; };

api.interceptors.request.use(config => {
  if (authToken) config.headers.Authorization = `Bearer ${authToken}`;
  return config;
});

api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      setAuthToken(null);
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);
```

---

## Phase 0 — Authentication Pages

### Pages to Build

| Page | Route | Components |
|---|---|---|
| Register | `/register` | Form: name, email, password |
| Login | `/login` | Form: email, password |
| Password Reset Request | `/reset` | Form: email |
| Password Reset Confirm | `/reset/:token` | Form: new password |

### Auth Context

```typescript
// src/store/AuthContext.tsx
interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}
// JWT stored in memory via setAuthToken() — never in localStorage
```

### Protected Route Wrapper

```tsx
// src/components/common/ProtectedRoute.tsx
const ProtectedRoute = ({ children }: { children: ReactNode }) => {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? children : <Navigate to="/login" />;
};
```

### Phase 0 Checklist

- [ ] Register form validates email format and password length
- [ ] Login stores JWT in memory and updates auth context
- [ ] Protected routes redirect to `/login` if not authenticated
- [ ] Logout clears token and redirects to login
- [ ] Toast notifications for auth errors
- [ ] Password reset flow sends email + confirms reset

---

## Phase 1 — Layout & Navigation

### Layout Components

```
components/layout/
├── Layout.tsx          # Wraps all protected pages with Navbar + Sidebar
├── Navbar.tsx          # Top bar: logo, notification badge, user avatar
├── Sidebar.tsx         # Left nav links to all pages
└── PageHeader.tsx      # Page title + optional action button
```

### Navigation Links

```
Dashboard        /
Resume           /resume
Internships      /internships
Recommendations  /recommendations
Applications     /applications
Career Tools     /career
Cover Letters    /drafts
Interview Prep   /interview
LinkedIn         /linkedin
Skills           /skills
Notifications    /notifications
Settings         /settings
```

### Notification Badge

```tsx
// Navbar shows unread notification count
const { data } = useQuery('notifications', () => api.get('/api/notifications?unread_only=true'));
<span className="badge">{data?.unread_count}</span>
```

### Phase 1 Checklist

- [ ] Layout renders correctly on mobile (320px), tablet (768px), desktop (1024px)
- [ ] Sidebar collapses to hamburger menu on mobile
- [ ] Active nav link highlighted
- [ ] Notification badge shows unread count and updates in real-time

---

## Phase 2 — Dashboard

### Route: `/`

### Components

```
pages/Dashboard/
├── Dashboard.tsx
├── ResumeScoreCard.tsx    # Score gauge (0-100) + quick feedback
├── QuickActions.tsx       # Links to Upload Resume, View Matches, etc.
├── RecentActivity.tsx     # Latest notifications + applications
└── CoachBriefCard.tsx     # Latest coaching brief from Coach Agent
```

### Dashboard Layout

```
┌──────────────────────────────────────────────────────────┐
│  Welcome back, {name}!                    [🔔 3]         │
├──────────┬──────────────────────────────────────────────┤
│ Resume   │  Latest Coaching Brief                        │
│ Score    │  • You haven't applied in 5 days...           │
│  78/100  │  • Docker trending +28% in your target roles  │
│          │  • 3 new strong matches since yesterday        │
├──────────┴──────────────────────────────────────────────┤
│  Quick Actions                                            │
│  [View Recommendations] [Prepare Interview] [LinkedIn]   │
├──────────────────────────────────────────────────────────┤
│  Recent Activity                                          │
│  ✅ Application sent — TechCorp Backend Intern            │
│  📄 Resume analyzed — Score: 78/100                      │
└──────────────────────────────────────────────────────────┘
```

---

## Phase 3 — Resume Page

### Route: `/resume`

### Two Entry Points

```tsx
// If no resume exists → show choice
<div>
  <button onClick={() => navigate('/resume/upload')}>Upload Existing Resume</button>
  <button onClick={() => navigate('/resume/build')}>Create with AI Builder</button>
</div>

// If resume exists → show analysis
<ResumeAnalysis />
```

### Components

```
pages/Resume/
├── ResumePage.tsx         # Router: upload choice OR analysis view
├── ResumeUpload.tsx       # Drag-and-drop PDF/DOCX upload
├── ResumeAnalysis.tsx     # Score, feedback, extracted data tabs
├── ScoreGauge.tsx         # Animated 0-100 gauge
├── SkillsDisplay.tsx      # Skill chips with type badges
└── SectionFeedback.tsx    # Per-section feedback with improvement tips
```

### Resume Builder Route: `/resume/build`

```
pages/ResumeBuilder/
├── BuilderPage.tsx         # Manages 12-step session
├── ConversationUI.tsx      # Chat-style input for each question
├── ProgressBar.tsx         # Step 3/12 visual indicator
├── TemplatePicker.tsx      # Template cards with preview thumbnails
├── ResumePreview.tsx       # Rendered HTML iframe preview
├── ATSScoreCard.tsx        # Score breakdown: Structure/Keywords/Completeness
└── ExportButtons.tsx       # PDF and DOCX download buttons
```

### Phase 3 Checklist

- [ ] Upload rejects non-PDF/DOCX files with clear error
- [ ] Analysis shows score gauge, section breakdown, skill chips
- [ ] Builder shows one question at a time (step 1 of 12)
- [ ] Progress bar updates per step
- [ ] Template picker shows AI recommendation + rationale
- [ ] Preview renders HTML iframe of selected template
- [ ] PDF and DOCX export buttons trigger download

---

## Phase 4 — Internship Listings

### Route: `/internships`

### Components

```
pages/Internships/
├── ListingsPage.tsx         # Paginated listing cards + filters
├── FilterBar.tsx            # Search, company, location filters
├── InternshipCard.tsx       # Card: title, company, match %, apply button
├── InternshipDetail.tsx     # Full detail + skill gap + buttons
└── SkillGapDisplay.tsx      # Matched skills (green) vs. missing (red)
```

### Internship Detail Page (`/internships/:id`)

```
┌──────────────────────────────────────────────────────────┐
│ Backend Developer Intern · TechCorp · Bangalore           │
├──────────────────────────────────────────────────────────┤
│ Match: 74%  ████████████████░░░░░                         │
│ Matched: Python, FastAPI, PostgreSQL, Git                 │
│ Missing: Docker, Redis                                    │
├──────────────────────────────────────────────────────────┤
│ [Track Application]  [Draft Cover Letter]  [Prepare for Interview] │
├──────────────────────────────────────────────────────────┤
│ Full description...                                       │
└──────────────────────────────────────────────────────────┘
```

---

## Phase 5 — Recommendations & Career Tools

### Recommendations (`/recommendations`)

```
pages/Recommendations/
├── RecommendationsPage.tsx
├── RecommendationCard.tsx    # Match %, matched skills, missing skills, actions
└── RefreshButton.tsx         # Triggers POST /api/recommendations/refresh
```

### Career Tools (`/career`)

```
pages/CareerTools/
├── CareerToolsPage.tsx       # Tabs: Career Paths | Role Comparator
├── CareerPaths.tsx           # 3-5 cards ranked by alignment score
├── PathCard.tsx              # Path: title, timeline, required skills, steps
├── RoleComparator.tsx        # Select 2-4 listings → side-by-side table
└── ComparisonTable.tsx       # Common skills (green) | unique per role (blue)
```

---

## Phase 6 — Applications & Cover Letters

### Applications (`/applications`)

```
pages/Applications/
├── ApplicationsPage.tsx
├── ApplicationCard.tsx       # Status badge, notes, applied date, update button
├── StatusDropdown.tsx        # APPLIED | INTERVIEW_SCHEDULED | REJECTED | ACCEPTED
└── NotesEditor.tsx           # Inline editable notes field
```

### Cover Letters (`/drafts`)

```
pages/Drafts/
├── DraftsPage.tsx            # List of all drafts by status
├── DraftCard.tsx             # Preview, status badge, action buttons
├── DraftEditor.tsx           # Full editor with Approve/Discard buttons
└── GenerateButton.tsx        # Triggers Writer Agent per listing
```

---

## Phase 7 — Interview Prep

### Route: `/interview`

```
pages/Interview/
├── InterviewHomePage.tsx     # History list + "Start New" per listing
├── InterviewSession.tsx      # Live Q&A chat UI
├── QuestionCard.tsx          # Question + text input + progress (Q3/10)
├── InterviewReport.tsx       # Full feedback report
├── ScoreGauge.tsx            # Overall score + readiness badge
├── QuestionResult.tsx        # Per-question: score, feedback, model answer
└── ImprovementsPanel.tsx     # Top 3 areas + recommended resources
```

### Session UI Flow

```
Setup → Q1 (user types) → Q2 → ... → Q10 → "Evaluating..." → Report
```

### Report Display

```
Overall: 72/100   Almost Ready ⚡
Technical: 68/100  |  Behavioral: 77/100

✅ Top Strengths
  • Strong understanding of REST API design
  • Good project experience with real-world tools

🎯 Improve These
  • Database indexing and query optimization
  • STAR method for behavioral answers

📚 Recommended Resources
  • PostgreSQL indexing and performance tuning
  • Grokking the System Design Interview
```

---

## Phase 8 — LinkedIn Optimizer

### Route: `/linkedin`

```
pages/LinkedIn/
├── LinkedInPage.tsx          # Input form OR report view
├── ProfileInputForm.tsx      # Text areas for each LinkedIn section
├── LinkedInReport.tsx        # Full optimization report
├── ScoreGauge.tsx            # Profile score 0-100 with color coding
├── HeadlineVariants.tsx      # 3 options with [Copy] button each
├── SectionImprovement.tsx    # Before/After with [Copy] button
├── SkillsOptimizer.tsx       # Add/remove/reorder with [Copy] button
└── RegeneratePanel.tsx       # Inline "make it shorter" → regenerate
```

### Score Color Coding

```
0–40:  Red    — Needs significant work
41–70: Amber  — Good foundation, room to improve
71–100: Green — Strong profile
```

---

## Phase 9 — Skills Dashboard & Notifications

### Skills Dashboard (`/skills`)

```
pages/Skills/
├── SkillsDashboard.tsx
├── TrendChart.tsx             # Line chart: skill frequency over time (recharts)
├── SkillSnapshotTable.tsx     # Table: skill, current %, trend arrow, delta
└── AnalystInsightCard.tsx     # Latest Analyst Agent natural language insight
```

### Notifications (`/notifications`)

```
pages/Notifications/
├── NotificationsPage.tsx
├── NotificationItem.tsx       # Type icon, title, content, timestamp, read status
└── NotificationActions.tsx    # Mark read | Mark all read buttons
```

---

## Phase 10 — Bolt AI Chat Widget

```
components/bolt/
├── BoltWidget.tsx             # Floating widget, bottom-right
├── BoltChat.tsx               # Chat message list
├── BoltMessage.tsx            # User and bot message bubbles
├── BoltInput.tsx              # Text input + send button
└── TypingIndicator.tsx        # Animated dots while generating
```

### Widget Behavior

```tsx
const BoltWidget = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  // History preserved during session (React state)
  // Toggle: click Bolt icon → expand/collapse
  // Auto-detects intent: reads Coach brief for context
};
```

---

## Phase 11 — Polish & Responsive Finalization

### Responsive Breakpoints

| Breakpoint | Min Width | Adjustments |
|---|---|---|
| Mobile | 320px | Single column, hamburger nav, stacked cards |
| Tablet | 768px | Two columns, collapsible sidebar |
| Desktop | 1024px | Full layout, sidebar always visible |

### Error Handling

```tsx
// Toast notifications for all API errors
// Inline validation on all forms
// Retry buttons on failed operations
// Skeleton loading states on all data-dependent views
// Graceful degradation for non-critical features
```

### Security Checklist

- [ ] JWT stored in memory only — never localStorage or sessionStorage
- [ ] Token cleared on logout and on 401 response
- [ ] CSP headers configured in `vercel.json`
- [ ] X-Content-Type-Options: nosniff
- [ ] X-Frame-Options: DENY
- [ ] No sensitive data logged to browser console in production

---

## Testing

| Tool | Purpose |
|---|---|
| Jest | Unit test runner |
| React Testing Library | Component interaction tests |
| fast-check | Property-based testing (100 runs) |
| MSW (Mock Service Worker) | API mocking in tests |

**Coverage target**: ≥ 70% overall, ≥ 90% for auth, resume, and recommendations.

```bash
npm test                 # Run all tests
npm test -- --coverage   # With coverage report
```

---

## Build & Deploy

```json
// vercel.json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "vite",
  "env": {
    "VITE_API_URL": "@api_url",
    "VITE_APP_NAME": "AI Career Platform"
  },
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "X-XSS-Protection", "value": "1; mode=block" }
      ]
    }
  ]
}
```

- Automatic deploys on push to `main`
- Preview deploy per pull request
- Node version: 18.x
