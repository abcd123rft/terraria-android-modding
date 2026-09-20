---
name: terraria-modding
description: 修改安卓《泰拉瑞亚》（Unity + IL2CPP，国服 com.xd.terraria，国际服同理）时使用：用 Frida/JsHook 注入脚本，按名字操作 il2cpp 运行时做功能修改（无敌/飞行/移速/事件/时间/物品/无子弹发射/武器改造），用 Android 系统 UI（Activity.addContentView）做**触摸不穿透、退出即消失**的游戏内修改器菜单，并从安装包离线提取物品图标。含成品脚本、可复用工具、完整踩坑清单。当用户要求给泰拉瑞亚做修改器、加功能、做菜单界面、或提取游戏素材时加载本技能。
---

# 泰拉瑞亚 · 修改与修改器菜单开发技能

> 本技能记录的是**本机实测过的**做法与坑（不是通用攻略）。
>
> **时效性 / Freshness**：验证于 **2026-09-19**，目标为**国服 1.4.56002**（versionCode 303538，
> Unity 2021.3.26f1c1 / IL2CPP，物品数 6266）。本文里凡是**具体数字/偏移/条数**（图集表偏移、物品 ID 上限、
> 名表与图标表覆盖范围等）都属于**易随更新失效**的快照 ⚠️；而「按名字取类/字段/方法」的方法论与菜单设计
> 属于**长期有效** ✅。哪些会过期、过期后怎么重建，见 **`版本与时效.md`**。英文版见 **`SKILL.en.md`**。

## 项目里可直接用的东西（AI 落地首选）

| 想干什么 | 直接用项目里的文件 |
|---|---|
| 下发/调试脚本 | `/sdcard/Download/DSHA/泰拉瑞亚项目/控制面板/jshook.py` |
| 拿来就能跑的修改器 | `/sdcard/Download/DSHA/泰拉瑞亚项目/控制面板/系统菜单.js` |
| 功能与用法说明 | `/sdcard/Download/DSHA/泰拉瑞亚项目/控制面板/面板说明.md` |
| 物品全量数据（6227 件 × 141 字段） | `/sdcard/Download/DSHA/泰拉瑞亚项目/物品库/out/terraria_items_all.csv` |
| 图标/名字/分类表的重建脚本 | `/sdcard/Download/DSHA/泰拉瑞亚项目/物品图标/*.py`、`物品库/生成名称表.py` |
| 图集 PNG（图标交付用） | `/sdcard/Download/DSHA/terraria_icons/atlas_{0,1}.png` |
| 解包产物（离线分析用） | `/root/DshaWorks/unpack/`（resources.assets 等，约 856MB） |

## 0. 30 秒索引

| 我要干什么 | 看哪节 / 用哪个文件 |
|---|---|
| 直接给游戏装上一个能用的修改器 | §2：`成品/系统菜单.js` + `脚本/jshook.py` |
| 加一个新功能（改字段/调方法） | §3 核心方法 + §5 配方速查 |
| 做的效果「没生效」 | §4 持续效果的正确挂法 + `参考/踩坑清单.md` |
| 改菜单界面 / 加控件 | §6 菜单设计与实现 |
| 物品图标 / 素材 | §7 图标流水线 + `脚本/构建图标表.py` 等 |
| 游戏更新了 / 崩了 | §9 抗更新 + `参考/踩坑清单.md` |

---

## 1. 环境与通道

- **目标**：安卓国服《泰拉瑞亚》`com.xd.terraria`，Unity **2021.3.26f1c1** + **IL2CPP**（`libil2cpp.so`），
  Activity 是 `com.unity3d.player.UnityPlayerActivity`，横屏 2376×1080、density 3.0。
- **注入通道**：JsHook（Frida 宿主，MCP 在 `http://127.0.0.1:19820/mcp`，key 在 `/root/.dsh/jshook_key`），
  客户端就是本包里的 `脚本/jshook.py`：
  ```bash
  python3 jshook.py targets                 # 列出目标
  python3 jshook.py exec --file x.js --wait 6      # 先 unload 再下发，等 6 秒读日志
  python3 jshook.py exec --file x.js --sub "selfTest: false||selfTest: true"   # 打补丁后下发
  python3 jshook.py log --tail 200          # 单独读日志
  ```
  `exec` 返回 `{ok, exec, unload, log}`，**日志要跟着 exec 一起读**（单独读经常是空的）。
