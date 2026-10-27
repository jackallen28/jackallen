# CircuitPathways

A responsive, interactive showcase for PiPath and ArduinoPath, made for Banyule Nillumbik Tech School.

## Run locally

No build step or package installation is required. From this directory:

```sh
python3 -m http.server 3000 --bind 0.0.0.0
```

The site uses local fonts, school branding, and the three supplied captioned walkthrough recordings. Videos load only when a visitor opens a walkthrough. Serve over HTTP rather than opening `index.html` directly.

## Experience

- Floating glass-effect BNTS logo and two pathway choices.
- A three-stage traffic-light or ultrasonic-sensor taster: connect, choose support, run.
- Beginner, Moderate and Advanced scaffolding, progressive hints, and blocks/text views.
- A live traffic-light sequence and distance slider; simplified demonstrations, not code execution or hardware simulation.
- Actual app screenshots with interactive callouts and original captioned videos.
- Full-app project cards and links to the programs; these projects do not open additional website games.

Supports keyboard navigation, reduced motion, mobile layouts and native accessible video controls. No analytics, accounts, backend, or external runtime requests.

## Assets

School logos are copied from the supplied PiPath repository. Recordings were supplied by the project owner; screenshot stills are extracted from those recordings. Self-hosted Manrope, DM Sans and Playfair Display fonts use the SIL Open Font License; licenses are included in `assets/fonts/`.

## Deploy

The site can be published directly with GitHub Pages:

1. Open [Settings → Pages](https://github.com/jackallen28/jackallen/settings/pages).
2. Under **Build and deployment**, choose **Deploy from a branch**.
3. Select **master** and **/ (root)**, then **Save**.

After GitHub completes the deployment, the site is available at:

**https://jackallen28.github.io/jackallen/**

The `.nojekyll` file tells Pages to serve the static files directly. Further pushes to `master` update the site automatically once Pages is enabled.

For another static host, publish this directory and keep `assets/` alongside `index.html`. MP4 files total about 68 MB; the host must permit these file sizes and ideally support byte-range video requests. Deploying the showcase does not change the teaching applications.
