# 泰拉瑞亚控制面板 · 现状与用法

> 目标形态：**注入游戏进程、在游戏画面里显示可点的修改器菜单**。
> 现有两条实现路线：**系统 UI 版（`系统菜单.js`，推荐）** 与 JsHook modmenu 版（`游戏内菜单.js`，旧方案）。

## 一、当前有哪些东西

| 资产 | 状态 | 说明 |
|---|---|---|
| `jshook.py` | ✅ **主力可用** | JsHook MCP 客户端：列出目标 / 下发脚本 / 读日志 / 卸载，命令行直接用 |
| **`系统菜单.js`** | ✅ **推荐** | **Android 系统 UI 版**修改器菜单：用 `View`/`WindowManager` 画，触摸不穿透、不留死图标，见第三节 |
| `../物品图标/` | ✅ 已打通 | **物品图标流水线**：从安装包解出「物品ID → 图集矩形」（6085 件），供菜单显示真实图标，见**第七节** |
| `游戏内菜单.js` | ⚠️ 旧方案 | JsHook `modmenu`（ImGui）版：老式悬浮菜单，触摸会穿透、遗留图标清不掉，见第四节 |
| `terraria_cli`（聊天工具） | ✅ 已挂载 | Host 侧插件（不需要浏览器授权），聊天里直接驱动 JsHook |
| 独立网页面板 | ❌ **已删除** | `board_server.py` + `board.html`，2026-09-17 按用户要求移除 |
| DSH 图形界面内嵌面板 | ⏸ 已停 | 插件 `trpan-2`，本部署拿不到授权卡片（approval prompts disabled） |

## 二、命令行用法（现在就能用）

```bash
cd "/sdcard/Download/DSHA/泰拉瑞亚项目/控制面板"

python3 jshook.py ping                       # 测通道
python3 jshook.py targets                    # 列出 JsHook 注入目标
python3 jshook.py log --tail 100             # 读最近日志
python3 jshook.py unload                     # 卸载当前脚本
python3 jshook.py exec --file "<脚本>" [--sub "旧||新"]... [--wait 1.5] [--tail 200]
echo '<脚本内容>' | python3 jshook.py exec --stdin
```

`exec` 已封装四步：**先 unload → frida_execute → 等待 → frida_read_log**，返回单行 JSON。

**JsHook MCP 端点**（不经 DSH 也能下发脚本）：

```
http://127.0.0.1:19820/mcp     POST JSON-RPC，请求头 X-Api-Key
握手：initialize → 取响应头 Mcp-Session-Id，后续请求带上
调用：tools/call {"name":"frida_execute","arguments":{"package":"com.xd.terraria","code":"..."}}
KEY：存 /root/.dsh/jshook_key；会话 id 缓存 /tmp/jshook_sid
工具共 54 个：frida_execute / frida_read_log / frida_unload / frida_list_targets / imgui_* / mem_* / kernel_* / shell_exec …
```

> ⚠️ 该端点是 **JsHook App 里的开关**，没打开时 `ping` 报 `Connection refused`（设备上也不会出现监听端口）。
> 这时要去手机上把 JsHook 的 MCP 服务打开，**反复重试不会让它自己起来**。

## 三、系统菜单：Android 系统 UI 版（推荐）

**文件**：`系统菜单.js`

**原理**：不用 JsHook 的任何图形 API，改成用 **Android 框架自己的 UI**——Frida 的 Java 桥拿到游戏 Activity，再
`Activity.addContentView()` 把一块原生 `View`（`LinearLayout` + `Button` + `Switch` + `ScrollView`）挂进
`com.unity3d.player.UnityPlayerActivity` 自己的窗口里；控件全部是 `android.widget.*` 系统控件。

```bash
python3 jshook.py exec --file 系统菜单.js --wait 2
```

**相比 modmenu 版的三个实质好处**：

| | modmenu 版（旧） | 系统 UI 版（本文件） |
|---|---|---|
| 谁来画 | JsHook 的 root 守护进程（ImGui） | 游戏进程自己（Android View 树） |
| 触摸 | **会穿透**：覆盖层只读输入、从不消费 → 点面板会同时点到游戏 | **不穿透**：事件走标准 View 分发，面板吃掉的触摸游戏收不到 |
| 连带手段 | 只能钩 `UnityEngine.Input` 让游戏「看不到」触摸 | 不需要任何输入钩子 |
| 关掉 | 跨会话遗留的图标 `closeAll()` 清不掉，严重时得重启手机 | 视图属于游戏进程，脚本卸载/游戏重启即消失 |
| 依赖 | JsHook 守护进程、modmenu schema（字段名错了只得到空白菜单） | 只用公开框架 API |

**面板结构**（2026-09-19 改版）：顶部一排**标签页**（角色 / 武器 / 事件 / 时间 / 物品 / 其它），点一下切换整页，
不再是一条长滚动里的手风琴 —— 一屏基本放得下，不用来回滚。页内**开关类两列排布**（高度省一半），
面板宽度 250dp，滚动区**按当前页内容自适应高度**（短页不留一大片空）。标题栏可按住拖动、▾ 收起成小 chip
（收起时标签栏也一起隐藏）。

**六个标签页的内容**：