- **免 root**：JsHook 在未 root 设备上用虚拟化/沙箱容器跑游戏副本，可以注入；纯注入方案本身需要 root 或容器。
- **设备侧**：容器里可用 `python3 /root/.dsh/adb-shell.py '<单条命令>'`（不能带管道/重定向），
  查进程/读 `/proc`、拷 tombstone 等；`/app/*` 是零配置的 App 层接口（启动应用、读屏、截屏…）。
- **改文件**：游戏私有目录 `/data/user/0/com.xd.terraria/…` 容器里读不到，但**游戏进程自己能写**（见 §7 缓存方案）。

## 2. 五分钟跑起来（下发成品菜单）

```bash
# 1) 确认游戏在前台（后台时 JsHook 日志会读不到）
T=$(cat /root/.dsh/.bridge_token); curl -s "http://127.0.0.1:3090/app/launch?pkg=com.xd.terraria&token=$T"

# 2) 下发成品菜单
cd /sdcard/Download/DSHA/skills/terraria-modding/成品
python3 ../脚本/jshook.py exec --file 系统菜单.js --wait 7
```
正常日志：
```
[系统菜单] 面板已挂载（content，宽 250dp，顶层节点 6 个）
[系统菜单] 就绪：面板已挂载，触摸不会穿透
[系统菜单] 图标：图集 0 就绪 2048×2048（来源 私有缓存）
[系统菜单] 已挂 PlayerFrame 持续效果钩子
[系统菜单] 已挂 UpdateEquips 钩子（argc=1，每帧属性写入点）
```
图标需要两张图集（`/sdcard/Download/DSHA/terraria_icons/atlas_0.png`、`atlas_1.png`）：
菜单启动时会在**后台线程**把它们拉进游戏私有缓存（先试本地 HTTP `127.0.0.1:8899`，见 `脚本/图标HTTP服务.py`），
之后一直走缓存，不再需要服务。

**自检**：`--sub "selfTest: false||selfTest: true"` 会跑全量自检（属性/武器/事件/图标/布局）并写日志。

## 3. 核心方法：按名字操作 il2cpp（不要用固定地址）

```js
// 1) 拿到 Assembly-CSharp 的 image，再按「命名空间+类名」取类
var il = { /* NativeFunction 包装 il2cpp_* 导出，见成品脚本的 IL 模块 */ };
var Main   = il.class_from_name(ACS, "Terraria", "Main");
var Player = il.class_from_name(ACS, "Terraria", "Player");

// 2) 字段：按名字查（结果要缓存！每次按名字查是线性扫描）
var f = il.class_get_field_from_name(Player, "moveSpeed");   // → FieldInfo*
il2cpp_field_get_value(obj, f, buf);       // 读实例字段
il2cpp_field_static_get_value(f, buf);     // 读静态字段
il2cpp_field_set_value(obj, f, buf);       // 写实例字段
il2cpp_field_static_set_value(f, buf);     // 写静态字段

// 3) 方法：按名字 + **参数个数**查；游戏更新可能改 argc → 一定试多个候选
function findMethod(cls, name, argcs) {
  for (var i = 0; i < argcs.length; i++) {
    var m = il2cpp_class_get_method_from_name(cls, name, argcs[i]);
    if (!m.isNull()) return { m: m, argc: argcs[i] };
  }
  return null;
}

// 4) 调方法：runtime_invoke（慢但通用）
var args = Memory.alloc(8 * n);            // 参数指针数组
args.writePointer(intArg(1));              // 值类型要自己 alloc 一块再放指针
il2cpp_runtime_invoke(m, objOrNull, args, excPtr);
```
**类型读写**（`field_get_type` → `type_get_name` 判断）：
`Boolean`→1 字节、`Byte/SByte/Int16`→对应宽度、`Int32`→`writeS32`、`Single`→`writeFloat`、`Double`→`writeDouble`（`Main.time` 是 Double）、
`String`→`readPointer` 再 `readUtf8String`。
**数组**（il2cpp）：`data = arr.add(0x20)`，`length` 在 `arr.add(0x18).readS32()`；
`TextureAssets.Item` 就是 `Asset<Texture2D>[]`，元素 = 指针。

## 4. 持续效果的正确挂法（最容易「没生效」的地方）

