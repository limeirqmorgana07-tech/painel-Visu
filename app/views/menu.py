from flask import request, url_for
from flask_login import current_user

TODOS = ("admin", "almoxarife", "encarregado", "compras", "consulta")
PLANEJ = "PLANEJ"   # perfis escolhidos em Planejamento → Referências (padrão: só administrador)

# (grupo, endpoint, rótulo, perfis)
MENU = [
    # Gestão: só o resumo de todos os setores
    ("Gestão", "gerencial.sinergia|faturamento", "Faturamento gerencial", "DIRETORIA"),
    ("Gestão", "gerencial.sinergia|dre", "DRE", "DIRETORIA"),
    ("Gestão", "gerencial.sinergia|fluxo", "Fluxo de caixa", "DIRETORIA"),
    ("Gestão", "gerencial.sinergia|saldos", "Saldos bancários", "DIRETORIA"),
    ("Gestão", "gerencial.sinergia|inadimplencia-entradas", "Inadimplência · Entradas", "DIRETORIA"),
    ("Gestão", "gerencial.sinergia|inadimplencia-saidas", "Inadimplência · Saídas", "DIRETORIA"),
    ("Gestão", "gerencial.sinergia|saude-obra", "Saúde financeira por obra", "DIRETORIA"),
    ("Gestão", "gerencial.sinergia|inconsistencias", "Inconsistências", "DIRETORIA"),
    # Obras
    ("Obras", "obras.lista", "Minhas obras", TODOS),
    ("Obras", "solicitacoes.entregas", "Entregas nas obras", ("admin", "almoxarife", "encarregado")),
    ("Obras", "solicitacoes.rota", "Rota do motorista", ("admin", "almoxarife", "motorista")),
    ("Obras", "solicitacoes.quadro", "Quadro das entregas", ("admin", "almoxarife")),
    ("Obras", "rastreio.mapa", "Caminhão ao vivo", ("admin", "almoxarife")),
    # Planejamento das obras (cronograma, equipe de campo e rateio por centro de custo)
    ("Planejamento", "planejamento.cronograma", "Cronograma de obras", PLANEJ),
    ("Planejamento", "planejamento.distribuicao", "Distribuição de funcionários", PLANEJ),
    ("Planejamento", "planejamento.programacao", "Programação diária", PLANEJ),
    ("Planejamento", "planejamento.percentuais", "% do tempo por obra", PLANEJ),
    ("Planejamento", "planejamento.funcionarios", "Funcionários de obra", PLANEJ),
    ("Planejamento", "planejamento.referencias", "Referências e cores", PLANEJ),
    ("Planejamento", "planejamento.rateio", "Rateio por centro de custo", "DIRETORIA"),
    # Estoque
    ("Estoque", "main.resumo_estoque", "Resumo do estoque", TODOS),
    ("Estoque", "estoque.central", "Estoque Central", ("admin", "almoxarife", "consulta")),
    ("Estoque", "estoque.obras", "Almoxarifados e obras", ("admin", "almoxarife", "encarregado", "consulta")),
    ("Estoque", "estoque.insumos", "Insumos", TODOS),
    ("Estoque", "estoque.inventarios", "Inventários", ("admin", "almoxarife", "consulta")),
    ("Estoque", "estoque.movimentacoes", "Movimentações", ("admin", "almoxarife")),
    ("Estoque", "estoque.depositos", "Depósitos", ("admin",)),
    # Compras
    ("Compras", "solicitacoes.lista", "Solicitações", ("admin", "almoxarife", "encarregado")),
    ("Compras", "compras.lista", "Materiais a comprar", ("admin", "compras", "almoxarife", "consulta")),
    ("Compras", "cotacoes.lista", "Cotações", ("admin", "compras", "almoxarife", "consulta")),
    ("Compras", "aprovacoes.lista", "Aprovações de compra", "APROVADOR"),
    ("Compras", "notas.pedidos", "Pedidos de compra (Omie)", ("admin", "almoxarife", "compras", "consulta")),
    # Notas fiscais: produto (NF-e) e serviço (NFS-e), separadas do Financeiro
    ("Notas fiscais", "notas.lista", "Produto · notas lançadas", ("admin", "almoxarife", "compras", "consulta")),
    ("Notas fiscais", "sefaz.notas", "Produto · na SEFAZ (a lançar)", ("admin", "almoxarife", "compras", "consulta")),
    ("Notas fiscais", "nfse.recebidas", "Serviço · recebidas", "NFSE_REC"),
    ("Notas fiscais", "nfse.lista", "Serviço · emitidas", "DIRETORIA"),
    # Financeiro
    ("Financeiro", "gerencial.financeiro_painel", "Contas a pagar e receber", "DIRETORIA"),
    ("Financeiro", "fin_bi.saldos", "Saldos bancários", "DIRETORIA"),
    ("Financeiro", "fin_bi.fluxo", "Fluxo de caixa projetado", "DIRETORIA"),
    ("Financeiro", "fin_bi.ponto_equilibrio", "Ponto de equilíbrio", "DIRETORIA"),
    ("Financeiro", "fin_bi.dda", "DDA · boletos a lançar", "DDA"),
    ("Financeiro", "caixinha.inicio", "Caixinha dos encarregados", "CAIXINHA"),
    ("Financeiro", "fin_bi.lotes", "Arquivo de pagamento em lote", "DIRETORIA"),
    # BI: todos os painéis de todos os setores ficam juntos aqui (cada um com o ícone do setor)
    ("BI", "bi.comercial", "Comercial", "DIRETORIA"),
    ("BI", "fin_bi.obras", "Obras · Multiobras", "DIRETORIA"),
    ("BI", "gerencial.obra", "Obras · Visão por obra", "DIRETORIA"),
    ("BI", "gerencial.estoque", "Estoque", "DIRETORIA"),
    ("BI", "gerencial.compras", "Compras", "DIRETORIA"),
    ("BI", "fin_bi.resultado", "Financeiro · resultado e atrasos", "DIRETORIA"),
    ("BI", "bi.painel", "Financeiro e despesas", "DIRETORIA"),
    ("BI", "setores.rh", "RH / DP", "DIRETORIA"),
    ("BI", "setores.juridico", "Jurídico", "DIRETORIA"),
    # Administração
    ("Administração", "demandas.painel", "Painel de demandas", ("admin",)),
    ("Administração", "aprovacoes.configurar", "Alçadas de aprovação", ("admin",)),
    ("Administração", "bi.categorias", "Categorias de gasto", ("admin",)),
    ("Administração", "integracoes.painel", "Integrações", ("admin",)),
    ("Administração", "sefaz.certificado", "Certificado digital (A1)", ("admin",)),
    ("Administração", "notas.omie_etapas", "Omie: etapa Conferido", ("admin",)),
    ("Administração", "usuarios.lista", "Usuários e permissões", ("admin",)),
]


