# One "System Warning" sensor for your whole Home Assistant

A pattern for collapsing *"is anything in my house in a state I should know about?"* into a
**single `binary_sensor`** that you can put on a dashboard, colour a header with, or hang one
notification off — while still being able to add new things to watch in ~2 minutes without
touching any of the plumbing.

- **`binary_sensor.system_warning`** — one problem sensor. `on` = at least one thing needs
  attention.
- **One notification automation** — fires once on the `off → on` edge and tells you *which*
  things tripped, by name.
- **A label** (`monitored`) — the list of things being watched. Adding/removing a check is
  just adding/removing the label.

Everything is built with **UI helpers** (Settings → Devices & Services → Helpers) and one
**UI automation**. No YAML packages, no `configuration.yaml` edits, no restarts.

---

## The architecture

```
     raw entities                wrapper "status" sensors            aggregator            automation
  (battery %, toner,          each: state = "ok" | "warning"      any "warning"?         off→on edge
   error codes, ...)          + label: monitored                                        → notify with names
 ┌─────────────────┐          ┌──────────────────────────┐        ┌──────────────────┐  ┌───────────────┐
 │ sensor.printer… │ ───────► │ sensor.printer_toner_    │ ──┐    │                  │  │ Notify on     │
 │ sensor.roborock…│ ───────► │   status         (label) │ ──┼──► │ binary_sensor.   │─►│ System        │
 │ binary_sensor…  │ ───────► │ sensor.roborock_error_   │ ──┤    │ system_warning   │  │ Warning       │
 │ ...             │          │   status         (label) │ ──┘    │ (problem)        │  └───────────────┘
 └─────────────────┘          └──────────────────────────┘        └──────────────────┘
```

The key move: **don't** write one giant template that ANDs/ORs 15 different raw sensors
together. Instead, give every check its own tiny **Template sensor** that outputs the literal
string `ok` or `warning`, and let the aggregator just count the `warning`s.

Why:

- Each check is independent and readable — one source entity, one condition, one line.
- You can see *exactly* which check is unhappy in the entity list (filter by the label).
- The aggregator and the automation never change — they work off the label, so adding check
  #16 doesn't risk breaking checks #1–15.
- Each wrapper is a real entity with history, so you can graph "how often did the printer trip".

---

## Part 1 — the wrapper "status" sensors

For each thing you want to watch, create a **Template helper → Sensor**:

- **Name:** `<Thing> Status` (e.g. `Printer Toner Status`)
- **State template:**

  ```jinja
  {% set s = states('sensor.YOUR_SOURCE_ENTITY') %}
  {% if s in ['unavailable','unknown','none'] or <BAD CONDITION> %}warning{% else %}ok{% endif %}
  ```

- **Label:** `monitored` (create the label once, then assign it here)
- No device class, no unit.

`<BAD CONDITION>` is whatever "bad" means for that entity. Examples:

| Kind of check              | `<BAD CONDITION>`                    |
|----------------------------|-------------------------------------|
| Low battery percentage     | `s\|float(0) < 20`                   |
| Low battery voltage        | `s\|float(0) < 12.2`                 |
| Consumable time left (sec) | `s\|float(0) < 180000`              |
| Printer toner %            | `s\|float(0) < 15`                   |
| A "problem" binary_sensor  | `s == 'on'`                         |
| An error-code sensor       | `s != 'none'` (plus the unavailable guard) |
| Just "is it reporting?"    | *(nothing — the unavailable guard is the whole check)* |
| Ratio of two sensors       | use two `{% set %}` lines, e.g. `(u\|float(0) / t\|float(1)) > 0.9` |

**Treating `unavailable`/`unknown` as `warning` is deliberate** — a sensor that has stopped
reporting is itself something you want to know about. Drop that part of the condition for any
check where a missing value is genuinely fine.

**Naming when you have several of the same kind of device** (multiple UPSs, printers, per-room
sensors): put the common part first and the device name last —
`UPS Battery Replacement Status - Gaming PC`, `UPS Battery Replacement Status - Rack` — so they
sort together in the entity list.

---

## Part 2 — the aggregator

One **Template helper → Binary sensor**:

- **Name:** `System Warning`
- **Device class:** `Problem`
- **State template:**

  ```jinja
  {{ label_entities('monitored') | select('is_state', 'warning') | list | count > 0 }}
  ```

That's the whole thing. `label_entities('monitored')` returns every entity carrying the label,
so this sensor automatically includes any wrapper you add later. It's `on` whenever one or more
wrappers are `warning`.

