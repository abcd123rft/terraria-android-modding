---
name: terraria-modding
description: Use when modding Android Terraria (Unity + IL2CPP; CN build com.xd.terraria, same approach for the global build) — injecting Frida/JsHook scripts to edit gameplay by il2cpp member names (god mode, flight, move speed, events, time, item spawning, infinite ammo, weapon edits), building an in-game mod menu with Android system UI (Activity.addContentView — touches never fall through, disappears with the game), and extracting item icons offline from the APK. Ships a ready-to-run menu script, reusable tools and a full pitfall list.
---

# Terraria (Android) · Modding & Mod-Menu Development

> Everything here was **measured on a real device**, not copied from generic guides.
> Verified: **2026-09-19** against CN build **1.4.56002** (versionCode 303538, Unity 2021.3.26f1c1, IL2CPP).
> Timeliness details and what goes stale after a game update: see `版本与时效.md` (also summarised in §9).

## 0. 30-second index

| Goal | Where |
|---|---|
| Just install a working mod menu | §2 + `成品/系统菜单.js` + `脚本/jshook.py` |
| Add a new feature (read/write a field, call a method) | §3 core technique + §5 recipe table |
| An effect "does nothing" | §4 correct way to hook per-frame effects + `参考/踩坑清单.md` |
| Change the menu UI / add widgets | §6 menu design |
| Item icons / assets | §7 icon pipeline |
| Game updated / game crashed | §9 + `参考/踩坑清单.md` |

## 1. Environment & channels

- Target: CN Terraria `com.xd.terraria`, Unity **2021.3.26f1c1** + **IL2CPP** (`libil2cpp.so`),
  activity `com.unity3d.player.UnityPlayerActivity`, landscape 2376×1080 @ density 3.0.
- Injection: **JsHook** (a Frida host; MCP at `http://127.0.0.1:19820/mcp`, key in `/root/.dsh/jshook_key`).
  Client = `脚本/jshook.py`:
  ```bash
  python3 jshook.py targets
  python3 jshook.py exec --file x.js --wait 6                                  # unload → execute → wait → read log
  python3 jshook.py exec --file x.js --sub "selfTest: false||selfTest: true"   # patch text before sending
  python3 jshook.py log --tail 200
  ```
  `exec` returns `{ok, exec, unload, log}` — **read the log together with exec** (a separate `log` call is often empty).
- No root: JsHook can also run the game inside its own virtualised container (no root needed) — injection itself needs root or such a container.
- Device shell from the container: `python3 /root/.dsh/adb-shell.py '<single command>'` (no pipes/redirects).
  `/app/*` are zero-config app-layer endpoints (launch app, read screen, screenshot, …).
- Game-private files (`/data/user/0/com.xd.terraria/…`) are **not readable from the container**, but the
  **game process itself can write them** (used for the icon cache, §7).

## 2. Run the finished menu in 5 minutes

```bash
# 1) make sure the game is in the foreground (JsHook logs are empty while it is backgrounded)
T=$(cat /root/.dsh/.bridge_token); curl -s "http://127.0.0.1:3090/app/launch?pkg=com.xd.terraria&token=$T"

# 2) push the menu
cd 成品 && python3 ../脚本/jshook.py exec --file 系统菜单.js --wait 7
```
Expected log:
```
[系统菜单] 面板已挂载（content，宽 250dp，顶层节点 6 个）
[系统菜单] 图标：图集 0 就绪 2048×2048（来源 私有缓存）
[系统菜单] 已挂 UpdateEquips 钩子（argc=1，每帧属性写入点）
[系统菜单] 已挂 PlayerFrame 持续效果钩子
```
Icons need the two atlas PNGs in `/sdcard/Download/DSHA/terraria_icons/atlas_{0,1}.png`; the menu fetches them
into the game's private cache from a local HTTP server (`脚本/图标HTTP服务.py`) **on a background thread**, once.

Self-test: `--sub "selfTest: false||selfTest: true"` runs a full check (stats / weapon / events / icons / layout).

## 3. Core technique — address il2cpp by NAME (never by fixed address)

