"""NFS-e (nota fiscal de SERVIÇO) emitidas pela empresa — Prefeitura do Recife.

Webservice da prefeitura (modelo nacional ABRASF 1.00), com o MESMO certificado A1 usado na SEFAZ
(guardado criptografado; senha só no Render, CERT_<EMPRESA>_SENHA):
  https://nfse.recife.pe.gov.br/WSNacional/nfse_v01.asmx — método ConsultarNfse (SOAP 1.1, parâmetro inputXML)
A consulta é por prestador (CNPJ + inscrição municipal) e período de emissão. Só traz as notas EMITIDAS pela
empresa: o modelo 1.00 não tem consulta de notas recebidas (serviços tomados).
"""
import io
import re
import zipfile
from datetime import date, datetime, timedelta
from xml.sax.saxutils import escape

import requests
from lxml import etree

from ..extensions import db
from ..models import Configuracao, Empresa, LogIntegracao, NFSeEmitida, TituloFinanceiro
from . import sefaz as sz

URL = "https://nfse.recife.pe.gov.br/WSNacional/nfse_v01.asmx"
NS_WS = "http://nfse.recife.pe.gov.br/"
NS_ABRASF = "http://www.abrasf.org.br/ABRASF/arquivos/nfse.xsd"
IM_PADRAO = {"27396528000188": "8402728"}   # Ramos Diniz — inscrição municipal no Recife


class ErroNFSe(Exception):
    pass


def inscricao(emp):
    return (Configuracao.obter(f"nfse_im_{emp.id}") or IM_PADRAO.get(emp.cnpj or "") or "").strip() or None


def emite(emp):
    """Empresa que emite nota de serviço no Recife (tem inscrição municipal informada)."""
    return bool(inscricao(emp))


def _dig(v):
    return re.sub(r"\D", "", str(v or ""))


def xml_consulta(cnpj, im, ini, fim, pagina=None):
    pag = f"<Pagina>{pagina}</Pagina>" if pagina else ""
    return (f'<ConsultarNfseEnvio xmlns="{NS_ABRASF}"><Prestador><Cnpj>{_dig(cnpj)}</Cnpj>'
            f"<InscricaoMunicipal>{_dig(im)}</InscricaoMunicipal></Prestador>"
            f"<PeriodoEmissao><DataInicial>{ini.isoformat()}</DataInicial><DataFinal>{fim.isoformat()}</DataFinal>"
            f"</PeriodoEmissao>{pag}</ConsultarNfseEnvio>")


def envelope(dados):
    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body>'
            f'<ConsultarNfseRequest xmlns="{NS_WS}"><inputXML>{escape(dados)}</inputXML></ConsultarNfseRequest>'
            "</soap:Body></soap:Envelope>")


def _post(corpo, cp, kp):
    cab = {"Content-Type": "text/xml; charset=utf-8", "SOAPAction": f'"{NS_WS}ConsultarNfse"'}
    try:
        r = requests.post(URL, data=corpo.encode("utf-8"), headers=cab, cert=(cp, kp), timeout=90)
    except requests.exceptions.SSLError:
        r = requests.post(URL, data=corpo.encode("utf-8"), headers=cab, cert=(cp, kp), timeout=90, verify=False)
    except requests.exceptions.RequestException as e:
        raise ErroNFSe(f"Não consegui falar com o webservice da prefeitura: {str(e)[:150]}")
    if r.status_code >= 400 and not r.text.strip().startswith("<"):
        raise ErroNFSe(f"Webservice da prefeitura respondeu HTTP {r.status_code}.")
    return r.content


def _local(el):
    return etree.QName(el).localname if isinstance(el.tag, str) else ""


def _abrir_resposta(conteudo):
    """A resposta vem num envelope SOAP; o XML da ABRASF pode vir como texto (escapado) dentro de ...Result."""
    raiz = etree.fromstring(conteudo)
    falha = raiz.xpath(".//*[local-name()='Fault']")
    if falha:
        msg = " ".join(t.strip() for t in falha[0].itertext() if t.strip())
        raise ErroNFSe(f"Erro do webservice: {msg[:300]}")
    for el in raiz.iter():
        if _local(el).endswith("Result") or _local(el) in ("outputXML", "return"):
            txt = (el.text or "").strip()
            if txt.startswith("<"):
                return etree.fromstring(txt.encode("utf-8"))
            if len(el):
                return el[0]
    res = raiz.xpath(".//*[local-name()='ConsultarNfseResposta']")
    if res:
        return res[0]
    return raiz


def _t(el, *caminho):
    for nome in caminho:
        if el is None:
            return None
        achou = el.xpath(f".//*[local-name()='{nome}']")
        el = achou[0] if achou else None
    return (el.text or "").strip() if el is not None and el.text else None


def _f(v):
    try:
        return round(float(str(v).replace(",", ".")), 2) if v not in (None, "") else 0.0
    except ValueError:
        return 0.0


def _data(v):
    if not v:
        return None
    v = v.strip()
    for tam, fmt in ((19, "%Y-%m-%dT%H:%M:%S"), (10, "%Y-%m-%d")):
        try:
            return datetime.strptime(v[:tam], fmt)
        except ValueError:
            continue
    return None


def mensagens(resp):
    out = []
    for m in resp.xpath(".//*[local-name()='MensagemRetorno']"):
        cod, txt, cor = _t(m, "Codigo"), _t(m, "Mensagem"), _t(m, "Correcao")
        out.append(" ".join(x for x in [cod and f"[{cod}]", txt, cor and f"({cor})"] if x))
    return out


