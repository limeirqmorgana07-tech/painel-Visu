// Painel Comercial Visu — servidor (Seja Expert)
import express from 'express';
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { config, redirectUri } from './src/config.js';
import * as ca from './src/contaAzul.js';
import { dadosDeVendas, faixasComissao, FAIXAS_PADRAO, remontarVendas, vendasContaAzulEmCache } from './src/vendas.js';
import * as pedidos from './src/pedidos.js';
import * as anexos from './src/anexos.js';
import * as receber from './src/receber.js';
import * as notasCA from './src/notasCA.js';
import { dadosFinanceiros } from './src/financeiro.js';
import { planilhaConfigurada } from './src/planilha.js';
import * as google from './src/google.js';
import * as pscript from './src/planilhaScript.js';
import * as extrato from './src/extrato.js';
import * as divergencias from './src/divergencias.js';
import * as cadastros from './src/cadastros.js';
import * as envioCA from './src/envioContaAzul.js';
import { gerarDemoParcelas, gerarDemoContaAzul, gerarDemoPlanilha } from './src/demo.js';
import * as usuarios from './src/usuarios.js';
import { paginasDe, veFinanceiro, veVendas, definirPerfis, padraoDe, perfisPersonalizados, padroesOriginais, BLOCOS, blocosDe, definirBlocos, blocosPersonalizados, blocosPadrao, vePedidos, veHistorico } from './src/paginas.js';
import { statusBanco, lerKV, salvarKV } from './src/tokenStore.js';

const raiz = path.dirname(fileURLToPath(import.meta.url));

// Um erro inesperado em segundo plano (API fora do ar, banco instável) não pode derrubar o painel inteiro.
process.on('unhandledRejection', (e) => console.error('[erro em segundo plano]', e?.message || e));
process.on('uncaughtException', (e) => console.error('[erro inesperado]', e?.message || e));
const app = express();
app.set('trust proxy', 1);
app.use(express.urlencoded({ extended: false }));

