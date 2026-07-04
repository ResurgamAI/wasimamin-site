# CLAUDE.md

Guidance for Claude Code (and other AI agents) working in this repository.

## What this is

The source for **wasimamin.us** — the personal portfolio site of Wasim Amin,
J.D., M.B.A. (U.S. corporate attorney, management consultant, and legal-AI
specialist). It is a **static site** deployed on **Netlify**. There is no
build step, framework, package manager, or test suite — the HTML is authored
directly and served as-is.

## Layout

| Path | Purpose |
| --- | --- |
| `index.html` | The entire public site. Single self-contained file — inline CSS in `<style>` and inline JS (including a Three.js-style 3D canvas hero) in `<script>`. Edit this directly. |
| `hero-animation.html` | Standalone hero/background animation experiment. |
| `_headers` | Netlify HTTP header rules (also mirrored in `netlify.toml`). |
| `netlify.toml` | Netlify config: header rules and the `/tracker` → private-tracker redirect. |
| `robots.txt`, `sitemap.xml` | SEO. `Disallow: /private/`. |
| `.well-known/mcp/server-card.json` | MCP server card advertising the site as a discovery resource (no live MCP tools are served). |
| `private/LRkFOQzb3fY/` | Obscured, non-indexed job-application tracker (`index.html`) plus `jds/` job descriptions. The random path segment is the access gate. |
| `tracker.py` | CLI that manages the job tracker by editing `private/LRkFOQzb3fY/index.html` directly through the GitHub Contents API. |
| `000_Wasim_Amin_Resume_2026.pdf`, `Wasim_Amin_Deal_Sheet.pdf` | Downloadable assets linked from the site. |
| `files 5/`, `files7/`, `*.zip` | Older snapshots / packaged uploads. Not part of the live site — do not edit these when making site changes. |

## Working on the site

- **Everything is hand-authored.** Keep `index.html` self-contained: no
  external build tooling, no bundler, no npm. New styles go in the existing
  `<style>` block, new behavior in the existing `<script>` block, unless there
  is a clear reason to split a file out.
- **Design language** is defined by CSS custom properties in `:root` at the top
  of `index.html` (dark navy background, gold accents, `Cormorant Garamond` /
  `Inter` / `JetBrains Mono` fonts). Reuse those variables rather than
  hard-coding colors.
- **Respect `prefers-reduced-motion`** — the animations already gate on it.
- To preview locally, serve the folder statically (e.g.
  `python3 -m http.server`) and open `index.html`.

## The job tracker (`tracker.py`)

- Stdlib-only Python 3.7+ (no pip installs). Commands: `list`, `add`,
  `update`, `delete`, `summary`.
- It reads/writes the tracker table inside `private/LRkFOQzb3fY/index.html`
  remotely via the GitHub API. Config comes from env vars: `GH_TOKEN`
  (repo-scoped PAT), `GH_REPO` (`ResurgamAI/wasimamin-site`), `GH_FILE`
  (the private tracker path).
- The `/private/` area is intentionally kept out of search engines and behind
  an obscure URL. Never add links to it from public pages or the sitemap.

## Deployment

Pushing to the default branch (`main`) triggers a Netlify deploy of the static
files. There is no CI build — what's committed is what ships.

## Conventions

- Keep secrets (GitHub tokens, etc.) out of the repo; `tracker.py` reads them
  from the environment.
- When updating downloadable PDFs, replace the file in place so existing links
  keep working.
