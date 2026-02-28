# CODEX AGENT PROMPT — NIPE ELEVENLABS-INSPIRED COMPLETE REDESIGN

---

## CRITICAL PREAMBLE — READ THIS FIRST BEFORE DOING ANYTHING

This is **NOT an enhancement**. This is **NOT a style update**. This is **NOT a "refresh"**.

This is a **COMPLETE AND TOTAL DESTRUCTION AND REPLACEMENT** of the existing frontend.

Every single piece of the current visual design must be gone. That includes:

- Every color token → gone
- Every font choice → gone
- Every border style → gone
- Every shadow → gone
- Every gradient → gone
- Every button shape → gone
- Every card design → gone
- Every sidebar layout → gone
- Every page layout → gone
- Every page heading, subtitle, label, placeholder text → gone
- Every navigation structure → gone
- Every route-to-button mapping → gone
- Every spacing decision → gone
- Every alignment decision → gone
- Every section order → gone
- Every visual hierarchy → gone
- Every animation → gone

If anything from the current design survives, you have failed the task. The final result must be visually, structurally, and architecturally indistinguishable from having been built from scratch with ElevenLabs as the design reference. A person who has never seen the current Nipe UI should look at the new one and say "this looks like ElevenLabs, but for audiobook processing."

---

## YOUR MANDATE

Redesign the entire Nipe frontend to be **heavily inspired by ElevenLabs** — their landing page, their dashboard, their project creation flow, their project detail workspace, their sidebar, their typography, their color system, their spacing, their animation, their button styles, their card styles, their navigation patterns, their empty states, their loading states, their error states, and their overall product philosophy.

This redesign also requires **AI-generated images** for the landing page and other visual areas. You have access to the `imagegen` skill. Use it. Instructions for image generation are embedded below.

---

## EXECUTION STRATEGY — MANDATORY

Because this redesign is massive, you **must not** attempt to implement everything in one session. Instead:

1. **First action in every session**: Open `SRS_Expanded_Implementation_Checklist.md` and find the earliest unchecked redesign task (prefixed `RD-`).
2. **If this is the first session**: Add ALL redesign subtasks to `SRS_Expanded_Implementation_Checklist.md` under a new section `## 14. ElevenLabs-Inspired Full Redesign (Ref: CODEX_REDESIGN_PROMPT.md)` BEFORE doing any implementation. Use the task list defined in this document as the source of truth.
3. **One task at a time**: Implement one `RD-*` task completely (code + visual verification + any tests) before moving to the next.
4. **Mark complete**: After finishing each task, mark it `[x]` in the checklist.
5. **Never skip**: Do not skip ahead to later `RD-*` tasks unless the earlier one is explicitly blocked with a reason and a follow-up task ID.

The goal is: **after every single `RD-*` task is marked `[x]`, the Nipe UI must be a complete, pixel-faithful ElevenLabs-inspired product with no trace of the old design.**

---

## SECTION 1 — ELEVENLABS DESIGN SYSTEM (SOURCE OF TRUTH)

### 1.1 Where to Study ElevenLabs

Study these resources before implementing anything:

- **Main website**: https://elevenlabs.io — landing page, hero, features, footer
- **App**: https://elevenlabs.io/app (requires account) — dashboard, project creation, sidebar
- **UI component library**: https://ui.elevenlabs.io — their open-source component system
- **UI blocks / examples**: https://ui.elevenlabs.io/blocks — agent/audio component blocks
- **Setup docs**: https://ui.elevenlabs.io/docs/setup
- **GitHub repo (official UI)**: https://github.com/elevenlabs/ui
- **Agents platform docs**: https://elevenlabs.io/docs/conversational-ai/dashboard

### 1.2 Exact Design Token Values

These are pulled directly from ElevenLabs' actual `globals.css` in their GitHub repo (`elevenlabs/ui`):

```css
/* DARK MODE — their primary/default mode */
--background: oklch(0.145 0 0);        /* pure near-black, no hue, no tint */
--foreground: oklch(0.985 0 0);        /* near-white */
--card: oklch(0.205 0 0);              /* elevated dark surface */
--card-foreground: oklch(0.985 0 0);
--popover: oklch(0.269 0 0);
--popover-foreground: oklch(0.985 0 0);
--primary: oklch(0.922 0 0);           /* WHITE as primary CTA — their key design choice */
--primary-foreground: oklch(0.205 0 0);/* dark text on white button */
--secondary: oklch(0.269 0 0);
--secondary-foreground: oklch(0.985 0 0);
--muted: oklch(0.269 0 0);
--muted-foreground: oklch(0.708 0 0);  /* medium gray text */
--accent: oklch(0.371 0 0);
--accent-foreground: oklch(0.985 0 0);
--destructive: oklch(0.704 0.191 22.216); /* red-orange for errors */
--border: oklch(1 0 0 / 10%);          /* extremely subtle white border */
--input: oklch(1 0 0 / 15%);
--ring: oklch(0.556 0 0);
--sidebar: oklch(0.205 0 0);            /* sidebar slightly elevated */
--sidebar-foreground: oklch(0.985 0 0);
--sidebar-primary: oklch(0.488 0.243 264.376); /* blue for sidebar active */
--sidebar-accent: oklch(0.269 0 0);
--sidebar-border: oklch(1 0 0 / 10%);
--surface: oklch(0.2 0 0);
--surface-foreground: oklch(0.708 0 0); /* muted on surface */

/* RADIUS */
--radius: 0.625rem;  /* 10px — subtly rounded, not aggressive */
--radius-sm: calc(var(--radius) - 4px);
--radius-md: calc(var(--radius) - 2px);
--radius-lg: var(--radius);
--radius-xl: calc(var(--radius) + 4px);
```