### 4.1 钩谁
本环境**`Interceptor.onLeave` 不回调**（同一指针挂 onEnter 计数正常、onEnter+onLeave 恒为 0）→ 只能用 `onEnter`。
一帧内 `Player` 的方法顺序（实测）：
```
Update → UpdateSocialShadow → UpdateImmunity → ResetEffects → UpdateBuffs → UpdatePet
→ UpdateEquips → UpdateArmorSets → UpdateLifeRegen → UpdateManaRegen → UpdateJumpHeight
→ ItemCheck → PlayerFrame
```
- **`PlayerFrame/0`**：帧内最后一个，适合写「不会被 ResetEffects 覆盖」的字段
  （`creativeGodMode`、`immune`、`wingsLogic/wings/wingTime`、`maxMinions`、`luck`…）。
- **`Player.UpdateEquips/1`**：在 `ResetEffects` **之后**、移动计算**之前** ——
  `moveSpeed / maxRunSpeed / accRunSpeed / runAcceleration / statDefense` 这些**每帧被 ResetEffects 清零**的字段，
  必须在这里写才有用（只写 PlayerFrame 等于白写，这是「移速修改不生效」的真因）。
- 钩子地址 = `class_get_method_from_name(...).readPointer()`，`onEnter(a)` 里 `a[0]` 就是 `this`。
- 别只挂一次就以为好了：**挂上后打日志**（`已挂 UpdateEquips 钩子（argc=1）`），不然签名不对会静默落空。

### 4.2 心跳（50ms setInterval）
适合：状态类字段的复写（天气）、背包扫描（无子弹发射）、时间条同步、手持武器轮询。

**性能上真正要盯的两件事**（实测 2026-09-20）：
1. **一次 Java 调用 ≈ 0.13–0.28ms** —— 界面重复创建才是卡顿主因（重建 120 个 View = 100ms+）。
   弹层/列表/键盘一律「建一次复用」；`setText`/`setBackground`/`isChecked` 全部做「值没变就不碰 View」，
   去重标记记在 **View 自己身上**（`v.__txt`），别记在按 id 的模块级 map（面板重挂后会误判成已设置）。
2. **字段访问别每次进 il2cpp**（2–4µs/次）—— 用 `il2cpp_field_get_offset` 取偏移后
   `p.add(off).writeFloat(v)` 直读直写（1.4µs，零 il2cpp 调用）；每个字段**首次**直读时用官方 API 对拍一次，
   不一致就永久退回慢路径。负缓存必须用 `ck in cache` 判断（`if (cache[ck])` 对 null/false 永远判假）。
重活（网络、批量裁图）**不要放主线程**：主线程做网络会抛 `android.os.NetworkOnMainThreadException`，
放到 `setTimeout`（Frida 脚本线程）里做。

### 4.3 写字段的两个「接口陷阱」
- **写物品字段别用写 Player 的接口**：`setF(obj,'stack',v)`（内部固定用 `Player` 类查字段名）会静默失败
  （日志 `无字段 stack`）→ 必须 `setOn(IL.Item, item, 'stack', v)`。**这是「无子弹发射关闭后数量没还原」的真因。**
- 写完要**回读校验**并打日志，否则静默失败很难发现。

## 5. 功能配方速查（都是实测过的字段/方法）