def ler_notas(resp):
    """Lista de dicionários, um por NFS-e (CompNfse) da resposta."""
    notas = []
    for comp in resp.xpath(".//*[local-name()='CompNfse']"):
        inf = comp.xpath(".//*[local-name()='InfNfse']")
        if not inf:
            continue
        inf = inf[0]
        val = inf.xpath(".//*[local-name()='Servico']/*[local-name()='Valores']")
        val = val[0] if val else inf
        tom = inf.xpath(".//*[local-name()='TomadorServico']")
        tom = tom[0] if tom else None
        canc = comp.xpath(".//*[local-name()='NfseCancelamento']")
        dcanc = _t(canc[0], "DataHora") if canc else None
        comp_txt = _t(inf, "Competencia")
        competencia = _data(comp_txt)
        notas.append({
            "numero": _t(inf, "Numero"),
            "codigo_verificacao": _t(inf, "CodigoVerificacao"),
            "data_emissao": _data(_t(inf, "DataEmissao")),
            "competencia": competencia.date() if competencia else None,
            "rps": _t(inf, "IdentificacaoRps", "Numero"),
            "tomador_nome": (_t(tom, "RazaoSocial") if tom is not None else None) or "—",
            "tomador_doc": _dig((_t(tom, "Cnpj") or _t(tom, "Cpf")) if tom is not None else ""),
            "discriminacao": _t(inf, "Discriminacao"),
            "item_servico": _t(inf, "ItemListaServico"),
            "valor_servicos": _f(_t(val, "ValorServicos")),
            "valor_deducoes": _f(_t(val, "ValorDeducoes")),
            "valor_pis": _f(_t(val, "ValorPis")),
            "valor_cofins": _f(_t(val, "ValorCofins")),
            "valor_inss": _f(_t(val, "ValorInss")),
            "valor_ir": _f(_t(val, "ValorIr")),
            "valor_csll": _f(_t(val, "ValorCsll")),
            "iss_retido": _t(val, "IssRetido") == "1",
            "aliquota": _f(_t(val, "Aliquota")) or None,
            "valor_iss": _f(_t(val, "ValorIss")),
            "valor_liquido": _f(_t(val, "ValorLiquidoNfse")),
            "cancelada": bool(canc),
            "cancelada_em": _data(dcanc) if dcanc else None,
            "xml": etree.tostring(comp, encoding="unicode"),
        })
    return [n for n in notas if n["numero"]]


def gravar(emp, notas):
    novas = 0
    for n in notas:
        reg = NFSeEmitida.query.filter_by(empresa_id=emp.id, numero=n["numero"]).first()
        if not reg:
            reg = NFSeEmitida(empresa_id=emp.id, numero=n["numero"])
            db.session.add(reg)
            novas += 1
        for k, v in n.items():
            if k != "numero":
                setattr(reg, k, v)
        if not reg.valor_liquido:
            reg.valor_liquido = round((reg.valor_servicos or 0) - reg.retencoes, 2)
    db.session.flush()
    return novas


def _meses(ini, fim):
    """Quebra o período em meses (a prefeitura limita o tamanho da resposta)."""
    a = ini
    while a <= fim:
        prox = (a.replace(day=1) + timedelta(days=32)).replace(day=1)
        yield a, min(fim, prox - timedelta(days=1))
        a = prox


def consultar(emp, ini, fim, max_paginas=20):
    """Busca as NFS-e emitidas no período. Devolve (total lido, novas, avisos)."""
    im = inscricao(emp)
    if not im:
        raise ErroNFSe(f"{emp.nome}: informe a inscrição municipal (Notas de serviço → configurar).")
    lidas = novas = 0
    avisos = []
    with sz._pem(emp) as (cp, kp, _chave, _cert):
        for a, b in _meses(ini, fim):
            vistos = set()
            for pagina in range(1, max_paginas + 1):
                resp = _abrir_resposta(_post(envelope(xml_consulta(emp.cnpj, im, a, b, pagina if pagina > 1 else None)), cp, kp))
                notas = ler_notas(resp)
                msgs = mensagens(resp)
                if not notas:
                    # "nenhuma NFS-e encontrada" não é erro
                    for m in msgs:
                        if not re.search(r"E\d*:?\s*N[aã]o (existe|foi encontrad)|nenhum|n[aã]o encontrad", m, re.I) \
                                and not m.startswith("[E180]"):
                            avisos.append(f"{a:%m/%Y}: {m}")
                    break
                nums = {n["numero"] for n in notas}
                if nums <= vistos:          # o servidor não pagina: devolveu as mesmas
                    break
                vistos |= nums
                lidas += len(notas)
                novas += gravar(emp, notas)
                if len(notas) < 50:
                    break
    db.session.commit()
    return lidas, novas, avisos


def buscar(emp, ini, fim, usuario=None):
    try:
        lidas, novas, avisos = consultar(emp, ini, fim)
        msg = f"{lidas} nota(s) lida(s), {novas} nova(s) ({ini:%d/%m/%Y} a {fim:%d/%m/%Y})."
        if avisos:
            msg += " Prefeitura: " + " | ".join(avisos[:3])
        db.session.add(LogIntegracao(sistema="nfse", operacao=f"NFS-e emitidas — {emp.nome}", sucesso=True,
                                     mensagem=msg[:500], usuario=usuario))
        Configuracao.definir(f"nfse_{emp.id}_ultima", datetime.utcnow().isoformat())
        db.session.commit()
        return True, msg
    except (ErroNFSe, sz.ErroSefaz) as e:
        db.session.rollback()
        db.session.add(LogIntegracao(sistema="nfse", operacao=f"NFS-e emitidas — {emp.nome}", sucesso=False,
                                     mensagem=str(e)[:500], usuario=usuario))
        db.session.commit()
        return False, str(e)
    except Exception as e:  # noqa: BLE001 — resposta inesperada
        db.session.rollback()
        return False, f"{emp.nome}: resposta inesperada da prefeitura ({type(e).__name__}: {str(e)[:150]})."


# ---------------------------------------------------------------- lista, conferência e exportação

def filtrar(empresa_id=None, ini=None, fim=None, q=None, situacao=None):
    qy = NFSeEmitida.query
    if empresa_id:
        qy = qy.filter(NFSeEmitida.empresa_id == empresa_id)
    if ini:
        qy = qy.filter(NFSeEmitida.data_emissao >= datetime.combine(ini, datetime.min.time()))
    if fim:
        qy = qy.filter(NFSeEmitida.data_emissao < datetime.combine(fim + timedelta(days=1), datetime.min.time()))
    if situacao == "canceladas":
        qy = qy.filter(NFSeEmitida.cancelada.is_(True))
    elif situacao == "validas":
        qy = qy.filter(NFSeEmitida.cancelada.is_(False))
    notas = qy.order_by(NFSeEmitida.data_emissao.desc(), NFSeEmitida.id.desc()).all()
    if q:
        from .fin_bi import norm
        alvo = norm(q)
        notas = [n for n in notas if alvo in norm(f"{n.numero} {n.tomador_nome} {n.tomador_doc} {n.discriminacao} {n.obra}")]
    return notas


