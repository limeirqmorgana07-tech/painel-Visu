// Guarda o token da Conta Azul. A Conta Azul troca o refresh_token a cada renovação,
// então ele precisa ser salvo sempre. Com DATABASE_URL usa Postgres; sem ele, um arquivo.
import fs from 'node:fs/promises';
import path from 'node:path';
import { config } from './config.js';

let pool = null;
let falhouEm = 0;
export let erroBanco = '';

// Aceita a connection string do jeito que o Neon mostra (às vezes vem como: psql 'postgresql://...')
const limparUrl = (u) => String(u || '').trim().replace(/^psql\s+/i, '').replace(/^['"]|['"]$/g, '').trim();

// Se o banco não responder, o painel continua no ar usando arquivo e tenta o banco de novo em 1 minuto.
async function db() {
  const url = limparUrl(config.databaseUrl);
  if (!url) return null;
  if (pool) return pool;
  if (Date.now() - falhouEm < 60e3) return null;
  try {
    const { default: pg } = await import('pg');
    const p = new pg.Pool({ connectionString: url, ssl: url.includes('localhost') ? false : { rejectUnauthorized: false }, max: 4, connectionTimeoutMillis: 10000 });
    p.on('error', (e) => { console.error('[banco] conexão perdida:', e.message); });
    await p.query(`CREATE TABLE IF NOT EXISTS conta_azul_token (
      id INT PRIMARY KEY DEFAULT 1, dados JSONB NOT NULL, atualizado_em TIMESTAMPTZ DEFAULT now())`);
    await p.query('CREATE TABLE IF NOT EXISTS painel_kv (chave TEXT PRIMARY KEY, dados JSONB NOT NULL, atualizado_em TIMESTAMPTZ DEFAULT now())');
    pool = p; erroBanco = '';
    console.log('[banco] conectado ao Postgres');
    return pool;
  } catch (e) {
    falhouEm = Date.now(); erroBanco = e.message;
    console.error('[banco] não foi possível conectar (usando arquivo por enquanto):', e.message);
    return null;
  }
}
export async function statusBanco() { const p = await db(); return { configurado: !!limparUrl(config.databaseUrl), conectado: !!p, erro: erroBanco || null }; }

export async function lerToken() {
  const p = await db();
  if (p) {
    const r = await p.query('SELECT dados FROM conta_azul_token WHERE id = 1');
    return r.rows[0]?.dados || null;
  }
  try {
    return JSON.parse(await fs.readFile(config.arquivoToken, 'utf8'));
  } catch {
    return null;
  }
}

export async function salvarToken(dados) {
  const p = await db();
  if (p) {
    await p.query(
      `INSERT INTO conta_azul_token (id, dados, atualizado_em) VALUES (1, $1, now())
       ON CONFLICT (id) DO UPDATE SET dados = EXCLUDED.dados, atualizado_em = now()`,
      [dados]
    );
    return;
  }
  await fs.mkdir(path.dirname(config.arquivoToken), { recursive: true });
  await fs.writeFile(config.arquivoToken, JSON.stringify(dados), { mode: 0o600 });
}

export async function apagarToken() {
  const p = await db();
  if (p) return p.query('DELETE FROM conta_azul_token WHERE id = 1');
  await fs.rm(config.arquivoToken, { force: true });
}

// Armazenamento genérico (ex.: cache dos itens das vendas, para não buscar tudo de novo a cada reinício)
export async function lerKV(chave) {
  const p = await db();
  if (p) {
    const r = await p.query('SELECT dados FROM painel_kv WHERE chave = $1', [chave]);
    return r.rows[0]?.dados ?? null;
  }
  try { return JSON.parse(await fs.readFile(path.join(path.dirname(config.arquivoToken), `${chave}.json`), 'utf8')); } catch { return null; }
}

export async function salvarKV(chave, dados) {
  const p = await db();
  if (p) {
    await p.query(`INSERT INTO painel_kv (chave, dados, atualizado_em) VALUES ($1, $2, now())
      ON CONFLICT (chave) DO UPDATE SET dados = EXCLUDED.dados, atualizado_em = now()`, [chave, JSON.stringify(dados)]);
    return;
  }
  await fs.mkdir(path.dirname(config.arquivoToken), { recursive: true });
  await fs.writeFile(path.join(path.dirname(config.arquivoToken), `${chave}.json`), JSON.stringify(dados));
}
