"""BI Financeiro (diretoria): fluxo de caixa projetado, resultado por obra, atrasos, DDA — e BI Multiobras."""
import os
import uuid
from datetime import date, datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import BoletoDDA, Configuracao, Empresa, LogIntegracao, TituloFinanceiro
from ..services import fin_bi, multiobras

bp = Blueprint("fin_bi", __name__, url_prefix="/bi")


def _d(txt):
    try:
        return datetime.strptime(txt, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _bloqueio():
    from .gerencial import e_diretoria
    if not e_diretoria(current_user):
        flash("Os painéis de BI financeiro e de obras são restritos à diretoria.", "warning")
        return redirect(url_for("main.dashboard"))
    return None


def pode_dda(u):
    """DDA: diretoria e quem tem perfil de Compras (ex.: Thomas — Almoxarife e Compras)."""
    from .gerencial import e_diretoria
    return u.is_authenticated and (e_diretoria(u) or u.tem_perfil(("compras",)))


def _bloqueio_dda():
    if not pode_dda(current_user):
        flash("O DDA é liberado para a diretoria e para o perfil de Compras.", "warning")
        return redirect(url_for("main.dashboard"))
    return None


def _empresa():
    return request.args.get("empresa", type=int)


def _comum():
    from .gerencial import e_diretoria
    return {"empresas": Empresa.query.order_by(Empresa.id).all(), "empresa_id": _empresa(),
            "tem_dados": fin_bi.tem_dados(), "diretoria": e_diretoria(current_user)}


# ---------------------------------------------------------------- fluxo de caixa

@bp.route("/financeiro/")
@login_required
def inicio():
    return redirect(url_for("fin_bi.fluxo"))


@bp.route("/financeiro/fluxo")
@login_required
def fluxo():
    if (r := _bloqueio()):
        return r
    modo = request.args.get("modo", "mensal")
    modo = modo if modo in ("mensal", "diario") else "mensal"
    dias = request.args.get("dias", 30, type=int)
    saldo = request.args.get("saldo")
    saldo = fin_bi._num(saldo) if saldo not in (None, "") else None
    origem_saldo = "digitado" if saldo is not None else "padrao"
    if saldo is None:
        from ..services.saldos import total_saldos
        tb = total_saldos(_empresa())
        if tb is not None:
            saldo, origem_saldo = tb, "bancos"
    f = fin_bi.fluxo(_empresa(), modo=modo, dias=dias, sem_transf=request.args.get("transf") != "1", saldo=saldo,
                     vencidos_no_inicio=request.args.get("vi", "1") == "1")
    return render_template("fin_bi/fluxo.html", f=f, aba="fluxo", origem_saldo=origem_saldo, **_comum())


@bp.route("/financeiro/fluxo/saldo", methods=["POST"])
@login_required
def fluxo_saldo():
    if (r := _bloqueio()):
        return r
    v = fin_bi._num(request.form.get("saldo"))
    Configuracao.definir("fluxo_saldo_inicial", f"{v:.2f}")
    Configuracao.definir("fluxo_saldo_data", date.today().isoformat())
    db.session.commit()
    flash(f"Saldo inicial do fluxo de caixa salvo: R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), "success")
    return redirect(request.referrer or url_for("fin_bi.fluxo"))


@bp.route("/financeiro/fluxo/detalhe")
@login_required
def fluxo_detalhe():
    if (r := _bloqueio()):
        return r
    de, ate = _d(request.args.get("de")), _d(request.args.get("ate"))
    tipo = request.args.get("tipo") if request.args.get("tipo") in ("pagar", "receber") else None
    vencidos = request.args.get("vencidos") == "1"
    realizado = request.args.get("realizado") == "1"
    if not vencidos and not (de and ate):
        return redirect(url_for("fin_bi.fluxo"))
    ts = fin_bi.titulos_periodo(_empresa(), de, ate, tipo, realizado=realizado, vencidos=vencidos,
                                sem_transf=request.args.get("transf") != "1")
    dda = []
    if not realizado and tipo != "receber":
        dda = [b for b in fin_bi._boletos_a_lancar(_empresa())
               if b.vencimento and ((vencidos and b.vencimento < date.today()) or
                                    (not vencidos and de <= b.vencimento <= ate and b.vencimento >= date.today()))]
    titulo = ("Vencidos em aberto" if vencidos else
              (f"{'Realizado' if realizado else 'Previsto'} de {de.strftime('%d/%m/%Y')} a {ate.strftime('%d/%m/%Y')}"
               if de != ate else f"{'Realizado' if realizado else 'Previsto'} em {de.strftime('%d/%m/%Y')}"))
    return render_template("fin_bi/fluxo_detalhe.html", ts=ts, dda=dda, titulo=titulo, tipo=tipo, realizado=realizado,
                           aba="fluxo", **_comum())


# ---------------------------------------------------------------- resultado por obra, top 10

@bp.route("/financeiro/resultado")
@login_required
def resultado():
    if (r := _bloqueio()):
        return r
    x = fin_bi.resultado(_empresa(), _d(request.args.get("de")), _d(request.args.get("ate")), request.args.get("cc") or None)
    return render_template("fin_bi/resultado.html", x=x, aba="resultado", **_comum())


@bp.route("/financeiro/atrasos")
@login_required
def atrasos():
    if (r := _bloqueio()):
        return r
    return render_template("fin_bi/atrasos.html", x=fin_bi.atrasos(_empresa()), aba="atrasos", hoje=date.today(),
                           **_comum())


@bp.route("/financeiro/ponto-equilibrio", methods=["GET", "POST"])
@login_required
def ponto_equilibrio():
    if (r := _bloqueio()):
        return r
    if request.method == "POST":
        for g in fin_bi.PE_GRUPOS_PADRAO:
            v = request.form.get("r_" + fin_bi.norm(g))
            if v in fin_bi.PE_OPCOES:
                Configuracao.definir("pe_grupo:" + fin_bi.norm(g), v)
        db.session.commit()
        flash("Classificação fixo x variável salva.", "success")
        return redirect(url_for("fin_bi.ponto_equilibrio", **request.args))
    x = fin_bi.ponto_equilibrio(_empresa(), _d(request.args.get("de")), _d(request.args.get("ate")))
    return render_template("fin_bi/ponto_equilibrio.html", x=x, aba="pe", norm=fin_bi.norm, **_comum())


# ---------------------------------------------------------------- DDA

@bp.route("/financeiro/dda", methods=["GET", "POST"])
@login_required
def dda():
    if (r := _bloqueio_dda()):
        return r
    if request.method == "POST":
        arq = request.files.get("arquivo")
        if not arq or not arq.filename:
            flash("Escolha o arquivo do DDA exportado do banco.", "danger")
            return redirect(url_for("fin_bi.dda"))
        pasta = os.path.join(current_app.instance_path, "uploads")
        os.makedirs(pasta, exist_ok=True)
        caminho = os.path.join(pasta, uuid.uuid4().hex + os.path.splitext(arq.filename)[1].lower())
        arq.save(caminho)
        try:
            res = fin_bi.importar_dda(caminho, arq.filename, request.form.get("empresa_id", type=int))
            msg = (f"DDA: {res['lidos']} boleto(s) no arquivo, {res['novos']} novo(s). "
                   f"{res['lancados']} já lançado(s) no financeiro, {res['faltando']} faltando lançar"
                   + (f", {res['conferir']} para conferir (mais de uma conta a pagar possível)" if res.get('conferir') else "") + ".")
            db.session.add(LogIntegracao(sistema="dda", operacao="Importar DDA", sucesso=True, mensagem=msg,
                                         usuario=current_user.nome))
            db.session.commit()
            flash(msg, "success")
        except Exception as e:  # noqa: BLE001 — arquivo fora do padrão
            db.session.rollback()
            flash(f"Não consegui ler o DDA: {e}", "danger")
        finally:
            if os.path.exists(caminho):
                os.remove(caminho)
        return redirect(url_for("fin_bi.dda"))
    from .gerencial import _d as _data_arg
    # período padrão: do mês atual em diante (boletos de meses anteriores só com "todos os períodos")
    todos_periodos = request.args.get("periodo") == "todos"
    de, ate = _data_arg(request.args.get("de")), _data_arg(request.args.get("ate"))
    if not (de or ate or todos_periodos or "de" in request.args):
        de = date.today().replace(day=1)
    x = fin_bi.lista_dda(request.args.get("ver", "todos"), busca=request.args.get("q", ""), de=de, ate=ate,
                         empresa_id=_empresa(), pagamento=request.args.get("pag", ""))
    from ..services import financeiro
    ult = (LogIntegracao.query.filter(LogIntegracao.operacao.like("DDA: contas a pagar%"))
           .order_by(LogIntegracao.id.desc()).first())
    ult_geral = (LogIntegracao.query.filter(LogIntegracao.operacao.like("Base financeira%"))
                 .order_by(LogIntegracao.id.desc()).first())
    return render_template("fin_bi/dda.html", x=x, aba="dda", hoje=date.today(), ult_pagar=ult, ult_geral=ult_geral,
                           atualizando=financeiro.atualizando_agora(), **_comum())


@bp.route("/financeiro/dda/<int:bid>", methods=["GET", "POST"])
@login_required
def dda_boleto(bid):
    if (r := _bloqueio_dda()):
        return r
    b = db.get_or_404(BoletoDDA, bid)
    if request.method == "POST":
        acao = request.form.get("acao")
        if acao == "ignorar":
            b.ignorado, b.manual, b.titulo_chave, b.titulo_empresa_id = True, True, None, None
            flash("Boleto marcado como ignorado (não entra no fluxo de caixa).", "success")
        elif acao == "vincular":
            t = db.session.get(TituloFinanceiro, request.form.get("titulo_id", type=int) or 0)
            if t:
                b.titulo_chave, b.titulo_empresa_id, b.manual, b.ignorado = t.chave, t.empresa_id, True, False
                flash(f"Boleto vinculado a {t.nome} ({t.vencimento.strftime('%d/%m/%Y') if t.vencimento else '—'}).", "success")
        elif acao == "automatico":
            b.manual, b.ignorado = False, False
            fin_bi.conciliar()
            flash("Voltou para a conciliação automática.", "success")
        elif acao == "excluir":
            db.session.delete(b)
            db.session.commit()
            flash("Boleto excluído da lista do DDA.", "success")
            return redirect(url_for("fin_bi.dda"))
        db.session.commit()
        return redirect(url_for("fin_bi.dda_boleto", bid=b.id))
    from .gerencial import _d as _data_arg
    busca = (request.args.get("q") or "").strip()
    de, ate = _data_arg(request.args.get("de")), _data_arg(request.args.get("ate"))
    achados = (fin_bi.buscar_titulos_pagar(busca, b.empresa_id if request.args.get("so_empresa") else None, de=de, ate=ate,
                                           so_abertos=bool(request.args.get("abertos")))
               if (busca or de or ate) else None)
    return render_template("fin_bi/dda_boleto.html", b=b, cands=fin_bi.candidatos_dda(b, incluir_pagos=bool(request.args.get("pagos"))), achados=achados,
                           diag=fin_bi.diagnostico_dda(b) if not b.titulo_chave else [], busca=busca, de=de, ate=ate,
                           aba="dda", **_comum())


@bp.route("/financeiro/dda/atualizar", methods=["POST"])
@login_required
def dda_atualizar():
    """Depois de lançar no Omie / Mais Controle os títulos que faltavam: busca o contas a pagar e confere de novo."""
    if (r := _bloqueio_dda()):
        return r
    from flask import current_app
    from ..services import financeiro
    disp, ocup, sem = financeiro.disparar_pagar(current_app._get_current_object(), current_user.nome)
    partes = []
    if disp:
        partes.append("Buscando o contas a pagar de " + " e ".join(disp)
                      + ". Leva de 1 a 3 minutos; depois o DDA é conferido sozinho — recarregue a página.")
    if ocup:
        partes.append("Já existe uma atualização em andamento para " + " e ".join(ocup) + ".")
    if sem:
        partes.append("Sem credenciais da API no Render para " + " e ".join(sem) + ".")
    flash(" ".join(partes) or "Nada para atualizar.", "info" if disp else "warning")
    return redirect(url_for("fin_bi.dda"))


@bp.route("/financeiro/dda/conciliar", methods=["POST"])
@login_required
def dda_conciliar():
    if (r := _bloqueio_dda()):
        return r
    res = fin_bi.conciliar()
    db.session.commit()
    flash(f"Conciliação refeita: {res['lancados']} lançado(s), {res['faltando']} faltando lançar"
          + (f", {res['conferir']} para conferir" if res.get('conferir') else "") + ".", "success")
    return redirect(url_for("fin_bi.dda"))


# ---------------------------------------------------------------- Compras com e sem OC

@bp.route("/compras/ordens")
@login_required
def compras_oc():
    if (r := _bloqueio()):
        return r
    x = fin_bi.compras_oc(_empresa(), _d(request.args.get("de")), _d(request.args.get("ate")))
    return render_template("fin_bi/compras_oc.html", x=x, **_comum())


# ---------------------------------------------------------------- Multiobras

@bp.route("/obras/")
@login_required
def obras():
    if (r := _bloqueio()):
        return r
    status = request.args.get("status", "Em Andamento")
    x = multiobras.calcular(status=status or None, busca=request.args.get("q"), empresa=request.args.get("emp"),
                            ordem=request.args.get("ordem", "custo"))
    return render_template("fin_bi/multiobras.html", x=x)


@bp.route("/obras/<obra_ext>")
@login_required
def obra(obra_ext):
    if (r := _bloqueio()):
        return r
    x = multiobras.detalhe(obra_ext)
    if not x:
        flash("Obra não encontrada no Mais Controle.", "warning")
        return redirect(url_for("fin_bi.obras"))
    return render_template("fin_bi/obra.html", x=x)


# ---------------------------------------------------------------- arquivo de pagamento em lote

@bp.route("/financeiro/lotes", methods=["GET", "POST"])
@login_required
def lotes():
    from ..models import LotePagamento
    from ..services import pagamento_lote as pl
    if (r := _bloqueio()):
        return r
    empresas = Empresa.query.order_by(Empresa.id).all()
    emp = db.session.get(Empresa, request.values.get("empresa", type=int) or 0) or (empresas[0] if empresas else None)
    if request.method == "POST" and emp:
        acao = request.form.get("acao")
        if acao == "cfg":
            pl.salvar_cfg(emp, request.form)
            flash(f"Conta pagadora de {emp.nome} salva.", "success")
        elif acao == "criar":
            try:
                lote = pl.criar(emp, request.form, current_user)
                db.session.commit()
                flash(f"{lote.numero} criado: {len(lote.itens)} conta(s), total R$ {lote.total:,.2f}."
                      .replace(",", "X").replace(".", ",").replace("X", "."), "success")
                return redirect(url_for("fin_bi.lote", lid=lote.id))
            except pl.ErroLote as e:
                db.session.rollback()
                flash(str(e), "danger")
        return redirect(url_for("fin_bi.lotes", empresa=emp.id, de=request.form.get("de"), ate=request.form.get("ate")))
    from datetime import timedelta
    hoje = date.today()
    de = _d(request.args.get("de")) or hoje
    ate = _d(request.args.get("ate")) or (hoje + timedelta(days=7))
    if ate < de:
        ate = de
    cands = pl.candidatos(emp.id, de, ate) if emp else []
    historico = LotePagamento.query.order_by(LotePagamento.id.desc()).limit(30).all()
    return render_template("fin_bi/lotes.html", emp=emp, empresas=empresas, cands=cands, de=de, ate=ate,
                           cfg=pl.cfg(emp) if emp else {}, campos=pl.CAMPOS_CFG, cfg_ok=pl.cfg_ok(pl.cfg(emp)) if emp else False,
                           historico=historico, hoje=hoje, tem_dados=fin_bi.tem_dados())


@bp.route("/financeiro/lotes/<int:lid>", methods=["GET", "POST"])
@login_required
def lote(lid):
    from flask import Response
    from ..models import LotePagamento
    from ..services import pagamento_lote as pl
    if (r := _bloqueio()):
        return r
    lt = db.get_or_404(LotePagamento, lid)
    if request.method == "POST":
        acao = request.form.get("acao")
        if acao == "enviado":
            lt.status = "Enviado ao banco"
        elif acao == "cancelar":
            lt.status = "Cancelado"
            flash("Lote cancelado: as contas voltaram a ficar disponíveis para um novo lote.", "success")
        db.session.commit()
        return redirect(url_for("fin_bi.lote", lid=lid))
    fmt = request.args.get("baixar")
    if fmt == "remessa":
        try:
            txt = pl.gerar_cnab(lt)
            db.session.commit()
        except pl.ErroLote as e:
            db.session.rollback()
            flash(str(e), "danger")
            return redirect(url_for("fin_bi.lote", lid=lid))
        return Response(txt.encode("ascii", "replace"), mimetype="text/plain",
                        headers={"Content-Disposition": f"attachment; filename={pl.nome_arquivo(lt)}"})
    if fmt == "planilha":
        return Response(pl.planilha(lt), mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f"attachment; filename={lt.numero}.xlsx"})
    return render_template("fin_bi/lote.html", lt=lt, cfg_ok=pl.cfg_ok(pl.cfg(lt.empresa)), tem_dados=True)


# ---------------------------------------------------------------- saldos bancários

@bp.route("/financeiro/saldos", methods=["GET", "POST"])
@login_required
def saldos():
    from ..models import ContaBancaria
    from ..services import saldos as sb
    if (r := _bloqueio()):
        return r
    if request.method == "POST":
        acao = request.form.get("acao")
        try:
            if acao == "omie":
                n = 0
                for emp in Empresa.query.filter_by(sistema="omie").all():
                    n += sb.atualizar_omie(emp)
                flash(f"Saldos do Omie atualizados ({n} conta(s)).", "success")
            elif acao == "ofx":
                arq = request.files.get("arquivo")
                if not arq or not arq.filename:
                    raise sb.ErroSaldo("Escolha o arquivo OFX do extrato.")
                res = sb.importar_ofx(arq.read(), request.form.get("empresa_id", type=int))
                flash(" | ".join(f"{x['conta']}: {x['novos']} lançamento(s) novo(s), saldo "
                                 + (f"R$ {x['saldo']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if x['saldo'] is not None else "—")
                                 for x in res), "success")
            elif acao == "manual":
                cid = request.form.get("conta_id", type=int)
                cb = db.session.get(ContaBancaria, cid) if cid else None
                if not cb:
                    nome = (request.form.get("nome") or "").strip()
                    if not nome:
                        raise sb.ErroSaldo("Informe o nome da conta (ex.: Itaú Ag 7477 C/C 15614-0).")
                    import uuid as _u
                    cb = ContaBancaria(origem="manual", chave=f"manual:{_u.uuid4().hex[:12]}", nome=nome[:120],
                                       empresa_id=request.form.get("empresa_id", type=int))
                    db.session.add(cb)
                v = sb._num(request.form.get("saldo"))
                if v is None:
                    raise sb.ErroSaldo("Informe o saldo.")
                cb.saldo, cb.saldo_em = round(v, 2), _d(request.form.get("saldo_em")) or date.today()
                cb.obs = f"Digitado por {current_user.nome}"
                db.session.commit()
                flash(f"Saldo de {cb.nome} salvo.", "success")
            elif acao == "desativar":
                cb = db.get_or_404(ContaBancaria, request.form.get("conta_id", type=int) or 0)
                cb.ativa = not cb.ativa
                db.session.commit()
                flash(f"{cb.nome}: {'ativa' if cb.ativa else 'fora da soma dos saldos'}.", "success")
        except Exception as e:  # noqa: BLE001
            db.session.rollback()
            flash(str(e), "danger")
        return redirect(url_for("fin_bi.saldos"))
    todas = ContaBancaria.query.order_by(ContaBancaria.empresa_id, ContaBancaria.nome).all()
    return render_template("fin_bi/saldos.html", r=sb.resumo(), todas=todas, conf=sb.conferencia_mensal(),
                           hoje=date.today(), aba="saldos", **_comum())
