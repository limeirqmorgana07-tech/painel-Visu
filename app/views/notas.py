from datetime import date

import os
import uuid

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from .. import perfil_requerido
from ..extensions import db
from ..models import Obra, Compra, NotaFiscal, NotaItem, NotaOrdemMC, NotaPedidoItem, NotaParcela, PedidoERP, PedidoERPItem, fmt_cnpj
from ..services import estoque as est
from ..services import nfe
from ..services import pedidos_erp as ped

bp = Blueprint("notas", __name__, url_prefix="/notas")
PERFIS = ("almoxarife", "compras", "consulta")


@bp.route("/")
@perfil_requerido(*PERFIS)
def lista():
    q = NotaFiscal.query
    texto = request.args.get("q", "").strip()
    if texto:
        like = f"%{texto}%"
        dig = "".join(ch for ch in texto if ch.isdigit())
        conds = [NotaFiscal.emitente_nome.ilike(like), NotaFiscal.numero.ilike(like)]
        if dig:
            conds.append(NotaFiscal.numero == dig.lstrip("0"))
            if len(dig) >= 8:
                conds += [NotaFiscal.emitente_cnpj.ilike(f"%{dig}%"), NotaFiscal.chave.ilike(f"%{dig}%")]
        q = q.filter(db.or_(*conds))
    emp_f = request.args.get("empresa", "")
    if emp_f == "sem":
        q = q.filter(NotaFiscal.destinatario_cnpj.is_(None))
    elif emp_f.isdigit():
        from ..models import Empresa
        e = db.session.get(Empresa, int(emp_f))
        if e:
            q = q.filter(NotaFiscal.destinatario_cnpj == e.cnpj)
    obra_f = request.args.get("obra", "")
    if obra_f == "sem":
        q = q.filter(NotaFiscal.obra_id.is_(None), NotaFiscal.centro_custo.is_(None))
    elif obra_f == "empresa":
        q = q.filter(NotaFiscal.obra_id.is_(None), NotaFiscal.centro_custo.isnot(None))
    elif obra_f.isdigit():
        q = q.filter(NotaFiscal.obra_id == int(obra_f))
    notas = q.order_by(NotaFiscal.emissao.desc().nullslast(), NotaFiscal.id.desc()).limit(300).all()
    hoje = date.today()
    vencidas = (NotaParcela.query.filter(NotaParcela.pago_em.is_(None), NotaParcela.vencimento < hoje)
                .order_by(NotaParcela.vencimento).all())
    return render_template("notas/lista.html", notas=notas, texto=texto, vencidas=vencidas, hoje=hoje,
                           obras=Obra.query.order_by(Obra.nome).all(), obra_f=obra_f,
                           empresas=nfe._empresas(), emp_f=emp_f)


def _pasta_previa():
    p = os.path.join(current_app.instance_path, "nf_previa")
    os.makedirs(p, exist_ok=True)
    return p


@bp.route("/nova", methods=["GET", "POST"])
@perfil_requerido("almoxarife", "compras")
def nova():
    """Passo 1: lê a chave/XML e mostra a PRÉ-VISUALIZAÇÃO. Nada é gravado até confirmar."""
    if request.method == "POST":
        arq = request.files.get("xml")
        xml = arq.read() if arq and arq.filename else None
        r = _previa(xml, request.form.get("chave"), request.form.get("obra") or "")
        if r is not None:
            return r
    return render_template("notas/nova.html", obras=ped.obras_para_escolha(), centros_usados=_centros_usados())


@bp.route("/nova/sefaz/<int:rid>")
@perfil_requerido("almoxarife", "compras")
def nova_sefaz(rid):
    """Lança uma NF-e que veio da SEFAZ: mesma pré-visualização, já com o XML completo."""
    from ..models import NFeRecebida
    n = db.get_or_404(NFeRecebida, rid)
    if not n.xml:
        flash("O XML completo desta nota ainda não chegou da SEFAZ (aguardando a Ciência da Operação). "
              "Pode lançar só pela chave, e o XML completa depois.", "warning")
    r = _previa(n.xml.encode("utf-8") if n.xml else None, n.chave, "")
    return r if r is not None else redirect(url_for("sefaz.notas"))