### 1.3 Typography

- **Primary font**: **Geist** — https://vercel.com/font (available via `@fontsource/geist` or Google Fonts CDN)
- **Monospace font**: **Geist Mono** — for code, config, run logs (`@fontsource/geist-mono`)
- ElevenLabs uses their proprietary "Waldenburg" font; Geist is the closest public equivalent in weight, proportion, and character
- NO separate serif font — Geist is used for everything (headings, body, UI labels)
- Font weights used: 400 (regular), 500 (medium), 600 (semibold), 700 (bold)
- Letter-spacing on headings: `-0.02em` to `-0.04em` (tight tracking)
- NO uppercase labels (current Nipe uses `tracking-[0.16em] uppercase` — eliminate this entirely)

### 1.4 Key Visual Principles

1. **Pure neutral dark** — No blue tint on background. No hue whatsoever (`oklch(x 0 0)`). Backgrounds are pure achromatic dark neutrals.
2. **White as primary** — The primary CTA button is white with dark text. NOT blue. NOT colored. White.
3. **Ghost/outline as secondary** — Secondary actions use a very subtle border `oklch(1 0 0 / 15%)` with transparent background.
4. **Ultra-subtle borders** — `oklch(1 0 0 / 10%)` everywhere. Not visible until you look closely.
5. **Minimal decoration** — No rounded frame cards containing the whole app. No gradients on the body. Flat dark surfaces.
6. **High information density** — Content fills the space. No large padding blocks.
7. **Subtle ambient glow** — Landing page only: 1-2 large blurred radial gradients at extreme low opacity (6-10%) in the very corners or behind the hero. Not everywhere.
8. **Flat layout, no floating shells** — The current Nipe has a `nipe-shell-frame` that creates a rounded-corner floating card. ElevenLabs is full-screen, flat, edge-to-edge.
9. **Status colors are minimal** — Green dot for active/success, amber dot for running/pending, red dot for error. No large colored banners.
10. **Hover states** — Cards lift with `box-shadow` and border brightens from 10% → 20% white opacity. Buttons dim to 80% opacity on hover. No dramatic transforms.

### 1.5 Animation System

ElevenLabs uses these exact animation utilities (copy into new `globals.css`):

```css
@keyframes fade-in {
  from { opacity: 0; transform: scale(0.95) translateY(10px); }
  to   { opacity: 1; transform: scale(1) translateY(0); }
}
@keyframes fade-in-up {
  from { opacity: 0; transform: translateY(20px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes fade-in-scale {
  from { opacity: 0; transform: scale(0.9); }
  to   { opacity: 1; transform: scale(1); }
}
/* Easing: cubic-bezier(0.4, 0, 0.2, 1) on all transitions */
/* Duration: 0.3s–0.6s depending on element size */
```

Apply: `animate-fade-in`, `animate-fade-in-up`, `animate-fade-in-scale` as Tailwind utilities.

---

## SECTION 2 — LANDING PAGE

### 2.1 ElevenLabs Landing Page Anatomy

Study https://elevenlabs.io carefully. Their landing page structure:

1. **Sticky transparent navbar** — becomes blurred/frosted on scroll
2. **Hero** — massive, full-width, dark, centered headline + sub-headline + 2 CTA buttons + interactive demo below
3. **Trust/logo strip** — scrolling marquee of partner/client logos (or in our case: format/feature tags)
4. **Feature showcase** — product capability sections alternating layout
5. **Technical bento grid** — cards showing APIs, capabilities, integrations
6. **Customer story strip** — testimonial or use-case cards (or in our case: use-case pills)
7. **Footer** — 4-column link grid + bottom bar

### 2.2 Nipe Landing Page — New Content

**Navbar**:
- Left: Nipe logo (monogram "N" in a dark square, or a simple wordmark "nipe" in Geist Bold)
- Center: Features · How it Works · Modes · Export
- Right: `Sign in` (ghost button) · `Get started` (white filled button, small, rounded-full)
- Background: transparent, becomes `oklch(0.145 0 0 / 80%)` with `backdrop-blur-md` on scroll
- No border by default; thin border appears on scroll

**Hero Section**:
- Headline (very large, 64px–80px desktop): `"Bring Any Story to Life"`
- Sub-headline (18px, muted): `"Upload a novel, academic paper, or manuscript. Nipe extracts characters, maps voices, and produces a fully-tagged audiobook-ready export in minutes."`
- CTAs: `"Start a Project"` (white, filled, `rounded-full`, `px-6 py-2.5`) · `"See how it works"` (ghost, same size)
- Background: pure `oklch(0.145 0 0)` — no gradient — but add 2 ambient blobs:
  - Blob 1: bottom-left, `oklch(0.488 0.243 264.376 / 0.07)` (very faint blue), 600px diameter, `blur-[140px]`
  - Blob 2: top-right, `oklch(0.75 0.18 65 / 0.06)` (very faint orange), 500px diameter, `blur-[120px]`
