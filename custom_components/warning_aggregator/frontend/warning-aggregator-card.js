/*!
 * warning-aggregator-card
 * Part of the ha-warning-aggregator integration.
 *
 * Shows a green "All Sensors OK" when nothing is wrong, or a warning header
 * plus the list of monitors that are not OK.
 */

const VERSION = "0.1.0";

const OK_ICON = "mdi:check-circle";
const PROBLEM_ICON = "mdi:alert";
const UNKNOWN_ICON = "mdi:help-circle";

const STYLE = `
  <style>
    ha-card { overflow: hidden; }
    .header {
      padding: 16px 16px 0;
      font-size: var(--ha-card-header-font-size, 1.5rem);
      font-weight: 500;
      color: var(--ha-card-header-color, var(--primary-text-color));
    }
    .status {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 16px;
    }
    .status ha-icon { --mdc-icon-size: 32px; flex: none; }
    .status .text {
      font-size: 1.1rem;
      font-weight: 500;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .status.ok { color: var(--success-color, #43a047); }
    .status.problem { color: var(--warning-color, #ffa600); }
    .status.unknown { color: var(--secondary-text-color); }
    .count {
      background: currentColor;
      color: var(--card-background-color, var(--ha-card-background, #fff));
      border-radius: 999px;
      padding: 0 8px;
      font-size: 0.8rem;
      line-height: 1.4;
      min-width: 10px;
      text-align: center;
    }
    ul { margin: 0; padding: 0 8px 8px; list-style: none; }
    li {
      display: flex;
      align-items: center;
      gap: 4px;
      padding: 10px 8px;
      cursor: pointer;
      border-top: 1px solid var(--divider-color);
      color: var(--primary-text-color);
    }
    li:hover { background: var(--secondary-background-color); }
    li ha-icon { --mdc-icon-size: 20px; color: var(--secondary-text-color); flex: none; }
    .err { padding: 16px; color: var(--error-color); }
  </style>
`;