```js
var Main   = il2cpp_class_from_name(ACS, "Terraria", "Main");       // ACS = Assembly-CSharp image
var Player = il2cpp_class_from_name(ACS, "Terraria", "Player");

var f = il2cpp_class_get_field_from_name(Player, "moveSpeed");     // cache the FieldInfo*!
il2cpp_field_get_value(obj, f, buf);          // instance field
il2cpp_field_static_get_value(f, buf);        // static field
il2cpp_field_set_value(obj, f, buf);          // write instance field
il2cpp_field_static_set_value(f, buf);        // write static field

// ALWAYS try several parameter counts — a game update may change argc
// (real case: UpdateEquips is argc=1, not 0)
function findMethod(cls, name, argcs) {
  for (var i = 0; i < argcs.length; i++) {
    var m = il2cpp_class_get_method_from_name(cls, name, argcs[i]);
    if (!m.isNull()) return { m: m, argc: argcs[i] };
  }
  return null;
}
il2cpp_runtime_invoke(m, objOrNull, argsArray, excPtr);            // generic call (slow but universal)
```
Type-aware read/write from `il2cpp_type_get_name()`: `Boolean`→1 byte, `Byte/SByte/Int16`→that width,
`Int32`→`writeS32`, `Single`→`writeFloat`, `Double`→`writeDouble` (`Main.time` is Double),
`String`→`readPointer` then `readUtf8String`.
il2cpp arrays: data at `arr + 0x20`, length at `arr + 0x18` (`TextureAssets.Item` is an `Asset<Texture2D>[]`).

## 4. Hooking per-frame effects (where "it does nothing" comes from)

### 4.1 What to hook
**`Interceptor.onLeave` never fires in this environment** → use `onEnter` only.
Measured intra-frame order of `Player` methods:
```
Update → UpdateSocialShadow → UpdateImmunity → ResetEffects → UpdateBuffs → UpdatePet
→ UpdateEquips → UpdateArmorSets → UpdateLifeRegen → UpdateManaRegen → UpdateJumpHeight
→ ItemCheck → PlayerFrame
```
- **`PlayerFrame/0`** — last one in the frame: write fields that ResetEffects does *not* clear
  (`creativeGodMode`, `immune`, `wingsLogic/wings/wingTime`, `maxMinions`, `luck`, …).
- **`Player.UpdateEquips/1`** — runs *after* `ResetEffects` and *before* movement: fields like
  `moveSpeed / maxRunSpeed / accRunSpeed / runAcceleration / statDefense` **must** be written here;
  writing them at frame end is a no-op (this is why "move-speed mod doesn't work").
- `onEnter(a)` → `a[0]` is `this`. Always log that the hook attached (silent argc mismatch = silent failure).

### 4.2 Heartbeat (50 ms `setInterval`)
For state re-assertion (weather), inventory scans (infinite ammo), seek-bar sync, held-weapon polling.
Heavy work (network, bitmap crops) must **not** run on the main thread (`NetworkOnMainThreadException`) —
use `setTimeout` (the Frida JS thread).

### 4.3 Two field-write traps
- **Don't write item fields with the Player helper**: `setF(obj,'stack',v)` resolves the name on the
  `Player` class and fails silently (log: `无字段 stack`) → use `setOn(IL.Item, item, 'stack', v)`.
  (This was the cause of "ammo not restored after disabling infinite ammo".)
- Always read back and log what you wrote; silent failures are otherwise invisible.

## 5. Feature recipes (all measured)