- Below CTAs: an AI-generated hero image or illustration (see image generation instructions below)

**Trust Strip** (marquee):
- Scrolling horizontal loop of badges: `TXT · EPUB · Markdown · Audiobook · Academic · Author · Custom Mode · Multi-Character · Voice Mapping · Pronunciation · Analytics · JSON Export`
- Each badge: `border border-white/10 rounded-full px-3 py-1 text-sm text-muted-foreground`
- Infinite CSS scroll animation, paused on hover

**Features Bento Grid**:
- Section heading: `"Everything your audiobook pipeline needs"`
- 3-column bento grid (desktop), 2-col (tablet), 1-col (mobile)
- 6 cards, each with: small icon (top-left), bold card title, 1-line description, subtle card surface (`bg-card border border-white/10`)
- Cards:
  1. Character Extraction — `"Automatically identifies every speaking character and narrator from raw text"`
  2. Voice Mapping — `"Assign distinct ElevenLabs voices to each character with intelligent defaults"`
  3. Pipeline Runs — `"Trigger deterministic processing runs with full observability and restart support"`
  4. Narrative Analytics — `"Inspect tension, valence, and character co-occurrence trends across chapters"`
  5. Pronunciation Control — `"Define per-character and global pronunciation rules before export"`
  6. Structured Export — `"Download JSON or CSV exports ready for downstream audio production"`

**How It Works** (3-step):
- Section heading: `"From manuscript to production in three steps"`
- Horizontal numbered steps (stacked on mobile):
  1. `Upload` — `"Drop your TXT, EPUB, or Markdown file. Nipe ingests it, normalizes the text, and prepares it for analysis."`
  2. `Configure` — `"Set the processing mode, define characters, assign voices, and tune pipeline parameters."`
  3. `Export` — `"Trigger a run and download your fully-tagged, voice-ready export when it completes."`

**CTA Banner**:
- Full-width section: `"Ready to process your first manuscript?"`
- Single button: `"Create your first project"` (white, filled, `rounded-full`)
- Background: `bg-card border-y border-white/10`

**Footer**:
- 4 columns: Product · Resources · Modes · Legal
- Product: Dashboard · New Project · Exports · Analytics
- Resources: Documentation · API Reference · Changelog
- Modes: Audiobook · Academic · Author · Custom
- Legal: Privacy · Terms
- Bottom bar: `© 2025 Nipe. Built for audiobook creators.`

### 2.3 Image Generation Instructions for Landing Page

**Use the imagegen skill at** `/Users/elhamdev/.cursor/skills/imagegen/SKILL.md` — read it first, then generate images.

Generate the following images:

**Image 1 — Hero Visual** (`frontend/public/images/hero-visual.png`):
```
A dark, minimal, high-tech dashboard UI mockup floating against a near-black background. 
The mockup shows a sidebar on the left with navigation items, and a main content area 
displaying a character map with nodes connected by lines, representing a story's 
character relationships. The color scheme is near-black backgrounds, white text, 
very subtle white borders, and a single accent highlight in deep blue. The overall 
mood is professional, clean, modern SaaS. No brand logos visible. Photorealistic 
UI screenshot style. 16:9 aspect ratio.
```

**Image 2 — Feature: Character Extraction** (`frontend/public/images/feature-characters.png`):
```
A dark UI panel showing a list of fictional character names (like "Narrator", "Sung Jin-Woo", 
"Cha Hae-In") each with a small avatar circle, a gender tag pill, and an alias count badge. 
The background is near-black, text is white, borders are extremely subtle white at 10% opacity. 
Clean, minimal, high-information-density SaaS interface. Square crop.
```

**Image 3 — Feature: Analytics** (`frontend/public/images/feature-analytics.png`):
```
A dark analytics dashboard panel showing a tension/emotion line chart with multiple 
character-colored lines over chapter numbers on the x-axis. Values range smoothly. 
Background near-black, chart lines in blue, orange, and teal. Grid lines at 5% white opacity. 
Clean SaaS chart design. Square crop.
```

**Image 4 — How It Works Illustration** (`frontend/public/images/how-it-works.png`):
```
A minimal dark illustration showing three connected steps: a document icon on the left, 
a gear/settings icon in the center, and a download/export icon on the right. Connected 
by a subtle dotted line. Near-black background, white icons, very clean and geometric. 
Wide landscape crop 3:1 aspect ratio.
```

---

## SECTION 3 — APP SHELL (SIDEBAR + LAYOUT)

### 3.1 ElevenLabs Shell Pattern

ElevenLabs uses:
- **Fixed left sidebar**: always visible, `240px` wide expanded, `64px` collapsed (icon-only)
- **Full-screen dark canvas**: no floating frame card. The sidebar and content area are edge-to-edge, full-height
- **Sidebar content** (top to bottom):
  - Logo area (top, ~56px height)
  - Navigation items (icon + label, each ~40px tall, `rounded-md` hover state)
  - Group labels (small uppercase muted text dividers)
  - Flex-grow spacer
  - User account area (bottom, avatar + name + settings)
- **No separate top header bar for route title** — the current route's `<h1>` is inside the content area itself
- **Collapse button**: small `<` icon inside the sidebar bottom area or beside the logo