def totais(notas):
    v = [n for n in notas if not n.cancelada]
    return {"qtd": len(v), "canceladas": len(notas) - len(v),
            "servicos": round(sum(n.valor_servicos or 0 for n in v), 2),
            "iss": round(sum(n.valor_iss or 0 for n in v), 2),
            "iss_retido": round(sum(n.valor_iss or 0 for n in v if n.iss_retido), 2),
            "retencoes": round(sum(n.retencoes for n in v), 2),
            "liquido": round(sum(n.valor_liquido or 0 for n in v), 2)}


def conferir_recebimentos(notas):
    """Para cada nota: parcela do contas a receber (Mais Controle/Omie) com o mesmo cliente e valor."""
    from .fin_bi import _parecido
    if not notas:
        return {}
    ini = min((n.data_emissao or datetime.now()) for n in notas).date() - timedelta(days=60)
    tits = TituloFinanceiro.query.filter(TituloFinanceiro.tipo == "receber",
                                         TituloFinanceiro.vencimento >= ini).all()
    usados, out = set(), {}
    for n in sorted(notas, key=lambda x: x.data_emissao or datetime.min):
        if n.cancelada:
            continue
        melhor = None
        for t in tits:
            if t.id in usados or t.empresa_id != n.empresa_id:
                continue
            ok_valor = any(abs((t.valor or 0) - v) <= max(1.0, v * 0.005)
                           for v in (n.valor_liquido or 0, n.valor_servicos or 0) if v)
            if not ok_valor or _parecido(t.nome, n.tomador_nome) < 0.5:
                continue
            dias = abs((t.vencimento - (n.data_emissao.date() if n.data_emissao else t.vencimento)).days)
            if dias > 120:
                continue
            if melhor is None or dias < melhor[0]:
                melhor = (dias, t)
        if melhor:
            usados.add(melhor[1].id)
            out[n.id] = melhor[1]
    return out


COLUNAS = [("Empresa", lambda n: n.empresa.nome), ("Nº NFS-e", lambda n: n.numero),
           ("Cód. verificação", lambda n: n.codigo_verificacao), ("Emissão", lambda n: n.data_emissao),
           ("Competência", lambda n: n.competencia), ("RPS", lambda n: n.rps), ("Tomador", lambda n: n.tomador_nome),
           ("CNPJ/CPF tomador", lambda n: n.tomador_doc), ("Obra", lambda n: n.obra),
           ("Item serviço", lambda n: n.item_servico), ("Discriminação", lambda n: n.discriminacao),
           ("Valor serviços", lambda n: n.valor_servicos), ("Deduções", lambda n: n.valor_deducoes),
           ("PIS", lambda n: n.valor_pis), ("COFINS", lambda n: n.valor_cofins), ("INSS", lambda n: n.valor_inss),
           ("IR", lambda n: n.valor_ir), ("CSLL", lambda n: n.valor_csll), ("Alíquota ISS", lambda n: n.aliquota),
           ("ISS", lambda n: n.valor_iss), ("ISS retido", lambda n: "Sim" if n.iss_retido else "Não"),
           ("Valor líquido", lambda n: n.valor_liquido),
           ("Situação", lambda n: "Cancelada" if n.cancelada else "Normal")]


def excel(notas, recebidos=None):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    ws = wb.active
    ws.title = "NFS-e emitidas"
    cab = [c for c, _ in COLUNAS] + (["Recebimento (contas a receber)"] if recebidos is not None else [])
    ws.append(cab)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1E3A5F")
    for n in notas:
        linha = [f(n) for _, f in COLUNAS]
        if recebidos is not None:
            t = recebidos.get(n.id)
            linha.append("" if n.cancelada else (
                f"{t.nome} · venc. {t.vencimento:%d/%m/%Y} · " + ("recebido" if not t.aberto else "em aberto")
                if t else "não encontrado"))
        ws.append(linha)
    moeda = {i + 1 for i, (c, _) in enumerate(COLUNAS) if c in (
        "Valor serviços", "Deduções", "PIS", "COFINS", "INSS", "IR", "CSLL", "ISS", "Valor líquido")}
    for row in ws.iter_rows(min_row=2):
        for c in row:
            if c.column in moeda:
                c.number_format = '#,##0.00'
            elif isinstance(c.value, datetime):
                c.number_format = "dd/mm/yyyy hh:mm"
            elif isinstance(c.value, date):
                c.number_format = "dd/mm/yyyy"
    larg = {"Discriminação": 60, "Tomador": 38, "Empresa": 16, "Recebimento (contas a receber)": 45}
    for i, c in enumerate(cab, 1):
        ws.column_dimensions[get_column_letter(i)].width = larg.get(c, 15)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    t = totais(notas)
    ws2 = wb.create_sheet("Resumo")
    for k, rot in [("qtd", "Notas válidas"), ("canceladas", "Canceladas"), ("servicos", "Valor dos serviços"),
                   ("iss", "ISS"), ("iss_retido", "ISS retido pelo tomador"), ("retencoes", "Total de retenções"),
                   ("liquido", "Valor líquido")]:
        ws2.append([rot, t[k]])
    ws2.column_dimensions["A"].width = 28
    ws2.column_dimensions["B"].width = 18
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def zip_xml(notas):
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as z:
        for n in notas:
            if n.xml:
                z.writestr(f"NFSe_{_dig(n.empresa.cnpj)}_{n.numero}.xml",
                           '<?xml version="1.0" encoding="utf-8"?>\n' + n.xml)
    return bio.getvalue()


def status(emp):
    ult = Configuracao.obter(f"nfse_{emp.id}_ultima")
    return {"emp": emp, "im": inscricao(emp), "cert": sz.pronto(emp), "var": sz.var_senha(emp),
            "ultima": datetime.fromisoformat(ult) if ult else None,
            "qtd": NFSeEmitida.query.filter_by(empresa_id=emp.id).count()}


def empresas_emissoras():
    return [e for e in Empresa.query.order_by(Empresa.id).all() if emite(e)]



