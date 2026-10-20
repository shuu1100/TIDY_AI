---
name: Warm Desktop File Utility
colors:
  surface: '#fbf9f3'
  surface-dim: '#dbdad4'
  surface-bright: '#fbf9f3'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f5f4ed'
  surface-container: '#efeee7'
  surface-container-high: '#e9e8e2'
  surface-container-highest: '#e4e3dc'
  on-surface: '#1b1c18'
  on-surface-variant: '#4e4636'
  inverse-surface: '#30312d'
  inverse-on-surface: '#f2f1ea'
  outline: '#807664'
  outline-variant: '#d1c5b0'
  surface-tint: '#785a00'
  primary: '#785a00'
  on-primary: '#ffffff'
  primary-container: '#e5b94f'
  on-primary-container: '#634a00'
  inverse-primary: '#edc156'
  secondary: '#5e5f57'
  on-secondary: '#ffffff'
  secondary-container: '#e3e3d8'
  on-secondary-container: '#64655c'
  tertiary: '#136b4d'
  on-tertiary: '#ffffff'
  tertiary-container: '#7fcfaa'
  on-tertiary-container: '#00593e'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffdf9b'
  primary-fixed-dim: '#edc156'
  on-primary-fixed: '#251a00'
  on-primary-fixed-variant: '#5a4300'
  secondary-fixed: '#e3e3d8'
  secondary-fixed-dim: '#c7c7bd'
  on-secondary-fixed: '#1b1c16'
  on-secondary-fixed-variant: '#464740'
  tertiary-fixed: '#a2f3cc'
  tertiary-fixed-dim: '#87d7b1'
  on-tertiary-fixed: '#002114'
  on-tertiary-fixed-variant: '#005138'
  background: '#fbf9f3'
  on-background: '#1b1c18'
  surface-variant: '#e4e3dc'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: -0.005em
  body-lg:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-lg:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.02em
  code-tabular:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 0.75rem
  gutter-compact: 0.5rem
  margin: 1rem
  margin-window: 0.5rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
---

## Brand & Style

This design system is engineered for a focused, desktop-grade local file management and productivity utility. Rooted in the reliable, utilitarian ergonomics of desktop file explorers, it merges clean functionalism with an organic, warm paper-and-canvas tactile clarity.

### Personality & Demographics
- **Tone:** Methodical, unhurried, trustworthy, tactile, and quiet.
- **Audience:** Knowledge workers, developers, archivists, and power users who demand lightning-fast spatial orientation and distraction-free organization for local storage.
- **Atmospheric Stance:** It eliminates gratuitous visual noise, neon saturated accents, floating glass sheets, and decorative complexity. It relies on subtle surface changes, clean 1px division, and deliberate chromatic cues reminiscent of archival parchment and classic manila folders.

### Design Movement
**Warm Functionalism / Desktop Utility Minimalism:** A fusion of modern Swiss information architecture and desktop operating system utility conventions. Structural density is prioritized over decorative padding, relying strictly on warm neutral surfaces, crisp micro-borders, and disciplined folder amber accents to guide navigational momentum.

## Colors

The palette grounds the interface in quiet, paper-like warm neutrals punctuated by purposeful archival tones.

### Surface Hierarchy
- **Canvas / Root Background (`#F7F6F2`):** Surrounds the application window, title bar, and outer boundaries, establishing a warm, natural base.
- **Sidebar & Navigation Tiers (`#F0EFE9`):** A slightly deeper warm stone tint providing immediate spatial grounding for directory trees and drives.
- **Workspace, File Tables & Panes (`#FFFFFF`):** High-clarity white reserved for the active file grid, detail cards, and content inspectors.
- **Borders & Dividers (`#E5E3DC`):** Consistent 1px boundary line separating views, column headers, and structured rows without high contrast jarring.

### Chromatic Accents & Feedback
- **Folder Golden Amber (`#E5B94F`):** The functional primary. Applied strictly to directory nodes, primary action calls, folder icons, and active segment tabs.
- **Primary Ink (`#292A26`):** Deep charcoal delivering optimal contrast for file names, column titles, and critical metadata.
- **Secondary Ink (`#77786F`):** Muted warm slate for byte sizes, modified timestamps, breadcrumb dividers, and inactive state descriptions.
- **Success (`#2F8060`):** Muted forest green for batch completion, disk integrity passes, and sync states.
- **Alert / Destructive (`#C64C4C`):** Restrained archival red for delete confirmations, disk capacity thresholds, and path collision errors.
- **Selection & Focus Tint (`rgba(229, 185, 79, 0.12)`): Translucent golden wash applied to highlighted rows and lassoed multi-selections.

## Typography

The typography uses Inter across all hierarchical levels to ensure pixel-level legibility, compact line-height discipline, and native OS desktop familiarity.

### Editorial Guidelines
- **Tabular Figures:** Numbers representing file sizes, modification dates, and sector counts strictly use tabular figures (`fontFeatureSettings: "'tnum' on"`) to maintain optical vertical alignment down data columns.
- **Hierarchy Restraint:** Desktop utility views must avoid excessive headline scaling. The maximum workspace heading scales at 24px (`headline-lg`), keeping density high and scroll distance minimal.
- **Labels vs Body:** Directory paths and table column headers utilize `label-md` or `label-sm` with tight capitalization and slight positive tracking, distinguishing metadata labels from file titles.

## Layout & Spacing

The layout philosophy follows a structured split-pane multi-column model optimized for high-density file operations and horizontal scanning.