| Feature | How |
|---|---|
| God mode | `Player.creativeGodMode=true`, `immune=true`, `immuneTime=3600`, `lavaImmune=true` (per frame) |
| God mode (defense) | `statDefense=200`, `endurance=0.5`, `lavaImmune=true` |
| Max stats | `statDefense=100`, `meleeDamage/rangedDamage/magicDamage/minionDamage=3`, `*Crit=100`, `wingTime(Max)=200` |
| **Flight (no wings)** | must write **all**: `wingsLogic=1`, `wings=1`, `wingTime=200`, `wingTimeMax=200` |
| **Move speed** | write in the **UpdateEquips** hook: `moveSpeed=2.2`, `maxRunSpeed=12`, `accRunSpeed=10`, `runAcceleration/runSlowdown=0.6`, `jumpSpeedBoost=5` |
| Luck / minions | `luck=1`, `maxMinions=20` |
| Clear debuffs | iterate buff slots, `Player.DelBuff(i)` for ids in `DEBUFF_IDS` |
| **Difficulty** | `Player.difficulty` is a **Byte**: 0=Classic 1=Expert 2=Master → cycle `(cur+1)%3` |
| Blood moon / eclipse | `Main.bloodMoon` / `Main.eclipse` — **re-assert every frame** (game clears them each frame) |
| **Rain** | write fields directly: `Main.raining=true`, `Main.rainTime=36000`, `Main.maxRaining=1` (`StartRain/3` needs preconditions → measured ineffective) |
| **Sandstorm** | `Sandstorm.Happening=true`, `TimeLeft=36000`, `Severity=1`, `IntendedSeverity=1` (Happening alone is cancelled by `UpdateTime` that same frame) |
| Invasions | `Main.StartInvasion(type)`: goblin 1 / pirate 3 / martian 4; off = `invasionType=0, invasionSize=0` |
| Party / lantern night | static fields `BirthdayParty.ManualParty`, `LanternNight.ManualLanterns` |
| World time | `Main.time` (Double, 0–54000), `Main.dayTime` (bool); "lock" = write back on every tick |
| **Infinite ammo** | on enable: snapshot each ammo stack (`AMMO[slot]` + `AMMO_TYPE[slot]`); tick: `stack<base → write base`, `stack>base → base=stack` (pickups accumulate); on disable: write base back and remove the injected stack. If no matching ammo exists: `SetDefaults(useAmmo)` into an empty slot (the `useAmmo` value **is** the ammo item id) with `stack=9999` |
| Spawn item | `Item.SetDefaults(id,false)` into an empty inventory slot (prefer hotbar 0–9), `Item.stack` for count |
| Weapon edits | set `Item.damage/crit/useTime/shootSpeed/mana`; **on=write+remember original, off=restore**; revert = `SetDefaults(type,false)` |
| Held weapon | `Player.lastHotbarItem` (**this port has no `selectedItem`**) + `inventory`; `useAmmo>0` means ranged |
| Slot-kind filtering | Ammo slots (54–57) list only ammo, coin slots (50–53) only coins: compress the ID set from the item table into a **range string** embedded in the script (~250 chars) and test membership by range at runtime — no file reads |
| Item name | `Terraria.Lang.GetItemNameValue(id)` via `runtime_invoke` — **~10 ms per call**, use an offline name table instead |
| **Inventory CRUD** | slot count **read at runtime** (this port: **59** slots = 0–9 hotbar / 10–49 main / 50–58 coins+ammo; `arr.add(0x18).readS32()`); read = per-slot `type/stack`; add = `SetDefaults(id,false)` + `stack` (clamp by `Item.maxStack`); delete = `SetDefaults(0,false)`; modify = rewrite `stack` / copy to an empty slot / overwrite via the item picker; refresh with **dirty checks** (only update changed tiles) |
| Weather "follow vs hold" | when syncing, **also compare the switch's real checked state** (comparing internal state alone misses UI repairs); tag auto-synced switches so they *don't* hold the weather (it may end naturally → switch turns off), while user-opened ones re-assert every frame; turning off = stop this round immediately + 2.5 s mute |
| Infinite-ammo traps | item fields must be written with `setOn(IL.Item,…)`; never leave the legacy `topUpAmmo()` running (it forces stacks to 9999 and fights the base tracking) |

## 6. Mod-menu design (Android system-UI version)

### 6.1 Why not JsHook's modmenu (ImGui)
| | modmenu | **system UI (this design)** |
|---|---|---|
| Drawn by | JsHook daemon (ImGui) | the game process itself (`Activity.addContentView`) |
| Touch | **falls through** to the game | normal View dispatch — **never falls through** |
| Lifecycle | leftover floating icon | belongs to the game process, gone with it |
| Deps | JsHook graphics API + schema | public framework APIs only |

