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

Most project/team links are centralized in:

```text
src/data/site.ts
```

Update:

- `liveDashboardUrl`
- `demoVideoUrl`
- `repositoryUrl`
- the four team members
- LinkedIn links
- portfolio links

## Assets

Brand assets:

```text
public/assets/brand/sentinel-logo.svg
public/assets/brand/sentinel-logo.png
```

The provided Sentinel logo is already installed.

The current site deliberately uses designed placeholders for:

- final architecture diagram
- dashboard screenshots
- incident screenshots
- product/demo video
- team photos if you later want them

Replace the placeholder components once the final assets exist.

## Light / dark mode

The site respects the visitor's system theme the first time they visit and stores their manual selection in `localStorage` under:

```text
sentinel-theme
```

The theme palette is defined at the top of:

```text
src/styles.css
```

## GitHub Pages

A ready-to-use workflow is included at the repository-root path:

```text
.github/workflows/sentinel-site-pages.yml
```

When these files are copied into the Sentinel repository, GitHub Actions will build `sentinel-site/` and publish its `dist/` directory to Pages after pushes to `main` that affect the site.

### Enable Pages

In GitHub:

1. Open the repository.
2. Go to **Settings → Pages**.
3. Under **Build and deployment**, choose **GitHub Actions**.
4. Push the website + workflow to `main`.
5. Open the Actions tab and watch **Deploy Sentinel website to GitHub Pages**.

The Vite config uses `base: './'`, so you do not need to hardcode the repository name.

## Live Streamlit dashboard

For now, the website can remain permanently hosted on GitHub Pages while the live dashboard is temporary.

When you start ngrok, paste the public URL into:

```ts
liveDashboardUrl: 'https://your-ngrok-url.ngrok.app'
```

in `src/data/site.ts`.

Later, replace it with the permanent cloud deployment URL. No other site code needs to change.

## Homepage motion system

The homepage is intentionally spacious and story-driven. It uses lightweight React + CSS animation only; no animation library is required.

Included interactions:

- scroll-triggered reveals with `IntersectionObserver`
- subtle Sentinel logo pulse
- animated healthy pipeline/data pulse
- changing data-health signals
- animated detector illustrations
- FHIR resource relationship lines
- moving architecture data particles
- count animation for the controlled volume experiment
- smooth light/dark theme transitions

Animation automatically reduces when the visitor has `prefers-reduced-motion` enabled.

The main animation helpers are:

```text
src/components/Reveal.tsx
src/components/CountUp.tsx
```
