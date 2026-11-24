"""Photo-referenced, synthetic inspection sites (metres, NED).

These are authored training layouts, not surveys of the referenced facilities.
The same primitive manifest drives the visible structures and collision proxies.
Small bolts, fouling and surface damage are visual details only.
"""
from copy import deepcopy
from functools import lru_cache
from .world import Box, Cylinder

SITE_KEYS = ('subsea_cable_inspection', 'subsea_pipeline_inspection', 'port_facility_inspection','cooperative_cable_repair')


def _cyl(items, name, a, b, radius, material='steel', detail='', entity=None):
    items.append(dict(type='cylinder', name=name, p0=list(a), p1=list(b), radius=radius,
                      material=material, detail=detail, entity_id=entity))


def _box(items, name, center, size, material='concrete', detail='', entity=None):
    items.append(dict(type='box', name=name, center=list(center), size=list(size),
                      material=material, detail=detail, entity_id=entity))


def _target(key, slug, label, point, target, description, radius=.65):
    return dict(id=f'{key}-{slug}', entity_id=f'{key}-{slug}', label=label,
                point=list(point), target_point=list(target), radius=1.1,
                target_radius=radius, hold_s=5., description=description)


def _cable():
    key=SITE_KEYS[0]; g=[]
    # Black sheathed cable emerges from a short protective mattress, rises over
    # supports and returns to the bed. The supported free span is visible from
    # either side; the buried continuation is intentionally not rendered.
    path=[(3,0,17.94),(8,0,17.88),(12,0,17.7),(16,0,16.75),
          (20,0,16.98),(24,0,16.75),(28,0,17.65),(32,0,17.83),(38,0,17.83)]
    for i,(a,b) in enumerate(zip(path,path[1:])):
        entity=f'{key}-span' if i in (3,4) else f'{key}-sheath' if i==6 else None
        _cyl(g,f'C01 cable section {i+1}',a,b,.085,'cable','cable',entity)
    for x in (16,24):
        _box(g,f'C01 grout support {x}',(x,0,17.4),(1.2,1.1,1.2),'grout','sandbag')
    _box(g,'C01 articulated protection mattress',(9,0,17.67),(4.8,3.0,.56),
         'concrete','mattress',f'{key}-mattress')
    _cyl(g,'C01 split protection sleeve',(34,0,17.73),(38,0,17.73),.22,'polymer','restrictor',f'{key}-sleeve')
    _box(g,'C01 termination skid',(40,0,17.48),(3.0,2.2,.32),'steel','skid')
    _box(g,'C01 termination cover',(40,0,16.8),(2.3,1.55,1.0),'yellow','cabinet')
    _cyl(g,'C01 termination inlet',(38,0,17.73),(39,0,17.15),.25,'polymer','restrictor')
    # Low rock support/riprap: coarse collision envelope also drawn visibly.
    for x,y,r in ((5,2.9,.35),(11,-3,.45),(15,2.6,.35),(25,2.5,.42),(31,-2.5,.36),(41,3,.48)):
        _box(g,f'C01 rock {x}',(x,y,18-r*.45),(r*2,r*1.6,r*.9),'rock','rock')
    targets=[
        _target(key,'mattress','保護墊：邊緣錯位與覆蓋', (9,-3.3,17.0),(9,-.7,17.22),
                '記錄連接繩、邊緣抬起與覆蓋範圍；勿用機械手搬動保護墊。',1.4),
        _target(key,'span','海纜懸跨：支點與離底間隙',(20,-2.5,16.5),(20,0,16.98),
                '從側面記錄海纜離底間隙及兩端支點；照片不能代替工程跨距量測。',.9),
        _target(key,'sheath','外護套：局部磨耗',(30,-2.3,17.2),(30,0,17.74),
                '辨識表面磨耗與附著物，保留近照；不推定內部導體已損傷。',.55),
        _target(key,'sleeve','彎曲限制器：節段接縫',(36,-2.5,17.15),(36,0,17.73),
                '檢視分節保護套的接縫、端部支承與局部偏移。',.75)]
    return dict(key=key,name='海底電纜巡檢場',seabed_depth=18.,biome='temperate',
                visibility_m=12.,start_pos=[0,-5,4],spool_pos=[-3,-6,0],tether_length=80.,
                geometry=g,targets=targets,brief='沿海纜檢查保護墊、懸跨、外護套與彎曲限制器；接近後穩定拍照留證。')