| 功能 | 写法 |
|---|---|
| 无敌 | `Player.creativeGodMode=true`、`immune=true`、`immuneTime=3600`、`lavaImmune=true`（每帧写） |
| 上帝模式 | `statDefense=200`、`endurance=0.5`、`lavaImmune=true` |
| 满配 | `statDefense=100`、`meleeDamage/rangedDamage/magicDamage/minionDamage=3`、`*Crit=100`、`wingTime(Max)=200` |
| **飞行（无翅膀）** | 必须同时写 `wingsLogic=1`、`wings=1`、`wingTime=200`、`wingTimeMax=200`（只写 wingTime 完全无效） |
| **移速** | 在 **UpdateEquips** 钩子里写 `moveSpeed=2.2`、`maxRunSpeed=12`、`accRunSpeed=10`、`runAcceleration/runSlowdown=0.6`、`jumpSpeedBoost=5` |
| 幸运/召唤上限 | `luck=1`、`maxMinions=20` |
| 清减益 | `Player.DelBuff(i)` 遍历 buff 槽，对 `DEBUFF_IDS` 里的 id 调用 |
| **难度** | `Player.difficulty` 是 **Byte**：0=经典 1=专家 2=大师 → `(cur+1)%3` 循环 |
| 血月/日食 | `Main.bloodMoon / Main.eclipse`（**每帧**复写：游戏每帧按昼夜清掉） |
| **下雨** | **直接写字段**：`Main.raining=true`、`Main.rainTime=36000`、`Main.maxRaining=1`（`StartRain/3` 要满足前置条件，实测不生效） |
| **沙尘暴** | `Sandstorm.Happening=true`、`TimeLeft=36000`、`Severity=1`、`IntendedSeverity=1`（只写 Happening 会被 `UpdateTime` 当帧取消） |
| 入侵 | `Main.StartInvasion(type)`：哥布林 1 / 海盗 3 / 火星 4；关 = `invasionType=0, invasionSize=0` |
| 派对/灯笼夜 | 静态字段 `BirthdayParty.ManualParty`、`LanternNight.ManualLanterns` |
| 世界时间 | `Main.time`（Double，0–54000）、`Main.dayTime`（bool）；锁定 = 每次心跳写回 |
| **无子弹发射** | 开：记住每种弹药的 `stack` 基准（`AMMO[槽]`）+ 记录 `AMMO_TYPE[槽]`；心跳里 `stack<基准→写回基准`、`stack>基准→抬基准`（捡到的累加）；关：写回基准、移除临时塞的弹药。**没有对应弹药时**临时 `SetDefaults(useAmmo值)`（`useAmmo` 的值就是弹药物品 ID）+ `stack=9999` |
| 添加物品 | `Item.SetDefaults(id,false)` 写进空格子（`Player.inventory` 数组，优先 0–9 快捷栏），数量用 `Item.stack` |
| 武器改造 | 改 `Item.damage/crit/useTime/shootSpeed/mana` 等；**开=写入并记原值，关=写回原值**；恢复原厂 = `SetDefaults(type,false)` |
| 读手持武器 | `Player.lastHotbarItem`（**本移植版没有 `selectedItem`**）+ `inventory` 数组；`useAmmo>0` 是远程 |
| 物品名 | `Terraria.Lang.GetItemNameValue(id)`（`runtime_invoke`）；**别每条都调**（~10ms/次），离线名表优先 |
| **背包操作（增删改查）** | 槽位**按数组真实长度**（本移植版 **59** 格：0–9 快捷栏 / 10–49 主背包 / 50–58 钱币弹药，`arr.add(0x18).readS32()`）；查=逐格读 `type/stack`；增=`SetDefaults(id,false)`+`stack`（按 `Item.maxStack` 封顶）；删=`SetDefaults(0,false)`；改=改写 `stack`/复制到空格/用物品面板覆盖；刷新用**脏检查**（只更新变了的格子）。**类型化筛选**：弹药格（54–57）只列弹药、钱币格（50–53）只列钱币——弹药/钱币 ID 集合从物品表离线生成**区间串**内嵌脚本（约 250 字符），运行时按区间判成员，零文件读取；筛选与分类/搜索叠加 |
| 天气「跟随 vs 维持」 | 同步时**同时比对开关真实勾选状态**（只比内部 STATE 会漏补 UI）；用 `auto` 标记区分「跟随游戏」（不维持，自然停→开关自动灭）与「用户点开」（每帧复写=无限维持）；关闭=立刻停本轮 + 2.5s 静默期 |
| 无子弹发射的坑 | 写物品字段只能用 `setOn(IL.Item,…)`；**别同时留旧版 `topUpAmmo()`**（它把弹药补到 9999，和基准追踪打架） |

## 6. 修改器菜单设计与实现（Android 系统 UI 版）

### 6.1 为什么不用 JsHook 的 modmenu
| | modmenu（ImGui） | **系统 UI（本方案）** |
|---|---|---|
| 谁来画 | JsHook 守护进程 | 游戏进程自己（`Activity.addContentView`） |
| 触摸 | **会穿透**，得额外钩 `UnityEngine.Input` | **不穿透**，走标准 View 事件分发 |
| 退出 | 遗留悬浮图标清不掉 | 属于游戏进程，退出即消失 |
| 依赖 | JsHook 图形 API + schema | 只用公开框架 API |

### 6.2 骨架
```js
act.addContentView(panel, new FrameLayout.LayoutParams(dp(250), WRAP));
// 面板根：LinearLayout，setContentDescription(唯一标记) —— 重新下发时靠它 sweep 掉旧面板
```
结构：`[标题栏(可拖动/▾收起)] [状态栏] [顶部标签页] [滚动区]`。
弹层（选物品/数字键盘）再叠一层 `addContentView`，自带 `OnTouchListener` 吞触摸。

