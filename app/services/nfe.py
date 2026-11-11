"""Notas fiscais de compra (NF-e modelo 55).

- Chave de acesso (44 dígitos, é o código de barras do DANFE):
  cUF(2) AAMM(2+2) CNPJ emitente(14) modelo(2) série(3) número(9) tpEmis(1) código(8) DV(1).
  Lida por leitor USB (que "digita" a chave) ou pela câmera do celular.
- XML da NF-e: traz fornecedor, itens, valores e as parcelas (duplicatas) com vencimento —
  base de "condições de pagamento" e "pagamentos em atraso" do painel.
"""
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime

from ..extensions import db
from ..models import NotaFiscal, NotaItem, NotaParcela
from .estoque import RegraNegocio, normalizar

UFS = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO", "21": "MA", "22": "PI",
       "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
       "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF"}


def limpar_chave(texto):
    return re.sub(r"\D", "", texto or "")


def dv_chave(chave43):
    soma, peso = 0, 2
    for d in reversed(chave43):
        soma += int(d) * peso
        peso = 2 if peso == 9 else peso + 1
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def ler_chave(texto):
    c = limpar_chave(texto)
    if len(c) != 44:
        raise RegraNegocio(f"A chave precisa ter 44 números (lidos {len(c)}). Leia de novo o código de barras do DANFE.")
    if dv_chave(c[:43]) != int(c[43]):
        raise RegraNegocio("Chave inválida (dígito verificador não confere). Leia de novo o código de barras.")
    return {"chave": c, "uf": UFS.get(c[0:2], c[0:2]), "ano": 2000 + int(c[2:4]), "mes": int(c[4:6]),
            "emitente_cnpj": c[6:20], "modelo": c[20:22], "serie": str(int(c[22:25])), "numero": str(int(c[25:34]))}


def _t(el, caminho, ns):
    x = el.find(caminho, ns)
    return x.text.strip() if x is not None and x.text else None


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def ler_xml(conteudo):
    try:
        raiz = ET.fromstring(conteudo)
    except ET.ParseError:
        raise RegraNegocio("Arquivo XML inválido. Envie o XML da NF-e que o fornecedor mandou por e-mail.")
    ns = {"n": "http://www.portalfiscal.inf.br/nfe"}
    inf = raiz.find(".//n:infNFe", ns)
    if inf is None:
        raise RegraNegocio("Este XML não é de uma NF-e.")
    chave = limpar_chave(inf.get("Id"))
    emissao = _t(inf, "n:ide/n:dhEmi", ns) or _t(inf, "n:ide/n:dEmi", ns)
    try:
        emissao = datetime.fromisoformat(emissao[:19]) if emissao else None
    except ValueError:
        emissao = None
    itens = []
    for det in inf.findall("n:det", ns):
        p = det.find("n:prod", ns)
        itens.append({"codigo": _t(p, "n:cProd", ns), "descricao": _t(p, "n:xProd", ns), "ncm": _t(p, "n:NCM", ns),
                      "unidade": _t(p, "n:uCom", ns), "quantidade": _f(_t(p, "n:qCom", ns)),
                      "valor_unitario": _f(_t(p, "n:vUnCom", ns)), "valor_total": _f(_t(p, "n:vProd", ns))})
    parcelas = []
    for dup in inf.findall("n:cobr/n:dup", ns):
        venc = _t(dup, "n:dVenc", ns)
        parcelas.append({"numero": _t(dup, "n:nDup", ns), "valor": _f(_t(dup, "n:vDup", ns)),
                         "vencimento": date.fromisoformat(venc) if venc else None})
    return {"chave": chave, "numero": _t(inf, "n:ide/n:nNF", ns), "serie": _t(inf, "n:ide/n:serie", ns),
            "emitente_cnpj": _t(inf, "n:emit/n:CNPJ", ns), "emitente_nome": _t(inf, "n:emit/n:xNome", ns),
            "destinatario_cnpj": _t(inf, "n:dest/n:CNPJ", ns), "emissao": emissao,
            "valor_total": _f(_t(inf, "n:total/n:ICMSTot/n:vNF", ns)), "itens": itens, "parcelas": parcelas}


