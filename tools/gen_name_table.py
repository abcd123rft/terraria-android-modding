#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「物品 ID → 中文名」做成离线名表，内嵌进 系统菜单.js 的 ITEM_NAMES。

为什么要做：菜单里显示物品名原来是每次调一次 il2cpp 的
`Lang.GetItemNameValue`（每次都要「按名字查方法」+ `runtime_invoke`，实测量级 ~10ms/次），
一页 24 个格子就是 300~400ms 的卡顿。名字是静态数据，离线内嵌后**零调用**。

数据源：`物品库/out/terraria_items_all.csv`（当初就是从游戏进程里导出的，与运行时名字一致）。

用法：
    python3 生成名称表.py            # 只生成 /tmp/item_names.js 并打印统计
    python3 生成名称表.py --write    # 直接写回 ../控制面板/系统菜单.js
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, 'out', 'terraria_items_all.csv')
MENU = os.path.normpath(os.path.join(HERE, '..', '控制面板', '系统菜单.js'))
MAX_ID = 6265           # 与图标表一致（含国服新增物品）
CHUNK = 2000


def load_names():
    names = {}
    with open(CSV, encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            try:
                i = int(row['ID'])
            except (KeyError, ValueError, TypeError):
                continue
            nm = (row.get('中文名') or '').strip()
            if nm:
                names[i] = nm
    return names


def js_str(s):
    """转义成可以安全放进 JS 字符串字面量的形式。
       注意**换行必须转义**：名表用 '\n' 当分隔符，直接写进字面量会让字符串跨行 → 语法错误。"""
    return (s.replace('\\', '\\\\').replace('"', '\\"')
             .replace('\r', '\\r').replace('\n', '\\n'))


def build_block(names):
    arr = [names.get(i, '') for i in range(MAX_ID + 1)]
    blob = '\n'.join(arr)
    chunks = [blob[i:i + CHUNK] for i in range(0, len(blob), CHUNK)]
    lines = ['/* ── 物品中文名离线表（由 物品库/生成名称表.py 生成，请勿手改） ──',
             '   第 i 项 = ID i 的中文名，空串表示该 ID 无名（运行时再问游戏兜底）。',
             '   内嵌的目的：避免每显示一个名字就做一次 il2cpp 调用（翻页卡顿的主因）。 */',
             'var ITEM_NAMES = [']
    lines += ['"%s",' % js_str(c) for c in chunks]
    lines.append('];')
    return '\n'.join(lines) + '\n', len(names), len(blob)


if __name__ == '__main__':
    names = load_names()
    block, n, size = build_block(names)
    open('/tmp/item_names.js', 'w', encoding='utf-8').write(block)
    print('CSV 里有名字的物品 %d 件；生成 /tmp/item_names.js %.1f KB（名表覆盖 ID 0..%d）'
          % (n, len(block.encode()) / 1024, MAX_ID))
    if '--write' in sys.argv:
        src = open(MENU, encoding='utf-8').read()
        a = src.index('var ITEM_NAMES = [')
        b = src.index('];', a) + 3
        src = src[:a] + block.rstrip('\n') + src[b:]
        open(MENU, 'w', encoding='utf-8').write(src)
        print('已写回 %s' % MENU)
