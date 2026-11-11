// Registro de acessos ao painel (v90): quem entrou, quando, de onde e que páginas abriu. Só o ADM consulta.
// Com banco: tabela painel_acessos. Sem banco: as últimas 5.000 entradas na chave "acessos".
import { banco, lerKV, salvarKV } from './tokenStore.js';

let tabelaOk = false, mem = null, memP = null;
const carregarMem = async () => { if (!mem) mem = await (memP ||= lerKV('acessos').then((x) => x || []).catch(() => [])); return mem; };
const recente = new Map(); // anti-repetição: mesma pessoa + mesmo evento em pouco tempo conta uma vez
async function tabela() {
  const p = await banco().catch(() => null);
  if (!p) return null;
  if (!tabelaOk) {
    await p.query(`CREATE TABLE IF NOT EXISTS painel_acessos (id BIGSERIAL PRIMARY KEY, usuario_id TEXT, nome TEXT, perfil TEXT, tipo TEXT, pagina TEXT, ip TEXT, disp TEXT, em TIMESTAMPTZ DEFAULT now())`);
    await p.query('CREATE INDEX IF NOT EXISTS painel_acessos_em ON painel_acessos (em DESC)');
    tabelaOk = true;
  }
  return p;
}
function dispositivo(ua = '') {
  const s = String(ua);
  const so = /iphone|ipad/i.test(s) ? 'iPhone/iPad' : /android/i.test(s) ? 'Android' : /windows/i.test(s) ? 'Windows' : /mac os/i.test(s) ? 'Mac' : /linux/i.test(s) ? 'Linux' : '';
  const nav = /edg\//i.test(s) ? 'Edge' : /opr\//i.test(s) ? 'Opera' : /chrome\//i.test(s) ? 'Chrome' : /firefox\//i.test(s) ? 'Firefox' : /safari\//i.test(s) ? 'Safari' : '';
  return [nav, so].filter(Boolean).join(' · ') || 'outro';
}
const ipDe = (req) => String(req?.headers?.['x-forwarded-for'] || req?.socket?.remoteAddress || '').split(',')[0].trim();

export async function registrar(u, tipo, req, pagina = '') {
  if (!u?.id) return;
  const chave = `${u.id}|${tipo}|${pagina}`, agora = Date.now(), janela = tipo === 'login' ? 0 : tipo === 'abriu' ? 10 * 60e3 : 5 * 60e3;
  if (janela && agora - (recente.get(chave) || 0) < janela) return;
  recente.set(chave, agora);
  const x = { usuario_id: u.id, nome: u.nome || (u.id === '__admin' ? 'Administrador (senha mestre)' : ''), perfil: u.perfil || (u.id === '__admin' ? 'adm' : ''), tipo, pagina: String(pagina || '').slice(0, 40), ip: ipDe(req).slice(0, 60), disp: dispositivo(req?.headers?.['user-agent']), em: new Date().toISOString() };
  try {
    const p = await tabela();
    if (p) { await p.query('INSERT INTO painel_acessos (usuario_id, nome, perfil, tipo, pagina, ip, disp, em) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)', [x.usuario_id, x.nome, x.perfil, x.tipo, x.pagina, x.ip, x.disp, x.em]); return; }
    await carregarMem();
    mem.push(x); if (mem.length > 5000) mem = mem.slice(-5000);
    await salvarKV('acessos', mem);
  } catch (e) { console.warn('[acessos]', e.message); }
}

export async function listar(dias = 30) {
  const desde = new Date(Date.now() - Math.min(Math.max(+dias || 30, 1), 365) * 864e5).toISOString();
  const p = await tabela();
  if (p) { const r = await p.query('SELECT usuario_id, nome, perfil, tipo, pagina, ip, disp, em FROM painel_acessos WHERE em >= $1 ORDER BY em DESC LIMIT 20000', [desde]); return r.rows.map((x) => ({ ...x, em: new Date(x.em).toISOString() })); }
  await carregarMem();
  return mem.filter((x) => x.em >= desde).reverse();
}
