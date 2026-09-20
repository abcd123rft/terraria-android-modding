# 踩坑清单（全部是本机实测踩过的）

> **时效性**：以下均为 **2026-09-19** 在国服 `1.4.56002`（Unity 2021.3.26f1c1 / IL2CPP，Android 16）上实测；
> Frida/JsHook 行为（如 `onLeave` 不触发、`extends` 不生效）可能随注入器版本变化。详见 `../版本与时效.md`。

> 每条格式：**现象 → 真因 → 修法**。带 ⚠️ 的是会造成严重后果（改不动 / 卡死 / 把游戏搞崩）的。

## 一、Frida / Java 桥

| # | 现象 | 真因 | 修法 |
|---|---|---|---|
| 1 | `TypeError: cannot read property 'classFactory' of undefined` | `var juse = Java.use` 把方法摘出来，丢了 `this` | 包一层 `function juse(n){ return Java.use(n); }` |
| 2 | `findViewById()` 返回的对象没有 ViewGroup 方法 | 返回的是声明类型 `android.view.View` 的包装 | `Java.cast(v, Java.use('android.view.ViewGroup'))` |
| 3 | 面板/弹层关不掉：`removeView is not a function` | `view.getParent()` 返回 **`ViewParent` 包装**，没有 removeView | 自己在建视图时记下父容器（content FrameLayout），用它 removeView |
| 4 | 日志里调 `view.getParent().getHeight()` 报 `not a function` | 同上（ViewParent 没有 getHeight） | 量高度直接量那个 View 本身 |
| 5 | ⚠️ `Java.array('byte', 65536)` 报 `Error: expected an integer` | Frida 的 `Java.array(type, elements)` 不接受「按长度建数组」 | 用 Java 9+ 的 `InputStream.readAllBytes()`，或 `Java.array('byte', [..])` 传数组 |
| 6 | ⚠️ `Java.registerClass` 的 **`extends` 完全不生效** | 实测动态类父类永远是 `java.lang.Object`（`BaseAdapter`/`ArrayAdapter` 一样）；`Java.cast`、反射 `Method.invoke` 都救不了（ART 报 `got com.dsha...Adapter`） | 不要给 Android 类做子类；只 `implements` 接口（且要实现该接口**全部**方法，新 API 会加方法如 `Adapter.getAutofillOptions`） |
| 7 | ⚠️ 游戏突然被杀，tombstone：`ClassLoaderContext::EncodeContextInternal ↔ EncodeSharedLibAndParent` 递归 512 帧 + `stack overflow` | 每次 `Java.registerClass` 新增一个 `DexClassLoader`，ART 编类加载器上下文是递归的，注册太多爆栈 | **每类监听器只注册一个类** + `View.setTag` 分发；`postMain` 只注册一个 `Runnable` + 队列；吞触摸/拖动监听器单例。自查 `grep -c Java.registerClass`（本脚本只剩 6~7 处） |
| 8 | `Interceptor.onLeave` 不触发（`onEnter+onLeave` 计数恒 0） | 本环境实测不支持 onLeave | 只用 `onEnter`；需要「方法跑完再写」就换挂点（见 §4.1 的方法顺序） |
| 9 | `Java.scheduleOnMainThread` 投递的任务被丢掉 | **在主线程里再调它**会丢任务 | `onMain` 必须带「已在主线程就直接执行」快路径（`Process.getCurrentThreadId() === Process.id`）；要真正延后一帧用 `Handler.post` |
| 10 | View 操作报 `CalledFromWrongThreadException` | View 只能在主线程碰 | 全部 UI 操作走 `onMain`/`postMain`；滑块/开关的程序化赋值加 `suppress` 标记避免触发回调 |
| 11 | 网络请求报 `NetworkOnMainThreadException` | 弹层/列表是在主线程构建的，主线程不能做网络 | 下载放 `setTimeout`（Frida 脚本线程）里做，做成启动预热 |

## 二、运行时读写（il2cpp）

