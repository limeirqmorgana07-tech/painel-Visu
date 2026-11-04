// Conciliação bancária (reunião de 03/11/2026, item do financeiro): importa o extrato do banco (OFX, CSV ou Excel)
// e confere com o que foi baixado na Conta Azul (recebimentos e pagamentos) no mesmo período.
import crypto from 'node:crypto';
import XLSX from 'xlsx';
import { lerKV, salvarKV } from './tokenStore.js';
import { sem, numero, dataISO, lerCSV } from './planilha.js';

const CHAVE = 'extratos';
let memo = null; // { contas: { [conta]: { lancamentos: [...], arquivos: [...] } } }
async function carregar() { if (!memo) memo = (await lerKV(CHAVE).catch(() => null)) || { contas: {} }; return memo; }
const r2 = (v) => Math.round((Number(v) || 0) * 100) / 100;
const id = (...p) => crypto.createHash('sha1').update(p.join('|')).digest('hex').slice(0, 16);

// ---------- leitura do arquivo ----------
function lerOFX(txt) {
  const out = [];
  const blocos = txt.split(/<STMTTRN>/i).slice(1);
  const tag = (b, t) => { const m = b.match(new RegExp(`<${t}>([^<\\r\\n]*)`, 'i')); return m ? m[1].trim() : ''; };
  for (const b of blocos) {
    const d = tag(b, 'DTPOSTED'); const data = d ? `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}` : '';
    const valor = numero(tag(b, 'TRNAMT').replace(',', '.'));
    const desc = [tag(b, 'NAME'), tag(b, 'MEMO')].filter(Boolean).join(' · ');
    if (data && valor) out.push({ data, valor: r2(valor), desc, fitid: tag(b, 'FITID') });
  }
  const conta = (txt.match(/<ACCTID>([^<\r\n]*)/i) || [])[1]?.trim() || '';
  const banco = (txt.match(/<ORG>([^<\r\n]*)/i) || [])[1]?.trim() || (txt.match(/<BANKID>([^<\r\n]*)/i) || [])[1]?.trim() || '';
  return { lancamentos: out, sugestao_conta: [banco, conta].filter(Boolean).join(' ') };
}
// CSV/Excel: procura as colunas de data, descrição e valor (ou crédito/débito)
function lerTabela(matriz) {
  let h = -1, idx = {};
  for (let i = 0; i < Math.min(matriz.length, 20); i++) {
    const c = (matriz[i] || []).map(sem);
    const d = c.findIndex((x) => /^data( lancamento| do lancamento| movimento)?$/.test(x) || x === 'data'), v = c.findIndex((x) => /^valor( \(r\$\))?$|^valor do lancamento|^valor r\$/.test(x));
    const cr = c.findIndex((x) => /^credito|^entrada/.test(x)), db = c.findIndex((x) => /^debito|^saida/.test(x));
    const ds = c.findIndex((x) => /historico|descricao|lancamento|detalhe|memo/.test(x) && !/^data/.test(x) && !/^valor/.test(x));
    if (d >= 0 && (v >= 0 || cr >= 0 || db >= 0)) { h = i; idx = { d, v, cr, db, ds }; break; }
  }
  if (h < 0) throw new Error('Não achei as colunas do extrato. O arquivo precisa ter Data e Valor (ou Crédito e Débito). Se puder, exporte o extrato em OFX.');
  const out = [];
  for (const lin of matriz.slice(h + 1)) {
    if (!lin) continue;
    const data = dataISO(lin[idx.d]); if (!data) continue;
    let valor = idx.v >= 0 ? numero(lin[idx.v]) : numero(lin[idx.cr]) - Math.abs(numero(lin[idx.db]));
    const desc = idx.ds >= 0 ? String(lin[idx.ds] ?? '').trim() : '';
    if (/saldo/i.test(desc) && !/pix|ted|doc|pag|receb/i.test(desc)) continue; // linhas de saldo do dia
    if (valor) out.push({ data, valor: r2(valor), desc });
  }
  return { lancamentos: out, sugestao_conta: '' };
}
export function lerArquivoExtrato(bytes, nome = '') {
  const n = nome.toLowerCase(), txt = bytes.toString('latin1');
  if (n.endsWith('.ofx') || /<OFX>/i.test(txt)) return lerOFX(txt);
  if (n.endsWith('.csv') || n.endsWith('.txt')) { let t = bytes.toString('utf8'); if (t.includes('�')) t = txt; return lerTabela(lerCSV(t)); }
  const wb = XLSX.read(bytes, { type: 'buffer', cellDates: false });
  let melhor = null;
  for (const aba of wb.SheetNames) { try { const r = lerTabela(XLSX.utils.sheet_to_json(wb.Sheets[aba], { header: 1, raw: true, defval: '' })); if (!melhor || r.lancamentos.length > melhor.lancamentos.length) melhor = r; } catch { /* outra aba */ } }
  if (!melhor) throw new Error('Não achei as colunas do extrato (Data e Valor) em nenhuma aba.');
  return melhor;
}

// ---------- guarda ----------
export async function importarExtrato({ bytes, nome, conta, simular }, u) {
  const r = lerArquivoExtrato(bytes, nome);
  conta = String(conta || r.sugestao_conta || 'Conta sem nome').trim().slice(0, 80);
  await carregar();
  const c = memo.contas[conta] || { lancamentos: [], arquivos: [] };
  const ja = new Set(c.lancamentos.map((l) => l.id));
  // mesma data + valor + descrição repetidos no mesmo arquivo continuam separados (ordem no arquivo)
  const cont = new Map();
  const novos = r.lancamentos.map((l) => { const base = l.fitid || [l.data, l.valor, sem(l.desc)].join('|'); const k = (cont.get(base) || 0) + 1; cont.set(base, k); return { ...l, id: id(conta, base, l.fitid ? '' : k) }; }).filter((l) => !ja.has(l.id));
  const datas = r.lancamentos.map((l) => l.data).sort();
  const resumo = { conta, arquivo: nome, lidos: r.lancamentos.length, novos: novos.length, repetidos: r.lancamentos.length - novos.length, de: datas[0] || null, ate: datas[datas.length - 1] || null, entradas: r2(novos.filter((l) => l.valor > 0).reduce((s, l) => s + l.valor, 0)), saidas: r2(novos.filter((l) => l.valor < 0).reduce((s, l) => s + l.valor, 0)) };
  if (simular) return resumo;
  c.lancamentos.push(...novos.map((l) => ({ ...l, arquivo: nome })));
  c.lancamentos.sort((a, b) => a.data.localeCompare(b.data));
  c.arquivos.push({ nome, em: new Date().toISOString(), por: u?.nome || '', novos: novos.length, de: resumo.de, ate: resumo.ate });
  memo.contas[conta] = c;
  await salvarKV(CHAVE, memo);
  return resumo;
}
export async function apagarConta(conta) { await carregar(); delete memo.contas[conta]; await salvarKV(CHAVE, memo); }
export async function lancamentosExtrato(de = '0000-00-00', ate = '9999-12-31') {
  await carregar();
  return Object.entries(memo.contas).map(([conta, c]) => ({ conta, arquivos: c.arquivos, lancamentos: c.lancamentos.filter((l) => l.data >= de && l.data <= ate) }));
}
