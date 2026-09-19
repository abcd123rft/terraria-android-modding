# 菜单实现细节（可直接抄的代码模式）

> **时效性**：以下均为 **2026-09-19** 在国服 `1.4.56002`（Unity 2021.3.26f1c1 / IL2CPP，Android 16）上实测；
> Frida/JsHook 行为（如 `onLeave` 不触发、`extends` 不生效）可能随注入器版本变化。详见 `../版本与时效.md`。

> 都是 `成品/系统菜单.js` 里跑通过的写法。行号会变，按函数名搜。

## 1. 每类监听器只注册一个类 + View tag 分发（防类加载器爆炸）

```js
// 模块级：整场只创建这些类，且都是惰性创建一次
var MAIN_H = null, POST_RUN = null, POST_Q = [];
function postMain(fn) {                       // 真正的「下一轮主线程」（Handler.post，主线程调用也能延后）
  if (!fn) return;
  POST_Q.push(fn);
  if (!MAIN_H) MAIN_H = Java.use('android.os.Handler').$new(Java.use('android.os.Looper').getMainLooper());
  if (!POST_RUN) {
    POST_RUN = Java.registerClass({ name: uniq('Post'), implements: [Java.use('java.lang.Runnable')],
      methods: { run: function () {
        var q = POST_Q; POST_Q = [];
        for (var i = 0; i < q.length; i++) { try { q[i](); } catch (e) {} }
      } } }).$new();
  }
  MAIN_H.post(POST_RUN);
}

// 面板里：一个 CLICKER 管所有按钮
var HANDLERS = {}, HSEQ = 0, CLICKER = null;
function bindClick(v, target) {               // target = 动作 id（走 dispatch）或 JS 函数
  var name;
  if (typeof target === 'function') { name = 'h' + (++HSEQ); HANDLERS[name] = target; }
  else name = String(target);
  if (!CLICKER) {
    CLICKER = Java.registerClass({ name: uniq('Clk'), implements: [ClickI],
      methods: { onClick: function (view) {
        var t = ''; try { t = String(view.getTag().toString()); } catch (e) {}
        if (!t) return;
        if (HANDLERS[t]) { HANDLERS[t](view); return; }
        dispatch(t);
      } } }).$new();
  }
  v.setTag(jStr(name));
  v.setOnClickListener(CLICKER);
  S.views[name] = v;                          // 便于自检/调试 performClick
}
// 同理：bindCheck（开关）、bindSeek（滑块，min 记在 SEEK_MIN[tag]）、bindDrag（拖动，状态记在 DRAGS[tag]）
```

## 2. 系统 UI 面板骨架

```js
var panel = LinearLayout.$new(act);
panel.setOrientation(1);
panel.setContentDescription(jStr(CFG.marker));      // ← 重新下发时靠它 sweep 掉旧面板
panel.setBackground(bg); panel.setPadding(...);
panel.addView(bar);        // [标题(可拖动)][▾收起]
panel.addView(status);     // 状态栏：唯一的用户反馈通道（本移植版 Main.NewText 抛异常）
panel.addView(tabBar);     // 顶部标签页
panel.addView(scroll);     // 滚动区（里面是各 page 容器）
act.addContentView(panel, new FrameLayout.LayoutParams(dp(250), WRAP));
```

- **拖动 + 轻点**：`OnTouchListener` 里按 `getAction()` 区分（0 记录按下点、2 超阈值算拖动、1/3 未移动则当轻点）。
- **收起 chip**：把 status/scroll/tabBar/title 全 `GONE`，根宽度改 `WRAP_CONTENT`，按钮文字改 `≡ 修改器`。
- **弹层**：再叠一层 `addContentView`，根自带 `OnTouchListener` 吞触摸；维护 `OVL[]`，开新弹层前关掉旧的。

## 3. 自适应高度（数字键盘/列表不被裁）

```js
function fit(cap) {
  var VS = juse('android.view.View$MeasureSpec');
  body.measure(VS.makeMeasureSpec(K.widthPx - dp(18), -2147483648 /*AT_MOST*/),
               VS.makeMeasureSpec(0, 0 /*UNSPECIFIED*/));
  var h = body.getMeasuredHeight();
  var scr = act.getResources().getDisplayMetrics().heightPixels.value;
  var avail = Math.max(dp(140), Math.round(scr - K.posY() - dp(90)));
  scroll.setLayoutParams(LLP.$new(MATCH, Math.min(Math.max(h + dp(10), dp(120)), Math.min(cap || avail, avail))));
}
```