function escapeHtml(value) {
  return String(value).replace(
    /[&<>"']/g,
    (c) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[c],
  );
}

class WarningAggregatorCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement("warning-aggregator-card-editor");
  }

  static getStubConfig(hass) {
    const match = Object.keys(hass.states).find(
      (id) =>
        id.startsWith("binary_sensor.") &&
        Array.isArray(hass.states[id].attributes.problem_entities),
    );
    return { entity: match || "binary_sensor.system_warning" };
  }

  setConfig(config) {
    if (!config || (!config.entity && !config.label)) {
      throw new Error(
        "warning-aggregator-card: set 'entity' (a Warning Aggregator sensor) or 'label'.",
      );
    }
    this._config = {
      ok_text: "All Sensors OK",
      problem_text: "Sensors need attention",
      hide_when_ok: false,
      problem_states: ["warning"],
      ...config,
    };
    this._lastKey = undefined;
    if (this._hass) this._update();
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  getCardSize() {
    const problems = this._problems ? this._problems.length : 0;
    return 1 + Math.min(problems, 8);
  }

  _name(entityId) {
    const st = this._hass.states[entityId];
    return (st && st.attributes.friendly_name) || entityId;
  }

  _resolve() {
    const hass = this._hass;
    const cfg = this._config;

    if (cfg.entity) {
      const st = hass.states[cfg.entity];
      if (!st) return { error: `Entity not found: ${cfg.entity}` };

      const known = st.state !== "unavailable" && st.state !== "unknown";
      const on = st.state === "on";
      const ids = st.attributes.problem_entities || [];
      const names = st.attributes.problem_names || [];
      let problems = ids.map((id, i) => ({
        entityId: id,
        name: names[i] || this._name(id),
      }));
      // Plain problem sensor with no breakdown attributes: fall back to itself.
      if (on && problems.length === 0) {
        problems = [
          {
            entityId: cfg.entity,
            name: cfg.title || st.attributes.friendly_name || cfg.entity,
          },
        ];
      }
      return {
        title: cfg.title ?? st.attributes.friendly_name ?? cfg.entity,
        known,
        on,
        problems,
      };
    }

    // Label mode: compute the list client-side from the entity registry.
    const problemStates = new Set(cfg.problem_states);
    const problems = [];
    for (const [id, ent] of Object.entries(hass.entities || {})) {
      if (!ent.labels || !ent.labels.includes(cfg.label)) continue;
      const st = hass.states[id];
      if (st && problemStates.has(st.state)) {
        problems.push({ entityId: id, name: this._name(id) });
      }
    }
    problems.sort((a, b) => a.name.localeCompare(b.name));
    return {
      title: cfg.title ?? `Label: ${cfg.label}`,
      known: true,
      on: problems.length > 0,
      problems,
    };
  }

  _moreInfo(entityId) {
    const ev = new Event("hass-more-info", { bubbles: true, composed: true });
    ev.detail = { entityId };
    this.dispatchEvent(ev);
  }

  _update() {
    if (!this._hass || !this._config) return;

    const data = this._resolve();
    const key = JSON.stringify(data);
    if (key === this._lastKey) return;
    this._lastKey = key;
    this._problems = data.problems || [];

    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    const root = this.shadowRoot;

    if (data.error) {
      this.style.display = "";
      root.innerHTML = `<ha-card><div class="err">${escapeHtml(data.error)}</div></ha-card>${STYLE}`;
      return;
    }

    if (!data.on && this._config.hide_when_ok) {
      this.style.display = "none";
      root.innerHTML = "";
      return;
    }
    this.style.display = "";

    let status;
    if (!data.known) {
      status = { cls: "unknown", icon: UNKNOWN_ICON, text: "Status unavailable" };
    } else if (data.on) {
      status = { cls: "problem", icon: PROBLEM_ICON, text: this._config.problem_text };
    } else {
      status = { cls: "ok", icon: OK_ICON, text: this._config.ok_text };
    }

    const header = this._config.title
      ? `<div class="header">${escapeHtml(this._config.title)}</div>`
      : "";

    const list =
      data.on && this._problems.length
        ? `<ul>${this._problems
            .map(
              (p) =>
                `<li data-entity="${escapeHtml(p.entityId)}">` +
                `<ha-icon icon="mdi:chevron-right"></ha-icon>` +
                `<span>${escapeHtml(p.name)}</span></li>`,
            )
            .join("")}</ul>`
        : "";

    root.innerHTML = `
      <ha-card>
        ${header}
        <div class="status ${status.cls}">
          <ha-icon icon="${status.icon}"></ha-icon>
          <div class="text">
            <span>${escapeHtml(status.text)}</span>
            ${data.on ? `<span class="count">${this._problems.length}</span>` : ""}
          </div>
        </div>
        ${list}
      </ha-card>
      ${STYLE}
    `;

    root.querySelectorAll("li[data-entity]").forEach((li) => {
      li.addEventListener("click", () => this._moreInfo(li.dataset.entity));
    });
  }
}

class WarningAggregatorCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (schema) =>
        ({
          entity: "Aggregator sensor (binary_sensor)",
          label: "…or a label to watch directly",
          title: "Title (optional)",
          ok_text: "Text when everything is OK",
          problem_text: "Heading when there are problems",
          hide_when_ok: "Hide the card entirely when all OK",
        })[schema.name] || schema.name;
      this._form.addEventListener("value-changed", (ev) => {
        this.dispatchEvent(
          new CustomEvent("config-changed", { detail: { config: ev.detail.value } }),
        );
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = this._config;
    this._form.schema = [
      { name: "entity", selector: { entity: { domain: "binary_sensor" } } },
      { name: "label", selector: { label: {} } },
      { name: "title", selector: { text: {} } },
      { name: "ok_text", selector: { text: {} } },
      { name: "problem_text", selector: { text: {} } },
      { name: "hide_when_ok", selector: { boolean: {} } },
    ];
  }
}

customElements.define("warning-aggregator-card", WarningAggregatorCard);
customElements.define("warning-aggregator-card-editor", WarningAggregatorCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "warning-aggregator-card",
  name: "Warning Aggregator",
  description:
    "Green 'All Sensors OK', or a warning with the list of monitors that are not OK.",
  preview: true,
  documentationURL: "https://github.com/bensonrodney/ha-warning-aggregator",
});

// eslint-disable-next-line no-console
console.info(
  `%c warning-aggregator-card %c ${VERSION} `,
  "background:#ffa600;color:#111;font-weight:700;border-radius:3px 0 0 3px",
  "background:#333;color:#fff;border-radius:0 3px 3px 0",
);
