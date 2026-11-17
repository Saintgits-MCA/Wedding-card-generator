/* Wedding Card Studio - browser-side visual editor. No Node/npm required. */
(() => {
  'use strict';
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => [...root.querySelectorAll(s)];
  const pagesEl = $('.pages');
  if (!pagesEl) return;

  const root = document.documentElement;
  const stage = $('#preview-stage');
  const pagePicker = $('#pagePicker');
  const sizeSelect = $('#cardSize');
  const widthInput = $('#customWidth');
  const heightInput = $('#customHeight');
  const orientation = $('#orientation');
  let selected = null;
  let activePage = 0;
  let history = [];
  let historyIndex = -1;
  let pointerState = null;
  let suppressHistory = false;
  const MAX_HISTORY = 60;

  const setVar = (name, value) => root.style.setProperty(name, value);
  window.setVar = setVar;
  window.setFont = (name, font) => setVar(name, `"${font}", serif`);
  window.setBorder = (value) => {
    $$('.frame').forEach(el => {
      el.classList.remove('b-double','b-temple','b-single','b-dots','b-corners','b-none');
      el.classList.add(`b-${value}`);
      if(value==='corners' && !el.querySelector('.corner')) ['c1','c2','c3','c4'].forEach(cls=>{const c=document.createElement('span');c.className=`corner ${cls}`;c.textContent='❖';el.append(c);c.classList.add('editable');});
      el.querySelectorAll('.corner').forEach(c => c.hidden = value !== 'corners');
    });
    pushHistory();
  };

  function currentSheets() { return $$('.sheet', pagesEl); }
  function cleanClone(el) {
    const clone = el.cloneNode(true);
    clone.querySelectorAll('.resize-handle').forEach(n => n.remove());
    clone.querySelectorAll('.selected').forEach(n => n.classList.remove('selected'));
    clone.querySelectorAll('[contenteditable="true"]').forEach(n => n.removeAttribute('contenteditable'));
    return clone;
  }
  function snapshot() {
    return {
      pages: currentSheets().map(s => cleanClone(s).outerHTML),
      width: root.style.getPropertyValue('--card-width') || '148mm',
      height: root.style.getPropertyValue('--card-height') || '210mm',
      paper: getComputedStyle(root).getPropertyValue('--paper').trim(),
      ink: getComputedStyle(root).getPropertyValue('--ink').trim(),
      accent: getComputedStyle(root).getPropertyValue('--accent').trim(),
      display: getComputedStyle(root).getPropertyValue('--display').trim(),
      body: getComputedStyle(root).getPropertyValue('--body').trim(),
      ml: getComputedStyle(root).getPropertyValue('--mlf').trim(),
      zoom: root.style.getPropertyValue('--zoom') || '0.8'
    };
  }
  function pushHistory() {
    if (suppressHistory) return;
    const snap = snapshot();
    const encoded = JSON.stringify(snap);
    if (historyIndex >= 0 && JSON.stringify(history[historyIndex]) === encoded) return;
    history = history.slice(0, historyIndex + 1);
    history.push(snap);
    if (history.length > MAX_HISTORY) history.shift();
    historyIndex = history.length - 1;
    updateHistoryButtons();
  }
  function restore(snap) {
    suppressHistory = true;
    pagesEl.innerHTML = snap.pages.join('');
    setVar('--card-width', snap.width); setVar('--card-height', snap.height);
    setVar('--paper', snap.paper); setVar('--ink', snap.ink); setVar('--accent', snap.accent);
    if (snap.display) setVar('--display', snap.display);
    if (snap.body) setVar('--body', snap.body);
    if (snap.ml) setVar('--mlf', snap.ml);
    setVar('--zoom', snap.zoom);
    widthInput.value = parseFloat(snap.width); heightInput.value = parseFloat(snap.height);
    orientation.value = parseFloat(snap.width) > parseFloat(snap.height) ? 'landscape' : 'portrait'; sizeSelect.value = 'custom';
    updatePrintSize(); initEditable(); refreshPagePicker(); selectElement(null);
    suppressHistory = false;
  }
  function updateHistoryButtons() {
    $('#undoBtn').disabled = historyIndex <= 0;
    $('#redoBtn').disabled = historyIndex >= history.length - 1;
  }
  function undo() { if (historyIndex > 0) { historyIndex--; restore(history[historyIndex]); updateHistoryButtons(); } }
  function redo() { if (historyIndex < history.length - 1) { historyIndex++; restore(history[historyIndex]); updateHistoryButtons(); } }

  function applyDimensions(w, h) {
    const landscape = orientation.value === 'landscape';
    const a = landscape ? Math.max(w,h) : Math.min(w,h);
    const b = landscape ? Math.min(w,h) : Math.max(w,h);
    widthInput.value = a; heightInput.value = b;
    setVar('--card-width', `${a}mm`); setVar('--card-height', `${b}mm`);
    updatePrintSize();
  }
  function updatePrintSize() {
    const w = parseFloat(widthInput.value) || 148;
    const h = parseFloat(heightInput.value) || 210;
    let style = $('#dynamicPageRule');
    if (!style) { style = document.createElement('style'); style.id = 'dynamicPageRule'; document.head.appendChild(style); }
    style.textContent = `@media print { @page { size: ${w}mm ${h}mm; margin: 0; } }`;
  }
  sizeSelect.addEventListener('change', () => {
    if (sizeSelect.value === 'custom') return;
    const [w,h] = sizeSelect.value.split(',').map(Number);
    applyDimensions(w,h); pushHistory();
  });
  [widthInput,heightInput].forEach(input => input.addEventListener('change', () => {
    const w = Math.min(420, Math.max(50, Number(widthInput.value) || 148));
    const h = Math.min(594, Math.max(50, Number(heightInput.value) || 210));
    sizeSelect.value = 'custom'; applyDimensions(w,h); pushHistory();
  }));
  orientation.addEventListener('change', () => { applyDimensions(Number(widthInput.value)||148, Number(heightInput.value)||210); pushHistory(); });

  function refreshPagePicker() {
    const count = currentSheets().length;
    pagePicker.innerHTML = '';
    currentSheets().forEach((_, i) => {
      const op = document.createElement('option'); op.value = i; op.textContent = `Page ${i+1}`; pagePicker.append(op);
    });
    activePage = Math.min(activePage, count - 1);
    pagePicker.value = String(activePage);
    $('#deletePageBtn').disabled = count <= 1;
  }
  function goPage(index) {
    const sheets = currentSheets();
    activePage = Math.max(0, Math.min(index, sheets.length - 1));
    pagePicker.value = String(activePage);
    sheets.forEach((s,i) => s.style.display = i === activePage ? '' : 'none');
    selectElement(null);
  }
  pagePicker.addEventListener('change', () => goPage(Number(pagePicker.value)));
  $('#addPageBtn').addEventListener('click', () => {
    pushHistory();
    const source = currentSheets()[activePage] || currentSheets()[0];
    const copy = cleanClone(source);
    pagesEl.append(copy); activePage = currentSheets().length - 1;
    initEditable(); refreshPagePicker(); goPage(activePage); pushHistory();
  });
  $('#duplicatePageBtn').addEventListener('click', () => $('#addPageBtn').click());
  $('#deletePageBtn').addEventListener('click', () => {
    const sheets = currentSheets(); if (sheets.length <= 1) return;
    if (!confirm(`Delete page ${activePage + 1}?`)) return;
    pushHistory(); sheets[activePage].remove(); activePage = Math.max(0, activePage - 1);
    refreshPagePicker(); goPage(activePage); pushHistory();
  });

  function selectElement(el) {
    if (selected) selected.classList.remove('selected');
    selected = el;
    if (!selected) { $('#selectionHint').textContent = 'Select an item on the card. Double-click text to edit it.'; return; }
    selected.classList.add('selected');
    $('#selectionHint').textContent = selected.classList.contains('custom-image') ? 'Photo selected — drag to move or use the handle to resize.' : 'Selected. Drag to move, use the blue handle to resize, double-click text to edit.';
    const cs = getComputedStyle(selected);
    const family = cs.fontFamily.split(',')[0].replace(/["']/g,'').trim();
    $('#objectFont').value = [...$('#objectFont').options].some(o => o.value === family) ? family : '';
    $('#objectSize').value = Math.round(parseFloat(cs.fontSize) || 24);
    $('#objectColor').value = toHex(cs.color) || '#222222';
    $('#objectAlign').value = cs.textAlign || 'center';
    $('#objectRotate').value = selected.dataset.rotate || 0;
    $('#rotateLabel').textContent = `${$('#objectRotate').value}°`;
  }
  function toHex(rgb) {
    const m = rgb.match(/\d+/g); if (!m || m.length < 3) return null;
    return '#' + m.slice(0,3).map(v => Number(v).toString(16).padStart(2,'0')).join('');
  }
  function addHandle(el) {
    if (!el.querySelector(':scope > .resize-handle')) {
      const h = document.createElement('span'); h.className = 'resize-handle'; h.setAttribute('aria-hidden','true'); el.append(h);
    }
  }
  function initEditable() {
    currentSheets().forEach(sheet => {
      const targets = $$('.lang > *, .frame > .phone, .frame > .corner', sheet);
      targets.forEach(el => {
        if (el.classList.contains('resize-handle')) return;
        el.classList.add('editable');
        if (!el.classList.contains('corner')) el.style.position = 'relative';
        if (!el.classList.contains('corner')) addHandle(el);
      });
      $$('.custom-object,.custom-image', sheet).forEach(el => { el.classList.add('editable'); addHandle(el); });
    });
  }
  function localPointScale() { return Number(getComputedStyle(root).getPropertyValue('--zoom').trim()) || 1; }

  pagesEl.addEventListener('click', ev => {
    const el = ev.target.closest('.editable');
    if (el) { ev.stopPropagation(); selectElement(el); }
    else if (ev.target.closest('.sheet')) selectElement(null);
  });
  pagesEl.addEventListener('dblclick', ev => {
    const el = ev.target.closest('.editable');
    if (!el || el.classList.contains('custom-image')) return;
    pushHistory(); el.setAttribute('contenteditable','true'); el.focus();
    const range = document.createRange(); range.selectNodeContents(el); range.collapse(false);
    const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(range);
  });
  pagesEl.addEventListener('focusout', ev => {
    if (ev.target.matches('.editable[contenteditable="true"]')) { ev.target.removeAttribute('contenteditable'); pushHistory(); }
  });

  pagesEl.addEventListener('pointerdown', ev => {
    const el = ev.target.closest('.editable');
    if (!el || ev.button !== 0 || el.isContentEditable) return;
    selectElement(el);
    const resize = ev.target.classList.contains('resize-handle');
    pushHistory();
    pointerState = { el, resize, x: ev.clientX, y: ev.clientY, dx: Number(el.dataset.dx)||0, dy: Number(el.dataset.dy)||0, scale: Number(el.dataset.scale)||1 };
    ev.preventDefault();
    el.setPointerCapture?.(ev.pointerId);
  });
  pagesEl.addEventListener('pointermove', ev => {
    if (!pointerState) return;
    const p = pointerState, factor = localPointScale();
    if (p.resize) {
      const delta = Math.max(-100, (ev.clientX-p.x + ev.clientY-p.y) / 2 / factor);
      p.el.dataset.scale = String(Math.max(.25, Math.min(4, p.scale + delta / 100)));
      p.el.style.setProperty('--object-scale', p.el.dataset.scale);
    } else {
      const dx = p.dx + (ev.clientX-p.x)/factor, dy = p.dy + (ev.clientY-p.y)/factor;
      p.el.dataset.dx = String(dx); p.el.dataset.dy = String(dy);
      p.el.style.setProperty('--dx', `${dx}px`); p.el.style.setProperty('--dy', `${dy}px`);
    }
  });
  function finishPointer() { if (pointerState) { pointerState = null; pushHistory(); } }
  pagesEl.addEventListener('pointerup', finishPointer);
  pagesEl.addEventListener('pointercancel', finishPointer);

  function requireSelection() { if (!selected) { alert('Please select an item on the card first.'); return false; } return true; }
  $('#objectFont').addEventListener('change', e => { if(requireSelection()){ selected.style.fontFamily = e.target.value ? `"${e.target.value}", serif` : ''; pushHistory(); } });
  $('#objectSize').addEventListener('change', e => { if(requireSelection()){ selected.style.fontSize = `${Math.max(6,Math.min(120,Number(e.target.value)||24))}px`; pushHistory(); } });
  $('#objectColor').addEventListener('input', e => { if(selected) selected.style.color = e.target.value; });
  $('#objectColor').addEventListener('change', pushHistory);
  $('#objectAlign').addEventListener('change', e => { if(requireSelection()){ selected.style.textAlign = e.target.value; pushHistory(); } });
  $('#objectRotate').addEventListener('input', e => { if(selected){ const n=Number(e.target.value); selected.dataset.rotate=n; selected.style.rotate=`${n}deg`; $('#rotateLabel').textContent=`${n}°`; } });
  $('#objectRotate').addEventListener('change', pushHistory);
  $('#boldText').addEventListener('click', () => { if(requireSelection()){ selected.style.fontWeight = getComputedStyle(selected).fontWeight==='700'?'400':'700'; pushHistory(); } });
  $('#italicText').addEventListener('click', () => { if(requireSelection()){ selected.style.fontStyle = getComputedStyle(selected).fontStyle==='italic'?'normal':'italic'; pushHistory(); } });
  $('#duplicateObject').addEventListener('click', () => {
    if(!requireSelection()) return; pushHistory();
    const copy = cleanClone(selected); copy.classList.remove('selected'); copy.dataset.dx = String((Number(selected.dataset.dx)||0)+16); copy.dataset.dy=String((Number(selected.dataset.dy)||0)+16);
    copy.style.setProperty('--dx',`${copy.dataset.dx}px`); copy.style.setProperty('--dy',`${copy.dataset.dy}px`);
    selected.parentElement.append(copy); initEditable(); selectElement(copy); pushHistory();
  });
  $('#deleteObject').addEventListener('click', () => { if(requireSelection()){pushHistory(); selected.remove(); selectElement(null); pushHistory();} });

  $('#addTextBtn').addEventListener('click', () => {
    pushHistory(); const sheet=currentSheets()[activePage]; const frame=$('.frame',sheet);
    const el=document.createElement('div'); el.className='editable custom-object'; el.textContent='Double-click to edit this text';
    el.style.fontFamily='var(--display)'; el.style.fontSize='22px'; el.style.color='var(--ink)'; el.dataset.dx='0'; el.dataset.dy='0';
    frame.append(el); initEditable(); selectElement(el); el.setAttribute('contenteditable','true'); el.focus(); pushHistory();
  });
  $('#addImageBtn').addEventListener('click', () => $('#imageUpload').click());
  $('#imageUpload').addEventListener('change', ev => {
    const file=ev.target.files?.[0]; if(!file) return;
    if(!file.type.startsWith('image/')) { alert('Choose an image file.'); return; }
    const reader=new FileReader(); reader.onload=()=>{
      pushHistory(); const sheet=currentSheets()[activePage]; const frame=$('.frame',sheet);
      const wrap=document.createElement('div'); wrap.className='editable custom-image'; wrap.dataset.dx='0'; wrap.dataset.dy='0';
      const img=document.createElement('img'); img.src=reader.result; img.alt='Uploaded decoration'; wrap.append(img);
      frame.append(wrap); initEditable(); selectElement(wrap); pushHistory(); ev.target.value='';
    }; reader.readAsDataURL(file);
  });

  // Global styling controls.
  $$('.input-group input[type="color"]').forEach(input => input.addEventListener('change', () => pushHistory()));
  $('#bodyFont').addEventListener('change', e => { setVar('--body',`"${e.target.value}", serif`); pushHistory(); });
  $('#mlFont').addEventListener('change', e => { setVar('--mlf',`"${e.target.value}", serif`); pushHistory(); });
  $('#displayFont').addEventListener('change', e => { setVar('--display',`"${e.target.value}", serif`); pushHistory(); });
  $('#palettePreset').addEventListener('change', e => {
    const palettes={ivory:['#FFF8E8','#6E1E1E','#B8860B'],rose:['#FFF5F5','#7A1F3D','#C58A9B'],sage:['#F4F7F0','#294936','#A58A45'],navy:['#F4F6FA','#1F3556','#9AA7B8'],blush:['#FFF4F0','#65334F','#C58A78']};
    const p=palettes[e.target.value]; if(!p) return; setVar('--paper',p[0]);setVar('--ink',p[1]);setVar('--accent',p[2]);
    const colors=$$('.sidebar input[type="color"]'); if(colors[0])colors[0].value=p[0];if(colors[1])colors[1].value=p[2];if(colors[2])colors[2].value=p[1]; pushHistory();
  });
  $('#patternStyle').addEventListener('change', e => { currentSheets().forEach(s => {s.classList.remove('pat-none','pat-dots','pat-lines','pat-vignette');s.classList.add(`pat-${e.target.value}`);}); pushHistory(); });
  $('#dividerStyle').addEventListener('change', e => { $$('.dv').forEach(el => {el.classList.remove('dv-line','dv-diamond','dv-dots'); if(e.target.value!=='none')el.classList.add(`dv-${e.target.value}`); el.hidden=e.target.value==='none';}); pushHistory(); });
  $('#canvasZoom').addEventListener('input', e => { setVar('--zoom',e.target.value); $('#zoom-label').textContent=`${Math.round(Number(e.target.value)*100)}%`; });
  $('#canvasZoom').addEventListener('change', pushHistory);
  // Existing inline colour inputs use setVar; record their final values for undo.
  $$('.sidebar input[type="color"]').forEach(input => input.addEventListener('change', pushHistory));

  $('#undoBtn').addEventListener('click', undo); $('#redoBtn').addEventListener('click', redo);
  document.addEventListener('keydown', ev => {
    if (document.activeElement.isContentEditable) return;
    if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase()==='z') { ev.preventDefault(); ev.shiftKey ? redo() : undo(); }
    if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase()==='y') { ev.preventDefault(); redo(); }
    if ((ev.key==='Delete' || ev.key==='Backspace') && selected && !selected.isContentEditable && !['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)) $('#deleteObject').click();
  });

  $('#printPdf').addEventListener('click', () => { updatePrintSize(); currentSheets().forEach(s => s.style.display=''); window.print(); });
  window.addEventListener('afterprint', () => goPage(activePage));
  $('#downloadPng').addEventListener('click', async function () {
    const button=this, sheets=currentSheets();
    const oldZoom=root.style.getPropertyValue('--zoom') || '0.8';
    const oldDisplays=sheets.map(s=>s.style.display);
    if (typeof html2canvas === 'undefined') { alert('PNG export library did not load.'); return; }
    button.disabled=true; button.textContent='Preparing PNG…'; document.body.classList.add('exporting');
    try {
      if(document.fonts?.ready) await document.fonts.ready;
      setVar('--zoom','1');
      sheets.forEach(s => s.style.display='');
      for(let i=0;i<sheets.length;i++) {
        const canvas=await html2canvas(sheets[i],{scale:3,useCORS:true,backgroundColor:null,logging:false,width:sheets[i].offsetWidth,height:sheets[i].offsetHeight});
        const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
        if(!blob) throw new Error('Could not create the PNG file.');
        const url=URL.createObjectURL(blob), link=document.createElement('a');
        link.href=url; link.download=`wedding-invitation-page-${i+1}.png`; document.body.append(link); link.click(); link.remove();
        setTimeout(()=>URL.revokeObjectURL(url),2500);
        await new Promise(r=>setTimeout(r,350));
      }
    } catch(err) { console.error(err); alert(`PNG export failed: ${err.message}`); }
    finally { setVar('--zoom',oldZoom); sheets.forEach((s,i)=>{s.style.display=oldDisplays[i];}); goPage(activePage); document.body.classList.remove('exporting'); button.disabled=false; button.textContent='📷 Download PNG'; }
  });

  // Browser-local recovery for a design the customer was already editing.
  const saveKey = 'wedding-card-studio:' + (document.body.dataset.saveKey || document.title);
  function saveLocal() {
    try { localStorage.setItem(saveKey, JSON.stringify(snapshot())); } catch (_) { /* storage may be disabled or full */ }
  }
  const originalPush = pushHistory;
  pushHistory = function(){ originalPush(); saveLocal(); };
  window.addEventListener('beforeunload', saveLocal);

  // Initial card dimensions and history baseline.
  setVar('--card-width','148mm'); setVar('--card-height','210mm');
  updatePrintSize(); initEditable(); refreshPagePicker(); goPage(0);
  pushHistory();
  // try {
  //   const saved=localStorage.getItem(saveKey);
  //   if(saved) {
  //     if(confirm('A previous edit of this invitation was saved in this browser. Restore it?')) {
  //       const parsed=JSON.parse(saved); restore(parsed); history=[parsed]; historyIndex=0; updateHistoryButtons();
  //     } else { localStorage.removeItem(saveKey); }
  //   }
  // } catch (_) { /* ignore corrupt local recovery data */ }
})();
