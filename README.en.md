# Terraria (Android) Modding Skill & Mod Menu

> **中文说明见 [README.md](README.md)（默认）** · Everything here was measured on a real device — no generic advice.
>
> **⬇️ Download:** [latest release](https://github.com/abcd123rft/terraria-android-modding/releases/latest)
> (zip with docs + menu + tools, **no game assets**) · or just browse the folders below.

A reusable **skill package + working mod menu** for modding the Android build of *Terraria*
(Unity + IL2CPP; verified on the CN build `com.xd.terraria` `1.4.56002`, Unity 2021.3.26f1c1, Android 16).
It covers how to edit gameplay through il2cpp by member **name**, how to build an **in-game menu with Android
system UI** (touches never fall through the game), and how to **extract item icons offline** from the APK.

- **Verified on:** 2026-09-19 · CN build `1.4.56002` (versionCode 303538) · OnePlus PKR110 / Android 16
- **Read [skill/FRESHNESS.md](skill/FRESHNESS.md) first** — every number in here is a snapshot; it lists what goes
  stale after a game update and how to rebuild it.

## What's inside

| Path | What it is |
|---|---|
| [`skill/SKILL.md`](skill/SKILL.md) | Main skill (Chinese): environment & channels, il2cpp-by-name technique, correct per-frame hooking, feature recipes, menu design, icon pipeline, update resilience |
| [`skill/SKILL.en.md`](skill/SKILL.en.md) | The same skill in English (with YAML frontmatter — load it as an agent skill) |
| [`skill/FRESHNESS.md`](skill/FRESHNESS.md) | Freshness ledger: verified-on date, target build, which constants go stale, how to rebuild, 3-step self check |
| [`skill/reference/pitfalls.md`](skill/reference/pitfalls.md) | 39 measured pitfalls (see also the Chinese list with 50) — symptom → root cause → fix (incl. the crash that a stack overflow from too many dynamic classes causes) |
| [`skill/reference/menu-implementation.md`](skill/reference/menu-implementation.md) | Copy-paste code patterns: tag dispatch, panel skeleton, auto height, virtual list, icon cropping, weather sync, infinite ammo |
| [`menu/terraria-mod-menu.js`](menu/terraria-mod-menu.js) | ⭐ Ready-to-run in-game mod menu (~330 KB): 6 tab pages, icon grid with search, 9 event switches, weapon mods, virtual list |
| [`menu/MENU-MANUAL.zh-CN.md`](menu/MENU-MANUAL.zh-CN.md) | End-user manual for the menu |
| [`tools/`](tools) | `jshook.py` (injection client) · icon/name-table generators · APK unpacker · Texture2D parser · local icon server |

## Highlights of the approach

- **Address the game by name, never by address.** `il2cpp_class_from_name` + field/method lookup by name,
  with an **argc fallback** for method lookups (a game update may add/remove parameters).
- **Per-frame effects need the right hook.** `PlayerFrame` is the last `Player` method of the frame, but
  `moveSpeed`/`statDefense` are reset by `ResetEffects()` every frame → those must be written in
  **`Player.UpdateEquips`** (after the reset, before movement). `onLeave` never fires in this environment.
- **Android system UI instead of an ImGui overlay:** the menu is a normal `View` tree added with
  `Activity.addContentView` → touches never fall through to the game and it disappears with the process.
- **Hard stability limit:** never call `Java.registerClass` on a hot path — every dynamic class adds a
  `DexClassLoader`, and ART's recursive class-loader-context encoding will **stack-overflow and kill the game**.
  One class per listener type + `View.setTag` dispatch (the full tombstone signature is in the pitfalls doc).
- **Offline everything:** item names, atlas rects and category data are generated outside the game
  (the atlas rect table is plain inside `resources.assets`, keyed by `CRC32("item_<id>.png")`, and the atlas
  PNG is stored **vertically flipped** — crop `(X, 2048−Y−H)`).

## Quick start

```bash
# 1) push the menu into a running game (JsHook / Frida host with MCP on 127.0.0.1:19820)
cd menu
python3 ../tools/jshook.py exec --file terraria-mod-menu.js --wait 7

# 2) icons: the menu loads two 2048² atlas pages into the game's private cache.
#    Extract them from YOUR OWN copy of the game (see skill/SKILL.md §7), put them at
#    /sdcard/Download/DSHA/terraria_icons/atlas_0.png and atlas_1.png,
#    and if the game cannot read /sdcard, serve them once with:
python3 ../tools/icon_http_server.py 8899

# 3) full self-check after every push
python3 ../tools/jshook.py exec --file terraria-mod-menu.js --sub "selfTest: false||selfTest: true" --wait 12
```

## Requirements

- Android device (arm64) with the game installed; **Frida-based injection** (e.g. JsHook) reachable at
  `127.0.0.1:19820` (key at `/root/.dsh/jshook_key`, override with `JSHOOK_KEY_FILE`).
- Python 3 for the tools. The offline APK pipeline additionally needs `lz4`, `Pillow` and `texture2ddecoder`.
- The menu is written for the CN build's package name; for another build pass `--package` to `jshook.py`.

## Changelog (latest first)

> 这一版加的「特殊仆从也可多只（实验）」会干扰仆从的形态/AI 分支选择，已按用户要求撤回，菜单行为回到 v1.2.7；相关发现保留在踩坑清单第 53 条。

**v1.2.8 (withdrawn)**
- New experimental switch **"allow multiple special minions"**: besides the total cap, the game remembers
  "already have one of this type" in **per-type boolean fields** (`stardustMinion`, `palworldFoxsparksMinion`,
  `twinsMinion`, `spiderMinion`, …, 14 in total, found by enumerating the Player field table with
  `il2cpp_class_get_fields`); the switch clears them every frame.
- The manual now states two **vanilla hard rules** that no field write can change: (1) "unique" minions such as the
  Stardust Dragon always stay a single entity — extra slots make it **longer**, not more numerous; (2) sentries of the
  **same type** cannot coexist (re-summoning relocates the old one) — `maxTurrets` only raises the total across types.
- Also documented a testing pitfall: this port **cannot simulate "press use" from Frida** (`controlUseItem` and
  `Main.mouseLeft` are both overwritten by the input layer every frame), so "can a second one be summoned" must be
  verified by hand.

**v1.2.7**
- New **"Remove summon count limit"** switch on the Misc page: raises both the **minion** (`maxMinions`) and
  **sentry/turret** (`maxTurrets`) caps to 99 and keeps `slotsMinions` in sync, plus a button that reads the live
  values back. Two measured gotchas, both now documented: those fields are **recomputed every frame from equipment**
  (a one-shot write is reverted within 400 ms), so they must be written every frame; and since `Interceptor.onEnter`
  runs before the target body, the write belongs in the per-frame hooks. Verified by attaching a `Player.ItemCheck`
  probe — it reads **99** at the exact moment the game checks the summon limit.

**v1.2.6**
- Fixed the **bag page showing only the five section headers, no slots**: the new "prewarm" ran on the title screen
  (no active player yet, so the slot count read 0) and built five headers plus sixteen empty rows while still marking
  itself built — and because that row count equalled the expected child count, the self-heal check could not notice.
  Now the grid is only built when `bagSlots() > 0`, the self-heal also rebuilds when there are zero tiles but slots
  exist, and a failed prewarm is retried by the poll **as soon as a player appears** (which lands during world loading,
  hiding the hitch).

**v1.2.5**
- New **"Paths & configuration"** section (manual §10, SKILL.md §11, this README): exactly what to edit when you move
  the assets or the scripts — only two constants live inside the game process (atlas fallback `DIR`, atlas HTTP `HTTP`),
  container-side tools take env vars (`ICON_DIR`, `ICON_LOG`, `JSHOOK_URL`, `JSHOOK_KEY_FILE`, `--package`, `TASSETS`,
  `ICON_DST`), and five scripts have a single hardcoded path each (their comments state the expected layout), plus a
  four-step self check. The game-side cache path is computed at runtime via `getCacheDir()`, so changing device or
  package name needs no edit.

**v1.2.4**
- **Icon atlas fix**: the atlases extracted from `resources.assets` were missing two conversion steps —
  Unity textures are stored **bottom-up** (needs a row flip) and the bytes may be **BGRA** (needs an R/B swap).
  Result: every item icon was **upside down** and gold coins looked **blue**. The earlier workaround
  (cropping at `H−Y−H`) only fixed the *position*, never the content — and it survived review because the
  icons used for verification (swords, hammers) are near-symmetric vertically. Fixed at the asset level with
  `tools/fix_atlas_orientation.py`; the menu now crops plain `(X, Y, X+W, Y+H)`. Verify icon orientation with a
  **potion bottle** (neck up) or a **coin** (gold), never with a sword.
- Remember to refresh the game-side cache after swapping atlases: serve them, call
  `TERRARIA_SYS_MENU.icon.warm(true)`, then reload the script.

**v1.2.3**
- **Performance pass** (measured): reopening the item picker 133 ms → **1.6 ms**, bag page re-entry 53 ms → **9 ms**,
  bag scan 1.24 ms → **0.50 ms**, number pad 26.7 ms → **6.8 ms**, one field write 4.40 µs → **1.70 µs**.
  Two changes did most of the work: (1) **field access by cached offset** (`il2cpp_field_get_offset` + direct
  memory read/write, verified once against the official API with automatic fallback), and (2) **build Android
  views once and reuse them** (a single Java call costs 0.13–0.28 ms, so rebuilding 120 views = 100 ms+).
  Idle cost is now ~0: `playerIdle()` short-circuits both per-frame hooks when every switch is off.

**v1.2.2**
- Bag page: opening the item picker from an **ammo** slot lists only ammo, from a **coin** slot only coins
  (ID sets compressed offline into range strings; search and category filters still compose).

## Legal / fair use

- **No game assets are included in this repository.** The two atlas PNGs, the item name/rect tables and any
  other extracted content stay out of the repo; the scripts are meant to be run against **your own legally
  obtained copy** of the game (that is how the modding community normally works).
- `menu/terraria-mod-menu.js` embeds **interoperability data derived from the game** (item ids/names and atlas
  rectangles) so the menu works out of the box. You can regenerate those tables locally with `tools/` and ship
  your own build — see `skill/SKILL.md` §7.
- This is a **memory-editing trainer for single-player use**. Use it in your own world only; do not use it in
  multiplayer, do not redistribute game assets, and respect the game's Terms of Service and local law.
- Code in this repository is MIT-licensed (see [LICENSE](LICENSE)); *Terraria* and its assets are the property
  of Re-Logic / the respective publisher. This project is unofficial and not affiliated with them.

## Credits

Built and verified on-device over a long reverse-engineering session: UnityFS/IL2CPP internals, the
`CRC32("item_<id>.png")` key discovery, the flipped-atlas crop, the dynamic-class crash analysis and the
Android-system-UI menu design are all documented in `skill/` so the next person (or agent) does not have to
rediscover them.
