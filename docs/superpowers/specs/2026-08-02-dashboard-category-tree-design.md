# Dashboard category tree design

## Goal

Make the existing spending breakdown easier to scan by presenting each parent
category as an expandable group with its child categories nested beneath it.

## Scope

- Keep the current monthly dashboard route, data service, and income/expense
  filter.
- Keep a top-level category without children as a single row.
- Render each parent category as a native expandable row whose total and share
  represent its rolled-up spending.
- Render child categories beneath the parent with clear tree indentation,
  individual totals, and proportional meters.
- Preserve the active Income or Expenses filter while showing or hiding whole
  category groups.
- Add the supplied Lunch Money mascot beside the dashboard welcome heading as a
  decorative local asset.

## Design

`fetch_category_spending()` already returns top-level categories with their
children and parent rollups. The dashboard template will use that existing
shape: a `details` element is the parent-group control and child rows are its
contents. The summary remains the only interactive element, so keyboard and
screen-reader users get the native expanded/collapsed semantics without a
custom state store.

Child meters use the same income or expense total as the surrounding parent
row, so their length is comparable with every category shown in that view. The
parent's meter continues to show the roll-up total. CSS supplies the visual
indentation and connector; no new dashboard API or persistence is needed.

The supplied mascot is downloaded into the dashboard static assets and rendered
beside the welcome heading with empty alternative text. This preserves the
heading as the page's accessible name and avoids a dependency on an external
request during dashboard rendering.

## Error handling

Existing unavailable and empty states remain unchanged. A parent category with
an empty child list renders as a normal standalone row.

## Verification

- Add rendering assertions for a parent category and its child row.
- Verify the dashboard test suite and project formatting, linting, type
  checking, and tests through the Taskfile.
