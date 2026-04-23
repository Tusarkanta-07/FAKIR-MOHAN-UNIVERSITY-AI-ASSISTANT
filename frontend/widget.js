// =============================================================================
// 🎓 FMU AI ASSISTANT — EMBEDDABLE CHAT WIDGET
// =============================================================================
// Add this to any website:
//
//   <script>
//     window.fmuConfig = {
//       apiUrl: "https://your-space.hf.space",
//       chatbotId: "fmu-chatbot",
//     };
//   </script>
//   <script src="widget.js" defer></script>
//
// =============================================================================

(function () {
    'use strict';

    const config = window.fmuConfig || window.chatbaseConfig || {};
    const chatbotId = config.chatbotId || 'fmu-chatbot';
    const apiUrl = (config.apiUrl || '').replace(/\/+$/, '');
    const themeColor = config.themeColor || '#0F4C81';

    if (!apiUrl) {
        console.error('[FMU Widget] Missing apiUrl in window.fmuConfig');
        return;
    }

    const styles = `
        #fmu-bubble {
            position:fixed; bottom:24px; right:24px;
            width:60px; height:60px; border-radius:50%;
            background: linear-gradient(135deg, ${themeColor}, #1A6BB5);
            color:white; border:none; cursor:pointer;
            display:flex; align-items:center; justify-content:center;
            font-size:14px; font-weight:900;
            box-shadow: 0 4px 24px ${themeColor}55;
            z-index:99999;
            transition: all 0.3s ease;
            font-family: 'Inter', -apple-system, sans-serif;
        }
        #fmu-bubble:hover { transform:scale(1.08); box-shadow:0 6px 32px ${themeColor}77; }
        #fmu-bubble.open { transform:rotate(90deg) scale(0.9); }

        #fmu-window {
            position:fixed; bottom:96px; right:24px;
            width:380px; height:540px;
            background:#12121A;
            border:1px solid rgba(255,255,255,0.07);
            border-radius:20px;
            box-shadow:0 12px 48px rgba(0,0,0,0.5);
            display:none; flex-direction:column;
            overflow:hidden; z-index:99999;
            font-family:'Inter',-apple-system,sans-serif;
            animation:fmuSlide 0.3s ease-out;
        }
        #fmu-window.open { display:flex; }
        @keyframes fmuSlide { from{opacity:0;transform:translateY(16px) scale(0.96)} to{opacity:1;transform:translateY(0) scale(1)} }

        .fmu-hdr { padding:16px 20px; background:linear-gradient(135deg,${themeColor},#1A6BB5); color:white; display:flex; align-items:center; justify-content:space-between; }
        .fmu-hdr-left { display:flex; align-items:center; gap:10px; }
        .fmu-hdr-av { width:36px;height:36px;border-radius:50%;background:rgba(255,255,255,0.2);display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:900; }
        .fmu-hdr-name { font-weight:700;font-size:14px; }
        .fmu-hdr-st { font-size:11px;opacity:0.85; }
        .fmu-close { background:none;border:none;color:white;font-size:22px;cursor:pointer;opacity:0.8; }
        .fmu-close:hover { opacity:1; }

        .fmu-msgs { flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:10px;background:#0A0A0F; }
        .fmu-msgs::-webkit-scrollbar{width:4px} .fmu-msgs::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.1);border-radius:4px}

        .fmu-m { max-width:85%;padding:10px 14px;border-radius:14px;font-size:13px;line-height:1.6;word-wrap:break-word;animation:fmuFade 0.3s ease-out; }
        @keyframes fmuFade { from{opacity:0;transform:translateY(6px)} to{opacity:1;transform:translateY(0)} }
        .fmu-m.bot { background:#1A1A2E;color:#E0E0F0;align-self:flex-start;border-bottom-left-radius:4px; }
        .fmu-m.user { background:${themeColor};color:white;align-self:flex-end;border-bottom-right-radius:4px; }

        .fmu-dots { display:flex;gap:4px;padding:12px 16px;align-self:flex-start; }
        .fmu-dot { width:7px;height:7px;border-radius:50%;background:#506070;animation:fmuB 1.4s infinite; }
        .fmu-dot:nth-child(2){animation-delay:0.2s} .fmu-dot:nth-child(3){animation-delay:0.4s}
        @keyframes fmuB { 0%,60%,100%{transform:translateY(0)} 30%{transform:translateY(-6px)} }

        .fmu-inp { padding:10px 14px;border-top:1px solid rgba(255,255,255,0.06);background:#12121A;display:flex;align-items:center;gap:8px; }
        .fmu-inp input { flex:1;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);border-radius:999px;padding:10px 16px;color:white;font-size:13px;font-family:inherit;outline:none; }
        .fmu-inp input:focus { border-color:${themeColor}88; }
        .fmu-inp input::placeholder { color:#506070; }
        .fmu-snd { width:36px;height:36px;border-radius:50%;background:${themeColor};color:white;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0; }
        .fmu-snd:disabled { opacity:0.4;cursor:not-allowed; }
        .fmu-ft { text-align:center;padding:5px;font-size:10px;color:#506070;background:#12121A; }

        @media(max-width:480px) {
            #fmu-window { width:calc(100% - 32px);right:16px;bottom:88px;height:60vh; }
        }
    `;

    const styleEl = document.createElement('style');
    styleEl.textContent = styles;
    document.head.appendChild(styleEl);

    const bubble = document.createElement('button');
    bubble.id = 'fmu-bubble';
    bubble.textContent = 'FM';
    bubble.setAttribute('aria-label', 'Open FMU AI Assistant');
    document.body.appendChild(bubble);

    const win = document.createElement('div');
    win.id = 'fmu-window';
    win.innerHTML = `
        <div class="fmu-hdr">
            <div class="fmu-hdr-left">
                <div class="fmu-hdr-av">FM</div>
                <div><div class="fmu-hdr-name">FMU AI Assistant</div><div class="fmu-hdr-st">● Online</div></div>
            </div>
            <button class="fmu-close" id="fmu-close">✕</button>
        </div>
        <div class="fmu-msgs" id="fmu-msgs"></div>
        <div class="fmu-inp">
            <input id="fmu-input" placeholder="Ask about FMU..." autocomplete="off">
            <button class="fmu-snd" id="fmu-send"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg></button>
        </div>
        <div class="fmu-ft">FMU AI Assistant • Fakir Mohan University</div>
    `;
    document.body.appendChild(win);

    let isOpen = false, hist = [], loading = false;

    function toggle() { isOpen = !isOpen; bubble.classList.toggle('open',isOpen); win.classList.toggle('open',isOpen); if(isOpen) document.getElementById('fmu-input').focus(); }
    function addM(role,text) {
        const c = document.getElementById('fmu-msgs'), d = document.createElement('div');
        d.className = `fmu-m ${role}`;
        let s = text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
        s = s.replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>').replace(/\*(.*?)\*/g,'<em>$1</em>').replace(/`(.*?)`/g,'<code style="background:rgba(255,255,255,0.08);padding:1px 4px;border-radius:3px">$1</code>').replace(/\n/g,'<br>');
        d.innerHTML = s; c.appendChild(d); c.scrollTop = c.scrollHeight;
    }
    function showT() { const c=document.getElementById('fmu-msgs'),d=document.createElement('div');d.id='fmu-typing';d.className='fmu-dots';d.innerHTML='<div class="fmu-dot"></div><div class="fmu-dot"></div><div class="fmu-dot"></div>';c.appendChild(d);c.scrollTop=c.scrollHeight; }
    function hideT() { const e=document.getElementById('fmu-typing');if(e)e.remove(); }

    async function send() {
        if(loading) return;
        const inp = document.getElementById('fmu-input'), msg = inp.value.trim();
        if(!msg) return;
        addM('user',msg); hist.push({role:'user',content:msg}); inp.value=''; loading=true;
        document.getElementById('fmu-send').disabled=true; showT();
        try {
            const r = await fetch(`${apiUrl}/api/chat/${encodeURIComponent(chatbotId)}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg,history:hist.slice(-10),stream:false})});
            hideT();
            if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||'Failed');}
            const d = await r.json(), reply = d.response||'Sorry, I could not respond.';
            addM('bot',reply); hist.push({role:'assistant',content:reply});
        } catch(e) { hideT(); addM('bot',`⚠️ ${e.message}`); }
        loading=false; document.getElementById('fmu-send').disabled=false; inp.focus();
    }

    bubble.addEventListener('click',toggle);
    document.getElementById('fmu-close').addEventListener('click',toggle);
    document.getElementById('fmu-send').addEventListener('click',send);
    document.getElementById('fmu-input').addEventListener('keydown',e=>{ if(e.key==='Enter'){e.preventDefault();send();} });

    addM('bot',"Hello! 👋 I'm the FMU AI Assistant. Ask me anything about Fakir Mohan University!");
})();
