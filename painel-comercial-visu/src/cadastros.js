// Cadastros novos feitos no lançamento do pedido (botão +): cliente, tipo de produto, material e cor.
// O cliente novo também é cadastrado na Conta Azul (quando conectada); o resultado fica guardado aqui.
import { lerKV, salvarKV } from './tokenStore.js';
import * as ca from './contaAzul.js';
import { config } from './config.js';

const CHAVE = 'cadastros_novos';
export const CAMPOS_CAD = ['cliente', 'tipo_produto', 'material', 'cor'];
let memo = null;
async function carregar() { if (!memo) memo = (await lerKV(CHAVE).catch(() => null)) || {}; for (const c of CAMPOS_CAD) memo[c] ||= []; return memo; }
const sem = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/\s+/g, ' ').trim();

export async function listarCadastros() { return carregar(); }

export async function incluirCadastro(b, u) {
  const campo = b?.campo;
  if (!CAMPOS_CAD.includes(campo)) throw new Error('Campo inválido.');
  const nome = String(b?.nome || '').replace(/\s+/g, ' ').trim().slice(0, 200);
  if (nome.length < 2) throw new Error('Informe o nome.');
  const d = await carregar();
  const ja = d[campo].find((x) => sem(x.nome) === sem(nome));
  const item = ja || { nome, em: new Date().toISOString(), por: u?.nome || '' };
  let conta_azul = null;
  if (campo === 'cliente') {
    Object.assign(item, { tipo: b.tipo === 'Física' ? 'Física' : 'Jurídica', documento: String(b.documento || '').trim(), email: String(b.email || '').trim(), telefone: String(b.telefone || '').trim() });
    if (b.conta_azul && !item.ca_id) {
      if (config.demo) conta_azul = { ok: true, id: 'demo-' + Date.now(), demo: true };
      else if (!(await ca.statusConexao().catch(() => ({}))).conectado) conta_azul = { ok: false, erro: 'A Conta Azul não está conectada: o cliente ficou só no painel.' };
      else {
        try { const r = await ca.criarCliente({ nome, tipo: item.tipo, documento: item.documento, email: item.email, telefone: item.telefone }); conta_azul = { ok: true, id: r.id }; }
        catch (e) { conta_azul = { ok: false, erro: e.message }; }
      }
      if (conta_azul.ok) { item.ca_id = conta_azul.id; item.ca_em = new Date().toISOString(); } else item.ca_erro = conta_azul.erro;
    }
  }
  if (!ja) d[campo].push(item);
  await salvarKV(CHAVE, d);
  return { campo, item, conta_azul, ja_existia: !!ja };
}
