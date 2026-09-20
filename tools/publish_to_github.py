# -*- coding: utf-8 -*-
"""一条命令把本地仓库推上 GitHub 并发布最新 Release（token 只用于本次请求，不落盘）。

用法：
    python3 publish_to_github.py <TOKEN> [版本号]
例：
    python3 publish_to_github.py github_pat_xxx v1.2.4

做的事情：
  1) 校验 token（/user）；
  2) 推送本地仓库到 main（用带 token 的一次性 URL，完后不动 .git/config）；
  3) 建/更新 Release <版本号>，上传 terraria-modding-skill-<版本>-noassets.zip；
  4) 删掉该 Release 里除新附件以外的旧附件，并删掉更早的 Release（只留最新的）。

注意：**不上传含游戏素材的 full 包**（图集是游戏资源，仓库与 Release 都不放）。
"""
import json, os, subprocess, sys, urllib.request, urllib.error

OWNER, REPO = 'abcd123rft', 'terraria-android-modding'
REPO_DIR = '/sdcard/Download/DSHA/terraria-modding-skill-repo'
ZIP_DIR = '/sdcard/Download/DSHA'

def api(method, path, token, data=None, ctype='application/json'):
    url = path if path.startswith('http') else 'https://api.github.com' + path
    body = None
    if data is not None:
        body = data if isinstance(data, bytes) else json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header('Authorization', 'Bearer ' + token)
    req.add_header('Accept', 'application/vnd.github+json')
    req.add_header('User-Agent', 'dsha-publish')
    if body is not None:
        req.add_header('Content-Type', ctype)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw[:1] in (b'{', b'[') else raw)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try: return e.code, json.loads(raw)
        except Exception: return e.code, raw[:400]

def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    token = sys.argv[1].strip()
    ver = sys.argv[2] if len(sys.argv) > 2 else 'v1.2.4'
    asset = os.path.join(ZIP_DIR, 'terraria-modding-skill-%s-noassets.zip' % ver)
    if not os.path.exists(asset):
        print('缺附件：%s（先构建 zip）' % asset); sys.exit(1)

    st, me = api('GET', '/user', token)
    if st != 200:
        print('❌ token 无效（HTTP %d）：%s' % (st, me)); sys.exit(2)
    print('✅ token 有效，用户 %s' % me.get('login'))

    # ① 推送
    url = 'https://%s:%s@github.com/%s/%s.git' % (me['login'], token, OWNER, REPO)
    print('→ 推送 main …')
    r = subprocess.run(['git', '-C', REPO_DIR, 'push', url, 'HEAD:main'],
                       capture_output=True, text=True)
    print((r.stdout + r.stderr).strip()[-800:])
    if r.returncode != 0:
        print('❌ 推送失败'); sys.exit(3)
    sha = subprocess.run(['git', '-C', REPO_DIR, 'rev-parse', 'HEAD'],
                         capture_output=True, text=True).stdout.strip()
    print('✅ 已推送 %s' % sha[:10])

    # ② Release
    st, rel = api('GET', '/repos/%s/%s/releases/tags/%s' % (OWNER, REPO, ver), token)
    if st == 200:
        rid = rel['id']
        print('→ Release %s 已存在（id=%d），更新说明' % (ver, rid))
    else:
        st, rel = api('POST', '/repos/%s/%s/releases' % (OWNER, REPO), token,
                      {'tag_name': ver, 'target_commitish': 'main', 'name': '修改器技能包 %s' % ver,
                       'body': '', 'draft': False, 'prerelease': False})
        if st not in (200, 201):
            print('❌ 建 Release 失败（HTTP %d）：%s' % (st, rel)); sys.exit(4)
        rid = rel['id']
        print('✅ 已建 Release %s' % ver)

    # ③ 附件：删旧的，传新的
    st, assets = api('GET', '/repos/%s/%s/releases/%d/assets' % (OWNER, REPO, rid), token)
    keep = os.path.basename(asset)
    if isinstance(assets, list):
        for a in assets:
            if a['name'] == keep:
                api('DELETE', '/repos/%s/%s/releases/assets/%d' % (OWNER, REPO, a['id']), token)
                print('   删旧附件 %s' % a['name'])
    print('→ 上传 %s（%.1f MB）…' % (keep, os.path.getsize(asset) / 1048576))
    up = 'https://uploads.github.com/repos/%s/%s/releases/%d/assets?name=%s' % (OWNER, REPO, rid, keep)
    st, res = api('POST', up, token, open(asset, 'rb').read(), 'application/zip')
    if st not in (200, 201):
        print('❌ 上传失败（HTTP %d）：%s' % (st, res)); sys.exit(5)
    print('✅ 附件已上传：%s' % res.get('browser_download_url'))

    # ④ 删掉更早的 Release
    st, allrel = api('GET', '/repos/%s/%s/releases' % (OWNER, REPO), token)
    if isinstance(allrel, list):
        for r2 in allrel:
            if r2['tag_name'] != ver:
                api('DELETE', '/repos/%s/%s/releases/%d' % (OWNER, REPO, r2['id']), token)
                print('   已删除旧 Release %s' % r2['tag_name'])

    print('\n完成：https://github.com/%s/%s/releases/tag/%s' % (OWNER, REPO, ver))

if __name__ == '__main__':
    main()