def _pipeline():
    key=SITE_KEYS[1]; g=[]
    # 610 mm synthetic coated pipeline. Concrete joints and anodes are explicit
    # parts rather than a single perfectly smooth, shiny tube.
    for i in range(7):
        a=3+i*5; b=a+5
        entity=f'{key}-coating' if i==1 else f'{key}-span' if i==3 else None
        _cyl(g,f'P01 pipe spool {i+1}',(a,0,20.95),(b,0,20.95),.305,'pipe','pipe',entity)
    for x in (3,13,23,33,38):
        _box(g,f'P01 support sleeper {x}',(x,0,21.68),(1.0,2.3,.64),'concrete','sleeper')
    _cyl(g,'P01 flange joint',(27.75,0,20.95),(28.25,0,20.95),.49,'steel','flange',f'{key}-flange')
    _cyl(g,'P01 sacrificial bracelet anode',(32.45,0,20.95),(33.1,0,20.95),.38,'anode','anode',f'{key}-anode')
    _cyl(g,'P01 elbow riser',(38,0,20.95),(38,0,19.1),.305,'pipe','pipe')
    _box(g,'P01 valve skid',(39.2,0,21.68),(4.2,3.4,.38),'steel','skid')
    _box(g,'P01 valve body',(38,0,19.55),(1.0,1.0,1.4),'yellow','valve')
    for x in (37.3,41.1):
        for y in (-1.5,1.5):
            _cyl(g,f'P01 guard post {x} {y}',(x,y,21.5),(x,y,18.8),.08,'yellow')
    for y in (-1.5,1.5):
        _cyl(g,f'P01 guard rail {y}',(37.3,y,18.8),(41.1,y,18.8),.08,'yellow')
    targets=[
        _target(key,'coating','管段塗層：表面剝落',(10,-2.7,20.45),(10,0,20.95),
                '記錄外塗層剝落與鏽色表面，不以照片判定剩餘壁厚。',.8),
        _target(key,'span','管線懸跨：支承與離底',(20,-2.8,20.6),(20,0,20.95),
                '觀察管底與海床之間的連續空隙，保持側向安全距離。',1.1),
        _target(key,'flange','法蘭：螺栓與接縫',(28,-2.5,20.5),(28,0,20.95),
                '逐項拍攝法蘭接縫、螺栓圈及腐蝕外觀；不操作帶壓閥件。',.7),
        _target(key,'anode','犧牲陽極：耗損外觀',(32.8,-2.5,20.45),(32.8,0,20.95),
                '比較陽極表面與固定帶；僅做目視記錄，未模擬電位探針量測。',.7)]
    return dict(key=key,name='海底管線巡檢場',seabed_depth=22.,biome='temperate',
                visibility_m=13.,start_pos=[0,-5,4],spool_pos=[-3,-6,0],tether_length=85.,
                geometry=g,targets=targets,brief='沿包覆管線檢查塗層、懸跨、法蘭螺栓及犧牲陽極；以目視與照片完成記錄。')


