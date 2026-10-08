// Guarda o token da Conta Azul. A Conta Azul troca o refresh_token a cada renovação,
// então ele precisa ser salvo sempre. Com DATABASE_URL usa Postgres; sem ele, um arquivo.
import fs from 'node:fs/promises';
import path from 'node:path';
import { config } from './config.js';

let pool = null;

async function db() {
  if (!config.databaseUrl) return null;
  if (pool) return pool;
  const { default: pg } = await import('pg');
  pool = new pg.Pool({
    connectionString: config.databaseUrl,
    ssl: config.databaseUrl.includes('localhost') ? false : { rejectUnauthorized: false },
  });
  await pool.query(`CREATE TABLE IF NOT EXISTS conta_azul_token (
    id INT PRIMARY KEY DEFAULT 1, dados JSONB NOT NULL, atualizado_em TIMESTAMPTZ DEFAULT now())`);
  return pool;
}

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
