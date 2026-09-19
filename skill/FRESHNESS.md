# 版本与时效性 / Version & Freshness

**EN summary:** everything in this repo was measured on **2026-09-19** against the CN build
**1.4.56002** (versionCode 303538, Unity 2021.3.26f1c1 / IL2CPP, item count 6266, Android 16, arm64).
Numbers such as the atlas-table offset, item-id ranges and covered id ranges are **snapshots** and go stale
after a game update — §2 says how to rebuild each one. The methodology (address il2cpp by name, Android
system-UI menus, offline extraction) is version-independent.

> **本技能包所有结论都是「某一时刻在某台设备上实测」的结果，不是永久真理。**
> Every conclusion here was measured **at a point in time on one device** — treat the numbers as a snapshot.
>
> 验证日期 / Verified on: **2026-09-19**
> 验证设备 / Device: OnePlus PKR110 · Android 16 (SDK 36) · arm64 · 容器在设备内

## 1. 实测时的目标版本 / Target build at verification time

| 项 | 值 | 会不会变 |
|---|---|---|
| 包名 | `com.xd.terraria`（国服） | ✅ 稳定（换包名才变） |
| versionName / versionCode | `1.4.56002` / `303538` | ⚠️ **每次更新都变** |
| Unity / 脚本后端 | `2021.3.26f1c1` / IL2CPP | ⚠️ 大版本更新可能变（方法/字段名一般仍在） |
| Activity | `com.unity3d.player.UnityPlayerActivity` | ✅ 稳定 |
| 物品总数（`TextureAssets.Item` 长度） | `6266` | ⚠️ 加物品就变（脚本运行时读，不用改） |
| 图集页 | `Item1`/`Item2` 2048²，另有 3 张 1024² | ⚠️ 重打包可能改 |
| 注入环境 | JsHook MCP `127.0.0.1:19820`，key `/root/.dsh/jshook_key` | ✅ 稳定 |

## 2. 会「过期」的硬编码常量 / Hard-coded numbers that go stale

| 常量 | 值 | 在哪 | 失效后怎么办 |
|---|---|---|---|
| 图集矩形表偏移 | `resources.assets` **18755426** | `脚本/构建图标表.py` 的 `DB_OFFSET` | 用运行时 `PackedEntry.TextureId` 拼字节签名在 `resources.assets` 里重搜，改 `DB_OFFSET` |
| 记录长度 / 条数 | 22 字节 / 6230 条 | 同上 | 一般不变；条数随物品数变 |
| 图集尺寸（裁剪翻转用） | 2048 | `构建图标表.py`、菜单 `ICON` 模块的 `ATLAS_H` | 若图集改尺寸，同步改这两处 |
| **图标矩形表**（内嵌） | ID 0..6265，6233 条有图标 | `成品/系统菜单.js` 的 `ICON_TABLE` | 重跑 `构建图标表.py` → `注入图标表.py --write` |
| **物品名表**（内嵌） | ID 0..6265 | 同上的 `ITEM_NAMES` | 重跑 `脚本/生成名称表.py --write`（数据源 `物品库/out/terraria_items_all.csv`） |
| **分类表**（内嵌） | 6265 字符 | 同上的 `CAT_MAP` | 重新导出物品库 CSV 后重跑分类生成 |
| **别名物品补充表** | 148 条 | `数据/物品矩形表_补充.json` | `脚本/补别名图标.py gen → collect → parse` |
| CRC32 命名规则 | `item_<id>.png` | `构建图标表.py` | 用运行时真值重新做一次字典攻击验证 |

## 3. 不会因为游戏更新而失效的部分 / Update-proof parts

- 所有**按名字**取类/字段/方法的逻辑（`Player.moveSpeed`、`Main.raining`、`Item.stack`…）——
  但要留意**方法参数个数**（脚本已带 `argc` 兜底：`findMethod(cls, name, [1,0,2])`）。
- 菜单 UI 方案（`Activity.addContentView` + 系统 View）、虚拟列表、tag 分发、图标三条交付通道。
- 物品列表上限是**运行时读** `TextureAssets.Item` 长度 → 新增物品照样列得出来（名字走运行时兜底、图标缺就显示 ID）。

## 4. 已知不成立/未验证的东西 / Not verified (don't assume)

| 项 | 状态 |
|---|---|
| `Java.registerClass` 的 `extends` | ❌ 本机实测**不生效**（动态类父类恒为 `Object`）——换 Frida 版本可能不同 |
| `Interceptor.onLeave` | ❌ 本机实测不触发 —— 换 Frida 版本可能不同 |
| 免 root 注入 | ⚠️ 未实测；理论上需 JsHook 虚拟化容器或重打包 APK |
| 国际服 / 其他版本 | ⚠️ 未实测，但类名字段名基本一致，`jshook.py --package` 换包名即可试 |
| 33 件未进图集的物品图标 | ❌ 目前只能显示 ID 占位（贴图是独立 Texture2D，未去解） |

## 5. 每次用之前建议做的三步自检 / 3-step self check

```bash
# ① 通道是否通
python3 脚本/jshook.py ping

# ② 下发菜单并看日志里这几行（钩子/图集来源/物品范围）
cd 成品 && python3 ../脚本/jshook.py exec --file 系统菜单.js --wait 7

# ③ 跑全量自检
python3 ../脚本/jshook.py exec --file 系统菜单.js --sub "selfTest: false||selfTest: true" --wait 12
```
日志里出现 `找不到 XXX` / `无字段 XXX` / `图集 0 不可用` 就是**该部分已随更新失效**，
按第 2 节表格重建对应数据即可（功能逻辑本身通常不用改）。

## 6. 文档时效性标注约定 / Freshness markers used in this package

- ✅ **实测通过**（有日志/截图证据）
- ⚠️ **易随更新失效**（数字/偏移/条数类）
- ❌ **实测不成立**（明确不要用）
- ❓ **未验证**（推测，需自行确认）