def menu_do_usuario():
    if not current_user.is_authenticated:
        return []
    from ..models import Compra
    atual = request.endpoint or ""
    abertas = None
    if current_user.pode("compras", "almoxarife"):
        abertas = Compra.query.filter(Compra.status.in_(["Pendente de compra", "Em cotação", "Compra autorizada"])).count()
    grupos, ordem = {}, []
    from ..services import aprovacao as aprov
    criticos = 0
    if current_user.pode("almoxarife", "compras"):
        from ..services.alertas import itens_criticos
        criticos = len(itens_criticos())
    separar = 0
    if current_user.pode("almoxarife"):
        from ..extensions import db
        from ..models import Solicitacao, SolicitacaoItem
        separar = (db.session.query(SolicitacaoItem.solicitacao_id).join(Solicitacao)
                   .filter(Solicitacao.cancelada.is_(False), SolicitacaoItem.qtd_reservada > 0,
                           db.or_(SolicitacaoItem.separado.is_(False), SolicitacaoItem.separado.is_(None)))
                   .distinct().count())
    aprovador = not current_user.simulando and (current_user.perfil_ativo == "admin" or aprov.e_aprovador(current_user))
    pend_aprov = len(aprov.pendentes_para(current_user)) if aprovador else 0
    from ..services.demandas import oculto as _dem_oculto
    esconder = {"demandas.painel"} if _dem_oculto() else set()
    if not current_user.simulando:
        esconder |= menu_oculto(current_user)
    for grupo, ep, rotulo, perfis in MENU:
        if ep in esconder:
            continue
        if _permitido(current_user, perfis, aprovador):
            if grupo not in grupos:
                grupos[grupo] = []
                ordem.append(grupo)
            ep_real, _, arg = ep.partition("|")
            if arg:
                ativo = atual == ep_real and (request.view_args or {}).get("slug") == arg
                href = url_for(ep_real, slug=arg)
            else:
                ativo = _menu_de(atual) == ep
                href = url_for(ep)
            badge = abertas if ep == "compras.lista" and abertas else None
            if ep == "aprovacoes.lista" and pend_aprov:
                badge = pend_aprov
            if ep == "estoque.central" and criticos:
                badge = criticos
            if ep == "solicitacoes.entregas" and separar:
                badge = separar
            grupos[grupo].append({"endpoint": ep, "href": href, "rotulo": rotulo, "ativo": ativo, "badge": badge,
                                  "icone": ICONE_ITEM.get(ep) if grupo == "BI" else None})
    return [(g, grupos[g]) for g in ordem]