| 分组 | 内容 |
|---|---|
| 角色 | 读属性 / 满配（生命 500·魔力 200）/ 回满血 / 清减益 / 改经典难度；**★ 无敌**（`creativeGodMode`）/ 上帝模式 / 持续加成 / 召唤上限拉满 / **飞行（没翅膀也能飞）** / 加速跑 / 幸运拉满 |
| 武器 | **按手持武器的种类自适应**，且**每项都是可开关的修改**：<br>顶部一行「**本把已改：…**」实时列出这把武器当前挂了哪些修改；<br>通用组：读武器 / **伤害增量（数值右侧小「改」按钮手动输入）** / 必暴 / 快挥 / 自动挥舞 / 恢复原厂；**枪械·弓才出现**「★ 无子弹发射」+「弹速拉满」；魔法才出现「魔力消耗清零」。<br>**开 = 写入并记住原值，关 = 把原值写回去**；**换武器、改参数、进这一页都会自动读取当前武器**，数据（伤害/暴击/使用/弹速/魔力/用弹）显示在**面板顶部的状态栏**上；修改本身不弹「成功」提示，只写日志。<br>**无子弹发射**：没弹药也能打 —— 开启时记住每种弹药的**基准数量**，打掉多少补回多少；期间捡到的弹药会累加进基准，**关闭时数量还原成基准**（= 原数量 + 期间捡到的）；背包完全没有对应弹药时会临时塞一份进空格子（关闭时移除）。<br>（2026-09-19 修：① 写物品数量原来误用了只能写 Player 的接口 → 改成 `setOn(IL.Item,…)`；② 旧版 `topUpAmmo()` 还在心跳里把弹药补到 9999，和基准追踪打架 → 已移除。实测 `60→打掉3→57→心跳回60→捡到10→70→关闭=70` ✓） |
| 事件 | **9 个全是开关**：血月 / 日食 / 下雨 / 沙尘暴 / 哥布林入侵 / 海盗入侵 / 火星暴乱 / 派对 / 灯笼夜；开着就**每帧复写**（血月天亮也不散、雨量拉满、入侵打完自动重开）；**下雨/沙尘暴跟随游戏真实状态**（游戏自然下雨 → 开关自动点亮并在状态栏提示；这种是「跟随」，雨会自然停、开关再自动关）；**你自己点开的才会一直维持**；**关掉会立刻停掉本轮**；⚠ 停止全部事件并复位开关 |
| 世界时间 | **滑动条**改时间（0–54000）+ 日出 / 正午 / 日落 / 午夜快捷键 + **锁定时间**（冻结昼夜）+ 设白天 / 夜晚 |
| **背包**（原「物品」页） | **背包操作页**：**每次进入这一页自动读取一次背包**（59 格：0–9 快捷栏 / 10–49 主背包 / 50–53 钱币格 / 54–57 弹药格 / 58 其它），网格**按类型分区并配色**（快捷栏蓝底 / 钱币金底 / 弹药绿底），每格显示 图标 + 名字 + 槽号 + ×数量。<br>**页面只留一个「刷新背包」按钮**；其他操作全部在**点格子时于该格子旁边弹出**：`放入/替换物品`（物品面板选完写进这一格，钱币格/弹药格会提示对应类型）、`改数量`（内置键盘，按 maxStack 封顶）、`复制到空格`、`删除该格`、`⚠ 清空整个背包`（点两次确认）、`关闭`（点弹窗外空白处也能关）。<br>停在页面时每秒自动刷新（脏检查，只更新变了的格子）。**原「添加物品」已并入这里**（点格子 → 放入/替换物品）。<br>操作弹窗为**两列紧凑布局**，**贴着你点的那个格子**（下面放不下会自动翻到格子上方），点弹窗外空白处关闭。<br>（2026-09-19 修：① 建格重复 → **建前先清空容器 + 进入即置位的「进行中」防重入标记**（真因：Frida 的 JS 在 `Java.registerClass` 这类长 Java 调用期间会被 Java 线程重入，轮询趁机再进一次建格，两套网格交错）；② 弹窗定位被固定预留夹到同一位置 + 竖排按钮太高 → 改贴格子 + 两列布局；③ 结构异常自愈：每次刷新校验容器子节点数，对不上就重建；④ 弹窗贴不住格子（差 ~160px）→ 真因是**高度按行数估算**（估 438px，实际 314px），改成**先 measure 再定位**，现在弹窗底边与格子顶边只差 6px；⑤ **点「放入/替换」没效果** → 真因是按钮回调在 `for` 循环里用 `var` 建闭包，**捕获了循环变量**，同一行按钮最后都执行该行最后一个动作（行 `[放入/替换｜关闭]` 里点前者实际执行了「关闭」）→ 改用 `forEach` 每元素独立作用域；⑥ 背包弹窗补上菜单标记，脚本重载时能被 `sweep()` 清掉，避免残留全屏透明层吞掉点击；⑦ **弹药格/钱币格点「放入」时物品面板自动只列对应物品**（2026-09-20 加）：从**弹药格**（54–57）打开只列**弹药**（80 件），从**钱币格**（50–53）打开只列**钱币**（71–74 四枚）；此时隐藏分类条，改显示「只看弹药/只看钱币（N 件）」+「显示全部物品」一键取消筛选。物品集合由 `物品库/out/terraria_items_all.csv` 的「弹药ID」列**离线生成 ID 区间表**（`BAG_FILTER`）内嵌进脚本，零运行时开销、不读文件；搜索词与筛选叠加生效（例：弹药筛选里搜「箭」＝25 件）） |
| 添加物品（旧入口） | **直接点「物品 …」那一行（图标）** 就弹出分类菜单：**20 个类别**（武器·近战/远程/魔法/召唤、护甲三件、饰品·翅膀、时装、染料、坐骑、弹药、工具、药水、材料、方块、任务物品…）→ 物品面板：**顶部横向分类**（全部 / 20 个类别，左右可滑）+ **搜索框（用系统输入法，按名字过滤）** + **图标虚拟列表**（每行 4 格，一路滑到底、不用翻页）→ 点选即选中（面板上「物品 …」那一行会**同时显示该物品的图标**）；数量走「**修改数量（手动输入）**」；「添加到背包」按该数量入包，**优先快捷栏**。<br>（原物品 ID 滑动条与 ±/× 按钮已按需求删除） |
| 物品图标 | 覆盖 **ID 0..6265 全部物品**（含国服新增：6147 K记鸡腿 / 6190 讯飞飞盘 / 6205 心动短剑 …）。图标不是截图拼的，是**从安装包里离线解出来的图集**：`物品ID → 图集矩形` 由 `item_<id>.png` 的 **CRC32** 当 key 在 `resources.assets` 的图集矩形表里二分查得（6085 件，见 `物品图标/README.md`）。运行时**先读游戏私有缓存**（`cache/dsha_atlas_N.png`），没有才由后台线程从容器里的 `127.0.0.1:8899` 拉一次并缓存；三条通道都拿不到时**自动退回纯文字列表**，功能不受影响。<br>**完整挖掘过程见第七节。** |
| 其它 | 打印内部状态到日志 |

