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
*{margin:0;padding:0;box-sizing:border-box}
body{
  background:#111;color:#ccc;
  font-family:'Courier New',monospace;
  display:flex;flex-direction:column;
  align-items:center;padding:2rem;
}
h1{color:#fff;margin-bottom:1rem}
canvas{
  border:3px solid #333;border-radius:8px;
  margin-bottom:1rem;background:#0a0a0a;
}
.ctl{display:flex;flex-direction:column;gap:0.5rem}
.row{display:flex;gap:0.5rem;align-items:center}
input[type="text"]{
  flex:1;padding:0.4rem 0.6rem;
  background:#222;border:1px solid #444;
  color:#fff;font-family:inherit;
  border-radius:4px;width:200px;
}
input[type="color"]{
  width:34px;height:30px;
  border:none;background:none;cursor:pointer;
}
input[type="range"]{flex:1;accent-color:#555}
button{
  padding:0.4rem 0.8rem;background:#333;
  color:#fff;border:1px solid #555;
  font-family:inherit;cursor:pointer;
  border-radius:4px;
}
button:hover{background:#444}
</style>
</head>
<body>
<h1>prbox</h1>
<canvas id="m"></canvas>
<div class="ctl">
  <div class="row">
    <input type="text" id="t" placeholder="Text..." />
    <input type="color" id="c" value="#00ff00" />
    <button onclick="show()">Show</button>
    <button onclick="clr()">Clear</button>
  </div>
  <div class="row">
    <input type="range" id="b" min="0" max="100" value="100" />
  </div>
</div>
<script>
const F={
' ':[0,0,0,0,0,0,0],
'!':[4,4,4,4,4,0,4],
',':[0,0,0,0,0,4,8],
'-':[0,0,0,14,0,0,0],
'.':[0,0,0,0,0,0,4],
':':[0,0,4,0,4,0,0],
'?':[14,17,1,2,4,0,4],
'0':[14,17,19,21,25,17,14],
'1':[4,12,4,4,4,4,14],
'2':[14,17,1,2,4,8,31],
'3':[14,17,1,6,1,17,14],
'4':[2,6,10,18,31,2,2],
'5':[31,16,30,1,1,17,14],
'6':[6,8,16,30,17,17,14],
'7':[31,1,2,4,8,8,8],
'8':[14,17,17,14,17,17,14],
'9':[14,17,17,15,1,2,12],
'A':[4,10,17,31,17,17,17],
'B':[30,17,17,30,17,17,30],
'C':[14,17,16,16,16,17,14],
'D':[28,18,17,17,17,18,28],
'E':[31,16,16,30,16,16,31],
'F':[31,16,16,30,16,16,16],
'G':[14,17,16,23,17,17,14],
'H':[17,17,17,31,17,17,17],
'I':[14,4,4,4,4,4,14],
'J':[7,2,2,2,2,18,12],
'K':[17,18,20,24,20,18,17],
'L':[16,16,16,16,16,16,31],
'M':[17,27,21,21,17,17,17],
'N':[17,17,25,21,19,17,17],
'O':[14,17,17,17,17,17,14],
'P':[30,17,17,30,16,16,16],
'Q':[14,17,17,17,21,18,13],
'R':[30,17,17,30,20,18,17],
'S':[14,17,16,14,1,17,14],
'T':[31,4,4,4,4,4,4],
'U':[17,17,17,17,17,17,14],
'V':[17,17,17,17,17,10,4],
'W':[17,17,17,21,21,21,10],
'X':[17,17,10,4,10,17,17],
'Y':[17,17,10,4,4,4,4],
'Z':[31,1,2,4,8,16,31]
};

function hexRgb(h){
  h=h.replace('#','');
  return[
    parseInt(h.substring(0,2),16),
    parseInt(h.substring(2,4),16),
    parseInt(h.substring(4,6),16)
  ];
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

function draw(cv,s){
  const ctx=cv.getContext('2d');
  const W=s.width,H=s.height;
  const sz=Math.max(6,Math.min(16,
    Math.floor(560/W)-2));
  const gp=Math.max(2,Math.floor(sz/4));
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
        ctx.fillStyle='rgba('+rgb[0]+','
          +rgb[1]+','+rgb[2]+','+s.brightness+')';
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

async function poll(){
  try{
    const r=await fetch(API);
    draw(cv,await r.json());
  }catch(e){}
}

async function show(){
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

document.getElementById('b')
  .addEventListener('input',async(e)=>{
  await fetch(API+'/brightness',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({brightness:e.target.value/100})
  });
});

document.getElementById('t')
  .addEventListener('keydown',(e)=>{
  if(e.key==='Enter')show();
});

setInterval(poll,500);
poll();
</script>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse)
def preview():
    return _PREVIEW_HTML
