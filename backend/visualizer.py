"""
visualizer.py — Three.js Spacecraft Visualizer for KALPANA
Generates self-contained HTML pages with interactive 3D satellite models
driven by the LLM answer text. No Gemini/external AI needed.
"""

import re
import json
from dataclasses import dataclass, field
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class VisualizationResult:
    html: str
    viz_types: list[str]
    extracted_data: dict
    error: Optional[str] = None


@dataclass
class VisualizationRequest:
    query: str
    answer: str
    viz_type: str


@dataclass
class MissionData:
    name: str
    orbit_alt_km: Optional[float] = None
    longitude_deg: Optional[float] = None
    launch_mass_kg: Optional[float] = None
    dry_mass_kg: Optional[float] = None
    orbit_type: str = "GEO"
    payloads: list[str] = field(default_factory=list)
    imager_bands: int = 0
    imager_res_km: float = 1.0
    sounder_channels: int = 0
    has_drt: bool = False
    has_sasr: bool = False
    has_bss: bool = False
    mission_life_years: Optional[float] = None
    launch_vehicle: str = ""
    launch_date: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# ANSWER PARSER  — extracts structured data from LLM text
# ─────────────────────────────────────────────────────────────────────────────

MISSION_ALIASES = {
    "insat-3dr": "INSAT-3DR", "insat-3d": "INSAT-3D", "insat-3ds": "INSAT-3DS",
    "insat-3a": "INSAT-3A",   "kalpana-1": "KALPANA-1", "kalpana1": "KALPANA-1",
    "oceansat-2": "OCEANSAT-2", "oceansat-3": "OCEANSAT-3",
    "meghatropiques": "MeghaTropiques", "megha tropiques": "MeghaTropiques",
    "saral": "SARAL-AltiKa", "saral-altika": "SARAL-AltiKa",
    "scatsat-1": "SCATSAT-1", "scatsat": "SCATSAT-1",
}

def _canonical(name: str) -> str:
    return MISSION_ALIASES.get(name.lower().strip(), name.strip())

def _float(text: str, pattern: str) -> Optional[float]:
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None

def parse_answer(query: str, answer: str) -> dict[str, MissionData]:
    """
    Extract structured MissionData objects from the LLM answer string.
    Returns dict keyed by canonical mission name.
    """
    text = answer + "\n" + query
    missions: dict[str, MissionData] = {}

    # ── Detect mentioned missions ──────────────────────────────────────────
    all_patterns = [
        r'\b(INSAT[-\s]?3D[RS]?)\b',
        r'\b(INSAT[-\s]?3A)\b',
        r'\b(KALPANA[-\s]?1)\b',
        r'\b(OCEANSAT[-\s]?[23])\b',
        r'\b(MeghaTropiques)\b',
        r'\b(SARAL[-\s]?AltiKa)\b',
        r'\b(SCATSAT[-\s]?1)\b',
    ]
    found_names = []
    for pat in all_patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            cn = _canonical(m.group(0))
            if cn not in found_names:
                found_names.append(cn)

    if not found_names:
        # Fall back: use anything that looks like a mission name
        for m in re.finditer(r'\b([A-Z][A-Z0-9\-]{2,}\d)\b', text):
            cn = _canonical(m.group(0))
            if cn not in found_names:
                found_names.append(cn)

    if not found_names:
        found_names = ["ISRO Satellite"]

    for name in found_names:
        md = MissionData(name=name)

        # ── Numeric extractions (broad, works across all missions) ─────────
        alt = _float(text, r'(\d[\d,]+)\s*km.*?orbit|orbit.*?(\d[\d,]+)\s*km')
        if not alt:
            alt = _float(text, r'35[,\s]?786')
        md.orbit_alt_km = alt or 35786.0

        lon = _float(text, r'(\d{1,3})[°\s]*[Ee](?:ast)?')
        md.longitude_deg = lon

        lm = _float(text, r'launch\s+mass[^\d]*(\d[\d,]+)\s*kg')
        if not lm:
            lm = _float(text, r'(\d[\d,]+)\s*kg.*?launch|lift.*?(\d[\d,]+)\s*kg')
        md.launch_mass_kg = lm

        dm = _float(text, r'dry\s+mass[^\d]*(\d[\d,]+)\s*kg')
        md.dry_mass_kg = dm

        # Imager bands
        ib = _float(text, r'(\d+)[- ]?channel\s+[Ii]mager|[Ii]mager.*?(\d+)\s+band')
        md.imager_bands = int(ib) if ib else 6

        # Sounder channels
        sc = _float(text, r'(\d+)[- ]?channel\s+[Ss]ounder|[Ss]ounder.*?(\d+)\s+channel')
        md.sounder_channels = int(sc) if sc else 0

        tl = text.lower()
        md.has_drt  = bool(re.search(r'\bdrt\b|data relay transponder', tl))
        md.has_sasr = bool(re.search(r'\bsas\b|search.{0,10}rescue|sarsat', tl))
        md.has_bss  = bool(re.search(r'\bbss\b|broadcast satellite', tl))

        # Payloads
        plist = []
        if md.imager_bands:   plist.append(f"{md.imager_bands}-channel Imager")
        if md.sounder_channels: plist.append(f"{md.sounder_channels}-channel Sounder")
        if md.has_drt:        plist.append("DRT")
        if md.has_sasr:       plist.append("SAS&R")
        if md.has_bss:        plist.append("S-band BSS")
        if not plist:
            # generic fallback from text
            for kw in ["Imager", "Sounder", "Transponder", "Scatterometer", "Altimeter", "Radiometer"]:
                if kw.lower() in tl:
                    plist.append(kw)
        md.payloads = plist or ["Payload"]

        # Mission life
        ml = _float(text, r'mission\s+life[^\d]*(\d+(?:\.\d+)?)\s*year')
        md.mission_life_years = ml

        # Orbit type
        if re.search(r'\bleo\b|sun.sync|polar orbit', tl):
            md.orbit_type = "LEO"
            md.orbit_alt_km = md.orbit_alt_km if md.orbit_alt_km and md.orbit_alt_km < 2000 else 720.0
        else:
            md.orbit_type = "GEO"

        # Launch vehicle & date
        lv = re.search(r'\b(GSLV[-\s]?[A-Z0-9]+|PSLV[-\s]?C?\d+)\b', text, re.IGNORECASE)
        md.launch_vehicle = lv.group(0) if lv else ""
        ld = re.search(r'\b(\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{4})\b', text)
        md.launch_date = ld.group(0) if ld else ""

        missions[name] = md

    return missions


