// Usuários do painel: perfis Diretor (vê os dashboards) e ADM (vê tudo, gerencia usuários e a conexão com a Conta Azul).
// Ninguém recebe senha pronta: cada pessoa recebe um link de convite pessoal e cria a própria senha.
// As senhas ficam só como hash (scrypt) no banco (DATABASE_URL) ou no arquivo local.
import crypto from 'node:crypto';
import { config } from './config.js';
import { lerKV, salvarKV } from './tokenStore.js';

export const PERFIS = { diretor: 'Diretor', adm: 'ADM' };
const CHAVE = 'usuarios';
const VALIDADE_CONVITE_DIAS = 7;

// Perfis iniciais pedidos pela Seja Expert: dois diretores da Visu e dois administradores (Seja Expert).
// Nomes e e-mails podem ser ajustados na página Usuários ou pela variável USUARIOS_JSON.
const INICIAIS = [
  { id: 'diretor-1', nome: 'Diretor 1', email: '', perfil: 'diretor' },
  { id: 'diretor-2', nome: 'Diretor 2', email: '', perfil: 'diretor' },
  { id: 'morgana', nome: 'Morgana Limeira', email: 'morgana.limeira@sejaexpergestao.com', perfil: 'adm' },
  { id: 'gestor-seja-expert', nome: 'Gestor Seja Expert', email: '', perfil: 'adm' },
];

const b64 = (s) => Buffer.from(s).toString('base64url');
const de64 = (s) => Buffer.from(s, 'base64url').toString();
const hmac = (s) => crypto.createHmac('sha256', config.segredoSessao).update(s).digest('base64url');
const igual = (a, b) => a.length === b.length && crypto.timingSafeEqual(Buffer.from(a), Buffer.from(b));
const limpo = (u) => ({ id: u.id, nome: u.nome, email: u.email || '', perfil: u.perfil, senha_criada: !!u.hash && !u.temporaria, temporaria: !!(u.hash && u.temporaria), temp_expira_em: u.temporaria && u.temp_exp ? new Date(u.temp_exp).toISOString() : null, ultimo_acesso: u.ultimo_acesso || null, criado_em: u.criado_em || null });

let cache = null;
async function carregar() {
  if (cache) return cache;
  let lista = await lerKV(CHAVE).catch(() => null);
  if (!Array.isArray(lista)) {
    let base = INICIAIS;
    try { if (process.env.USUARIOS_JSON) base = JSON.parse(process.env.USUARIOS_JSON); } catch { console.warn('USUARIOS_JSON inválido; usando os perfis iniciais.'); }
    lista = base.map((u) => ({ ...u, ver: 0, criado_em: new Date().toISOString() }));
    await salvarKV(CHAVE, lista).catch(() => {});
  }
  cache = lista;
  return cache;
}
async function gravar(lista) { cache = lista; await salvarKV(CHAVE, lista); }

export async function listar() { return (await carregar()).map(limpo); }
export async function porId(id) { return (await carregar()).find((u) => u.id === id) || null; }

export async function salvar({ id, nome, email, perfil }) {
  const lista = await carregar();
  nome = String(nome || '').trim(); email = String(email || '').trim().toLowerCase();
  if (!nome) throw new Error('Informe o nome.');
  if (!PERFIS[perfil]) throw new Error('Perfil inválido.');
  if (email && lista.some((u) => u.email === email && u.id !== id)) throw new Error('Já existe um usuário com esse e-mail.');
  let u = id && lista.find((x) => x.id === id);
  if (u) Object.assign(u, { nome, email, perfil });
  else {
    const base = nome.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'usuario';
    let novo = base, n = 2; while (lista.some((x) => x.id === novo)) novo = `${base}-${n++}`;
    u = { id: novo, nome, email, perfil, ver: 0, criado_em: new Date().toISOString() };
    lista.push(u);
  }
  await gravar(lista);
  return limpo(u);
}

export async function remover(id) {
  const lista = await carregar();
  await gravar(lista.filter((u) => u.id !== id));
}

// ---------- convite: link pessoal para criar (ou redefinir) a senha ----------
export async function gerarConvite(id) {
  const lista = await carregar();
  const u = lista.find((x) => x.id === id);
  if (!u) throw new Error('Usuário não encontrado.');
  u.ver = (u.ver || 0) + 1; // invalida links e sessões anteriores dessa pessoa
  u.hash = null; u.salt = null; u.temporaria = false; u.temp_exp = null;
  await gravar(lista);
  const exp = Date.now() + VALIDADE_CONVITE_DIAS * 864e5;
  const corpo = b64(JSON.stringify({ id: u.id, v: u.ver, exp }));
  return { link: `${config.urlPublica}/convite/${corpo}.${hmac('convite.' + corpo)}`, expira_em: new Date(exp).toISOString(), usuario: limpo(u) };
}

export async function lerConvite(token) {
  const [corpo, sig] = String(token || '').split('.');
  if (!corpo || !sig || !igual(sig, hmac('convite.' + corpo))) return { erro: 'Link inválido.' };
  let d; try { d = JSON.parse(de64(corpo)); } catch { return { erro: 'Link inválido.' }; }
  if (d.exp < Date.now()) return { erro: 'Este link expirou. Peça um novo ao administrador do painel.' };
  const u = await porId(d.id);
  if (!u || (u.ver || 0) !== d.v) return { erro: 'Este link já foi usado ou foi substituído por um mais novo. Peça um novo ao administrador do painel.' };
  return { usuario: u };
}

