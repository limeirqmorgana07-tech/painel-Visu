"""BI Financeiro (padrão Mais Controle) sobre a base unificada TituloFinanceiro.

- Fluxo de caixa projetado: mensal (realizado nos meses passados + previsto) e diário.
- Resultado por obra / centro de custo: previsto (competência) x realizado (caixa).
- Top 10 clientes e favorecidos.
- Atrasos por centro de custo, cliente e favorecido (com faixas de dias).
- Compras com e sem ordem de compra (Materiais e Equipamentos).
- DDA: boletos do banco x contas a pagar lançadas (lançado / falta lançar).
"""
import csv
import io
import os
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher

from ..extensions import db
from ..models import BoletoDDA, Configuracao, Empresa, TituloFinanceiro
from .fin_dados import data as _data, financeira, norm, num as _num

MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
FAIXAS_ATRASO = [("1 a 30 dias", 1, 30), ("31 a 60 dias", 31, 60), ("61 a 90 dias", 61, 90), ("Mais de 90 dias", 91, 99999)]


def rot_mes(y, m):
    return f"{MESES[m - 1]}/{str(y)[2:]}"


def _add_mes(y, m, n):
    m0 = y * 12 + (m - 1) + n
    return m0 // 12, m0 % 12 + 1


def _q(empresa_id=None, tipo=None):
    q = TituloFinanceiro.query
    if empresa_id:
        q = q.filter(TituloFinanceiro.empresa_id == empresa_id)
    if tipo:
        q = q.filter(TituloFinanceiro.tipo == tipo)
    return q


def eh_transferencia(t):
    n = norm(t.categoria) + " " + norm(t.natureza)
    return "TRANSFERENCIA" in n


def tem_dados():
    return TituloFinanceiro.query.first() is not None


# ---------------------------------------------------------------- classificação das despesas

class Grupos:
    """Grupo de gasto de um título: classificação do usuário (Categorias de gasto) ou, na falta, o grupo que
    o próprio Mais Controle informa. None = categoria oculta (lucros, empréstimos, transferências...)."""

    def __init__(self):
        from .categorias import Classificador
        self.cl = Classificador()

    def de(self, t):
        from .categorias import grupo
        if eh_transferencia(t):   # transferência entre contas/empresas nunca é despesa
            return None
        cat = self.cl.categoria(t.categoria or "")
        if cat is not None:
            return grupo(cat)
        g = norm(t.grupo)
        if g.startswith("MATERIA"):
            return "Materiais"
        if g.startswith("EQUIPAMENTO"):
            return "Equipamentos"
        if g.startswith("MAO DE OBRA"):
            return "Mão de obra"
        return "Administrativo e outros" if g else "Sem classificação"


# ---------------------------------------------------------------- fluxo de caixa

def saldo_inicial():
    return _num(Configuracao.obter("fluxo_saldo_inicial", "0"))


def _boletos_a_lancar(empresa_id=None):
    q = BoletoDDA.query.filter(BoletoDDA.titulo_chave.is_(None), BoletoDDA.ignorado.is_(False))
    if empresa_id:
        q = q.filter(db.or_(BoletoDDA.empresa_id == empresa_id, BoletoDDA.empresa_id.is_(None)))
    return q.all()