def _previa(xml, chave_form, obra):
    """Monta a pré-visualização (nada é gravado). Devolve a página ou None se deu erro (com aviso)."""
    if True:
        try:
            dados = nfe.ler_xml(xml) if xml else None
            chave = chave_form or (dados or {}).get("chave")
            info = nfe.ler_chave(chave)
            if dados and dados["chave"] != info["chave"]:
                raise nfe.RegraNegocio("O XML enviado é de outra nota (a chave não confere com a lida no código de barras).")
            token = None
            if xml:
                token = uuid.uuid4().hex + ".xml"
                with open(os.path.join(_pasta_previa(), token), "wb") as fh:
                    fh.write(xml)
            ident = nfe.identificar_empresa(info["chave"], dados, obra)
            session["nf_previa"] = {"chave": info["chave"], "token": token, "obra": obra}
            existente = NotaFiscal.query.filter_by(chave=info["chave"]).first()
            # nota "de mentira" (não vai para o banco) só para sugerir pedido/OC na prévia
            tmp = NotaFiscal(chave=info["chave"], emitente_cnpj=info["emitente_cnpj"],
                             emitente_nome=(dados or {}).get("emitente_nome"),
                             destinatario_cnpj=(dados or {}).get("destinatario_cnpj"),
                             valor_total=(dados or {}).get("valor_total"), emissao=(dados or {}).get("emissao"))
            if not tmp.destinatario_cnpj and ident["empresa"]:
                tmp.destinatario_cnpj = ident["empresa"].cnpj
            ocs = ped.sugerir_ordens_mc(tmp, limite=5) if (dados and ped.empresa_da_nota(tmp) != "omie") else []
            pcs = [p for p in ped.pedidos_abertos() if p.fornecedor_cnpj and p.fornecedor_cnpj == info["emitente_cnpj"]][:5]
            db.session.expunge(tmp) if tmp in db.session else None
            return render_template("notas/previa.html", info=info, dados=dados, existente=existente,
                                   cnpj=fmt_cnpj(info["emitente_cnpj"]), obras=ped.obras_para_escolha(), centros_usados=_centros_usados(),
                                   obra_sel=obra, ocs=ocs, pcs=pcs, ident=ident, empresas=nfe._empresas(),
                                   condicao=nfe.condicao_pagamento(dados["emissao"], dados["parcelas"]) if dados else None)
        except nfe.RegraNegocio as e:
            flash(str(e), "danger")
    return None


@bp.route("/nova/confirmar", methods=["POST"])
@perfil_requerido("almoxarife", "compras")
def confirmar_nova():
    """Passo 2: grava a nota que foi pré-visualizada."""
    prev = session.pop("nf_previa", None)
    if not prev:
        flash("A pré-visualização expirou. Leia a nota de novo.", "warning")
        return redirect(url_for("notas.nova"))
    xml, caminho = None, None
    if prev.get("token"):
        caminho = os.path.join(_pasta_previa(), os.path.basename(prev["token"]))
        if os.path.exists(caminho):
            xml = open(caminho, "rb").read()
    try:
        nota, criada = nfe.registrar(current_user, chave=prev["chave"], xml_bytes=xml)
        emp_id = request.form.get("empresa_id", type=int)
        if emp_id and not nota.tem_xml:
            from ..models import Empresa
            nfe.definir_empresa(nota, db.session.get(Empresa, emp_id))
        obra = request.form.get("obra", prev.get("obra"))
        if obra:
            ped.definir_obra(nota, obra)
        db.session.commit()
        flash(("Nota registrada." if criada else "Nota já existia — dados completados.")
              + ("" if nota.tem_xml else " Envie o XML para trazer itens, valores e parcelas.")
              + " Confira abaixo o pedido de compra desta nota.", "success")
        _omie_conferir(nota)
        return redirect(url_for("notas.detalhe", nid=nota.id))
    except nfe.RegraNegocio as e:
        db.session.rollback()
        flash(str(e), "danger")
        return redirect(url_for("notas.nova"))
    finally:
        if caminho and os.path.exists(caminho):
            os.remove(caminho)