### Layout Model
- **Structural Composition:** Three distinct spatial zones:
  1. **Navigation Sidebar:** Fixed/collapsible column (width: 220px–260px) anchored with `#F0EFE9`.
  2. **Main Workspace:** Flexible central canvas anchored with `#FFFFFF`, housing dynamic breadcrumbs, action toolbars, and the primary file list/grid.
  3. **Inspector Pane:** Contextual right panel (width: 280px–320px) bordered by 1px lines for file preview, EXIF info, and metadata editing.
- **Window Padding:** Consistent 8px (`margin-window`) padding surrounding external window perimeters when unmaximized.
- **Grid Structure:** The main workspace operates on a dynamic horizontal column-header layout with resizable split gutters (12px default).

### Form Factors & Adaptation
- **Desktop (Default, >1024px):** Three-pane layout active simultaneously. Breadcrumbs fully expanded with direct path inline editing.
- **Compact Desktop / Tablet View (768px - 1023px):** Inspector collapses to an off-canvas slide-over drawer; sidebar switches to icon-and-pinned nodes only.
- **Target Touch Adaptation:** If pointer type is coarse, row heights step up from dense 28px to comfortable 38px, while internal cell padding shifts from `space-xs` to `space-sm`.

## Elevation & Depth

This design system explicitly rejects deep multi-layered drop shadows, blur backdrops, and artificial glowing highlights. Spatial organization is achieved through planar color layering and hairline containment.

### Surface Tiers
- **Base Layer (0dp):** System frame and outer canvas (`#F7F6F2`).
- **Sidebar Inset (0dp):** Anchored flush on the canvas with a single right border `1px solid #E5E3DC`.
- **Active Workspace Pane (0dp):** Solid white `#FFFFFF` bounded by `1px solid #E5E3DC`.
- **Flyouts, Menus & Tooltips (Elevation 1):** Floating elements (context menus, drive-selector dropdowns) use a single hairline border (`1px solid #E5E3DC`) paired with an ultra-subtle, non-diffuse ambient shadow:
  `box-shadow: 0 2px 4px rgba(41, 42, 38, 0.04), 0 1px 2px rgba(41, 42, 38, 0.02)`.
- **Modal Dialogs (Elevation 2):** Overlays use an understated backdrop (`rgba(41, 42, 38, 0.25)`) and a tight enclosure:
  `box-shadow: 0 8px 16px rgba(41, 42, 38, 0.06), 0 2px 4px rgba(41, 42, 38, 0.04)`.

## Shapes

The design uses tight, disciplined radii (`roundedness: 1`) to preserve the crisp aesthetic of an operating system desktop utility while mitigating harsh, clinical sharp points.

### Radius Assignments
- **Core Elements (0.25rem / 4px):** Primary buttons, directory tree selection strips, search inputs, breadcrumb pills, and file table selection states.
- **Card Enclosures & Popovers (0.5rem / 8px):** Modals, inspector preview containers, context menus, and drive card widgets.
- **Pills / Status Dots (Full 9999px):** File counter badges and batch activity indicators only.

## Components

### Buttons
- **Primary:** Solid `#E5B94F` background, `#292A26` label, `4px` radius, `0 1px 1px rgba(0,0,0,0.04)` elevation. Hover shifts to `#D6A93F`. Active presses drop 0.5px vertically.
- **Secondary / Toolbar:** Transparent background, `1px solid #E5E3DC`, `#292A26` label. Hover activates `#F0EFE9`.
- **Ghost:** No border. Soft hover wash using `#F0EFE9`. Used for title bar actions, sort headers, and icon toggles.

### Breadcrumb Navigation Bar
- Structured horizontally across the top of the main file list.
- Encased in a `32px` tall container with `#FFFFFF` background and `1px solid #E5E3DC` perimeter.
- Folders appear as inline clickable segments separated by a minimalist `/` or `›` in `#77786F`.
- Double-clicking empty breadcrumb space toggles it into a standard editable URI text input.

### File Tables & List Views
- **Header:** Sticky top row in `#F7F6F2`, `1px solid #E5E3DC` bottom rule, uppercase `label-sm` text in `#77786F`.
- **Row Heights:** 30px compact (default), 40px relaxed.
- **Row States:**
  - *Default:* `#FFFFFF` background.
  - *Hover:* `#F7F6F2`.
  - *Selected:* `rgba(229, 185, 79, 0.14)` with an active `2px` left border in `#E5B94F`.
  - *Cut / Hidden:* 50% opacity.
- **Alignment:** Names left-aligned; modification dates, file types, and sizes use `code-tabular` right-aligned.

### Directory Sidebar Tree
- Nested tree nodes indented by `12px` per directory tier.
- Left-aligned chevron toggles accompanied by a standard `#E5B94F` folder icon.
- Unselected folders render in `#292A26`; selected tree rows apply `#F7F6F2` background with `#292A26` bold weight.

### Input Fields & Search
- Surface: `#FFFFFF`. Border: `1px solid #E5E3DC`.
- Focus State: Border transitions to `#292A26` with no glowing halo.
- Leading search icon in `#77786F` with an optional inline shortcut badge (`Ctrl + F`) rendered in `label-sm` muted gray.

### Checkboxes & Selection Controls
- Base box: `14px x 14px`, `2px` radius, border `1px solid #77786F`, background `#FFFFFF`.
- Checked: Fill `#E5B94F`, border `#E5B94F`, with a centered `#292A26` check glyph.

### Storage Usage Cards
- Clean panels in `#FFFFFF` framed with `1px solid #E5E3DC`.
- Segmented progress bar: Background track in `#F0EFE9` (height: 6px, radius: 3px), filled with `#E5B94F` (used) and `#2F8060` (free/system).
- Space summaries utilize `code-tabular` for clean visual comparisons.