### 3.2 New Nipe Shell — Global (non-project)

```
┌──────────────────────────────────────────────────────┐
│ SIDEBAR (240px)          │ MAIN CONTENT               │
│                          │                            │
│ [N] nipe                 │ <page content here>         │
│                          │ (no header bar)            │
│ ─────────────────────    │                            │
│ 🏠 Dashboard             │                            │
│ ➕ New Project           │                            │
│ ⚙️  Settings             │                            │
│                          │                            │
│ [spacer]                 │                            │
│                          │                            │
│ [avatar] User Name       │                            │
└──────────────────────────────────────────────────────┘
```

- Sidebar background: `bg-sidebar` (`oklch(0.205 0 0)`)
- Main content background: `bg-background` (`oklch(0.145 0 0)`)
- Sidebar separator: `border-r border-white/10`
- Active nav item: `bg-sidebar-accent text-foreground rounded-md`
- Inactive nav item: `text-muted-foreground hover:text-foreground hover:bg-sidebar-accent/50`
- Logo: `"N"` monogram in a `24px` square, or the wordmark `"nipe"` in `font-bold`
- Collapse toggle: inside sidebar, below logo

### 3.3 New Nipe Shell — Within Project Workspace

When inside a project (`/projects/:id/*`), the sidebar swaps to project-scoped navigation:

```
┌──────────────────────────────────────────────────────┐
│ SIDEBAR (240px)          │ MAIN CONTENT               │
│                          │                            │
│ ← All Projects           │ <breadcrumb inside page>   │
│ ─────────────────────    │                            │
│ SETUP                    │                            │
│   📄 Overview            │                            │
│   📤 Upload              │                            │
│                          │                            │
│ CONFIGURATION            │                            │
│   🎭 Mode                │                            │
│   👥 Characters          │                            │
│   🎙️ Voice              │                            │
│   ⚙️  Pipeline           │                            │
│                          │                            │
│ OPERATIONS               │                            │
│   ▶️  Runs               │                            │
│   📦 Exports             │                            │
│                          │                            │
│ INSIGHTS                 │                            │
│   📊 Analytics           │                            │
│                          │                            │
│ MANAGE                   │                            │
│   🔧 Settings            │                            │
└──────────────────────────────────────────────────────┘
```

- Group labels: `text-[10px] font-semibold tracking-widest text-muted-foreground/60 px-3 mb-1 mt-4`
- Nav items: same style as global sidebar
- Lock states: locked items show a `lock` icon inline (16px, muted color) — NO colored lock overlays, NO "go to required step" banners
- Lock behavior: clicking a locked item shows a `sonner` toast: `"Complete [step name] first"` — nothing else

---

## SECTION 4 — DASHBOARD PAGE

### 4.1 ElevenLabs Dashboard Pattern

ElevenLabs' dashboard (observed from their app and docs):
- Clean page heading area: left-aligned title, right-aligned CTA
- Filter tabs below heading (pills, not boxes)
- Project/agent grid: 3 columns, card-based
- Each card: minimal info, status indicator, quick actions on hover
- Empty state: centered, simple, clear CTA

### 4.2 New Nipe Dashboard

**Route**: `/dashboard`

**Layout**:
```
My Projects                              [+ New Project]
─────────────────────────────────────────────────────
[All]  [Active]  [Archived]          [🔍 Search...]

┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Project Name │ │ Project Name │ │ Project Name │
│              │ │              │ │              │
│ [Audiobook]  │ │ [Academic]   │ │ [Author]     │
│ ● Active     │ │ ○ No runs    │ │ ✓ Exported   │
│              │ │              │ │              │
│ 3 days ago   │ │ 1 week ago   │ │ 2 hours ago  │
└──────────────┘ └──────────────┘ └──────────────┘
```

**Project Card** (`project-card.tsx`):
- Container: `bg-card border border-white/10 rounded-lg p-4 cursor-pointer`
- Hover: `border-white/20 shadow-lg shadow-black/20` transition `duration-150`
- Project name: `text-base font-semibold text-foreground truncate`
- Mode badge: `text-xs px-2 py-0.5 rounded-full border border-white/10 text-muted-foreground`
- Status indicator: colored dot (3 states) + label
  - `● oklch(0.60 0.18 142)` = green = "Last run succeeded"
  - `● oklch(0.75 0.18 65)`  = amber = "Run in progress"
  - `● oklch(0.60 0.20 25)`  = red   = "Last run failed"
  - `○ text-muted-foreground` = gray = "No runs yet"
- Date: `text-xs text-muted-foreground mt-auto`
- On click: navigate to `/projects/:id/overview`
- Hover actions (appear on hover): archive icon (top-right, 16px, muted)

**Empty State**:
- Centered icon (book or document, 48px, muted)
- Heading: `"No projects yet"`
- Sub: `"Create your first project to get started"`
- Button: `"Create a project"` (white, filled)

**Data source**: `GET /api/dashboard/project-control-panel/projects`

---

## SECTION 5 — PROJECT CREATION WIZARD

### 5.1 ElevenLabs Project Creation Pattern

ElevenLabs creates agents via a clean focused modal or dedicated page:
- Centered, narrow column (max-w-lg or max-w-xl)
- Step progress indicator at top (dots or numbered)
- One focused form per step
- Clear Back / Continue navigation
- Cancel returns to dashboard