@bp.route("/<int:nid>", methods=["GET", "POST"])
@perfil_requerido(*PERFIS)
def detalhe(nid):
    nota = db.get_or_404(NotaFiscal, nid)
    if request.method == "POST" and current_user.pode("almoxarife", "compras") and request.form.get("acao") == "empresa":
        from ..models import Empresa
        e = db.session.get(Empresa, request.form.get("empresa_id", type=int) or 0)
        if nota.tem_xml:
            flash("A empresa desta nota vem do XML (CNPJ do destinatário) e não pode ser trocada.", "warning")
        elif e:
            nfe.definir_empresa(nota, e)
            db.session.commit()
            flash(f"Nota marcada como da {e.nome}.", "success")
        return redirect(url_for("notas.detalhe", nid=nota.id))
    if request.method == "POST" and current_user.pode("almoxarife", "compras"):
        arq = request.files.get("xml")
        try:
            nfe.registrar(current_user, chave=nota.chave, xml_bytes=arq.read() if arq and arq.filename else None)
            db.session.commit()
            flash("XML incluído: itens, valores e parcelas atualizados.", "success")
        except nfe.RegraNegocio as e:
            db.session.rollback()
            flash(str(e), "danger")
        return redirect(url_for("notas.detalhe", nid=nota.id))
    sefaz_rec = None
    if not nota.tem_xml:
        from ..models import NFeRecebida
        antes = (nota.emitente_nome, nota.valor_total, nota.emissao)
        r = nfe.completar_pela_sefaz(nota, current_user, buscar_nome=not nota.emitente_nome)
        if r == "xml":
            db.session.commit()
            flash("O XML desta nota chegou da SEFAZ: itens, valores e parcelas foram preenchidos.", "success")
            return redirect(url_for("notas.detalhe", nid=nota.id))
        if (nota.emitente_nome, nota.valor_total, nota.emissao) != antes:
            db.session.commit()
        sefaz_rec = NFeRecebida.query.filter_by(chave=nota.chave).first()
        if not nota.destinatario_cnpj:
            ident = nfe.identificar_empresa(nota.chave, obra=nota.obra_id)
            if ident["empresa"] and ident["certo"]:
                nfe.definir_empresa(nota, ident["empresa"])
                db.session.commit()
    compras = Compra.query.filter_by(nota_id=nota.id).all()
    empresa = ped.empresa_da_nota(nota)
    todos = request.args.get("todos") == "1"
    pedidos, mesmo_forn, pre = ([], False, {})
    if empresa in ("omie", None):
        pedidos, mesmo_forn, pre = ped.sugerir(nota, todos=todos)
    ocs = []
    busca_oc = request.args.get("oc", "").strip()
    if empresa in ("maiscontrole", None) or busca_oc:
        ocs = ped.sugerir_ordens_mc(nota, busca=busca_oc or None)
    return render_template("notas/detalhe.html", nota=nota, compras=compras, cnpj=fmt_cnpj(nota.emitente_cnpj),
                           hoje=date.today(), empresa=empresa, pedidos=pedidos, mesmo_forn=mesmo_forn, pre=pre,
                           todos=todos, ocs=ocs, busca_oc=busca_oc, ult_ped=ped.ultima_atualizacao(),
                           atualizando=ped.em_andamento(), tem_pedidos=PedidoERP.query.first() is not None,
                           insumo_de=lambda it: ped.resolver_insumo(it, criar=False),
                           obras=ped.obras_para_escolha(nota.obra), centros_usados=_centros_usados(), sug_obra=ped.sugestao_obra(nota),
                           sug_obras=ped.sugestao_obras(nota),
                           depositos=_depositos_entrada(nota), cot_info=_cotacoes_nota(nota), sefaz_rec=sefaz_rec,
                           entrada=_linhas_entrada(nota),
                           ident=(nfe.identificar_empresa(nota.chave, obra=nota.obra_id) if not nota.destinatario_cnpj else None),
                           empresas=nfe._empresas())


