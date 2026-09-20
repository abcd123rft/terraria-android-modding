# -*- coding: utf-8 -*-
"""修正图集 PNG：① 整幅上下翻转 ② R/B 通道换回。

为什么需要它：从 resources.assets 解出来的两张物品图集在转换时漏了两步 ——
  · Unity 纹理是**自下而上**存的，写出 PNG 时没翻回来 → 整幅图上下颠倒；
  · 纹理字节序是 **BGRA**，当成 RGBA 写 → 红蓝通道互换（金币会变蓝色）。
之前只按「矩形 y 改成 图高-Y-H」把**位置**找对了，但图块**内容**仍是倒的，
所以药水瓶是倒立的、金币是蓝的。本脚本直接修素材本身（图片在任何看图软件里也是正的），
之后脚本里裁剪矩形就应该是朴素的 (X, Y, X+W, Y+H)。

用法：
  python3 修正图集.py 文件1.png [文件2.png ...]        # 原地修正，先备份成 *.orig.png
  python3 修正图集.py --no-backup 文件.png
"""
import struct, sys, zlib, os, time

def read_png(path):
    d = open(path, 'rb').read()
    if d[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('不是 PNG：' + path)
    p, idat, ihdr = 8, [], None
    while p < len(d):
        ln = struct.unpack_from('>I', d, p)[0]
        typ = d[p + 4:p + 8]
        body = d[p + 8:p + 8 + ln]
        if typ == b'IHDR':
            ihdr = struct.unpack('>IIBBBBB', body)
        elif typ == b'IDAT':
            idat.append(body)
        elif typ == b'IEND':
            break
        p += 12 + ln
    w, h, depth, ctype, comp, filt, inter = ihdr
    if depth != 8 or ctype != 6 or inter != 0:
        raise ValueError('只支持 8bit RGBA 非隔行 PNG：%s (depth=%d ctype=%d inter=%d)' % (path, depth, ctype, inter))
    raw = zlib.decompress(b''.join(idat))
    return w, h, raw

def unfilter(w, h, raw):
    bpp, stride = 4, w * 4
    out = bytearray(h * stride)
    pos = 0
    prev = bytearray(stride)
    for y in range(h):
        ft = raw[pos]; pos += 1
        line = bytearray(raw[pos:pos + stride]); pos += stride
        if ft == 0:
            pass
        elif ft == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xff
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xff
        elif ft == 3:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xff
        elif ft == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xff
        else:
            raise ValueError('未知过滤器类型 %d（第 %d 行）' % (ft, y))
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return out

def write_png(path, w, h, pix):
    stride = w * 4
    raw = bytearray()
    for y in range(h):
        raw.append(0)                                  # 过滤器 0（None）
        raw += pix[y * stride:(y + 1) * stride]
    def chunk(typ, body):
        return struct.pack('>I', len(body)) + typ + body + struct.pack('>I', zlib.crc32(typ + body) & 0xffffffff)
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) +
                           chunk(b'IDAT', zlib.compress(bytes(raw), 9)) + chunk(b'IEND', b''))

def fix(path, backup=True):
    t0 = time.time()
    w, h, raw = read_png(path)
    pix = unfilter(w, h, raw)
    stride = w * 4
    out = bytearray(len(pix))
    for y in range(h):                                  # 上下翻转
        src = (h - 1 - y) * stride
        out[y * stride:(y + 1) * stride] = pix[src:src + stride]
    for i in range(0, len(out), 4):                     # R/B 换回
        out[i], out[i + 2] = out[i + 2], out[i]
    if backup:
        bak = path + '.orig.png'
        if not os.path.exists(bak):
            os.rename(path, bak)
        else:
            os.remove(path)
    write_png(path, w, h, out)
    print('%s：%dx%d 已修正（翻转+通道），耗时 %.1fs，大小 %d → %d' %
          (os.path.basename(path), w, h, time.time() - t0, len(raw), os.path.getsize(path)))
    if backup:
        print('   原图备份：%s' % (path + '.orig.png'))

if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a != '--no-backup']
    nb = '--no-backup' in sys.argv
    if not args:
        print(__doc__)
    for f in args:
        fix(f, backup=not nb)