# ─────────────────────────────────────────────────────────────────────────────
# VIZ TYPE SELECTOR  — decides which buttons to show per answer
# ─────────────────────────────────────────────────────────────────────────────

def get_available_viz_types(query: str, answer: str) -> list[dict]:
    """
    Returns list of {type, label} dicts to show as viz buttons.
    Always includes 3d_orbit. Adds others based on content.
    """
    text = (query + " " + answer).lower()
    buttons = []

    # 3D spacecraft view — always shown
    buttons.append({"type": "3d_orbit", "label": "3D Spacecraft View"})

    # Payload dashboard — if specs are discussed
    if any(k in text for k in ["band", "channel", "resolution", "ifov", "payload", "imager", "sounder", "mhz", "mbit"]):
        buttons.append({"type": "payload_specs", "label": "Payload Dashboard"})

    # Comparison chart — if multiple missions
    mission_count = len(re.findall(
        r'\b(INSAT|OCEANSAT|KALPANA|SARAL|SCATSAT|Megha)\b', text, re.IGNORECASE
    ))
    if mission_count >= 2:
        buttons.append({"type": "comparison_chart", "label": "Comparison Chart"})

    return buttons


# ─────────────────────────────────────────────────────────────────────────────
# HTML GENERATORS
# ─────────────────────────────────────────────────────────────────────────────

def _part_data_js(missions: dict[str, MissionData]) -> str:
    """Serialize parsed mission data to JS for injection into HTML."""
    out = []
    for name, md in missions.items():
        out.append({
            "name": md.name,
            "orbit_alt_km": md.orbit_alt_km,
            "longitude_deg": md.longitude_deg,
            "launch_mass_kg": md.launch_mass_kg,
            "dry_mass_kg": md.dry_mass_kg,
            "orbit_type": md.orbit_type,
            "payloads": md.payloads,
            "imager_bands": md.imager_bands,
            "sounder_channels": md.sounder_channels,
            "has_drt": md.has_drt,
            "has_sasr": md.has_sasr,
            "has_bss": md.has_bss,
            "mission_life_years": md.mission_life_years,
            "launch_vehicle": md.launch_vehicle,
            "launch_date": md.launch_date,
        })
    return json.dumps(out, indent=2)


# ── 1. 3D ORBIT / SPACECRAFT VIEW ────────────────────────────────────────────