Put `binary_sensor.system_warning` on a dashboard, use it in a
[Mushroom template card](https://github.com/piitaya/lovelace-mushroom) header, drive an LED,
whatever.

---

## Part 3 — the notification

One UI automation. Trigger on the edge, list the tripped entities by friendly name:

```yaml
alias: Notify on System Warning
description: >
  When binary_sensor.system_warning transitions from off (ok) to on (warning),
  notify with the list of tripped monitored sensors.
mode: single

triggers:
  - trigger: state
    entity_id: binary_sensor.system_warning
    from: "off"
    to: "on"

# Don't spam if it flaps off→on again within 5 minutes
conditions:
  - condition: template
    value_template: >
      {{ state_attr('automation.notify_on_system_warning', 'last_triggered') is none
         or (now() - state_attr('automation.notify_on_system_warning', 'last_triggered')).total_seconds() > 300 }}

variables:
  tripped_list: >
    {{ label_entities('monitored') | select('is_state', 'warning')
       | map('state_attr', 'friendly_name') | list }}

actions:
  - action: notify.YOUR_NOTIFY_SERVICE          # swap for your own (mobile_app_*, discord, etc.)
    continue_on_error: true
    data:
      title: "⚠️ System Warning"
      message: "{{ tripped_list | length }} sensor(s) need attention: {{ tripped_list | join(', ') }}"
```

Notes:

- `continue_on_error: true` on each notify action so one dead notifier doesn't stop the others.
- The `last_triggered` condition is a cheap re-notify guard. If you want re-alerts while it
  stays tripped, add a time-pattern trigger and an `is_state('binary_sensor.system_warning',
  'on')` condition instead.
- Want the raw entity_ids too? Change the `map('state_attr', 'friendly_name')` to drop the
  `map(...)` for entity_ids, or build a richer message.

---

## Adding a new check later

1. Create a **Template → Sensor** helper named `<Thing> Status` with the `ok`/`warning`
   template above.
2. Give it the `monitored` label.
3. Done. The aggregator and the automation pick it up automatically.

To *pause* a check, just remove the label — the wrapper sensor stays, but stops counting.
(This setup uses that: a few `* Status` helpers exist but are intentionally unlabelled.)

---

## FAQ / design notes

**Why the label instead of listing entities in the template?**
So the aggregator and automation are written once and never edited. Adding check #20 can't
break checks #1–19, and there's no list to keep in sync in three places.

**Why string `ok`/`warning` instead of a boolean or `on`/`off`?**
Readability in the UI, and it keeps the aggregator's filter trivial
(`select('is_state', 'warning')`). A wrapper that errors renders as `unknown`, which is
visibly *not* `warning` — you notice the broken check rather than it silently passing.

**Why Template *helpers* and not `template:` YAML?**
Helpers are created/edited in the UI, reload instantly, show up in the helper registry, and
don't need file access or a restart. Same engine, less friction.

**Why one wrapper per check instead of one big template?**
Isolation and visibility. Each check is one source + one condition, independently greppable in
the entity list, with its own history graph. A 40-line template that's `on` "for reasons" is
the thing this pattern exists to avoid.

**Does it survive restarts / sensor flapping?**
The aggregator is stateless (recomputed from current states), so yes. The notification's
5-minute guard covers brief flapping.

---

## Appendix — a real, complete example

The `monitored` label on this system currently carries 14 wrapper sensors. Each is a
Template → Sensor helper; the source entity names are specific to this install but the shape
is identical.

| Wrapper (`sensor.…`)                          | Watches                          | Trips (`warning`) when |
|----------------------------------------------|----------------------------------|------------------------|
| `bike_battery_status`                        | e-bike battery voltage           | `< 12.0` V |
| `car_battery_status`                         | car battery voltage              | `< 12.2` V |
| `gdrive_storage_status`                      | Google Drive used / total        | `> 90 %` full |
| `phone_battery_status`                       | phone battery %                  | `< 20 %` |
| `phone_storage_status`                       | phone internal storage free (GB) | `< 2` |
| `pod_temperature_status`                     | a temp sensor                    | not reporting |
| `printer_toner_status`                       | HP black cartridge %             | `< 15 %` |
| `roborock_battery_status`                    | vacuum battery %                 | `< 20 %` |
| `roborock_error_status`                      | vacuum error code                | anything other than `none` |
| `roborock_filter_status`                     | filter time left (s)             | `< 36000` |
| `roborock_main_brush_status`                 | main brush time left (s)         | `< 180000` |
| `roborock_sensor_status`                     | sensor-clean time left (s)       | `< 18000` |
| `roborock_side_brush_status`                 | side brush time left (s)         | `< 72000` |
| `ups_battery_replacement_status_gaming_pc`   | UPS "battery needs replacement"  | binary_sensor is `on` |

Representative templates:

```jinja
{# Printer Toner Status #}
{% set s = states('sensor.hp_laserjet_pro_mfp_m127fn_black_cartridge_hp_cf283a') %}
{% if s in ['unavailable','unknown','none'] or s|float(0) < 15 %}warning{% else %}ok{% endif %}

{# Roborock Error Status #}
{% set s = states('sensor.roborock_q7_max_vacuum_error') %}
{% if s in ['unavailable','unknown'] or s != 'none' %}warning{% else %}ok{% endif %}

{# GDrive Storage Status (ratio of two sensors) #}
{% set u = states('sensor.used_storage') %}
{% set t = states('sensor.total_available_storage') %}
{% if u in ['unavailable','unknown','none'] or t in ['unavailable','unknown','none'] or t|float(0) == 0 %}warning
{% elif (u|float(0) / t|float(1)) > 0.9 %}warning
{% else %}ok{% endif %}

{# UPS Battery Replacement Status - Gaming PC (wrapping a problem binary_sensor) #}
{% set s = states('binary_sensor.apc_back_ups_battery_needs_replacement') %}
{% if s in ['unavailable','unknown','none'] or s == 'on' %}warning{% else %}ok{% endif %}
```