### 6.3 节点体系（spec 驱动，加控件只改数据）
`page`（标签页）/`head`（折叠组）/`group`（代码控显隐）/`row`（等宽按钮排）/
`seek`（滑块+数值）/`text`（可改字标签）/`iconrow`（图标+文字，可整行可点）/
`labelbtn`（文字+行尾小按钮，例「伤害增量：50 [改]」）/`btn`/`sw`/`note`。

### 6.4 关键实现点
- **标签页**：`page` 节点 → 建页容器 + 顶部等宽 tab；切换只切 `setVisibility`。`showPage()` 里加
  **进页钩子**（角色页自动读属性、武器页自动读武器、时间页同步时间条）。
- **开关两列**：`buildInto` 遇到连续两个非 `wide` 的 `sw` 就并排放一行（各 weight 1），落单的占整行。
- **自适应高度**：`body.measure(MeasureSpec(width, AT_MOST), MeasureSpec(0, UNSPECIFIED))` 后
  把滚动区高度设成 `min(内容高, 可用高)`（可用高 = 屏高 − 浮层 Y − 余量）→ 数字键盘/列表都不会被裁掉。
- **虚拟列表（6000 件不卡）**：`[上占位][6~8 行窗口][下占位]`，行高固定 `ROW_H`，
  占位高度 = `first*ROW_H` / `(total-first-N)*ROW_H`（两段之和恒定 → 不跳）；
  监听 `View.OnScrollChangeListener` 算 `first = scrollY / ROW_H`，**跨一行只把划出去那行挪到另一端重填**（环形复用）；
  `first` 必须夹在 `[0, total-N]`，否则滚到底会滑进一片空白。
- **搜索**：`EditText`（`setInputType(1)`）用系统输入法 + `TextWatcher`（一个动态类实现 3 个方法），
  按**离线名表**过滤（零 il2cpp 调用）；选中物品后 `InputMethodManager.hideSoftInputFromWindow` 收起。
- **图标**：`iconrow` + `ImageView.setImageBitmap(ICON.bitmap(id, dp44))`，点图标行直接弹物品面板。
- **数字键盘**：游戏窗口里系统 IME 不可靠，数量输入用**面板内置键盘**（不回弹 IME 更稳）。

### 6.5 性能与稳定性红线
- **热路径里绝不 `Java.registerClass`**：每个动态类都会新增一个 `DexClassLoader`，
  ART 编「类加载器上下文」是**递归**的，注册多了会**栈溢出把游戏打崩**
  （tombstone 特征：`ClassLoaderContext::EncodeContextInternal ↔ EncodeSharedLibAndParent` 反复递归 512 帧
  + `Cause: stack pointer is not in a rw map; likely due to stack overflow`）。
  → **每类监听器只注册一个类**，用 `View.setTag(名字)` 分发；`postMain` 只注册一个 `Runnable` + 队列；
  吞触摸/拖动监听器共用一个实例。自查：`grep -c 'Java.registerClass' 系统菜单.js` 应只在 6~7 个工厂里。
- **`Java.registerClass` 的 `extends` 不生效**（实测动态类父类永远是 `java.lang.Object`，
  `BaseAdapter`/`ArrayAdapter` 都一样）→ **不能给 Android 类做子类**，`ListView`/`RecyclerView` 的 Adapter 路线走不通；
  `implements` 可以用（接口所有方法都要实现）。所以列表要**手写虚拟列表**。
- **名称/图集等重数据离线做**，别在游戏里循环探测。

## 7. 物品图标流水线（从安装包离线提取）

1. **素材位置**：APK 的 `assets/bin/Data/data.unity3d`（UnityFS v8、LZ4；`resources.assets` 里是元数据+贴图）。
   解包两个 16 字节对齐坑：块信息前对齐；数据块起点 = 头部+块信息后再对齐（差 7 字节）。
   → `脚本/extract_bundle.py`；发布版无类型树 → 手写 Texture2D 解析 `脚本/unity_tex.py`。
2. **图集矩形表就在包里**（明文）：`resources.assets` 偏移 **18755426**：
   `int32 条数(6230)` + 6230 条 × **22 字节**，**按 key 升序**：
   `key:int32, AtlasIndex:int32, w/h/x/y:int16×4, scale:int16, TileDataOffset:int32`。
   另一份同构表在偏移 3042920（1024 低清版）。
3. **key = `int32(CRC32("item_<id>.png"))`**（小写 + `.png`，26/26 实测命中）。
   找表偏移的办法：用运行时 `PackedEntry.TextureId` 的真值拼字节签名在 `resources.assets` 里搜。