def _cotacoes_nota(nota):
    from ..services import cotacoes as cs
    try:
        return cs.cotacoes_da_nota(nota)
    except Exception:  # a comparação é informativa: nunca impede abrir a nota
        current_app.logger.exception("Falha ao comparar cotação da nota %s", nota.id)
        return {"mc": [], "linhas": [], "cotacoes": []}


def _centros_usados():
    """Centros de custo digitados antes (fora das obras), para aparecerem na busca."""
    return [c for (c,) in db.session.query(NotaFiscal.centro_custo).filter(
        NotaFiscal.obra_id.is_(None), NotaFiscal.centro_custo.isnot(None), NotaFiscal.centro_custo != "Empresa")
        .distinct().order_by(NotaFiscal.centro_custo).limit(200)]


def _linhas_entrada(nota):
    """Para a seção "Entrada no estoque": cada item com o insumo sugerido, quanto já entrou e o local padrão."""
    from ..models import Movimentacao
    deps = _depositos_entrada(nota)
    padrao = deps[1] if len(deps) > 1 and nota.obra and nota.obra.deposito is deps[1] else deps[0]
    linhas = []
    varias = len(nota.rateios) > 1
    for ni in nota.itens:
        ins, motivo = nfe.sugerir_insumo(ni, nota)
        feito = nfe.ja_entrou(ni)
        chave = nota.destino_item(ni) if varias else None
        linhas.append({"ni": ni, "insumo": ins, "motivo": motivo, "feito": feito, "obra": chave,
                       "dep": _deposito_da_chave(chave, deps[0]) if varias else padrao,
                       "resta": max(0.0, (ni.quantidade or 0) - feito)})
    movs = (Movimentacao.query.filter(Movimentacao.nota_id == nota.id, Movimentacao.tipo == "entrada")
            .order_by(Movimentacao.id).all())
    obras_nota = [(r.chave, r.label, _deposito_da_chave(r.chave, deps[0]).id) for r in nota.rateios] if varias else []
    return {"linhas": linhas, "deps": deps, "padrao": padrao, "movs": movs, "obras": obras_nota,
            "pendente": any(l["resta"] > 1e-6 for l in linhas)}


def _depositos_entrada(nota):
    from ..models import Deposito
    central = est.deposito_central()
    deps = [central]
    obras = [r.obra for r in nota.rateios if r.obra] if len(nota.rateios) > 1 else ([nota.obra] if nota.obra else [])
    for ob in obras:
        if ob.deposito and ob.deposito not in deps:
            deps.append(ob.deposito)
    deps += [d for d in Deposito.query.filter(Deposito.tipo == "almoxarifado").order_by(Deposito.nome) if d not in deps]
    return deps


def _deposito_da_chave(chave, central):
    """Local padrão do item: depósito da obra indicada (ou o Estoque Central)."""
    from ..models import Obra
    if chave and chave.startswith("obra:"):
        ob = db.session.get(Obra, int(chave[5:] or 0))
        if ob and ob.deposito:
            return ob.deposito
    return central