def condicao_pagamento(emissao, parcelas):
    if not parcelas:
        return "À vista / sem duplicata"
    if not emissao:
        return f"{len(parcelas)} parcela(s)"
    dias = [max(0, (p["vencimento"] - emissao.date()).days) for p in parcelas if p.get("vencimento")]
    return "/".join(str(d) for d in dias) + " dias" if dias else f"{len(parcelas)} parcela(s)"


def registrar(usuario, chave=None, xml_bytes=None):
    """Cria (ou completa) a nota pela chave e/ou XML. Devolve (nota, criada?)."""
    dados = ler_xml(xml_bytes) if xml_bytes else None
    info = ler_chave(chave or (dados or {}).get("chave"))
    if dados and dados["chave"] != info["chave"]:
        raise RegraNegocio("O XML enviado é de outra nota (a chave não confere com a lida no código de barras).")
    nota = NotaFiscal.query.filter_by(chave=info["chave"]).first()
    criada = nota is None
    if criada:
        nota = NotaFiscal(chave=info["chave"], numero=info["numero"], serie=info["serie"],
                          emitente_cnpj=info["emitente_cnpj"], criado_por=getattr(usuario, "nome", None) or "Sistema",
                          emissao=datetime(info["ano"], info["mes"], 1))
        db.session.add(nota)
        if not dados:
            completar_pela_sefaz(nota, usuario, buscar_nome=True)
    if dados and not nota.tem_xml:
        nota.numero, nota.serie = dados["numero"] or nota.numero, dados["serie"] or nota.serie
        nota.emitente_nome, nota.destinatario_cnpj = dados["emitente_nome"], dados["destinatario_cnpj"]
        nota.emissao = dados["emissao"] or nota.emissao
        nota.valor_total, nota.tem_xml = dados["valor_total"], True
        nota.xml = xml_bytes.decode("utf-8", "ignore") if isinstance(xml_bytes, bytes) else xml_bytes
        nota.condicao = condicao_pagamento(dados["emissao"], dados["parcelas"])
        for i in dados["itens"]:
            nota.itens.append(NotaItem(**i))
        for p in dados["parcelas"]:
            nota.parcelas.append(NotaParcela(**p))
    if not nota.destinatario_cnpj:
        ident = identificar_empresa(nota.chave, dados, nota.obra_id)
        if ident["empresa"]:
            nota.destinatario_cnpj = ident["empresa"].cnpj
    db.session.flush()
    return nota, criada


def item_parecido(nota, nome):
    """Item da nota mais parecido com o nome do insumo (para sugerir o custo unitário)."""
    alvo = set(normalizar(nome).split())
    melhor, pontos = None, 0
    for it in nota.itens:
        p = len(alvo & set(normalizar(it.descricao).split()))
        if p > pontos:
            melhor, pontos = it, p
    return melhor


# ---------------------------------------------------------------- chave a partir de foto ou PDF do DANFE

def _chaves_no_texto(texto):
    """Sequências de 44 dígitos (aceita espaços/pontos entre os blocos, como no DANFE) com DV válido."""
    achadas = []
    so = re.sub(r"[^\d\n]", "", texto or "")
    candidatos = re.findall(r"\d{44}", so) + re.findall(r"\d{44}", re.sub(r"\D", "", texto or ""))
    for c in candidatos:
        if dv_chave(c[:43]) == int(c[43]) and c not in achadas:
            achadas.append(c)
    return achadas


