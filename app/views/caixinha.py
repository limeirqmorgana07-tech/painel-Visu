"""Caixinha dos encarregados (cartão pré-pago): recargas, gastos com foto, conferência e alerta de saldo."""
import io
from datetime import date, datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import CaixaCartao, CaixaCategoria, CaixaMovimento, Empresa, Obra, Usuario, agora
from ..services import caixinha as cx

bp = Blueprint("caixinha", __name__, url_prefix="/caixinha")


def pode_gerir(u=None):
    """Financeiro: diretoria (admin / aprova sem limite) e o perfil Consulta (RH, Financeiro…)."""
    from .gerencial import e_diretoria
    u = u or current_user
    return u.is_authenticated and (e_diretoria(u) or u.tem_perfil(("consulta",)))


def tem_cartao(u=None):
    u = u or current_user
    return u.is_authenticated and CaixaCartao.query.filter_by(usuario_id=u.id, ativo=True).first() is not None


def pode_ver_menu(u):
    return pode_gerir(u) or tem_cartao(u)


def _cartao_permitido(cid):
    c = db.get_or_404(CaixaCartao, cid)
    if not (pode_gerir() or c.usuario_id == current_user.id):
        abort(403)
    return c


def _d(txt):
    try:
        return datetime.strptime(txt, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _obras():
    return Obra.query.filter(db.or_(Obra.status == "Em andamento", Obra.status.is_(None))).order_by(Obra.nome).all()


@bp.before_request
@login_required
def _guarda():
    cx.garantir_categorias()


@bp.route("/")
def inicio():
    gerir = pode_gerir()
    meus = CaixaCartao.query.filter_by(usuario_id=current_user.id, ativo=True).all()
    if not gerir and not meus:
        flash("Você ainda não tem cartão da caixinha cadastrado. Fale com o financeiro.", "warning")
        return redirect(url_for("main.dashboard"))
    if not gerir and len(meus) == 1:
        return redirect(url_for("caixinha.cartao", cid=meus[0].id))
    mostrar = request.args.get("mostrar", "ativos")
    q = CaixaCartao.query if gerir else CaixaCartao.query.filter_by(usuario_id=current_user.id)
    if mostrar == "ativos":
        q = q.filter(CaixaCartao.ativo.is_(True))
    cartoes = sorted(q.all(), key=lambda c: (c.usuario.nome if c.usuario else ""))
    sits = {c.id: cx.situacao(c) for c in cartoes}
    usuarios = Usuario.query.filter(Usuario.ativo.is_(True)).order_by(Usuario.nome).all() if gerir else []
    return render_template("caixinha/inicio.html", cartoes=cartoes, sits=sits, gerir=gerir, mostrar=mostrar,
                           usuarios=usuarios, empresas=Empresa.query.order_by(Empresa.id).all())


@bp.route("/cartao/novo", methods=["POST"])
@bp.route("/cartao/<int:cid>/editar", methods=["POST"])
def cartao_salvar(cid=None):
    if not pode_gerir():
        abort(403)
    c = db.session.get(CaixaCartao, cid) if cid else CaixaCartao(ativo=True)
    if cid and not c:
        abort(404)
    f = request.form
    u = db.session.get(Usuario, f.get("usuario_id", type=int) or 0)
    if not u:
        flash("Escolha o encarregado (usuário do sistema).", "danger")
        return redirect(request.referrer or url_for("caixinha.inicio"))
    c.usuario_id = u.id
    c.empresa_id = f.get("empresa_id", type=int) or None
    c.descricao = (f.get("descricao") or "").strip()[:120] or None
    pct = cx.num(f.get("alerta_pct") or "20")
    c.alerta_pct = pct if 1 <= pct <= 90 else 20
    if "ativo" in f:
        c.ativo = f.get("ativo") == "1"
    if not c.id:
        db.session.add(c)
    db.session.commit()
    flash(f"Cartão de {u.nome} salvo.", "success")
    return redirect(url_for("caixinha.cartao", cid=c.id))


@bp.route("/cartao/<int:cid>")
def cartao(cid):
    c = _cartao_permitido(cid)
    filtro = request.args.get("ver", "todos")
    movs = c.movimentos
    if filtro == "gastos":
        movs = [m for m in movs if m.tipo == "gasto"]
    elif filtro == "conferir":
        movs = [m for m in movs if m.tipo == "gasto" and m.status == "enviado"]
    elif filtro == "devolvidos":
        movs = [m for m in movs if m.tipo == "gasto" and m.status == "devolvido"]
    elif filtro == "recargas":
        movs = [m for m in movs if m.tipo != "gasto"]
    return render_template("caixinha/cartao.html", c=c, sit=cx.situacao(c), movs=movs, filtro=filtro,
                           gerir=pode_gerir(), dono=c.usuario_id == current_user.id, cats=cx.categorias(),
                           obras=_obras(), hoje=date.today(), status=cx.STATUS,
                           usuarios=Usuario.query.filter(Usuario.ativo.is_(True)).order_by(Usuario.nome).all() if pode_gerir() else [],
                           empresas=Empresa.query.order_by(Empresa.id).all())


def _destino(valor, m):
    valor = (valor or "").strip()
    m.obra_id, m.centro_custo = None, None
    if valor.startswith("obra:"):
        ob = db.session.get(Obra, int(valor[5:] or 0))
        m.obra_id = ob.id if ob else None
    elif valor == "empresa":
        m.centro_custo = "Empresa"
    elif valor.startswith("outro:") and valor[6:].strip():
        m.centro_custo = valor[6:].strip()[:200]


@bp.route("/cartao/<int:cid>/gasto", methods=["POST"])
@bp.route("/gasto/<int:mid>/editar", methods=["POST"])
def gasto_salvar(cid=None, mid=None):
    """Encarregado lança o gasto com a foto do comprovante (ou corrige um devolvido)."""
    if mid:
        m = db.get_or_404(CaixaMovimento, mid)
        c = _cartao_permitido(m.cartao_id)
        if m.status == "conferido" and not pode_gerir():
            flash("Gasto já conferido pelo financeiro: não dá mais para alterar.", "warning")
            return redirect(url_for("caixinha.cartao", cid=c.id))
    else:
        c = _cartao_permitido(cid)
        m = CaixaMovimento(cartao_id=c.id, tipo="gasto", criado_por=current_user.nome)
    f = request.form
    valor = cx.num(f.get("valor"))
    if valor <= 0:
        flash("Informe o valor do gasto.", "danger")
        return redirect(url_for("caixinha.cartao", cid=c.id))
    foto = request.files.get("foto")
    if foto and foto.filename:
        from ..services.fotos import ErroFoto, reduzir
        try:
            m.foto = reduzir(foto.read())
        except ErroFoto as e:
            flash(str(e), "danger")
            return redirect(url_for("caixinha.cartao", cid=c.id))
    if not m.foto:
        flash("Tire ou anexe a foto do comprovante.", "danger")
        return redirect(url_for("caixinha.cartao", cid=c.id))
    if not f.get("categoria") or not f.get("obra"):
        flash("Escolha a categoria do gasto e a obra / centro de custo.", "danger")
        return redirect(url_for("caixinha.cartao", cid=c.id))
    m.valor = valor
    m.data = _d(f.get("data")) or date.today()
    m.categoria = (f.get("categoria") or "").strip()[:120]
    _destino(f.get("obra"), m)
    m.descricao = (f.get("descricao") or "").strip()[:255] or None
    if mid and m.status == "devolvido":
        m.status = "enviado"   # corrigido: volta para a conferência
    if not mid:
        db.session.add(m)
    db.session.commit()
    sit = cx.situacao(c)
    flash(f"Gasto de {cx.moeda(valor)} lançado. Saldo do cartão: {cx.moeda(sit['saldo'])}.", "success")
    if cx.verificar_alerta(c):
        flash(f"Atenção: o saldo chegou a {sit['pct']:.0f}% da última recarga — o financeiro foi avisado.", "warning")
    return redirect(url_for("caixinha.cartao", cid=c.id))


@bp.route("/cartao/<int:cid>/recarga", methods=["POST"])
def recarga(cid):
    if not pode_gerir():
        abort(403)
    c = db.get_or_404(CaixaCartao, cid)
    f = request.form
    valor = cx.num(f.get("valor"))
    tipo = "ajuste" if f.get("tipo") == "ajuste" else "recarga"
    if tipo == "recarga" and valor <= 0 or tipo == "ajuste" and not valor:
        flash("Informe o valor.", "danger")
        return redirect(url_for("caixinha.cartao", cid=c.id))
    db.session.add(CaixaMovimento(cartao_id=c.id, tipo=tipo, valor=valor, data=_d(f.get("data")) or date.today(),
                                  descricao=(f.get("descricao") or "").strip()[:255] or None, status="conferido",
                                  criado_por=current_user.nome, conferido_por=current_user.nome, conferido_em=agora()))
    if tipo == "recarga":
        c.alerta_enviado_em = None   # nova recarga: novo ciclo de alerta
    db.session.commit()
    db.session.refresh(c)
    flash(f"{'Recarga' if tipo == 'recarga' else 'Ajuste'} de {cx.moeda(valor)} registrado. Saldo: {cx.moeda(cx.saldo(c))}.", "success")
    cx.verificar_alerta(c)
    return redirect(url_for("caixinha.cartao", cid=c.id))


@bp.route("/movimento/<int:mid>/conferir", methods=["POST"])
def conferir(mid):
    if not pode_gerir():
        abort(403)
    m = db.get_or_404(CaixaMovimento, mid)
    acao = request.form.get("acao")
    if acao == "excluir":
        cid = m.cartao_id
        db.session.delete(m)
        db.session.commit()
        flash("Lançamento excluído.", "success")
        return redirect(url_for("caixinha.cartao", cid=cid))
    m.status = {"conferir": "conferido", "devolver": "devolvido", "reabrir": "enviado"}.get(acao, m.status)
    m.obs_conferencia = (request.form.get("obs") or "").strip()[:255] or m.obs_conferencia
    m.conferido_por, m.conferido_em = current_user.nome, agora()
    db.session.commit()
    if m.status == "devolvido":
        _avisar_devolvido(m)
    return redirect(request.referrer or url_for("caixinha.cartao", cid=m.cartao_id))


def _avisar_devolvido(m):
    from ..services import notificacoes as notif
    u = m.cartao.usuario
    if not (u and u.telefone and u.callmebot_apikey):
        return
    texto = (f"*VIEIRA DINIZ · CAIXINHA*\nO financeiro devolveu o gasto de {cx.moeda(m.valor)} de "
             f"{m.data.strftime('%d/%m')} ({m.categoria}) para corrigir"
             + (f": {m.obs_conferencia}" if m.obs_conferencia else ".")
             + f"\n{url_for('caixinha.cartao', cid=m.cartao_id, _external=True)}")
    notif.em_segundo_plano(lambda uid, t: notif._enviar_callmebot(db.session.get(Usuario, uid), t), u.id, texto)


@bp.route("/movimento/<int:mid>/foto")
def foto(mid):
    m = db.get_or_404(CaixaMovimento, mid)
    _cartao_permitido(m.cartao_id)
    if not m.foto:
        abort(404)
    return send_file(io.BytesIO(m.foto), mimetype="image/jpeg", download_name=f"caixinha_{m.id}.jpg")


@bp.route("/relatorio")
def relatorio():
    if not pode_gerir():
        abort(403)
    hoje = date.today()
    ini = _d(request.args.get("de")) or hoje.replace(day=1)
    fim = _d(request.args.get("ate")) or hoje
    emp = request.args.get("empresa", type=int)
    cid = request.args.get("cartao", type=int)
    if request.args.get("excel"):
        return send_file(cx.exportar(ini, fim, emp, cid), as_attachment=True,
                         download_name=f"caixinha_{ini:%Y%m%d}_{fim:%Y%m%d}.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    return render_template("caixinha/relatorio.html", r=cx.relatorio(ini, fim, emp, cid), ini=ini, fim=fim, emp=emp,
                           cid=cid, empresas=Empresa.query.order_by(Empresa.id).all(),
                           cartoes=CaixaCartao.query.all(), status=cx.STATUS)


@bp.route("/categorias", methods=["GET", "POST"])
def categorias():
    if not pode_gerir():
        abort(403)
    if request.method == "POST":
        f = request.form
        x = db.session.get(CaixaCategoria, f.get("id", type=int) or 0) or CaixaCategoria(ativo=True)
        nome = " ".join((f.get("nome") or "").split())
        if nome:
            x.nome = nome[:120]
            x.ativo = f.get("ativo", "1") == "1"
            if not x.id:
                x.ordem = (db.session.query(db.func.max(CaixaCategoria.ordem)).scalar() or 0) + 1
                db.session.add(x)
            db.session.commit()
            flash("Categoria salva.", "success")
        return redirect(url_for("caixinha.categorias"))
    return render_template("caixinha/categorias.html", cats=cx.categorias(False))