# ícone do setor em cada painel do BI
ICONE_ITEM = {"bi.comercial": "Comercial", "gerencial.multiobras": "Obras", "fin_bi.obras": "Obras",
              "fin_bi.compras_oc": "Compras", "fin_bi.resultado": "Financeiro", "gerencial.obra": "Obras",
              "gerencial.estoque": "Estoque", "gerencial.compras": "Compras", "bi.painel": "Financeiro",
              "setores.rh": "RH / DP", "setores.juridico": "Jurídico"}


# telas internas -> item de menu que fica destacado
_ALIAS = {
    "notas.omie_etapas": "notas.omie_etapas",
    "planejamento.rateio_exportar": "planejamento.rateio",
    "caixinha.cartao": "caixinha.inicio", "caixinha.relatorio": "caixinha.inicio", "caixinha.categorias": "caixinha.inicio", "planejamento.programacao_texto": "planejamento.programacao",
    "nfse.ver_recebida": "nfse.recebidas", "nfse.recebidas": "nfse.recebidas", "nfse.ver": "nfse.lista",
    "solicitacoes.entregas": "solicitacoes.entregas", "solicitacoes.rota": "solicitacoes.rota", "solicitacoes.quadro": "solicitacoes.quadro",
    "obras.classificar": "obras.lista",
    "estoque.entrada": "estoque.central", "estoque.inventario": "estoque.central",
    "estoque.transferencia": "estoque.central",
    "estoque.deposito": "estoque.obras", "estoque.consumo": "estoque.obras",
    "estoque.insumo": "estoque.insumos", "estoque.insumo_form": "estoque.insumos",
    "estoque.deposito_editar": "estoque.depositos",
    "estoque.inventario_ver": "estoque.inventarios", "estoque.inventario_novo": "estoque.inventarios",
    "aprovacoes.configurar": "aprovacoes.configurar",
    "gerencial.fornecedor": "gerencial.compras", "fin_bi.compras_oc": "gerencial.compras", "gerencial.financeiro": "gerencial.financeiro_painel",
    "bi.gastos": "bi.painel", "bi.categorias": "bi.categorias", "bi.comercial": "bi.comercial",
    "notas.pedidos": "notas.pedidos",
    "fin_bi.obra": "fin_bi.obras", "fin_bi.lote": "fin_bi.lotes", "fin_bi.atrasos": "fin_bi.resultado", "fin_bi.fluxo_detalhe": "fin_bi.fluxo",
    "fin_bi.dda_boleto": "fin_bi.dda", "fin_bi.inicio": "fin_bi.fluxo", "gerencial.multiobras": "fin_bi.obras",
}


def _menu_de(endpoint):
    if endpoint in _ALIAS:
        return _ALIAS[endpoint]
    bp = endpoint.split(".")[0]
    padrao = {"obras": "obras.lista", "solicitacoes": "solicitacoes.lista", "compras": "compras.lista",
              "usuarios": "usuarios.lista", "integracoes": "integracoes.painel", "aprovacoes": "aprovacoes.lista",
              "notas": "notas.lista", "cotacoes": "cotacoes.lista", "bi": "bi.painel", "nfse": "nfse.lista"}
    return padrao.get(bp, endpoint)



# ---------------------------------------------------------------- acessos recentes (Início)

_ENDPOINTS_MENU = None


def _endpoints_menu():
    global _ENDPOINTS_MENU
    if _ENDPOINTS_MENU is None:
        _ENDPOINTS_MENU = {ep.partition("|")[0] for _, ep, _, _ in MENU}
    return _ENDPOINTS_MENU


def chave_acesso(endpoint, view_args):
    """Telas do menu (e as Sinergia por slug) contam como acesso; o resto (detalhes, ações) não."""
    if not endpoint or endpoint not in _endpoints_menu():
        return None
    if endpoint == "gerencial.sinergia" and (view_args or {}).get("slug"):
        return f"{endpoint}|{view_args['slug']}"
    return endpoint