def fluxo(empresa_id=None, modo="mensal", dias=30, sem_transf=True, saldo=None, vencidos_no_inicio=True,
          meses_passados=6, meses_futuros=11, hoje=None):
    hoje = hoje or date.today()
    saldo = saldo_inicial() if saldo is None else saldo
    todos = [t for t in _q(empresa_id).all() if not (sem_transf and eh_transferencia(t))]
    abertos = [t for t in todos if t.aberto and t.saldo > 0]
    dda = _boletos_a_lancar(empresa_id)
    venc_ent = sum(t.saldo for t in abertos if t.tipo == "receber" and t.vencimento and t.vencimento < hoje)
    venc_sai = sum(t.saldo for t in abertos if t.tipo == "pagar" and t.vencimento and t.vencimento < hoje)
    venc_dda = sum(b.valor or 0 for b in dda if b.vencimento and b.vencimento < hoje)
    sem_data = [t for t in abertos if not t.vencimento]

    if modo == "diario":
        chaves = [hoje + timedelta(days=i) for i in range(max(1, min(int(dias or 30), 180)))]
        chave_de = (lambda d: d)
        rot = (lambda d: d.strftime("%d/%m") + " " + ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"][d.weekday()])
    else:
        ini_y, ini_m = _add_mes(hoje.year, hoje.month, -meses_passados)
        chaves = [_add_mes(ini_y, ini_m, i) for i in range(meses_passados + 1 + meses_futuros)]
        chave_de = (lambda d: (d.year, d.month))
        rot = (lambda k: rot_mes(*k))
    linhas = {k: {"chave": k, "rotulo": rot(k), "ent_real": 0.0, "sai_real": 0.0, "ent_prev": 0.0, "sai_prev": 0.0,
                  "dda": 0.0, "qtd_prev": 0} for k in chaves}
    from .fin_dados import Realizado
    real = Realizado(empresa_id)
    for t in todos:
        if modo != "mensal":
            break
        for d_, v_ in real.de(t):
            k = chave_de(d_)
            if k in linhas:
                linhas[k]["ent_real" if t.tipo == "receber" else "sai_real"] += v_
    for t in abertos:
        if not t.vencimento or t.vencimento < hoje:
            continue
        k = chave_de(t.vencimento)
        if k in linhas:
            linhas[k]["ent_prev" if t.tipo == "receber" else "sai_prev"] += t.saldo
            linhas[k]["qtd_prev"] += 1
    for b in dda:
        if b.vencimento and b.vencimento >= hoje:
            k = chave_de(b.vencimento)
            if k in linhas:
                linhas[k]["dda"] += b.valor or 0
    lista = [linhas[k] for k in chaves]
    atual = chave_de(hoje)
    acumulado = saldo + ((venc_ent - venc_sai - venc_dda) if vencidos_no_inicio else 0.0)
    for x in lista:
        x["passado"] = modo == "mensal" and x["chave"] < atual
        x["atual"] = x["chave"] == atual
        if x["passado"]:
            x["resultado"] = x["ent_real"] - x["sai_real"]
            x["acumulado"] = None
        else:
            x["resultado"] = x["ent_prev"] - x["sai_prev"] - x["dda"]
            acumulado += x["resultado"]
            x["acumulado"] = acumulado
        for c in ("ent_real", "sai_real", "ent_prev", "sai_prev", "dda", "resultado"):
            x[c] = round(x[c], 2)
        if x["acumulado"] is not None:
            x["acumulado"] = round(x["acumulado"], 2)
        if isinstance(x["chave"], date):
            x["de"] = x["ate"] = x["chave"]
        else:
            y, m = x["chave"]
            ny, nm = _add_mes(y, m, 1)
            x["de"], x["ate"] = date(y, m, 1), date(ny, nm, 1) - timedelta(days=1)
    grafico = [{"rotulo": x["rotulo"], "passado": x["passado"], "ent_real": x["ent_real"], "sai_real": x["sai_real"],
                "ent_prev": x["ent_prev"], "sai_prev": x["sai_prev"], "dda": x["dda"], "acumulado": x["acumulado"],
                "de": x["de"].isoformat(), "ate": x["ate"].isoformat()} for x in lista]
    futuros = [x for x in lista if not x["passado"]]
    negativo = next((x for x in futuros if x["acumulado"] is not None and x["acumulado"] < 0), None)
    return {"modo": modo, "linhas": lista, "grafico": grafico, "saldo": saldo, "hoje": hoje, "dias": dias,
            "vencidos": {"entradas": round(venc_ent, 2), "saidas": round(venc_sai, 2), "dda": round(venc_dda, 2)},
            "vencidos_no_inicio": vencidos_no_inicio,
            "totais": {"entradas": round(sum(x["ent_prev"] for x in futuros), 2),
                       "saidas": round(sum(x["sai_prev"] for x in futuros), 2),
                       "dda": round(sum(x["dda"] for x in futuros), 2)},
            "saldo_final": futuros[-1]["acumulado"] if futuros else saldo, "primeiro_negativo": negativo,
            "sem_data": len(sem_data), "sem_data_valor": round(sum(t.saldo for t in sem_data), 2),
            "sem_transf": sem_transf}


def titulos_periodo(empresa_id=None, de=None, ate=None, tipo=None, realizado=False, vencidos=False,
                    sem_transf=True, hoje=None):
    hoje = hoje or date.today()
    q = _q(empresa_id, tipo)
    if vencidos:
        q = q.filter(TituloFinanceiro.aberto.is_(True), TituloFinanceiro.vencimento < hoje)
    elif realizado:
        from ..models import BaixaFinanceira
        if BaixaFinanceira.query.first():
            bq = db.session.query(BaixaFinanceira.empresa_id, BaixaFinanceira.chave).filter(
                BaixaFinanceira.data >= de, BaixaFinanceira.data <= ate)
            if tipo:
                bq = bq.filter(BaixaFinanceira.tipo == tipo)
            alvo = set(bq.all())
            lst = [t for t in q.order_by(TituloFinanceiro.vencimento).all()
                   if (t.empresa_id, t.chave) in alvo and not (sem_transf and eh_transferencia(t))]
            return lst
        q = q.filter(TituloFinanceiro.baixado_em >= de, TituloFinanceiro.baixado_em <= ate)
    else:
        q = q.filter(TituloFinanceiro.aberto.is_(True), TituloFinanceiro.vencimento >= max(de, hoje),
                     TituloFinanceiro.vencimento <= ate)
    lst = [t for t in q.order_by(TituloFinanceiro.vencimento, TituloFinanceiro.valor.desc()).all()
           if not (sem_transf and eh_transferencia(t))]
    return lst


# ---------------------------------------------------------------- resultado por obra / centro de custo

def _cc(t):
    return (t.centro_custo or "Sem centro de custo").strip()


def resultado(empresa_id=None, ini=None, fim=None, cc=None):
    hoje = date.today()
    fim = fim or hoje
    ini = ini or date(fim.year, 1, 1)
    gr = Grupos()
    por = defaultdict(lambda: {"rec_prev": 0.0, "rec_real": 0.0, "desp_prev": 0.0, "desp_real": 0.0, "obra_ext": None})
    clientes, favorecidos = defaultdict(float), defaultdict(float)
    por_mes = defaultdict(lambda: {"rec": 0.0, "desp": 0.0})
    detalhe = []
    from .fin_dados import Realizado
    realiz = Realizado(empresa_id, ini)
    for t in _q(empresa_id).all():
        if t.tipo == "receber":
            if financeira(t.natureza) or eh_transferencia(t):
                continue
        elif gr.de(t) is None:
            continue
        c = _cc(t)
        if cc and norm(c) != norm(cc):
            continue
        p = por[c]
        p["obra_ext"] = p["obra_ext"] or t.obra_ext
        prev = t.competencia and ini <= t.competencia <= fim
        bx = [(d_, v_) for d_, v_ in realiz.de(t) if d_ and ini <= d_ <= fim]
        real = bool(bx)
        if t.tipo == "receber":
            if prev:
                p["rec_prev"] += t.valor or 0
            for d_, v_ in bx:
                p["rec_real"] += v_
                clientes[t.nome or "—"] += v_
                por_mes[(d_.year, d_.month)]["rec"] += v_
        else:
            if prev:
                p["desp_prev"] += t.valor or 0
            for d_, v_ in bx:
                p["desp_real"] += v_
                favorecidos[t.nome or "—"] += v_
                por_mes[(d_.year, d_.month)]["desp"] += v_
        if cc and (prev or real):
            detalhe.append(t)
    linhas = []
    for c, p in por.items():
        if not any(p[k] for k in ("rec_prev", "rec_real", "desp_prev", "desp_real")):
            continue
        r_prev, r_real = p["rec_prev"] - p["desp_prev"], p["rec_real"] - p["desp_real"]
        linhas.append({"cc": c, "obra_ext": p["obra_ext"], **{k: round(v, 2) for k, v in p.items() if k != "obra_ext"},
                       "res_prev": round(r_prev, 2), "res_real": round(r_real, 2),
                       "margem_real": round(r_real / p["rec_real"] * 100, 1) if p["rec_real"] else None})
    linhas.sort(key=lambda x: -(x["rec_real"] + x["desp_real"]))
    tot = {k: round(sum(x[k] for x in linhas), 2) for k in ("rec_prev", "rec_real", "desp_prev", "desp_real",
                                                           "res_prev", "res_real")}
    tot["margem_real"] = round(tot["res_real"] / tot["rec_real"] * 100, 1) if tot["rec_real"] else None
    from .bi import meses_entre
    meses = meses_entre(ini, fim)
    serie = [{"rotulo": rot_mes(y, m), "rec": round(por_mes[(y, m)]["rec"], 2), "desp": round(por_mes[(y, m)]["desp"], 2),
              "res": round(por_mes[(y, m)]["rec"] - por_mes[(y, m)]["desp"], 2)} for y, m in meses]
    return {"ini": ini, "fim": fim, "linhas": linhas, "tot": tot, "serie": serie, "cc": cc,
            "top_clientes": sorted(clientes.items(), key=lambda x: -x[1])[:10],
            "top_favorecidos": sorted(favorecidos.items(), key=lambda x: -x[1])[:10],
            "detalhe": sorted(detalhe, key=lambda t: (t.baixado_em or t.competencia or date.min), reverse=True)[:400]}


# ---------------------------------------------------------------- atrasos

def atrasos(empresa_id=None, hoje=None, sem_transf=True):
    hoje = hoje or date.today()
    out = {}
    for tipo in ("pagar", "receber"):
        ts = [t for t in _q(empresa_id, tipo).filter(TituloFinanceiro.aberto.is_(True),
                                                      TituloFinanceiro.vencimento < hoje).all()
              if t.saldo > 0 and not (sem_transf and eh_transferencia(t))]
        por_cc, por_nome = defaultdict(float), defaultdict(float)
        faixas = {f[0]: 0.0 for f in FAIXAS_ATRASO}
        for t in ts:
            por_cc[_cc(t)] += t.saldo
            por_nome[t.nome or "—"] += t.saldo
            d = (hoje - t.vencimento).days
            for rot, a, b in FAIXAS_ATRASO:
                if a <= d <= b:
                    faixas[rot] += t.saldo
        out[tipo] = {"total": round(sum(t.saldo for t in ts), 2), "qtd": len(ts),
                     "por_cc": sorted(((k, round(v, 2)) for k, v in por_cc.items()), key=lambda x: -x[1])[:15],
                     "por_nome": sorted(((k, round(v, 2)) for k, v in por_nome.items()), key=lambda x: -x[1])[:15],
                     "faixas": [(k, round(v, 2)) for k, v in faixas.items()],
                     "lista": sorted(ts, key=lambda t: (t.vencimento, -t.saldo))[:300]}
    return out


# ---------------------------------------------------------------- compras com e sem OC

def compras_oc(empresa_id=None, ini=None, fim=None):
    """Materiais e equipamentos lançados no financeiro, com e sem ordem de compra (Mais Controle) / pedido (Omie)."""
    hoje = date.today()
    fim = fim or hoje
    ini = ini or date(fim.year - 1, fim.month, 1)
    gr = Grupos()
    emp = {e.id: e.nome for e in Empresa.query.all()}
    from .bi import meses_entre
    meses = meses_entre(ini, fim)
    serie = {k: {"com": 0.0, "sem": 0.0} for k in meses}
    forn_sem, cc_sem, por_emp = defaultdict(float), defaultdict(float), defaultdict(lambda: {"com": 0.0, "sem": 0.0})
    por_grupo = defaultdict(lambda: {"com": 0.0, "sem": 0.0})
    sem_lista = []
    q = _q(empresa_id, "pagar").filter(TituloFinanceiro.competencia >= ini, TituloFinanceiro.competencia <= fim)
    for t in q.all():
        g = gr.de(t)
        if g not in ("Materiais", "Equipamentos"):
            continue
        k = "com" if (t.ordem_compra or "").strip() not in ("", "0", "-") else "sem"
        v = t.valor or 0
        mk = (t.competencia.year, t.competencia.month)
        if mk in serie:
            serie[mk][k] += v
        por_emp[emp.get(t.empresa_id, "—")][k] += v
        por_grupo[g][k] += v
        if k == "sem":
            forn_sem[t.nome or "—"] += v
            cc_sem[_cc(t)] += v
            sem_lista.append(t)
    com = sum(x["com"] for x in serie.values())
    sem = sum(x["sem"] for x in serie.values())
    return {"ini": ini, "fim": fim, "com": round(com, 2), "sem": round(sem, 2), "total": round(com + sem, 2),
            "pct_com": round(com / (com + sem) * 100, 1) if com + sem else 0.0,
            "serie": [{"rotulo": rot_mes(y, m), "com": round(serie[(y, m)]["com"], 2),
                       "sem": round(serie[(y, m)]["sem"], 2)} for y, m in meses],
            "por_empresa": {k: {kk: round(vv, 2) for kk, vv in v.items()} for k, v in por_emp.items()},
            "por_grupo": {k: {kk: round(vv, 2) for kk, vv in v.items()} for k, v in por_grupo.items()},
            "top_forn_sem": sorted(((k, round(v, 2)) for k, v in forn_sem.items()), key=lambda x: -x[1])[:10],
            "top_cc_sem": sorted(((k, round(v, 2)) for k, v in cc_sem.items()), key=lambda x: -x[1])[:10],
            "sem_lista": sorted(sem_lista, key=lambda t: -(t.valor or 0))[:200],
            "tem_dados": bool(com or sem)}


# ---------------------------------------------------------------- DDA

CAB_NOME = ("BENEFICIARIO", "CEDENTE", "FAVORECIDO", "SACADOR", "EMITENTE", "RAZAO SOCIAL", "NOME")
CAB_CNPJ = ("CNPJ", "CPF")
CAB_VENC = ("VENCIMENTO", "VENC", "DATA DE VENCIMENTO", "DT VENC")
CAB_VALOR = ("A PAGAR", "VALOR A PAGAR", "VALOR DO DOCUMENTO", "VALOR NOMINAL", "VALOR DO BOLETO", "VALOR ORIGINAL",
             "ATE VENC", "VALOR")
CAB_LINHA = ("LINHA DIGITAVEL", "CODIGO DE BARRAS", "COD BARRAS", "LINHA")
CAB_DOC = ("N DOC", "NO DOC", "NUM DOC", "NUMERO DO DOCUMENTO", "N DO DOCUMENTO", "DOCUMENTO", "SEU NUMERO")
CAB_PAGADOR = ("PAGADOR", "SACADO", "EMPRESA")
CAB_TIPO = ("TIPO DE BOLETO", "TIPO", "ESPECIE")
CAB_BANCO = ("BANCO",)


def _ler_tabela(caminho):
    ext = os.path.splitext(caminho)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        import openpyxl
        wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
        for ws in wb.worksheets:
            yield from ([c for c in r] for r in ws.iter_rows(values_only=True))
        return
    if ext == ".xls":
        try:
            import xlrd
        except ImportError:
            raise ValueError("Para ler .xls, abra no Excel e salve como .xlsx (Pasta de Trabalho do Excel).")
        wb = xlrd.open_workbook(caminho)
        for sh in wb.sheets():
            for i in range(sh.nrows):
                linha = []
                for c in sh.row(i):
                    if c.ctype == xlrd.XL_CELL_DATE:
                        linha.append(xlrd.xldate.xldate_as_datetime(c.value, wb.datemode))
                    else:
                        linha.append(c.value)
                yield linha
        return
    if ext == ".pdf":
        import pdfplumber
        with pdfplumber.open(caminho) as pdf:
            achou = False
            for p in pdf.pages:
                tabelas = p.extract_tables() or \
                    p.extract_tables({"vertical_strategy": "text", "horizontal_strategy": "text"}) or []
                for t in tabelas:
                    for r in t:
                        achou = True
                        yield [(" ".join(str(c).split()) if c is not None else "") for c in r]
                p.close()
            if not achou:
                raise ValueError("Não encontrei a tabela de boletos nesse PDF (é imagem ou print?). "
                                 "Exporte a lista do DDA em Excel ou salve a tela como PDF pelo navegador.")
        return
    if ext in (".csv", ".txt"):
        bruto = open(caminho, "rb").read()
        texto = bruto.decode("latin-1")
        for enc in ("utf-8-sig", "latin-1"):
            try:
                texto = bruto.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        try:
            dialeto = csv.Sniffer().sniff(texto[:4000], delimiters=";,\t")
        except csv.Error:
            class dialeto(csv.excel):
                delimiter = ";"
        yield from csv.reader(io.StringIO(texto), dialeto)
        return
    if ext in (".png", ".jpg", ".jpeg"):
        raise ValueError("Print da tela não dá para ler automaticamente. No app do Itaú, exporte a lista do DDA "
                         "em Excel/PDF, ou monte a planilha no modelo (Beneficiário, CNPJ, Vencimento, Nº doc., Valor).")
    raise ValueError("Formato não suportado. Envie o DDA em Excel (.xlsx ou .xls), CSV ou PDF.")


def _col(cab, opcoes):
    for op in opcoes:
        for i, c in enumerate(cab):
            if c == op or c.startswith(op + " ") or (len(op) > 5 and op in c):
                return i
    return None


def empresa_do_pagador(nome, empresas=None):
    """Pagador do DDA -> empresa do sistema (RAMOS DINIZ... -> Ramos; F. DINIZ / VIEIRA DINIZ... -> F. Diniz)."""
    n = norm(nome)
    if not n:
        return None
    empresas = empresas if empresas is not None else Empresa.query.all()
    ramos = [e for e in empresas if "RAMOS" in norm(e.nome)]
    outras = [e for e in empresas if "RAMOS" not in norm(e.nome)]
    if "RAMOS" in n:
        return ramos[0].id if ramos else None
    if "DINIZ" in n and outras:
        return outras[0].id
    return None


def ler_dda(caminho):
    """Lê o arquivo do DDA (Itaú ou outro banco): acha a linha de cabeçalho e as colunas pelo nome."""
    linhas = list(_ler_tabela(caminho))
    cab_i, cols = None, None
    for i, r in enumerate(linhas[:60]):
        cab = [norm(c) for c in r]
        v, n = _col(cab, CAB_VENC), _col(cab, CAB_VALOR)
        if v is not None and n is not None:
            cab_i, cols = i, {"nome": _col(cab, CAB_NOME), "cnpj": _col(cab, CAB_CNPJ), "venc": v, "valor": n,
                              "linha": _col(cab, CAB_LINHA), "doc": _col(cab, CAB_DOC), "pagador": _col(cab, CAB_PAGADOR),
                              "tipo": _col(cab, CAB_TIPO), "banco": _col(cab, CAB_BANCO)}
            break
    if cab_i is None:
        raise ValueError("Não encontrei as colunas de vencimento e valor no arquivo do DDA. Confira se é a lista "
                         "de boletos (com Beneficiário, Vencimento e Valor).")
    out = []
    for r in linhas[cab_i + 1:]:
        def pega(c):
            i = cols[c]
            return r[i] if i is not None and i < len(r) else None
        venc = _data(pega("venc"))
        valor = pega("valor")
        valor = float(valor) if isinstance(valor, (int, float)) else _num(re.sub(r"[^\d,.\-]", "", str(valor or "")))
        if not venc or not valor:
            continue
        banco = pega("banco")
        banco = str(int(banco)) if isinstance(banco, float) else str(banco or "")
        out.append({"beneficiario": str(pega("nome") or "").strip()[:200] or None,
                    "cnpj": re.sub(r"\D", "", str(pega("cnpj") or ""))[:14] or None,
                    "vencimento": venc, "valor": round(abs(valor), 2),
                    "linha": re.sub(r"\D", "", str(pega("linha") or ""))[:60] or None,
                    "documento": str(pega("doc") or "").strip()[:60] or None,
                    "pagador": str(pega("pagador") or "").strip()[:200] or None,
                    "tipo": str(pega("tipo") or "").strip()[:60] or None,
                    "banco": re.sub(r"\D", "", banco).zfill(3)[:5] if re.sub(r"\D", "", banco) else None})
    if not out:
        raise ValueError("O arquivo do DDA não tem boletos com vencimento e valor.")
    return out


def importar_dda(caminho, arquivo, empresa_id=None):
    """Grava os boletos (sem duplicar: mesma linha digitável, ou mesmo beneficiário+vencimento+valor) e concilia."""
    regs = ler_dda(caminho)
    chave = lambda nome, venc, valor, doc: (norm(nome), venc, round(valor or 0, 2), norm(doc))
    existentes = {chave(b.beneficiario, b.vencimento, b.valor, b.documento) for b in BoletoDDA.query.all()}
    linhas_exist = {b.linha for b in BoletoDDA.query.filter(BoletoDDA.linha.isnot(None))}
    empresas = Empresa.query.all()
    novos = 0
    for r in regs:
        k = chave(r["beneficiario"], r["vencimento"], r["valor"], r["documento"])
        if (r["linha"] and r["linha"] in linhas_exist) or k in existentes:
            continue
        existentes.add(k)
        emp = empresa_id or empresa_do_pagador(r["pagador"], empresas)
        db.session.add(BoletoDDA(empresa_id=emp, arquivo=arquivo[:200], **r))
        novos += 1
    db.session.flush()
    c = conciliar()
    db.session.commit()
    return {"lidos": len(regs), "novos": novos, **c}


def _parecido(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 0.9
    ta, tb = set(a.split()) - {"LTDA", "ME", "EPP", "SA", "S", "A", "EIRELI", "DE", "DA", "DO"}, \
        set(b.split()) - {"LTDA", "ME", "EPP", "SA", "S", "A", "EIRELI", "DE", "DA", "DO"}
    j = len(ta & tb) / len(ta | tb) if ta | tb else 0
    return max(j, SequenceMatcher(None, a, b).ratio())


def _mesmo_doc(a, b):
    """Nº do documento do boleto x do lançamento (muitos boletos trazem o nº da nota: 89669, 000228092...)."""
    da, db_ = re.sub(r"\D", "", str(a or "")).lstrip("0"), re.sub(r"\D", "", str(b or "")).lstrip("0")
    if len(da) < 4 or len(db_) < 4:
        return False
    return da == db_ or da.startswith(db_) or db_.startswith(da)


def conciliar(refazer=False):
    """Liga cada boleto do DDA a uma conta a pagar: mesmo valor e vencimento até 5 dias de diferença (ou até 45 com
    o mesmo nº de documento). Conta em aberto, nº do documento e vencimento igual pesam a favor.
    Quando há mais de uma conta a pagar igualmente possível (ex.: duas parcelas do mesmo fornecedor com o mesmo
    valor), NÃO vincula sozinho: o boleto fica em “Conferir” para escolher à mão.
    Vínculos e 'ignorar' feitos à mão são mantidos."""
    boletos = BoletoDDA.query.filter(BoletoDDA.manual.is_(False)).all()
    usados = {(b.titulo_empresa_id, b.titulo_chave) for b in BoletoDDA.query.filter(BoletoDDA.manual.is_(True))
              if b.titulo_chave}
    for b in boletos:
        b.titulo_chave = b.titulo_empresa_id = None
        b.conferir = 0
    if not boletos:
        return {"lancados": 0, "faltando": 0, "conferir": 0}
    vmin = min(b.vencimento for b in boletos) - timedelta(days=40)
    vmax = max(b.vencimento for b in boletos) + timedelta(days=40)
    cands = defaultdict(list)
    for t in TituloFinanceiro.query.filter(TituloFinanceiro.tipo == "pagar", TituloFinanceiro.vencimento >= vmin,
                                           TituloFinanceiro.vencimento <= vmax).all():
        cands[round(t.valor or 0)].append(t)
    opcoes = defaultdict(list)    # boleto -> [(score, dias, t)]
    for b in boletos:
        for chave in (round(b.valor) - 1, round(b.valor), round(b.valor) + 1):
            for t in cands.get(chave, []):
                if abs((t.valor or 0) - b.valor) > max(0.05, b.valor * 0.001):
                    continue
                if b.empresa_id and t.empresa_id != b.empresa_id:
                    continue
                dias = abs((t.vencimento - b.vencimento).days)
                sim = _parecido(b.beneficiario, t.nome)
                mesmo_doc = _mesmo_doc(b.documento, t.documento)
                # v1.43.7: vencimento distante só com o mesmo nº de documento (antes bastava o nome parecido e
                # o boleto da parcela 2 caía na parcela já paga de outra nota do mesmo fornecedor)
                # v1.44.1: conta EM ABERTO do mesmo fornecedor (nome parecido) também liga com até 15 dias
                if not (dias <= 5 or (mesmo_doc and dias <= 45) or (t.aberto and sim >= 0.7 and dias <= 15)):
                    continue
                if not t.aberto and dias > 3 and not mesmo_doc:
                    continue   # conta já paga com outro vencimento não é a deste boleto
                score = sim * 2 + (1 - dias / 40) + (0.6 if t.aberto else 0) + \
                    (1.0 if mesmo_doc else 0) + (0.8 if dias == 0 else 0)
                opcoes[b.id].append((score, dias, t))
    # boletos com opção mais forte primeiro
    ordem = sorted(boletos, key=lambda b: -max((o[0] for o in opcoes.get(b.id, [])), default=-1))
    ligados, conferir = set(), 0
    for b in ordem:
        livres = sorted([o for o in opcoes.get(b.id, []) if (o[2].empresa_id, o[2].chave) not in usados],
                        key=lambda o: -o[0])
        if not livres:
            continue
        melhor = livres[0]
        empatados = [o for o in livres[1:] if melhor[0] - o[0] < 0.35]
        # vencimento idêntico só em um deles resolve o empate; senão, deixa para escolher à mão
        if empatados and not (melhor[1] == 0 and all(o[1] != 0 for o in empatados)):
            b.conferir = 1 + len(empatados)
            conferir += 1
            continue
        t = melhor[2]
        b.titulo_empresa_id, b.titulo_chave = t.empresa_id, t.chave
        ligados.add(b.id)
        usados.add((t.empresa_id, t.chave))
    db.session.flush()
    return {"lancados": len(ligados), "conferir": conferir,
            "faltando": sum(1 for b in boletos if b.id not in ligados and not b.ignorado and not b.conferir)}


def _bate_busca(q, *textos):
    """Busca livre do DDA: cada palavra precisa aparecer em algum campo (nome, nº doc./nota, valor)."""
    alvo = " ".join(norm(str(t or "")) for t in textos)
    digitos = re.sub(r"\D", "", alvo)
    for p in norm(q).split():
        if p in alvo:
            continue
        pd = re.sub(r"\D", "", p)
        if pd and pd.lstrip("0") and pd.lstrip("0") in digitos:
            continue
        return False
    return True


def _valor_txt(v):
    v = float(v or 0)
    return f"{v:.2f} {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + f" {v:.2f}"


def lista_dda(filtro="todos", hoje=None, busca="", de=None, ate=None, empresa_id=None, pagamento=""):
    """Boletos do DDA com a situação. Empresa, período de vencimento, busca e pagamento (a pagar / pago) valem
    também para os totais do topo; `filtro` (faltando, lançados, conferir) só escolhe as linhas."""
    hoje = hoje or date.today()
    q = BoletoDDA.query
    if empresa_id:
        q = q.filter(BoletoDDA.empresa_id == empresa_id)
    if de:
        q = q.filter(BoletoDDA.vencimento >= de)
    if ate:
        q = q.filter(BoletoDDA.vencimento <= ate)
    bs = q.order_by(BoletoDDA.vencimento, BoletoDDA.valor.desc()).all()
    chaves = {(b.titulo_empresa_id, b.titulo_chave) for b in bs if b.titulo_chave}
    titulos = {}
    if chaves:
        for t in TituloFinanceiro.query.filter(TituloFinanceiro.tipo == "pagar",
                                               TituloFinanceiro.chave.in_([c for _, c in chaves])).all():
            titulos[(t.empresa_id, t.chave)] = t
    linhas = []
    for b in bs:
        t = titulos.get((b.titulo_empresa_id, b.titulo_chave)) if b.titulo_chave else None
        if b.ignorado:
            st = "Ignorado"
        elif t:
            st = "Lançado" if t.aberto else "Lançado e pago"
        elif (b.conferir or 0) > 1:
            st = "Conferir"
        else:
            st = "Falta lançar"
        linhas.append({"b": b, "t": t, "status": st, "vencido": b.vencimento < hoje})
    if busca and busca.strip():
        linhas = [x for x in linhas if _bate_busca(busca, x["b"].beneficiario, x["b"].documento, x["b"].linha,
                                                     x["b"].cnpj, _valor_txt(x["b"].valor),
                                                     x["t"].nome if x["t"] else "", x["t"].documento if x["t"] else "")]
    if pagamento == "pago":
        linhas = [x for x in linhas if x["status"] == "Lançado e pago"]
    elif pagamento == "aberto":
        linhas = [x for x in linhas if x["status"] not in ("Lançado e pago", "Ignorado")]
    cont = defaultdict(lambda: [0, 0.0])
    for x in linhas:
        cont[x["status"]][0] += 1
        cont[x["status"]][1] += x["b"].valor or 0
    if filtro == "faltando":
        linhas = [x for x in linhas if x["status"] == "Falta lançar"]
    elif filtro == "lancados":
        linhas = [x for x in linhas if x["status"].startswith("Lançado")]
    elif filtro == "conferir":
        linhas = [x for x in linhas if x["status"] == "Conferir"]
    return {"linhas": linhas, "busca": busca or "", "de": de, "ate": ate, "empresa_id": empresa_id,
            "pagamento": pagamento or "", "cont": {k: (v[0], round(v[1], 2)) for k, v in cont.items()},
            "filtro": filtro}


def buscar_titulos_pagar(busca, empresa_id=None, limite=60, de=None, ate=None, so_abertos=False):
    """Contas a pagar por nº da nota / documento, fornecedor, valor ou OC (e/ou período de vencimento)."""
    q = TituloFinanceiro.query.filter(TituloFinanceiro.tipo == "pagar")
    if empresa_id:
        q = q.filter(TituloFinanceiro.empresa_id == empresa_id)
    if de:
        q = q.filter(TituloFinanceiro.vencimento >= de)
    if ate:
        q = q.filter(TituloFinanceiro.vencimento <= ate)
    palavras = norm(busca).split()
    if not palavras:
        if not (de or ate):
            return []
        lst = q.order_by(TituloFinanceiro.vencimento, TituloFinanceiro.nome).limit(400).all()
        return [t for t in lst if t.aberto or not so_abertos][:limite * 3]
    # pré-filtro no banco pela palavra mais longa (nome, documento, descrição ou OC)
    p0 = max(palavras, key=len)
    num = re.sub(r"\D", "", p0)
    conds = [TituloFinanceiro.nome.ilike(f"%{p0}%"), TituloFinanceiro.documento.ilike(f"%{p0}%"),
             TituloFinanceiro.descricao.ilike(f"%{p0}%"), TituloFinanceiro.ordem_compra.ilike(f"%{p0}%")]
    if num and num.lstrip("0"):
        conds += [TituloFinanceiro.documento.ilike(f"%{num.lstrip('0')}%")]
    v = None
    txt = busca.replace("R$", "").strip()
    if re.fullmatch(r"[\d.]*,\d{1,2}|\d+\.\d{1,2}", txt):   # parece valor: 265,20 / 1.446,00 / 265.20
        v = float(txt.replace(".", "").replace(",", ".")) if "," in txt else float(txt)
        conds.append(db.and_(TituloFinanceiro.valor >= v - 0.05, TituloFinanceiro.valor <= v + 0.05))
    achados = q.filter(db.or_(*conds)).order_by(TituloFinanceiro.vencimento.desc()).limit(500).all()
    achados = [t for t in achados if ((v is not None and abs((t.valor or 0) - v) <= 0.05)
               or _bate_busca(busca, t.nome, t.documento, t.descricao, t.ordem_compra, t.centro_custo))
               and (t.aberto or not so_abertos)]
    return achados[:limite]


def diagnostico_dda(boleto):
    """Por que o boleto não ligou sozinho: contas a pagar com o MESMO VALOR (qualquer empresa, ±90 dias) e o motivo."""
    if not boleto.valor:
        return []
    q = TituloFinanceiro.query.filter(TituloFinanceiro.tipo == "pagar",
                                      TituloFinanceiro.valor >= boleto.valor - max(0.05, boleto.valor * 0.001),
                                      TituloFinanceiro.valor <= boleto.valor + max(0.05, boleto.valor * 0.001),
                                      TituloFinanceiro.vencimento >= boleto.vencimento - timedelta(days=90),
                                      TituloFinanceiro.vencimento <= boleto.vencimento + timedelta(days=90))
    usados = {(b.titulo_empresa_id, b.titulo_chave) for b in BoletoDDA.query.filter(BoletoDDA.id != boleto.id)
              if b.titulo_chave}
    saida = []
    for t in q.order_by(TituloFinanceiro.vencimento).limit(30).all():
        dias = abs((t.vencimento - boleto.vencimento).days)
        sim = _parecido(boleto.beneficiario, t.nome)
        doc = _mesmo_doc(boleto.documento, t.documento)
        motivos = []
        if boleto.empresa_id and t.empresa_id != boleto.empresa_id:
            motivos.append("outra empresa")
        if (t.empresa_id, t.chave) in usados:
            motivos.append("já ligada a outro boleto")
        if not t.aberto:
            motivos.append("já paga")
        if dias > 5 and not doc and not (t.aberto and sim >= 0.7 and dias <= 15):
            motivos.append(f"vencimento {dias} dia(s) diferente")
        if sim < 0.5:
            motivos.append("fornecedor com nome diferente")
        saida.append({"t": t, "dias": dias, "sim": round(sim * 100), "doc": doc,
                      "motivo": ", ".join(motivos) or "pode ser esta — clique em É este"})
    return saida


def candidatos_dda(boleto, limite=15, incluir_pagos=False):
    """Contas a pagar parecidas para vincular um boleto à mão (só as em aberto, a não ser que peça as pagas)."""
    q = TituloFinanceiro.query.filter(TituloFinanceiro.tipo == "pagar",
                                      TituloFinanceiro.vencimento >= boleto.vencimento - timedelta(days=60),
                                      TituloFinanceiro.vencimento <= boleto.vencimento + timedelta(days=60))
    if not incluir_pagos:
        q = q.filter(TituloFinanceiro.aberto.is_(True))
    if boleto.empresa_id:
        q = q.filter(TituloFinanceiro.empresa_id == boleto.empresa_id)
    cs = []
    for t in q.all():
        dv = abs((t.valor or 0) - boleto.valor) / boleto.valor if boleto.valor else 1
        if dv > 0.2:
            continue
        sim = _parecido(boleto.beneficiario, t.nome)
        cs.append((sim * 2 + (1 - dv * 5) + (1 - abs((t.vencimento - boleto.vencimento).days) / 60), t))
    cs.sort(key=lambda x: -x[0])
    return [t for _, t in cs[:limite]]


# ---------------------------------------------------------------- ponto de equilíbrio

PE_GRUPOS_PADRAO = {"Materiais": "variavel", "Equipamentos": "variavel", "Terreno": "variavel",
                    "Impostos": "variavel", "Mão de obra": "obra", "Administrativo e outros": "fixo",
                    "Despesas financeiras": "fixo", "Sem classificação": "fixo"}
PE_OPCOES = {"variavel": "Custo variável", "fixo": "Custo fixo", "obra": "Variável se for de obra; fixo se administrativo",
             "fora": "Não entra"}
_ADMIN_CC = ("ADMIN", "ESCRITORIO", "SEDE", "EMPRESA", "DIRETORIA", "GERAL", "MATRIZ")


def pe_regra(grupo):
    return Configuracao.obter("pe_grupo:" + norm(grupo)) or PE_GRUPOS_PADRAO.get(grupo, "fixo")


def _de_obra(t):
    cc = norm(t.centro_custo)
    if t.obra_ext:
        return True
    return bool(cc) and not any(x in cc for x in _ADMIN_CC)


def ponto_equilibrio(empresa_id=None, ini=None, fim=None, hoje=None):
    """Ponto de equilíbrio contábil por competência: custos fixos ÷ margem de contribuição (%).
    Receita = contas a receber faturado (sem empréstimos, aportes, transferências). Custos = contas a pagar
    lançado, separado em variável x fixo pelo grupo de gasto (regra ajustável na tela)."""
    hoje = hoje or date.today()
    fim = fim or hoje
    ini = ini or date(*_add_mes(fim.year, fim.month, -11), 1)
    meses = []
    y, m = ini.year, ini.month
    while (y, m) <= (fim.year, fim.month):
        meses.append((y, m))
        y, m = _add_mes(y, m, 1)
    base = {k: {"rec": 0.0, "cv": 0.0, "cf": 0.0} for k in meses}
    grupos = Grupos()
    por_grupo = defaultdict(lambda: {"cv": 0.0, "cf": 0.0, "fora": 0.0})
    regras = {}
    for t in _q(empresa_id).filter(TituloFinanceiro.competencia >= ini, TituloFinanceiro.competencia <= fim).all():
        k = (t.competencia.year, t.competencia.month)
        if k not in base or eh_transferencia(t):
            continue
        v = t.valor or 0
        if t.tipo == "receber":
            if not financeira(t.natureza) and not financeira(t.categoria):
                base[k]["rec"] += v
            continue
        g = grupos.de(t)
        if g is None:
            continue
        if g not in regras:
            regras[g] = pe_regra(g)
        r = regras[g]
        if r == "obra":
            r = "variavel" if _de_obra(t) else "fixo"
        if r == "variavel":
            base[k]["cv"] += v
            por_grupo[g]["cv"] += v
        elif r == "fixo":
            base[k]["cf"] += v
            por_grupo[g]["cf"] += v
        else:
            por_grupo[g]["fora"] += v
    linhas = []
    for k in meses:
        b = base[k]
        mc = b["rec"] - b["cv"]
        mcp = mc / b["rec"] if b["rec"] > 0 else None
        pe = b["cf"] / mcp if mcp and mcp > 0 else None
        linhas.append({"rotulo": rot_mes(*k), "rec": round(b["rec"], 2), "cv": round(b["cv"], 2), "cf": round(b["cf"], 2),
                       "mc": round(mc, 2), "mcp": round(mcp * 100, 1) if mcp is not None else None, "resultado": round(mc - b["cf"], 2),
                       "pe": round(pe, 2) if pe is not None else None})
    n = len(meses) or 1
    rec, cv, cf = (sum(x[c] for x in linhas) for c in ("rec", "cv", "cf"))
    mcp = (rec - cv) / rec if rec > 0 else None
    pe_mes = (cf / n) / mcp if mcp and mcp > 0 else None
    rec_mes = rec / n
    return {"ini": ini, "fim": fim, "meses": linhas, "n": n,
            "tot": {"rec": round(rec, 2), "cv": round(cv, 2), "cf": round(cf, 2), "mc": round(rec - cv, 2),
                    "mcp": round(mcp * 100, 1) if mcp is not None else None, "resultado": round(rec - cv - cf, 2),
                    "rec_mes": round(rec_mes, 2), "cf_mes": round(cf / n, 2),
                    "pe_mes": round(pe_mes, 2) if pe_mes is not None else None,
                    "pe_ano": round(pe_mes * 12, 2) if pe_mes is not None else None,
                    "margem_seg": round((rec_mes - pe_mes) / rec_mes * 100, 1) if pe_mes is not None and rec_mes > 0 else None,
                    "meses_acima": sum(1 for x in linhas if x["pe"] is not None and x["rec"] >= x["pe"])},
            "grupos": sorted(((g, regras.get(g) or pe_regra(g), round(v["cv"], 2), round(v["cf"], 2), round(v["fora"], 2))
                              for g, v in por_grupo.items()), key=lambda x: -(x[2] + x[3] + x[4])),
            "todos_grupos": [g for g in PE_GRUPOS_PADRAO], "opcoes": PE_OPCOES,
            "regras": {g: pe_regra(g) for g in PE_GRUPOS_PADRAO}}
