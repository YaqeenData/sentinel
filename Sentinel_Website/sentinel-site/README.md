# Sentinel Website

Static product + engineering case-study website for Sentinel. Designed to live inside the main Sentinel repository under `sentinel-site/` and deploy independently to GitHub Pages.

## Stack

- React + TypeScript
- Vite
- HashRouter (works cleanly under GitHub Pages project URLs)
- CSS variables for light/dark mode
- No backend required

## Run locally

```bash
cd sentinel-site
npm install
npm run dev
```

## Build

```bash
npm run build
```

The production site is created in `sentinel-site/dist/`.

## Where to edit content

- `src/data/site.ts`: **all links** (`LIVE_DEMO_URL`, `REPOSITORY_URL`), team data, demo video/poster paths and the architecture image. The ngrok live-demo URL is changed here and only here; every button reads it through `LiveDemoLink`.
- `src/data/content.ts`: all home-page copy (snapshot, Aisha scenario, resources, downstream value, product journey, the five checks, architecture notes, scope).
- `src/pages/HomePage.tsx`: layout only. `src/refine.css` holds the styles for the sections added in this update (`rf-*`), on top of `styles.css` and `redesign.css`.

## Assets

- `public/assets/screenshots/`: real dashboard screenshots (webp, 1920x1080).
- `public/assets/demo/sentinel-product-demo.mp4`: the 97 s demo with on-screen commentary (muted-free, controls, no autoplay) and its poster.
- `public/assets/architecture/sentinel-architecture-final.webp`: the final architecture diagram from the case study.

## Deployment

Unchanged: Vite `base: '/sentinel/'` and HashRouter for GitHub Pages.
