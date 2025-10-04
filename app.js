const SECTION_TO_FILE={politics:'outputs/politics.json',economy:'outputs/economy.json',society:'outputs/society.json',culture:'outputs/culture.json',world:'outputs/world.json',it_science:'outputs/it_science.json'};
async function loadSection(s){const st=document.getElementById('status');st.textContent='불러오는 중…';try{const r=await fetch(SECTION_TO_FILE[s]);if(!r.ok)throw 0;const j=await r.json();if(!j.length)throw 0;st.textContent='업데이트됨';return j.slice(0,3)}catch{st.textContent='데이터 없음';return[]}}
function renderCards(list){const root=document.getElementById('articles');root.innerHTML=list.map(a=>`<article class='card'><h3>${a.title}</h3><p>${a.summary||a.content}</p><a href='${a.url}' target='_blank'>원문 보기</a></article>`).join('');}
function setup(){const btns=document.querySelectorAll('.controls button');async function sel(b){btns.forEach(x=>x.classList.remove('active'));b.classList.add('active');renderCards(await loadSection(b.dataset.cat));}
btns.forEach((b,i)=>{b.onclick=()=>sel(b);if(i===0)sel(b);});}
document.addEventListener('DOMContentLoaded',setup);