// ---------- usuários e sessão ----------
// Perfis: Diretor (dashboards) e ADM (dashboards + usuários + conexão com a Conta Azul).
// PAINEL_SENHA continua valendo como senha mestra de ADM, para o primeiro acesso e emergências.
const COOKIE = 'visu_sessao';
const esc = (t) => String(t ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const lerCookie = (req) => { const m = (req.headers.cookie || '').match(new RegExp(`${COOKIE}=([^;]+)`)); return m ? decodeURIComponent(m[1]) : ''; };
const gravarCookie = (req, res, valor, horas = 12) => res.setHeader('Set-Cookie', `${COOKIE}=${encodeURIComponent(valor)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${horas * 3600}${req.secure ? '; Secure' : ''}`);

async function exigeLogin(req, res, next) {
  req.usuario = await usuarios.lerSessao(lerCookie(req)).catch(() => null);
  if (req.usuario?.temporaria) {
    if (req.path.startsWith('/api/')) return res.status(403).json({ erro: 'troque a senha temporária para continuar' });
    return res.redirect('/trocar-senha');
  }
  if (req.usuario) return next();
  if (req.path.startsWith('/api/')) return res.status(401).json({ erro: 'login necessário' });
  res.redirect('/login');
}
function exigeAdm(req, res, next) {
  exigeLogin(req, res, () => {
    if (req.usuario.perfil === 'adm') return next();
    if (req.path.startsWith('/api/')) return res.status(403).json({ erro: 'apenas para o perfil ADM' });
    res.status(403).send(pagina('Acesso restrito', '<p>Esta ação é só para o perfil ADM. Fale com o administrador do painel.</p><a class="b" href="/">Voltar ao painel</a>'));
  });
}

const pagina = (titulo, corpo) => `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(titulo)} · Painel de Gestão Visu</title>
<link rel="icon" href="/logo.png"><style>
body{margin:0;min-height:100vh;display:grid;place-items:center;font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
background:radial-gradient(120% 140% at 100% 0%,#0A57D6 0%,#00348C 55%,#00225E 100%);color:#0B1F44}
.cx{background:#fff;padding:32px 28px;border-radius:18px;width:min(360px,90vw);box-shadow:0 20px 50px rgba(60,0,40,.35);text-align:center}
img{width:170px;height:auto;display:block;margin:4px auto 6px}h1{font-size:18px;margin:14px 0 4px}p{margin:0 0 16px;color:#575272;font-size:13.5px;line-height:1.5}
label{display:block;text-align:left;font-size:12px;font-weight:600;color:#575272;margin:10px 0 4px}
input{width:100%;box-sizing:border-box;padding:11px 12px;border:1px solid #CFCCDD;border-radius:10px;font:inherit}
button,.b{display:block;margin-top:14px;width:100%;box-sizing:border-box;padding:11px;border:0;border-radius:10px;background:#00348C;color:#fff;font:600 15px system-ui;cursor:pointer;text-decoration:none}
.e{color:#c0153a;font-size:13px;margin-top:10px}.d{font-size:12px;color:#8A86A0;margin-top:14px}</style></head><body>
<div class="cx"><img src="/logo-visu-azul.png" alt="Visu"><h1>${esc(titulo)}</h1>${corpo}</div></body></html>`;

const paginaLogin = (erro = '', email = '') => pagina('Painel de Gestão', `<p>Acesso restrito</p>
<form method="post" action="/login"><label for="email">E-mail</label><input id="email" type="email" name="email" value="${esc(email)}" autocomplete="username" autofocus>
<label for="senha">Senha</label><input id="senha" type="password" name="senha" autocomplete="current-password" required><button>Entrar</button>
${erro ? `<div class="e">${esc(erro)}</div>` : ''}</form><div class="d">Primeiro acesso? Entre com a senha temporária que você recebeu; o painel pede para criar a sua.</div>`);

app.get('/login', (req, res) => res.send(paginaLogin()));
app.post('/login', async (req, res) => {
  const email = String(req.body.email || '').trim();
  const senha = String(req.body.senha || '');
  const r = await usuarios.autenticar(email, senha).catch(() => ({ erro: 'E-mail ou senha incorretos.' }));
  let u = r.u || null;
  if (!u && config.senhaPainel && (!email || email.toLowerCase() === 'admin')) {
    const ok = crypto.timingSafeEqual(crypto.createHash('sha256').update(senha).digest(), crypto.createHash('sha256').update(config.senhaPainel).digest());
    if (ok) u = usuarios.ADMIN_MESTRE;
  }
  if (!u) return res.status(401).send(paginaLogin(r.erro || 'E-mail ou senha incorretos.', email));
  gravarCookie(req, res, usuarios.cookieDeSessao(u));
  if (u.id !== '__admin') usuarios.registrarAcesso(u.id);
  res.redirect(u.temporaria ? '/trocar-senha' : '/');
});
app.get('/sair', (req, res) => {
  res.setHeader('Set-Cookie', `${COOKIE}=; Path=/; Max-Age=0`);
  res.redirect('/login');
});

// troca de senha: obrigatória depois de entrar com senha temporária; opcional a qualquer momento
const paginaTroca = (u, erro = '') => pagina(u.temporaria ? `Olá, ${u.nome.split(' ')[0]}` : 'Trocar senha', `<p>${u.temporaria ? 'Você entrou com uma senha temporária. Crie a sua senha para continuar.' : 'Escolha uma nova senha.'}</p>
<form method="post" action="/trocar-senha">${u.temporaria ? '' : '<label for="atual">Senha atual</label><input id="atual" type="password" name="atual" required autocomplete="current-password">'}
<label for="nova">Nova senha (mínimo 8 caracteres)</label><input id="nova" type="password" name="nova" minlength="8" required autocomplete="new-password">
<label for="nova2">Repita a nova senha</label><input id="nova2" type="password" name="nova2" minlength="8" required autocomplete="new-password">
<button>Salvar e entrar</button>${erro ? `<div class="e">${esc(erro)}</div>` : ''}</form>${u.temporaria ? '' : '<div class="d"><a href="/">Voltar ao painel</a></div>'}`);
async function sessaoParaTroca(req, res) {
  const u = await usuarios.lerSessao(lerCookie(req)).catch(() => null);
  if (!u) { res.redirect('/login'); return null; }
  if (u.id === '__admin') { res.send(pagina('Trocar senha', '<p>A senha mestra é a variável PAINEL_SENHA no Render. Para ter senha própria, gere uma senha temporária para você na página Usuários.</p><a class="b" href="/">Voltar ao painel</a>')); return null; }
  return u;
}
app.get('/trocar-senha', async (req, res) => { const u = await sessaoParaTroca(req, res); if (u) res.send(paginaTroca(u)); });
app.post('/trocar-senha', async (req, res) => {
  const u = await sessaoParaTroca(req, res); if (!u) return;
  try {
    if (req.body.nova !== req.body.nova2) throw new Error('As duas senhas não são iguais.');
    const novo = await usuarios.trocarSenha(u.id, { atual: req.body.atual, nova: req.body.nova });
    gravarCookie(req, res, usuarios.cookieDeSessao(novo));
    res.redirect('/');
  } catch (e) { res.status(400).send(paginaTroca(u, e.message)); }
});

// convite: a pessoa abre o link pessoal e cria a própria senha
app.get('/convite/:token', async (req, res) => {
  const r = await usuarios.lerConvite(req.params.token);
  if (r.erro) return res.status(400).send(pagina('Link de acesso', `<p>${esc(r.erro)}</p><a class="b" href="/login">Ir para o login</a>`));
  const u = r.usuario;
  res.send(pagina(`Olá, ${u.nome.split(' ')[0]}`, `<p>Crie sua senha para acessar o Painel de Gestão Visu como <b>${esc(usuarios.PERFIS[u.perfil])}</b>.</p>
<form method="post"><label for="email">Seu e-mail (será o login)</label><input id="email" type="email" name="email" value="${esc(u.email)}" required autocomplete="username">
<label for="senha">Nova senha (mínimo 8 caracteres)</label><input id="senha" type="password" name="senha" minlength="8" required autocomplete="new-password">
<label for="senha2">Repita a senha</label><input id="senha2" type="password" name="senha2" minlength="8" required autocomplete="new-password">
<button>Criar senha e entrar</button></form><div class="d">Este link é pessoal e vale uma vez só.</div>`));
});
app.post('/convite/:token', async (req, res) => {
  try {
    if (req.body.senha !== req.body.senha2) throw new Error('As duas senhas não são iguais.');
    const u = await usuarios.aceitarConvite(req.params.token, { senha: req.body.senha, email: req.body.email });
    gravarCookie(req, res, usuarios.cookieDeSessao(u));
    usuarios.registrarAcesso(u.id);
    res.redirect('/');
  } catch (e) {
    res.status(400).send(pagina('Link de acesso', `<p>${esc(e.message)}</p><a class="b" href="${esc(req.originalUrl)}">Tentar de novo</a>`));
  }
});

// ---------- usuários (perfil ADM) ----------
app.use(express.json());
app.get('/api/eu', exigeLogin, async (req, res) => res.json({ id: req.usuario.id, nome: req.usuario.nome, email: req.usuario.email || '', perfil: req.usuario.perfil, paginas: paginasDe(req.usuario), perfis: { diretor: padraoDe('diretor'), comercial: padraoDe('comercial'), financeiro: padraoDe('financeiro'), consultor: padraoDe('consultor'), vendedor: padraoDe('vendedor') }, vendedor: req.usuario.vendedor || '', perfis_originais: padroesOriginais(), blocos: blocosDe(req.usuario.perfil), blocos_def: BLOCOS, blocos_perfis: req.usuario.perfil === 'adm' ? Object.fromEntries(['diretor', 'comercial', 'financeiro', 'consultor', 'vendedor'].map((k) => [k, blocosDe(k)])) : undefined, blocos_padrao: req.usuario.perfil === 'adm' ? blocosPadrao() : undefined, visual_padrao: (await lerKV('visual_padrao').catch(() => null)) || null }));
// o que cada perfil vê (ADM edita em Usuários e permissões)
app.post('/api/perfis', exigeAdm, async (req, res) => {
  const atual = perfisPersonalizados();
  const { perfil, paginas } = req.body || {};
  if (!['diretor', 'comercial', 'financeiro', 'consultor', 'vendedor'].includes(perfil)) return res.status(400).json({ erro: 'Perfil inválido.' });
  if (paginas === null) delete atual[perfil];
  else if (Array.isArray(paginas) && paginas.length) atual[perfil] = paginas.map(String);
  else return res.status(400).json({ erro: 'Deixe pelo menos uma página marcada.' });
  definirPerfis(atual);
  await salvarKV('perfis_paginas', perfisPersonalizados());
  res.json({ ok: true, perfil, paginas: padraoDe(perfil) });
});
lerKV('perfis_paginas').then((o) => definirPerfis(o)).catch(() => {});
// o que cada perfil vê dentro do Painel executivo e do Quadro de indicadores
app.post('/api/blocos', exigeAdm, async (req, res) => {
  const { perfil, blocos } = req.body || {};
  if (!['diretor', 'comercial', 'financeiro', 'consultor', 'vendedor'].includes(perfil)) return res.status(400).json({ erro: 'Perfil inválido.' });
  const atual = blocosPersonalizados();
  if (blocos === null) delete atual[perfil]; else if (Array.isArray(blocos)) atual[perfil] = blocos.map(String); else return res.status(400).json({ erro: 'Lista de blocos inválida.' });
  definirBlocos(atual); await salvarKV('perfis_blocos', blocosPersonalizados());
  res.json({ ok: true, perfil, blocos: blocosDe(perfil) });
});
lerKV('perfis_blocos').then((o) => definirBlocos(o)).catch(() => {});

// faixas de comissão: o ADM define (vale para todos); null volta ao padrão da especificação
app.get('/api/comissao', exigeLogin, async (req, res) => res.json({ faixas: await faixasComissao(), padrao: FAIXAS_PADRAO() }));
app.post('/api/comissao', exigeAdm, async (req, res) => {
  if (req.body?.faixas === null) { await salvarKV('comissao_faixas', null); dadosDeVendas(true).catch(() => {}); return res.json({ faixas: FAIXAS_PADRAO() }); }
  const faixas = (Array.isArray(req.body?.faixas) ? req.body.faixas : [])
    .map((f) => ({ de: Math.round(Number(f.de) * 100) / 100, pct: Math.round(Number(f.pct) * 100) / 100 }))
    .filter((f) => f.de >= 0 && f.pct > 0 && f.pct <= 100).sort((a, b) => a.de - b.de);
  if (!faixas.length) return res.status(400).json({ erro: 'Informe pelo menos uma faixa (a partir de R$ X, Y%).' });
  await salvarKV('comissao_faixas', { faixas, atualizado_em: new Date().toISOString(), por: req.usuario.nome });
  dadosDeVendas(true).catch(() => {});
  res.json({ faixas });
});

// visual (tema) padrão do painel: o ADM escolhe; cada pessoa ainda pode trocar só no navegador dela
const VISUAIS = ['azul', 'branco', 'oceano', 'degrade', 'classico', 'vibrante', 'sol', 'turquesa', 'fio', 'pop', 'vidro', 'preto', 'noite'];
app.post('/api/visual', exigeAdm, async (req, res) => {
  const t = VISUAIS.includes(req.body?.t) ? req.body.t : 'classico';
  const d = req.body?.d === 'compacta' ? 'compacta' : 'normal';
  const m = ['lateral', 'compacto', 'topo'].includes(req.body?.m) ? req.body.m : 'lateral';
  await salvarKV('visual_padrao', { t, d, m, atualizado_em: new Date().toISOString(), por: req.usuario.nome });
  res.json({ ok: true, t, d, m });
});
// Usuários: o ADM gerencia todos; os diretores criam e cuidam do acesso dos vendedores (e do Comercial e consultores externos)
const PERFIS_DIRETOR = ['vendedor', 'comercial', 'consultor'];
function exigeGestorUsuarios(req, res, next) {
  exigeLogin(req, res, () => {
    if (['adm', 'diretor'].includes(req.usuario.perfil)) return next();
    return res.status(403).json({ erro: 'apenas para ADM e diretores' });
  });
}
async function podeGerirUsuario(eu, id, perfilNovo) {
  if (eu.perfil === 'adm') return true;
  const alvo = id ? await usuarios.porId(id) : null;
  if (alvo && !PERFIS_DIRETOR.includes(alvo.perfil)) return false;
  if (perfilNovo !== undefined && !PERFIS_DIRETOR.includes(perfilNovo)) return false;
  return true;
}
const SO_ADM_USU = 'Diretores cadastram e cuidam só do acesso de Vendedor, Comercial e Consultor externo. Para os outros perfis, fale com o ADM.';
app.get('/api/usuarios', exigeGestorUsuarios, async (req, res) => res.json({ usuarios: await usuarios.listar(), perfis: usuarios.PERFIS, perfis_permitidos: req.usuario.perfil === 'adm' ? Object.keys(usuarios.PERFIS) : PERFIS_DIRETOR, banco: await usuarios.bancoConfigurado(), banco_status: await statusBanco().catch((e) => ({ erro: e.message })) }));
// v89: "Ver o painel como" uma pessoa: exatamente as páginas, blocos e funções que o servidor dá a ela
app.get('/api/usuarios/:id/visao', exigeAdm, async (req, res) => {
  try {
    const u = (await usuarios.listar()).find((x) => x.id === req.params.id);
    if (!u) return res.status(404).json({ erro: 'Usuário não encontrado.' });
    res.json({ paginas: paginasDe(u), blocos: blocosDe(u.perfil), vendedor: u.perfil === 'vendedor' ? u.vendedor || '' : '',
      pode: { lancar: pedidos.podeLancar(u), gestao: pedidos.podeEditarTudo(u), importar: pedidos.podeEditarTudo(u), fonte: u.perfil === 'adm' } });
  } catch (e) { res.status(500).json({ erro: e.message }); }
});
app.post('/api/usuarios', exigeGestorUsuarios, async (req, res) => {
  try {
    const b = req.body || {};
    if (!(await podeGerirUsuario(req.usuario, b.id, b.perfil))) return res.status(403).json({ erro: SO_ADM_USU });
    res.json(await usuarios.salvar(b));
  } catch (e) { res.status(400).json({ erro: e.message }); }
});
app.delete('/api/usuarios/:id', exigeGestorUsuarios, async (req, res) => {
  if (req.params.id === req.usuario.id) return res.status(400).json({ erro: 'Você não pode remover o próprio acesso.' });
  if (!(await podeGerirUsuario(req.usuario, req.params.id))) return res.status(403).json({ erro: SO_ADM_USU });
  await usuarios.remover(req.params.id); res.json({ ok: true });
});
app.post('/api/usuarios/:id/senha-temporaria', exigeGestorUsuarios, async (req, res) => {
  if (!(await podeGerirUsuario(req.usuario, req.params.id))) return res.status(403).json({ erro: SO_ADM_USU });
  try { res.json(await usuarios.gerarSenhaTemporaria(req.params.id)); } catch (e) { res.status(400).json({ erro: e.message }); }
});
app.post('/api/usuarios/:id/convite', exigeGestorUsuarios, async (req, res) => {
  if (!(await podeGerirUsuario(req.usuario, req.params.id))) return res.status(403).json({ erro: SO_ADM_USU });
  try { res.json(await usuarios.gerarConvite(req.params.id)); } catch (e) { res.status(400).json({ erro: e.message }); }
});

app.get('/saude', (req, res) => res.json({ ok: true }));
app.get('/saude/banco', async (req, res) => res.json(await statusBanco().catch((e) => ({ erro: e.message }))));
app.get(['/treinamento.mp4', '/treinamento.vtt'], exigeLogin, (req, res) => res.sendFile(path.join(raiz, 'public', req.path.slice(1)), { maxAge: 0, etag: true, lastModified: true }));
app.get('/politica-premiacao.pdf', exigeLogin, (req, res) => res.sendFile(path.join(raiz, 'public', 'politica-premiacao.pdf')));
app.get(['/logo.png', '/logo-visu.png', '/logo-visu-azul.png'], (req, res) => res.sendFile(path.join(raiz, 'public', req.path.slice(1))));
// bibliotecas de exportação (Excel e PDF), servidas pelo próprio painel para não depender de CDN
const VENDOR = { 'xlsx.full.min.js': 'xlsx/dist/xlsx.full.min.js', 'jspdf.umd.min.js': 'jspdf/dist/jspdf.umd.min.js', 'jspdf.plugin.autotable.min.js': 'jspdf-autotable/dist/jspdf.plugin.autotable.min.js' };
app.get('/vendor/:arq', exigeLogin, (req, res) => (VENDOR[req.params.arq] ? res.sendFile(path.join(raiz, 'node_modules', VENDOR[req.params.arq]), { maxAge: '30d' }) : res.sendStatus(404)));
app.use('/vitrine', express.static(path.join(raiz, 'public', 'vitrine'), { maxAge: '7d' }));

// ---------- conexão com a Conta Azul ----------
app.get('/conectar', exigeAdm, (req, res) => {
  if (!config.clientId || !config.clientSecret) {
    return res.status(500).send('Faltam CONTA_AZUL_CLIENT_ID e CONTA_AZUL_CLIENT_SECRET nas variáveis de ambiente.');
  }
  res.redirect(ca.urlDeAutorizacao());
});

app.get('/callback', exigeAdm, async (req, res) => {
  try {
    if (req.query.error) throw new Error(String(req.query.error_description || req.query.error));
    await ca.trocarCodigo(String(req.query.code || ''), String(req.query.state || ''));
    res.redirect('/?conectado=1');
  } catch (e) {
    res.status(400).send(`<p>Não foi possível conectar à Conta Azul.</p><pre>${String(e.message).replace(/</g, '&lt;')}</pre><p><a href="/">Voltar</a></p>`);
  }
});

// ---------- conexão com o Google (planilha de vendas) ----------
app.get('/google/conectar', exigeAdm, (req, res) => {
  if (!google.credenciaisGoogle()) return res.status(500).send('<p>Faltam GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET nas variáveis de ambiente do Render (veja o README, seção "Planilha em tempo real").</p><p><a href="/#conciliacao">Voltar</a></p>');
  res.redirect(google.urlAutorizacaoGoogle(config.planilhaConta));
});
app.get('/google/callback', exigeAdm, async (req, res) => {
  try {
    if (req.query.error) throw new Error(String(req.query.error_description || req.query.error));
    await google.trocarCodigoGoogle(String(req.query.code || ''), String(req.query.state || ''));
    dadosDeVendas(true).catch(() => {});
    res.redirect('/?google=1#conciliacao');
  } catch (e) {
    res.status(400).send(`<p>Não foi possível conectar ao Google.</p><pre>${String(e.message).replace(/</g, '&lt;')}</pre><p><a href="/#conciliacao">Voltar</a></p>`);
  }
});
app.post('/google/desconectar', exigeAdm, async (req, res) => { await google.desconectarGoogle(); dadosDeVendas(true).catch(() => {}); res.redirect('/#conciliacao'); });
// planilha ligada pelo e-mail do ADM (Apps Script): sem GOOGLE_CLIENT_ID/SECRET no Render
app.get('/api/planilha-script', exigeAdm, async (req, res) => { const chave = await pscript.chaveScript(); const id = pscript.arquivoScript() || google.idPlanilha() || 'COLE_AQUI_O_ID_DA_PLANILHA'; res.json({ ...pscript.statusScript(), arquivo_id: id, script: pscript.modeloScript(chave, id), planilha_link: pscript.arquivoScript() ? `https://docs.google.com/spreadsheets/d/${id}/edit` : config.planilhaLink, conta: config.planilhaConta }); });
app.post('/api/planilha-script/arquivo', exigeAdm, async (req, res) => { try { res.json({ arquivo_id: await pscript.definirArquivo(req.body?.link) }); } catch (e) { res.status(400).json({ erro: e.message }); } });
// grava na planilha do Google os recebimentos já baixados na Conta Azul (só células vazias)
// pedidos do painel → vendas na Conta Azul (quando a gestão liga o envio)
async function enviarPedidosCA(u, opcoes = {}) {
  const r = await envioCA.enviarPedidos(u, opcoes);
  await pedidos.salvarConfigPedidos({ ultimo_envio_ca: { em: new Date().toISOString(), por: u?.nome || 'Horário automático', enviados: r.enviados.length, ja_existiam: r.ja_existiam.length, erros: r.erros.slice(0, 20), complementares: r.complementares } }, u);
  if (r.enviados.length) dadosDeVendas(true).catch(() => {});
  return r;
}
async function gravarRecebimentosNaPlanilha(u, forcar = false) {
  if (!pscript.scriptConfigurado()) throw new Error('Ligue a planilha pelo seu e-mail primeiro.');
  const { lerPlanilha } = await import('./src/planilha.js');
  const plan = await lerPlanilha();
  const pg = await pedidos.pagamentosPorPedido(vendasContaAzulEmCache() || (await dadosDeVendas().catch(() => null), vendasContaAzulEmCache()));
  const itens = pedidos.itensParaPlanilha(pg, plan.linhas, pscript.ateScript());
  const fila = pscript.filaCelulas();
  if (!itens.length && !fila.length) { await pscript.marcarGravacao({ celulas: 0, pedidos: 0, enviados: 0, buscando_baixas: pg.buscando_baixas || 0 }); return { celulas: 0, pedidos: 0, buscando_baixas: pg.buscando_baixas || 0 }; }
  const r = await pscript.enviarParaPlanilha(itens, forcar);
  if (r.adiado) { await pscript.marcarGravacao({ adiado: true, motivo: r.motivo, pendentes: itens.length }); return { ...r, pendentes: itens.length }; }
  if (fila.length && r.versao == null) { await pscript.marcarGravacao({ erro: 'script antigo: copie o script novo pelo painel para gravar os campos em branco' }); throw new Error('Para gravar os campos em branco na planilha, o script precisa ser atualizado: em Controle → Planilha × sistema (mês) → Ligar pelo meu e-mail, copie o script novo, cole no Apps Script, salve e faça Implantar → Gerenciar implantações → Editar → Nova versão.'); }
  if (fila.length) await pscript.concluirCelulas(r.celulas_feitas, r.pulados);
  await pedidos.logPlanilha(u, itens, r); await pscript.marcarGravacao({ celulas: r.celulas, pedidos: r.pedidos, aba: r.aba, enviados: itens.length, pulados: r.pulados || null, codigos: r.codigos || [] });
  if (r.celulas) dadosDeVendas(true).catch(() => {});
  return { ...r, buscando_baixas: pg.buscando_baixas || 0 };
}
app.post('/api/planilha-script/gravar', exigeAdm, async (req, res) => { try { if (req.body?.ativo !== undefined) await pscript.definirGravar(req.body.ativo); if (req.body?.ate) await pscript.definirAte(req.body.ate); res.json({ ...pscript.statusScript(), ...(req.body?.agora ? await gravarRecebimentosNaPlanilha(req.usuario, !!req.body.forcar) : {}) }); } catch (e) { if (req.body?.agora) await pscript.marcarGravacao({ erro: e.message }).catch(() => {}); res.status(400).json({ erro: e.message }); } });
// campos em branco preenchidos no painel (Qualidade dos dados) → planilha do Google
app.get('/api/planilha-script/celulas', exigeLogin, async (req, res) => res.json({ fila: pscript.filaCelulas(), historico: pscript.historicoCelulas().slice(0, 100) }));
app.post('/api/planilha-script/celulas', exigeLogin, async (req, res) => {
  try {
    if (!['adm', 'diretor', 'financeiro'].includes(req.usuario?.perfil)) return res.status(403).json({ erro: 'só ADM, diretoria e financeiro preenchem a planilha pelo painel' });
    if (!pscript.scriptConfigurado()) throw new Error('Ligue a planilha pelo seu e-mail primeiro (Controle → Planilha × sistema (mês)).');
    const lista = (req.body?.itens || []).filter((x) => x && Number(x.linha) > 0 && x.campo && String(x.valor ?? '').trim() !== '').slice(0, 300);
    if (!lista.length) throw new Error('Nada para gravar.');
    await pscript.adicionarCelulas(lista, req.usuario);
    let r = null;
    try { r = await gravarRecebimentosNaPlanilha(req.usuario, false); } catch (e) { return res.json({ ok: true, na_fila: pscript.filaCelulas().length, aviso: e.message }); }
    res.json({ ok: true, ...r, na_fila: pscript.filaCelulas().length });
  } catch (e) { res.status(400).json({ erro: e.message }); }
});
// horários fixos (Fortaleza): gravação na planilha e atualização da Conta Azul, para não consumir a API e o Render o tempo todo
const HORARIOS_SINCRONIZA = ['09:30', '14:00', '17:30'];
// ao subir o servidor: preenche novo × recompra em branco (painel e fila da planilha) uma vez, sem esperar o próximo horário
setTimeout(() => { preencherNovoRecompra(null).then((r) => { if (r.planilha && pscript.scriptConfigurado() && pscript.statusScript().gravar) return gravarRecebimentosNaPlanilha(null); }).catch((e) => console.warn('[pedidos] novo × recompra:', e.message)); }, 90e3);
let ultimoHorarioSincronizado = '';
const horaFortaleza = () => new Intl.DateTimeFormat('pt-BR', { timeZone: 'America/Fortaleza', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date());
setInterval(() => {
  const agora = horaFortaleza();
  if (!HORARIOS_SINCRONIZA.includes(agora) || agora === ultimoHorarioSincronizado) return;
  ultimoHorarioSincronizado = agora;
  pedidos.configPedidos().then((c) => (c.enviar_ca ? enviarPedidosCA(null) : null)).catch((e) => console.warn('[conta azul] envio de pedidos:', e.message))
    .finally(() => dadosDeVendas(true).catch((e) => console.warn('[conta azul] atualização:', e.message)));
  preencherNovoRecompra(null).catch((e) => console.warn('[pedidos] novo × recompra:', e.message))
    .finally(() => { if (pscript.scriptConfigurado() && pscript.statusScript().gravar) gravarRecebimentosNaPlanilha(null).catch((e) => { console.warn('[planilha] gravação:', e.message); pscript.marcarGravacao({ erro: e.message }).catch(() => {}); }); });
}, 60e3);
app.post('/api/planilha-script', exigeAdm, async (req, res) => {
  try { const arq = await pscript.ligarScript(req.body?.url, req.usuario); dadosDeVendas(true).catch(() => {}); res.json({ ok: true, nome: arq.nome, alterado_em: arq.alterado_em, ...pscript.statusScript() }); }
  catch (e) { res.status(400).json({ erro: e.message }); }
});
app.delete('/api/planilha-script', exigeAdm, async (req, res) => { await pscript.desligarScript(); dadosDeVendas(true).catch(() => {}); res.json({ ok: true }); });
app.get('/api/google', exigeLogin, async (req, res) => res.json({ ...(await google.statusGoogle()), redirect_uri: google.redirectGoogle() }));

app.post('/desconectar', exigeAdm, async (req, res) => {
  await ca.desconectar();
  res.redirect('/');
});

// ---------- API do painel ----------
app.get('/api/status', exigeLogin, async (req, res) => {
  res.json({ ...(await ca.statusConexao()), demo: config.demo, redirect_uri: redirectUri(), credenciais_ok: !!(config.clientId && config.clientSecret) });
});

// Base de vendas (linhas da planilha já padronizadas). Os indicadores são calculados no navegador,
// para os filtros responderem na hora.
app.get('/api/vendas', exigeLogin, async (req, res) => {
  if (!veVendas(req.usuario)) return res.status(403).json({ erro: 'seu perfil não tem acesso aos dados de vendas' });
  try {
    res.json({ ...(await dadosDeVendas(req.query.forcar === '1')), planilha_link: config.planilhaLink, planilha_conta: config.planilhaConta, google: await google.statusGoogle().catch(() => null), planilha_script: pscript.statusScript() });
  } catch (e) {
    console.error('[vendas]', e);
    res.status(502).json({ erro: e.message });
  }
});

// Gestão financeira (DRE, caixa, contas a receber/pagar, saldos) pela API da Conta Azul
// Quem é (ou não é) vendedor: o ADM marca como inativo quem aparece na Conta Azul mas não vende (financeiro, escritório etc.)
// Não vendedores apontados na revisão de 22/10/2026 (Tiago): entram como inativos uma única vez; o ADM pode reativar.
const NAO_VENDEDORES_PADRAO = ['Tiago - Financeiro', 'Escritório BPO', 'Morgana Limeira', 'Anderson Alves', 'Visu'];
app.get('/api/vendedores', exigeLogin, async (req, res) => {
  let cfg = (await lerKV('vendedores_config').catch(() => null)) || { inativos: [] };
  if (!cfg.revisao_2210) {
    const ja = new Set((cfg.inativos || []).map((x) => String(x).toLowerCase()));
    cfg = { ...cfg, inativos: [...(cfg.inativos || []), ...NAO_VENDEDORES_PADRAO.filter((x) => !ja.has(x.toLowerCase()))], revisao_2210: true };
    await salvarKV('vendedores_config', cfg).catch(() => {});
  }
  res.json(cfg);
});
app.post('/api/vendedores', exigeAdm, async (req, res) => {
  const inativos = [...new Set((Array.isArray(req.body?.inativos) ? req.body.inativos : []).map((x) => String(x).trim()).filter(Boolean))];
  await salvarKV('vendedores_config', { inativos, revisao_2210: true, atualizado_em: new Date().toISOString(), por: req.usuario.nome });
  res.json({ inativos });
});

app.get('/api/financeiro', exigeLogin, async (req, res) => {
  if (!veFinanceiro(req.usuario)) return res.status(403).json({ erro: 'seu perfil não tem acesso ao financeiro' });
  try { res.json(await dadosFinanceiros(req.query.forcar === '1')); }
  catch (e) { console.error('[financeiro]', e); res.status(502).json({ erro: e.message }); }
});

// ---------- Pedidos de venda no painel (reunião de 03/11/2026) ----------
const exigePedidos = (req, res, next) => (vePedidos(req.usuario) ? next() : res.status(403).json({ erro: 'seu perfil não tem acesso aos pedidos de venda' }));
const depoisDeMudar = () => remontarVendas();
const resp = (fn) => async (req, res) => { try { res.json(await fn(req)); } catch (e) { res.status(400).json({ erro: e.message }); } };
// códigos já usados na planilha ligada e na Conta Azul: a sequência do "+ Novo pedido" continua deles
async function codigosExternos() {
  const d = await dadosDeVendas().catch(() => null);
  pedidos.definirCodigosExternos([...(d?.linhas || []).map((l) => l.cd).filter(Boolean), ...(d?.conta_azul?.vendas || []).map((v) => v.n).filter((n) => n != null)]);
  return d;
}
// clientes cadastrados: Conta Azul (cadastro) + planilha + pedidos do painel
const cacheClientes = { quando: 0, lista: [] };
app.get('/api/pedidos/clientes', exigeLogin, exigePedidos, resp(async () => {
  const d = await dadosDeVendas().catch(() => null), m = new Map();
  const add = (nome, origem, data, doc) => { nome = String(nome || '').trim(); if (!nome || nome === 'Vendas consolidadas do mês' || nome === 'Sem cliente') return; const k = nome.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/\s+/g, ' '); const x = m.get(k) || { nome, origens: [], ultima: '', vezes: 0, documento: '' }; if (!x.origens.includes(origem)) x.origens.push(origem); if (data && data > x.ultima) x.ultima = data; if (doc) x.documento = doc; x.vezes++; m.set(k, x); };
  (await pedidos.listar()).forEach((r) => add(r.cliente, 'painel', r.data));
  if (['planilha', 'painel', 'misto'].includes(d?.fonte)) d.linhas.forEach((l) => add(l.c, 'planilha', l.d));
  (d?.conta_azul?.vendas || []).forEach((v) => add(v.c, 'conta_azul', v.d));
  if (!config.demo && (await ca.statusConexao().catch(() => ({}))).conectado) {
    if (Date.now() - cacheClientes.quando > 3600e3) { cacheClientes.lista = await ca.buscarClientes().catch(() => []); cacheClientes.quando = Date.now(); }
    cacheClientes.lista.forEach((c) => add(c.nome, 'cadastro', '', c.documento));
  }
  (await cadastros.listarCadastros()).cliente.forEach((c) => add(c.nome, c.ca_id ? 'cadastro' : 'novo', '', c.documento));
  return { clientes: [...m.values()].sort((a, b) => b.vezes - a.vezes), cadastro_conta_azul: cacheClientes.lista.length };
}));
// botão + no lançamento: cliente, tipo de produto, material ou cor novos (o cliente também vai para a Conta Azul)
app.post('/api/cadastros', exigeLogin, exigePedidos, resp(async (req) => {
  if (!pedidos.podeLancar(req.usuario)) throw new Error('Seu perfil só consulta os pedidos.');
  const r = await cadastros.incluirCadastro(req.body || {}, req.usuario);
  if (r.campo === 'cliente' && r.conta_azul?.ok) cacheClientes.quando = 0;
  return r;
}));
app.post('/api/pedidos/preencher-pagamentos', exigeLogin, exigePedidos, resp(async (req) => {
  if (!pedidos.podeLancar(req.usuario)) throw new Error('Seu perfil só consulta os pedidos.');
  const pg = await pedidos.pagamentosPorPedido(vendasContaAzulEmCache(), true);
  const r = await pedidos.preencherPagamentos(pg, req.usuario); if (r.linhas) depoisDeMudar(); return { ...r, buscando_baixas: pg.buscando_baixas || 0 };
}));
app.get('/api/pedidos', exigeLogin, exigePedidos, resp(async (req) => {
  await codigosExternos();
  let pagamentos = null;
  try { pagamentos = await pedidos.pagamentosPorPedido(vendasContaAzulEmCache(), req.query.forcar === '1'); if (pagamentos?.conectado && (await pedidos.preencherPagamentos(pagamentos, null, { auto: true })).linhas) depoisDeMudar(); } catch (e) { pagamentos = { erro: e.message }; }
  notasCA.atualizarNotas(vendasContaAzulEmCache());
  const [registros, cfg, cads, notas_ca] = await Promise.all([pedidos.listar(), pedidos.configPedidos(), cadastros.listarCadastros(), notasCA.notasPorCodigo().catch(() => ({}))]);
  return { registros, config: cfg, cadastros: cads, pagamentos, notas_ca, campos_valor: pedidos.CAMPOS_VALOR, proximo_codigo: pedidos.proximoCodigo(new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 10)), codigos_externos: pedidos.codigosExternosLista(), horas_edicao: Number(process.env.HORAS_EDICAO_PEDIDO || 24),
    vendedor: req.usuario.perfil === 'vendedor' ? req.usuario.vendedor || '' : '', vendedor_padrao: req.usuario.vendedor || '', whatsapp_aprovacao: (await pedidos.configPedidos()).whatsapp_aprovacao || [], pode: { lancar: pedidos.podeLancar(req.usuario), gestao: pedidos.podeEditarTudo(req.usuario), importar: pedidos.podeEditarTudo(req.usuario), fonte: req.usuario.perfil === 'adm' },
    planilha_conectada: planilhaConfigurada() || config.demo, eu: { id: req.usuario.id, nome: req.usuario.nome, perfil: req.usuario.perfil, vendedor: req.usuario.vendedor || '' } };
}));
app.get('/api/pedidos/proximo-codigo', exigeLogin, exigePedidos, resp(async (req) => { await pedidos.listar(); await codigosExternos(); return { codigo: req.query.de ? pedidos.proximoComplemento(req.query.de) : pedidos.proximoCodigo(req.query.data) }; }));
app.post('/api/pedidos', exigeLogin, exigePedidos, resp(async (req) => { await codigosExternos(); const r = await pedidos.criarPedido(req.body, req.usuario); depoisDeMudar(); return { registros: r }; }));
app.patch('/api/pedidos/:id', exigeLogin, exigePedidos, resp(async (req) => { const r = await pedidos.alterar(req.params.id, req.body?.mudancas || req.body, req.usuario); depoisDeMudar(); return { registro: r }; }));
// anexos do pedido: comprovante de pagamento (vendedor e gestão) e nota fiscal (gestão); arquivo enviado cru, até 5 MB
app.post('/api/pedidos/:id/anexos', exigeLogin, exigePedidos, express.raw({ type: () => true, limit: '6mb' }), resp(async (req) => {
  const r = await pedidos.registro(req.params.id); if (!r) throw new Error('Linha não encontrada.');
  const tipo = req.query.tipo === 'nf' ? 'nf' : 'comprovante';
  if (tipo === 'nf' && !pedidos.podeEditarTudo(req.usuario)) throw new Error('A nota fiscal é anexada pela gestão.');
  if (tipo === 'comprovante' && !pedidos.ehDoVendedor(req.usuario, r)) throw new Error('Só o vendedor do pedido ou a gestão anexa o comprovante.');
  const nome = String(req.query.nome || 'arquivo').slice(0, 120), mime = String(req.headers['content-type'] || '').split(';')[0].trim().toLowerCase();
  const g = await anexos.guardarArquivo({ registro: r.id, codigo: r.codigo, tipo, nome, mime, bytes: Buffer.isBuffer(req.body) ? req.body : null, por: req.usuario.nome });
  return { registro: await pedidos.anexar(r.id, { id: g.id, tipo, nome, mime, tamanho: g.tamanho }, req.usuario) };
}));
app.delete('/api/pedidos/:id/anexos/:aid', exigeLogin, exigePedidos, resp(async (req) => { const r = await pedidos.removerAnexo(req.params.id, req.params.aid, req.usuario); await anexos.apagarArquivo(req.params.aid); return { registro: r }; }));
app.get('/api/anexos/:aid', exigeLogin, async (req, res) => {
  try {
    const a = await anexos.lerArquivo(req.params.aid); if (!a) return res.status(404).send('Arquivo não encontrado.');
    const r = await pedidos.registro(a.registro); if (!r || !pedidos.podeVerRegistro(req.usuario, r)) return res.status(403).send('Sem acesso a este arquivo.');
    res.set('Content-Type', a.mime || 'application/octet-stream'); res.set('Content-Disposition', `inline; filename*=UTF-8''${encodeURIComponent(a.nome || 'arquivo')}`); res.set('Cache-Control', 'private, max-age=3600');
    res.send(a.dados);
  } catch (e) { res.status(500).send(e.message); }
});
// Contas a receber · gestão da cobrança: anotações por título e DNIs (leitura: quem vê o Financeiro; edição: ADM, diretores e financeiro)
const podeCobranca = (u) => ['adm', 'diretor', 'financeiro'].includes(u?.perfil);
app.get('/api/receber/gestao', exigeLogin, resp(async (req) => ({ ...(await receber.lerGestao()), acoes: receber.ACOES, pode_editar: podeCobranca(req.usuario) })));
app.post('/api/receber/titulo', exigeLogin, resp(async (req) => { if (!podeCobranca(req.usuario)) throw new Error('Só ADM, diretores e financeiro editam a cobrança.'); return { anot: await receber.salvarTitulo(req.body || {}, req.usuario) }; }));
app.post('/api/receber/dni', exigeLogin, resp(async (req) => { if (!podeCobranca(req.usuario)) throw new Error('Só ADM, diretores e financeiro editam a cobrança.'); return { dni: await receber.salvarDni(req.body || {}, req.usuario) }; }));
app.post('/api/pedidos/:id/solicitar', exigeLogin, exigePedidos, resp(async (req) => ({ registro: await pedidos.solicitarAlteracao(req.params.id, req.body || {}, req.usuario) })));
app.post('/api/pedidos/:id/responder', exigeLogin, exigePedidos, resp(async (req) => { const r = await pedidos.responderSolicitacao(req.params.id, req.body || {}, req.usuario); depoisDeMudar(); return { registro: r }; }));
app.delete('/api/pedidos/:id', exigeLogin, exigePedidos, resp(async (req) => { await pedidos.excluir(req.params.id, req.usuario); depoisDeMudar(); return { ok: true }; }));
app.post('/api/pedidos/unificar-cliente', exigeLogin, exigePedidos, resp(async (req) => { const r = await pedidos.unificarCliente(req.body?.de, req.body?.para, req.usuario); depoisDeMudar(); return r; }));
// importação: JSON {de, ate, modo, simular} lê a planilha conectada; com ?arquivo=nome.xlsx o corpo é o próprio .xlsx
app.post('/api/pedidos/importar', exigeLogin, exigePedidos, express.raw({ type: ['application/octet-stream', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'], limit: '25mb' }), resp(async (req) => {
  const arquivo = Buffer.isBuffer(req.body) && req.body.length ? req.body : null;
  const o = arquivo ? req.query : req.body || {};
  const r = await pedidos.importar({ de: String(o.de || '2026-01'), ate: String(o.ate || '9999-12'), modo: ['substituir', 'faltam'].includes(o.modo) ? o.modo : 'novas', simular: String(o.simular) !== 'false' && o.simular !== false, bytes: arquivo, nomeArquivo: String(req.query.arquivo || '') }, req.usuario);
  if (!r.simular && r.importadas !== undefined) depoisDeMudar();
  return r;
}));
// envio sob demanda (gestão): atualiza a Conta Azul e grava os pedidos na planilha agora, para grandes volumes
app.post('/api/sincronizar-agora', exigeLogin, exigePedidos, resp(async (req) => {
  if (!pedidos.podeEditarTudo(req.usuario)) throw new Error('Só a gestão envia os pedidos manualmente.');
  const cfg = await pedidos.configPedidos();
  const envio = cfg.enviar_ca ? await enviarPedidosCA(req.usuario).catch((e) => ({ erro_envio: e.message })) : null;
  await dadosDeVendas(true);
  const r = pscript.scriptConfigurado() ? await gravarRecebimentosNaPlanilha(req.usuario, true) : { aviso: 'Planilha não ligada: só a Conta Azul foi atualizada.' };
  return { ok: true, ...r, envio, quando: new Date().toISOString() };
}));
async function preencherNovoRecompra(u) {
  const d = await dadosDeVendas().catch(() => null);
  const r = await pedidos.preencherNovoRecompra(d?.conta_azul?.vendas || [], u);
  let fila = 0;
  if (r.celulas.length && pscript.scriptConfigurado()) { await pscript.adicionarCelulas(r.celulas, u); fila = r.celulas.length; }
  if (r.painel) depoisDeMudar();
  return { planilha: fila, sem_ligacao: !pscript.scriptConfigurado() ? r.celulas.length : 0, painel: r.painel };
}
app.post('/api/pedidos/novo-recompra', exigeLogin, exigePedidos, resp(async (req) => {
  if (!pedidos.podeEditarTudo(req.usuario)) throw new Error('Só a gestão preenche novo × recompra em lote.');
  const r = await preencherNovoRecompra(req.usuario);
  if (r.planilha && pscript.statusScript().gravar) gravarRecebimentosNaPlanilha(req.usuario, true).catch(() => {});
  return r;
}));
app.post('/api/pedidos/assumir', exigeLogin, exigePedidos, resp(async (req) => {
  const registros = await pedidos.assumirDaPlanilha(String(req.body?.codigo || ''), req.usuario);
  depoisDeMudar(); dadosDeVendas(true).catch(() => {});
  return { registros };
}));
app.post('/api/pedidos/conta-azul', exigeAdm, resp(async (req) => {
  const c = await pedidos.salvarConfigPedidos({ enviar_ca: !!req.body?.ativo }, req.usuario);
  return c;
}));
app.post('/api/pedidos/enviar-ca', exigeLogin, exigePedidos, resp(async (req) => {
  if (!pedidos.podeEditarTudo(req.usuario)) throw new Error('Só a gestão envia os pedidos para a Conta Azul.');
  const codigos = Array.isArray(req.body?.codigos) && req.body.codigos.length ? req.body.codigos.map(String) : null;
  const r = await enviarPedidosCA(req.usuario, { codigos });
  return { ...r, config: await pedidos.configPedidos() };
}));
app.post('/api/pedidos/planilha-uso', exigeAdm, resp(async (req) => {
  // encerrar: o painel vira a única ferramenta; as vendas que só estão na planilha (a partir do corte) entram como pedidos do painel
  const encerrar = !!req.body?.encerrar;
  let importadas = null;
  if (encerrar) { const cfg = await pedidos.configPedidos(); const r = await pedidos.importar({ de: cfg.corte || '2026-11', ate: '9999-12', modo: 'novas', simular: false }, req.usuario); importadas = r.linhas; }
  const c = await pedidos.salvarConfigPedidos({ planilha_encerrada: encerrar, planilha_encerrada_em: encerrar ? new Date().toISOString() : null }, req.usuario);
  depoisDeMudar(); await dadosDeVendas(true).catch(() => {});
  return { ...c, importadas };
}));
app.post('/api/pedidos/config', exigeAdm, resp(async (req) => { const f = ['painel', 'misto'].includes(req.body?.fonte) ? req.body.fonte : 'planilha'; const r = await pedidos.salvarConfigPedidos({ fonte: f, corte: f === 'misto' ? (/^\d{4}-\d{2}$/.test(req.body?.corte || '') ? req.body.corte : '2026-11') : undefined }, req.usuario); depoisDeMudar(); return r; }));
// WhatsApp da diretoria para o aviso de pedido de aprovação (o vendedor abre o WhatsApp com a mensagem pronta)
app.post('/api/pedidos/whatsapp', exigeLogin, resp(async (req) => {
  if (!['adm', 'diretor'].includes(req.usuario.perfil)) throw new Error('Só ADM e diretores definem o WhatsApp dos avisos.');
  const lista = (Array.isArray(req.body?.numeros) ? req.body.numeros : []).map((x) => ({ nome: String(x?.nome || '').trim().slice(0, 40), numero: String(x?.numero || '').replace(/\D/g, '').slice(0, 15) })).filter((x) => x.numero.length >= 10).slice(0, 5);
  const r = await pedidos.salvarConfigPedidos({ whatsapp_aprovacao: lista }, req.usuario);
  return { whatsapp_aprovacao: r.whatsapp_aprovacao };
}));
app.get('/api/pedidos/historico', exigeLogin, (req, res, next) => (veHistorico(req.usuario) ? next() : res.status(403).json({ erro: 'o histórico de alterações é só para a gestão' })), resp(async (req) => ({ itens: await pedidos.historico({ codigo: req.query.codigo, usuario: req.query.usuario, acao: req.query.acao, dias: req.query.dias || 90 }) })));

// ---------- Conciliação bancária: extrato do banco × baixas na Conta Azul ----------
const exigeExtrato = (req, res, next) => (paginasDe(req.usuario).includes('extrato') ? next() : res.status(403).json({ erro: 'seu perfil não tem acesso à conciliação bancária' }));
const cacheBaixasExtrato = new Map();
async function baixasDoSistema(de, ate) {
  const k = de + '|' + ate, c = cacheBaixasExtrato.get(k);
  if (c && Date.now() - c.t < 10 * 60e3) return c.d;
  let lista = [];
  if (config.demo) {
    const base = gerarDemoPlanilha(), vendas = gerarDemoContaAzul(base.linhas);
    lista = gerarDemoParcelas(vendas).filter((p) => p.pago > 0).map((p) => ({ tipo: 'r', data: p.data_pagamento, valor: p.pago, pessoa: p.descricao.replace(/ - parcela.*/, ''), desc: p.descricao, conta: p.baixas?.[0]?.conta || '', aprox: false }));
    const r = (x) => ((Math.sin(x) * 10000) % 1 + 1) % 1; // despesas fictícias
    for (let i = 0; i < 120; i++) { const d = new Date(Date.UTC(2026, 6, 1) + Math.floor(r(i) * 125) * 864e5).toISOString().slice(0, 10); lista.push({ tipo: 'p', data: d, valor: -Math.round(200 + r(i + 7) * 4800), pessoa: ['Fornecedor de tecido', 'Energia', 'Aluguel', 'Transportadora', 'Folha'][i % 5], desc: 'Pagamento', conta: ['Banco do Brasil', 'Sicredi', 'Banco Inter', 'Caixa'][i % 4], aprox: false }); }
  } else if ((await ca.statusConexao()).conectado) {
    const [rec, pag] = await Promise.all([ca.buscarParcelas('receber', { pagamento_de: de, pagamento_ate: ate }), ca.buscarParcelas('pagar', { pagamento_de: de, pagamento_ate: ate })]);
    const m = (p, sinal) => ({ tipo: sinal > 0 ? 'r' : 'p', data: p.data_pagamento || p.vencimento, aprox: !p.data_pagamento, valor: Math.round(sinal * (p.pago || p.total) * 100) / 100, pessoa: p.pessoa, desc: p.descricao, conta: p.conta || '', categoria: p.categorias?.[0]?.nome || '' });
    lista = [...rec.filter((p) => p.pago > 0).map((p) => m(p, 1)), ...pag.filter((p) => p.pago > 0).map((p) => m(p, -1))];
  }
  lista = lista.filter((x) => x.data >= de && x.data <= ate);
  cacheBaixasExtrato.set(k, { t: Date.now(), d: lista });
  return lista;
}
app.get('/api/extrato', exigeLogin, exigeExtrato, resp(async (req) => {
  const de = /^\d{4}-\d{2}-\d{2}$/.test(req.query.de || '') ? req.query.de : new Date(Date.now() - 62 * 864e5).toISOString().slice(0, 10);
  const ate = /^\d{4}-\d{2}-\d{2}$/.test(req.query.ate || '') ? req.query.ate : new Date().toISOString().slice(0, 10);
  const [contas, sistema] = await Promise.all([extrato.lancamentosExtrato(de, ate), baixasDoSistema(de, ate).catch((e) => ({ erro: e.message }))]);
  return { de, ate, contas, sistema: Array.isArray(sistema) ? sistema : [], erro_sistema: sistema?.erro || null, conta_azul: config.demo || (await ca.statusConexao()).conectado };
}));
app.post('/api/extrato/importar', exigeLogin, exigeExtrato, express.raw({ type: () => true, limit: '20mb' }), resp(async (req) => {
  if (!Buffer.isBuffer(req.body) || !req.body.length) throw new Error('Envie o arquivo do extrato (OFX, CSV ou Excel).');
  return extrato.importarExtrato({ bytes: req.body, nome: String(req.query.nome || ''), conta: String(req.query.conta || ''), simular: req.query.simular !== 'false' }, req.usuario);
}));
// Divergências (Conferência): fechamento mensal comercial e financeiro, com observações e ações
const exigeDiv = (req, res, next) => (paginasDe(req.usuario).includes('divergencias') ? next() : res.status(403).json({ erro: 'seu perfil não tem acesso às divergências' }));
const editaDiv = (u) => ['adm', 'diretor', 'financeiro'].includes(u?.perfil);
let cacheSaldosCA = { t: 0, d: [] };
async function saldosContaAzul() {
  if (config.demo) return [{ nome: 'Bradesco', saldo: 18240.55 }, { nome: 'Itaú', saldo: 9310.2 }, { nome: 'Sicoob', saldo: 4120.08 }, { nome: 'InfinitePay', saldo: 1388.4 }];
  if (Date.now() - cacheSaldosCA.t < 4 * 3600e3) return cacheSaldosCA.d;
  const d = await ca.buscarSaldos().catch(() => []);
  cacheSaldosCA = { t: Date.now(), d };
  return d;
}
app.get('/api/divergencias', exigeLogin, exigeDiv, resp(async (req) => ({ ...(await divergencias.lerDivergencias()), saldos_ca: await saldosContaAzul(), pode_editar: editaDiv(req.usuario) })));
app.post('/api/divergencias', exigeLogin, exigeDiv, resp(async (req) => {
  if (!editaDiv(req.usuario)) throw new Error('Só a gestão e o financeiro alteram as divergências.');
  return { ...(await divergencias.salvarDivergencias(req.body || {}, req.usuario)), saldos_ca: await saldosContaAzul(), pode_editar: true };
}));
app.delete('/api/extrato/conta', exigeAdm, resp(async (req) => { await extrato.apagarConta(String(req.query.conta || '')); return { ok: true }; }));

// Mapeamento de colunas e inconsistências da planilha, sem as linhas
app.get('/api/planilha', exigeLogin, async (req, res) => {
  try {
    const d = await dadosDeVendas(req.query.forcar === '1');
    res.json({ fonte: d.fonte, planilha_configurada: planilhaConfigurada(), linhas: d.linhas.length, qualidade: d.qualidade });
  } catch (e) { res.status(502).json({ erro: e.message }); }
});

// Mostra a estrutura crua da API para conferir nomes de campos (usar uma vez após conectar)
app.get('/api/diagnostico', exigeAdm, async (req, res) => {
  try { res.json(await ca.amostraBruta()); } catch (e) { res.status(502).json({ erro: e.message }); }
});

// Página do painel (o arquivo é um fragmento; aqui recebe o cabeçalho HTML completo)
const cabecalho = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><link rel="icon" href="/logo.png"></head><body>';
app.get(['/', '/index.html'], exigeLogin, async (req, res) => {
  const corpo = await fs.readFile(path.join(raiz, 'public', 'painel.html'), 'utf8');
  res.type('html').send(cabecalho + corpo + '</body></html>');
});

google.carregarGoogle().catch(() => {});
pscript.carregarScript().catch(() => {});
app.listen(config.porta, () => {
  console.log(`Painel Comercial Visu em ${config.urlPublica} (porta ${config.porta})`);
  if (!config.senhaPainel) console.warn('ATENÇÃO: PAINEL_SENHA não definida — sem senha mestra de ADM; só entram usuários com convite aceito.');
  if (!config.databaseUrl) console.warn('ATENÇÃO: sem DATABASE_URL, usuários e senhas ficam em arquivo e se perdem quando o servidor reinicia.');
  console.log(`URL de redirecionamento para cadastrar na Conta Azul: ${redirectUri()}`);
  if (config.databaseUrl) statusBanco().then((b) => console.log(b.conectado ? '[banco] DATABASE_URL ok: usuários, senhas e a conexão com a Conta Azul ficam guardados' : `[banco] DATABASE_URL configurada, mas sem conexão: ${b.erro}`));
});
