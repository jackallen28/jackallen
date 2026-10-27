# Program finder: "Which program suits my class?"

A single self-contained page for teachers (`program-finder.html`). Seven short questions about the
class produce a recommended project, platform and version, a stretch option, curriculum links and a
copyable summary for a booking request. Built from `Program_Finder_Build_Plan.md`.

- One file, all CSS and JS inline. No network requests, cookies or storage; refreshing clears answers.
- All content and scoring lives in the JSON block `#finder-config` at the top of the file.
- Styled with the Banyule Nillumbik Tech School logo and colours; light and dark themes.
- Add `?debug=1` to the address to see every variant's score.

## Tuning notes

The plan's formulas are implemented as written, plus two small additions needed to meet the
acceptance personas (both are config values in `scoring`):

- `platformFamiliarityBonus` (1.5): a bonus for a platform the class has already used.
- `codingGapPenalty` (3 per point) with a per-variant `minCoding`: stops block-coding classes being
  sent straight to typed-code platforms.

## Still to confirm

- Booking link (`meta.bookingUrl`; the button stays hidden until it is set).
- Dotpoints for variants other than the three seeded in the plan are drafts for teachers to check.
- Curriculum wording should be checked against `Circuit_Pathways_Curriculum_Links.xlsx`.
- The logo is the SVG used in BNTS_FidgetCAD; swap in the official asset if one is preferred.

## Tests

`node program-finder/test-personas.cjs` (needs Playwright) checks the eight personas, the Year 7-8
flow, the no-scroll layout at 1366x768, and that nothing is stored or fetched.