| # | 现象 | 真因 | 修法 |
|---|---|---|---|
| 12 | ⚠️ 写物品字段没反应、日志出现 `无字段 xxx` | 用了**只写 Player** 的 `setF(obj, name, v)` 去写 Item | 写物品字段必须 `setOn(IL.Item, item, name, v)`；写完**回读校验** |
| 13 | ⚠️ 某功能「没生效」但也没报错 | `class_get_method_from_name(cls, name, argc)` 的 **argc 写死了**，实际签名不同（例：`UpdateEquips` 是 1 参不是 0 参） | 用 `findMethod(cls, name, [1,0,2])` 试多个候选，并在挂上后打日志 |
| 14 | 移速/防御类修改无效 | `moveSpeed/maxRunSpeed/accRunSpeed/statDefense` 每帧被 `ResetEffects()` 清零，而 `PlayerFrame` 是帧内最后一个方法 | 另挂 **`Player.UpdateEquips`**（ResetEffects 之后、移动之前）写这些字段 |
| 15 | 飞行（无翅膀）无效 | 只写了 `wingTime`，而 `wingsLogic/wings` 是 0 → 游戏不走翅膀逻辑 | 同时写 `wingsLogic=1`、`wings=1`、`wingTime(Max)=200` |
| 16 | 血月/日食设了又变 false | 游戏**每帧**按昼夜清掉 | 放进**每帧钩子**复写（50ms 心跳太慢，只在 1/20 帧有效） |
| 17 | 下雨/沙尘暴方法调了没反应 | `Main.StartRain/3`、`Sandstorm.StartSandstorm/0` 有前置条件 | **直接写字段**：`Main.raining/rainTime/maxRaining`、`Sandstorm.Happening/TimeLeft/Severity/IntendedSeverity` |
| 18 | 伪造沙尘暴测试「同步不生效」 | 只写 `Happening=true`，被 `Sandstorm.UpdateTime()` 当帧取消 | 测试时**连 `TimeLeft` 一起写** |
| 19 | ⚠️ 遍历类/读未初始化静态字段/对上千物品循环读 `Asset<T>.Value` → Frida 静默死掉、游戏主线程被拖住（之后所有 `exec`/`log` 都像坏了） | 触发 access violation / 长时间占用 | **只做定点读取**；能离线做的事绝不去游戏里循环；用 `/proc/<pid>/task/<tid>/stack` 判断是不是真死锁（`epoll_wait` = 还活着） |
| 20 | 大脚本下发失败 | 单行 34 万字符会挂 | 拆成多段字符串拼接（300KB 级脚本实测可以） |
| 21 | 物品名显示卡顿（翻页 300~500ms） | 每个名字都调 `Lang.GetItemNameValue`（按名字查方法 + `runtime_invoke`，~10ms/次） | 离线生成名表内嵌；方法指针也缓存起来 |
| 22 | 手持武器检测不到更换 | `Player` 上**没有 `selectedItem`** 字段 | 用 `Player.lastHotbarItem` + `inventory` 数组 |

## 三、菜单 UI

| # | 现象 | 真因 | 修法 |
|---|---|---|---|
| 23 | 折叠一个分组，别的分组一起没了 | 建节点时把子节点加到了 `cur`（上一个分组的 body） | 遇到 `head` 要 `parent.addView(head); parent.addView(body);`，`cur` 只指向当前 body |
| 24 | 反复打开弹层会叠起来 / 顶部出现半行残影 | 新弹层没有关掉旧的 | 维护 `OVL[]`，新弹层打开前把旧的都关掉；面板 close 时一起清 |
| 25 | 数字键盘/列表底部按钮被挡住 | 浮层滚动区高度写死（`listPx`）比内容矮 | 加 `fit()`：`measure()` 后取 `min(内容高, 屏高 − 浮层Y − 余量)` |
| 26 | 虚拟列表「划到底还能一直往下滑、底部一片空白」 | `first` 没夹住，窗口停在全空行位置 | `first = clamp(first, 0, total − 窗口行数)`；小分类把多余行 `GONE` |
| 27 | 换武器/改参数「没有读取武器数据」 | 读取一直在跑，但结果只写了日志（`UI.say` 被换成 `log` 后无显示） | 状态栏（面板顶部那条）显示；**自动读取要看得见才算生效** |
| 28 | 开关状态和实际不一致 | 同步只比内部 `STATE`：某次同步时面板还没挂载 → `setSwitch` 直接返回，`STATE` 却已改成和游戏一致 → **永远不再补 UI** | 同步时**也跟开关真实勾选状态比一次**，不一致就补 |
| 29 | 自动同步点亮的天气开关把雨「锁死」 | 跟随游戏状态的开关也走了「每帧复写」 | 加 `auto` 标记：跟随=不维持（自然停→开关自动灭），用户自己点开=维持；**修 UI 时不要动这个标记** |