def generate_3d_orbit_html(query: str, answer: str, missions: dict[str, MissionData]) -> str:

    mission_list = list(missions.values())
    primary = mission_list[0] if mission_list else MissionData(name="ISRO Satellite")
    data_js = _part_data_js(missions)
    answer_js = json.dumps(answer[:2000])

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>KALPANA — 3D Spacecraft · {primary.name}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#020810;font-family:'IBM Plex Mono',monospace;overflow:hidden;color:#d4e4f0}}
#stage{{position:relative;width:100vw;height:100vh}}
canvas{{display:block;width:100%;height:100%}}
#hud{{position:absolute;top:12px;left:14px;pointer-events:none;display:flex;flex-direction:column;gap:4px}}
#sat-id{{color:#00d2ff;font-size:11px;letter-spacing:.14em;text-transform:uppercase;font-family:'Orbitron',monospace}}
#sat-sub{{color:#1a4a6a;font-size:9px;letter-spacing:.08em}}
#controls{{position:absolute;bottom:10px;left:14px;pointer-events:none;display:flex;flex-direction:column;gap:2px}}
.ctl{{color:#0e3a58;font-size:9px;letter-spacing:.06em}}
#legend{{position:absolute;top:12px;right:12px;display:flex;flex-direction:column;gap:4px}}
.leg{{display:flex;align-items:center;gap:6px;font-size:9px;color:#0e4060;letter-spacing:.06em;cursor:pointer;padding:3px 8px;border-radius:4px;transition:all .15s}}
.leg:hover{{background:rgba(0,210,255,.08);color:#00d2ff}}
.ldot{{width:8px;height:8px;border-radius:50%;flex-shrink:0}}
#tooltip{{position:absolute;pointer-events:none;background:rgba(2,8,20,.95);border:0.5px solid #0a3860;border-radius:8px;padding:9px 13px;max-width:220px;display:none;z-index:10}}
#tt-l{{color:#00d2ff;font-size:11px;font-weight:bold;margin-bottom:4px}}
#tt-b{{color:#1e6888;font-size:10px;line-height:1.65}}
#answer-box{{position:absolute;bottom:12px;left:50%;transform:translateX(-50%);width:min(700px,90vw);background:rgba(2,8,20,.92);border:0.5px solid rgba(0,210,255,.2);border-radius:10px;padding:12px 16px;font-size:10px;color:#3a7090;line-height:1.75;max-height:110px;overflow-y:auto;letter-spacing:.02em;white-space:pre-wrap}}
#answer-box b{{color:#00d2ff}}
#view-btns{{position:absolute;bottom:10px;right:12px;display:flex;flex-direction:column;gap:4px}}
.vbtn{{background:rgba(2,8,20,.88);border:0.5px solid #0a2a48;color:#1e6888;font-size:9px;padding:5px 10px;border-radius:5px;cursor:pointer;letter-spacing:.06em;font-family:'IBM Plex Mono',monospace}}
.vbtn:hover,.vbtn.active{{border-color:#00d2ff;color:#00d2ff}}
</style>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&family=IBM+Plex+Mono:wght@300;400;500&display=swap" rel="stylesheet"/>
</head>
<body>
<div id="stage">
  <canvas id="c"></canvas>
  <div id="hud">
    <div id="sat-id">{primary.name} · MOSDAC</div>
    <div id="sat-sub">GEO · {int(primary.orbit_alt_km or 35786):,} KM{f" · {primary.longitude_deg}° E" if primary.longitude_deg else ""}{f" · {int(primary.launch_mass_kg):,} KG" if primary.launch_mass_kg else ""}</div>
  </div>
  <div id="controls">
    <div class="ctl">drag — rotate</div>
    <div class="ctl">scroll — zoom</div>
    <div class="ctl">hover — inspect</div>
  </div>
  <div id="legend">
    <div class="leg" data-key="imager"><span class="ldot" style="background:#1a7bc0"></span>imager</div>
    <div class="leg" data-key="sounder"><span class="ldot" style="background:#c07010"></span>sounder</div>
    <div class="leg" data-key="cooler"><span class="ldot" style="background:#7aaabb"></span>radiant cooler</div>
    <div class="leg" data-key="drt"><span class="ldot" style="background:#208050"></span>DRT</div>
    <div class="leg" data-key="sasr"><span class="ldot" style="background:#20a060"></span>SAS&amp;R</div>
    <div class="leg" data-key="bss"><span class="ldot" style="background:#7030b0"></span>S-band BSS</div>
    <div class="leg" data-key="panel"><span class="ldot" style="background:#112244"></span>solar arrays</div>
    <div class="leg" data-key="star"><span class="ldot" style="background:#2a88aa"></span>star trackers</div>
  </div>
  <div id="tooltip"><div id="tt-l"></div><div id="tt-b"></div></div>
  <div id="answer-box"></div>
  <div id="view-btns">
    <button class="vbtn active" data-view="front">earth face</button>
    <button class="vbtn" data-view="top">top deck</button>
    <button class="vbtn" data-view="panel">solar array</button>
    <button class="vbtn" data-view="full">full view</button>
  </div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
const MISSIONS = {data_js};
const ANSWER   = {answer_js};

window.addEventListener('load', () => {{
const cv=document.getElementById('c');
const stage=document.getElementById('stage');
const ttEl=document.getElementById('tooltip');
const ttL=document.getElementById('tt-l');
const ttB=document.getElementById('tt-b');
const ansBox=document.getElementById('answer-box');
const satId=document.getElementById('sat-id');
const satSub=document.getElementById('sat-sub');

const W=()=>stage.clientWidth,H=()=>stage.clientHeight;
const PI=Math.PI;

const renderer=new THREE.WebGLRenderer({{canvas:cv,antialias:true}});
renderer.setPixelRatio(Math.min(devicePixelRatio,2));
renderer.setClearColor(0x020810,1);
renderer.shadowMap.enabled=true;

const scene=new THREE.Scene();
const cam=new THREE.PerspectiveCamera(42,W()/Math.max(1,H()),.1,4000);

new ResizeObserver(()=>{{renderer.setSize(W(),H(),false);cam.aspect=W()/Math.max(1,H());cam.updateProjectionMatrix();}}).observe(stage);
renderer.setSize(W(),H(),false);

// Lights
scene.add(new THREE.AmbientLight(0x0a1828,5));
const kl=new THREE.DirectionalLight(0xffe8a0,3.5);kl.position.set(300,200,-100);kl.castShadow=true;scene.add(kl);
const fillLight = new THREE.DirectionalLight(0x2255aa, 2);
fillLight.position.set(-200, 50, 300);
scene.add(fillLight);
// Stars
const sv=new Float32Array(12000);for(let i=0;i<12000;i++) sv[i]=(Math.random()-.5)*3000;
const sbg=new THREE.BufferGeometry();sbg.setAttribute('position',new THREE.BufferAttribute(sv,3));
scene.add(new THREE.Points(sbg,new THREE.PointsMaterial({{color:0xffffff,size:.45,sizeAttenuation:true,transparent:true,opacity:.7}})));

// Materials
const M={{
  struct:  new THREE.MeshStandardMaterial({{color:0x3a4a5a,metalness:.75,roughness:.35}}),
  panel:   new THREE.MeshStandardMaterial({{color:0x0d1e38,metalness:.4,roughness:.5,emissive:0x000408}}),
  pgrid:   new THREE.MeshStandardMaterial({{color:0x1a3060,metalness:.3,roughness:.6}}),
  imager:  new THREE.MeshStandardMaterial({{color:0x1a6bb0,metalness:.6,roughness:.3}}),
  lens:    new THREE.MeshStandardMaterial({{color:0x080e18,metalness:.95,roughness:.05}}),
  sounder: new THREE.MeshStandardMaterial({{color:0xb06010,metalness:.6,roughness:.3}}),
  cooler:  new THREE.MeshStandardMaterial({{color:0x6a9aaa,metalness:.65,roughness:.3}}),
  drt:     new THREE.MeshStandardMaterial({{color:0x1a7040,metalness:.5,roughness:.4,side:THREE.DoubleSide}}),
  sasr:    new THREE.MeshStandardMaterial({{color:0x10a050,metalness:.5,roughness:.35}}),
  bss:     new THREE.MeshStandardMaterial({{color:0x6020a0,metalness:.5,roughness:.4}}),
  thruster:new THREE.MeshStandardMaterial({{color:0x222c38,metalness:.9,roughness:.15}}),
  nozzle:  new THREE.MeshStandardMaterial({{color:0x889a9a,metalness:.9,roughness:.2}}),
  white:   new THREE.MeshStandardMaterial({{color:0xdde8ee,metalness:.5,roughness:.4}}),
  gold:    new THREE.MeshStandardMaterial({{color:0xd4960a,metalness:.8,roughness:.25}}),
  dark:    new THREE.MeshStandardMaterial({{color:0x1a2430,metalness:.7,roughness:.4}}),
  star:    new THREE.MeshStandardMaterial({{color:0x2a7888,metalness:.7,roughness:.3}}),
}};

const SAT=new THREE.Group();scene.add(SAT);
const clickables=[],partGroups={{}};
function reg(mesh,key,label,desc){{mesh.userData={{label,desc,key}};clickables.push(mesh);(partGroups[key]||(partGroups[key]=[])).push(mesh);return mesh;}}
function a(m){{SAT.add(m);return m;}}

// ── BUS ──
const bus=a(reg(new THREE.Mesh(new THREE.BoxGeometry(16,20,14),M.struct.clone()),'bus','Spacecraft bus','I-2K bus · 3-axis stabilised · momentum-biased · star trackers'));bus.castShadow=true;
for(let i=-3;i<=3;i++){{const s=a(new THREE.Mesh(new THREE.BoxGeometry(16.1,.8,14.1),M.gold.clone()));s.position.y=i*2.4;}}
[[-1,-1],[-1,1],[1,-1],[1,1]].forEach(([sx,sz])=>{{const c=a(new THREE.Mesh(new THREE.BoxGeometry(1.2,20,1.2),M.white.clone()));c.position.set(sx*8.1,0,sz*7.1);}});
[true,false].forEach(top=>{{const p=a(new THREE.Mesh(new THREE.BoxGeometry(15.4,9,.2+14),M.dark.clone()));p.position.y=top?5:-5;}});

// ── SOLAR ARRAYS ──
[-1,1].forEach((s,si)=>{{
  a(new THREE.Mesh(new THREE.BoxGeometry(6,.8,1),M.struct.clone())).position.set(s*11,4,0);
  const panel=a(reg(new THREE.Mesh(new THREE.BoxGeometry(46,.5,13),M.panel.clone()),'panel','Solar array '+(si===0?'A':'B'),'GaAs multi-junction cells · biannual yaw via micro-stepping SADA'));
  panel.position.set(s*35,4,0);panel.castShadow=true;
  for(let r=-2;r<=2;r++){{const rl=a(new THREE.Mesh(new THREE.BoxGeometry(46,.6,.3),M.pgrid.clone()));rl.position.set(s*35,4,r*2.5);}}
  for(let c=-5;c<=5;c++){{const cl=a(new THREE.Mesh(new THREE.BoxGeometry(.3,.6,13),M.pgrid.clone()));cl.position.set(s*35+c*3.8,4,0);}}
  const fr=a(new THREE.Mesh(new THREE.BoxGeometry(47,.8,14),M.white.clone()));fr.position.set(s*35,4.5,0);
  // secondary segment
  const p2=a(reg(new THREE.Mesh(new THREE.BoxGeometry(28,.5,9),M.panel.clone()),'panel','Solar array seg-2','Secondary panel segment'));
  p2.position.set(s*62,0,0);
  a(new THREE.Mesh(new THREE.BoxGeometry(.6,3,1),M.struct.clone())).position.set(s*49,2,0);
}});

// ── EARTH DECK ──
// Imager
const ih=a(reg(new THREE.Mesh(new THREE.BoxGeometry(9,6,9),M.imager.clone()),'imager','6-channel Imager','VIS·SWIR·MWIR·WV·TIR-1·TIR-2 · aperture 310mm · 1km VIS res'));ih.position.set(-3,-13,0);
a(new THREE.Mesh(new THREE.CylinderGeometry(3.8,4.2,4,16),M.dark.clone())).position.set(-3,-16.5,0);
a(reg(new THREE.Mesh(new THREE.CylinderGeometry(2.8,2.8,.4,32),M.lens.clone()),'imager','Imager aperture','310mm telescope · 28µrad IFOV (VIS/SWIR)')).position.set(-3,-18.8,0);
const sm=a(reg(new THREE.Mesh(new THREE.BoxGeometry(4,.3,4),M.white.clone()),'imager','Scan mirror','Linear E-W scan · 8µR step · 200°/s rate'));sm.position.set(-3,-15,.5);sm.rotation.x=.35;

// Sounder
a(reg(new THREE.Mesh(new THREE.BoxGeometry(8,5.5,8),M.sounder.clone()),'sounder','18-channel IR Sounder','18 IR + 1 VIS · 280µrad IFOV · 10km ground res · 160min full frame')).position.set(5,-12.75,0);
a(new THREE.Mesh(new THREE.CylinderGeometry(2.6,2.9,3.5,16),M.sounder.clone())).position.set(5,-16.2,0);
a(reg(new THREE.Mesh(new THREE.CylinderGeometry(2.3,2.3,.4,32),M.lens.clone()),'sounder','Sounder aperture','310mm · filter wheel · 13-bit quantisation')).position.set(5,-18,0);
a(reg(new THREE.Mesh(new THREE.CylinderGeometry(1.8,1.8,.5,8),M.gold.clone()),'sounder','Filter wheel','19-channel · maintains 213K')).position.set(5,-15.5,3.5);

// Radiant cooler
a(reg(new THREE.Mesh(new THREE.BoxGeometry(7,2.5,6),M.cooler.clone()),'cooler','Passive radiant cooler','95K (BOL) / 100K (EOL) · sounder filter wheel at 213K')).position.set(1,-11.25,-10);
for(let f=0;f<5;f++){{const fi=a(new THREE.Mesh(new THREE.BoxGeometry(7,.15,1.5),M.white.clone()));fi.position.set(1,-11.25,-11.2+f*.4);}}

// ── TOP DECK ──
// DRT dish
a(new THREE.Mesh(new THREE.CylinderGeometry(1,1.3,3,8),M.struct.clone())).position.set(-4,11.5,-2);
const dsh=a(reg(new THREE.Mesh(new THREE.SphereGeometry(4.8,24,12,0,PI*2,0,PI/2.1),M.drt.clone()),'drt','Data Relay Transponder','Relay met data from 1000+ DCP stations · India & Indian Ocean'));dsh.rotation.x=PI;dsh.position.set(-4,14.5,-2);
a(new THREE.Mesh(new THREE.CylinderGeometry(.5,.7,2.5,8),M.white.clone())).position.set(-4,18,-2);

// SAS&R
a(reg(new THREE.Mesh(new THREE.BoxGeometry(3.5,1.5,3.5),M.sasr.clone()),'sasr','SAS&R transponder','COSPAR-SARSAT · South Asian & Indian Ocean distress')).position.set(-6,11,4);
const sm2=a(new THREE.Mesh(new THREE.CylinderGeometry(.4,.4,5,8),M.sasr.clone()));sm2.position.set(-6,14.5,4);
a(new THREE.Mesh(new THREE.SphereGeometry(.7,8,8),M.white.clone())).position.set(-6,17.3,4);

// BSS
a(reg(new THREE.Mesh(new THREE.BoxGeometry(5,3,4),M.bss.clone()),'bss','S-band BSS','2×S-band transponders · ~70kg comms payload')).position.set(5,11.5,2);
[[-1,0,0],[1,0,0],[0,.4,.3]].forEach(([rx,ry,rz])=>{{const ba=a(new THREE.Mesh(new THREE.CylinderGeometry(.3,.3,6,6),M.bss.clone()));ba.position.set(5+rx,15.5,2+rz);ba.rotation.z=rx*.25;}});

// IBMU + thermal louvers
a(reg(new THREE.Mesh(new THREE.BoxGeometry(3,2,3),M.white.clone()),'bus','Integrated bus management unit','Manages all bus systems · thermal management · concurrent Imager+Sounder ops')).position.set(0,-2,7.5);
for(let i=-3;i<=3;i++){{const l=a(new THREE.Mesh(new THREE.BoxGeometry(10,.15,1.2),new THREE.MeshStandardMaterial({{color:0x889aaa,metalness:.7,roughness:.3}})));l.position.set(0,-2,7.5+i*.5);}}

// Star trackers
[[-7,2,7.5],[7,2,7.5],[-7,-2,-7.5],[7,-2,-7.5]].forEach(([x,y,z],i)=>{{
  a(reg(new THREE.Mesh(new THREE.BoxGeometry(2,2,2),M.star.clone()),'star','Star tracker '+(i+1),'Precise attitude · enables 1km imaging accuracy')).position.set(x,y,z);
  a(new THREE.Mesh(new THREE.BoxGeometry(1.2,1.2,.5),M.lens.clone())).position.set(x,y,z+(z>0?.9:-.9));
}});

// Thrusters
[[-5,-9,-4],[-5,-9,4],[5,-9,-4],[5,-9,4],[-9,0,-4],[-9,0,4],[9,0,-4],[9,0,4]].forEach(([x,y,z])=>{{
  a(new THREE.Mesh(new THREE.CylinderGeometry(.7,1.1,2,8),M.thruster.clone())).position.set(x,y,z);
  a(new THREE.Mesh(new THREE.CylinderGeometry(.9,1.3,1,8),M.nozzle.clone())).position.set(x,y-1,z);
}});

// ── VIEWS ──
const views={{
  full:  {{pos:[0,30,170],look:[0,0,0]}},
  front: {{pos:[0,-18,90], look:[0,-12,0]}},
  top:   {{pos:[0,95,35],  look:[0,10,0]}},
  panel: {{pos:[100,8,35], look:[20,4,0]}},
}};
let tPos=[...views.front.pos],tLook=[...views.front.look];
let cPos=[...views.front.pos],cLook=[...views.front.look];

document.querySelectorAll('.vbtn').forEach(b=>b.addEventListener('click',()=>{{
  document.querySelectorAll('.vbtn').forEach(x=>x.classList.remove('active'));b.classList.add('active');
  const v=views[b.dataset.view];tPos=[...v.pos];tLook=[...v.look];manTheta=null;
}}));

// Legend click → flash + zoom
document.querySelectorAll('.leg').forEach(l=>l.addEventListener('click',()=>{{
  const key=l.dataset.key;
  const grp=partGroups[key]||[];
  grp.forEach(m=>{{if(m.material){{m.material.emissive=new THREE.Color(.08,.38,.72);m.material.emissiveIntensity=.8;}}}}); 
  setTimeout(()=>grp.forEach(m=>{{if(m.material){{m.material.emissive=new THREE.Color(0,0,0);m.material.emissiveIntensity=0;}}}}),2500);
  if(grp.length){{let cx=0,cy=0,cz=0;grp.forEach(m=>{{cx+=m.position.x;cy+=m.position.y;cz+=m.position.z;}});cx/=grp.length;cy/=grp.length;cz/=grp.length;tLook=[cx,cy,cz];tPos=[cx+50,cy+30,cz+80];manTheta=null;}}
}}));

// Orbit cam
let isDrag=false,lx=0,ly=0,manTheta=null,manPhi=null,manR=null;
stage.addEventListener('mousedown',e=>{{isDrag=true;lx=e.clientX;ly=e.clientY;const dx=cPos[0]-cLook[0],dy=cPos[1]-cLook[1],dz=cPos[2]-cLook[2];manR=Math.sqrt(dx*dx+dy*dy+dz*dz);manTheta=Math.atan2(dx,dz);manPhi=Math.asin(dy/manR);}});
window.addEventListener('mouseup',()=>isDrag=false);
stage.addEventListener('mousemove',e=>{{if(!isDrag||manTheta===null)return;manTheta+=(e.clientX-lx)*.006;manPhi=Math.max(-.5,Math.min(1.2,manPhi+(e.clientY-ly)*.004));lx=e.clientX;ly=e.clientY;const lk=tLook;tPos[0]=lk[0]+manR*Math.sin(manTheta)*Math.cos(manPhi);tPos[1]=lk[1]+manR*Math.sin(manPhi);tPos[2]=lk[2]+manR*Math.cos(manTheta)*Math.cos(manPhi);}});
stage.addEventListener('wheel',e=>{{const sc=1+e.deltaY*.002;tPos=tPos.map((v,i)=>tLook[i]+(v-tLook[i])*sc);e.preventDefault();}},{{passive:false}});

// Tooltip raycaster
const ray=new THREE.Raycaster(),mouse=new THREE.Vector2();
stage.addEventListener('mousemove',e=>{{
  if(isDrag)return;
  const r=stage.getBoundingClientRect();mouse.x=((e.clientX-r.left)/r.width)*2-1;mouse.y=-((e.clientY-r.top)/r.height)*2+1;
  ray.setFromCamera(mouse,cam);
  const hits=ray.intersectObjects(clickables,false);
  if(hits.length){{const d=hits[0].object.userData;ttL.textContent=d.label;ttB.textContent=d.desc;ttEl.style.display='block';ttEl.style.left=(e.clientX-r.left+14)+'px';ttEl.style.top=(e.clientY-r.top-10)+'px';}}
  else ttEl.style.display='none';
}});

// Flash payloads from answer
const al=ANSWER.toLowerCase();
const flash=(key,col)=>{{const g=partGroups[key]||[];g.forEach(m=>{{if(m.material){{m.material.emissive=new THREE.Color(...col);m.material.emissiveIntensity=.7;}}}}); setTimeout(()=>g.forEach(m=>{{if(m.material){{m.material.emissive=new THREE.Color(0,0,0);m.material.emissiveIntensity=0;}}}}),4500);}};
if(al.includes('imager')||al.includes('vis')||al.includes('tir')||al.includes('swir'))flash('imager',[.1,.4,.9]);
if(al.includes('sounder')||al.includes('profile')||al.includes('humidity'))flash('sounder',[.8,.4,.05]);
if(al.includes('cooler')||al.includes('95k')||al.includes('detector'))flash('cooler',[.3,.7,.8]);
if(al.includes('drt')||al.includes('relay'))flash('drt',[.1,.7,.4]);
if(al.includes('search')||al.includes('rescue'))flash('sasr',[.1,.8,.5]);
if(al.includes('bss')||al.includes('broadcast'))flash('bss',[.5,.1,.8]);
if(al.includes('solar')||al.includes('sada'))flash('panel',[.1,.35,.85]);
if(al.includes('star tracker')||al.includes('attitude'))flash('star',[.1,.6,.7]);

// Render answer
const kw=['Imager','Sounder','DRT','SAS&R','BSS','INSAT','GSLV','PSLV','orbit','GEO','LEO','transponder','radiant cooler','star tracker','SWIR','MWIR','TIR','IFOV','SADA'];
let html=ANSWER;
kw.forEach(k=>{{html=html.replace(new RegExp('\\\\b('+k.replace(/[&]/g,'\\\\&')+')\\\\b','g'),'<b style="color:#00d2ff">$1</b>');}});
ansBox.innerHTML=html;

// Auto-rotate
let autoTheta=.3,autoOn=true,idleT=null;
stage.addEventListener('mousedown',()=>{{autoOn=false;clearTimeout(idleT);}});
window.addEventListener('mouseup',()=>{{idleT=setTimeout(()=>autoOn=true,4500);}});

function lerp(a,b,t){{return a+(b-a)*t}}
function lerpA(a,b,t){{return a.map((v,i)=>lerp(v,b[i],t))}}

const lv=new THREE.Vector3();
let T=0;
(function loop(){{
  requestAnimationFrame(loop);T+=.016;
  cPos=lerpA(cPos,tPos,.045);cLook=lerpA(cLook,tLook,.045);
  if(autoOn&&manTheta===null){{autoTheta+=.0006;const r=Math.sqrt(cPos.reduce((s,v,i)=>s+Math.pow(v-cLook[i], 2),0))||90;const phi=.18;tPos[0]=cLook[0]+r*Math.sin(autoTheta)*Math.cos(phi);tPos[1]=cLook[1]+r*Math.sin(phi);tPos[2]=cLook[2]+r*Math.cos(autoTheta)*Math.cos(phi);}}
  cam.position.set(...cPos);lv.set(...cLook);cam.lookAt(lv);
  renderer.render(scene,cam);
}})();

}});
</script>
</body>
</html>"""


# ── 2. PAYLOAD SPECS DASHBOARD ────────────────────────────────────────────────

def generate_payload_specs_html(query: str, answer: str, missions: dict[str, MissionData]) -> str:
    mission_list = list(missions.values())
    primary = mission_list[0] if mission_list else MissionData(name="ISRO Satellite")

    # Extract spec table entries from answer
    spec_rows = []
    patterns = [
        (r'(\d+(?:\.\d+)?)\s*km.*?resol|resol.*?(\d+(?:\.\d+)?)\s*km', "Resolution"),
        (r'IFOV[^\d]*(\d+(?:\.\d+)?)\s*µrad', "IFOV (µrad)"),
        (r'(\d+(?:\.\d+)?)\s*Mbit', "Downlink (Mbit/s)"),
        (r'aperture[^\d]*(\d+)\s*mm', "Aperture (mm)"),
        (r'(\d+)\s*channel', "Channels"),
        (r'(\d+(?:\.\d+)?)\s*K.*?(?:detector|BOL|EOL)', "Detector temp (K)"),
        (r'(\d[\d,]+)\s*kg.*?(?:launch|mass)', "Launch mass (kg)"),
        (r'mission\s+life[^\d]*(\d+)\s*year', "Mission life (yr)"),
    ]
    for pat, label in patterns:
        m = re.search(pat, answer, re.IGNORECASE)
        if m:
            val = next((g for g in m.groups() if g), "—")
            spec_rows.append((label, val))

    rows_html = "".join(
        f'<tr><td class="sk">{label}</td><td class="sv">{val}</td></tr>'
        for label, val in spec_rows
    ) if spec_rows else '<tr><td class="sk" colspan="2" style="color:#1a4a6a">No numeric specs parsed — see answer below</td></tr>'

    payload_pills = "".join(
        f'<span class="ppill">{p}</span>' for p in primary.payloads
    ) if primary.payloads else '<span class="ppill">Payload data</span>'

    answer_escaped = answer.replace("<", "&lt;").replace(">", "&gt;")[:3000]

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>KALPANA — Payload Dashboard · {primary.name}</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&family=IBM+Plex+Mono:wght@300;400;500&display=swap" rel="stylesheet"/>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#020810;color:#d4e4f0;font-family:'IBM Plex Mono',monospace;padding:28px;min-height:100vh}}
.title{{font-family:'Orbitron',monospace;font-size:13px;letter-spacing:.2em;color:#00d2ff;margin-bottom:20px;text-transform:uppercase}}
.title span{{color:#3a5570}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:22px}}
.card{{background:rgba(0,210,255,.025);border:0.5px solid rgba(0,210,255,.15);border-radius:10px;padding:18px 20px}}
.card-title{{font-family:'Orbitron',monospace;font-size:9px;letter-spacing:.18em;color:#3a5570;text-transform:uppercase;margin-bottom:14px}}
.spec-table{{width:100%;border-collapse:collapse}}
.sk{{font-size:10px;color:#2a6a90;padding:5px 0;letter-spacing:.05em;border-bottom:0.5px solid rgba(0,210,255,.06)}}
.sv{{font-size:11px;color:#00d2ff;padding:5px 0;text-align:right;letter-spacing:.04em;border-bottom:0.5px solid rgba(0,210,255,.06)}}
.payloads{{display:flex;flex-wrap:wrap;gap:7px;margin-top:8px}}
.ppill{{padding:4px 12px;background:rgba(0,210,255,.06);border:0.5px solid rgba(0,210,255,.2);border-radius:20px;font-size:10px;color:#00d2ff;letter-spacing:.06em}}
.meta-row{{display:flex;gap:12px;margin-bottom:22px;flex-wrap:wrap}}
.meta-chip{{padding:5px 14px;background:rgba(0,210,255,.03);border:0.5px solid rgba(0,210,255,.12);border-radius:5px;font-size:9px;color:#2a6a90;letter-spacing:.1em}}
.meta-chip b{{color:#00d2ff}}
.answer-box{{background:rgba(2,8,20,.7);border:0.5px solid rgba(0,210,255,.12);border-radius:10px;padding:16px 18px;font-size:11px;color:#2a5a78;line-height:1.8;letter-spacing:.02em;white-space:pre-wrap;max-height:280px;overflow-y:auto}}
.answer-box b{{color:#00d2ff}}
</style>
</head>
<body>
<div class="title">{primary.name} · <span>PAYLOAD DASHBOARD · MOSDAC</span></div>
<div class="meta-row">
  <div class="meta-chip">ORBIT <b>{primary.orbit_type}</b></div>
  {"<div class='meta-chip'>ALT <b>"+str(int(primary.orbit_alt_km or 35786))+' KM</b></div>' if primary.orbit_alt_km else ""}
  {"<div class='meta-chip'>LON <b>"+str(primary.longitude_deg)+"° E</b></div>" if primary.longitude_deg else ""}
  {"<div class='meta-chip'>LAUNCH MASS <b>"+str(int(primary.launch_mass_kg))+" KG</b></div>" if primary.launch_mass_kg else ""}
  {"<div class='meta-chip'>MISSION LIFE <b>"+str(primary.mission_life_years)+" YR</b></div>" if primary.mission_life_years else ""}
</div>
<div class="grid">
  <div class="card">
    <div class="card-title">Key specifications</div>
    <table class="spec-table">{rows_html}</table>
  </div>
  <div class="card">
    <div class="card-title">Payloads on board</div>
    <div class="payloads">{payload_pills}</div>
    <br/>
    {"<div class='meta-chip' style='margin-top:8px'>LAUNCH VEHICLE <b>"+primary.launch_vehicle+"</b></div>" if primary.launch_vehicle else ""}
    {"<div class='meta-chip' style='margin-top:8px'>LAUNCH DATE <b>"+primary.launch_date+"</b></div>" if primary.launch_date else ""}
  </div>
</div>
<div class="answer-box">{answer_escaped}</div>
</body>
</html>"""


# ── 3. COMPARISON CHART ───────────────────────────────────────────────────────

def generate_comparison_html(query: str, answer: str, missions: dict[str, MissionData]) -> str:
    mission_list = list(missions.values())[:4]  # max 4 missions
    names_js  = json.dumps([m.name for m in mission_list])
    alts_js   = json.dumps([m.orbit_alt_km or 0 for m in mission_list])
    masses_js = json.dumps([m.launch_mass_kg or 0 for m in mission_list])
    bands_js  = json.dumps([m.imager_bands or 0 for m in mission_list])
    sound_js  = json.dumps([m.sounder_channels or 0 for m in mission_list])
    answer_escaped = answer.replace("<", "&lt;").replace(">", "&gt;")[:2000]

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>KALPANA — Comparison Chart</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&family=IBM+Plex+Mono:wght@300;400;500&display=swap" rel="stylesheet"/>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#020810;color:#d4e4f0;font-family:'IBM Plex Mono',monospace;padding:22px;min-height:100vh}}
.title{{font-family:'Orbitron',monospace;font-size:12px;letter-spacing:.2em;color:#00d2ff;margin-bottom:18px;text-transform:uppercase}}
.charts{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:18px}}
.chart-card{{background:rgba(0,210,255,.018);border:0.5px solid rgba(0,210,255,.12);border-radius:10px;padding:16px}}
.chart-lbl{{font-size:9px;letter-spacing:.15em;color:#2a6070;text-transform:uppercase;margin-bottom:10px}}
canvas{{max-height:180px}}
.answer-box{{background:rgba(2,8,20,.7);border:0.5px solid rgba(0,210,255,.1);border-radius:10px;padding:14px 16px;font-size:10px;color:#2a5a78;line-height:1.8;max-height:200px;overflow-y:auto;white-space:pre-wrap}}
</style>
</head>
<body>
<div class="title">Mission Comparison — MOSDAC</div>
<div class="charts">
  <div class="chart-card"><div class="chart-lbl">Orbital Altitude (km)</div><canvas id="c1"></canvas></div>
  <div class="chart-card"><div class="chart-lbl">Launch Mass (kg)</div><canvas id="c2"></canvas></div>
  <div class="chart-card"><div class="chart-lbl">Imager Bands</div><canvas id="c3"></canvas></div>
  <div class="chart-card"><div class="chart-lbl">Sounder Channels</div><canvas id="c4"></canvas></div>
</div>
<div class="answer-box">{answer_escaped}</div>
<script>
const NAMES={names_js},ALTS={alts_js},MASSES={masses_js},BANDS={bands_js},SOUND={sound_js};
const COLORS=['rgba(0,210,255,.7)','rgba(255,170,0,.7)','rgba(0,255,136,.7)','rgba(170,80,255,.7)'];
const BORDERS=['rgba(0,210,255,1)','rgba(255,170,0,1)','rgba(0,255,136,1)','rgba(170,80,255,1)'];
const DEF={{responsive:true,plugins:{{legend:{{display:false}}}},scales:{{x:{{ticks:{{color:'#2a6070',font:{{size:9}}}},grid:{{color:'rgba(0,210,255,.05)'}}}},y:{{ticks:{{color:'#2a6070',font:{{size:9}}}},grid:{{color:'rgba(0,210,255,.05)'}}}}}}}};

window.addEventListener('load', () => {{
  function bar(id,data){{new Chart(document.getElementById(id),{{type:'bar',data:{{labels:NAMES,datasets:[{{data,backgroundColor:COLORS,borderColor:BORDERS,borderWidth:1}}]}},options:DEF}});}}
  bar('c1',ALTS);bar('c2',MASSES);bar('c3',BANDS);bar('c4',SOUND);
}});
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

async def generate_visualization(
    query: str,
    answer: str,
    viz_type: str,
    gemini_api_key: str = "",   # kept for API compatibility, not used
) -> VisualizationResult:
    """
    Generate a self-contained HTML visualization from the LLM answer.
    Returns VisualizationResult with .html set to a full standalone HTML page.
    """
    try:
        missions = parse_answer(query, answer)

        if viz_type == "3d_orbit":
            html = generate_3d_orbit_html(query, answer, missions)
        elif viz_type == "payload_specs":
            html = generate_payload_specs_html(query, answer, missions)
        elif viz_type == "comparison_chart":
            html = generate_comparison_html(query, answer, missions)
        else:
            html = generate_3d_orbit_html(query, answer, missions)

        extracted = {
            name: {
                "orbit_alt_km":    md.orbit_alt_km,
                "launch_mass_kg":  md.launch_mass_kg,
                "orbit_type":      md.orbit_type,
                "payloads":        md.payloads,
                "imager_bands":    md.imager_bands,
                "sounder_channels":md.sounder_channels,
            }
            for name, md in missions.items()
        }

        return VisualizationResult(
            html=html,
            viz_types=[viz_type],
            extracted_data=extracted,
        )

    except Exception as e:
        return VisualizationResult(
            html="",
            viz_types=[viz_type],
            extracted_data={},
            error=str(e),
        )