import re, json, base64, io
from PIL import Image
import os
R=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lv=open(R+'/Sources/GameCore/Levels.swift').read()
levels=[]
for m in re.finditer(r'LevelDefinition\(name: "([^"]+)", theme: \.(\w+), parTime: (\d+), map: """\n(.*?)\n\s*"""', lv, re.S):
    rows=[r.strip() for r in m.group(4).split('\n') if r.strip()]
    levels.append({'name':m.group(1),'theme':m.group(2),'parTime':int(m.group(3)),'map':'\n'.join(rows)})
assert len(levels)==4
art=open(R+'/App/Art.swift').read()
def pal(name):
    start=art.index(name+': [Character: UIColor] = [')+len(name+': [Character: UIColor] = [')
    seg=art[start:art.index('\n    ]', start)]
    out={}
    for ch,val in re.findall(r'"(\w)": (\.init\(hex: 0x[0-9a-f]+\)|\.white)', seg):
        out[ch]=0xffffff if val=='.white' else int(re.search(r'0x([0-9a-f]+)',val).group(1),16)
    return out
def rows_between(start, end):
    seg=art[art.index(start):art.index(end, art.index(start))]
    return re.findall(r'"([.\w]+)"', seg)
body=rows_between('private static let sassyBody = [', ']')
def legs(line_key):
    i=art.index(line_key); seg=art[i:art.index('\n',i)]
    return re.findall(r'"([.\w]+)"', seg)[0:2]
idle=re.findall(r'"([.\w]+)"', art[art.index('static let sassyIdle'):art.index('\n',art.index('static let sassyIdle'))])
runseg=art[art.index('static let sassyRun'):art.index('static let sassyJump')]
runs=[re.findall(r'"([.\w]+)"', l) for l in runseg.split('\n') if 'sprite(' in l]
jump=re.findall(r'"([.\w]+)"', art[art.index('static let sassyJump'):art.index('\n',art.index('static let sassyJump'))])
def frames(name):
    seg=art[art.index(f'static let {name} = ['):]
    seg=seg[:seg.index('\n    ]')]
    return [re.findall(r'"([.\w]+)"', block) for block in seg.split('sprite(')[1:]]
sprites={'sassyPalette':pal('sassyPalette'),'critterPalette':pal('critterPalette'),'sassyBody':body,
 'legs':{'idle':idle,'run1':runs[0],'run2':runs[1],'jump':jump},
 'beetle':frames('beetle'),'spiker':frames('spiker'),'bat':frames('bat')}
assert len(sprites['sassyPalette'])>=7 and len(sprites['critterPalette'])>=8, sprites['sassyPalette']
assert len(body)==11 and all(len(r)==18 for r in body), body
for k,v in sprites['legs'].items(): assert len(v)==2 and all(len(r)==18 for r in v),(k,v)
for k in ('beetle','spiker','bat'): assert len(sprites[k])==2 and all(len(f)==8 for f in sprites[k]),k
im=Image.open(R+'/docs/app-icon.png').convert('RGB').resize((256,256),Image.LANCZOS)
buf=io.BytesIO(); im.save(buf,'JPEG',quality=86)
icon='data:image/jpeg;base64,'+base64.b64encode(buf.getvalue()).decode()
t=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'template.html')).read()
t=t.replace('/*LEVELS*/',json.dumps(levels,ensure_ascii=False)).replace('/*SPRITES*/',json.dumps(sprites)).replace('__ICON__',icon)
open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'index.html'),'w').write(t)
print(len(t), [l['name'] for l in levels])
