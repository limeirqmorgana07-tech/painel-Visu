"""Notas fiscais de serviço (NFS-e) emitidas — Prefeitura do Recife (diretoria)."""
from datetime import date, datetime, timedelta

from flask import Blueprint, Response, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Configuracao, Empresa, NFSeEmitida
from ..services import nfse as ns

bp = Blueprint("nfse", __name__, url_prefix="/nfse")


def _d(txt):
    try:
        return datetime.strptime(txt, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _bloqueio():
    from .gerencial import e_diretoria
    if not e_diretoria(current_user):
        flash("As notas de serviço são restritas à diretoria.", "warning")
        return redirect(url_for("main.dashboard"))
    return None


def _filtros():
    hoje = date.today()
    ini = _d(request.args.get("de")) or hoje.replace(day=1)
    fim = _d(request.args.get("ate")) or hoje
    if fim < ini:
        ini, fim = fim, ini
    return {"empresa_id": request.args.get("empresa", type=int), "ini": ini, "fim": fim,
            "q": (request.args.get("q") or "").strip(), "situacao": request.args.get("situacao") or "todas"}


@bp.route("/")
@login_required
def lista():
    b = _bloqueio()
    if b:
        return b
    f = _filtros()
    notas = ns.filtrar(f["empresa_id"], f["ini"], f["fim"], f["q"], f["situacao"])
    receb = ns.conferir_recebimentos(notas)
    return render_template("nfse/lista.html", notas=notas, t=ns.totais(notas), receb=receb, f=f,
                           status=[ns.status(e) for e in Empresa.query.order_by(Empresa.id).all()],
                           empresas=Empresa.query.order_by(Empresa.id).all(), hoje=date.today(), timedelta=timedelta)


@bp.route("/exportar/<fmt>")
@login_required
def exportar(fmt):
    b = _bloqueio()
    if b:
        return b
    f = _filtros()
    notas = ns.filtrar(f["empresa_id"], f["ini"], f["fim"], f["q"], f["situacao"])
    nome = f"NFSe_emitidas_{f['ini']:%Y%m%d}_{f['fim']:%Y%m%d}"
    if fmt == "xml":
        return Response(ns.zip_xml(notas), mimetype="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="{nome}_xml.zip"'})
    return Response(ns.excel(notas, ns.conferir_recebimentos(notas)),
                    mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{nome}.xlsx"'})


@bp.route("/buscar", methods=["POST"])
@login_required
def buscar():
    b = _bloqueio()
    if b:
        return b
    ini = _d(request.form.get("de")) or date.today().replace(day=1)
    fim = _d(request.form.get("ate")) or date.today()
    if fim < ini:
        ini, fim = fim, ini
    if (fim - ini).days > 400:
        ini = fim - timedelta(days=400)
    alvo = request.form.get("empresa_id", type=int)
    emps = [e for e in ns.empresas_emissoras() if not alvo or e.id == alvo]
    if not emps:
        flash("Nenhuma empresa com inscrição municipal informada.", "warning")
    for e in emps:
        ok, msg = ns.buscar(e, ini, fim, current_user.nome)
        flash(f"{e.nome}: {msg}", "success" if ok else "danger")
        # desde 2026 as notas saem pelo Emissor Nacional: o XML nacional (base do DANFSe) vem do ADN
        try:
            ns.distribuir(e)
        except Exception as ex:  # noqa: BLE001
            db.session.rollback()
            flash(f"{e.nome}: não consegui buscar o XML nacional no Ambiente Nacional ({str(ex)[:150]}). "
                  "O PDF sai no resumo até a próxima busca.", "warning")
    return redirect(url_for("nfse.lista", de=ini.isoformat(), ate=fim.isoformat()))


@bp.route("/configurar", methods=["POST"])
@login_required
def configurar():
    if current_user.perfil_ativo != "admin":
        flash("Só o administrador altera a inscrição municipal.", "warning")
        return redirect(url_for("nfse.lista"))
    emp = db.get_or_404(Empresa, request.form.get("empresa_id", type=int) or 0)
    im = "".join(ch for ch in (request.form.get("im") or "") if ch.isdigit())
    Configuracao.definir(f"nfse_im_{emp.id}", im)
    db.session.commit()
    flash(f"{emp.nome}: inscrição municipal {'salva' if im else 'removida (não emite nota de serviço)'}.", "success")
    return redirect(url_for("nfse.lista"))


@bp.route("/<int:nid>", methods=["GET", "POST"])
@login_required
def ver(nid):
    b = _bloqueio()
    if b:
        return b
    n = db.get_or_404(NFSeEmitida, nid)
    if request.method == "POST":
        n.obra = (request.form.get("obra") or "").strip()[:200] or None
        db.session.commit()
        flash("Obra salva.", "success")
        return redirect(url_for("nfse.ver", nid=nid))
    return render_template("nfse/ver.html", n=n, receb=ns.conferir_recebimentos([n]).get(n.id))


@bp.route("/<int:nid>/xml")
@login_required
def xml(nid):
    b = _bloqueio()
    if b:
        return b
    n = db.get_or_404(NFSeEmitida, nid)
    return Response('<?xml version="1.0" encoding="utf-8"?>\n' + (n.xml or ""), mimetype="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="NFSe_{n.numero}.xml"'})


@bp.route("/<int:nid>/pdf")
@login_required
def pdf(nid):
    b = _bloqueio()
    if b:
        return b
    n = db.get_or_404(NFSeEmitida, nid)
    try:
        conteudo = ns.pdf_emitida(n)
    except Exception:  # noqa: BLE001
        current_app.logger.exception("PDF da NFS-e emitida %s", nid)
        flash("Não consegui montar o PDF desta nota. Use Imprimir ou baixe o XML.", "warning")
        return redirect(url_for("nfse.ver", nid=nid))
    modo = "attachment" if request.args.get("baixar") == "1" else "inline"
    return Response(conteudo, mimetype="application/pdf",
                    headers={"Content-Disposition": f'{modo}; filename="NFSe_{n.numero}.pdf"'})


# ---------------------------------------------------------------- recebidas (serviços contratados)

def _bloqueio_rec():
    from .gerencial import e_diretoria
    if not (e_diretoria(current_user) or current_user.tem_perfil(("compras", "consulta"))):
        flash("As notas de serviço recebidas são liberadas para a diretoria, Compras e Consulta.", "warning")
        return redirect(url_for("main.dashboard"))
    return None


def _filtros_rec():
    f = _filtros()
    if not request.args.get("de"):
        f["ini"] = (date.today() - timedelta(days=90)).replace(day=1)
    return f


def _lista_rec(f):
    notas = ns.filtrar_recebidas(f["empresa_id"], f["ini"], f["fim"], f["q"], f["situacao"])
    lanc = ns.lancadas_recebidas(notas)
    if f["situacao"] == "lancar":
        notas = [n for n in notas if n.id not in lanc]
    elif f["situacao"] == "lancadas":
        notas = [n for n in notas if n.id in lanc]
    return notas, lanc


@bp.route("/recebidas")
@login_required
def recebidas():
    b = _bloqueio_rec()
    if b:
        return b
    f = _filtros_rec()
    notas, lanc = _lista_rec(f)
    vivas = [n for n in notas if not n.cancelada]
    t = {"qtd": len(vivas), "canceladas": len(notas) - len(vivas),
         "servicos": round(sum(n.valor_servicos or 0 for n in vivas), 2),
         "liquido": round(sum(n.valor_liquido or 0 for n in vivas), 2),
         "a_lancar": sum(1 for n in vivas if n.id not in lanc),
         "valor_a_lancar": round(sum(n.valor_liquido or 0 for n in vivas if n.id not in lanc), 2)}
    from .gerencial import e_diretoria
    return render_template("nfse/recebidas.html", notas=notas, lanc=lanc, t=t, f=f, timedelta=timedelta,
                           status=[ns.status_adn(e) for e in Empresa.query.order_by(Empresa.id).all()],
                           empresas=Empresa.query.order_by(Empresa.id).all(), hoje=date.today(),
                           diretoria=e_diretoria(current_user))


@bp.route("/recebidas/buscar", methods=["POST"])
@login_required
def buscar_recebidas():
    b = _bloqueio_rec()
    if b:
        return b
    from ..services import sefaz as sz
    alvo = request.form.get("empresa_id", type=int)
    emps = [e for e in Empresa.query.order_by(Empresa.id).all() if sz.pronto(e) and (not alvo or e.id == alvo)]
    if not emps:
        flash("Nenhuma empresa com certificado A1 e senha no Render.", "warning")
    for e in emps:
        if request.form.get("recomecar") and current_user.perfil_ativo == "admin":
            Configuracao.definir(f"nfse_adn_{e.id}_nsu", "0")
            db.session.commit()
        ok, msg = ns.buscar_recebidas(e, current_user.nome)
        flash(f"{e.nome}: {msg}", "success" if ok else "danger")
    return redirect(url_for("nfse.recebidas"))


@bp.route("/recebidas/exportar/<fmt>")
@login_required
def exportar_recebidas(fmt):
    b = _bloqueio_rec()
    if b:
        return b
    f = _filtros_rec()
    notas, lanc = _lista_rec(f)
    nome = f"NFSe_recebidas_{f['ini']:%Y%m%d}_{f['fim']:%Y%m%d}"
    if fmt == "xml":
        return Response(ns.zip_xml_recebidas(notas), mimetype="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="{nome}_xml.zip"'})
    return Response(ns.excel_recebidas(notas, lanc),
                    mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{nome}.xlsx"'})


@bp.route("/recebida/<int:nid>", methods=["GET", "POST"])
@login_required
def ver_recebida(nid):
    b = _bloqueio_rec()
    if b:
        return b
    from ..models import NFSeRecebida
    n = db.get_or_404(NFSeRecebida, nid)
    if request.method == "POST":
        acao = request.form.get("acao")
        if acao == "obra":
            n.obra = (request.form.get("obra") or "").strip()[:200] or None
            flash("Obra salva.", "success")
        elif acao == "marcar":
            Configuracao.definir(f"nfse_rec_lanc_{n.id}",
                                 f"{current_user.nome} em {datetime.now():%d/%m/%Y}"
                                 + (f" · {request.form.get('obs').strip()[:80]}" if request.form.get("obs") else ""))
            flash("Nota marcada como lançada.", "success")
        elif acao == "vincular":
            from ..models import TituloFinanceiro
            t = db.get_or_404(TituloFinanceiro, request.form.get("tid", type=int) or 0)
            Configuracao.definir(f"nfse_rec_lanc_{n.id}", ns._texto_titulo(t) + f" · ligada por {current_user.nome}")
            flash("Nota ligada ao lançamento.", "success")
        elif acao == "desmarcar":
            Configuracao.definir(f"nfse_rec_lanc_{n.id}", "")
            flash("Marcação removida.", "success")
        db.session.commit()
        return redirect(url_for("nfse.ver_recebida", nid=nid))
    lanc = ns.lancadas_recebidas([n]).get(n.id)
    manual = Configuracao.obter(f"nfse_rec_lanc_{n.id}")
    return render_template("nfse/ver_recebida.html", n=n, lanc=lanc, manual=manual,
                           cands=[] if (lanc or n.cancelada) else ns.candidatos(n))


@bp.route("/recebida/<int:nid>/xml")
@login_required
def xml_recebida(nid):
    b = _bloqueio_rec()
    if b:
        return b
    from ..models import NFSeRecebida
    n = db.get_or_404(NFSeRecebida, nid)
    x = n.xml or ""
    if not x.lstrip().startswith("<?xml"):
        x = '<?xml version="1.0" encoding="utf-8"?>\n' + x
    return Response(x, mimetype="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="NFSe_{n.prestador_doc}_{n.numero}.xml"'})


@bp.route("/recebida/<int:nid>/pdf")
@login_required
def pdf_recebida(nid):
    b = _bloqueio_rec()
    if b:
        return b
    from ..models import NFSeRecebida
    n = db.get_or_404(NFSeRecebida, nid)
    pdf = ns.danfse(n)
    if not pdf:
        flash("Não consegui montar o PDF desta nota. Baixe o XML.", "warning")
        return redirect(url_for("nfse.ver_recebida", nid=nid))
    modo = "attachment" if request.args.get("baixar") == "1" else "inline"
    return Response(pdf, mimetype="application/pdf",
                    headers={"Content-Disposition": f'{modo}; filename="DANFSe_{n.prestador_doc}_{n.numero}.pdf"'})
