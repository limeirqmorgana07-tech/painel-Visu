// Painel Comercial Visu — servidor (Seja Expert)
import express from 'express';
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { config, redirectUri } from './src/config.js';
import * as ca from './src/contaAzul.js';
import { dadosDeVendas } from './src/vendas.js';
import { dadosFinanceiros } from './src/financeiro.js';
import { planilhaConfigurada } from './src/planilha.js';
import * as usuarios from './src/usuarios.js';
import { paginasDe, veFinanceiro, veVendas } from './src/paginas.js';

const raiz = path.dirname(fileURLToPath(import.meta.url));
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
background:radial-gradient(120% 140% at 100% 0%,#2F2963 0%,#241E48 60%);color:#241E48}
.cx{background:#fff;padding:32px 28px;border-radius:18px;width:min(360px,90vw);box-shadow:0 20px 50px rgba(60,0,40,.35);text-align:center}
img{width:170px;height:auto;display:block;margin:0 auto;background:#241E48;padding:14px 18px;border-radius:12px}h1{font-size:18px;margin:14px 0 4px}p{margin:0 0 16px;color:#575272;font-size:13.5px;line-height:1.5}
label{display:block;text-align:left;font-size:12px;font-weight:600;color:#575272;margin:10px 0 4px}
input{width:100%;box-sizing:border-box;padding:11px 12px;border:1px solid #CFCCDD;border-radius:10px;font:inherit}
button,.b{display:block;margin-top:14px;width:100%;box-sizing:border-box;padding:11px;border:0;border-radius:10px;background:#E8780C;color:#fff;font:600 15px system-ui;cursor:pointer;text-decoration:none}
.e{color:#c0153a;font-size:13px;margin-top:10px}.d{font-size:12px;color:#8A86A0;margin-top:14px}</style></head><body>
<div class="cx"><img src="/logo-visu.png" alt="Visu Design"><h1>${esc(titulo)}</h1>${corpo}</div></body></html>`;

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
app.get('/api/eu', exigeLogin, (req, res) => res.json({ id: req.usuario.id, nome: req.usuario.nome, email: req.usuario.email || '', perfil: req.usuario.perfil, paginas: paginasDe(req.usuario) }));
app.get('/api/usuarios', exigeAdm, async (req, res) => res.json({ usuarios: await usuarios.listar(), perfis: usuarios.PERFIS, banco: usuarios.bancoConfigurado() }));
app.post('/api/usuarios', exigeAdm, async (req, res) => {
  try { res.json(await usuarios.salvar(req.body || {})); } catch (e) { res.status(400).json({ erro: e.message }); }
});
app.delete('/api/usuarios/:id', exigeAdm, async (req, res) => {
  if (req.params.id === req.usuario.id) return res.status(400).json({ erro: 'Você não pode remover o próprio acesso.' });
  await usuarios.remover(req.params.id); res.json({ ok: true });
});
app.post('/api/usuarios/:id/senha-temporaria', exigeAdm, async (req, res) => {
  try { res.json(await usuarios.gerarSenhaTemporaria(req.params.id)); } catch (e) { res.status(400).json({ erro: e.message }); }
});
app.post('/api/usuarios/:id/convite', exigeAdm, async (req, res) => {
  try { res.json(await usuarios.gerarConvite(req.params.id)); } catch (e) { res.status(400).json({ erro: e.message }); }
});

app.get('/saude', (req, res) => res.json({ ok: true }));
app.get(['/logo.png', '/logo-visu.png'], (req, res) => res.sendFile(path.join(raiz, 'public', req.path.slice(1))));
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
    res.json(await dadosDeVendas(req.query.forcar === '1'));
  } catch (e) {
    console.error('[vendas]', e);
    res.status(502).json({ erro: e.message });
  }
});

// Gestão financeira (DRE, caixa, contas a receber/pagar, saldos) pela API da Conta Azul
app.get('/api/financeiro', exigeLogin, async (req, res) => {
  if (!veFinanceiro(req.usuario)) return res.status(403).json({ erro: 'seu perfil não tem acesso ao financeiro' });
  try { res.json(await dadosFinanceiros(req.query.forcar === '1')); }
  catch (e) { console.error('[financeiro]', e); res.status(502).json({ erro: e.message }); }
});

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

app.listen(config.porta, () => {
  console.log(`Painel Comercial Visu em ${config.urlPublica} (porta ${config.porta})`);
  if (!config.senhaPainel) console.warn('ATENÇÃO: PAINEL_SENHA não definida — sem senha mestra de ADM; só entram usuários com convite aceito.');
  if (!config.databaseUrl) console.warn('ATENÇÃO: sem DATABASE_URL, usuários e senhas ficam em arquivo e se perdem quando o servidor reinicia.');
  console.log(`URL de redirecionamento para cadastrar na Conta Azul: ${redirectUri()}`);
});
