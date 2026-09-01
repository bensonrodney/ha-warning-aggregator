# Screenshots

Used by the root `README.md` "Usage" section. Captured from a real Home
Assistant on a sandbox instance (Playwright).

**Dark mode only** — capture every screenshot with the browser context in
`color_scheme="dark"`. No light-mode twins.

**Reference them from the root README with Markdown syntax and a relative path**
— `![alt](docs/images/<file>)`, never an HTML `<img>` tag. HACS's info panel
rewrites relative paths *only* inside `![]()` / `[]()` syntax (to
`raw.githubusercontent.com/<repo>/<release-tag>/…`), so Markdown images stay
pinned to the tag of whatever release is being viewed — no per-release edits,
and old release notes never point at a moved/renamed file. A relative `<img
src>` 404s in HACS; an absolute one drifts to whatever `main` holds.

Overwrite files in place — don't rename or delete — so tag-pinned links in
already-published releases keep resolving.

| File | Shows |
| --- | --- |
| `wa-menu.png` | the **Warning Aggregator** helper-type menu (Monitored entity / Template check / Aggregator) |
| `create-aggregator.png` | the **Aggregator** config form |
| `monitor-entity.png` | the numeric monitor's threshold-or-range menu |
| `monitor-template.png` | the **Template check** form |
| `card-ok.png` | the card, all-OK (green) |
| `card-problem.png` | the card, tripped (warning header + listed monitors) |

The integration/brand artwork lives in `brands/` and
`custom_components/warning_aggregator/brand/`, not here.