def _ler_codigos(imagem):
    """Tenta ler o código de barras (Code 128 / ITF / QR) de uma imagem PIL com zxing-cpp."""
    import zxingcpp
    from PIL import ImageOps
    base = ImageOps.exif_transpose(imagem).convert("L")
    tentativas = [base]
    if max(base.size) > 2600:  # foto muito grande: reduz (zxing fica mais rápido e às vezes melhor)
        f = 2600 / max(base.size)
        tentativas.append(base.resize((int(base.width * f), int(base.height * f))))
    if max(base.size) < 1400:  # imagem pequena: amplia
        tentativas.append(base.resize((base.width * 2, base.height * 2)))
    tentativas.append(ImageOps.autocontrast(base))
    tentativas.append(base.point(lambda x: 0 if x < 140 else 255))  # preto e branco (foto com sombra)
    for img in list(tentativas):
        tentativas.append(img.rotate(90, expand=True))
    for img in tentativas:
        try:
            for r in zxingcpp.read_barcodes(img):
                for c in _chaves_no_texto(r.text):
                    return c
        except Exception:
            continue
    return None


def chave_de_arquivo(conteudo, nome=""):
    """Foto (jpg/png) do código de barras ou PDF do DANFE -> chave de 44 dígitos. Levanta RegraNegocio."""
    import io
    nome = (nome or "").lower()
    if not conteudo:
        raise RegraNegocio("Arquivo vazio.")
    if nome.endswith(".pdf") or conteudo[:4] == b"%PDF":
        import pdfplumber
        with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
            for pg in pdf.pages[:3]:
                achadas = _chaves_no_texto(pg.extract_text() or "")
                if achadas:
                    return achadas[0]
            for pg in pdf.pages[:2]:
                for res in (150, 200, 300, 110):  # DANFE escaneado: a resolução certa varia
                    c = _ler_codigos(pg.to_image(resolution=res).original)
                    if c:
                        return c
        raise RegraNegocio("Não achei a chave de acesso neste PDF. Confira se é o DANFE da nota.")
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(conteudo))
        img.load()
    except Exception:
        raise RegraNegocio("Formato de imagem não reconhecido. Envie JPG, PNG ou o PDF do DANFE.")
    c = _ler_codigos(img)
    if not c:
        raise RegraNegocio("Não consegui ler o código de barras na foto. Fotografe de perto, com o código "
                           "inteiro, reto e bem iluminado (sem reflexo), ou envie o PDF do DANFE.")
    return c


# ---------------------------------------------------------------- nota só pela chave: completar sozinha

def nome_por_cnpj(cnpj, consultar_internet=True):
    """Nome do fornecedor pelo CNPJ: primeiro no que o sistema já tem (SEFAZ, notas, pedidos, DDA);
    se não achar, na consulta pública de CNPJ (BrasilAPI). Devolve None se não conseguir."""
    from ..models import BoletoDDA, NFeRecebida, PedidoERP
    c = re.sub(r"\D", "", str(cnpj or ""))
    if len(c) != 14:
        return None
    for modelo, col_cnpj, col_nome in ((NFeRecebida, NFeRecebida.emitente_cnpj, NFeRecebida.emitente_nome),
                                       (NotaFiscal, NotaFiscal.emitente_cnpj, NotaFiscal.emitente_nome),
                                       (PedidoERP, PedidoERP.fornecedor_cnpj, PedidoERP.fornecedor_nome),
                                       (BoletoDDA, BoletoDDA.cnpj, BoletoDDA.beneficiario)):
        nome = (db.session.query(col_nome).filter(col_cnpj == c, col_nome.isnot(None), col_nome != "")
                .order_by(modelo.id.desc()).limit(1).scalar())
        if nome:
            return nome[:200]
    if not consultar_internet:
        return None
    try:
        import requests
        r = requests.get(f"https://brasilapi.com.br/api/cnpj/v1/{c}", timeout=4)
        if r.ok:
            d = r.json()
            return (d.get("razao_social") or d.get("nome_fantasia") or "").strip()[:200] or None
    except Exception:  # noqa: BLE001 — sem internet / serviço fora: fica o CNPJ mesmo
        return None
    return None


