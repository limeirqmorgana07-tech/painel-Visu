// Anexos dos pedidos (v78): comprovantes de pagamento (vendedor e gestão) e nota fiscal (gestão).
// Os arquivos ficam no banco do painel (tabela painel_anexos, coluna BYTEA); sem banco, numa pasta ao lado do token.
// O pedido guarda só a lista (id, tipo, nome, tamanho, quem, quando) no campo "anexos" da 1ª linha do pedido.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { banco } from './tokenStore.js';
import { config } from './config.js';

export const LIMITE_BYTES = 5 * 1024 * 1024;
export const TIPOS_ARQUIVO = ['application/pdf', 'image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif'];
let tabelaOk = false;

async function tabela() {
  const p = await banco();
  if (!p) return null;
  if (!tabelaOk) {
    await p.query(`CREATE TABLE IF NOT EXISTS painel_anexos (
      id TEXT PRIMARY KEY, registro TEXT NOT NULL, codigo TEXT, tipo TEXT NOT NULL, nome TEXT, mime TEXT, tamanho INT,
      dados BYTEA NOT NULL, criado_em TIMESTAMPTZ DEFAULT now(), criado_por TEXT)`);
    tabelaOk = true;
  }
  return p;
}
const pasta = () => path.join(path.dirname(config.arquivoToken), 'anexos');

export async function guardarArquivo({ registro, codigo, tipo, nome, mime, bytes, por }) {
  if (!bytes?.length) throw new Error('Arquivo vazio.');
  if (bytes.length > LIMITE_BYTES) throw new Error('Arquivo maior que 5 MB. Diminua a foto ou salve o PDF menor.');
  if (!TIPOS_ARQUIVO.includes(mime)) throw new Error('Envie PDF ou foto (JPG, PNG, WEBP ou HEIC).');
  const id = crypto.randomUUID();
  const p = await tabela();
  if (p) await p.query('INSERT INTO painel_anexos (id, registro, codigo, tipo, nome, mime, tamanho, dados, criado_por) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)', [id, registro, codigo || null, tipo, nome, mime, bytes.length, bytes, por || '']);
  else {
    await fs.mkdir(pasta(), { recursive: true });
    await fs.writeFile(path.join(pasta(), id), bytes);
    await fs.writeFile(path.join(pasta(), id + '.json'), JSON.stringify({ registro, codigo, tipo, nome, mime }));
  }
  return { id, tamanho: bytes.length };
}

export async function lerArquivo(id) {
  if (!/^[0-9a-f-]{36}$/.test(String(id))) return null;
  const p = await tabela();
  if (p) {
    const r = await p.query('SELECT registro, codigo, tipo, nome, mime, dados FROM painel_anexos WHERE id = $1', [id]);
    return r.rows[0] || null;
  }
  try {
    const meta = JSON.parse(await fs.readFile(path.join(pasta(), id + '.json'), 'utf8'));
    return { ...meta, dados: await fs.readFile(path.join(pasta(), id)) };
  } catch { return null; }
}

export async function apagarArquivo(id) {
  const p = await tabela();
  if (p) { await p.query('DELETE FROM painel_anexos WHERE id = $1', [id]); return; }
  await fs.rm(path.join(pasta(), id), { force: true }); await fs.rm(path.join(pasta(), id + '.json'), { force: true });
}