### 6.2 Skeleton
```js
act.addContentView(panel, new FrameLayout.LayoutParams(dp(250), WRAP));
// panel: LinearLayout with a unique contentDescription → a re-push sweeps the old panel away
```
Layout: `[title bar (draggable, ▾ collapses)] [status line] [tab bar] [scroll area]`.
Overlays (item picker / number pad) are another `addContentView` with their own touch-swallowing listener.

### 6.3 Spec-driven node system
`page` (tab) / `head` (collapsible group) / `group` (code-controlled visibility) / `row` (equal-width buttons) /
`seek` (slider + value) / `text` / `iconrow` (icon+text, whole row clickable) /
`labelbtn` (text + small trailing button, e.g. `Damage +50 [edit]`) / `btn` / `sw` / `note`.

### 6.4 Key implementation points
- **Tabs**: a `page` node builds a container + an equal-width tab; switching is `setVisibility`.
  `showPage()` also fires a **page-enter hook** (character page = read stats, weapon page = read weapon, time page = sync slider).
- **Two-column switches**: consecutive non-`wide` `sw` nodes are paired into one row (weight 1 each).
- **Auto height**: `body.measure(MeasureSpec(w, AT_MOST), MeasureSpec(0, UNSPECIFIED))` then
  scroll height = `min(content, available)` (available = screen − overlay Y − margin) → nothing gets clipped.
- **Virtual list (6000 items, no lag)**: `[top spacer][window of 6–8 rows][bottom spacer]`, fixed `ROW_H`;
  spacers keep the total height constant (no jumping); `OnScrollChangeListener` computes `first = scrollY / ROW_H`
  and **only the row that scrolled out is moved to the other end and refilled** (ring reuse).
  `first` must be clamped to `[0, totalRows − windowRows]`, otherwise you can scroll into blank space.
- **Search**: `EditText` (`setInputType(1)`, real system IME) + a `TextWatcher` dynamic class, filtering an
  **offline name table** (zero il2cpp calls); hide the IME with `InputMethodManager.hideSoftInputFromWindow`.
- **Number pad**: inside a game window the system IME is unreliable — use a built-in keypad for counts.

### 6.5 Performance & stability hard limits
- **Never call `Java.registerClass` on a hot path.** Every dynamic class adds a `DexClassLoader`; ART encodes the
  class-loader context **recursively**, and enough classes cause a **stack overflow that kills the game**
  (tombstone: `ClassLoaderContext::EncodeContextInternal ↔ EncodeSharedLibAndParent` recursing 512 frames,
  `Cause: stack pointer is not in a rw map; likely due to stack overflow`).
  → one class per listener type, dispatched by `View.setTag(name)`; `postMain` = one `Runnable` + a queue;
  touch-swallow/drag listeners are singletons. Self-check: `grep -c 'Java.registerClass' 系统菜单.js` (should be 6–7 factories only).
- **`extends` in `Java.registerClass` does not work here** (the dynamic class always extends `java.lang.Object`,
  `BaseAdapter`/`ArrayAdapter` alike) → you cannot subclass Android widgets, so `ListView`/`RecyclerView` adapters are
  impossible; `implements` works (all interface methods required). Hence the hand-written virtual list.
- Keep heavy data (names, atlas rects) **offline**; never loop over thousands of objects inside the game.

## 7. Item-icon pipeline (offline from the APK)

1. Assets live in `assets/bin/Data/data.unity3d` (UnityFS v8, LZ4). Two 16-byte alignment quirks (block info,
   and data-block start = align16 after header+blocksInfo; a 7-byte gap). → `脚本/extract_bundle.py`.
   Release build has no type tree → hand-written Texture2D parser → `脚本/unity_tex.py`.
2. **The atlas rect table is plain in the APK**: `resources.assets` offset **18755426**:
   `int32 count(6230)` + 6230 records × **22 bytes**, **sorted by key**:
   `key:int32, AtlasIndex:int32, w/h/x/y:int16×4, scale:int16, TileDataOffset:int32`.
   A second identical table sits at offset 3042920 (1024 low-res packing).
