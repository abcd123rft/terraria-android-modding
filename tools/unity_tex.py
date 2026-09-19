import struct
def _rstr(b,p):
    n=struct.unpack_from('<i',b,p)[0]; p+=4
    s=b[p:p+n]; p+=n
    return s.decode('utf-8','replace'), (p+3)//4*4
def _rvec(b,p):
    n=struct.unpack_from('<i',b,p)[0]; p+=4
    d=b[p:p+n]; p+=n
    return d,(p+3)//4*4
def parse_texture(d):
    """Unity 2021.3 Texture2D（无类型树）实测布局"""
    p=0; o={}
    o['m_Name'],p=_rstr(d,p)
    o['m_ForcedFallbackFormat'],p=struct.unpack_from('<i',d,p)[0],p+4
    p+=4   # m_DownscaleFallback + m_IsAlphaChannelOptional（各 1 字节，补齐到 4）
    for k in ['m_Width','m_Height','m_CompleteImageSize','m_MipsStripped','m_TextureFormat','m_MipCount']:
        o[k],p=struct.unpack_from('<i',d,p)[0],p+4
    p+=4   # m_IsReadable + m_StreamingMipmaps
    for k in ['m_StreamingMipmapsPriority','m_ImageCount','m_TextureDimension']:
        o[k],p=struct.unpack_from('<i',d,p)[0],p+4
    o['m_FilterMode'],p=struct.unpack_from('<i',d,p)[0],p+4
    o['m_Aniso'],p=struct.unpack_from('<i',d,p)[0],p+4
    o['m_MipBias'],p=struct.unpack_from('<f',d,p)[0],p+4
    for k in ['m_WrapU','m_WrapV','m_WrapW','m_LightmapFormat','m_ColorSpace']:
        o[k],p=struct.unpack_from('<i',d,p)[0],p+4
    o['m_PlatformBlob'],p=_rvec(d,p)
    o['image_data'],p=_rvec(d,p)
    o['stream_offset']=struct.unpack_from('<q',d,p)[0]; p+=8
    o['stream_size']=struct.unpack_from('<I',d,p)[0]; p+=4
    o['stream_path'],p=_rstr(d,p)
    return o
FMT={1:'Alpha8',3:'RGB24',4:'RGBA32',5:'ARGB32',7:'RGB565',10:'DXT1',12:'DXT5',
     47:'ASTC_RGB_4x4',48:'ASTC_RGBA_4x4',49:'ASTC_RGB_5x5',50:'ASTC_RGBA_5x5',
     51:'ASTC_RGB_6x6',52:'ASTC_RGBA_6x6',63:'ASTC_RGB_8x8',64:'ASTC_RGBA_8x8',
     65:'ETC_RGB4',67:'ETC2_RGB4',68:'ETC2_RGB4_PTA',69:'ETC2_RGBA8'}