@bp.route("/<int:nid>/entrada-estoque", methods=["POST"])
@perfil_requerido("almoxarife", "compras")
def entrada_estoque(nid):
    """Dá entrada no estoque direto pelos itens da nota (como o Recebimento de NF-e do Omie)."""
    from ..models import Deposito, Insumo
    nota = db.get_or_404(NotaFiscal, nid)
    f = request.form
    linhas = []
    chaves = [r.chave for r in nota.rateios] if len(nota.rateios) > 1 else []
    for ni in nota.itens:
        if chaves and f.get(f"obra_item_{ni.id}") in chaves:
            ni.destino = f.get(f"obra_item_{ni.id}")
        if not f.get(f"entrar_{ni.id}"):
            continue
        # insumo escolhido na lista tem prioridade; sem escolha, "novo" cadastra com o nome do item da nota
        ins = db.session.get(Insumo, f.get(f"insumo_{ni.id}", type=int) or 0) or ("novo" if f.get(f"novo_{ni.id}") else None)
        dep = db.session.get(Deposito, f.get(f"dep_{ni.id}", type=int) or 0)
        linhas.append((ni, ins, (f.get(f"qtd_{ni.id}") or "").replace(",", "."), dep))
    try:
        pulados = []
        n = nfe.dar_entrada(nota, linhas, current_user, pulados)
        db.session.commit()
        flash(f"{n} item(ns) da nota entraram no estoque.", "success")
        if pulados:
            flash("Ficaram para depois (falta escolher o insumo na lista ou marcar “cadastrar como novo insumo”): "
                  + "; ".join(pulados) + ".", "warning")
    except est.RegraNegocio as e:
        db.session.rollback()
        if chaves:  # guarda a obra escolhida para cada item mesmo se a entrada falhou
            for ni in nota.itens:
                if f.get(f"obra_item_{ni.id}") in chaves:
                    ni.destino = f.get(f"obra_item_{ni.id}")
            db.session.commit()
        flash(str(e), "danger")
        return redirect(url_for("notas.detalhe", nid=nid) + "#estoque")
    # F. Diniz: reflete no Omie (conclui o Recebimento da NF-e: estoque + contas a pagar lá)
    from ..services import omie_receb
    if omie_receb.aplicavel(nota):
        ok, msg = omie_receb.enviar(nota, current_user)
        db.session.commit()
        flash(("Omie: " + msg), "success" if ok else "warning")
    return redirect(url_for("notas.detalhe", nid=nid) + "#estoque")


def _omie_conferir(nota):
    """F. Diniz: ao lançar a nota (ou trocar a obra), põe o card do Omie em Conferido com o centro de custo."""
    from ..services import omie_receb
    if not omie_receb.aplicavel(nota) or omie_receb.modo() != "conferido" or nota.omie_concluido:
        return
    ok, msg = omie_receb.enviar(nota, current_user)
    db.session.commit()
    flash("Omie: " + msg, "success" if ok else "warning")


@bp.route("/<int:nid>/omie-departamento", methods=["POST"])
@perfil_requerido("almoxarife", "compras")
def omie_departamento(nid):
    """Liga a obra / centro de custo da nota a um departamento do Omie (fica salvo para as próximas notas)."""
    from ..services import omie_receb
    nota = db.get_or_404(NotaFiscal, nid)
    n = 0
    for nome, cod in zip(request.form.getlist("obra_nome"), request.form.getlist("departamento")):
        if cod.strip() and nome.strip():
            omie_receb.vincular_departamento(nota, cod.strip(), nome.strip())
            n += 1
    cod = (request.form.get("departamento") or "").strip()
    if not request.form.getlist("obra_nome") and cod and nota.centro_custo_label:
        omie_receb.vincular_departamento(nota, cod)
        n += 1
    if n:
        db.session.commit()
        flash(f"Departamento do Omie salvo ({n}). Vale também para as próximas notas dessas obras.", "success")
        _omie_conferir(nota)
    return redirect(url_for("notas.detalhe", nid=nid) + "#estoque")