def completar_pela_sefaz(nota, usuario=None, buscar_nome=False):
    """Nota lançada só pela chave: usa o que já veio da SEFAZ (XML completo ou, ao menos, o resumo:
    fornecedor, valor e data). Devolve "xml", "resumo" ou None."""
    from ..models import NFeRecebida
    if nota.tem_xml:
        return None
    rec = NFeRecebida.query.filter_by(chave=nota.chave).first()
    if rec and rec.xml:
        try:
            registrar(usuario, chave=nota.chave, xml_bytes=rec.xml.encode("utf-8"))
            return "xml"
        except RegraNegocio:
            pass
    feito = None
    if rec:
        if rec.empresa and not nota.destinatario_cnpj:
            nota.destinatario_cnpj = rec.empresa.cnpj
        nota.emitente_nome = nota.emitente_nome or rec.emitente_nome
        nota.valor_total = nota.valor_total or rec.valor
        if rec.emissao:
            nota.emissao = rec.emissao
        feito = "resumo"
    if buscar_nome and not nota.emitente_nome:
        nota.emitente_nome = nome_por_cnpj(nota.emitente_cnpj)
    return feito


def completar_pendentes():
    """Depois de cada busca na SEFAZ: completa as notas que estavam só com a chave."""
    n = 0
    for nota in NotaFiscal.query.filter(db.or_(NotaFiscal.tem_xml.is_(False), NotaFiscal.tem_xml.is_(None))).all():
        if completar_pela_sefaz(nota, buscar_nome=False) == "xml":
            n += 1
    return n


# ---------------------------------------------------------------- de qual empresa do grupo é a nota

def _empresas():
    from ..models import Empresa
    return Empresa.query.order_by(Empresa.id).all()


def empresa_por_cnpj(cnpj):
    c = re.sub(r"\D", "", str(cnpj or ""))
    return next((e for e in _empresas() if e.cnpj == c), None) if len(c) == 14 else None


def identificar_empresa(chave, dados=None, obra=None):
    """Descobre para qual empresa do grupo (F. Diniz ou Ramos Diniz) a nota foi emitida.

    A chave de acesso não traz o CNPJ do destinatário, então usa, nesta ordem:
    1. XML: CNPJ do destinatário (certo);
    2. Notas na SEFAZ: a nota foi trazida pelo certificado de qual CNPJ (certo);
    3. obra escolhida: o prefixo do nome (FDINIZ_ / RAMOS_);
    4. histórico do fornecedor: notas anteriores, boletos do DDA e pedidos do Omie (F. Diniz).
    Devolve {"empresa": Empresa|None, "motivo": str, "certo": bool}.
    """
    from collections import Counter
    from ..models import BoletoDDA, NFeRecebida, Obra, PedidoERP
    emps = _empresas()
    if dados and dados.get("destinatario_cnpj"):
        e = empresa_por_cnpj(dados["destinatario_cnpj"])
        if e:
            return {"empresa": e, "motivo": "CNPJ do destinatário no XML", "certo": True}
        return {"empresa": None, "certo": False,
                "motivo": f"o destinatário do XML (CNPJ {dados['destinatario_cnpj']}) não é F. Diniz nem Ramos Diniz"}
    c = limpar_chave(chave) if chave else None
    if c:
        rec = NFeRecebida.query.filter_by(chave=c).first()
        if rec and rec.empresa:
            return {"empresa": rec.empresa, "motivo": "nota encontrada na SEFAZ no CNPJ desta empresa", "certo": True}
    # obra escolhida: "obra:12" ou o id
    oid = None
    if isinstance(obra, str) and obra.startswith("obra:") and obra[5:].isdigit():
        oid = int(obra[5:])
    elif isinstance(obra, int):
        oid = obra
    if oid:
        o = db.session.get(Obra, oid)
        nome = normalizar(o.nome if o else "").replace(" ", "")
        for e in emps:
            pref = normalizar(e.prefixo_obras or "").replace("_", "")
            if pref and (nome.startswith(pref) or (pref == "FDINIZ" and nome.startswith("FDINZ"))):
                return {"empresa": e, "motivo": f"obra escolhida ({e.prefixo_obras})", "certo": False}
    try:
        emit = ler_chave(c)["emitente_cnpj"] if c else None
    except RegraNegocio:
        emit = None
    if not emit:
        return {"empresa": None, "motivo": "", "certo": False}
    votos = Counter()
    for (dest,) in (db.session.query(NotaFiscal.destinatario_cnpj)
                    .filter(NotaFiscal.emitente_cnpj == emit, NotaFiscal.destinatario_cnpj.isnot(None))):
        e = empresa_por_cnpj(dest)
        if e:
            votos[e.id] += 1
    for (eid,) in db.session.query(NFeRecebida.empresa_id).filter(NFeRecebida.emitente_cnpj == emit):
        if eid:
            votos[eid] += 1
    for (eid,) in db.session.query(BoletoDDA.empresa_id).filter(BoletoDDA.cnpj == emit):
        if eid:
            votos[eid] += 1
    omie = next((e for e in emps if e.sistema == "omie"), None)
    if omie and PedidoERP.query.filter_by(fornecedor_cnpj=emit).first():
        votos[omie.id] += 2
    if votos:
        (eid, n), *resto = votos.most_common()
        e = next((x for x in emps if x.id == eid), None)
        if resto and resto[0][1] == n:
            return {"empresa": None, "certo": False,
                    "motivo": "este fornecedor atende as duas empresas — escolha abaixo"}
        return {"empresa": e, "certo": False, "motivo": "pelo histórico deste fornecedor (notas, DDA, pedidos)"}
    return {"empresa": None, "certo": False, "motivo": "fornecedor novo, sem histórico — escolha abaixo"}