# ================================================================ NFS-e RECEBIDAS (serviços contratados)
# Ambiente de Dados Nacional (ADN) da NFS-e: distribui, por NSU, as notas em que a empresa é emitente, tomadora
# ou intermediária, de qualquer município que usa o padrão nacional (o Recife emite pelo Emissor Nacional desde
# 01/2026). Acesso com o certificado A1 da empresa (mesmo da SEFAZ).
ADN = "https://adn.nfse.gov.br/contribuintes"
ADN_DANFSE = "https://adn.nfse.gov.br/danfse/"


def _get_adn(url, cp, kp, params=None):
    try:
        r = requests.get(url, params=params, cert=(cp, kp), timeout=90, headers={"Accept": "application/json"})
    except requests.exceptions.SSLError:
        r = requests.get(url, params=params, cert=(cp, kp), timeout=90, verify=False,
                         headers={"Accept": "application/json"})
    except requests.exceptions.RequestException as e:
        raise ErroNFSe(f"Não consegui falar com o Ambiente Nacional da NFS-e: {str(e)[:150]}")
    return r


def _desempacotar(b64):
    import base64
    import gzip
    raw = base64.b64decode(b64)
    try:
        raw = gzip.decompress(raw)
    except OSError:
        pass
    return raw.decode("utf-8", errors="replace")


def _campo(d, *nomes):
    for n in nomes:
        for k, v in (d or {}).items():
            if k.lower() == n.lower():
                return v
    return None


def ler_nfse_nacional(xml_txt):
    """Campos da NFS-e no leiaute nacional (NFSe/infNFSe, com a DPS dentro)."""
    raiz = etree.fromstring(xml_txt.encode("utf-8"))

    def t(*cam, base=raiz):
        el = base
        for nome in cam:
            r = el.xpath(f".//*[local-name()='{nome}']")
            if not r:
                return None
            el = r[0]
        return (el.text or "").strip() or None

    emit = raiz.xpath(".//*[local-name()='infNFSe']/*[local-name()='emit']")
    emit = emit[0] if emit else raiz
    toma = raiz.xpath(".//*[local-name()='toma']")
    toma = toma[0] if toma else None
    inter = raiz.xpath(".//*[local-name()='interm']")
    inter = inter[0] if inter else None
    tp_ret = t("tribMun", "tpRetISSQN")
    vserv = _f(t("vServPrest", "vServ") or t("vServ"))
    vliq = _f(t("infNFSe", "valores", "vLiq") or t("vLiq"))
    ret = _f(t("infNFSe", "valores", "vTotalRet") or t("vTotalRet"))
    dh = _data(t("DPS", "dhEmi") or t("dhEmi") or t("dhProc"))
    comp = _data(t("dCompet"))
    return {
        "numero": t("nNFSe"),
        "data_emissao": dh,
        "competencia": comp.date() if comp else None,
        "emit_doc": _dig(t("CNPJ", base=emit) or t("CPF", base=emit)),
        "prestador_nome": t("xNome", base=emit) or "—",
        "toma_nome": (t("xNome", base=toma) if toma is not None else None) or "—",
        "dps": t("nDPS"),
        "item": t("cTribNac"),
        "toma_doc": _dig((t("CNPJ", base=toma) or t("CPF", base=toma)) if toma is not None else ""),
        "interm_doc": _dig((t("CNPJ", base=inter) or t("CPF", base=inter)) if inter is not None else ""),
        "municipio": t("xLocPrestacao") or t("xLocEmi"),
        "servico": (t("xTribNac") or t("xTribMun") or "")[:255] or None,
        "discriminacao": t("xDescServ"),
        "valor_servicos": vserv,
        "valor_iss": _f(t("infNFSe", "valores", "vISSQN") or t("vISSQN")),
        "iss_retido": tp_ret in ("2", "3"),
        "valor_retencoes": ret,
        "valor_liquido": vliq or round(vserv - ret, 2),
    }


def _cancelamento(xml_txt):
    return bool(re.search(r"<(?:\w+:)?e101101|tpEvento>\s*101101|e105102|Cancelamento", xml_txt or "", re.I))


