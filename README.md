# 泰拉瑞亚（安卓）修改技能包 & 修改器菜单

> English: [README.en.md](README.en.md) · 本仓库所有结论都是**在真机上实测**出来的，不是通用攻略。
>
> **⬇️ 下载**：[最新发布包](https://github.com/abcd123rft/terraria-android-modding/releases/latest)
> （文档 + 菜单 + 工具的 zip，**不含游戏素材**）· 也可以直接浏览下面的目录。

给安卓版《泰拉瑞亚》（Unity + IL2CPP；实测于**国服** `com.xd.terraria` `1.4.56002`，Unity 2021.3.26f1c1，
Android 16）用的**可复用技能包 + 能直接跑的修改器菜单**。包含：按**名字**操作 il2cpp 改功能、
用 **Android 系统 UI** 做游戏内菜单（触摸不穿透）、从安装包**离线提取物品图标**。

- **验证于**：2026-09-19 · 国服 `1.4.56002`（versionCode 303538）· OnePlus PKR110 / Android 16
- **请先读 [skill/FRESHNESS.md](skill/FRESHNESS.md)**：包内所有数字都是某次快照，哪些会随游戏更新失效、
  失效后怎么重建，都写在里面。

## 目录

| 路径 | 内容 |
|---|---|
| [`skill/SKILL.md`](skill/SKILL.md) | 主技能（中文）：环境与通道、按名字操作 il2cpp、每帧效果的正确挂法、功能配方、菜单设计、图标流水线、抗更新 |
| [`skill/SKILL.en.md`](skill/SKILL.en.md) | 英文版（带 YAML frontmatter，可当 agent 技能加载） |
| [`skill/FRESHNESS.md`](skill/FRESHNESS.md) | 时效性台账：验证日期、目标版本、哪些常量会过期、怎么重建、三步自检 |
| [`skill/reference/pitfalls.md`](skill/reference/pitfalls.md) | **50 条实测坑**：现象 → 真因 → 修法（含把游戏打崩的栈溢出事故） |
| [`skill/reference/menu-implementation.md`](skill/reference/menu-implementation.md) | 可直接抄的代码模式：tag 分发、面板骨架、自适应高度、虚拟列表、图标裁剪、天气同步、无子弹 |
| [`menu/terraria-mod-menu.js`](menu/terraria-mod-menu.js) | ⭐ 现成修改器菜单（约 280KB）：6 个标签页、图标网格+搜索、9 个事件开关、武器改造、虚拟列表 |
| [`menu/MENU-MANUAL.zh-CN.md`](menu/MENU-MANUAL.zh-CN.md) | 菜单使用说明（功能清单 / 布局 / 性能 / 更新应对） |
| [`tools/`](tools) | `jshook.py`（注入客户端）· 图标/名字表生成 · 安装包解包 · Texture2D 解析 · 本地图标服务 |

## 方法要点

- **按名字找成员，绝不用固定地址**：`il2cpp_class_from_name` + 按名字查字段/方法，
  方法查找**带参数个数兜底**（游戏更新可能改 argc）。
- **每帧效果要挂对钩子**：`PlayerFrame` 是帧内最后一个 `Player` 方法，但 `moveSpeed`/`statDefense`
  每帧被 `ResetEffects()` 清零 → 这些必须在 **`Player.UpdateEquips`**（重置之后、移动之前）里写；
  本环境 `onLeave` 不触发。
- **用 Android 系统 UI 而不是 ImGui 覆盖层**：`Activity.addContentView` 把原生 View 挂进游戏窗口 →
  触摸不穿透、退出游戏即消失。
- **稳定性红线**：热路径里绝不 `Java.registerClass` —— 每个动态类都会新增 `DexClassLoader`，
  ART 编「类加载器上下文」是递归的，注册多了会**栈溢出把游戏打崩**（tombstone 特征见踩坑文档）。
  改成「每类监听器一个类 + `View.setTag` 分发」。
- **能离线就离线**：物品名、图集矩形、分类数据都在游戏外生成（图集矩形表明文存在 `resources.assets` 里，
  key = `CRC32("item_<id>.png")`；图集 PNG **上下翻转存放**，裁剪要 `(X, 2048−Y−H)`）。

## 快速开始

```bash
# ① 把菜单下发进正在运行的游戏（JsHook / Frida 宿主，MCP 在 127.0.0.1:19820）
cd menu
python3 ../tools/jshook.py exec --file terraria-mod-menu.js --wait 7

# ② 图标：菜单会把两张 2048² 图集拉进游戏私有缓存。
#    图集请用 tools/ 从**你自己的**游戏安装包里提取，放到
#    /sdcard/Download/DSHA/terraria_icons/atlas_0.png 与 atlas_1.png；
#    若游戏进程读不到 /sdcard，用本地服务供一次：
python3 ../tools/icon_http_server.py 8899

# ③ 每次下发后跑一遍全量自检
python3 ../tools/jshook.py exec --file terraria-mod-menu.js --sub "selfTest: false||selfTest: true" --wait 12
```

## 环境要求

- 安卓设备（arm64）+ 已安装游戏；**Frida 注入通道**（如 JsHook）可达 `127.0.0.1:19820`
  （key 默认 `/root/.dsh/jshook_key`，可用 `JSHOOK_KEY_FILE` 覆盖）。
- Python 3；离线解包另需 `lz4`、`Pillow`、`texture2ddecoder`。
- 菜单按国服包名写，其他版本用 `jshook.py --package` 指定。

## 更新记录（新的在上）

> 这一版加的「特殊仆从也可多只（实验）」会干扰仆从的形态/AI 分支选择，已按用户要求撤回，菜单行为回到 v1.2.7；相关发现保留在踩坑清单第 53 条。

**v1.2.8（已撤回 / withdrawn）**
- 「其它」页再加 **特殊仆从也可多只（实验）**：游戏除总数外还用**每类一个布尔字段**记住「已经有这种了」
  （`stardustMinion` 星尘龙 / `palworldFoxsparksMinion` 火绒狐 / `twinsMinion` / `spiderMinion` … 共 14 个，
  用 `il2cpp_class_get_fields` 枚举 Player 字段表挖出来的），这个开关把它们每帧清 false。
- 手册里写明两条**游戏本身的硬规则**（改不了）：①「唯一型」仆从（星尘之龙）永远只有一条，多的召唤槽让它**变长**而不是变多；
  ②哨兵/炮台**同一类型只能存在一个**（再召唤是把原来那个挪过去），`maxTurrets` 只放开「不同类型哨兵的总数」。
- 顺带记下测试方法上的坑：这个移植版**没法从 Frida 模拟"按键使用物品"**（写 `controlUseItem` 或 `Main.mouseLeft`
  都会被输入层每帧覆盖），所以"能不能召出第二只"只能人工点一下验证。

**v1.2.7**
- 「其它」页新增**解除召唤数量限制**：把**仆从**（`maxMinions`）与**哨兵/炮台**（`maxTurrets`）上限一起抬到 99，
  装备召唤槽（`slotsMinions`）同步，另有「读取当前召唤上限」按钮回显实际数值。
  实测踩到的点：这三个字段**游戏每帧按装备重算**（一次性写 400ms 内就被改回 1），必须每帧写；
  而且 `Interceptor.onEnter` 跑在函数体之前，所以要挂在两个每帧钩子里。
  验证方式也记进了踩坑清单：另挂 `Player.ItemCheck` 探针，在它 onEnter 里读 —— 实测读到 **99**（游戏检查召唤数量时看到的就是上限值）。

**v1.2.6**
- 修复**背包页只剩分区标题、格子全没了**：上一版加的「预热」在标题界面（还没有活跃角色，槽位读到 0）就建了网格，
  只建出 5 个标题 + 16 个空行却把 `built` 置了位，而子节点数正好等于期望值 → 自愈也发现不了，进世界后永远空白。
  现在：建格前必须 `bagSlots() > 0`（否则直接返回且不置位）；自愈条件加「一个格子都没有但槽位存在 → 重建」；
  预热没成功时轮询会在**首次出现角色**时补建（正好落在读盘时，卡顿被盖住）。

**v1.2.5**
- 新增**「路径与配置」章节**（中文手册第十节 + SKILL.md 第 11 节 + 本 README）：换目录/换设备时
  要改哪些东西一目了然 —— 游戏进程内只有 2 个常量（图集本地回退目录 `DIR`、图集 HTTP 地址 `HTTP`），
  容器侧脚本优先用环境变量（`ICON_DIR`/`ICON_LOG`/`JSHOOK_URL`/`JSHOOK_KEY_FILE`/`--package`/`TASSETS`/`ICON_DST`），
  剩下 5 个脚本各只有一行硬编码路径（注释里写了它期望的目录关系），外加「改完四步自检」的命令。
  另外说明：游戏私有缓存路径由脚本 `getCacheDir()` 现算，**换设备/换包名都不用改**。

**v1.2.4**
- **图标素材修正**：从 `resources.assets` 导出图集时漏了两步 —— Unity 纹理**自下而上**存（要逐行翻转）、
  字节序是 **BGRA**（要换 R/B）。表现是**所有物品图标倒立、金币发蓝**。旧做法（把矩形 y 换成 `图高−Y−H`）
  只把图块**位置**找对了、没修内容，而当时验证用的是铁阔剑/铁锤这类**上下近似对称**的图标，所以一直没暴露。
  现在用 `tools/fix_atlas_orientation.py` 直接修素材，脚本里裁剪回到朴素 `(X, Y, X+W, Y+H)`。
  验证图标方向请用**药水瓶**（瓶口朝上）或**金币**（金色），别用剑/锤。
- 换图集后记得刷游戏侧缓存：本地起服务 → 游戏里 `TERRARIA_SYS_MENU.icon.warm(true)` → 重载脚本。

**v1.2.3**
- **性能优化**（均为实测）：物品面板再次打开 133ms → **1.6ms**、背包页再次进入 53ms → **9ms**、
  背包刷新 1.24ms → **0.50ms**、数字键盘 26.7ms → **6.8ms**、单次字段写入 4.40µs → **1.70µs**。
  两件事贡献最大：① **字段按缓存偏移直读直写**（`il2cpp_field_get_offset` + 直接读写内存，
  首次用官方 API 对拍、不一致自动退回慢路径）；② **Android 视图只建一次、复用**（一次 Java 调用实测
  0.13–0.28ms，重建 120 个视图就是 100ms+）。另外全部开关关闭时两个每帧钩子直接短路，空闲开销≈0。

**v1.2.2**
- 背包页：从**弹药格**打开物品面板只列弹药、从**钱币格**只列钱币（ID 集合离线压成区间串内嵌，
  与分类/搜索叠加生效）。

## 路径配置（换目录/换设备必读）

- **游戏进程内**只有 2 个常量要改：`menu/terraria-mod-menu.js` 里 `ICON` 的 `var DIR`（图集本地回退目录）
  与 `var HTTP`（图集 HTTP 服务地址，端口要和 `tools/icon_http_server.py` 一致）。
  图集**首选**来源是游戏私有缓存，路径由脚本 `getCacheDir()` 现算，不用改。
- **容器侧脚本**优先用环境变量：`ICON_DIR`、`ICON_LOG`、`JSHOOK_URL`、`JSHOOK_KEY_FILE`、`--package`、
  `TASSETS`、`ICON_DST`。
- **写死路径的 5 个脚本**（`inject_icon_table.py`、`gen_name_table.py`、`fix_alias_icons.py`、
  `extract_bundle.py`、`publish_to_github.py`）各只有一行，注释里写了期望的目录关系。
- 改完自检：`curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8899/atlas_0.png` → 下发脚本 →
  日志出现「图标：图集 0 就绪 …（来源 私有缓存/HTTP）」。

**完整清单**（每个常量、每个脚本改哪一行、目录结构要求、四步自检）见 `menu/MENU-MANUAL.zh-CN.md` 第十节。

## 版权与合规（重要）

- **本仓库不含任何游戏素材**：两张图集、物品名/矩形表等提取物都不入库；脚本面向**你自己合法拥有的游戏副本**运行
  （这也是 mod 工具社区的通行做法）。
- `menu/terraria-mod-menu.js` 内嵌了**为互操作而必需的派生数据**（物品 id/名称、图集矩形），开箱即用；
  你也可以用 `tools/` 在本地重新生成这些表后自行构建（见 `skill/SKILL.md` §7）。
- 这是**单机向的内存修改器**：请只在自己的世界里用，**不要用于多人游戏**、不要再分发游戏素材，
  并遵守游戏服务条款与当地法律。
- 仓库代码采用 MIT 许可（见 [LICENSE](LICENSE)）；*泰拉瑞亚* 及素材版权归 Re-Logic / 相应发行商所有，
  本项目非官方、与其无关联。