### 5.2 New Nipe Project Creation

**Route**: `/projects/new`

**Layout**: Full dark page with centered wizard card (`max-w-xl mx-auto`)

**Step indicator** (top of card):
```
① Name  ──  ② Upload  ──  ③ Mode
```
Active step: white text, white underline. Completed: muted with checkmark. Future: muted.

**Step 1 — Name**:
- Heading: `"Name your project"`
- Sub: `"Give your project a descriptive name. You can change this later."`
- Input: project name (required, autofocus)
- Textarea: description (optional, 3 rows)
- CTA: `"Continue"` (white, full-width)

**Step 2 — Upload Source**:
- Heading: `"Add your source text"`
- Sub: `"Upload a file or paste your text directly."`
- File type tabs: `TXT · EPUB · Markdown` (horizontal pill tabs)
- Drag-and-drop area: `border-2 border-dashed border-white/15 rounded-xl p-12 text-center`
  - Icon: upload icon (32px, muted)
  - Label: `"Drop your file here, or click to browse"`
  - Sub: `".txt, .epub, or .md up to 50MB"`
- Or a `"Paste text"` link that expands a textarea
- CTA: `"Continue"` (white) / `"Back"` (ghost)

**Step 3 — Mode Selection**:
- Heading: `"Choose a processing mode"`
- Sub: `"Each mode optimizes the pipeline for a specific type of content."`
- 2×2 grid of mode cards:
  - Each card: `border border-white/10 rounded-lg p-4 cursor-pointer`
  - Selected: `border-white/50 bg-white/5`
  - Icon (top-left, 20px), Mode name (bold), 1-line description (muted, small)
  - Modes: Audiobook / Academic / Author / Custom
- CTA: `"Create Project"` (white) / `"Back"` (ghost)

---

## SECTION 6 — PROJECT WORKSPACE PAGES

All pages share these layout rules:
- **Page header** (inside content, NOT in a top bar):
  ```
  All Projects > [Project Name] > [Page Name]   (breadcrumb, muted small text)
  
  [Page Title]                                [Optional CTA button]
  [Page subtitle / description]
  ─────────────────────────────────────────
  [Content]
  ```
- Page title: `text-2xl font-bold text-foreground`
- Page subtitle: `text-sm text-muted-foreground mt-1`
- Divider: `border-b border-white/10 mb-6`
- Content: no wrapping card — content sits directly on background

### 6.1 Overview Page

- 2-column stats grid (top): Cards for total chapters, characters found, last run status, export readiness
- Stats card: `bg-card border border-white/10 rounded-lg p-4`
- Timeline / activity feed (below): recent events in a vertical list with timestamps
- CTA if setup incomplete: `"Continue Setup"` button pointing to next incomplete step

### 6.2 Mode Page

- Same 2×2 mode card grid as creation wizard Step 3
- Currently selected mode highlighted
- `"Save Mode"` button bottom (appears only if mode changed)

### 6.3 Characters Page

- Full-width table (not cards):
  ```
  Name        Aliases    Gender    Dialogue Count    Actions
  ──────────────────────────────────────────────────────────
  Narrator    —          N/A       142               ✏️ 🗑️
  Jin-Woo     Solo, S    Male      387               ✏️ 🗑️
  ```
- Table: `bg-background` rows, `border-b border-white/5` between rows, hover: `bg-white/2`
- Floating action bar (bottom of page, sticky):
  - `"Extract Characters"` · `"Import JSON"` · `"Finalize Map"` buttons
  - `bg-card border border-white/10 rounded-xl px-4 py-2`
- Empty state: centered, `"No characters yet"` + `"Extract from text"` CTA

### 6.4 Voice Mapping Page

- Split layout: character list (left 40%) · voice assignment panel (right 60%)
- Character list: scrollable, each row shows character name + current voice assignment status
- Voice assignment panel: for selected character — voice selector dropdown, preview button, save button
- No heavy cards — just clean sections with subtle dividers

### 6.5 Pipeline Setup Page

- Settings form layout:
  - Section heading (muted, small caps)
  - Setting label (foreground) + description (muted, small) + control (right-aligned or below)
  - `border-b border-white/5` between settings
- Sections: General · LLM Config · Normalization · Segmentation
- Bottom: `"Save Configuration"` (white) + `"Start Run"` (white, emphasized) side by side

### 6.6 Run Monitor Page

- Top: progress bar (full-width, `h-1`, animated if running)
- Run status header: run ID, status badge, start time, duration
- Stage log: vertical timeline list
  - Each stage: icon (success/running/pending/error) + stage name + duration + timestamp
  - Running stage: pulsing icon
- Bottom: `"Cancel"` (ghost, destructive color) / `"Rerun"` / `"Recover"` based on state

### 6.7 Exports Page

- Run selector: horizontal tab row of completed run IDs (most recent first)
- Export options per run:
  - JSON Export: `bg-card border rounded-lg p-4` with size + download button
  - CSV Export: same
- No heavy decoration — minimal download center

### 6.8 Analytics Page

- Chart grid (responsive, 2 columns desktop):
  - Tension Graph
  - Polarity Graph
  - Character Co-occurrence
  - Character Analytics table
