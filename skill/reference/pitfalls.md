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
