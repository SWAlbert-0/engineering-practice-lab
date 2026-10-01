const assert=require('node:assert/strict');const {Game,onRoad,position,TOTAL}=require('../demos/04-tower-defense/engine.js');
let g=new Game();assert.match(g.build(200,120),/空地/);assert.equal(g.gold,160);assert.equal(g.build(180,60),'建造完成');assert.equal(g.gold,110);assert.match(g.build(180,60),/空地/);g.build(340,290);g.build(570,245);assert.match(g.build(100,50,'frost'),/金币不足/);assert.equal(g.next(),true);assert.equal(g.next(),false);g.paused=true;g.step(1);assert.equal(g.enemies.length,0);g.paused=false;g.step(1/60);assert.equal(g.enemies.length,1);
// Loss must be reachable without defenses.
g=new Game();for(let wave=0;wave<5&&g.state!=='lost';wave++){g.next();for(let i=0;i<60*100&&g.state==='running';i++)g.step(1/60)}assert.equal(g.state,'lost');assert.equal(g.life,0);
// Engine victory condition: controlled high-budget defense across all path bends.
g=new Game();g.gold=2000;for(const p of [[100,60],[190,60],[310,100],[180,250],[310,280],[380,280],[440,410],[565,300],[560,110],[650,110],[790,260],[650,340],[790,450],[860,330]])g.build(...p);for(let wave=0;wave<5;wave++){assert.equal(g.next(),true);for(let i=0;i<60*100&&g.state==='running';i++)g.step(1/60)}assert.equal(g.state,'won');assert.ok(g.life>0);
assert.equal(onRoad(240,200),true);assert.equal(position(TOTAL)[0],920);console.log('Tower: build, economy, pause, path, wave lock, loss and victory checks passed.');