分组可折叠；**按住标题栏可拖动，收起后按住小 chip 也能拖动**；标题栏 **▾ 收起**把面板缩成一小块 chip
（`≡ 修改器`，实测 `235×121 px`），轻点一下展开。**没有关闭按钮**：面板属于游戏进程，退出游戏它自然就消失了。

**反馈通道**：改了什么是写在面板顶部状态栏上的（本移植版 `Main.NewText` 抛异常用不了）。

**已知取舍 / 排障**：

| 现象 | 处理 |
|---|---|
| 日志里 `找不到 Activity（游戏没在前台？）` | 用 `/app/launch?pkg=com.xd.terraria` 把游戏调回前台再执行 |
| 面板建出来了但画面里看不到 | 少数机型 Unity 的 SurfaceView 被置顶 → 把脚本顶部 `CFG.host` 从 `'content'` 改成 `'panel'`（改用 `WindowManager` 子窗口，效果一样但拖动走窗口坐标） |
| 脚本重发后面板叠了两块 | 不会：新脚本会按 `contentDescription` 标记把上一块移除（`sweep()`） |
| 想临时把面板挪开 | 点标题栏 **▾** 收成小 chip（`≡ 修改器`）；面板随游戏进程存在，退出游戏即消失 |
| 面板一直开着影响操作 | 面板只在它自己那块区域内吃触摸，面板之外照常归游戏；也可以收起或拖到屏幕角落 |
| `unload` 后面板还留在屏幕上 | 正常：视图归游戏窗口所有，`unload` 只重置脚本状态。重发一次脚本即可（会先自动移除旧的）；程序化清理用 `globalThis.TERRARIA_SYS_MENU.close()` |
| 想改面板宽度/高度/初始位置 | 脚本顶部 `CFG.widthDp` / `CFG.heightRatio` / `CFG.startXDp` / `CFG.startYDp` |

**实测记录（2026-09-19 · OnePlus PKR110 / Android 16 / 2376×1080 / density 3.0）**：

- `android.R.id.content` 下有 4 个子视图，**`child[0]` 是 `com.unity3d.player.UnityPlayer`**（2376×1080 全屏），
  我们的面板是**最后一个子视图** → z 序最高，`isShown()=true`、`alpha=1`，确实盖在游戏画面上，触摸也先归面板。
- `Java.scheduleOnMainThread` 回调的 tid == 游戏 pid → 投递落在 **App 主线程（= Unity 主线程）**，直接调 il2cpp 安全。
- JsHook 的 `frida_unload` **不销毁 JS 运行时**（`globalThis` 上的标记卸载后仍读得到），
  所以残留在窗口里的面板监听器**不会变成死回调**；代价是 `unload` 也**不会**帮你移除面板。
- 面板 214dp 宽 + `heightRatio 0.52` ≈ 642×700 px（占屏高约 65%）。
- 两个必踩坑已修并在代码里注明：`var juse = Java.use` 会丢 `this`（报 `classFactory of undefined`）；
  `findViewById()` 的包装类型是 `android.view.View`，要 `Java.cast` 成 `ViewGroup` 才能 `getChildCount/getChildAt`。
- **收起 / 展开 / 拖动已自动验证通过**（打印「意图状态 + 视图实际状态」比对）：
  展开 `642×744`（lp 宽 642、状态栏与滚动区 `vis=0`）↔ 收起 `235×121`（lp 宽 `WRAP_CONTENT`、两者 `vis=8`）。
- **手势是注入合成 `MotionEvent` 验证的**：轻点 `▾` 两次 → 收起/展开正确翻转；
  收起态拖小 chip 位移 `150,210`、展开态拖标题栏位移 `-80,-120`，都与注入的位移**精确一致**。
- 按用户要求**去掉了关闭按钮**（`✕` 与底部「关闭面板」）：面板属于游戏进程，退出游戏即消失，不需要手动关；
  `UI.close()` 仍保留为程序化清理接口。
