import struct, os, sys, time
import lz4.block
BUNDLE='/root/DshaWorks/unpack/data.unity3d'; OUT='/root/DshaWorks/unpack'
def u32(b,p): return struct.unpack('>I',b[p:p+4])[0]
def i64(b,p): return struct.unpack('>q',b[p:p+8])[0]
def u16(b,p): return struct.unpack('>H',b[p:p+2])[0]
def cstr(b,p):
    e=b.index(b'\0',p); return b[p:e].decode('utf-8','replace'), e+1
f=open(BUNDLE,'rb'); head=f.read(256)
sig,p=cstr(head,0); ver=u32(head,p); p+=4
uv,p=cstr(head,p); ur,p=cstr(head,p)
size=i64(head,p); p+=8; cblk=u32(head,p); p+=4; ublk=u32(head,p); p+=4; flags=u32(head,p); p+=4
if ver>=7: p=(p+15)//16*16
f.seek(p); raw=lz4.block.decompress(f.read(cblk), uncompressed_size=ublk)
q=16; nb=u32(raw,q); q+=4
blocks=[(u32(raw,q+i*10),u32(raw,q+i*10+4),u16(raw,q+i*10+8)) for i in range(nb)]
q+=nb*10; nn=u32(raw,q); q+=4
nodes=[]
for _ in range(nn):
    off=i64(raw,q); sz=i64(raw,q+8); fl=u32(raw,q+16); q+=20
    path,q=cstr(raw,q); nodes.append([off,sz,fl,path])
data_start=((p+cblk)+15)//16*16
want=set(sys.argv[1:]) if len(sys.argv)>1 else set(n[3] for n in nodes)
print('要提取的节点:', sorted(want), flush=True)
handles={}
for nd in nodes:
    if nd[3] in want: handles[nd[3]]=open(os.path.join(OUT,nd[3]),'wb')
f.seek(data_start); gpos=0
for (us,cs,fl) in blocks:
    comp=f.read(cs)
    out=lz4.block.decompress(comp, uncompressed_size=us) if (fl&0x3f) in (2,3) else comp
    bs,be=gpos,gpos+len(out)
    for nd in nodes:
        if nd[3] not in handles: continue
        ns,ne=nd[0],nd[0]+nd[1]
        if ne<=bs or ns>=be: continue
        handles[nd[3]].write(out[max(ns,bs)-bs:min(ne,be)-bs])
    gpos=be
for h in handles.values(): h.close()
for k in sorted(want):
    pp=os.path.join(OUT,k)
    if os.path.exists(pp): print('  %-32s %.2f MB' % (k, os.path.getsize(pp)/1048576), flush=True)
