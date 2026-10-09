// Lê tipo de produto, material e cor a partir do nome do produto cadastrado na Conta Azul.
// A Conta Azul não tem esses campos separados; os termos vêm do catálogo da Visu.
// Para ajustar sem mexer no código: PRODUTOS_TERMOS_JSON='{"material":{"Poliamida":["pa","poliam"]}}'
import { sem } from './planilha.js';

const PADRAO = {
  tipo: {
    'Camiseta gola polo baby look': ['polo baby', 'gola polo baby', 'polo feminina'],
    'Camiseta gola polo': ['gola polo', 'polo'],
    'Baby look': ['baby look', 'babylook', 'baby'],
    'Regata machão': ['machao'],
    'Regata cavada': ['cavada'],
    Regata: ['regata'],
    Cropped: ['cropped', 'cropp'],
    Ecobag: ['ecobag', 'eco bag'],
    'Sacola esportiva': ['sacola', 'mochila', 'gym sack'],
    Headband: ['headband', 'faixa de cabeca', 'testeira'],
    Munhequeira: ['munhequeira'],
    Bandeira: ['bandeira', 'flamula'],
    Moletom: ['moletom', 'blusao', 'casaco'],
    Short: ['short', 'bermuda'],
    'Camiseta manga longa': ['manga longa', 'ml '],
    'Camiseta básica': ['camiseta', 'camisa', 'basica', 't-shirt', 'tshirt'],
  },
  material: {
    'Dry-fit poliamida': ['dry fit poliamida', 'dryfit poliamida', 'dry-fit poliamida'],
    'Dry-fit poliéster': ['dry fit', 'dryfit', 'dry-fit', 'poliester', 'sublimad', 'sublimacao'],
    Poliamida: ['poliamida', ' pa '],
    '100% algodão': ['algodao', '100%', 'penteado', 'fio 30'],
    'PV / malha mista': [' pv ', 'malha pv', 'piquet', 'pique'],
  },
  cor: {
    'Azul marinho': ['azul marinho', 'marinho'],
    'Azul royal': ['azul royal', 'royal'],
    Azul: ['azul'],
    Preto: ['preto', 'preta'],
    Branco: ['branco', 'branca'],
    Cinza: ['cinza', 'mescla', 'chumbo'],
    Vermelho: ['vermelho', 'vermelha'],
    Verde: ['verde'],
    Rosa: ['rosa', 'pink'],
    Amarelo: ['amarelo', 'amarela'],
    Laranja: ['laranja'],
    Roxo: ['roxo', 'roxa', 'lilas'],
    Colorida: ['colorid', 'estampad', 'sublimacao total', 'full print'],
  },
};

let termos = PADRAO;
try {
  if (process.env.PRODUTOS_TERMOS_JSON) {
    const extra = JSON.parse(process.env.PRODUTOS_TERMOS_JSON);
    termos = { ...PADRAO };
    for (const k of Object.keys(extra)) termos[k] = { ...extra[k], ...PADRAO[k] };
  }
} catch { /* mantém o padrão */ }

function achar(texto, grupo) {
  const t = ` ${sem(texto).replace(/[^a-z0-9%]+/g, ' ')} `;
  for (const [rotulo, chaves] of Object.entries(termos[grupo])) {
    if (chaves.some((c) => t.includes(sem(c)))) return rotulo;
  }
  return '';
}

export function lerAtributos(nome, descricao = '') {
  const texto = `${nome} ${descricao}`;
  return {
    tipo_produto: achar(texto, 'tipo'),
    material: achar(texto, 'material'),
    especificacao: /sublima/i.test(sem(texto)) ? 'Sublimação' : /bordad/i.test(sem(texto)) ? 'Bordado' : /silk|serigraf/i.test(sem(texto)) ? 'Silk' : '',
    cor: achar(texto, 'cor'),
  };
}
