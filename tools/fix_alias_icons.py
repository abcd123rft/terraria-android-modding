#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补「别名物品」的图标（贴图名不是 item_<id>.png 的那些）。

背景：绝大多数物品的贴图 key = CRC32("item_<id>.png")，能离线从安装包的图集矩形表查到。
但国服约 181 件（旧版/别名物品，如 3665 受困宝箱 = 用 id 48 的贴图、6147 K记鸡腿 …）
走的是别的资源名，CRC32 对不上 → 菜单里显示不出图标。

做法（**一次性**，需要游戏在跑）：
  ① python3 补别名图标.py gen            生成 /tmp/missN.js 三批探测脚本
  ② 逐批在游戏里跑（JsHook）：
       cd ../控制面板
       python3 jshook.py exec --file /tmp/miss1.js --wait 8   → 把日志里 "[缺图] R id|key …" 抄进 /tmp/pairs.txt
       （三批都跑一遍；也可以直接用 python3 补别名图标.py collect 自动跑 + 收集）
  ③ python3 补别名图标.py parse          用 /tmp/pairs.txt 离线查图集矩形表 → 物品矩形表_补充.json
  ④ python3 注入图标表.py --write         重新生成菜单里的 ICON_TABLE（会自动合并补充表）

注意：剩下约 33 件（如 6265）的贴图**根本没进图集**（独立贴图），查不到矩形，菜单里仍是 ID 占位。
"""
import json
import os
import re
import struct
import subprocess
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
MENU_DIR = os.path.normpath(os.path.join(HERE, '..', '控制面板'))
CSV = os.path.normpath(os.path.join(HERE, '..', '物品库', 'out', 'terraria_items_all.csv'))
ASSETS = os.environ.get('TASSETS', '/root/DshaWorks/unpack/resources.assets')
DB_OFFSET = 18755426
REC = 22
MAX_ID = 6265
PAIRS = '/tmp/pairs.txt'
BATCH = 60

JS_TMPL = r'''(function(){
var IDS=[%s];
function L(){ console.log('[缺图] ' + Array.prototype.join.call(arguments,' ')); }
var m=Process.findModuleByName('libil2cpp.so');
function E(n){var p=null;try{p=m.findExportByName(n);}catch(e){}if(!p){try{p=m.getExportByName(n);}catch(e){}}return p;}
function F(n,r,a){var x=E(n);if(!x)throw new Error('缺 '+n);return new NativeFunction(x,r,a);}
var il={domain_get:F('il2cpp_domain_get','pointer',[]),
 domain_get_assemblies:F('il2cpp_domain_get_assemblies','pointer',['pointer','pointer']),
 assembly_get_image:F('il2cpp_assembly_get_image','pointer',['pointer']),
 image_get_name:F('il2cpp_image_get_name','pointer',['pointer']),
 class_from_name:F('il2cpp_class_from_name','pointer',['pointer','pointer','pointer']),
 class_get_field_from_name:F('il2cpp_class_get_field_from_name','pointer',['pointer','pointer']),
 field_get_value:F('il2cpp_field_get_value','void',['pointer','pointer','pointer']),
 field_static_get_value:F('il2cpp_field_static_get_value','void',['pointer','pointer']),
 object_get_class:F('il2cpp_object_get_class','pointer',['pointer']),
 thread_attach:F('il2cpp_thread_attach','pointer',['pointer'])};
function cs(p){try{return (!p||p.isNull())?null:p.readUtf8String();}catch(e){return null;}}
var dom=il.domain_get(); il.thread_attach(dom);
var sz=Memory.alloc(8), asms=il.domain_get_assemblies(dom,sz), n=sz.readU64().toNumber(), ACS=null;
for(var i=0;i<n;i++){var img=il.assembly_get_image(asms.add(i*Process.pointerSize).readPointer()); if(String(cs(il.image_get_name(img)))==='Assembly-CSharp.dll') ACS=img;}
function cls(ns,nm){return il.class_from_name(ACS,Memory.allocUtf8String(ns),Memory.allocUtf8String(nm));}
var b=Memory.alloc(64);
il.field_static_get_value(il.class_get_field_from_name(cls('Terraria.GameContent','TextureAssets'),Memory.allocUtf8String('Item')),b);
var arr=b.readPointer(), len=arr.add(0x18).readS32();
L('数组长度=' + len + ' 本批 ' + IDS.length + ' 个');
var out=[], none=0;
for (var k=0;k<IDS.length;k++){
  var id=IDS[k], s=null;
  try{
    if (id < len) {
      var el=arr.add(0x20+id*Process.pointerSize).readPointer();
      if(!el.isNull()){
        il.field_get_value(el, il.class_get_field_from_name(il.object_get_class(el), Memory.allocUtf8String('Value')), b);
        var t=b.readPointer();
        if(!t.isNull()){
          var pp=t.add(96).readPointer();
          if(!pp.isNull()) s=id+'|'+pp.add(16).readS32();
        }
      }
    }
  }catch(e){}
  if(s) out.push(s); else none++;
}
L('拿到 TextureId 的 ' + out.length + ' 个，空 ' + none + ' 个');
for (var j=0;j<out.length;j+=15) L('R ' + out.slice(j,j+15).join(' '));
})();'''


def sgn(v):
    return v - 0x100000000 if v >= 0x80000000 else v


def key_of(item_id, pat='item_%d.png'):
    return sgn(zlib.crc32((pat % item_id).encode()) & 0xffffffff)


def load_db():
    d = open(ASSETS, 'rb').read()
    cnt = struct.unpack_from('<i', d, DB_OFFSET - 4)[0]
    out = {}
    q = DB_OFFSET
    for _ in range(cnt):
        key, atlas = struct.unpack_from('<ii', d, q)
        w, h, x, y, sc = struct.unpack_from('<hhhhh', d, q + 8)
        out[key] = dict(atlas=atlas, x=x, y=y, w=w, h=h, scale=sc)
        q += REC
    return out


def missing_ids():
    import csv as _csv
    db = load_db()
    ids = []
    with open(CSV, encoding='utf-8-sig', newline='') as f:
        for row in _csv.DictReader(f):
            try:
                ids.append(int(row['ID']))
            except (KeyError, ValueError, TypeError):
                pass
    return sorted(i for i in ids if key_of(i) not in db)


def gen():
    ids = missing_ids()
    files = []
    for n, a in enumerate(range(0, len(ids), BATCH)):
        path = '/tmp/miss%d.js' % (n + 1)
        open(path, 'w').write(JS_TMPL % ','.join(map(str, ids[a:a + BATCH])))
        files.append(path)
    print('缺图物品 %d 件，已生成 %d 个探测脚本：%s' % (len(ids), len(files), ' '.join(files)))
    print('依次执行并把日志里的 [缺图] R 行收进 %s（或用 collect 子命令自动做）' % PAIRS)


def collect():
    files = sorted(f for f in os.listdir('/tmp') if re.fullmatch(r'miss\d+\.js', f))
    open(PAIRS, 'w').close()
    for f in files:
        p = subprocess.run([sys.executable, 'jshook.py', 'exec', '--file', '/tmp/' + f, '--wait', '8'],
                           cwd=MENU_DIR, capture_output=True, text=True)
        try:
            data = json.loads(p.stdout)
        except ValueError:
            print('  %s 输出无法解析，跳过' % f)
            continue
        got = 0
        for line in (data.get('log') or {}).get('lines') or []:
            m = re.search(r'\[缺图\] R (.*)$', line)
            if m:
                with open(PAIRS, 'a') as out:
                    for tok in m.group(1).split():
                        if '|' in tok:
                            out.write(tok + '\n')
                            got += 1
        print('  %s → 收到 %d 条' % (f, got))
    seen = set()
    lines = []
    for line in open(PAIRS):
        if line.strip() and line not in seen:
            seen.add(line)
            lines.append(line)
    open(PAIRS, 'w').writelines(lines)
    print('共收集 %d 条（去重后）→ %s' % (len(lines), PAIRS))
    parse()


def parse():
    db = load_db()
    extra, miss = {}, []
    for line in open(PAIRS):
        line = line.strip()
        if '|' not in line:
            continue
        i, k = line.split('|')
        r = db.get(int(k))
        if r:
            extra[i] = r
        else:
            miss.append(i)
    json.dump({'说明': '别名物品：贴图名不是 item_<id>.png（多为旧版/共用贴图），'
                       'key 由运行时读 TextureAssets.Item[id].Value.PackedEntry.TextureId 得到。',
               'rects': extra},
              open(os.path.join(HERE, '物品矩形表_补充.json'), 'w'), ensure_ascii=False, indent=0)
    print('解析 %d 条：命中 %d，未命中（贴图没进图集）%d' % (len(extra) + len(miss), len(extra), len(miss)))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'gen'
    {'gen': gen, 'collect': collect, 'parse': parse}.get(cmd, gen)()
