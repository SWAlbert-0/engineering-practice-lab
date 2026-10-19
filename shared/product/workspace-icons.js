/* Small, local icon vocabulary; decorative SVGs inherit the action label. */
'use strict';
window.WorkspaceUI={icon(name,size=20){const paths={
 search:'<circle cx="10.8" cy="10.8" r="6.5"/><path d="m16 16 4.3 4.3"/>',
 file:'<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Z"/><path d="M14 3v6h6M8 13h8M8 17h5"/>',
 layers:'<path d="m12 3 10 5-10 5L2 8Zm-9 9 9 5 9-5M3 16l9 5 9-5"/>',
 home:'<path d="m3 10 9-7 9 7v10H3Z"/><path d="M9 20v-7h6v7"/>',
 check:'<path d="m5 12 4 4L19 6"/>',
 checklist:'<rect x="5" y="4" width="15" height="17" rx="3"/><path d="M9 2h6v4H9ZM8 11l1.5 1.5L12 10m-4 6 1.5 1.5L12 15m2-4h3m-3 5h3"/>',
 upload:'<path d="M12 16V3m-5 5 5-5 5 5M4 15v5h16v-5"/>',
 clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
 settings:'<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3" fill="currentColor" stroke="none"/><circle cx="15" cy="17" r="3" fill="currentColor" stroke="none"/>',
 book:'<path d="M12 5c-3-2-7-2-10-1v15c3-1 7-1 10 1 3-2 7-2 10-1V4c-3-1-7-1-10 1Zm0 0v15"/>',
 arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>',
 info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/>',
 plus:'<path d="M12 4v16M4 12h16"/>',
 grid:'<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',
 flask:'<path d="M9 3h6m-5 0v7L4 20h16l-6-10V3M8 15h8"/>',
 shield:'<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z"/><path d="m8 12 3 3 5-6"/>',
 pencil:'<path d="m16 3 5 5L9 20l-6 1 1-6Zm-1 2 5 5"/>',
 branch:'<circle cx="6" cy="5" r="2"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="5" r="2"/><path d="M6 7v10m12-10c0 7-12 3-12 10"/>',
 publish:'<path d="M5 12H3v9h18v-9h-2M12 16V3m-5 5 5-5 5 5"/>',
 list:'<path d="M9 5h12M9 12h12M9 19h12M3 5h.01M3 12h.01M3 19h.01"/>',
 quote:'<path d="M9 5H3v8h6v-2H5V7h4Zm12 0h-6v8h6v-2h-4V7h4ZM7 13l-3 6m15-6-3 6"/>'
 };return `<svg class="ui-icon" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${paths[name]||paths.file}</svg>`;}};