def distribuir(emp, max_lotes=40):
    """Busca no ADN as NFS-e novas desde o último NSU. Guarda as que a empresa é tomadora/intermediária.
    Devolve (recebidas novas, eventos de cancelamento, último NSU)."""
    from ..models import NFSeRecebida
    ult = int(Configuracao.obter(f"nfse_adn_{emp.id}_nsu") or 0)
    if not Configuracao.obter(f"nfse_adn_{emp.id}_emit_v145"):
        ult = 0   # v1.45.1: relê desde o início uma vez para guardar o XML nacional das notas EMITIDAS
    cnpj = _dig(emp.cnpj)
    novas = cancel = 0
    with sz._pem(emp) as (cp, kp, _c, _k):
        for _ in range(max_lotes):
            r = _get_adn(f"{ADN}/DFe/{ult}", cp, kp, {"cnpjConsulta": cnpj, "lote": "true"})
            if r.status_code in (401, 403):
                raise ErroNFSe(f"{emp.nome}: o Ambiente Nacional recusou o certificado (HTTP {r.status_code}).")
            try:
                d = r.json()
            except ValueError:
                if r.status_code == 404:
                    break
                raise ErroNFSe(f"{emp.nome}: resposta inesperada do Ambiente Nacional (HTTP {r.status_code}).")
            status_ = str(_campo(d, "StatusProcessamento") or "").upper()
            lote = _campo(d, "LoteDFe") or []
            if status_ == "REJEICAO":
                erros = _campo(d, "Erros") or []
                txt = "; ".join(str(_campo(e, "Descricao") or _campo(e, "Mensagem") or e) for e in erros) or "rejeição"
                raise ErroNFSe(f"{emp.nome}: Ambiente Nacional — {txt[:250]}")
            if not lote or status_ == "NENHUM_DOCUMENTO_LOCALIZADO":
                break
            maior = ult
            for doc in lote:
                nsu = int(_campo(doc, "NSU") or 0)
                maior = max(maior, nsu)
                b64 = _campo(doc, "ArquivoXml")
                if not b64:
                    continue
                xml_txt = _desempacotar(b64)
                tipo = str(_campo(doc, "TipoDocumento") or "").upper()
                chave = str(_campo(doc, "ChaveAcesso") or "")[:60]
                if tipo.startswith("EVENTO") or (tipo != "NFSE" and _cancelamento(xml_txt)):
                    if _cancelamento(xml_txt) and chave:
                        n = NFSeRecebida.query.filter_by(chave=chave).first() or \
                            NFSeEmitida.query.filter_by(chave=chave).first()
                        if n and not n.cancelada:
                            n.cancelada = True
                            cancel += 1
                    continue
                try:
                    info = ler_nfse_nacional(xml_txt)
                except etree.XMLSyntaxError:
                    continue
                if info["emit_doc"] == cnpj:
                    # emitida pela própria empresa (Emissor Nacional): guarda o XML nacional na aba Emitidas
                    if not chave:
                        m = re.search(r'Id="NFS(\d{50})"', xml_txt)
                        chave = m.group(1) if m else None
                    _gravar_emitida_nacional(emp, info, chave, xml_txt)
                    continue
                if cnpj not in (info["toma_doc"], info["interm_doc"]):
                    continue
                if not chave:
                    m = re.search(r'Id="NFS(\d{50})"', xml_txt)
                    chave = m.group(1) if m else f"{info['emit_doc']}-{info['numero']}"
                reg = NFSeRecebida.query.filter_by(chave=chave).first()
                if not reg:
                    reg = NFSeRecebida(empresa_id=emp.id, chave=chave)
                    db.session.add(reg)
                    novas += 1
                reg.nsu, reg.xml = nsu, xml_txt
                reg.prestador_doc = info["emit_doc"]
                for k in ("numero", "data_emissao", "competencia", "prestador_nome", "municipio", "servico",
                          "discriminacao", "valor_servicos", "valor_iss", "iss_retido", "valor_retencoes",
                          "valor_liquido"):
                    setattr(reg, k, info[k])
            db.session.flush()
            if maior <= ult:
                break
            ult = maior
            Configuracao.definir(f"nfse_adn_{emp.id}_nsu", str(ult))
            db.session.commit()
            if len(lote) < 50:
                break
    Configuracao.definir(f"nfse_adn_{emp.id}_ultima", datetime.utcnow().isoformat())
    Configuracao.definir(f"nfse_adn_{emp.id}_emit_v145", "1")
    db.session.commit()
    return novas, cancel, ult


def _gravar_emitida_nacional(emp, info, chave, xml_txt):
    """NFS-e emitida pelo Emissor Nacional: completa (ou cria) a nota da aba Emitidas com o XML nacional."""
    numero = (info.get("numero") or "").lstrip("0") or info.get("numero")
    if not numero:
        return None
    reg = (NFSeEmitida.query.filter_by(empresa_id=emp.id, chave=chave).first() if chave else None) or \
        NFSeEmitida.query.filter(NFSeEmitida.empresa_id == emp.id,
                                 db.func.ltrim(NFSeEmitida.numero, "0") == numero).first()
    if not reg:
        reg = NFSeEmitida(empresa_id=emp.id, numero=numero)
        db.session.add(reg)
    reg.chave, reg.xml_nacional = chave, xml_txt
    # dados que a prefeitura não traz mais (desde o Emissor Nacional) vêm do XML nacional
    if not reg.data_emissao:
        reg.data_emissao = info.get("data_emissao")
    if not reg.competencia:
        reg.competencia = info.get("competencia")
    if not reg.tomador_nome or reg.tomador_nome == "—":
        reg.tomador_nome = info.get("toma_nome")
    if not reg.tomador_doc:
        reg.tomador_doc = info.get("toma_doc")
    if not reg.discriminacao:
        reg.discriminacao = info.get("discriminacao")
    if not reg.valor_servicos:
        reg.valor_servicos = info.get("valor_servicos") or 0
    if not reg.valor_iss:
        reg.valor_iss = info.get("valor_iss") or 0
    if not reg.valor_liquido:
        reg.valor_liquido = info.get("valor_liquido") or 0
    if reg.iss_retido is None or (info.get("iss_retido") and not reg.iss_retido):
        reg.iss_retido = bool(info.get("iss_retido"))
    if not reg.rps:
        reg.rps = info.get("dps")
    if not reg.item_servico:
        reg.item_servico = info.get("item")
    if reg.codigo_verificacao and reg.codigo_verificacao.startswith("ADN") and chave:
        reg.codigo_verificacao = None   # a prefeitura só manda "ADN -": a nota vale pela chave de acesso nacional
    if reg.item_servico:
        reg.item_servico = reg.item_servico[:10]
    return reg


def buscar_recebidas(emp, usuario=None):
    try:
        novas, cancel, ult = distribuir(emp)
        msg = f"{novas} nota(s) recebida(s) nova(s), {cancel} cancelamento(s)."
        db.session.add(LogIntegracao(sistema="nfse", operacao=f"NFS-e recebidas — {emp.nome}", sucesso=True,
                                     mensagem=msg + f" NSU {ult}.", usuario=usuario))
        db.session.commit()
        return True, msg
    except (ErroNFSe, sz.ErroSefaz) as e:
        db.session.rollback()
        db.session.add(LogIntegracao(sistema="nfse", operacao=f"NFS-e recebidas — {emp.nome}", sucesso=False,
                                     mensagem=str(e)[:500], usuario=usuario))
        db.session.commit()
        return False, str(e)
    except Exception as e:  # noqa: BLE001
        db.session.rollback()
        return False, f"{emp.nome}: resposta inesperada do Ambiente Nacional ({type(e).__name__}: {str(e)[:150]})."


def danfse_local(xml_txt, cancelada=False):
    """DANFSe (PDF) no padrão nacional (NT 008/2026), montado aqui a partir do XML nacional (brazilfiscalreport)."""
    from brazilfiscalreport.danfse import Danfse
    from brazilfiscalreport.danfse.config import DanfseConfig
    x = xml_txt or ""
    if x.lstrip().startswith("<?xml"):
        x = x[x.index("?>") + 2:]
    return bytes(Danfse(xml=x.strip(), config=DanfseConfig(watermark_cancelled=bool(cancelada))).output())


