# Allentronics

Marketing site for Allentronics — an education studio led by Jack Allen, built with
[Astro](https://astro.build) and [Tailwind CSS v4](https://tailwindcss.com).

## Stack

- **Astro** (static output) with a single shared `Layout` (header + footer) reused on every page.
- **Tailwind CSS v4**, configured in `src/styles/global.css` (`@theme`) — no separate `tailwind.config` file needed.
- **@astrojs/sitemap** for an auto-generated sitemap.
- Contact form wired to **[Web3Forms](https://web3forms.com)** (client-side fetch, no backend/server required).

## Run locally

```bash
npm install
npm run dev      # http://localhost:4321
```

Other scripts:

```bash
npm run build     # type-check (astro check) + production build to dist/
npm run preview   # preview the production build locally
```

## Project structure

```
src/
  components/     Header, Footer, Button, SectionLabel, ImagePlaceholder, EducationPage
  layouts/         Layout.astro — shared <head>, header, footer, scroll-reveal script
  lib/site.ts      Site-wide constants: nav, contact details, primary CTA
  pages/
    index.astro                       Home
    manufacturing/index.astro         Manufacturing services (combined)
    education/
      3d-printing-cad.astro
      machine-leasing.astro
      ai-tools-in-education.astro
      microbits-electronics.astro
    contact.astro
  styles/global.css   Tailwind import + design tokens (font, colors, tracking) + .reveal animation
public/           Static files: favicon.svg, og-image.svg, robots.txt
```

## Editing copy

Page copy lives directly in each `.astro` file under `src/pages/` — headings, intro
paragraphs and content blocks are plain strings/arrays near the top of each file. Site-wide
details (nav labels, phone, email, socials, the primary CTA) live in `src/lib/site.ts`.

## Swapping images

Every photo slot is a clearly-labelled `<ImagePlaceholder label="..." />` component (a
diagonal-hatched box with a caption). To swap one for a real photo:

1. Drop the image file into `public/images/`.
2. Replace the `<ImagePlaceholder ... />` usage with a normal `<img>` (or Astro's `<Image>`
   component from `astro:assets` for automatic optimisation), e.g.:

   ```astro
   <img src="/images/nyikina-map.jpg" alt="Nyikina Country 3D map" class="aspect-[4/3] w-full rounded-lg object-cover" />
   ```

Keep photos large, edge-to-edge, and shot on a clean background (see the brief's photo
checklist) — that's the single biggest lever for a premium look on this design system.

## Contact form setup (Web3Forms)

1. Get a free access key at [web3forms.com](https://web3forms.com) (no account needed to start).
2. In `src/pages/contact.astro`, replace `YOUR_WEB3FORMS_ACCESS_KEY` with your real key.
3. That's it — submissions arrive by email, no server required. (Alternative: swap the
   `action`/fetch target for Formspree or a Cloudflare Pages Function if preferred.)

## Deployment (Cloudflare Pages)

1. Push this repo to GitHub.
2. In the Cloudflare dashboard: **Workers & Pages → Create → Pages → Connect to Git**.
3. Build settings:
   - **Build command:** `npm run build`
   - **Build output directory:** `dist`
4. Add the custom domain `allentronics.com.au` under the Pages project's **Custom domains** tab.

(Netlify/Vercel work the same way — same build command and output directory.)

## Accuracy notes

- Jack Allen is a **Master of Teaching candidate** at RMIT — never described as a
  "qualified" or "registered" teacher.
- No testimonials, client names, pricing or statistics are invented. Machine-leasing pricing
  and a few image slots are left as marked placeholders — fill them from real data before
  publishing.
- Verify `info@allentronics.com` against the `allentronics.com.au` domain before publishing
  (flagged in the original brief).