def _port():
    key=SITE_KEYS[2]; g=[]
    # Jetty: working water lies on negative East side, not inside a solid quay.
    _box(g,'J01 deck',(22,5,-1.05),(34,11,1.2),'concrete','deck')
    _box(g,'J01 shore abutment',(42,5,5),(5,16,15),'concrete','quay')
    for x in (8,16,24,32,38):
        for y in (1,8):
            entity=f'{key}-pile' if x==16 and y==1 else f'{key}-anode' if x==24 and y==1 else None
            _cyl(g,f'J01 pile {x} {y}',(x,y,-.5),(x,y,16),.48,'pile','pile',entity)
        _box(g,f'J01 transverse beam {x}',(x,4.5,.1),(1.0,9.0,1.1),'concrete','beam')
    for y in (1,8):
        _box(g,f'J01 longitudinal beam {y}',(22,y,.0),(33,1.0,1.25),'concrete','beam')
    for x in (8,24):
        _cyl(g,f'J01 diagonal brace {x}',(x,1,2.3),(x+8,1,10),.17,'steel','brace')
    _box(g,'J01 corrosion repair jacket',(16,1,8),(1.06,1.06,2.0),'rust','repair',f'{key}-pile')
    _box(g,'J01 anode bracket',(24,.46,10),(1.05,.18,.65),'anode','pile_anode',f'{key}-anode')
    _box(g,'J01 intake headwall',(34,1.0,12.7),(3.4,1.0,3.2),'concrete','headwall')
    _box(g,'J01 intake grille',(34,.42,12.7),(2.4,.18,2.0),'steel','grille',f'{key}-intake')
    _box(g,'J01 damaged concrete apron',(37,-1,15.7),(4,4,.6),'concrete','cracked',f'{key}-scour')
    for x in (10,23,35):
        _box(g,f'J01 rubber fender {x}',(x,-.6,1.3),(1.2,.8,3.1),'rubber','fender')
    targets=[
        _target(key,'pile','鋼樁：腐蝕與修補夾套',(16,-1.7,8),(16,.45,8),
                '環看修補夾套、螺栓與表面鏽蝕，保持纜線位於開闊側。',1.0),
        _target(key,'anode','港樁：陽極與固定架',(24,-1.8,10),(24,.32,10),
                '檢視陽極的表面耗損與固定架，勿將生物附著誤判為裂紋。',.7),
        _target(key,'intake','取水口：格柵與異物',(34,-2,12.7),(34,.27,12.7),
                '記錄格柵局部變形與掛網；本任務僅巡檢，不進入或拆除格柵。',1.2),
        _target(key,'scour','基腳：防沖刷板與接縫',(36.5,-4.5,14.7),(37,-1.4,15.38),
                '辨識基腳防護板裂縫與邊緣淘刷跡象，拍照保留周邊尺度。',1.4)]
    return dict(key=key,name='港口設施水下巡檢場',seabed_depth=16.,biome='harbor',
                visibility_m=10.,start_pos=[0,-7,3],spool_pos=[-3,-8,0],tether_length=85.,
                geometry=g,targets=targets,brief='巡檢碼頭鋼樁、陽極、取水格柵與防沖刷基腳；注意斜撐、低能見度與纜線路徑。')


def _repair():
    key='cooperative_cable_repair';g=[]
    for i in range(6):_cyl(g,f'R01 demonstration cable {i}',(2+i*2,0,11.55),(4+i*2,0,11.55),.12,'cable','cable')
    for x in (6,10):_box(g,f'R01 training support {x}',(x,0,11.85),(1.0,1.8,.3),'grout','sandbag')
    _box(g,'R01 equipment tray',(8,3,11.7),(2.4,1.5,.3),'steel','skid')
    _box(g,'R01 demonstration kit',(8,3,11.25),(1.5,.9,.6),'yellow','cabinet')
    target=_target(key,'maintenance','多人維修展示工作區',(8,-3,10.5),(8,0,11.55),'預設外護套磨耗；共同完成目視確認、展示保護套與復檢紀錄。',1.2)
    return dict(key=key,name='多人海纜維修展示場',seabed_depth=12.,biome='temperate',visibility_m=16.,
        start_pos=[5,-3.5,10.],spool_pos=[2,-6,0],tether_length=35.,geometry=g,targets=[target],
        repair=dict(point=[8.,0.,10.8],radius=6.),
        brief='巡檢、維護與復檢分工合作，為預設磨耗安裝展示保護套。這是抽象協作展示，不是實際施工程序。')

@lru_cache(maxsize=4)
def _manifest(key):
    builders=dict(zip(SITE_KEYS,(_cable,_pipeline,_port,_repair)))
    if key not in builders:
        return None
    site=builders[key]()
    site['reference_note']='依公開照片重建的虛構訓練場；尺寸與缺陷配置為遊戲估算，非現地數位孿生。'
    site['clear_points']=[site['start_pos']]+[t['point'] for t in site['targets']]+[t['target_point'] for t in site['targets']]
    site['model_version']=1
    return site


def site_manifest(key):
    """Return a caller-owned JSON-serializable manifest, or None for old scenes."""
    value=_manifest(key)
    return deepcopy(value) if value is not None else None


def site_obstacles(key):
    site=_manifest(key)
    if not site:
        return []
    obstacles=[]
    for item in site['geometry']:
        if item['type']=='cylinder':
            obstacles.append(Cylinder(item['name'],tuple(item['p0']),tuple(item['p1']),item['radius'],'inspection_structure'))
        else:
            obstacles.append(Box(item['name'],tuple(item['center']),tuple(v/2 for v in item['size']),0.,'inspection_structure'))
    return obstacles