## 四、通道与设备

| # | 现象 | 真因 | 修法 |
|---|---|---|---|
| 30 | `frida_read_log` 返回空 | **游戏切到后台**就没了（或日志被下一次 exec 重置） | 先 `/app/launch?pkg=…` 调回前台；日志**跟 exec 一起读** |
| 31 | 游戏进程读不到 `/sdcard`（`canRead()=false`） | targetSdk=30 + Android 13+ 分区存储；`requestLegacyExternalStorage` 对 targetSdk≥30 无效 | 走游戏**私有缓存**（游戏自己写）+ 容器内 HTTP 回退 |
| 32 | 容器里 `ls /data/data/<pkg>` 读不到 | 该路径在容器命名空间下不可见 | 用游戏进程自己列（Frida 里 `File.listFiles()`），或 `/data/user/0/...` |
| 33 | 截屏被拦 | `screencap` 属未列入白名单的设备命令（返回 `POLICY_BLOCKED`） | 用 `/app/ui/screenshot`（需无障碍服务）或让用户自己截图 |
| 34 | 探针脚本里 `window.__x` 不生效 | Frida 脚本环境没有 `window` | 用 `globalThis.__x` |
| 35 | ⚠️ 改物品数量「写进去了但没生效」，日志出现 `无字段 stack` | 用了**只写 Player** 的 `setF(obj,name,v)` 写 Item 字段（内部固定按 `Player` 类查名字） | 写物品字段用 `setOn(IL.Item, item, name, v)`；写完**回读校验** |
| 36 | 关闭「无子弹发射」后弹药数量不还原 | 旧版心跳里还挂着 `IL.topUpAmmo()`（把每种弹药补到最大堆叠 9999），和新的「基准数量追踪」打架 | 移除旧逻辑；基准追踪：开启记基准、打掉补回、捡到抬基准、关闭写回基准 |
| 37 | 读背包格读到**大负数** `type`（垃圾指针） | 槽位写死 60，而本移植版 `Player.inventory` 只有 **59** 格（0–58） | 运行时读数组长度 `arr.add(0x18).readS32()` 再夹住循环 |
| 38 | 模块级函数调用 UI 内部的辅助函数报 `ReferenceError: 'bagSlots' is not defined` | 辅助函数定义在 UI 模块（IIFE）里，模块级作用域看不到 | 统一走 `UI.xxx()`（连踩三处）；调试入口 `TERRARIA_SYS_MENU.bag.*` |
| 39 | 天气开关「跟随游戏状态」后雨再也不停 | 自动同步点亮的开关也走了「每帧复写」= 无限维持 | 加 `auto` 标记：跟随=不维持（自然停→开关自动灭），用户自己点开才维持；**修 UI 时不要动这个标记** |
| 40 | 测试脚本用 `getChildAt()` 遍历视图树，取不到文字（`getText()` 静默失败） | `ViewGroup.getChildAt` 的**声明返回类型是 `android.view.View`**，Frida 只暴露该类型的方法；`getParent()` 同理返回 `ViewParent`（连 `getVisibility()` 都没有） | 每次取到子节点先 `Java.cast(c, Java.use('android.widget.TextView'))` / `Java.cast(p, ViewGroup)` 再用；**别用 try/catch 吞掉**，否则会误判成「按钮不存在」 |
| 41 | 在 Frida `setTimeout` 回调里直接 `M.bag.tap()` / 点按钮 → `CalledFromWrongThreadException: Expected: main Calling: Thread-4` | Frida 的定时器跑在自己的线程，Android 视图只能在**主线程**动；而且此时坐标全是错的（`格子@241,3603`） | 定时器只负责**排期**：`setTimeout(function(){ M.post(fn) }, ms)`，所有视图操作都放进 `M.post`（内部走主线程 Handler） |
| 42 | 物品面板要给「弹药格」只列弹药，运行时逐 ID 问游戏太慢 | —— | 从离线物品表按「弹药ID > 0」生成 ID **区间串**（80 件压成 46 段，约 250 字符）内嵌脚本，运行时按区间判成员：零文件读取、零 il2cpp 调用；钱币就是 71–74 |
| 43 | 「脚本卡」以为是每帧钩子的锅，其实钩子全开也只占每秒 ~2.7ms | Frida 里 **一次 Java 调用实测 0.13–0.28ms**：重建 120 个 View = 100ms+。`setText`/`new Button`/`setBackground`/`isChecked` 才是真瓶颈 | 界面**只建一次**（弹层改常驻：关闭只 `setVisibility(GONE)`，下次 `show()` 复用）；列表窗口/分类 chips/标签页只在**状态真变了**时才碰 View；先用 `cfg.prof` 分段计时定位，别凭感觉优化 |
| 44 | 每个字段都要 `il2cpp_field_get_value/set_value`（2–4µs），钩子每帧写十几个、背包每秒扫 59 格 | IL2CPP 实例字段就是「对象指针 + `FieldInfo.offset`」 | `il2cpp_field_get_offset` 取偏移缓存住，之后 `p.add(off).writeFloat(v)` 直读直写（快 2–3 倍且零 il2cpp 调用，慢路径计数应恒为 0）。⚠ **读取用 `ck in cache` 判负缓存**，别用 `if (cache[ck])`——存进去的 null/false 会被判假，等于没缓存 |
| 45 | 直读的偏移「理论上对」但不敢用在正式脚本里 | 布局假设一旦不成立就是**静默写错内存** | 每个字段**第一次**直读时同时用官方 API 读一遍**对拍**，不一致就永久退回慢路径 + 写日志（`字段直读校验不一致：xxx`）。自校验让优化可回退、可观测 |
| 46 | UI 去重缓存（「文本没变就别 setText」）在**面板关闭再打开后**把新 View 判成「已设置」→ 状态栏/标签空白 | 去重标记记在模块级 map（按 id），而 View 是每次挂载新建的 | 标记记在 **View 自己身上**（`v.__txt`/`v.__vis`），View 一换标记自然失效；实测 Frida 的 Java 包装对象**可以加 JS 属性**，也可以当 `Map` 的键 |
| 47 | 大件 UI 首次构建卡 150–300ms，用户点开时要干等 | —— | **后台预热**（`cfg.prewarm`）：挂载后 `UI.post()` 里先建好再隐藏（同一轮 JS 内 show+hide，不会闪），用户点开时 0 等待；代价是启动后多两次主线程小卡（分段投递，别一次全建） |
| 48 | 心跳里每 50ms 无条件 `isChecked()` 查真实勾选状态（跨线程 JNI） | 为了修「STATE 与开关显示不一致」只能每轮都查 | 平时只比**游戏值 vs STATE**；面板（重新）挂载后强制完整核对一轮，另外每 40 个心跳（2s）兜底核对一次 → 省掉 40 倍调用，漂了也能 2 秒内自愈 |
| 49 | 物品图标**倒立**（药水瓶口朝下），而且金币是**蓝色**的 | 从 `resources.assets` 导图集时漏了两步：Unity 纹理**自下而上**存（PNG 要逐行翻转）、字节序是 **BGRA**（要换 R/B）。旧文档只把矩形 y 换成 `图高-Y-H`，那只修对了**位置**、没修**内容** | 修素材本身（`物品图标/修正图集.py`：翻转 + 换通道），脚本里裁剪回到朴素 `(X, Y, X+W, Y+H)`；验证别再用剑/锤这种上下近似对称的图标，用**药水瓶/金币**这种一眼能看出的 |
| 50 | 换了图集文件，游戏里还是旧图标 | 脚本优先读**游戏私有缓存** `cache/dsha_atlas_N.png`，`warm()` 见到文件已存在就直接跳过 | 起 `图标HTTP服务.py` → 游戏里 `TERRARIA_SYS_MENU.icon.warm(true)` 强制重下 → **重载脚本**（内存里已解码的 `pages[]` 也要换掉）。核对办法：Frida 里用 `MessageDigest` 算缓存文件 md5 与本地文件比对 |
| 51 | 背包页**只剩 5 个分区标题、一个格子都没有**（日志：`建格完成（… 格子 0，host子节点 21）`） | 预热在**标题界面**就跑：那时没有活跃角色，`bagSlots()` 返回 0 → 循环里 `slot >= N` 恒真，只建出「5 标题 + 16 空行」，格子一个不建；但 `BAG.built` 照样置位，而子节点数(21)又正好等于期望值 → 自愈比对也发现不了 | ① 建格前先确认 `bagSlots() > 0`，否则**直接返回且不置 built**；② 自愈条件加一条「`tiles.length === 0 && bagSlots() > 0` → 重建」；③ 预热没成功时，350ms 轮询里**等出现角色后补建一次**（正好落在读盘/加载时，卡顿被盖住）。教训：**预热这种「偏移卡顿」的优化必须先确认依赖的运行时状态已就绪**，否则会把「暂时不可用」固化成永久状态 |
| 52 | 想「解除召唤数量限制」，但一次性写 `maxMinions`/`maxTurrets` 400ms 内就自己变回 1 | 这两个字段以及 `slotsMinions` **游戏每帧按装备重算**（UpdateEquips 里从装备累计出来再赋值） | ① **必须每帧写**（挂在每帧钩子里的 `applyToPlayer` 才会生效）；② 生效窗口是「UpdateEquips 之后 ~ ItemCheck 之前」，而 `Interceptor.onEnter` 是在函数体**之前**跑的 —— 所以要在 `UpdateEquips` 和帧末 `PlayerFrame` 两处都写，实测在 `Player.ItemCheck` 的 onEnter 时刻能读到我们的值（99）；③ 自检办法：另挂一个 `ItemCheck` 探针，在它 onEnter 里读一遍字段，别只在帧间读（帧间读到的只是我们最后一次写的值，会误判成"已经生效"） |
| 53 | 想「多召同一类特殊仆从」：`maxMinions` 已抬到 99，游戏还是只让有一只（星尘之龙、火绒狐…） | 除了总数，游戏还用**每类一个布尔字段**记住「已经有这种了」：`stardustMinion`/`palworldFoxsparksMinion`/`twinsMinion`/`spiderMinion`/`hornetMinion`/`impMinion`/`pirateMinion`/`sharknadoMinion`/`UFOMinion`/`DeadlySphereMinion`/`flinxMinion`/`abigailMinion`/`deadCellsMushroomBoiMinion`/`palworldCattivaMinion`（用 `il2cpp_class_get_fields` 枚举 Player 字段表挖出来的）；另外**哨兵同类只能有一个**是硬编码规则，`maxTurrets` 只管总数不管同类 | ① 试过把这些字段每帧写 false 来放开（v1.2.8 短暂上线过一版），但会干扰仆从的形态/AI 分支选择，**已按用户要求撤回**；要做的话务必单独开关、可随时关；② 哨兵同类复制改不了，只能靠不同种类；③ **自动化测试的坑**：这个移植版没法从 Frida 模拟"按键使用物品"——写 `Player.controlUseItem` 或 `Main.mouseLeft` 都会被输入层每帧覆盖，所以"能不能召出第二只"只能让用户手点验证 |