- **持续类效果的正确挂法**（本次最大发现）：本环境里 `Interceptor` 的 **`onLeave` 不回调**
  （同一指针、同一时刻挂 `onEnter` 计数正常，`onEnter+onLeave` 恒为 0）；而这些属性会被游戏每帧重算，
  必须在「重算之后」写。实测一帧内 Player 方法顺序：
  `Update → UpdateSocialShadow → UpdateImmunity → ResetEffects → UpdateBuffs → UpdatePet → UpdateEquips
  → UpdateArmorSets → UpdateLifeRegen → UpdateManaRegen → UpdateJumpHeight → ItemCheck → PlayerFrame`，
  所以挂在**最后一个 `PlayerFrame` 的 `onEnter`**（其 arg0 实测就是 Player 实例，与 `ResetEffects.this` 相同）。
- `Main.time` 是 **System.Double**（类型读写必须支持 Double，否则写坏内存）；本移植版**没有 `Player.PickAmmo`**，
  「无子弹发射」改用后台心跳把背包里 `ammo != 0` 的堆叠补满。
- 武器种类自适应：读 `Item.useAmmo>0`（枪械/弓）/ `magic|mana>0` / `summon` / `melee` / `pick|axe|hammer`。
  实测切到枪械 `wp-ranged` 显示、换回近战即隐藏。
- `onMain()` 若已在主线程再调 `Java.scheduleOnMainThread`，**任务会被丢掉** → 已加「已在主线程就直接执行」的快路径。
- JsHook 的 `unload` 不销毁 JS 运行时，**上一会话的 `setInterval` 仍在跑** → 新会话启动时 `clearInterval` 回收旧定时器。
- 加物品：找背包第一个 `Item.type==0` 的槽 → `Item.SetDefaults(id,false)`（**只有 2 参重载**）→ 写 `stack`。实测 4956（天顶剑）成功入包。
- **弹层机制（分类选物品 / 数字键盘）**：弹层是另一个 `addContentView` 浮层（后加的在更上层），自带标记所以重发脚本时会被 `sweep()` 一并清掉。
  ⚠️ 弹层的 `close()` 有和面板**一模一样**的坑：`root.getParent()` 返回 `ViewParent` 包装，调 `removeView` 报 `not a function` → 弹层关不掉会一直叠着；
  必须用记下来的 `content`（`ViewGroup` 包装）来移除。已修，实测视图数 1→2→1。
- **不弹系统输入法**：游戏窗口里 IME 行为不可靠，所以「伤害增量 / 添加数量」用**面板内置数字键盘**（0–9 / 清空 / ⌫ / 确定）输入，纯触摸、无副作用。
- **物品分类表是离线生成后嵌进脚本的**：把 6227 件物品的 `分类`+`子类` 压成一张 **6265 字符的编码表**（第 i 个字符 = ID(i+1) 的类别码），
  这样游戏进程既不用读文件、也不依赖 HTTP 服务。生成源：`物品库/out/terraria_items_all.csv`。
- 实测分类选物品全流程：类别页 20 项 → 武器·近战（206）→ 每页 40 件（铁阔剑(4)/铁短剑(6)/木剑(24)…）→ 点选后 `STATE.itemId=4`，弹层正常关闭。
- **折叠分组的嵌套坑（用户报的「折叠角色就把所有功能都折起来」）**：构建嵌套界面时，分组头和分组体必须加到**传入的 `parent`**，
  不能加到循环里表示「当前分组体」的 `cur` —— 后者在上一个 `head` 处理后已经指向「上一个分组的 body」，
  于是第二个分组起全被塞进第一个分组里，折叠第一个就等于折叠全部。
  自查方法：数**内层容器的直接子节点数**，应为「分组数 × 2」（本面板 6 组 → 12）。
- **飞行必须同时给 `wingsLogic`/`wings`**：实测玩家这两个字段都是 0 时，只写 `wingTime=wingTimeMax=200` **完全飞不起来**
  （游戏要 `wingsLogic != 0` 才走翅膀飞行逻辑）。现在写 `wingsLogic=1 / wings=1 / wingTime=200 / wingTimeMax=200`。
- **加物品要优先放快捷栏（0–9）**：放背包深处（10+）在游戏 HUD 上看不见，用户会认为「功能没实现」。
  自检输出 `{"ok":true,"slot":3,"hotbar":true}` 即是验证。
- **装备修改改成「可开关 + 有登记」**：每项修改记录其字段原值（`MODS[槽位] = {__type, modKey: {字段: 原值}}`），
  开=写入并记原值、关=写回原值；`type` 变了（换物品）自动丢弃登记。实测 原伤害 5 → 开=55 → 关=5。
  ⚠️ 自查方式：调试探针里 **`ViewGroup.getChildAt()` 返回的包装类型是 `View`**，没有 `getText()`，
  想按文字找控件必须 `Java.cast(v, Java.use('android.widget.TextView'))`，否则会「遍历到 0 个文字控件」而误判按钮不存在。
- 另修掉两个从 modmenu 版一路带过来的真 bug：
  - **武器那组按钮全是坏的**：`IL.getF/setF` 内部写死查 `Player` 类字段，而武器属性在 `Item` 上 → 读回来全是 `undefined`，
    实测点「读选中武器」报 `Error: missing argument`。已新增通用版 `getOn/setOn(类, 对象, 字段)`，物品一律走 `IL.Item`。
  - **程序化关闭路径曾报错**：`panel.getParent()` 拿到的是 `ViewParent` 包装，实测 `removeView` 报 `not a function`。
    已改为记下 `android.R.id.content` 的 `ViewGroup` 引用再 `removeView`（`ViewParent` 只作兜底）；
    该路径现在由 `globalThis.TERRARIA_SYS_MENU.close()` 使用。

## 四、JsHook modmenu 版菜单（旧方案）