def danfse(n):
    """PDF da NFS-e: gerado aqui pelo XML (sempre que o XML for do padrão nacional); se não der, pede ao ADN."""
    if n.xml and "sped.fazenda.gov.br/nfse" in n.xml:
        try:
            return danfse_local(n.xml, getattr(n, "cancelada", False))
        except Exception:  # noqa: BLE001 — XML fora do esperado pela biblioteca: tenta o ADN
            pass
    if not re.fullmatch(r"\d{50}", n.chave or ""):
        return None
    try:
        with sz._pem(n.empresa) as (cp, kp, _c, _k):
            try:
                r = requests.get(ADN_DANFSE + n.chave, cert=(cp, kp), timeout=90, headers={"Accept": "*/*"})
            except requests.exceptions.SSLError:
                r = requests.get(ADN_DANFSE + n.chave, cert=(cp, kp), timeout=90, headers={"Accept": "*/*"},
                                 verify=False)
        if r.status_code == 200 and r.content[:4] == b"%PDF":
            return r.content
    except (requests.exceptions.RequestException, sz.ErroSefaz):
        return None
    return None


def filtrar_recebidas(empresa_id=None, ini=None, fim=None, q=None, situacao=None):
    from ..models import NFSeRecebida
    qy = NFSeRecebida.query
    if empresa_id:
        qy = qy.filter(NFSeRecebida.empresa_id == empresa_id)
    if ini:
        qy = qy.filter(NFSeRecebida.data_emissao >= datetime.combine(ini, datetime.min.time()))
    if fim:
        qy = qy.filter(NFSeRecebida.data_emissao < datetime.combine(fim + timedelta(days=1), datetime.min.time()))
    if situacao == "canceladas":
        qy = qy.filter(NFSeRecebida.cancelada.is_(True))
    elif situacao in ("validas", "lancar", "lancadas"):
        qy = qy.filter(NFSeRecebida.cancelada.is_(False))
    notas = qy.order_by(NFSeRecebida.data_emissao.desc(), NFSeRecebida.id.desc()).all()
    if q:
        from .fin_bi import norm
        alvo = norm(q)
        notas = [n for n in notas if alvo in norm(f"{n.numero} {n.prestador_nome} {n.prestador_doc} {n.discriminacao} {n.obra} {n.chave}")]
    return notas


def _numeros_nota(numero):
    """Formas do nº da NFS-e que podem aparecer no lançamento: 2600000000652 (nacional: ano + nº) -> 652."""
    d = _dig(numero)
    out = set()
    if d:
        out.add(d.lstrip("0") or "0")
        if len(d) >= 12 and d[:2].isdigit():
            out.add(d[2:].lstrip("0") or "0")
    return out


def _cnpj_dos_titulos(empresa_ids):
    """(empresa, chave do título) -> CNPJ do fornecedor, pelas tabelas originais (Omie: cadastro do fornecedor;
    Mais Controle: qualquer coluna de CNPJ/CPF do lançamento)."""
    from ..models import DadoImportado, Empresa
    out = {}
    for emp in Empresa.query.filter(Empresa.id.in_(list(empresa_ids) or [0])):
        if emp.sistema == "omie":
            cnpj_cli = {}
            for (d,) in db.session.query(DadoImportado.dados).filter_by(empresa_id=emp.id, tabela="fornecedores_clientes"):
                d = d or {}
                cod = d.get("codigo_cliente") or d.get("codigo_cliente_omie")
                if cod and d.get("cnpj_cpf"):
                    cnpj_cli[str(cod)] = _dig(d["cnpj_cpf"])
            for (d,) in db.session.query(DadoImportado.dados).filter_by(empresa_id=emp.id, tabela="contas_pagar"):
                d = d or {}
                ch = str(d.get("codigo_lancamento_omie") or d.get("codigo_lancamento_integracao") or "")
                c = _dig(d.get("cnpj_cpf")) or cnpj_cli.get(str(d.get("codigo_cliente_fornecedor") or ""))
                if ch and c:
                    out[(emp.id, ch[:80])] = c
        else:
            for (d,) in db.session.query(DadoImportado.dados).filter_by(empresa_id=emp.id, tabela="lancamentos"):
                d = d or {}
                c = next((_dig(v) for k, v in d.items() if v and ("cnpj" in k.lower() or "cpf" in k.lower())
                          and len(_dig(v)) in (11, 14)), None)
                if c and d.get("id_lancamento"):
                    out[(emp.id, "id:" + str(d["id_lancamento"]))] = c
    return out


def _cnpj_titulo(mapa, t):
    return mapa.get((t.empresa_id, t.chave)) or mapa.get((t.empresa_id, "id:" + str(t.chave).split("/")[0]))


def _valor_bate(v, n, tol=0.01):
    return any(x and abs((v or 0) - x) <= max(0.05, x * tol) for x in (n.valor_liquido, n.valor_servicos))


def _titulos_janela(notas):
    if not notas:
        return []
    datas = [n.data_emissao.date() for n in notas if n.data_emissao] or [date.today()]
    ini, fim = min(datas) - timedelta(days=90), max(datas) + timedelta(days=180)
    return TituloFinanceiro.query.filter(
        TituloFinanceiro.tipo == "pagar", TituloFinanceiro.empresa_id.in_({n.empresa_id for n in notas}),
        db.or_(TituloFinanceiro.vencimento.between(ini, fim), TituloFinanceiro.competencia.between(ini, fim))).all()


def _no_prazo(t, n, antes=90, depois=180):
    ref = n.data_emissao.date() if n.data_emissao else None
    d = t.competencia or t.vencimento
    if not ref or not d:
        return True
    return -antes <= (d - ref).days <= depois or (t.vencimento and -antes <= (t.vencimento - ref).days <= depois)


def _brl(v):
    return f"{v or 0:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _texto_titulo(t):
    sist = "Omie" if t.origem == "omie" else "Mais Controle"
    return (f"{sist} · {t.nome}" + (f" · doc. {t.documento}" if t.documento else "")
            + f" · venc. {t.vencimento.strftime('%d/%m/%Y') if t.vencimento else '—'} · R$ {_brl(t.valor)}")


