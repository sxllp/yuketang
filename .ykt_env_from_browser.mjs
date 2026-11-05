// 从本机 Chrome（已开远程调试端口）读取雨课堂登录态，并写入 .env
// 用法: node .ykt_env_from_browser.mjs [port] [envPath]
//   port     调试端口，默认 9223
//   envPath  .env 路径，默认取「当前工作目录/.env」
// 只打印打码后的值，不把凭证输出到屏幕
import fs from 'node:fs';
import path from 'node:path';

const port = process.argv[2] || '9223';
const ENV_PATH = process.argv[3] || path.resolve(process.cwd(), '.env');

const mask = v => (!v ? '(空)' : v.length <= 8 ? v.slice(0, 2) + '***' : v.slice(0, 4) + '*'.repeat(Math.max(3, v.length - 8)) + v.slice(-4));

const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const pages = list.filter(t => t.type === 'page');
const page = pages.find(t => (t.url || '').includes('yuketang')) || pages[0];
if (!page?.webSocketDebuggerUrl) {
  console.error('没找到页面。请在打开的 Chrome 窗口里进入雨课堂课程页面。');
  process.exit(1);
}

const ws = new WebSocket(page.webSocketDebuggerUrl);
let seq = 0;
const pending = new Map();
ws.addEventListener('message', ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) {
    const { resolve, reject } = pending.get(m.id);
    pending.delete(m.id);
    m.error ? reject(new Error(JSON.stringify(m.error))) : resolve(m.result);
  }
});
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const id = ++seq;
  pending.set(id, { resolve, reject });
  ws.send(JSON.stringify({ id, method, params }));
});
await new Promise(r => ws.addEventListener('open', r, { once: true }));

await send('Runtime.enable');
await send('Network.enable');

// 一次性把 url、sign、classroom_id 都从页面里取出来
const probe = `(() => {
  const href = location.href;
  let sign = '';
  try { sign = new URL(href).searchParams.get('sign') || ''; } catch (e) {}
  if (!sign) {
    for (const u of performance.getEntriesByType('resource').map(e => e.name)) {
      const m = u.match(/[?&]sign=([^&]+)/);
      if (m) { try { sign = decodeURIComponent(m[1]); } catch (e) { sign = m[1]; } break; }
    }
  }
  let cid = '';
  try { cid = localStorage.getItem('classroom_id') || localStorage.getItem('classroomId') || ''; } catch (e) {}
  return { href, sign, cid };
})()`;
const probeRes = await send('Runtime.evaluate', { expression: probe, returnByValue: true });
const info = probeRes.result.value || {};
const url = info.href || page.url || '';

const { cookies } = await send('Network.getAllCookies');
const jar = new Map();
for (const c of cookies.filter(c => c.domain.includes('yuketang'))) jar.set(c.name, c.value);

const classroomMatch = url.match(/\/lms-graph\/(\d+)/i) || url.match(/\/(?:livecast|classroom|classrooms)\/(\d+)/i);
const classroomId = String(info.cid || (classroomMatch ? classroomMatch[1] : '') || jar.get('classroomId') || jar.get('classroom_id') || '');
const sign = info.sign || '';

const universityId = jar.get('university_id') || jar.get('uv_id') || '';
const found = {
  CLASSROOM_ID: classroomId,
  SIGN: sign,
  UNIVERSITY_ID: String(universityId || ''),
  CSRF_TOKEN: jar.get('csrftoken') || '',
  SESSION_ID: jar.get('sessionid') || '',
};

console.log('当前页面:', url);
console.log('Cookie 命中:', [...jar.keys()].join(', ') || '(无)');
console.log('--- 取到的值 ---');
for (const [k, v] of Object.entries(found)) {
  const ok = v && !v.startsWith('<');
  console.log(`${ok ? '[OK]  ' : '[缺失]'} ${k.padEnd(13)} ${ok ? mask(v) + '  (len=' + v.length + ')' : '页面还没到课程内页 / 未登录'}`);
}

const missing = Object.entries(found).filter(([, v]) => !v).map(([k]) => k);
if (missing.length) {
  console.log('\n还缺:', missing.join(', '));
  console.log('请在 Chrome 窗口里: 扫码登录 -> 进「我听的课」-> 点进目标课程 -> 再点开一节课，让地址栏出现 /pro/livecast/...?sign=...');  ws.close();
  process.exit(2);
}

if (!/^\d+$/.test(found.CLASSROOM_ID) || !/^\d+$/.test(found.UNIVERSITY_ID)) {
  console.log('\n格式异常: CLASSROOM_ID / UNIVERSITY_ID 必须是纯数字');
  ws.close();
  process.exit(3);
}

// 按行替换 .env，保留注释与其它配置
const lines = fs.readFileSync(ENV_PATH, 'utf8').split(/\r?\n/);
const updated = [];
const out = lines.map(line => {
  const m = line.match(/^(\s*)([A-Z_]+)\s*=/);
  if (!m) return line;
  const key = m[2];
  if (key in found && found[key]) {
    updated.push(key);
    return `${m[1]}${key}=${found[key]}`;
  }
  return line;
});
fs.writeFileSync(ENV_PATH, out.join('\n'), 'utf8');
console.log('\n已写入 .env:', updated.join(', '));
ws.close();
