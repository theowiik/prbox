from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from ..display.base import DisplayState

router = APIRouter()


def _get_display(request: Request):
    return request.app.state.display


class ShowTextRequest(BaseModel):
    text: str
    color: str = "#00FF00"


class SetBrightnessRequest(BaseModel):
    brightness: float = Field(ge=0.0, le=1.0)


@router.get("/api/display")
def get_state(display=Depends(_get_display)) -> DisplayState:
    return display.get_state()


@router.post("/api/display/text")
def show_text(body: ShowTextRequest, display=Depends(_get_display)):
    display.show_text(body.text, body.color)
    return {"status": "ok"}


@router.post("/api/display/clear")
def clear(display=Depends(_get_display)):
    display.clear()
    return {"status": "ok"}


@router.post("/api/display/brightness")
def set_brightness(body: SetBrightnessRequest, display=Depends(_get_display)):
    display.set_brightness(body.brightness)
    return {"status": "ok"}


_PREVIEW_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>prbox</title>
<style>
:root{
  --bg:#0f0f1a;--surface:#1a1a2e;--border:#2a2a3e;
  --text:#e8e8e8;--dim:#777;--accent:#6366f1;--r:12px;
}
*{margin:0;padding:0;box-sizing:border-box}
body{
  background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;
  padding:2rem 2rem 6rem;min-height:100vh;
}
h1{font-size:1.25rem;font-weight:600;margin-bottom:.15rem}
.sub{color:var(--dim);font-size:.8rem;margin-bottom:1.5rem}
.grid{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(300px,1fr));
  gap:1rem;max-width:800px;
}
.card{
  background:var(--surface);border:1px solid var(--border);
  border-radius:var(--r);padding:1.25rem;
}
.card-head{
  display:flex;align-items:center;gap:.5rem;margin-bottom:1rem;
}
.card-head h2{font-size:.9rem;font-weight:600}
.badge{
  font-size:.6rem;background:var(--border);color:var(--dim);
  padding:.1rem .4rem;border-radius:4px;text-transform:uppercase;
  letter-spacing:.05em;margin-left:auto;
}
.w-temp{font-size:2.5rem;font-weight:700;line-height:1.1}
.w-detail{font-size:.8rem;color:var(--dim);margin-top:.2rem}
.actions{display:flex;align-items:center;gap:.5rem;margin-top:1rem}
.field{
  width:100%;background:var(--bg);border:1px solid var(--border);
  color:var(--text);padding:.5rem .75rem;border-radius:8px;
  font-size:.85rem;font-family:inherit;
}
.field:focus{outline:none;border-color:var(--accent)}
.field-row{display:flex;gap:.5rem;align-items:center;margin-top:.75rem}
input[type="color"]{
  width:32px;height:32px;border:none;background:none;
  cursor:pointer;border-radius:6px;
}
.btn{
  background:var(--accent);color:#fff;border:none;
  padding:.45rem .9rem;border-radius:8px;cursor:pointer;
  font-size:.8rem;font-family:inherit;transition:opacity .15s;
  white-space:nowrap;
}
.btn:hover{opacity:.85}
.btn-sm{padding:.25rem .6rem;font-size:.7rem}
.btn-ghost{background:transparent;border:1px solid var(--border);color:var(--dim)}
.btn-ghost:hover{border-color:var(--dim);color:var(--text)}
.toggle{
  display:flex;align-items:center;gap:.4rem;
  font-size:.8rem;color:var(--dim);cursor:pointer;
}
.toggle input{accent-color:var(--accent)}
.preview{
  position:fixed;bottom:1.25rem;right:1.25rem;
  background:var(--surface);border:1px solid var(--border);
  border-radius:var(--r);padding:.75rem;
  box-shadow:0 4px 24px rgba(0,0,0,.4);
}
.preview-label{
  font-size:.6rem;text-transform:uppercase;
  letter-spacing:.08em;color:var(--dim);margin-bottom:.5rem;
}
.preview canvas{border-radius:4px;display:block}
.preview-bar{
  display:flex;align-items:center;gap:.5rem;margin-top:.5rem;
}
.preview-bar input[type="range"]{flex:1;accent-color:var(--dim)}
</style>
</head>
<body>
<h1>prbox</h1>
<p class="sub">Event display box</p>
<div class="grid">
  <div class="card">
    <div class="card-head">
      <h2>Weather</h2>
      <span class="badge">Mock</span>
    </div>
    <div class="w-temp" id="w-temp">&mdash;</div>
    <div class="w-detail" id="w-cond"></div>
    <div class="w-detail" id="w-city">Stockholm</div>
    <div class="actions">
      <button class="btn" onclick="pushWeather()">Push to Display</button>
      <label class="toggle">
        <input type="checkbox" id="w-auto" />
        Auto
      </label>
    </div>
  </div>
  <div class="card">
    <div class="card-head">
      <h2>Manual</h2>
    </div>
    <input class="field" type="text" id="t" placeholder="Enter text..." />
    <div class="field-row">
      <input type="color" id="c" value="#00ff00" />
      <button class="btn" onclick="sendManual()">Send</button>
    </div>
  </div>
</div>
<div class="preview">
  <div class="preview-label">Display Preview</div>
  <canvas id="m"></canvas>
  <div class="preview-bar">
    <input type="range" id="b" min="0" max="100" value="100" />
    <button class="btn btn-sm btn-ghost" onclick="clr()">Clear</button>
  </div>