const hashSenha = (senha, salt) => crypto.scryptSync(String(senha), salt, 64).toString('base64');

export async function aceitarConvite(token, { senha, email }) {
  const r = await lerConvite(token);
  if (r.erro) throw new Error(r.erro);
  if (String(senha || '').length < 8) throw new Error('A senha precisa ter pelo menos 8 caracteres.');
  const lista = await carregar();
  const u = lista.find((x) => x.id === r.usuario.id);
  email = String(email || u.email || '').trim().toLowerCase();
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) throw new Error('Informe um e-mail válido.');
  if (lista.some((x) => x.email === email && x.id !== u.id)) throw new Error('Esse e-mail já está em uso por outro usuário.');
  u.email = email;
  u.salt = crypto.randomBytes(16).toString('base64');
  u.hash = hashSenha(senha, u.salt);
  u.temporaria = false; u.temp_exp = null;
  u.ver = (u.ver || 0) + 1; // o link deixa de valer
  await gravar(lista);
  return u;
}

// Retorna { u } ou { erro }. Senha temporária vale 7 dias e obriga a trocar no primeiro acesso.
export async function autenticar(email, senha) {
  email = String(email || '').trim().toLowerCase();
  const u = (await carregar()).find((x) => x.email === email && x.hash);
  if (!u) { hashSenha(senha, 'x'); return { erro: 'E-mail ou senha incorretos.' }; }
  if (!igual(hashSenha(senha, u.salt), u.hash)) return { erro: 'E-mail ou senha incorretos.' };
  if (u.temporaria && u.temp_exp && u.temp_exp < Date.now()) return { erro: 'Sua senha temporária expirou. Peça uma nova ao administrador do painel.' };
  return { u };
}

// ---------- senha temporária (o ADM gera e envia; a pessoa troca no primeiro acesso) ----------
const LETRAS = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789';
const bloco = (n) => Array.from(crypto.randomBytes(n), (b) => LETRAS[b % LETRAS.length]).join('');
export async function gerarSenhaTemporaria(id) {
  const lista = await carregar();
  const u = lista.find((x) => x.id === id);
  if (!u) throw new Error('Usuário não encontrado.');
  if (!u.email) throw new Error('Cadastre o e-mail da pessoa antes (botão Editar). Ele será o login.');
  const senha = `Visu-${bloco(4)}-${bloco(4)}`;
  u.salt = crypto.randomBytes(16).toString('base64');
  u.hash = hashSenha(senha, u.salt);
  u.temporaria = true;
  u.temp_exp = Date.now() + VALIDADE_CONVITE_DIAS * 864e5;
  u.ver = (u.ver || 0) + 1; // derruba sessões e links anteriores
  await gravar(lista);
  return { senha, login: config.urlPublica, email: u.email, expira_em: new Date(u.temp_exp).toISOString(), usuario: limpo(u) };
}

export async function trocarSenha(id, { atual, nova }) {
  const lista = await carregar();
  const u = lista.find((x) => x.id === id);
  if (!u) throw new Error('Usuário não encontrado.');
  if (!u.temporaria && !igual(hashSenha(atual || '', u.salt), u.hash)) throw new Error('A senha atual está incorreta.');
  if (String(nova || '').length < 8) throw new Error('A nova senha precisa ter pelo menos 8 caracteres.');
  if (u.temporaria && igual(hashSenha(nova, u.salt), u.hash)) throw new Error('A nova senha precisa ser diferente da temporária.');
  u.salt = crypto.randomBytes(16).toString('base64');
  u.hash = hashSenha(nova, u.salt);
  u.temporaria = false; u.temp_exp = null;
  u.ver = (u.ver || 0) + 1;
  await gravar(lista);
  return u;
}

export async function registrarAcesso(id) {
  const lista = await carregar();
  const u = lista.find((x) => x.id === id);
  if (u) { u.ultimo_acesso = new Date().toISOString(); await gravar(lista).catch(() => {}); }
}

// ---------- sessão ----------
// Cookie: base64(id.ver.exp).assinatura. Trocar a senha (novo convite) derruba as sessões antigas.
export function cookieDeSessao(u, horas = 12) {
  const corpo = b64(JSON.stringify({ id: u.id, v: u.ver || 0, exp: Date.now() + horas * 3600e3 }));
  return `${corpo}.${hmac('sessao.' + corpo)}`;
}
export async function lerSessao(valor) {
  const [corpo, sig] = String(valor || '').split('.');
  if (!corpo || !sig || !igual(sig, hmac('sessao.' + corpo))) return null;
  let d; try { d = JSON.parse(de64(corpo)); } catch { return null; }
  if (d.exp < Date.now()) return null;
  if (d.id === '__admin') return { id: '__admin', nome: 'Administrador (senha mestra)', perfil: 'adm', email: '' };
  const u = await porId(d.id);
  if (!u || (u.ver || 0) !== d.v || !u.hash) return null;
  return u;
}
export const ADMIN_MESTRE = { id: '__admin', ver: 0 };
export const bancoConfigurado = () => !!config.databaseUrl;
