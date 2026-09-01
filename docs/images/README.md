# Screenshots

Used by the root `README.md` "Usage" section. Captured from a real Home
Assistant on a sandbox instance (Playwright).

**Dark mode only** — capture every screenshot with the browser context in
`color_scheme="dark"`. No light-mode twins.

**Reference them from the root README with absolute `raw.githubusercontent.com`
URLs** (`.../ha-warning-aggregator/main/docs/images/<file>`), not relative
`<img src="docs/images/...">`. HACS's info panel only rewrites relative paths
inside markdown `![]()` / `[]()` syntax — an HTML `<img>` with a relative `src`
404s there. GitHub renders both, so absolute is the one that works everywhere.

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