</div>
<script>
const F={
' ':[0,0,0,0,0,0,0],'!':[4,4,4,4,4,0,4],
',':[0,0,0,0,0,4,8],'-':[0,0,0,14,0,0,0],
'.':[0,0,0,0,0,0,4],':':[0,0,4,0,4,0,0],
'?':[14,17,1,2,4,0,4],
'0':[14,17,19,21,25,17,14],'1':[4,12,4,4,4,4,14],
'2':[14,17,1,2,4,8,31],'3':[14,17,1,6,1,17,14],
'4':[2,6,10,18,31,2,2],'5':[31,16,30,1,1,17,14],
'6':[6,8,16,30,17,17,14],'7':[31,1,2,4,8,8,8],
'8':[14,17,17,14,17,17,14],'9':[14,17,17,15,1,2,12],
'A':[4,10,17,31,17,17,17],'B':[30,17,17,30,17,17,30],
'C':[14,17,16,16,16,17,14],'D':[28,18,17,17,17,18,28],
'E':[31,16,16,30,16,16,31],'F':[31,16,16,30,16,16,16],
'G':[14,17,16,23,17,17,14],'H':[17,17,17,31,17,17,17],
'I':[14,4,4,4,4,4,14],'J':[7,2,2,2,2,18,12],
'K':[17,18,20,24,20,18,17],'L':[16,16,16,16,16,16,31],
'M':[17,27,21,21,17,17,17],'N':[17,17,25,21,19,17,17],
'O':[14,17,17,17,17,17,14],'P':[30,17,17,30,16,16,16],
'Q':[14,17,17,17,21,18,13],'R':[30,17,17,30,20,18,17],
'S':[14,17,16,14,1,17,14],'T':[31,4,4,4,4,4,4],
'U':[17,17,17,17,17,17,14],'V':[17,17,17,17,17,10,4],
'W':[17,17,17,21,21,21,10],'X':[17,17,10,4,10,17,17],
'Y':[17,17,10,4,4,4,4],'Z':[31,1,2,4,8,16,31]
};

function hexRgb(h){
  h=h.replace('#','');
  return[parseInt(h.substring(0,2),16),
    parseInt(h.substring(2,4),16),
    parseInt(h.substring(4,6),16)];
}

function textPx(text,w,h){
  const px=new Uint8Array(w*h);
  const t=text.toUpperCase();
  const sy=Math.max(0,Math.floor((h-7)/2));
  let cx=1;
  for(const c of t){
    const g=F[c];
    if(!g){cx+=6;continue}
    for(let r=0;r<7;r++){
      const y=sy+r;
      if(y>=h)break;
      for(let b=0;b<5;b++){
        const x=cx+b;
        if(x>=w)break;
        if(g[r]&(16>>b))px[y*w+x]=1;
      }
    }
    cx+=6;
    if(cx>=w)break;
  }
  return px;
}

function draw(cv,s,maxW){
  const ctx=cv.getContext('2d');
  const W=s.width,H=s.height;
  const sz=Math.max(4,Math.min(14,
    Math.floor((maxW||560)/W)-2));
  const gp=Math.max(1,Math.floor(sz/4));
  const st=sz+gp;
  cv.width=W*st+gp;
  cv.height=H*st+gp;
  ctx.fillStyle='#0a0a0a';
  ctx.fillRect(0,0,cv.width,cv.height);
  const px=textPx(s.text,W,H);
  const rgb=hexRgb(s.color);
  const rad=sz/2-0.5;
  for(let y=0;y<H;y++){
    for(let x=0;x<W;x++){
      const on=px[y*W+x];
      const cx=gp+x*st+sz/2;
      const cy=gp+y*st+sz/2;
      ctx.beginPath();
      ctx.arc(cx,cy,rad,0,6.284);
      if(on){
        ctx.fillStyle='rgba('+rgb[0]+','+rgb[1]+','
          +rgb[2]+','+s.brightness+')';
        ctx.shadowColor=s.color;
        ctx.shadowBlur=sz*0.4;
      }else{
        ctx.fillStyle='#181818';
        ctx.shadowBlur=0;
      }
      ctx.fill();
      ctx.shadowBlur=0;
    }
  }
}

const API='/api/display';
const cv=document.getElementById('m');
let weatherData=null;
let autoTimer=null;

async function poll(){
  try{
    const r=await fetch(API);
    draw(cv,await r.json(),300);
  }catch(e){}
}

async function fetchWeather(){
  const r=await fetch('/api/sources/weather');
  const w=await r.json();
  weatherData=w;
  document.getElementById('w-temp').textContent=w.temp+'\\u00b0C';
  document.getElementById('w-temp').style.color=w.display_color;
  document.getElementById('w-cond').textContent=w.condition;
  document.getElementById('w-city').textContent=w.city;
  return w;
}

async function pushWeather(){
  const w=weatherData||await fetchWeather();
  await fetch(API+'/text',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({text:w.display_text,color:w.display_color})
  });
}

document.getElementById('w-auto').addEventListener('change',e=>{
  if(e.target.checked){
    pushWeather();
    autoTimer=setInterval(()=>{
      fetchWeather().then(()=>pushWeather());
    },30000);
  }else{
    clearInterval(autoTimer);
    autoTimer=null;
  }
});

async function sendManual(){
  const t=document.getElementById('t');
  const c=document.getElementById('c');
  await fetch(API+'/text',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({text:t.value,color:c.value})
  });
  t.value='';
}

async function clr(){
  await fetch(API+'/clear',{method:'POST'});
}

document.getElementById('b').addEventListener('input',async e=>{
  await fetch(API+'/brightness',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({brightness:e.target.value/100})
  });
});

document.getElementById('t').addEventListener('keydown',e=>{
  if(e.key==='Enter')sendManual();
});

fetchWeather();
setInterval(poll,500);
poll();
</script>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse)
def preview():
    return _PREVIEW_HTML