def definir_empresa(nota, empresa):
    """Grava a empresa (CNPJ do destinatário) na nota — nunca por cima do que veio no XML."""
    if empresa and not nota.tem_xml:
        nota.destinatario_cnpj = empresa.cnpj


# ---------------------------------------------------------------- entrada no estoque direto pela nota

def ja_entrou(item):
    """Quantidade deste item da nota que já entrou no estoque (entradas não estornadas)."""
    from ..models import Movimentacao
    q = (db.session.query(db.func.coalesce(db.func.sum(Movimentacao.quantidade), 0))
         .filter(Movimentacao.nota_item_id == item.id, Movimentacao.tipo == "entrada",
                 Movimentacao.estornada_em.is_(None)))
    return float(q.scalar() or 0)


def sugerir_insumo(item, nota=None):
    """Insumo do catálogo para um item da nota: o já associado; o mesmo código deste fornecedor em notas
    anteriores; o nome igual; ou o mais parecido. Devolve (insumo|None, motivo)."""
    from ..models import Insumo, _texto_busca
    from .estoque import buscar_insumos
    if item.insumo:
        return item.insumo, "associado"
    nota = nota or item.nota
    if item.codigo and nota and nota.emitente_cnpj:
        ant = (db.session.query(NotaItem.insumo_id).join(NotaFiscal)
               .filter(NotaFiscal.emitente_cnpj == nota.emitente_cnpj, NotaItem.codigo == item.codigo,
                       NotaItem.insumo_id.isnot(None), NotaItem.id != item.id)
               .order_by(NotaItem.id.desc()).limit(1).scalar())
        if ant:
            return db.session.get(Insumo, ant), "mesmo código deste fornecedor em nota anterior"
    igual = Insumo.query.filter_by(nome_busca=_texto_busca(item.descricao)).first()
    if igual:
        return igual, "mesmo nome no catálogo"
    # mesmo nome com espaços / pontuação diferentes (ex.: "CABO FLEX 1KV 2 X1,5MM" x "CABO FLEX 1KV 2X1,5MM")
    import re as _re
    from difflib import SequenceMatcher
    compacto = lambda t: _re.sub(r"[^A-Z0-9]", "", _texto_busca(t))
    alvo = compacto(item.descricao)
    primeira = (_texto_busca(item.descricao).split() or [""])[0]
    if alvo and primeira:
        cands = Insumo.query.filter(Insumo.nome_busca.like(primeira + "%"), Insumo.ativo.isnot(False)).limit(400).all()
        for c in cands:
            if compacto(c.nome) == alvo:
                return c, "mesmo nome no catálogo"
        melhor = max(cands, key=lambda c: SequenceMatcher(None, compacto(c.nome), alvo).ratio(), default=None)
        if melhor and SequenceMatcher(None, compacto(melhor.nome), alvo).ratio() >= 0.9:
            return melhor, "nome quase igual — confira"
    for n_palavras in (4, 3, 2):
        termos = " ".join([t for t in normalizar(item.descricao).split() if len(t) >= 3 and not t.isdigit()][:n_palavras])
        if termos:
            achados = buscar_insumos(termos, 2)
            if len(achados) == 1:
                return achados[0], "parecido — confira"
    return None, None


