# Terraria (Android) Modding Skill & Mod Menu

> **中文说明见 [README.zh-CN.md](README.zh-CN.md)** · Everything here was measured on a real device — no generic advice.

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
| [`skill/reference/pitfalls.md`](skill/reference/pitfalls.md) | 34 measured pitfalls — symptom → root cause → fix (incl. the crash that a stack overflow from too many dynamic classes causes) |
| [`skill/reference/menu-implementation.md`](skill/reference/menu-implementation.md) | Copy-paste code patterns: tag dispatch, panel skeleton, auto height, virtual list, icon cropping, weather sync, infinite ammo |
| [`menu/terraria-mod-menu.js`](menu/terraria-mod-menu.js) | ⭐ Ready-to-run in-game mod menu (~280 KB): 6 tab pages, icon grid with search, 9 event switches, weapon mods, virtual list |
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