**文件**：`游戏内菜单.js`。仅作备用与对照，新工作优先用 `系统菜单.js`。

注入环境里 JsHook 提供了一整套界面 API（`assets/jscore_bootstrap.js` 定义）：

| API | 说明 |
|---|---|
| `modmenu.create(title, options, run)` | **悬浮菜单**，返回 `{size,state,position,icon,edgeHiden,close,update}`；`run.onchange(res)` 回调 |
| `moddraw.create(run)` | 叠加绘制，句柄 `{line,rect,text,image,close}` |
| `canvas.create(run)` | `ondraw` 返回 Bitmap 的自绘层 |
| `view.*` / `dialog.input` | 视图查询 / 输入框 |
| `Il2Cpp` | 内置 **frida-il2cpp-bridge**（Unity 2021.3.26f1c1） |

**已查清**：
- 菜单选项是「**分组 + 条目**」结构（`mod.dex` 里有 `addItems` / `addCategory` / `getSearchGroups` / `getItemType` / `getItemClass` / `itemClassHash`），条目带 `type` 与 `class` 字段。
- 菜单**不在游戏进程里渲染**：由 JsHook 的 root 守护进程 `me.jsonet.jshook:root:daemon` 绘制（dex 里有 `me.jsonet.jshook.service.ModMenuCallback`，游戏侧通过 Binder 发指令）。
- 因此游戏进程里既找不到它的窗口（`WindowManagerGlobal` 根视图为 0），也删不掉它。
- 选项 schema 见 `modmenu研究.md`（`title`/`val`，滑块叫 `slider`）。

**铁律**：
1. **`create` 之后必须在同一次脚本会话里 `close()`** —— 跨会话遗留的菜单用 `closeAll()` 清不掉，会一直挂在屏幕上。
2. 测试新格式时，一律「创建 → 立刻关闭」，避免再积图标。

## 五、屏幕上残留的悬浮图标怎么清

> 只与 **modmenu 版**有关；`系统菜单.js` 不会产生这类残留。

`modmenu.closeAll()` 只作用于**当前脚本会话**，对之前遗留的无效。已确认无效的手段：
`closeAll()`（两次）、`imgui_clear`、游戏进程视图树摘除、`am force-stop me.jsonet.jshook`（只杀主进程，守护进程不受影响）、
`kill <pid>`（设备策略拦截）、JsHook 自己的 shell（`[安全拦截] 禁止杀死 daemon 进程`）。

**只能手动**（三选一）：
1. 点那个悬浮图标 → 看头部是否有 ×／关闭，或**长按拖动**（多数 frida 菜单拖到边缘/底部会出现删除区）；
2. 在 **JsHook 里关掉悬浮菜单 / 停止 root 守护进程**；
3. **重启手机**（最彻底）。

## 六、排障

| 现象 | 原因 / 处理 |
|---|---|
| `helper 返回无法解析` | JsHook 的 MCP 没开或 App 被杀：先 `python3 jshook.py ping` |
| `ping` 报 `Connection refused` | JsHook App 里的 **MCP 服务开关没打开**（设备上也没有 19820 监听端口）；去手机上打开，别反复重试 |
| `A script is already loaded` | `exec` 会自动先 unload；仍报就手动 `python3 jshook.py unload` |
| 脚本日志为空 | 游戏在后台被冻结 → 用 `/app/launch?pkg=com.xd.terraria` 调回前台再执行 |
| 悬浮菜单条目空白 | modmenu 版专有：`options` JSON 结构不对（见第四节） |
| 系统菜单 `Java 桥不可用` | 注入环境没带 Frida Java 桥，只能用 modmenu 版 |

---

## 七、物品图标是怎么挖出来的（完整过程）

菜单里「添加物品」的图标**不是截图、不是网上下的**，是从这个游戏的安装包里解出来的原生素材。
下面按真实经历记录：两轮失败 → 一个转折 → 三条关键结论 → 落地。

### 7.1 目标

「添加物品」的列表要**图标显示**，图标要**来自游戏自己的素材**并且**自动对应到名字**（6000+ 件，不能手工）。

### 7.2 第一轮：想从运行中的游戏里直接读（全部没成）

| 尝试 | 结果 |
|---|---|
| 读 `TextureAssets.Item[id]` 的 `Texture2D` 宽高 | **能读**（未加载也读得到），但只有尺寸，没有图集坐标 |
| 观察 `_batchTextureIndex` | 与物品 ID 连续（id 0→1400、1→1401、4→1404…）→ 一度以为「batch 序号 = 打包记录号」，**后来证明这条线索把人带偏了** |
| 读贴图的 `PackedEntry`（偏移 +96） | 只有**已加载**的贴图有值，且当时字段偏移对不上 |
| `Main.instance.LoadItem(id)` / `Asset.ActionUnityLoad()` 主动加载 | 贴图仍为 null，主动加载不生效 |
| `ConvertToABGR` / `ImageConversion.EncodeToPNG` 直接导像素 | 全 0 / 不可读（移动端压缩贴图） |
| `TextureAtlasDB.GetTexture(int, out db, out entry)`（3 种参数顺序） | 不抛异常但返回空 |
| 按 22 字节记录暴力搜索字段布局（用 51 个已知尺寸做约束） | 最高只命中 7/51 = 噪声级 |
| 货架式打包模拟（行/列/网格 × padding × 对齐 × 5 张图集全扫） | 最佳 0.398、有效样本 11，**没有命中的假设** |

### 7.3 第二轮：读实现（也没成）

