# -*- coding: utf-8 -*-
"""从安装包离线解析「物品ID → 图集矩形」，并生成校验图。
原理：
  1) 图集矩形表以「按 key 排序」的顺序序列化在 resources.assets 中（每条约 22 字节）；
  2) 物品的 key = int32(CRC32("item_<id>.png"))；
  3) 记录字段：key(int32) atlasIndex(int32) W(int16) H(int16) X(int16) Y(int16) scale(int16) flag(int32)；
  4) 图集 PNG 曾经是上下翻转存放的（2026-09-20 已修正：见 修正图集.py，现为正向且通道正常）；现在图集已修正为正向，裁剪矩形就是朴素的 (X, Y, X+W, Y+H)。
"""
import struct, zlib, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.environ.get('TASSETS', '/root/DshaWorks/unpack/resources.assets')
ATLAS_DIR = os.path.join(HERE, '图集')
PAGES = {0: 'atlas_Item1_2048x2048.png', 1: 'atlas_Item2_2048x2048.png'}
DB_OFFSET = 18755426          # 「Item」图集矩形表所在偏移（见 README）
REC = 22

def sgn(v):
    return v - 0x100000000 if v >= 0x80000000 else v

def key_of(item_id):
    return sgn(zlib.crc32(('item_%d.png' % item_id).encode()) & 0xffffffff)

def load_db(path=ASSETS):
    d = open(path, 'rb').read()
    cnt = struct.unpack_from('<i', d, DB_OFFSET - 4)[0]
    out = {}
    q = DB_OFFSET
    for _ in range(cnt):
        key, atlas = struct.unpack_from('<ii', d, q)
        w, h, x, y, sc = struct.unpack_from('<hhhhh', d, q + 8)
        out[key] = dict(atlas=atlas, x=x, y=y, w=w, h=h, scale=sc)
        q += REC
    return out, cnt, q

def build(max_id=7000):
    db, cnt, end = load_db()
    table = {}
    for i in range(max_id):
        r = db.get(key_of(i))
        if r:
            table[i] = r
    return db, table, cnt, end

if __name__ == '__main__':
    db, table, cnt, end = build()
    json.dump({str(k): v for k, v in sorted(table.items())},
              open(os.path.join(HERE, '物品矩形表.json'), 'w'), ensure_ascii=False, indent=0)
    with open(os.path.join(HERE, '物品矩形表.txt'), 'w') as f:
        f.write('# 物品ID 图集页 X Y 宽 高\n')
        for i, r in sorted(table.items()):
            f.write('%d %d %d %d %d %d\n' % (i, r['atlas'], r['x'], r['y'], r['w'], r['h']))
    # 图集复制到纯英文目录：供游戏进程 decodeFile 读取（也方便 HTTP 服务直接指向它）
    dst = os.environ.get('ICON_DST', '/sdcard/Download/DSHA/terraria_icons')
    try:
        os.makedirs(dst, exist_ok=True)
        import shutil
        for pg, src in PAGES.items():
            s = os.path.join(ATLAS_DIR, src)
            if os.path.exists(s):
                shutil.copyfile(s, os.path.join(dst, 'atlas_%d.png' % pg))
                print('已复制 %s → %s/atlas_%d.png' % (src, dst, pg))
    except Exception as e:
        print('复制图集失败（不影响矩形表）：%s' % e)
    pages = {}
    for r in db.values():
        pages[r['atlas']] = pages.get(r['atlas'], 0) + 1
    print('DB 条目 %d（偏移 %d..%d），各图集页条数 %s' % (cnt, DB_OFFSET, end, pages))
    print('解析出物品 %d 个（0..%d）' % (len(table), max(table)))
