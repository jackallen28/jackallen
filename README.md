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
scripts/verify.mjs Dependency-free automated checks
```

This is currently a front-end prototype. Canvas changes are kept in browser
memory and the upload/copilot experiences are simulated; no Arduino is flashed
and no prompt is sent to a remote model yet.
