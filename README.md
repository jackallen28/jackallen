# Sparkbench

Sparkbench is a browser-based Arduino prototyping workspace that combines a
visual module canvas, MakeCode-style logic blocks, and a conversational AI
copilot.

## Requirements

- [Node.js](https://nodejs.org/) 18 or newer
- A modern browser such as Chrome, Edge, Firefox, or Safari

There are no npm packages to install. The application and its development
server use only built-in browser and Node.js APIs.

## Render the app locally

From the repository root, start the included development server:

```bash
npm run dev
```

Open <http://localhost:4173> in your browser. To use a different port, pass it
after `--`:

```bash
npm run dev -- 8080
```

The server prints the exact URL when it is ready. Stop it with <kbd>Ctrl</kbd> +
<kbd>C</kbd>.

### Python alternative

If Node.js is unavailable, the site can also be served as static files:

```bash
python3 -m http.server 4173
```

Opening `index.html` directly may work, but using a local server more closely
matches deployment behavior and avoids browser restrictions on local files.

## Run automated checks

Run the dependency-free verification suite:

```bash
npm test
```

The suite checks that:

- the JavaScript has valid syntax;
- the expected HTML, CSS, and JavaScript assets are present;
- local stylesheet and script references resolve;
- HTML IDs are unique; and
- the controls required by `app.js` exist in the page.

## Host on Render

The repository includes a Render Blueprint in `render.yaml`. It configures a
static site, runs the production build, publishes only the contents of `dist/`,
and enables pull-request preview environments.

### Option 1: Deploy the Blueprint (recommended)

1. Push this repository to GitHub, GitLab, or Bitbucket.
2. Sign in to the [Render Dashboard](https://dashboard.render.com/).
3. Select **New +** and then **Blueprint**.
4. Connect the repository containing Sparkbench.
5. Render will detect `render.yaml`. Review the `sparkbench` service and select
   **Apply**.
6. Wait for the build and deploy to complete, then open the `onrender.com` URL
   shown on the service page.

Future pushes to the connected branch will automatically rebuild and deploy the
site. Render also creates previews for pull requests because the Blueprint sets
`pullRequestPreviewsEnabled: true`.

### Option 2: Create the static site manually

If you do not want to use the Blueprint, select **New + → Static Site**, connect
the repository, and enter:

| Render setting | Value |
| --- | --- |
| Language | `Node` |
| Build command | `npm run build` |
| Publish directory | `dist` |

No environment variables are required. Before deploying, reproduce Render's
production build locally:

```bash
npm run build
npx serve dist
```

If `npx serve` is unavailable, inspect the same output without downloading a
package:

```bash
cd dist
python3 -m http.server 4173
```

Do not commit `dist/`; Render creates it from the source files during each
deployment.

## Manual interaction checklist

After starting the app, verify these user flows:

1. **Search and filter:** Search for `pump`, then clear the search and switch
   among Sensors, Outputs, and Logic.
2. **Drag and drop:** Drag a module from the library onto the dotted canvas. A
   new module card should appear where it was dropped.
3. **Canvas tools:** Use the `−`, `+`, and fit controls and confirm the zoom
   percentage changes. Use **Clear** and cancel once before confirming.
4. **Prototype run:** Select **Run prototype** and confirm that an upload-success
   notification appears.
5. **Prompt flow:** Enter a prototype instruction in the AI Copilot and submit
   it. The user message should appear immediately, followed by an applied-change
   response.
6. **Responsive layout:** Resize below 1100px and 760px to verify the compact
   canvas layouts.

## Project structure

```text
index.html         Application markup and example plant-watering flow
styles.css         Workspace, component, and responsive styling
app.js             Drag/drop, filtering, canvas, run, and prompt interactions
scripts/serve.mjs  Dependency-free local static server
scripts/build.mjs  Creates the production-ready dist directory
scripts/verify.mjs Dependency-free automated checks
render.yaml        Render static-site Blueprint
```

This is currently a front-end prototype. Canvas changes are kept in browser
memory and the upload/copilot experiences are simulated; no Arduino is flashed
and no prompt is sent to a remote model yet.