3. **`key = int32(CRC32("item_<id>.png"))`** (lowercase, `.png`; verified 26/26 against runtime values).
   To relocate the table after an update: search `resources.assets` for a byte signature built from runtime
   `PackedEntry.TextureId` values.
4. **The atlas PNG is stored vertically flipped** → crop `(X, 2048−Y−H, X+W, 2048−Y)`
   (forgetting this yields "top aligned, bottom garbled" tiles).
5. **Alias items** (~181: legacy items sharing another item's texture, e.g. id 3665 "Trapped Chest" uses id 48's
   texture) don't follow `item_<id>.png` → read `TextureAssets.Item[id].Value.PackedEntry.TextureId` at runtime and
   look the rect up offline (`脚本/补别名图标.py gen|collect|parse`). 33 of them are not atlas-packed at all → ID placeholder.
6. **Delivery into the game**: rect table compressed to 9 chars/item and embedded in the script (`ICON_TABLE`,
   6233 items ≈ 55 KB, zero runtime deps). Atlas pages: **game-private cache** (`cache/dsha_atlas_N.png`, the normal
   path, no server needed) → local HTTP `127.0.0.1:8899` (fetched on a background thread, then cached) → `/sdcard`
   direct read (blocked on this device: `exists()=true` but `canRead()=false`; `requestLegacyExternalStorage` is
   ignored for targetSdk ≥ 30).
7. **Name table**: `Lang.GetItemNameValue` costs ~10 ms/call (24 tiles = 300 ms lag) → generate `ITEM_NAMES` offline
   (`脚本/生成名称表.py`, ids 0..6265), zero runtime calls, runtime lookup only as fallback.

## 8. Pitfall quick list (full list: `参考/踩坑清单.md`, 39 entries)

- Frida wrapper traps: `Java.use` detached loses `this`; `findViewById()` returns `android.view.View` (needs `Java.cast`);
  `getParent()` returns a `ViewParent` (no `removeView`/`getHeight`).
- Empty logs: the game being **backgrounded** kills the log channel (bring it to the front first); read logs with `exec`.
- `Java.scheduleOnMainThread` **drops tasks posted from the main thread** → `onMain` needs an is-main fast path.
- Warm-path probing: enumerating all classes / reading uninitialised statics / looping thousands of `Asset<T>.Value`
  reads causes a Frida-side access violation (script dies silently and the game's main thread stalls). **Targeted reads only.**
- Large scripts are fine over MCP (~300 KB), but **a single 340k-char line breaks the pipeline** — split into chunks.
- View calls must run on the main thread (`CalledFromWrongThreadException`); suppress switch callbacks when setting state.

## 9. Surviving game updates + self-check

- Logic addresses classes/fields/methods **by name** → minor updates keep working; method lookups use an **argc fallback**.
- Snapshots that may need regeneration: **icon rect table**, **name table**, **category table**, **alias table**;
  the item-range upper bound is read **at runtime** (`TextureAssets.Item` length) so brand-new items still appear.
- How to regenerate and where to look after an update: `版本与时效.md`.
- Self-check: `--sub "selfTest: false||selfTest: true"`, and read the hook/atlas lines in the log after every push.

## 10. Package contents

```
SKILL.md / SKILL.en.md   this file (Chinese / English)
版本与时效.md             verified-on dates, game build, which numbers go stale and how to rebuild
README.md                how to use this package (shortest paths)
参考/踩坑清单.md           39 measured pitfalls (symptom → cause → fix)
参考/菜单实现细节.md       copy-paste code patterns (tag dispatch, virtual list, weather sync, …)
成品/系统菜单.js           ready-to-run mod menu (~285 KB, icon + name tables embedded)
成品/面板说明.md           end-user manual for the menu
脚本/                      jshook.py, icon/name table generators, APK unpacker, Texture2D parser
数据/                      item rect tables (6085 + 148 alias entries)
atlas PNGs live in /sdcard/Download/DSHA/terraria_icons/
```
