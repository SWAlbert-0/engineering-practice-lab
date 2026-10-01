(function(root){
const PATH=[[0,120],[240,120],[240,350],[500,350],[500,180],[720,180],[720,400],[920,400]];
function dist(a,b){return Math.hypot(a[0]-b[0],a[1]-b[1])}
const LENGTHS=PATH.slice(1).map((p,i)=>dist(PATH[i],p)),TOTAL=LENGTHS.reduce((a,b)=>a+b,0);
function position(distance){for(let i=0;i<LENGTHS.length;i++){if(distance<=LENGTHS[i]){const t=distance/LENGTHS[i];return [PATH[i][0]+(PATH[i+1][0]-PATH[i][0])*t,PATH[i][1]+(PATH[i+1][1]-PATH[i][1])*t]}distance-=LENGTHS[i]}return PATH.at(-1)}
function onRoad(x,y){return PATH.slice(1).some((p,i)=>{const a=PATH[i],vx=p[0]-a[0],vy=p[1]-a[1],t=Math.max(0,Math.min(1,((x-a[0])*vx+(y-a[1])*vy)/(vx*vx+vy*vy)));return Math.hypot(x-a[0]-t*vx,y-a[1]-t*vy)<31})}
class Game{constructor(){this.life=12;this.gold=160;this.wave=0;this.kills=0;this.towers=[];this.enemies=[];this.effects=[];this.queue=0;this.timer=0;this.state='ready';this.paused=false;this.clock=0}
build(x,y,type='bolt'){if(this.state==='won'||this.state==='lost')return '本局已结束，请重开';const cost=type==='frost'?70:50;if(this.gold<cost)return '金币不足';if(x<22||x>878||y<22||y>478||onRoad(x,y)||this.towers.some(t=>Math.hypot(t.x-x,t.y-y)<43))return '请选择远离道路及其他塔的空地';this.gold-=cost;this.towers.push({x,y,type,cooldown:0});return '建造完成'}
next(){if(this.state!=='ready'||this.wave>=5)return false;this.wave++;this.queue=6+this.wave*2;this.timer=0;this.state='running';return true}
step(dt){if(this.paused||this.state!=='running')return;this.clock+=dt;this.timer-=dt;if(this.queue>0&&this.timer<=0){const hp=35+this.wave*13;this.enemies.push({d:0,hp,max:hp,slow:0,speed:48+this.wave*4});this.queue--;this.timer=.9}
for(const e of this.enemies){e.slow=Math.max(0,e.slow-dt);e.d+=e.speed*(e.slow>0?.48:1)*dt}
for(const t of this.towers){t.cooldown-=dt;if(t.cooldown>0)continue;const e=this.enemies.filter(e=>e.hp>0&&e.d<TOTAL&&dist([t.x,t.y],position(e.d))<(t.type==='frost'?135:155)).sort((a,b)=>b.d-a.d)[0];if(e){e.hp-=t.type==='frost'?8:22;if(t.type==='frost')e.slow=1.3;t.cooldown=t.type==='frost'?.8:.6;this.effects.push({a:[t.x,t.y],b:position(e.d),ttl:.12,type:t.type})}}
this.enemies=this.enemies.filter(e=>{if(e.hp<=0){this.kills++;this.gold+=8;return false}if(e.d>=TOTAL){this.life--;return false}return true});this.effects=this.effects.filter(e=>(e.ttl-=dt)>0);if(this.life<=0){this.life=0;this.state='lost'}else if(!this.queue&&!this.enemies.length){this.gold+=30;this.state=this.wave===5?'won':'ready'}}}
const api={Game,PATH,position,onRoad,TOTAL};if(typeof module!=='undefined')module.exports=api;else root.TowerEngine=api;
})(typeof window!=='undefined'?window:globalThis);