- Each chart: `bg-card border border-white/10 rounded-lg p-4`
- Chart heading: `text-sm font-semibold` top-left of card

### 6.9 Settings Page

- Grouped settings sections:
  - **General**: project name (editable inline), description, mode indicator
  - **LLM**: provider selector, model selector, quota display
  - **Danger Zone**: `border border-destructive/30 rounded-lg p-4`
    - Archive project, delete project — each with confirmation dialogs

---

## SECTION 7 — SHARED UI COMPONENT ADJUSTMENTS

These are tuning changes to existing Shadcn components to match the new design tokens. Do NOT rebuild them from scratch — just ensure their default styles match the new token values.

- **Button variants**:
  - `default`: `bg-primary text-primary-foreground` = white bg, dark text
  - `secondary`: `bg-secondary text-secondary-foreground border border-white/10`
  - `ghost`: `hover:bg-white/5 text-muted-foreground hover:text-foreground`
  - `destructive`: `bg-destructive/20 text-destructive border border-destructive/30`
  - All buttons: `rounded-md` (not `rounded-full` except landing CTAs), `text-sm`, `font-medium`

- **Card**: `bg-card border border-white/10 rounded-lg` — remove all shadow by default

- **Input**: `bg-input border border-white/15 text-foreground placeholder:text-muted-foreground rounded-md`

- **Badge**: `text-xs font-medium px-2 py-0.5 rounded-full border border-white/10 bg-transparent text-muted-foreground`

- **Separator**: `bg-white/10`

- **Table**: header row `text-xs text-muted-foreground`, data rows `text-sm`, hover `bg-white/3`

---

## SECTION 8 — THINGS TO REMOVE COMPLETELY

These patterns exist in the current Nipe frontend and must be **entirely deleted**:

1. `nipe-shell-frame` class — the floating card shell that wraps the entire app
2. `nipe-panel`, `nipe-sidebar`, `nipe-min-header`, `nipe-search-shell`, `nipe-logo-chip` — all custom classes
3. Manrope font and Plus Jakarta Sans font — remove from both HTML and CSS
4. Blue-tinted HSL color tokens — all current `--primary: 227 88% 58%` etc.
5. The top header bar with search and route title — replaced by in-content breadcrumb + `<h1>`
6. The `project-step-nav.tsx` linear step navigation — replaced by grouped sidebar nav
7. The "deep link guard" overlay — replaced by toast notifications
8. The `NIPE` uppercase tracking label — no uppercase brand labels
9. The `DashboardSquare02Icon` logo — replaced with an `N` monogram or wordmark
10. Body radial gradient background — replaced with flat `oklch(0.145 0 0)`
11. Light mode CSS variables — this app is dark-only now
12. The `--shadow-soft` custom token — removed entirely
13. The `nipe-shell-frame` grid layout with `112px` top row — replaced by standard sidebar+content flex layout
14. All `rounded-[1.7rem]` or `rounded-2xl` on layout containers — layout is flat, no rounding on shell

---

## SECTION 9 — NEW DEPENDENCIES

Install these before starting implementation:

```bash
# In /Users/elhamdev/work/nipe/frontend:
npm install @fontsource/geist @fontsource/geist-mono
```

Or use Google Fonts CDN in `index.html`:
```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&display=swap" rel="stylesheet" />
```

If `framer-motion` is not installed:
```bash
npm install framer-motion
```

---

## SECTION 10 — BACKEND API NOTES

No structural backend changes are required for the redesign. All needed data is already served by existing endpoints:

| New UI Need | Existing Endpoint |
|---|---|
| Dashboard project grid | `GET /api/dashboard/project-control-panel/projects` |
| Project detail | `GET /api/projects/{project_id}` |
| Project status | `GET /api/projects/{project_id}/setup-status` |
| Workspace summary | `GET /api/projects/{project_id}/workspace-summary` |
| Mode selection | `PUT /api/projects/{project_id}/mode` |
| Character table | `GET /api/projects/{project_id}/characters` |
| Voice mapping | `GET /api/projects/{project_id}/voices` |
| Pipeline config | (existing pipeline endpoints) |
| Run monitor | `GET /api/projects/{project_id}/runs/{run_id}` |
| Exports | `GET /api/projects/{project_id}/exports/{run_id}.json` |
| Analytics charts | `GET /api/projects/{project_id}/runs/{run_id}/tension-graph` etc. |

One possible lightweight addition (only if needed):
- `GET /api/projects` — simple list without the full control panel metadata, if the dashboard endpoint returns too much unnecessary data for a simple grid

---

## SECTION 11 — TASK LIST FOR SRS CHECKLIST

Add this entire section to `SRS_Expanded_Implementation_Checklist.md` as a new section after the existing last section. Use the following exact format:

```markdown
---

## 14. ElevenLabs-Inspired Full Redesign (Ref: CODEX_REDESIGN_PROMPT.md)

> WARNING: These tasks constitute a COMPLETE REDESIGN. None of the existing design elements
> survive. Every task must be completed before the redesign is considered done.
> Do not skip tasks. Do not treat these as enhancements.

### 14.1 Design System Foundation
- [ ] [RD-001] Install Geist and Geist Mono fonts; remove Manrope and Plus Jakarta Sans from all imports and HTML.
- [ ] [RD-002] Completely replace globals.css: remove all current tokens, write new ElevenLabs-inspired dark-first oklch token set, new radius, new border convention (white/10%), dark-only (remove light mode variables), new animation keyframes (fade-in, fade-in-up, fade-in-scale).
- [ ] [RD-003] Remove all nipe-* custom CSS classes (nipe-shell-frame, nipe-panel, nipe-sidebar, nipe-min-header, nipe-search-shell, nipe-logo-chip) from globals.css and all component files.
- [ ] [RD-004] Update Tailwind theme configuration to use new oklch tokens and Geist font stack.
- [ ] [RD-005] Update all Shadcn UI base components (button, card, input, badge, separator, table) to reflect new token values — no visual from old design survives.

### 14.2 App Shell Architecture
- [ ] [RD-006] Rewrite main-shell.tsx: remove nipe-shell-frame floating card, remove top header bar, implement flat full-screen dark layout with fixed left sidebar (240px/64px), no grid-based frame.
- [ ] [RD-007] Implement new global sidebar component with logo area (N monogram), nav items (icon + label), group labels, bottom user area, collapse animation (240px ↔ 64px, duration-200).
- [ ] [RD-008] Delete project-step-nav.tsx entirely; replace with new project-workspace sidebar component (grouped nav: Setup, Configuration, Operations, Insights, Manage).
- [ ] [RD-009] Implement simplified lock states in project sidebar: locked items show inline lock icon + sonner toast on click ("Complete [step] first"), no overlay, no deep-link guard banner.
- [ ] [RD-010] Remove route title header bar; implement in-content breadcrumb (muted small text) at top of each workspace page content area.

### 14.3 Landing Page
- [ ] [RD-011] Generate AI hero image using imagegen skill (prompt: dark SaaS dashboard UI mockup, character relationship graph, near-black, white text, minimal). Save to frontend/public/images/hero-visual.png.
- [ ] [RD-012] Generate AI feature images using imagegen skill: character list panel, analytics chart panel, how-it-works illustration. Save to frontend/public/images/.
- [ ] [RD-013] Rewrite landing-navbar.tsx: transparent sticky nav, logo left, links center (Features · How it Works · Modes · Export), CTAs right (Sign in ghost + Get started white), blur-on-scroll behavior.
- [ ] [RD-014] Rewrite hero-section.tsx: large centered headline "Bring Any Story to Life", sub-headline, 2 CTAs, 2 ambient blob backgrounds (faint blue + faint orange at ~7% opacity, 600px blur), hero visual image below CTAs.
- [ ] [RD-015] Rewrite/replace stats-section.tsx with trust-strip.tsx: infinite scrolling marquee of format/feature tags (TXT · EPUB · Markdown · Audiobook · etc.), paused on hover.
- [ ] [RD-016] Rewrite features-section.tsx as features-bento.tsx: 3-column bento grid of 6 capability cards (Character Extraction, Voice Mapping, Pipeline Runs, Analytics, Pronunciation, Export), each with icon + title + description + subtle card surface.
- [ ] [RD-017] Replace integrations-section.tsx with how-it-works.tsx: 3-step horizontal numbered sequence (Upload → Configure → Export) with descriptive text per step.
- [ ] [RD-018] Rewrite cta-section.tsx: full-width dark banner, "Ready to process your first manuscript?", single "Create your first project" white CTA.
- [ ] [RD-019] Rewrite footer-section.tsx: 4-column link grid (Product, Resources, Modes, Legal), bottom bar with copyright.
- [ ] [RD-020] Delete create-project-dialog.tsx from landing components (project creation moves to /projects/new wizard route, no dialog on landing).
- [ ] [RD-021] Assemble landing-page.tsx with new section order: Navbar → Hero → TrustStrip → FeaturesBento → HowItWorks → CTABanner → Footer.

### 14.4 Dashboard Page
- [ ] [RD-022] Rewrite dashboard-page.tsx: page heading "My Projects" + "New Project" button (top right), filter tabs (All · Active · Archived), search input, 3-column project grid.
- [ ] [RD-023] Create new project-card.tsx component: dark card surface, project name, mode badge, status dot indicator (green/amber/red/gray), relative date, hover lift effect, archive icon on hover.
- [ ] [RD-024] Implement dashboard empty state: centered book icon, "No projects yet" heading, "Create a project" CTA.
- [ ] [RD-025] Remove all summary stats, quota bars, and control panel telemetry from dashboard (these were part of the old design — none survive).

### 14.5 Project Creation Wizard
- [ ] [RD-026] Rewrite project-new-page.tsx as a 3-step centered wizard (max-w-xl): step indicator dots at top, Step 1 Name/Description, Step 2 Upload Source (tabs + drag-drop), Step 3 Mode selection (2x2 grid), Back/Continue navigation, Cancel → /dashboard.
- [ ] [RD-027] Wire wizard Step 1 to POST /api/projects/drafts, Step 2 to POST /api/projects/{id}/ingest/{type}, Step 3 to PUT /api/projects/{id}/mode.
- [ ] [RD-028] Implement drag-and-drop file area in wizard Step 2 with file type switching (TXT/EPUB/Markdown) and "Paste text" fallback textarea toggle.

### 14.6 Project Workspace Shell
- [ ] [RD-029] Rewrite project-workspace-shell.tsx: project name + "← All Projects" back link at sidebar top, grouped nav sections (Setup, Configuration, Operations, Insights, Manage), project-workspace-shell replaces the old shell for all /projects/:id/* routes.
- [ ] [RD-030] Remove project-workspace-home-page.tsx and project-setup-page.tsx; redirect /projects/:id (index) to /projects/:id/overview.

### 14.7 Workspace Pages — Individual Redesigns
- [ ] [RD-031] Rewrite project-overview-page.tsx: in-content breadcrumb, 2-col stats grid (chapters, characters, last run, export readiness), activity timeline feed below, "Continue Setup" CTA if incomplete.
- [ ] [RD-032] Rewrite project-mode-page.tsx: in-content breadcrumb, same 2x2 mode card grid as wizard, currently selected mode highlighted, "Save Mode" button appears only on change.
- [ ] [RD-033] Rewrite project-characters-page.tsx: full-width flat table (Name, Aliases, Gender, Dialogue Count, Actions), hover row highlight, floating sticky action bar at bottom (Extract, Import, Finalize), empty state with "Extract from text" CTA.
- [ ] [RD-034] Rewrite voice mapping page (project-setup-page.tsx → new voice-mapping layout): split 40/60 layout — character list left, voice assignment panel right, no heavy cards.
- [ ] [RD-035] Rewrite project-pipeline-setup-page.tsx: flat settings form layout with sections (General, LLM Config, Normalization, Segmentation), dividers between settings, "Save Configuration" + "Start Run" buttons at bottom.
- [ ] [RD-036] Rewrite project-run-monitor-page.tsx: full-width progress bar (h-1, animated if running), run status header (ID, status badge, start time, duration), stage timeline list with status icons, state-appropriate action buttons (Cancel/Rerun/Recover).
- [ ] [RD-037] Rewrite project-export-page.tsx: run selector tabs (completed runs, newest first), per-run download cards (JSON + CSV), minimal download center layout, no decoration.
- [ ] [RD-038] Rewrite project-dashboards-page.tsx: 2-column chart grid (Tension Graph, Polarity Graph, Character Co-occurrence, Character Analytics table), each in bg-card border rounded-lg container.
- [ ] [RD-039] Rewrite project-settings-page.tsx: grouped sections (General with inline name edit, LLM with provider/model selectors, Danger Zone with archive/delete and confirmation dialogs).

### 14.8 Review Pages
- [ ] [RD-040] Redesign project-speaker-review-page.tsx and project-emotion-review-page.tsx and project-low-confidence-review-page.tsx to match new flat layout pattern (in-content breadcrumb, table or card list, no old shell decoration).

### 14.9 Cleanup and Validation
- [ ] [RD-041] Audit every file in frontend/src for any surviving reference to old CSS classes (nipe-*, Manrope, Plus Jakarta Sans, HSL tokens, blue primary) and remove them.
- [ ] [RD-042] Audit every page for surviving old text labels, descriptions, and button copy — replace all with new ElevenLabs-inspired tone (clean, direct, product-focused).
- [ ] [RD-043] Verify Playwright visual baselines are invalidated and re-captured against new design (PW-028, PW-029 must be re-run after redesign).
- [ ] [RD-044] Verify all SWR hooks, API calls, and Zustand stores still work correctly after page rebuilds — no data flow regressions.
- [ ] [RD-045] Final cross-browser visual check: Chrome, Safari, Firefox — confirm dark theme renders correctly, no HSL/oklch fallback issues, fonts load correctly.
```

