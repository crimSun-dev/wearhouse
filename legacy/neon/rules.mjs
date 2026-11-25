export const slots = ['top', 'bottom', 'dress', 'outer', 'footwear', 'accessory'];
export const occasions = ['campus', 'casual', 'worship', 'formal', 'wedding'];
export const defaults = {color_hex:'#808080', style:'casual', rain_suitable:false, heavy:false, long_sleeve:false, long_bottom:false, formality:1};
export const garment = g => ({...g, attrs:{...defaults,...g.attrs}, origin:g.serial?'registered':'manual'});
const floor = {campus:1,casual:1,worship:1,formal:2,wedding:3};
export function allowed(items, ctx) {
  const by = Object.fromEntries(items.map(g=>[g.slot,g]));
  if (Object.keys(by).length!==items.length || !by.footwear) return false;
  if (by.dress ? (by.top || by.bottom) : !(by.top && by.bottom)) return false;
  if (ctx.hot && items.some(g=>g.attrs.heavy)) return false;
  if (ctx.rain && !items.some(g=>['footwear','outer'].includes(g.slot)&&g.attrs.rain_suitable)) return false;
  if (ctx.occasion==='worship' && (!items.some(g=>['top','dress','outer'].includes(g.slot)&&g.attrs.long_sleeve) || !items.some(g=>['bottom','dress'].includes(g.slot)&&g.attrs.long_bottom))) return false;
  return items.every(g=>g.slot==='accessory'||g.attrs.formality>=floor[ctx.occasion]);
}
function hls(hex) {
  const [r,g,b]=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)/255);
  const hi=Math.max(r,g,b), lo=Math.min(r,g,b), l=(hi+lo)/2, d=hi-lo;
  if (!d) return [0,l,0];
  const s=l<=0.5?d/(hi+lo):d/(2-hi-lo);
  let h=hi===r?(g-b)/d+(g<b?6:0):hi===g?(b-r)/d+2:(r-g)/d+4;
  return [h/6,l,s];
}
const styles = {'casual,sporty':.7,'casual,smart':.7,'casual,street':.8,'casual,modest':.7,'formal,smart':.8,'modest,smart':.8,'formal,modest':.7,'sporty,street':.8};
export function compatibility(items) {
  let total=0,n=0;
  for (let i=0;i<items.length;i++) for(let j=i+1;j<items.length;j++) {
    const a=items[i].attrs,b=items[j].attrs, x=hls(a.color_hex), y=hls(b.color_hex);
    let d=Math.abs(x[0]-y[0])*360; d=Math.min(d,360-d);
    const neutral=v=>v[2]<.3||v[1]<.25||v[1]>.9;
    const color=neutral(x)||neutral(y)?1:d<=35?.9:d>=150?.8:.45;
    const style=a.style===b.style?1:styles[[a.style,b.style].sort().join(',')]??.3;
    total+=(color+style)/2; n++;
  }
  return n?total/n:1;
}
export function recommend(wardrobe,ctx,today,k=5) {
  const by=Object.fromEntries(slots.map(s=>[s,wardrobe.filter(g=>g.slot===s&&(!ctx.hot||!g.attrs.heavy)&&(s==='accessory'||g.attrs.formality>=floor[ctx.occasion]))]));
  const bases=by.top.flatMap(t=>by.bottom.map(b=>[t,b])).concat(by.dress.map(d=>[d]));
  const scored=[];
  for(const base of bases) for(const shoe of by.footwear) for(const outer of [null,...by.outer]) for(const acc of [null,...by.accessory]) {
    const items=[...base,shoe,...[outer,acc].filter(Boolean)]; if(!allowed(items,ctx)) continue;
    const compat=compatibility(items);
    const pref=items.reduce((v,g)=>v+(g.times_chosen+2.5)/(g.times_recommended+5),0)/items.length;
    const recency=items.reduce((v,g)=>v+(g.last_worn_at?Math.exp(-Math.max((Date.parse(today)-Date.parse(g.last_worn_at))/86400000,0)/4):0),0)/items.length;
    scored.push({items,compat,pref,recency,score:.5*compat+.3*pref-.2*recency});
  }
  const order=(a,b)=>b.score-a.score || (a.items.map(g=>g.id).join(',')<b.items.map(g=>g.id).join(',')?-1:1);
  scored.sort(order); const picked=[],seen=new Set();
  for(const s of scored) {const core=['top','bottom','dress'].map(slot=>s.items.find(g=>g.slot===slot)?.id??'').join(','); if(!seen.has(core)){picked.push(s);seen.add(core);} if(picked.length===k)break;}
  for(const s of scored){if(picked.length===k)break;if(!picked.includes(s))picked.push(s);}
  return picked.sort(order).map((s,i)=>({...s,rank:i+1,...Object.fromEntries(['score','compat','pref','recency'].map(key=>[key,Number(s[key].toFixed(4))]))}));
}