@bp.route("/omie/etapas", methods=["GET", "POST"])
@perfil_requerido()
def omie_etapas():
    """Configuração: modo (Conferido x Concluir) e código da etapa Conferido no Omie."""
    from ..models import Configuracao, Empresa
    from ..services import omie_receb
    from ..services.omie import OmieErro
    emp = Empresa.query.filter_by(sistema="omie").first()
    etapas, erro = [], None
    if request.method == "POST":
        acao = request.form.get("acao")
        if acao == "salvar":
            Configuracao.definir("omie_receb_modo_v2", "concluir" if request.form.get("modo") == "concluir" else "conferido")
            Configuracao.definir("omie_etapa_conferido", (request.form.get("etapa") or "").strip()[:2])
            db.session.commit()
            flash("Configuração do Omie salva.", "success")
        elif acao == "departamentos" and emp:
            try:
                n = omie_receb.atualizar_departamentos(emp)
                flash(f"{n} departamento(s) copiados do Omie.", "success")
            except Exception as e:  # noqa: BLE001
                db.session.rollback()
                flash(f"Não consegui buscar os departamentos: {e}", "danger")
        return redirect(url_for("notas.omie_etapas", ver=request.form.get("ver")))
    if emp and request.args.get("ver"):
        try:
            etapas = omie_receb.etapas_em_uso(emp)
        except (OmieErro, Exception) as e:  # noqa: BLE001
            erro = str(e)[:300]
    return render_template("notas/omie_etapas.html", emp=emp, etapas=etapas, erro=erro, modo=omie_receb.modo(),
                           etapa=omie_receb.etapa_conferido() or "",
                           deps=omie_receb.departamentos(emp) if emp else [])


@bp.route("/<int:nid>/omie", methods=["POST"])
@perfil_requerido("almoxarife", "compras")
def enviar_omie(nid):
    from ..services import omie_receb
    nota = db.get_or_404(NotaFiscal, nid)
    ok, msg = omie_receb.enviar(nota, current_user)
    db.session.commit()
    flash("Omie: " + msg, "success" if ok else "warning")
    return redirect(url_for("notas.detalhe", nid=nid) + "#estoque")


@bp.route("/<int:nid>/obra", methods=["POST"])
@perfil_requerido("almoxarife", "compras")
def definir_obra(nid):
    nota = db.get_or_404(NotaFiscal, nid)
    try:
        if request.form.get("usar") == "todas":
            ped.definir_rateio(nota, ped.sugestao_obras(nota))
        elif request.form.get("usar"):
            ped.definir_rateio(nota, [request.form.get("usar")])
        else:
            ped.definir_rateio(nota, request.form.getlist("obra"))
        db.session.commit()
        if len(nota.rateios) > 1:
            flash("Obras da nota: " + " + ".join(r.label for r in nota.rateios)
                  + ". Indique a obra de cada item em Entrada no estoque.", "success")
        else:
            flash(f"Obra / centro de custo da nota: {nota.centro_custo_label or 'não definido'}.", "success")
        _omie_conferir(nota)
    except est.RegraNegocio as e:
        db.session.rollback()
        flash(str(e), "danger")
    return redirect(url_for("notas.detalhe", nid=nid))


@bp.route("/<int:nid>/vincular-pedidos", methods=["POST"])
@perfil_requerido("almoxarife", "compras")
def vincular_pedidos(nid):
    nota = db.get_or_404(NotaFiscal, nid)
    f = request.form
    linhas = []
    for iid in f.getlist("item_id", type=int):
        if not f.get(f"usar_{iid}"):
            continue
        it = db.session.get(PedidoERPItem, iid)
        if not it:
            continue
        ni = db.session.get(NotaItem, f.get(f"nota_item_{iid}", type=int) or 0)
        linhas.append((it, (f.get(f"qtd_{iid}") or "0").replace(",", "."), ni if ni and ni.nota_id == nota.id else None,
                       bool(f.get(f"entrar_{iid}"))))
    try:
        from ..models import Deposito
        dep = db.session.get(Deposito, f.get("deposito_id", type=int) or 0)
        feitos, entradas = ped.vincular(nota, linhas, current_user, dar_entrada=bool(f.get("dar_entrada")), deposito=dep)
        db.session.commit()
        flash(f"{feitos} item(ns) de pedido vinculado(s) à nota."
              + (f" {entradas} entrada(s) lançada(s) em {(dep or est.deposito_central()).nome}." if entradas else ""), "success")
    except est.RegraNegocio as e:
        db.session.rollback()
        flash(str(e), "danger")
    return redirect(url_for("notas.detalhe", nid=nid))