---

## SECTION 12 — ACCEPTANCE CRITERIA

The redesign is complete when ALL of the following are true:

1. **Zero surviving old design elements**: No Manrope font. No blue primary. No rounded shell frame. No uppercase brand labels. No `nipe-*` classes. No body gradient.
2. **Dark-only**: The app renders only in dark mode. No light mode toggle. No light mode CSS variables.
3. **ElevenLabs visual parity**: A person familiar with ElevenLabs' app should say "this is clearly inspired by ElevenLabs" when seeing Nipe for the first time.
4. **Landing page is visually complete**: All sections present, AI images embedded, all links working.
5. **Dashboard shows project grid**: Cards render with correct data from the API, empty state works.
6. **Project creation wizard works end-to-end**: All 3 steps, all API calls, success navigates to project overview.
7. **Project workspace is navigable**: All sidebar items route correctly, locked items show toast, breadcrumb is present on all pages.
8. **All 9 workspace pages are redesigned**: No page uses the old layout or old components.
9. **All `RD-*` tasks in the checklist are marked `[x]`**.
10. **No Playwright regressions** on data flow (visual baselines need re-capture, data assertions must pass).

---

## FINAL NOTE TO CODEX AGENT

You have access to the `imagegen` skill. Read it at `/Users/elhamdev/.cursor/skills/imagegen/SKILL.md` before generating any images. Generate images early (tasks RD-011, RD-012) so they are available for later page assembly.

Remember: **this is not an enhancement**. If any piece of the old Nipe UI survives, the task is not done. The bar is ElevenLabs parity — not "improved Nipe." Treat every file you touch as if you are building it from scratch with only the API contracts preserved.

Start by adding all `RD-*` tasks to `SRS_Expanded_Implementation_Checklist.md`, then execute from `RD-001` forward.