def registrar_acesso(usuario, chave):
    from ..extensions import db
    from ..models import AcessoRecente, agora
    try:
        a = AcessoRecente.query.filter_by(usuario_id=usuario.id, endpoint=chave).first()
        if not a:
            a = AcessoRecente(usuario_id=usuario.id, endpoint=chave, contagem=0)
            db.session.add(a)
        a.contagem = (a.contagem or 0) + 1
        a.ultimo_em = agora()
        db.session.commit()
    except Exception:  # noqa: BLE001 — nunca atrapalha a tela
        db.session.rollback()


def acessos_do_usuario(usuario, limite=8):
    """(recentes, sugestoes): telas do menu que o usuário abriu por último (só as que ele ainda pode ver) e,
    para quem está começando, sugestões do próprio menu."""
    from ..models import AcessoRecente
    itens = {}
    for grupo, lst in menu_do_usuario():
        for it in lst:
            itens[it["endpoint"]] = dict(it, grupo=grupo)
    recentes = []
    for a in (AcessoRecente.query.filter_by(usuario_id=usuario.id)
              .order_by(AcessoRecente.ultimo_em.desc()).limit(40)):
        it = itens.get(a.endpoint)
        if it and it not in recentes:
            recentes.append(dict(it, vezes=a.contagem, quando=a.ultimo_em))
        if len(recentes) >= limite:
            break
    sugestoes = []
    if len(recentes) < 4:
        usados = {r["endpoint"] for r in recentes}
        vistos_grupo = set()
        for ep, it in itens.items():
            if ep in usados or it["grupo"] in vistos_grupo or it["grupo"] == "Administração":
                continue
            vistos_grupo.add(it["grupo"])
            sugestoes.append(it)
            if len(sugestoes) + len(recentes) >= 6:
                break
    return recentes, sugestoes



# ---------------------------------------------------------------- menu por usuário (Administração)

FIXOS = {"usuarios.lista"}   # nunca some do menu do administrador (para não se trancar fora)


def _permitido(u, perfis, aprovador=None):
    """O perfil do usuário dá acesso a este item do menu?"""
    if perfis == "DDA":
        from .financeiro_bi import pode_dda
        return pode_dda(u)
    if perfis == "NFSE_REC":
        from .gerencial import e_diretoria
        return e_diretoria(u) or u.tem_perfil(("compras", "consulta"))
    if perfis == "CAIXINHA":
        from .caixinha import pode_ver_menu
        return pode_ver_menu(u)
    if perfis == "PLANEJ":
        from .planejamento import pode_ver
        return pode_ver(u)
    if perfis == "DIRETORIA":
        from .gerencial import e_diretoria
        return e_diretoria(u) and not getattr(u, "simulando", None)
    if perfis == "APROVADOR":
        if aprovador is not None:
            return aprovador
        from ..services import aprovacao as aprov
        return u.perfil_ativo == "admin" or aprov.e_aprovador(u)
    return u.tem_perfil(perfis)


def menu_oculto(u):
    """Itens do menu escondidos para este usuário pelo administrador."""
    import json
    try:
        return set(json.loads(getattr(u, "menu_oculto", None) or "[]")) - FIXOS
    except (ValueError, TypeError):
        return set()


def salvar_menu_oculto(u, endpoints):
    import json
    validos = {ep for _, ep, _, _ in MENU}
    u.menu_oculto = json.dumps(sorted((set(endpoints) & validos) - FIXOS))


def itens_do_perfil(u):
    """[(grupo, [(endpoint, rótulo, permitido_pelo_perfil, oculto)])] — para a tela de configuração."""
    oculto = menu_oculto(u)
    grupos, ordem = {}, []
    for grupo, ep, rotulo, perfis in MENU:
        if grupo not in grupos:
            grupos[grupo] = []
            ordem.append(grupo)
        grupos[grupo].append({"endpoint": ep, "rotulo": rotulo, "permitido": _permitido(u, perfis),
                              "oculto": ep in oculto, "fixo": ep in FIXOS})
    return [(g, grupos[g]) for g in ordem]


def bloqueado(u, endpoint, view_args):
    """A tela foi escondida do menu deste usuário? (abrir pelo endereço também fica bloqueado)"""
    if not endpoint or getattr(u, "simulando", None):
        return False
    oc = menu_oculto(u)
    if not oc:
        return False
    if endpoint in oc:
        return True
    if endpoint == "gerencial.sinergia" and f"{endpoint}|{(view_args or {}).get('slug')}" in oc:
        return True
    return False