@bp.route("/vinculo/<int:vid>/desfazer", methods=["POST"])
@perfil_requerido("almoxarife", "compras")
def desfazer_vinculo(vid):
    v = db.get_or_404(NotaPedidoItem, vid)
    nid = v.nota_id
    try:
        ped.desfazer(v, current_user, "Vínculo com pedido de compra desfeito")
        db.session.commit()
        flash("Vínculo desfeito" + (" e entrada estornada." if v.movimentacao_id else "."), "success")
    except est.RegraNegocio as e:
        db.session.rollback()
        flash(str(e), "danger")
    return redirect(url_for("notas.detalhe", nid=nid))


@bp.route("/<int:nid>/vincular-ocs", methods=["POST"])
@perfil_requerido("almoxarife", "compras")
def vincular_ocs(nid):
    nota = db.get_or_404(NotaFiscal, nid)
    try:
        n = ped.vincular_ordens_mc(nota, request.form.getlist("oc"), current_user)
        db.session.commit()
        flash(f"{n} ordem(ns) de compra do Mais Controle vinculada(s) à nota.", "success")
    except est.RegraNegocio as e:
        db.session.rollback()
        flash(str(e), "danger")
    return redirect(url_for("notas.detalhe", nid=nid))


@bp.route("/vinculo-oc/<int:vid>/desfazer", methods=["POST"])
@perfil_requerido("almoxarife", "compras")
def desfazer_oc(vid):
    v = db.get_or_404(NotaOrdemMC, vid)
    nid = v.nota_id
    db.session.delete(v)
    db.session.commit()
    flash(f"OC {v.ordem_numero} desvinculada.", "success")
    return redirect(url_for("notas.detalhe", nid=nid))


@bp.route("/<int:nid>/excluir", methods=["GET", "POST"])
@perfil_requerido("almoxarife", "compras")  # administrador, almoxarifado e compras
def excluir(nid):
    nota = db.get_or_404(NotaFiscal, nid)
    if request.method == "POST":
        try:
            r = ped.excluir_nota(nota, current_user, request.form.get("motivo"))
            db.session.commit()
            flash(f"Nota excluída. {r['estornos']} entrada(s) de estoque estornada(s)"
                  + (f", {r['compras']} recebimento(s) de Materiais a Comprar desfeito(s)" if r["compras"] else "")
                  + ". Se ela também foi lançada no Omie ou no Mais Controle, exclua lá também.", "success")
            return redirect(url_for("notas.lista"))
        except est.RegraNegocio as e:
            db.session.rollback()
            flash("Não foi possível excluir: " + str(e), "danger")
    from ..models import Movimentacao
    movs = Movimentacao.query.filter_by(nota_id=nota.id, tipo="entrada").filter(Movimentacao.estornada_em.is_(None)).all()
    return render_template("notas/excluir.html", nota=nota, movs=movs,
                           compras=Compra.query.filter_by(nota_id=nota.id).all())


@bp.route("/pedidos")
@perfil_requerido(*PERFIS)
def pedidos():
    ver = request.args.get("ver", "abertos")
    texto = request.args.get("q", "").strip()
    q = PedidoERP.query
    if texto:
        like = f"%{texto}%"
        q = q.filter(db.or_(PedidoERP.numero.ilike(like), PedidoERP.fornecedor_nome.ilike(like),
                            PedidoERP.fornecedor_cnpj.ilike(f"%{nfe.limpar_chave(texto) or texto}%")))
    lista = q.order_by(PedidoERP.emissao.desc().nullslast(), PedidoERP.id.desc()).limit(500).all()
    if ver == "abertos":
        lista = [p for p in lista if p.qtd_pendente > 1e-9]
    return render_template("notas/pedidos.html", pedidos=lista, ver=ver, texto=texto, ult=ped.ultima_atualizacao(),
                           atualizando=ped.em_andamento())


