"""Pedidos de compra do ERP e vínculo com as notas fiscais recebidas.

Origem dos pedidos
  F. Diniz  -> Omie: rotina produtos/pedidocompra, método PesquisarPedCompra (cabeçalho + produtos).
  Ramos Diniz -> Mais Controle: a "API para Relatórios" NÃO tem pedidos de compra. Usamos as Ordens de
                 Compra importadas dos PDFs (OrdemCompraMC: número, fornecedor, valor, data — sem itens),
                 vinculadas à nota pelo número da OC (NotaOrdemMC).

Fluxo
  1. Integrações/Notas -> "Atualizar pedidos do Omie" copia os pedidos (em segundo plano).
  2. Ao abrir uma nota, o sistema sugere os pedidos em aberto do MESMO fornecedor (CNPJ da nota)
     e pré-preenche a quantidade de cada item do pedido pelo item parecido da nota.
  3. O usuário confere e confirma: grava o vínculo nota x item do pedido e, se marcado,
     dá entrada no Estoque Central (uma movimentação por item, ligada à nota).
"""
import re
import threading
from datetime import date, datetime, timedelta

from ..extensions import db
from ..models import (Compra, DadoImportado, Deposito, Empresa, Insumo, LogIntegracao, Movimentacao, NotaOrdemMC,
                      NotaPedidoItem, Obra, OrdemCompraMC, PedidoERP, PedidoERPItem, agora)
from . import estoque as est
from .estoque import RegraNegocio, normalizar

_em_andamento = set()


# ---------------------------------------------------------------- utilidades

def _dig(v):
    return re.sub(r"\D", "", str(v or ""))