def _avaliar(n, t, cnpjs):
    """(pontos, motivo) — quanto o título parece ser o lançamento da nota."""
    from .fin_bi import _parecido
    c = _cnpj_titulo(cnpjs, t)
    mesmo_cnpj = bool(c and n.prestador_doc and c == n.prestador_doc)
    nome = max(_parecido(t.nome, n.prestador_nome), 0.7 if (sz._palavras(t.nome) & sz._palavras(n.prestador_nome)) else 0)
    nums = _numeros_nota(n.numero)
    tem_num = bool(nums & sz._numeros(t.documento, t.descricao))
    valor = _valor_bate(t.valor, n)
    pts = (3 if mesmo_cnpj else 0) + (2 * nome) + (2.5 if tem_num else 0) + (2 if valor else 0)
    motivos = [m for m, ok in (("mesmo CNPJ", mesmo_cnpj), ("fornecedor parecido", nome >= 0.6),
                               ("nº da nota no lançamento", tem_num), ("mesmo valor", valor)) if ok]
    casou = (mesmo_cnpj and (valor or tem_num)) or (tem_num and (nome >= 0.6 or valor)) or (nome >= 0.6 and valor)
    return pts, casou, motivos


def lancadas_recebidas(notas):
    """{id: texto} das NFS-e recebidas já lançadas no contas a pagar (Mais Controle / Omie) ou ligadas à mão.
    Casa por: CNPJ do fornecedor + valor (líquido ou bruto) ou nº; nº da nota no documento/descrição + fornecedor
    ou valor; fornecedor parecido + valor; ou várias parcelas do mesmo lançamento somando o valor da nota."""
    from collections import defaultdict
    res = {}
    vivas = [n for n in notas if not n.cancelada]
    for n in vivas:
        manual = Configuracao.obter(f"nfse_rec_lanc_{n.id}")
        if manual:
            res[n.id] = manual if manual.startswith(("Omie", "Mais Controle")) else "Marcada à mão · " + manual
    faltam = [n for n in vivas if n.id not in res]
    if not faltam:
        return res
    tits = _titulos_janela(faltam)
    cnpjs = _cnpj_dos_titulos({n.empresa_id for n in faltam})
    por_emp = defaultdict(list)
    for t in tits:
        por_emp[t.empresa_id].append(t)
    usados = set()
    for n in sorted(faltam, key=lambda x: x.data_emissao or datetime.min):
        melhor = None
        for t in por_emp.get(n.empresa_id, []):
            if t.id in usados or not _no_prazo(t, n):
                continue
            pts, casou, _m = _avaliar(n, t, cnpjs)
            if casou and (melhor is None or pts > melhor[0]):
                melhor = (pts, t)
        if melhor:
            usados.add(melhor[1].id)
            res[n.id] = _texto_titulo(melhor[1])
            continue
        # parcelas: mesmo fornecedor e mesmo documento/competência somando o valor da nota
        grupos = defaultdict(list)
        for t in por_emp.get(n.empresa_id, []):
            if t.id in usados or not _no_prazo(t, n):
                continue
            pts, _c, mot = _avaliar(n, t, cnpjs)
            if "mesmo CNPJ" in mot or "fornecedor parecido" in mot:
                grupos[(t.nome, t.documento, t.competencia)].append(t)
        for ts in grupos.values():
            if len(ts) > 1 and _valor_bate(sum(t.valor or 0 for t in ts), n):
                usados.update(t.id for t in ts)
                res[n.id] = _texto_titulo(ts[0]) + f" ({len(ts)} parcelas)"
                break
    return res


def candidatos(n, limite=12):
    """Lançamentos do contas a pagar que podem ser desta nota (para ligar à mão), com o motivo."""
    tits = _titulos_janela([n])
    cnpjs = _cnpj_dos_titulos({n.empresa_id})
    out = []
    for t in tits:
        if not _no_prazo(t, n, 120, 240):
            continue
        pts, casou, mot = _avaliar(n, t, cnpjs)
        perto = any(x and abs((t.valor or 0) - x) <= x * 0.05 for x in (n.valor_liquido, n.valor_servicos))
        if mot or perto:
            out.append({"t": t, "pts": pts + (0.5 if perto else 0), "motivos": mot or ["valor próximo"],
                        "casou": casou, "cnpj": _cnpj_titulo(cnpjs, t)})
    out.sort(key=lambda x: -x["pts"])
    return out[:limite]


COLUNAS_REC = [("Empresa (tomadora)", lambda n: n.empresa.nome), ("Nº NFS-e", lambda n: n.numero),
               ("Emissão", lambda n: n.data_emissao), ("Competência", lambda n: n.competencia),
               ("Prestador", lambda n: n.prestador_nome), ("CNPJ/CPF prestador", lambda n: n.prestador_doc),
               ("Município", lambda n: n.municipio), ("Obra", lambda n: n.obra), ("Serviço", lambda n: n.servico),
               ("Descrição", lambda n: n.discriminacao), ("Valor serviços", lambda n: n.valor_servicos),
               ("ISS", lambda n: n.valor_iss), ("ISS retido", lambda n: "Sim" if n.iss_retido else "Não"),
               ("Retenções", lambda n: n.valor_retencoes), ("Valor líquido", lambda n: n.valor_liquido),
               ("Situação", lambda n: "Cancelada" if n.cancelada else "Normal"), ("Chave de acesso", lambda n: n.chave)]


def excel_recebidas(notas, lancadas):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    ws = wb.active
    ws.title = "NFS-e recebidas"
    cab = [c for c, _ in COLUNAS_REC] + ["Lançada no contas a pagar"]
    ws.append(cab)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1E3A5F")
    for n in notas:
        ws.append([f(n) for _, f in COLUNAS_REC] + ["" if n.cancelada else (lancadas.get(n.id) or "NÃO LANÇADA")])
    moeda = {i + 1 for i, (c, _) in enumerate(COLUNAS_REC) if c in ("Valor serviços", "ISS", "Retenções", "Valor líquido")}
    for row in ws.iter_rows(min_row=2):
        for c in row:
            if c.column in moeda:
                c.number_format = '#,##0.00'
            elif isinstance(c.value, datetime):
                c.number_format = "dd/mm/yyyy hh:mm"
            elif isinstance(c.value, date):
                c.number_format = "dd/mm/yyyy"
    larg = {"Descrição": 60, "Prestador": 38, "Serviço": 40, "Chave de acesso": 55, "Lançada no contas a pagar": 45}
    for i, c in enumerate(cab, 1):
        ws.column_dimensions[get_column_letter(i)].width = larg.get(c, 15)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def zip_xml_recebidas(notas):
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as z:
        for n in notas:
            if n.xml:
                x = n.xml if n.xml.lstrip().startswith("<?xml") else '<?xml version="1.0" encoding="utf-8"?>\n' + n.xml
                z.writestr(f"NFSe_{n.prestador_doc or 'prest'}_{n.numero or n.id}.xml", x)
    return bio.getvalue()