4. **图集 PNG 上下翻转存放** → 裁剪矩形 `(X, 2048−Y−H, X+W, 2048−Y)`（不翻会得到「上对下错位」的花屏）。
5. **别名物品**：约 181 件（旧版/共用贴图，例：3665 受困宝箱用的是 id 48 的贴图）贴图名不是
   `item_<id>.png` → 用运行时 `TextureAssets.Item[id].Value.PackedEntry.TextureId` 拿到 key 再离线查矩形
   （`脚本/补别名图标.py gen|collect|parse`；剩 33 件贴图没进图集，只能显示 ID 占位）。
6. **进游戏**：矩形表压成 9 字符/件内嵌进脚本（`ICON_TABLE`，6085→6233 件 ≈ 55KB，运行时零依赖）；
   图集交付三条通道：**游戏私有缓存**（`cache/dsha_atlas_N.png`，日常走这条，不需要服务）→
   容器内 HTTP `127.0.0.1:8899`（后台线程拉一次并写缓存）→ `/sdcard` 直读（本机被分区存储挡住，
   `File.exists()=true` 但 `canRead()=false`，`requestLegacyExternalStorage` 对 targetSdk≥30 无效）。
7. **名字表**：`Lang.GetItemNameValue` 一次 ~10ms，一页 24 格就 300ms 卡顿 →
   离线生成 `ITEM_NAMES`（`脚本/生成名称表.py`，覆盖 ID 0..6265），运行时零调用，表外再兜底问游戏。

## 8. 踩坑速览（完整版见 `参考/踩坑清单.md`）

- Frida 包装类型坑：`Java.use` 摘出来会丢 `this`（报 `classFactory of undefined`）；
  `findViewById()` 返回 `android.view.View`（要 `Java.cast` 成 ViewGroup）；`getParent()` 是 `ViewParent`（没有 `removeView`/`getHeight`）。
- 游戏日志读不到：**游戏切后台就没了**（先用 `/app/launch` 调回前台）；单独 `log` 常为空，要跟 `exec` 一起读。
- `Java.scheduleOnMainThread` **在主线程里再调会丢任务** → `onMain` 必须有「已在主线程就直接执行」快路径。
- 遍历 Assembly-CSharp 全部类 / 读未初始化静态字段 / 对上千物品循环读 `Asset<T>.Value`
  → Frida 侧 access violation 静默死掉，还会把游戏主线程一起拖住。**只做定点读取。**
- 大脚本可以走 MCP（300KB 级 OK），但**单行 34 万字符会挂**，base64/大字符串要拆成多段拼接。
- `setText`/`setChecked` 等 View 操作**必须在主线程**（`CalledFromWrongThreadException`）；
  `Switch` 的程序化赋值要用 `suppress` 标记避免触发回调。

## 9. 抗游戏更新与自检

- 功能逻辑**按名字**取类/字段/方法 → 小版本更新基本直接用；方法查找**带 argc 兜底**（`[1,0,2]`）。
- 需要重跑的快照数据：**图标矩形表**（新物品没图标）、**名称表**、**分类表**、**别名物品表**；
  物品列表上限已改成**运行时读** `TextureAssets.Item` 长度 → 新物品照样能列出（名字走运行时兜底）。
- 自检：`--sub "selfTest: false||selfTest: true"`；下发后看日志里的钩子命中/图集来源。

## 10. 本包内容

```
SKILL.md                 ← 本文件（主技能）
成品/系统菜单.js          ← 现成可用的修改器菜单（284KB，含图标表与名表）
成品/面板说明.md          ← 使用者视角的完整说明（功能、布局、性能、更新应对）
脚本/jshook.py           ← JsHook MCP 客户端（下发/日志/卸载）
脚本/构建图标表.py         ← 安装包 → 物品矩形表 + 图集复制
脚本/注入图标表.py         ← 矩形表 → 系统菜单.js 的 ICON_TABLE（--write）
脚本/补别名图标.py         ← 别名物品图标补齐（gen/collect/parse）
脚本/生成名称表.py         ← 物品库 CSV → 离线名表（--write）
脚本/图标HTTP服务.py       ← 容器内静态服务（8899），仅首次建缓存时需要
脚本/extract_bundle.py · unity_tex.py  ← 解包 UnityFS 节点 / 手工解析 Texture2D
数据/物品矩形表.json(_补充) ← ID → 图集页/X/Y/宽/高
图集在 /sdcard/Download/DSHA/terraria_icons/（atlas_0.png / atlas_1.png，2048²）
```