@bp.route("/pedidos/atualizar", methods=["POST"])
@perfil_requerido("compras", "almoxarife")
def atualizar_pedidos():
    from ..services.financeiro import credenciais
    from ..models import Empresa
    emp = Empresa.query.filter_by(sistema="omie").first()
    if not emp or not credenciais(emp):
        flash("Credenciais do Omie não configuradas no Render (OMIE_FDINIZ_APP_KEY / OMIE_FDINIZ_APP_SECRET).", "danger")
    elif ped.disparar(current_app._get_current_object(), current_user.nome):
        flash("Buscando os pedidos de compra no Omie. Leva de alguns segundos a poucos minutos — recarregue a página.", "info")
    else:
        flash("A atualização dos pedidos já está em andamento.", "info")
    return redirect(request.referrer or url_for("notas.pedidos"))


@bp.route("/parcela/<int:pid>/pagar", methods=["POST"])
@perfil_requerido("compras", "consulta")
def pagar(pid):
    p = db.get_or_404(NotaParcela, pid)
    if p.pago_em:
        p.pago_em, p.pago_por = None, None
        flash("Baixa desfeita.", "info")
    else:
        p.pago_em, p.pago_por = date.today(), current_user.nome
        flash("Parcela marcada como paga.", "success")
    db.session.commit()
    return redirect(request.referrer or url_for("notas.detalhe", nid=p.nota_id))


@bp.route("/api/ler-arquivo", methods=["POST"])
@login_required
def api_ler_arquivo():
    """Foto do código de barras ou PDF do DANFE -> chave (leitura feita no servidor)."""
    arq = request.files.get("arquivo")
    if not arq or not arq.filename:
        return jsonify({"ok": False, "erro": "Escolha a foto ou o PDF do DANFE."})
    try:
        return jsonify({"ok": True, "chave": nfe.chave_de_arquivo(arq.read(), arq.filename)})
    except nfe.RegraNegocio as e:
        return jsonify({"ok": False, "erro": str(e)})
    except Exception:
        current_app.logger.exception("Falha ao ler arquivo do DANFE")
        return jsonify({"ok": False, "erro": "Não foi possível ler este arquivo. Tente outra foto ou o PDF."})


@bp.route("/api/chave")
@login_required
def api_chave():
    try:
        info = nfe.ler_chave(request.args.get("c", ""))
    except nfe.RegraNegocio as e:
        return jsonify({"ok": False, "erro": str(e)})
    nota = NotaFiscal.query.filter_by(chave=info["chave"]).first()
    ident = nfe.identificar_empresa(info["chave"])
    e = ident["empresa"]
    info.update(ok=True, cnpj=fmt_cnpj(info["emitente_cnpj"]),
                empresa=(e.nome if e else None), empresa_certa=ident["certo"], empresa_motivo=ident["motivo"],
                existente={"id": nota.id, "fornecedor": nota.fornecedor, "tem_xml": nota.tem_xml,
                           "valor": nota.valor_total} if nota else None)
    return jsonify(info)


@bp.route("/<int:nid>/danfe.pdf")
@perfil_requerido(*PERFIS)
def danfe(nid):
    nota = db.get_or_404(NotaFiscal, nid)
    xml = nota.xml
    if not xml:
        from ..models import NFeRecebida
        rec = NFeRecebida.query.filter_by(chave=nota.chave).first()
        xml = rec.xml if rec else None
    if not xml:
        flash("Esta nota ainda não tem XML; sem ele não dá para gerar o DANFE.", "warning")
        return redirect(url_for("notas.detalhe", nid=nid))
    return nfe.resposta_danfe(xml, nota.chave)


@bp.route("/<int:nid>/nota.xml")
@perfil_requerido(*PERFIS)
def baixar_xml(nid):
    nota = db.get_or_404(NotaFiscal, nid)
    xml = nota.xml
    if not xml:
        from ..models import NFeRecebida
        rec = NFeRecebida.query.filter_by(chave=nota.chave).first()
        xml = rec.xml if rec else None
    if not xml:
        flash("Esta nota ainda não tem XML.", "warning")
        return redirect(url_for("notas.detalhe", nid=nid))
    return nfe.resposta_xml(xml, nota.chave)