def status_adn(emp):
    from ..models import NFSeRecebida
    ult = Configuracao.obter(f"nfse_adn_{emp.id}_ultima")
    return {"emp": emp, "cert": sz.pronto(emp), "var": sz.var_senha(emp),
            "ultima": datetime.fromisoformat(ult) if ult else None,
            "nsu": Configuracao.obter(f"nfse_adn_{emp.id}_nsu") or "0",
            "qtd": NFSeRecebida.query.filter_by(empresa_id=emp.id).count()}


# ---------------------------------------------------------------- PDF das notas EMITIDAS (padrão da Prefeitura do Recife)

def _fmt_doc(d):
    d = re.sub(r"\D", "", str(d or ""))
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return d or "—"


def pdf_emitida(n):
    """PDF da NFS-e emitida: DANFSe no padrão nacional (o mesmo do Emissor Nacional) quando há o XML nacional;
    senão, um resumo montado com os dados da Prefeitura."""
    if n.xml_nacional:
        try:
            return danfse_local(n.xml_nacional, n.cancelada)
        except Exception:  # noqa: BLE001 — XML fora do esperado: cai no resumo
            pass
    return _pdf_resumo_emitida(n)


def _pdf_resumo_emitida(n):
    from fpdf import FPDF

    troca = {"\u2014": "-", "\u2013": "-", "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
             "\u2026": "...", "\u2022": "-", "\u00a0": " "}

    def t(v):  # fpdf (fonte padrão) só aceita latin-1
        v = str(v if v is not None else "")
        for a, b in troca.items():
            v = v.replace(a, b)
        return v.encode("latin-1", "replace").decode("latin-1")

    emp = n.empresa
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, 15)
    pdf.add_page()
    pdf.set_draw_color(0, 48, 78)
    pdf.set_fill_color(0, 48, 78)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 10, t("NOTA FISCAL DE SERVIÇO ELETRÔNICA - NFS-e"), border=0, fill=True, align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 9)
    pdf.ln(2)
    linha = [("Número da nota", n.numero), ("Emissão", n.data_emissao.strftime("%d/%m/%Y %H:%M") if n.data_emissao else "—"),
             ("Competência", n.competencia.strftime("%m/%Y") if n.competencia else "—"),
             ("Código de verificação", n.codigo_verificacao or "—")]
    w = (pdf.w - 20) / 4
    pdf.set_font("Helvetica", "B", 7)
    for rot, _ in linha:
        pdf.cell(w, 5, t(rot), border="LTR")
    pdf.ln()
    pdf.set_font("Helvetica", "", 10)
    for _, v in linha:
        pdf.cell(w, 7, t(v), border="LBR")
    pdf.ln(9)

    def bloco(titulo, linhas):
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(230, 236, 242)
        pdf.cell(0, 6, t(titulo), border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        for rot, v in linhas:
            pdf.set_font("Helvetica", "B", 8)
            pdf.cell(45, 6, t(rot), border="L")
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(0, 6, t(v), border="R", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 0, "", border="T", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    bloco("PRESTADOR DO SERVIÇO", [("Razão social", emp.nome if emp else ""), ("CNPJ", _fmt_doc(emp.cnpj if emp else "")),
                                   ("Inscrição municipal", inscricao(emp) if emp else "—"), ("Município", "Recife - PE")])
    bloco("TOMADOR DO SERVIÇO", [("Nome / razão social", n.tomador_nome or "—"), ("CPF / CNPJ", _fmt_doc(n.tomador_doc))]
          + ([("Obra", n.obra)] if n.obra else []))
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(230, 236, 242)
    pdf.cell(0, 6, t("DISCRIMINAÇÃO DOS SERVIÇOS"), border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 5, t(n.discriminacao or "—"), border=1, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 5, t(f"Item da lista de serviços: {n.item_servico or '—'}" + (f"   ·   RPS: {n.rps}" if n.rps else "")),
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    def brl(v):
        return "R$ " + f"{v or 0:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    valores = [("Valor dos serviços", n.valor_servicos), ("Deduções", n.valor_deducoes), ("PIS", n.valor_pis),
               ("COFINS", n.valor_cofins), ("INSS", n.valor_inss), ("IR", n.valor_ir), ("CSLL", n.valor_csll),
               (f"ISS{(' (' + str(n.aliquota) + ')') if n.aliquota else ''}{' - RETIDO' if n.iss_retido else ''}", n.valor_iss)]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(230, 236, 242)
    pdf.cell(0, 6, t("VALORES"), border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
    meia = (pdf.w - 20) / 2
    for i in range(0, len(valores), 2):
        for rot, v in valores[i:i + 2]:
            pdf.set_font("Helvetica", "", 8)
            pdf.cell(meia * 0.6, 6, t(rot), border="L" if True else 0)
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(meia * 0.4, 6, t(brl(v)), border="R", align="R")
        pdf.ln()
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(meia * 1.2, 9, t("VALOR LÍQUIDO DA NOTA"), border="LTB")
    pdf.cell(meia * 0.8, 9, t(brl(n.valor_liquido)), border="RTB", align="R", new_x="LMARGIN", new_y="NEXT")
    if n.cancelada:
        pdf.ln(4)
        pdf.set_text_color(200, 0, 0)
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, t("NOTA CANCELADA" + (f" EM {n.cancelada_em:%d/%m/%Y}" if n.cancelada_em else "")), align="C",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 7)
    pdf.multi_cell(0, 4, t("Representação da NFS-e gerada pelo Sistema de Gestão Vieira Diniz a partir do XML da "
                           "Prefeitura do Recife. A autenticidade pode ser confirmada no site da Prefeitura com o "
                           "número da nota, a inscrição municipal e o código de verificação."))
    return bytes(pdf.output())