def _num(v):
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _data(v):
    s = str(v or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            pass
    return None


def _pega(d, *nomes):
    for n in nomes:
        if isinstance(d, dict) and d.get(n) not in (None, ""):
            return d[n]
    return None


_STOP = {"COM", "PARA", "DE", "DA", "DO", "DAS", "DOS", "UND", "UNID", "PCT", "CX", "TIPO", "REF", "MM", "CM"}


def _tokens(txt):
    return {t for t in re.split(r"[^A-Z0-9]+", normalizar(txt)) if len(t) >= 3 and t not in _STOP}


def parecenca(a, b):
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


# ---------------------------------------------------------------- cópia dos pedidos do Omie

def _fornecedores_omie(emp, cli):
    """codigo_cliente -> (cnpj, nome). Usa a cópia já importada; se não houver, busca no Omie."""
    linhas = [d.dados for d in DadoImportado.query.filter_by(empresa_id=emp.id, tabela="fornecedores_clientes")]
    if not linhas:
        from .financeiro import _omie_paginas
        linhas = list(_omie_paginas(cli, "geral/clientes", "ListarClientesResumido", "clientes_cadastro_resumido"))
    return {str(c.get("codigo_cliente")): (_dig(c.get("cnpj_cpf"))[:14],
                                           c.get("nome_fantasia") or c.get("razao_social")) for c in linhas}


def _pesquisar(cli, pagina, desde):
    """PesquisarPedCompra: tenta com filtros de pedidos em aberto; se a conta recusar, só paginação."""
    base = {"nPagina": pagina, "nRegsPorPagina": 50}
    abertos = {"lExibirPedidosPendentes": True, "lExibirPedidosFaturados": True,
               "lExibirPedidosRecParciais": True, "lExibirPedidosFatParciais": True,
               "lExibirPedidosRecebidos": False, "lExibirPedidosCancelados": False,
               "lExibirPedidosEncerrados": False, "dDataInicial": desde.strftime("%d/%m/%Y"),
               "dDataFinal": date.today().strftime("%d/%m/%Y")}
    from .omie import OmieErro
    ultimo = None
    for extra in (abertos, {k: ("T" if v is True else "F" if v is False else v) for k, v in abertos.items()}, {}):
        try:
            return cli.chamar("produtos/pedidocompra", "PesquisarPedCompra", dict(base, **extra))
        except OmieErro as e:
            ultimo = e
            if "não configurado" in str(e) or "não existem registros" in str(e).lower():
                raise
    raise ultimo


def _gravar_pedido(emp, p, fornecedores):
    cab = _pega(p, "cabecalho_consulta", "cabecalho") or {}
    produtos = _pega(p, "produtos_consulta", "produtos") or []
    idp = _pega(cab, "nCodPed", "nCodPedido", "cCodIntPed")
    if not idp:
        return None, False
    ped = PedidoERP.query.filter_by(sistema="omie", id_externo=str(idp)).first()
    novo = ped is None
    if novo:
        ped = PedidoERP(sistema="omie", id_externo=str(idp), empresa_id=emp.id)
        db.session.add(ped)
    cod_for = str(_pega(cab, "nCodFor", "nCodFornecedor") or "")
    cnpj, nome = fornecedores.get(cod_for, (None, None))
    ped.numero = str(_pega(cab, "cNumero", "cNumPedido", "cCodIntPed") or idp)
    ped.fornecedor_codigo = cod_for or None
    ped.fornecedor_cnpj = _dig(_pega(cab, "cCnpjCpfFor", "cCnpjFor")) or cnpj or None
    ped.fornecedor_nome = nome or _pega(cab, "cNomeFor", "cRazaoFor")
    ped.emissao = _data(_pega(cab, "dIncData", "dDtEmissao", "dDataInclusao"))
    ped.previsao = _data(_pega(cab, "dDtPrevisao", "dPrevisao"))
    ped.etapa = str(_pega(cab, "cEtapa", "cStatus") or "") or None
    ped.projeto = str(_pega(cab, "nCodProj") or "") or None
    ped.observacao = _pega(cab, "cObs", "cObsInt")
    ped.dados = p
    existentes = {i.id_externo: i for i in ped.itens}
    total = 0.0
    for n, pr in enumerate(produtos):
        chave = str(_pega(pr, "nCodItem", "nCodIte", "cCodIntItem") or f"{_pega(pr, 'nCodProd') or 'x'}#{n}")
        it = existentes.get(chave)
        if not it:
            it = PedidoERPItem(id_externo=chave)
            ped.itens.append(it)
        it.produto_codigo = str(_pega(pr, "nCodProd") or "") or None
        it.produto_integracao = str(_pega(pr, "cCodIntProd") or "") or None
        it.codigo = str(_pega(pr, "cProduto", "cCodigo") or "") or None
        it.descricao = (_pega(pr, "cDescricao", "cDescrProd") or it.codigo or "Item")[:255]
        it.unidade = (_pega(pr, "cUnidade") or "UN")[:20]
        it.quantidade = _num(_pega(pr, "nQtde", "nQuantidade")) or 0
        it.qtd_recebida_erp = _num(_pega(pr, "nQtdeRec", "nQtdeRecebida")) or 0
        it.valor_unitario = _num(_pega(pr, "nValUnit", "nValorUnitario"))
        total += _num(_pega(pr, "nValTot", "nValorTotal")) or (it.quantidade * (it.valor_unitario or 0))
    ped.valor_total = _num(_pega(cab, "nValorTotal", "nTotalPedido")) or total
    return ped, novo


def sincronizar_omie(dias=365):
    from .financeiro import credenciais
    from .omie import OmieClient
    emp = Empresa.query.filter_by(sistema="omie").first()
    if not emp or not credenciais(emp):
        raise RuntimeError("Credenciais do Omie não configuradas (OMIE_FDINIZ_APP_KEY / OMIE_FDINIZ_APP_SECRET).")
    k, s = credenciais(emp)
    cli = OmieClient(app_key=k, app_secret=s, timeout=60)
    fornecedores = _fornecedores_omie(emp, cli)
    desde = date.today() - timedelta(days=dias)
    pagina, total_pag, lidos, novos, campos = 1, 1, 0, 0, None
    while pagina <= min(total_pag, 60):
        try:
            d = _pesquisar(cli, pagina, desde)
        except Exception as e:
            if "não existem registros" in str(e).lower():
                break
            raise
        total_pag = int(_pega(d, "nTotalPaginas", "total_de_paginas") or 1)
        lista = _pega(d, "pedidos_pesquisa", "pedido_compra_pesquisa") or next(
            (v for v in d.values() if isinstance(v, list)), [])
        for p in lista:
            if campos is None:
                campos = sorted((_pega(p, "cabecalho_consulta", "cabecalho") or {}).keys())
            ped, n = _gravar_pedido(emp, p, fornecedores)
            if ped:
                lidos += 1
                novos += int(n)
        db.session.commit()
        pagina += 1
    return lidos, novos, campos


def _rodar(app, usuario):
    with app.app_context():
        try:
            lidos, novos, campos = sincronizar_omie()
            msg = f"{lidos} pedido(s) de compra lidos do Omie, {novos} novo(s)."
            if campos:
                msg += "\nCampos do cabeçalho: " + ", ".join(campos)
            db.session.add(LogIntegracao(sistema="omie", operacao="Pedidos de compra", sucesso=True, mensagem=msg,
                                         usuario=usuario))
        except Exception as e:
            db.session.rollback()
            db.session.add(LogIntegracao(sistema="omie", operacao="Pedidos de compra", sucesso=False,
                                         mensagem=str(e)[:4000], usuario=usuario))
        finally:
            db.session.commit()
            _em_andamento.discard("omie")


def disparar(app, usuario):
    if "omie" in _em_andamento:
        return False
    _em_andamento.add("omie")
    threading.Thread(target=_rodar, args=(app, usuario), daemon=True).start()
    return True


def em_andamento():
    return "omie" in _em_andamento


def ultima_atualizacao():
    return (LogIntegracao.query.filter_by(operacao="Pedidos de compra")
            .order_by(LogIntegracao.id.desc()).first())


# ---------------------------------------------------------------- sugestão de vínculo

def pedidos_abertos():
    peds = PedidoERP.query.order_by(PedidoERP.emissao.desc().nullslast(), PedidoERP.id.desc()).all()
    return [p for p in peds if p.qtd_pendente > 1e-9]


def sugerir(nota, todos=False):
    """Devolve (pedidos sugeridos, mesmo_fornecedor?, pré-preenchimento {item_id: (qtd, nota_item)})."""
    abertos = pedidos_abertos()
    mesmos = [p for p in abertos if nota.emitente_cnpj and p.fornecedor_cnpj == nota.emitente_cnpj]
    lista = abertos if (todos or not mesmos) else mesmos
    # já vinculados a esta nota aparecem sempre
    ja = {v.pedido_item.pedido for v in nota.vinculos_pedido}
    lista = list(dict.fromkeys(list(ja) + lista))[:40]

    pre = {}
    if mesmos and nota.itens:
        sobra = {ni.id: (ni.quantidade or 0) - sum(v.quantidade for v in nota.vinculos_pedido if v.nota_item_id == ni.id)
                 for ni in nota.itens}
        pares = []
        for p in mesmos:
            for it in p.itens:
                if it.qtd_pendente <= 1e-9:
                    continue
                for ni in nota.itens:
                    s = parecenca(it.descricao, ni.descricao)
                    if s >= 0.5:
                        pares.append((s, it, ni))
        for s, it, ni in sorted(pares, key=lambda x: -x[0]):
            if it.id in pre or sobra.get(ni.id, 0) <= 1e-9:
                continue
            q = min(it.qtd_pendente, sobra[ni.id])
            pre[it.id] = (q, ni)
            sobra[ni.id] -= q
    return lista, bool(mesmos), pre


# ---------------------------------------------------------------- vínculo + entrada no estoque

def resolver_insumo(it, criar=True):
    q = None
    if it.produto_codigo:
        q = Insumo.query.filter_by(omie_codigo_produto=it.produto_codigo).first()
    if not q and it.produto_integracao:
        q = Insumo.query.filter_by(codigo_mc=it.produto_integracao).first()
    if not q and it.descricao:
        q = Insumo.query.filter_by(nome_busca=normalizar(it.descricao)).first()
    if not q and criar:
        cod_livre = it.produto_integracao and not Insumo.query.filter_by(codigo_mc=it.produto_integracao).first()
        q = Insumo(nome=(it.descricao or "ITEM").upper(), unidade=(it.unidade or "UN").upper(), ativo=True,
                   omie_codigo_produto=it.produto_codigo, codigo_mc=it.produto_integracao if cod_livre else None)
        db.session.add(q)
        db.session.flush()
    return q


def vincular(nota, linhas, usuario, dar_entrada=True, deposito=None):
    """linhas: [(PedidoERPItem, quantidade, NotaItem|None, entrar: bool)]. Devolve (vínculos, entradas).
    deposito: onde dar entrada (padrão: Estoque Central)."""
    feitos, entradas = 0, 0
    central = (deposito or est.deposito_central()) if dar_entrada else None
    doc = f"{nota.numero}/{nota.serie}" if nota.numero else None
    for it, qtd, ni, entrar in linhas:
        qtd = _num(qtd) or 0
        if qtd <= 0:
            continue
        if qtd > it.qtd_pendente + 1e-6:
            raise RegraNegocio(f"{it.pedido.rotulo} · {it.descricao}: quantidade {est.fmt_qtd(qtd)} maior que o "
                               f"pendente ({est.fmt_qtd(it.qtd_pendente)} {it.unidade}).")
        vu = (ni.valor_unitario if ni and ni.valor_unitario else None) or it.valor_unitario
        v = NotaPedidoItem(nota=nota, pedido_item=it, nota_item=ni, quantidade=qtd, valor_unitario=vu,
                           criado_por=usuario.nome)
        db.session.add(v)
        if dar_entrada and entrar:
            ins = resolver_insumo(it)
            mov = est.registrar_entrada(ins, central, qtd, usuario.nome, custo_unitario=vu, documento=doc,
                                        observacao=f"NF {doc or nota.chave[-9:]} · {it.pedido.rotulo}"[:255])
            db.session.flush()
            mov.nota_id = nota.id
            mov.nota_item_id = ni.id if ni else None
            v.movimentacao = mov
            entradas += 1
        feitos += 1
    if not feitos:
        raise RegraNegocio("Informe a quantidade recebida em pelo menos um item do pedido.")
    db.session.flush()
    auto_obra(nota)
    return feitos, entradas


def desfazer(vinculo, usuario, motivo):
    """Remove o vínculo; se gerou entrada no estoque, estorna a entrada."""
    if vinculo.movimentacao and vinculo.movimentacao.estornavel:
        mov = vinculo.movimentacao
        _sem_envio_omie(mov, est.estornar(mov, usuario, motivo or "Vínculo com pedido de compra desfeito"))
    db.session.delete(vinculo)
    db.session.flush()


# ---------------------------------------------------------------- Ordens de Compra do Mais Controle (Ramos Diniz)

CNPJ_FDINIZ, CNPJ_RAMOS = "56160494000126", "27396528000188"


def empresa_da_nota(nota):
    """'omie', 'maiscontrole' ou None (nota só com a chave: destinatário desconhecido)."""
    d = _dig(nota.destinatario_cnpj)
    if d == CNPJ_FDINIZ:
        return "omie"
    if d == CNPJ_RAMOS:
        return "maiscontrole"
    return None


def sugerir_ordens_mc(nota, busca=None, limite=12):
    """OCs do Mais Controle parecidas com a nota: fornecedor parecido, valor próximo e data até 6 meses antes."""
    ja = {v.ordem_numero for v in nota.vinculos_mc}
    q = OrdemCompraMC.query
    if busca:
        b = str(busca).strip()
        if b.isdigit():
            q = q.filter(OrdemCompraMC.numero == int(b))
        else:
            for termo in normalizar(b).split():
                q = q.filter(OrdemCompraMC.fornecedor.ilike(f"%{termo}%"))
        cands = q.order_by(OrdemCompraMC.data.desc()).limit(60).all()
        return [(o, None) for o in cands if o.numero not in ja][:limite]
    ref = nota.emissao.date() if nota.emissao else date.today()
    nome = nota.emitente_nome or ""
    notas = []
    for o in q.filter(OrdemCompraMC.data >= ref - timedelta(days=180)).all():
        if o.numero in ja or (o.status or "").lower().startswith("cancel"):
            continue
        s_nome = parecenca(nome, o.fornecedor) if nome else 0
        s_valor = 0
        if nota.valor_total and o.valor:
            dif = abs(nota.valor_total - o.valor) / max(nota.valor_total, o.valor)
            s_valor = 1 if dif <= 0.01 else 0.6 if dif <= 0.05 else 0.3 if dif <= 0.15 else 0
        if s_nome < 0.5 and s_valor < 1:
            continue
        pontos = s_nome * 2 + s_valor - (abs((ref - o.data).days) / 365 if o.data else 0.5)
        motivo = []
        if s_nome >= 0.5:
            motivo.append("mesmo fornecedor")
        if s_valor >= 1:
            motivo.append("mesmo valor")
        elif s_valor:
            motivo.append("valor próximo")
        notas.append((pontos, o, " · ".join(motivo)))
    notas.sort(key=lambda x: -x[0])
    return [(o, m) for _, o, m in notas[:limite]]


def vincular_ordens_mc(nota, numeros, usuario):
    feitos = 0
    ja = {v.ordem_numero for v in nota.vinculos_mc}
    for n in numeros:
        try:
            n = int(n)
        except (TypeError, ValueError):
            continue
        if n in ja:
            continue
        o = OrdemCompraMC.query.filter_by(numero=n).first()
        if not o:
            raise RegraNegocio(f"OC {n} não encontrada nas Ordens de Compra do Mais Controle.")
        db.session.add(NotaOrdemMC(nota=nota, ordem_numero=n, valor=o.valor, criado_por=usuario.nome))
        ja.add(n)
        feitos += 1
    if not feitos:
        raise RegraNegocio("Marque pelo menos uma ordem de compra.")
    db.session.flush()
    auto_obra(nota)
    return feitos


# ---------------------------------------------------------------- exclusão da nota

def _sem_envio_omie(mov, estorno):
    """Entrada que nunca foi ao Omie: marca entrada e estorno como resolvidos (não gera ajuste inútil lá)."""
    if not mov.omie_enviado_em and estorno is not None:
        mov.omie_enviado_em = estorno.omie_enviado_em = agora()
        mov.omie_id = estorno.omie_id = "cancelada-antes-do-envio"


def excluir_nota(nota, usuario, motivo):
    """Estorna as entradas de estoque da nota, desfaz recebimentos/vínculos e apaga a nota.
    Qualquer impedimento (material já usado/enviado) levanta RegraNegocio e nada é alterado."""
    motivo = (motivo or "").strip()
    if not motivo:
        raise RegraNegocio("Informe o motivo da exclusão.")
    texto = f"Exclusão da NF {nota.numero}/{nota.serie}: {motivo}"
    resumo = {"estornos": 0, "compras": 0, "pedidos": len(nota.vinculos_pedido), "ocs": len(nota.vinculos_mc)}
    movs = (Movimentacao.query.filter_by(nota_id=nota.id)
            .filter(Movimentacao.tipo == "entrada", Movimentacao.estornada_em.is_(None)).all())
    # 1) recebimentos de "Materiais a Comprar": tira a reserva da solicitação antes de estornar
    for c in Compra.query.filter_by(nota_id=nota.id).all():
        for mov in [m for m in movs if m.insumo_id == c.insumo_id and (m.observacao or "").startswith(f"Recebimento {c.numero}")]:
            q = mov.quantidade or 0
            item = c.item
            if item and mov.solicitacao_id and (item.qtd_reservada or 0) > 0:
                volta = min(q, item.qtd_reservada)
                s = est.saldo(mov.destino, mov.insumo, criar=False)
                if s:
                    s.reservada = max(0.0, (s.reservada or 0) - volta)
                item.qtd_reservada -= volta
                item.qtd_pendente_compra = (item.qtd_pendente_compra or 0) + volta
            c.qtd_recebida = max(0.0, (c.qtd_recebida or 0) - q)
            if c.status == "Recebido":
                c.status = "Comprado"
            resumo["compras"] += 1
        c.nota_id = None
    # 2) estorna todas as entradas da nota (recebimentos, vínculos com pedido, entradas avulsas)
    for mov in movs:
        novo = est.estornar(mov, usuario, texto[:200])
        _sem_envio_omie(mov, novo)
        resumo["estornos"] += 1
    # 3) solta as movimentações (inclusive as já estornadas antes) e apaga a nota
    ids_itens = [i.id for i in nota.itens]
    q_movs = Movimentacao.query.filter(db.or_(Movimentacao.nota_id == nota.id,
                                              Movimentacao.nota_item_id.in_(ids_itens) if ids_itens else db.false()))
    for m in q_movs.all():
        m.nota_id = None
        m.nota_item_id = None    # a entrada pelo item da nota (seção Entrada no estoque) também prende a nota
        m.documento = (m.documento or f"NF {nota.numero}/{nota.serie}")[:80]
    for v in list(nota.vinculos_pedido):
        v.movimentacao_id = None
    db.session.add(LogIntegracao(sistema="estoque", operacao="Nota fiscal excluída", sucesso=True, usuario=usuario.nome,
                                 mensagem=f"NF {nota.numero}/{nota.serie} · {nota.fornecedor} · chave {nota.chave}\n"
                                          f"Motivo: {motivo}\n{resumo['estornos']} entrada(s) estornada(s), "
                                          f"{resumo['compras']} recebimento(s) desfeito(s), {resumo['pedidos']} vínculo(s) "
                                          f"com pedido do Omie e {resumo['ocs']} com OC do Mais Controle removidos."))
    db.session.delete(nota)
    db.session.flush()
    return resumo


# ---------------------------------------------------------------- obra / centro de custo da nota

EMPRESA = "Empresa"   # centro de custo administrativo (igual ao Mais Controle)


def obra_por_centro_custo(texto):
    """Acha a obra cadastrada que corresponde a um centro de custo do Mais Controle/Omie."""
    t = normalizar(texto)
    if not t or t in ("EMPRESA", "ESCRITORIO"):
        return None
    obras = Obra.query.all()
    for o in obras:
        if normalizar(o.nome) == t or (o.codigo_mc and normalizar(o.codigo_mc) == t):
            return o
    melhor, nota = None, 0.0
    for o in obras:
        p = parecenca(o.nome, texto)
        if p > nota:
            melhor, nota = o, p
    return melhor if nota >= 0.8 else None


def sugestao_obra(nota):
    """(Obra|None, texto do centro de custo, origem) a partir das OCs/pedidos vinculados."""
    for v in nota.vinculos_mc:
        o = v.ordem
        if o and o.centro_custo:
            partes = [c.strip() for c in o.centro_custo.split("|") if c.strip()]
            obras = [x for x in (obra_por_centro_custo(c) for c in partes) if x]
            if obras:
                return obras[0], obras[0].nome, f"OC {o.numero}"
            return None, partes[0] if partes else None, f"OC {o.numero}"
    for v in nota.vinculos_pedido:
        pj = v.pedido_item.pedido.projeto
        if pj:
            ob = Obra.query.filter_by(omie_codigo_projeto=pj).first()
            if ob:
                return ob, ob.nome, v.pedido_item.pedido.rotulo
    return None, None, None


def sugestao_obras(nota):
    """Todas as obras / centros de custo das OCs do Mais Controle e pedidos do Omie vinculados à nota,
    no formato do formulário ('obra:<id>', 'empresa', 'outro:<texto>'), sem repetir."""
    vals = []
    for v in nota.vinculos_mc:
        o = v.ordem
        if o and o.centro_custo:
            for c in [c.strip() for c in o.centro_custo.split("|") if c.strip()]:
                ob = obra_por_centro_custo(c)
                val = f"obra:{ob.id}" if ob else ("empresa" if normalizar(c) == "EMPRESA" else f"outro:{c[:200]}")
                if val not in vals:
                    vals.append(val)
    for v in nota.vinculos_pedido:
        pj = v.pedido_item.pedido.projeto
        ob = Obra.query.filter_by(omie_codigo_projeto=pj).first() if pj else None
        if ob and f"obra:{ob.id}" not in vals:
            vals.append(f"obra:{ob.id}")
    return vals


def auto_obra(nota):
    """Preenche a obra da nota pelo pedido/OC vinculado, se ainda não tiver. OC do Mais Controle com mais de
    um centro de custo: a nota fica com todas as obras (cada item indica a sua na Entrada no estoque)."""
    if nota.obra_id or nota.centro_custo:
        return
    vals = sugestao_obras(nota)
    if len(vals) > 1:
        definir_rateio(nota, vals)
        return
    ob, texto, _ = sugestao_obra(nota)
    if ob:
        nota.obra = ob
    elif texto and normalizar(texto) == "EMPRESA":
        nota.centro_custo = EMPRESA
    elif texto:
        nota.centro_custo = texto[:200]   # centro de custo do Mais Controle que não é obra cadastrada


def definir_obra(nota, valor):
    """valor do formulário: 'obra:<id>', 'empresa', 'outro:<texto>' ou '' (sem definição)."""
    valor = (valor or "").strip()
    nota.obra_id, nota.centro_custo = None, None
    if valor.startswith("obra:"):
        ob = db.session.get(Obra, int(valor[5:] or 0))
        if not ob:
            raise RegraNegocio("Obra não encontrada.")
        nota.obra = ob
    elif valor == "empresa":
        nota.centro_custo = EMPRESA
    elif valor.startswith("outro:") and valor[6:].strip():
        nota.centro_custo = valor[6:].strip()[:200]


def definir_rateio(nota, valores, pcts=None):
    """Uma ou mais obras / centros de custo (valores como em definir_obra). A 1ª vira a obra principal da nota;
    com mais de uma, cada item da nota indica a sua obra na Entrada no estoque (sem rateio proporcional)."""
    from ..models import NotaRateio
    linhas = []
    for v in valores:
        v = (v or "").strip()
        if v and v not in linhas:
            linhas.append(v)
    nota.rateios.clear()
    if not linhas:
        definir_obra(nota, "")
        return
    definir_obra(nota, linhas[0])
    if len(linhas) == 1:
        for it in nota.itens:
            it.destino = None
        return
    validas = []
    for v in linhas:
        r = NotaRateio()
        if v.startswith("obra:"):
            ob = db.session.get(Obra, int(v[5:] or 0))
            if not ob:
                raise RegraNegocio("Obra não encontrada.")
            r.obra_id = ob.id
        elif v == "empresa":
            r.centro_custo = EMPRESA
        elif v.startswith("outro:") and v[6:].strip():
            r.centro_custo = v[6:].strip()[:200]
        else:
            continue
        nota.rateios.append(r)
        validas.append(r.chave)
    for it in nota.itens:  # item apontando para obra que saiu da lista volta para a 1ª
        if it.destino and it.destino not in validas:
            it.destino = None


def obras_para_escolha(atual=None):
    """Obras em andamento (as concluídas/paralisadas ficam fora da lista, exceto a já escolhida)."""
    q = Obra.query.filter(db.or_(Obra.status == "Em andamento", Obra.status.is_(None)))
    obras = q.order_by(Obra.nome).all()
    if atual is not None and atual not in obras:
        obras.insert(0, atual)
    return obras
