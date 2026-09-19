#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「物品矩形表.json」压成 系统菜单.js 里的 ICON_TABLE 数据块。

编码（每个物品 9 个字符，字符表 = base64url 的 64 个字符 A-Za-z0-9-_）：
    [图集页 1][X 2][Y 2][宽 2][高 2]     每个数字 = 高低各 6 位
    全 0（'AAAAAAAAA'）表示该 ID 没有图集图标。
图集 PNG 上下翻转存放，运行时裁剪矩形 = (X, 2048-Y-H, X+W, 2048-Y)。

用法：
    python3 注入图标表.py            # 只是生成 /tmp/icon_table.js 并打印统计
    python3 注入图标表.py --write    # 直接写回 控制面板/系统菜单.js
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MENU = os.path.normpath(os.path.join(HERE, '..', '控制面板', '系统菜单.js'))
AL = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
MAX_ID = 6265           # 物品 ID 上限（含国服新增物品）
SUPP = '物品矩形表_补充.json'   # 别名物品（贴图不是 item_<id>.png 的，靠运行时 TextureId 补出来的）
CHUNK = 2000


def two(v):
    return AL[(v >> 6) & 63] + AL[v & 63]


def build_block():
    tab = json.load(open(os.path.join(HERE, '物品矩形表.json'), encoding='utf-8'))
    # 合并「别名物品」补充表（没有就跳过）
    sp = os.path.join(HERE, SUPP)
    if os.path.exists(sp):
        try:
            extra = json.load(open(sp, encoding='utf-8')).get('rects', {})
            for k, v in extra.items():
                tab.setdefault(k, v)
            print('  已合并补充表 %s：%d 条' % (SUPP, len(extra)))
        except Exception as e:
            print('  补充表读取失败（忽略）：%s' % e)
    out = []
    for i in range(MAX_ID + 1):
        r = tab.get(str(i))
        out.append(AL[0] + AL[0] * 8 if not r else
                   AL[r['atlas']] + two(r['x']) + two(r['y']) + two(r['w']) + two(r['h']))
    s = ''.join(out)
    lines = ['/* ── 物品图标矩形表（离线解析安装包得到，见 物品图标/README.md） ──',
             '   每个物品 9 个字符：图集页(1) X(2) Y(2) 宽(2) 高(2)，字符表 = base64url 的 64 个字符；',
             '   全 0 表示该 ID 没有图集图标。由 物品图标/注入图标表.py 自动生成，请勿手改。 */',
             'var ICON_TABLE = [']
    lines += ['"%s",' % s[i:i + CHUNK] for i in range(0, len(s), CHUNK)]
    lines.append('];')
    return '\n'.join(lines) + '\n', len(tab)


if __name__ == '__main__':
    block, n = build_block()
    open('/tmp/icon_table.js', 'w', encoding='utf-8').write(block)
    print('已生成 /tmp/icon_table.js：%d 个物品，%.1f KB' % (n, len(block) / 1024))
    if '--write' in sys.argv:
        src = open(MENU, encoding='utf-8').read()
        a = src.index('var ICON_TABLE = [')
        b = src.index('];', a) + 3
        src = src[:a] + block.rstrip('\n') + src[b:]
        open(MENU, 'w', encoding='utf-8').write(src)
        print('已写回 %s' % MENU)
