"""임시 — Project registry R3 누락 정정. 실행 후 삭제."""
import glob, os, json

REG = r'C:\claude\.claude\hooks\registry'
patterns = ['C:/Users/AidenKim', 'C:' + chr(92) + 'Users' + chr(92) + 'AidenKim']
sep = chr(92)

updated = []
for jf in glob.glob(REG + '/**/*.json', recursive=True):
    raw = open(jf, 'r', encoding='utf-8', newline='').read()
    if any(p in raw for p in patterns):
        new = raw.replace(patterns[0], '$HOME').replace(patterns[1], '$HOME')
        open(jf, 'w', encoding='utf-8', newline='').write(new)
        updated.append(os.path.relpath(jf, REG).replace(sep, '/'))

print(f'{len(updated)} Project registry json updated -> $HOME')
for u in updated:
    print(f'  - {u}')

print()
print('--- 검증: parse + $HOME 확장 + 스크립트 존재 ---')
bad = 0
phantom = []
for jf in glob.glob(REG + '/**/*.json', recursive=True):
    if '_disabled' in jf.replace(sep, '/'):
        continue
    try:
        spec = json.load(open(jf, encoding='utf-8'))
    except Exception as e:
        print(f'  JSON ERROR {os.path.basename(jf)}: {e}')
        bad += 1
        continue
    cmd = spec.get('command', '')
    if any(p in cmd for p in patterns):
        print(f'  STILL HARDCODED: {os.path.basename(jf)}')
        bad += 1
        continue
    exp = os.path.expandvars(cmd)
    parts = exp.replace('"', '').split()
    script = ''
    for i, p in enumerate(parts):
        if p == '-File' and i + 1 < len(parts):
            script = parts[i + 1]
            break
        if p.endswith(('.py', '.mjs', '.ps1', '.cjs', '.js')):
            script = p
    if script and not os.path.isfile(script):
        phantom.append((os.path.relpath(jf, REG), script))

print(f'검증 완료: bad={bad}, phantom(script 부재)={len(phantom)}')
if phantom:
    print('--- phantom 목록 (script 부재, R3 와 별개 결함) ---')
    for n, s in phantom:
        print(f'  {n} -> {s}')
