/* ============================================================
   CreativeOS — shared shell
   Injected into every product page. Builds the persistent chrome
   (brand, top bar, product rail) and wires the cross-product
   surfaces: ⌘K search, notifications, wallet, toast.
   A page only ships its <main class="pane" data-view="…">.
   ============================================================ */
(function(){
  var HUES={home:'#A6AEBB',framevault:'#7C5CFF',filmcrew:'#3DA9FC',rightsforge:'#F4A259',creatorstack:'#FF5C87',studio:'#B47CFF',settings:'#6B7480'};

  var NAV=[
    {grp:'Workspace'},
    {v:'home',label:'Home',href:'home.html'},
    {v:'framevault',label:'FrameVault',href:'framevault.html'},
    {grp:'Products'},
    {v:'filmcrew',label:'FilmCrew',href:'filmcrew.html'},
    {v:'rightsforge',label:'RightsForge',href:'rightsforge.html'},
    {v:'creatorstack',label:'CreatorStack',href:'creatorstack.html'},
    {v:'studio',label:'OTT Studio',href:'studio.html'},
    {spring:true},
    {v:'settings',label:'Settings',href:'settings.html'}
  ];

  /* One search index spanning every product */
  var INDEX=[
    {t:'OTT',s:'@ott · Cinematographer',type:'person',ty:'◍',prod:'FrameVault',h:HUES.framevault,href:'framevault.html'},
    {t:'Maya Rún',s:'@maya · Director',type:'person',ty:'◍',prod:'FrameVault',h:HUES.framevault,href:'framevault.html'},
    {t:'Studio Kestrel',s:'Production company',type:'person',ty:'◍',prod:'FrameVault',h:HUES.framevault,href:'framevault.html'},
    {t:'"Halcyon"',s:'DP role open · £1,200',type:'project',ty:'🎬',prod:'FilmCrew',h:HUES.filmcrew,href:'filmcrew.html'},
    {t:'"Nightshift"',s:'Short film · wrapped',type:'project',ty:'🎬',prod:'FilmCrew',h:HUES.filmcrew,href:'filmcrew.html'},
    {t:'"The Archivist"',s:'Pilot · optioned',type:'IP',ty:'📜',prod:'RightsForge',h:HUES.rightsforge,href:'rightsforge.html'},
    {t:'"Cold Open"',s:'Winning concept · funded',type:'IP',ty:'📜',prod:'RightsForge',h:HUES.rightsforge,href:'rightsforge.html'},
    {t:'"Umber" LUT pack',s:'Licensed 34× · royalties',type:'asset',ty:'🎨',prod:'RightsForge',h:HUES.rightsforge,href:'rightsforge.html'},
    {t:'Cinematic ambient — pack',s:'Music · royalty-free',type:'asset',ty:'🎵',prod:'RightsForge',h:HUES.rightsforge,href:'rightsforge.html'},
    {t:'"Neon Dusk"',s:'Brand challenge · closes 2d',type:'challenge',ty:'🏆',prod:'CreatorStack',h:HUES.creatorstack,href:'creatorstack.html'},
    {t:'"Halcyon" cut',s:'Workspace project',type:'project',ty:'🎞️',prod:'OTT Studio',h:HUES.studio,href:'studio.html'}
  ];

  var NOTIFS=[
    {prod:'FilmCrew',h:HUES.filmcrew,txt:'New offer for <b>"Halcyon"</b>',t:'18 minutes ago',unread:true,href:'filmcrew.html'},
    {prod:'RightsForge',h:HUES.rightsforge,txt:'<b>"Umber"</b> licensed again · +£28',t:'1 hour ago',unread:true,href:'rightsforge.html'},
    {prod:'CreatorStack',h:HUES.creatorstack,txt:'<b>"Neon Dusk"</b> closes in 2 days',t:'3 hours ago',unread:true,href:'creatorstack.html'},
    {prod:'RightsForge',h:HUES.rightsforge,txt:'Producer bookmarked <b>"The Archivist"</b>',t:'5 hours ago',unread:false,href:'rightsforge.html'}
  ];

  function el(html){ var d=document.createElement('div'); d.innerHTML=html.trim(); return d.firstChild; }
  var view=(document.querySelector('.pane')||{}).getAttribute?document.querySelector('.pane').getAttribute('data-view'):'home';

  /* ---- build shell ---- */
  var app=el('<div class="app"></div>');
  app.appendChild(el('<div class="brand"><span class="glyph"></span><b>CreativeOS</b></div>'));

  var bar=el('<div class="bar"></div>');
  bar.appendChild(el('<div class="search" id="searchTrigger"><span>🔍</span><span>Search people, projects, IP, assets…</span><span class="kbd">⌘K</span></div>'));
  bar.appendChild(el('<div class="spacer"></div>'));
  var unread=NOTIFS.filter(function(n){return n.unread}).length;
  bar.appendChild(el('<button class="iconbtn" id="themeBtn" title="Toggle light / dark" aria-label="Toggle theme"><span id="themeIcon">'+(document.documentElement.getAttribute('data-theme')==='dark'?'☾':'☀')+'</span></button>'));
  bar.appendChild(el('<button class="iconbtn" id="notifBtn" title="Notifications" aria-label="Notifications">🔔<span class="badge" id="notifBadge">'+unread+'</span></button>'));
  bar.appendChild(el('<button class="iconbtn" id="msgBtn" title="Messages" aria-label="Messages">✉<span class="badge">2</span></button>'));
  bar.appendChild(el('<button class="me" id="meBtn"><span class="av">O</span><small>OTT</small><span style="color:var(--text-lo);font-size:11px">▾</span></button>'));
  app.appendChild(bar);

  var rail=el('<nav class="rail" id="rail"></nav>');
  NAV.forEach(function(n){
    if(n.grp){ rail.appendChild(el('<div class="cap grp">'+n.grp+'</div>')); return; }
    if(n.spring){ rail.appendChild(el('<div class="spring"></div>')); return; }
    var a=el('<a class="navi'+(n.v===view?' active':'')+'" href="'+n.href+'" style="--h:'+HUES[n.v]+'"><span class="ic"></span>'+n.label+'</a>');
    rail.appendChild(a);
  });
  app.appendChild(rail);

  /* move the page's <main> into the shell */
  var main=document.querySelector('.pane');
  document.body.insertBefore(app,main);
  app.appendChild(main);

  /* ---- overlays ---- */
  document.body.appendChild(el('<div class="scrim" id="scrim"></div>'));
  var cmd=el('<div class="cmd" id="cmd" role="dialog" aria-label="Search everything"><div class="in"><span class="lens">🔍</span><input id="cmdInput" placeholder="Search people, projects, IP, assets, challenges…" autocomplete="off"><span class="kbd">esc</span></div><div class="res" id="cmdRes"></div></div>');
  document.body.appendChild(cmd);

  var notifDrop=el('<div class="drop" id="notifDrop"><div class="dh"><b>Notifications</b><a id="markRead">Mark all read</a></div><div class="dl" id="notifList"></div></div>');
  document.body.appendChild(notifDrop);
  var nl=notifDrop.querySelector('#notifList');
  NOTIFS.forEach(function(n){
    nl.appendChild(el('<a class="nrow'+(n.unread?' unread':'')+'" href="'+n.href+'" style="--h:'+n.h+'"><span class="nd"'+(n.unread?'':' style="background:var(--text-lo);box-shadow:none"')+'></span><div><div class="nt"><span class="prodx"'+(n.unread?'':' style="color:var(--text-mid)"')+'>'+n.prod+'</span> · '+n.txt+'</div><div class="nm">'+n.t+'</div></div></a>'));
  });

  var pmenu=el('<div class="drop pmenu" id="pmenu"><div class="whead"><div class="cap" style="margin-bottom:6px">Wallet balance</div><div class="bal">£3,412.00</div><div class="split"><span class="s">FilmCrew <b>£1,940</b></span><span class="s">RightsForge <b>£1,212</b></span><span class="s">CreatorStack <b>£260</b></span></div></div><a class="mi" href="framevault.html">◍ Your public page</a><div class="mi">💳 Wallet &amp; payouts</div><a class="mi" href="settings.html">🔔 Notification settings</a><a class="mi" href="settings.html">🔒 Permissions</a><a class="mi" href="settings.html">⚙ Account settings</a></div>');
  document.body.appendChild(pmenu);

  var toastEl=el('<div class="toast" id="toast"></div>');
  document.body.appendChild(toastEl);

  /* ---- toast ---- */
  var tTimer;
  window.cosToast=function(msg){ toastEl.textContent=msg; toastEl.classList.add('show'); clearTimeout(tTimer); tTimer=setTimeout(function(){toastEl.classList.remove('show')},2200); };

  /* ---- command palette ---- */
  var scrim=document.getElementById('scrim'), cmdInput=document.getElementById('cmdInput'), cmdRes=document.getElementById('cmdRes');
  var selIdx=0, filtered=[];
  function openCmd(){ scrim.classList.add('show'); cmd.classList.add('show'); cmdInput.value=''; renderCmd(''); cmdInput.focus(); }
  function closeCmd(){ scrim.classList.remove('show'); cmd.classList.remove('show'); }
  function renderCmd(q){
    q=q.trim().toLowerCase();
    var list = q? INDEX.filter(function(i){return (i.t+' '+i.s+' '+i.prod+' '+i.type).toLowerCase().indexOf(q)>-1}) : INDEX;
    selIdx=0;
    if(!list.length){ cmdRes.innerHTML='<div class="empty">No matches. One index spans every product.</div>'; filtered=[]; return; }
    var groups={}; list.forEach(function(i){ (groups[i.prod]=groups[i.prod]||[]).push(i); });
    var html='', flat=[];
    Object.keys(groups).forEach(function(g){
      html+='<div class="cap g">'+g+'</div>';
      groups[g].forEach(function(i){ var idx=flat.length; flat.push(i);
        html+='<a class="r" href="'+i.href+'" data-i="'+idx+'" style="--h:'+i.h+'"><span class="ty">'+i.ty+'</span><span class="rt">'+i.t+' <small>· '+i.s+'</small></span><span class="rp">'+i.type+'</span></a>';
      });
    });
    filtered=flat; cmdRes.innerHTML=html; hi();
  }
  function hi(){ cmdRes.querySelectorAll('.r').forEach(function(r,i){ r.classList.toggle('sel',i===selIdx); }); }
  cmdInput.addEventListener('input',function(){ renderCmd(cmdInput.value); });
  cmdInput.addEventListener('keydown',function(e){
    if(e.key==='ArrowDown'){e.preventDefault(); selIdx=Math.min(selIdx+1,filtered.length-1); hi();}
    else if(e.key==='ArrowUp'){e.preventDefault(); selIdx=Math.max(selIdx-1,0); hi();}
    else if(e.key==='Enter'){e.preventDefault(); var r=cmdRes.querySelectorAll('.r')[selIdx]; if(r) window.location.href=r.getAttribute('href');}
  });
  document.getElementById('searchTrigger').addEventListener('click',openCmd);
  scrim.addEventListener('click',closeCmd);

  /* ---- dropdowns ---- */
  function closeDrops(){ notifDrop.classList.remove('show'); pmenu.classList.remove('show'); }
  function toggle(elm){ var open=elm.classList.contains('show'); closeDrops(); if(!open) elm.classList.add('show'); }
  document.getElementById('themeBtn').addEventListener('click',function(){
    var next = document.documentElement.getAttribute('data-theme')==='dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    try{ localStorage.setItem('ott-theme', next); }catch(e){}
    document.getElementById('themeIcon').textContent = next==='dark' ? '☾' : '☀';
  });
  document.getElementById('notifBtn').addEventListener('click',function(e){ e.stopPropagation(); toggle(notifDrop); });
  document.getElementById('meBtn').addEventListener('click',function(e){ e.stopPropagation(); toggle(pmenu); });
  document.getElementById('msgBtn').addEventListener('click',function(){ window.cosToast('Messages — one inbox, threads from every product'); });
  document.addEventListener('click',function(e){ if(!notifDrop.contains(e.target)&&!pmenu.contains(e.target)) closeDrops(); });
  document.getElementById('markRead').addEventListener('click',function(e){
    e.preventDefault();
    notifDrop.querySelectorAll('.nrow.unread').forEach(function(r){r.classList.remove('unread'); var d=r.querySelector('.nd'); d.style.background='var(--text-lo)'; d.style.boxShadow='none';});
    var b=document.getElementById('notifBadge'); if(b) b.style.display='none'; window.cosToast('All caught up');
  });

  /* ---- global keys ---- */
  document.addEventListener('keydown',function(e){
    if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){ e.preventDefault(); cmd.classList.contains('show')?closeCmd():openCmd(); }
    else if(e.key==='Escape'){ closeCmd(); closeDrops(); }
  });

  /* any element with data-toast fires a toast instead of navigating */
  document.addEventListener('click',function(e){
    var t=e.target.closest('[data-toast]'); if(t){ e.preventDefault(); window.cosToast(t.getAttribute('data-toast')); }
  });
})();