## 4. 手写虚拟列表（6000 件不卡、无翻页）

```js
var ROW_H = dp(64), VIS_ROWS = 6, COLS = 4;
// body = [上占位][窗口 win（VIS_ROWS 行 × COLS 格）][下占位]
function applyWindow(first) {
  var total = Math.ceil(curIds.length / COLS);
  first = Math.max(0, Math.min(first, Math.max(0, total - VIS_ROWS)));   // ← 不夹住会滑进空白
  for (var v = 0; v < rows.length; v++) rows[v].row.setVisibility(v < total ? VIS : GONE);
  var d = (curFirst < 0) ? 0 : (first - curFirst);
  if (Math.abs(d) === 1) {                    // 环形复用：只重填划出去的那一行
    if (d > 0) { var r0 = rows.shift(); rows.push(r0);
                 win.removeView(r0.row); win.addView(r0.row); fillRow(first + VIS_ROWS - 1, r0); }
    else       { var r1 = rows.pop(); rows.unshift(r1);
                 win.removeView(r1.row); win.addView(r1.row, 0); fillRow(first, r1); }
  } else if (curFirst < 0 || d !== 0) { for (var i = 0; i < rows.length; i++) fillRow(first + i, rows[i]); }
  curFirst = first;
  topPad.setLayoutParams(LLP.$new(MATCH, first * ROW_H));
  botPad.setLayoutParams(LLP.$new(MATCH, Math.max(0, (total - first - VIS_ROWS) * ROW_H)));  // 两段之和恒定 → 不跳
  ICON.prefetch(curIds.slice((first + VIS_ROWS) * COLS, (first + VIS_ROWS + 3) * COLS), ICON_PX);
}
// 滚动监听（单方法接口）
SCROLLER = Java.registerClass({ name: uniq('Scr'), implements: [juse('android.view.View$OnScrollChangeListener')],
  methods: { onScrollChange: function (v, x, y, ox, oy) { onScroll(y); } } }).$new();
o.scroll.setOnScrollChangeListener(SCROLLER);
```

## 5. 图标裁剪（含上下翻转）

```js
var crop = B.createBitmap.overload('android.graphics.Bitmap','int','int','int','int','android.graphics.Matrix','boolean')
            .call(B, atlas, r.x, 2048 - r.y - r.h, r.w, r.h, matrix /* setScale(f,f) */, false);   // 一次完成裁+缩
```

## 6. 天气「跟随 vs 维持」

```js
// 每 50ms：跟游戏真实状态同步，并**额外比对开关的真实勾选状态**（只比 STATE 会漏补 UI）
var r = !!IL.getS(IL.Main, 'raining');
var rUi = UI.S.switches['e-rain'] ? !!UI.S.switches['e-rain'].isChecked() : null;
if (r !== STATE.evRain || (rUi !== null && rUi !== r)) {
  var changed = (r !== STATE.evRain);
  STATE.evRain = r;
  if (changed) STATE.evRainAuto = r;          // 只有游戏自己变了才算「跟随」；修 UI 时别动这个标记
  UI.setSwitch('e-rain', r);
  if (changed) UI.say('检测到游戏' + (r ? '正在下雨' : '已停雨') + '：下雨开关已自动' + (r ? '打开' : '关闭'));
}
// 每帧：只有「用户自己开的」（auto=false）才复写维持
if (STATE.evRain && !STATE.evRainAuto) { IL.setS(IL.Main,'raining',true); IL.setS(IL.Main,'rainTime',36000); IL.setS(IL.Main,'maxRaining',1); }
// 关闭：立刻停掉本轮 + 2.5s 静默窗口（防止开关自己弹回去）
```

## 7. 无子弹发射（基准追踪）

```js
// 开：记基准 + 记类型（写回前校验，避免槽里换了东西被误写）
for each 背包格: if (item.ammo) { AMMO[slot] = item.stack; AMMO_TYPE[slot] = item.ammo; }
if (武器 useAmmo 在背包里没有对应弹药) { 找空格 SetDefaults(useAmmo); stack=9999; AMMO_INJECT=slot; }
// 心跳：打掉多少补回多少；捡到就抬基准（stack > 基准 → 基准 = stack）
if (st > AMMO[s]) AMMO[s] = st; else if (st < AMMO[s]) IL.setOn(IL.Item, it, 'stack', AMMO[s]);
// 关：把 stack 写回基准（= 原数量 + 期间捡到的），临时格清空
```