| 尝试 | 结果 |
|---|---|
| 找 `Assembly-CSharp.dll` 读 IL | APK 里**没有**托管程序集，只有 `global-metadata.dat`(11.9MB)，IL 已被 IL2CPP 编译掉 |
| 把 `Item` 表 262KB 嵌进脚本、在游戏里构造 `byte[]` 调 `LoadData(byte[])` | 数组构造成功，但**一调就 `breakpoint triggered`** → 该方法的 methodPointer 很可能是**未编译的陷阱桩** |
| 遍历 Assembly-CSharp 全部类 / 读未初始化静态字段 | **Frida 侧 access violation，脚本静默死掉**，而且会把游戏主线程一起拖住（之后 JsHook 所有调用返回空，看起来像工具坏了） |

> ⚠️ 这一轮留下的纪律：**能离线做的事，绝不去游戏里循环探测**。要做运行时探测只做「定点单字段读取」。

### 7.4 转折：回到安装包里找数据

1. 先在资源里搜类名：`globalgamemanagers.assets` 里有 **`TextureAtlasDB` / `TextureAtlasEntry`** 字符串 → 这两个类确实存在。
2. 既然「图集是打包好的」（两张 2048² 图集就在包里），描述打包结果的**矩形表也一定在包里**。
3. 拿运行时读到的字典**前 5 个 key**拼成字节签名（`1F 78 05 80 8A 0F 06 80 …`），在 `resources.assets` 里搜 —— **命中两处**：
   - 偏移 **18755426**：`Item` 的 2048 版，**6230 条**
   - 偏移 **3042920**：`Item` 的 1024 版，6229 条（另一套打包坐标）

**表结构**（`int32 条数` 紧跟其后，**按 key 升序**，可直接二分）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `key` | int32 | 见 7.5 |
| `AtlasIndex` | int32 | 0 = `Item1`(2048²)，1 = `Item2`(2048²) |
| `TextureWidth` / `TextureHeight` | int16 ×2 | 图标实际像素 |
| `TextureOffsetX` / `TextureOffsetY` | int16 ×2 | 图集内偏移 |
| `TextureScale` | int16 | 实测恒为 1 |
| `TileDataOffset` | int32 | 实测恒为 −1 |

记录周期 **22 字节**。解析出来后与运行时的 26 条真值逐条对上（例：记录 0 = `30×28 @ (1488,1772)`、atlas=0，与 `PackedEntry` 完全一致）✔

### 7.5 key 是什么：**CRC32 的资源路径**

- key 的分布一眼就是哈希：6230 个值在 int32 上近似均匀，**最小值 ≈ 2³¹/6230**（均匀分布最小值该有的量级）。
- 用运行时的 `TextureAssets.Item[id].Value.PackedEntry.TextureId` 拿到 **26 组 (物品ID → key) 真值**。
- 拿真值做**字典攻击**：前缀（`Images/`、`Assets/`、`Terraria/`…）× 名字（`Item_N`/`ItemN`/`item_N`…）× 后缀（`.png`/`.xnb`/空）× 8 种哈希（乘 31、DJB2、FNV-1a、CRC32、Unity `StringToHash`、adler32…）。
- **命中：`key = int32(CRC32("item_<id>.png"))`，26/26 全中。**（注意是小写 `item_` + `.png`，一个字符都不能错；普通字符串哈希全都不是。）

从此**完全离线**：6085 件物品的矩形一次算完，再也不用碰游戏进程。

### 7.6 最后一个坑：图集是**上下翻转**存的

按 `(X, Y, X+W, Y+H)` 裁出来的图标是「上面一截对、下面错位」的规律性花屏 —— 非常像「坐标算错」，其实不是。
把 y 换成 **`2048 − Y − H`** 之后图标立刻正确（ID 4 铁阔剑、6 铁短剑、7 铁锤、17 蓝色手机…）。
**结论：图集 PNG 上下翻转存放**，正确矩形 = `(X, 2048−Y−H, X+W, 2048−Y)`。

### 7.7 落地进菜单

| 步骤 | 做法 |
|---|---|
| 矩形表内嵌 | 每件压成 **9 个字符**（图集页 1 + X 2 + Y 2 + 宽 2 + 高 2，字符表 = base64url 的 64 个字符）→ `ICON_TABLE`，6085 件 ≈ **55KB**，直接内嵌进 `系统菜单.js`，**运行时零依赖** |
| 图标进进程 | ① 游戏私有缓存 `cache/dsha_atlas_N.png`（**日常走这条，不需要任何服务**）→ ② 容器内 HTTP `127.0.0.1:8899`（缺缓存时拉一次并写入 ①）→ ③ 直接读 `/sdcard`（本机被分区存储挡住，留给别的机型） |
| 网络不能在主线程 | 弹层是在主线程建的，主线程 `openStream()` 会抛 `android.os.NetworkOnMainThreadException` → 下载统一放 `ICON.warm()`（Frida 脚本线程），主线程只做本地 `decodeFile` |
| Frida 数组坑 | `Java.array('byte', N)` 不支持「按长度建数组」（报 `expected an integer`）→ 改用 `InputStream.readAllBytes()` |
| 界面 | **虚拟列表**：每行 4 个格子（真实图标 + 中文名），8 行窗口循环复用（6000 件也只有 32 个格子 View），滑动浏览、不用翻页；面板上「物品 …」那一行是 `iconrow`，**点它就弹选择面板** |
| 退化保护 | 图集三条通道都拿不到时，列表**自动退回纯文字**，功能不受影响 |

### 7.8 游戏更新后怎么重跑