def dar_entrada(nota, linhas, usuario, pulados=None):
    """linhas: [(NotaItem, Insumo|None ou "novo", quantidade, Deposito)]. Devolve quantas entradas lançou.
    Com a lista `pulados`, o item sem insumo escolhido fica para depois (os outros entram) em vez de travar tudo."""
    from ..models import Insumo
    from . import estoque as est
    doc = f"{nota.numero}/{nota.serie}" if nota.numero else None
    n = 0
    for item, insumo, qtd, dep in linhas:
        if pulados is not None and not insumo:
            pulados.append(item.descricao)
            continue
        qtd = est._num(qtd) if qtd not in (None, "") else 0
        if qtd <= 0:
            continue
        resta = (item.quantidade or 0) - ja_entrou(item)
        if qtd > resta + 1e-6:
            raise RegraNegocio(f"{item.descricao}: {est.fmt_qtd(qtd)} é mais do que falta entrar "
                               f"({est.fmt_qtd(max(resta, 0))} {item.unidade or ''}).")
        if insumo == "novo":
            insumo = Insumo(nome=(item.descricao or "ITEM").upper()[:255], unidade=(item.unidade or "UN").upper()[:20],
                            ativo=True, grupo="Material")
            db.session.add(insumo)
            db.session.flush()
        if not insumo:
            raise RegraNegocio(f"{item.descricao}: escolha o insumo do catálogo (ou marque cadastrar como novo).")
        if not dep:
            raise RegraNegocio(f"{item.descricao}: escolha o local de estoque.")
        item.insumo = insumo
        mov = est.registrar_entrada(insumo, dep, qtd, usuario.nome, custo_unitario=item.valor_unitario,
                                    documento=doc, observacao=f"NF {doc or nota.chave[-9:]} · {nota.fornecedor}"[:255])
        db.session.flush()
        mov.nota_id, mov.nota_item_id = nota.id, item.id
        n += 1
    if not n:
        if pulados:
            raise RegraNegocio("Escolha o insumo do catálogo (clique numa opção da lista que aparece ao digitar) ou "
                               "marque “cadastrar como novo insumo” em: " + "; ".join(pulados) + ".")
        raise RegraNegocio("Informe a quantidade em pelo menos um item.")
    return n


# ---------------------------------------------------------------- DANFE (PDF) e download do XML

def danfe_pdf(xml_texto):
    """PDF do DANFE a partir do XML da NF-e (biblioteca brazilfiscalreport)."""
    from brazilfiscalreport.danfe import Danfe
    if isinstance(xml_texto, bytes):
        xml_texto = xml_texto.decode("utf-8", "ignore")
    return bytes(Danfe(xml=xml_texto).output())


def resposta_danfe(xml_texto, chave):
    from flask import Response, current_app, flash, redirect, request
    try:
        pdf = danfe_pdf(xml_texto)
    except Exception:  # noqa: BLE001 — XML fora do padrão esperado pela biblioteca
        current_app.logger.exception("Falha ao gerar DANFE %s", chave)
        flash("Não consegui montar o DANFE deste XML. Baixe o XML e abra no portal da SEFAZ.", "danger")
        return redirect(request.referrer or "/")
    baixar = request.args.get("baixar") == "1"
    return Response(pdf, mimetype="application/pdf", headers={
        "Content-Disposition": f'{"attachment" if baixar else "inline"}; filename="DANFE-{chave}.pdf"'})


def resposta_xml(xml_texto, chave):
    from flask import Response
    corpo = xml_texto.encode("utf-8") if isinstance(xml_texto, str) else xml_texto
    return Response(corpo, mimetype="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="NFe{chave}.xml"'})