```bash
cd "/sdcard/Download/DSHA/泰拉瑞亚项目/物品图标"

# ① 安装包 → 矩形表 + 两张图集（复制到 /sdcard/Download/DSHA/terraria_icons/）
PYTHONPATH=/root/DshaWorks/pylibs python3 构建图标表.py

# ② 矩形表 → 系统菜单.js 的 ICON_TABLE（9 字符/件）
python3 注入图标表.py --write

# ③ 下发菜单
cd ../控制面板 && python3 jshook.py exec --file 系统菜单.js --wait 3
```

若游戏版本变了导致表偏移不同：`构建图标表.py` 顶部 `DB_OFFSET` 改一下即可（用运行时 `PackedEntry.TextureId`
重新做一次 CRC32 命中验证，确认新偏移）。

### 7.9 相关文件

| 文件 | 用途 |
|---|---|
| `../物品图标/构建图标表.py` | 解析安装包里的图集矩形表 → `物品矩形表.json/.txt`，并复制图集到英文路径 |
| `../物品图标/注入图标表.py` | 矩形表 → `系统菜单.js` 的 `ICON_TABLE`（`--write` 写回） |
| `../物品图标/图标HTTP服务.py` | 容器内静态服务（8899），**只在私有缓存还没建立时需要** |
| `../物品图标/物品矩形表.txt` | 6085 件物品的 `ID → 页/X/Y/宽/高`（人可读） |
| `../物品图标/图集/` | 解出来的 5 张图集（2048² ×2 正式用，1024² ×3 留档） |
| `../物品图标/校验_前48个.png` | 前 48 件裁剪校验图（肉眼确认图标正确） |
| `../物品图标/README.md` | 更细的技术记录（解包对齐坑、Texture2D 手工解析、历史弯路） |
| `../物品图标/extract_bundle.py` · `unity_tex.py` | 从 `data.unity3d` 解节点（含两个 16 字节对齐修正）、手工解析 Unity 2021 `Texture2D` |

### 7.10 一句话教训

> 数据**能离线解就别去运行时猜**：这次真正解决问题的三步是「去包里找序列化的表 → 认出 key 是 CRC32 → 发现图集上下翻转」，
> 而前面所有在游戏进程里猜内存布局的尝试，一共只换来几条**错误线索**和一次把游戏拖住的事故。

---

## 八、性能与稳定性（2026-09-19 修）

### 8.1 翻页卡顿 → 已改成虚拟列表（实测数字）

| 操作 | 优化前 | 优化后 |
|---|---|---|
| 列表**滚动跨一行** | 原来要翻页：重建 ~100 个 View + 24 次裁图 + 24 次 il2cpp 取名字 → **~300–500ms/页** | **只重填划出去的那一行**（4 个格子）→ 约 5–10ms，滑动跟手 |
| **首次进某个分类** | **~430–580ms** | 建 8 行窗口 + 填名 **~160ms** 一次性完成（之后滚动几乎零成本） |

做法：
1. **虚拟列表（手写）**：`body = [上占位][8 行窗口][下占位]`，占位高度按固定行高 `ROW_H` 计算 → 滚动条长度/范围和真实总高一致；
   监听滚动，**跨一行时把划出去的那行挪到另一端重填**（环形复用），跨多行才整窗重填；
   为什么不用 `ListView`/`RecyclerView`：这个 Frida 构建里 **`Java.registerClass` 的 `extends` 完全不生效**
   （实测动态类父类永远是 `java.lang.Object`，`BaseAdapter`/`ArrayAdapter` 都一样），做不了 Adapter 子类；
2. **物品名离线表**：名字原来是每次 `Lang.GetItemNameValue`（按名字查方法 + `runtime_invoke`，~10ms/次），
   改成内嵌 82KB 名表（`ITEM_NAMES`，由 `物品库/生成名称表.py` 生成），运行时零调用；
3. **两帧渲染**：首次进分类时先铺名字/占位返回、图标放到下一轮主线程消息里填；
4. **后台预裁**：滚动时顺手在后台线程把接下来几行的图标裁好（缓存 240 张）；
5. **图标单次裁剪**：`createBitmap(src,x,y,w,h,matrix,false)` 一次完成裁剪+放大。

### 8.2 ⚠️ 一次真实崩溃：动态类注册过多（已修，勿再犯）

**现象**：游戏突然被杀，tombstone 里是
```
signal 11 (SIGSEGV)  Cause: stack pointer is not in a rw map; likely due to stack overflow
art::ClassLoaderContext::EncodeContextInternal ↔ EncodeSharedLibAndParent   ← 反复递归 512 帧
```
**根因**：Frida 每次 `Java.registerClass` 都会新建一个 **DexClassLoader**，而 ART 生成「类加载器上下文」是**递归**的，
动态类注册太多 → 递归过深 → 栈溢出。当时有两个来源：
- 我新加的 `postMain()` **每次调用都注册一个新 Runnable**（翻页/建界面越多次数越多，无上限）；
- 原来每个按钮/开关/标签各注册一个监听器类（一次建界面约 75 个）。

**修法（已是现状）**：
- 监听器**每类只注册一个类**，用 `View.setTag(字符串)` 分发（点击/开关/滑块/拖动都是）；
- `postMain` 只注册**一个** `Runnable` + 队列；
- 吞触摸、拖动监听器共用一个实例；
- 结果：**每个脚本会话只有 6 个动态类**，重载多少次都只 +6（已压测：重载 2 次 + 连续翻页 20 次不崩）。

> 自查：`grep -c 'Java.registerClass' 系统菜单.js` 应只出现在 6 个工厂里；
> **任何出现在循环或每次回调里的 `registerClass` 都是定时炸弹。**

### 8.3 虚拟列表的两个坑（都已修）

1. **能一直往下滑 / 底部一片空白**：`first` 必须夹在 `[0, 总行数 − 窗口行数]`。
   否则滚到底时窗口会停在「全是空行」的位置 —— 现象就是「划到底还能继续滑，看到空白」。
   另外小分类（行数不足一窗）要把多余的行 `GONE` 掉，不然也会多出一屏空白。
2. **部分物品没有图标**：国服有 181 件**别名物品**（旧版/共用贴图，如 3665 受困宝箱用的是 id 48 的贴图），
   它们的贴图名不是 `item_<id>.png`，CRC32 对不上。已用运行时读 `PackedEntry.TextureId` 补出 **148 件**
   （脚本：`物品图标/补别名图标.py`，结果存 `物品矩形表_补充.json`，`注入图标表.py` 会自动合并）；
   剩下 **33 件**的贴图根本没进图集（独立贴图），菜单里仍是 `ID n` 占位。

### 8.4 游戏日志不稳时的调试通道

游戏切到后台时 JsHook 的日志常读不到。`物品图标/图标HTTP服务.py` 现在多了一个端点：
`GET http://127.0.0.1:8899/log?m=<文本>` → 追加写入容器里的 `/tmp/dsha_icon_log.txt`。
游戏侧转发要用「覆写 `console.log` → 攒批 → 由 Frida 线程 `setTimeout` 发出」，**不能在主线程发 HTTP**
（`NetworkOnMainThreadException`）。

---

## 八点五、给别人/别的 AI 复用的技能包

`/sdcard/Download/DSHA/skills/terraria-modding/`（同时装在 agent 预设
`/root/.dsh/.agent-presets/terraria/skills/terraria-modding/`，新会话可自动加载）：
`SKILL.md`（主技能：环境通道 / il2cpp 操作 / 每帧钩子 / 功能配方 / 菜单设计 / 图标流水线 / 抗更新）、
`参考/踩坑清单.md`（35 条实测坑：现象→真因→修法）、`参考/菜单实现细节.md`（可直接抄的代码模式）、
`脚本/`（jshook.py 与图标/名字表生成工具）、`成品/系统菜单.js`（现成菜单）、`数据/`（矩形表）。

---

## 九、游戏更新后还能不能用？

**结论：小版本更新基本可以直接用；下面这几处是「快照数据」，更新后要不要重跑看情况。**

### 9.1 不受更新影响的部分（占绝大多数）

- **所有功能逻辑**都靠**运行时按名字**找 il2cpp 的类/字段/方法（`Player.moveSpeed`、`Main.raining`、
  `Sandstorm.Happening`、`Item.stack`…），**不依赖固定地址或偏移** → 游戏更新照样能找到。
- **方法查找带 argc 兜底**：`findMethod(cls, 名字, [1,0,2])` 会依次试参数个数
  （`UpdateEquips` 就吃过「以为 0 参、实际 1 参」的亏），签名微调也能挂上；
  下发后日志会打印 `已挂 UpdateEquips 钩子（argc=1…）`、`PlayerFrame 命中（argc=0）`，一眼能看出有没有落空。
- **物品数量上限是运行时读的**（`TextureAssets.Item` 数组长度）→ 更新新增的物品**照样能列出来**，
  名字走运行时 `Lang.GetItemNameValue` 兜底。
- 图标进游戏的三条通道（私有缓存 → 本地 HTTP → /sdcard）与版本无关。

### 9.2 更新后可能需要重跑的快照数据

| 数据 | 更新后的表现 | 怎么补 |
|---|---|---|
| `ICON_TABLE`（图标矩形表，内嵌在 `系统菜单.js`） | **新增物品没有图标**（显示 `ID n` 占位，功能正常） | 重跑 `物品图标/构建图标表.py` →`注入图标表.py --write`；若表偏移变了，用 key 字节签名在 `resources.assets` 里重新搜（见 `物品图标/README.md` 7.4） |
| `ITEM_NAMES`（物品中文名表） | 新物品名字走运行时兜底（能用，略慢） | 重跑 `物品库/生成名称表.py --write` |
| `CAT_MAP`（物品分类表） | 新物品不落进分类 chips（「全部」+ 搜索仍能找到） | 重新导出物品库 CSV 后重跑分类生成脚本 |
| `物品矩形表_补充.json`（别名物品） | 新的别名物品没图标 | `物品图标/补别名图标.py gen` → `collect` → `parse` |
| 游戏私有缓存里的两张图集 | 清数据/重装后首次没有图标 | 起一次 `物品图标/图标HTTP服务.py`，菜单会自动拉取并重新缓存 |

### 9.3 极端情况

- **改包名 / 换 Activity**：`jshook.py` 的 `--package` 与脚本里的默认包名要同步改。
- **换了 Unity/IL2CPP 大版本**：脚本用的是运行时 il2cpp API，一般仍可用；但**离线解包脚本**
  （`extract_bundle.py` / `unity_tex.py`）要按新格式核对（UnityFS 对齐、Texture2D 布局）。
- **加了反调试/反注入**：JsHook 可能连不上（表现为 `ping` 不通、脚本下发无日志）→ 只能换注入方式，
  脚本本身不用改。
- **随时自检**：`python3 jshook.py exec --file 系统菜单.js --sub "selfTest: false||selfTest: true"`
  会跑一遍全量自检（属性/武器/事件/图标/布局）并写日志。
