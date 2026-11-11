"""Caixinha dos encarregados: cartão pré-pago com recargas do financeiro, gastos com foto (categoria e obra /
centro de custo) enviados pelo encarregado e alerta quando o saldo chega a 20% do valor da última recarga."""
import io
from datetime import date, datetime

from flask import url_for

from ..extensions import db
from ..models import CaixaCartao, CaixaCategoria, CaixaMovimento, Usuario, agora

CATEGORIAS_PADRAO = ["Alimentação", "Combustível", "Material de consumo / pequenas compras", "Ferramentas",
                     "Transporte (Uber, ônibus, frete)", "Estacionamento / pedágio", "Hospedagem",
                     "Serviços de terceiros", "Outros"]
STATUS = {"enviado": "A conferir", "conferido": "Conferido", "devolvido": "Devolvido para corrigir"}


def garantir_categorias():
    if not CaixaCategoria.query.first():
        for i, n in enumerate(CATEGORIAS_PADRAO):
            db.session.add(CaixaCategoria(nome=n, ordem=i, ativo=True))
        db.session.commit()


def categorias(ativas=True):
    q = CaixaCategoria.query
    if ativas:
        q = q.filter(CaixaCategoria.ativo.is_(True))
    return q.order_by(CaixaCategoria.ordem, CaixaCategoria.nome).all()


def _sinal(m):
    if m.tipo == "recarga":
        return m.valor or 0
    if m.tipo == "gasto":
        return -(m.valor or 0)
    return m.valor or 0   # ajuste (+/-)


def saldo(cartao):
    return round(sum(_sinal(m) for m in cartao.movimentos), 2)


def situacao(cartao):
    """Saldo, valor disponível logo depois da última recarga (base do alerta) e % que resta."""
    movs = sorted(cartao.movimentos, key=lambda m: (m.data, m.criado_em or datetime.min, m.id or 0))
    s, base, ult = 0.0, 0.0, None
    for m in movs:
        s += _sinal(m)
        if m.tipo == "recarga":
            base, ult = s, m
    s = round(s, 2)
    pct = (s / base * 100) if base > 0 else (0 if s <= 0 else 100)
    limite = round(base * (cartao.alerta_pct or 20) / 100, 2)
    gastos = [m for m in cartao.movimentos if m.tipo == "gasto"]
    return {"saldo": s, "base": round(base, 2), "pct": max(0.0, min(100.0, pct)), "limite": limite,
            "alerta": base > 0 and s <= limite, "ultima_recarga": ult,
            "a_conferir": sum(1 for m in gastos if m.status == "enviado"),
            "devolvidos": sum(1 for m in gastos if m.status == "devolvido")}


def gestores():
    """Quem recebe o alerta além do encarregado: administradores e diretoria (aprova sem limite), ativos."""
    return [u for u in Usuario.query.filter(Usuario.ativo.is_(True)).all()
            if u.perfil == "admin" or getattr(u, "aprova_sem_limite", False)]


def verificar_alerta(cartao):
    """Saldo chegou a 20% (ou ao % do cartão) do disponível na última recarga: avisa uma vez por recarga."""
    sit = situacao(cartao)
    if not sit["alerta"] or cartao.alerta_enviado_em:
        return False
    cartao.alerta_enviado_em = agora()
    db.session.commit()
    texto = (f"*VIEIRA DINIZ · CAIXINHA*\nCartão de *{cartao.usuario.nome}*{(' (' + cartao.descricao + ')') if cartao.descricao else ''} "
             f"está com saldo de *{moeda(sit['saldo'])}* ({sit['pct']:.0f}% da última recarga de {moeda(sit['base'])}).\n"
             f"Hora de programar uma nova recarga.")
    try:
        link = url_for("caixinha.cartao", cid=cartao.id, _external=True)
        texto += f"\n{link}"
    except Exception:  # noqa: BLE001 — fora de requisição
        pass
    from . import notificacoes as notif
    destinos = [cartao.usuario] + [g for g in gestores() if g.id != cartao.usuario_id]

    def _enviar(ids, txt):
        for uid in ids:
            u = db.session.get(Usuario, uid)
            if u and u.telefone and u.callmebot_apikey:
                try:
                    notif._enviar_callmebot(u, txt)
                except Exception:  # noqa: BLE001
                    pass
    notif.em_segundo_plano(_enviar, [u.id for u in destinos], texto)
    return True


def moeda(v):
    return "R$ " + f"{v or 0:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def num(txt):
    t = str(txt or "").replace("R$", "").strip()
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return round(float(t), 2)
    except ValueError:
        return 0.0


def relatorio(ini, fim, empresa_id=None, cartao_id=None):
    q = CaixaMovimento.query.join(CaixaCartao).filter(CaixaMovimento.tipo == "gasto", CaixaMovimento.data >= ini,
                                                      CaixaMovimento.data <= fim)
    if empresa_id:
        q = q.filter(CaixaCartao.empresa_id == empresa_id)
    if cartao_id:
        q = q.filter(CaixaMovimento.cartao_id == cartao_id)
    movs = q.order_by(CaixaMovimento.data, CaixaMovimento.id).all()
    por_cc, por_cat = {}, {}
    for m in movs:
        por_cc[m.cc] = por_cc.get(m.cc, 0) + (m.valor or 0)
        por_cat[m.categoria or "—"] = por_cat.get(m.categoria or "—", 0) + (m.valor or 0)
    return {"movs": movs, "total": round(sum(m.valor or 0 for m in movs), 2),
            "por_cc": sorted(por_cc.items(), key=lambda x: -x[1]), "por_cat": sorted(por_cat.items(), key=lambda x: -x[1])}


def exportar(ini, fim, empresa_id=None, cartao_id=None):
    import openpyxl
    from openpyxl.styles import Font, PatternFill
    r = relatorio(ini, fim, empresa_id, cartao_id)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Gastos"
    ws.append(["Data", "Encarregado", "Cartão", "Empresa", "Obra / centro de custo", "Categoria", "Descrição", "Valor",
               "Situação", "Conferido por"])
    for m in r["movs"]:
        c = m.cartao
        ws.append([m.data, c.usuario.nome if c.usuario else "", c.descricao or "", c.empresa.nome if c.empresa else "",
                   m.cc, m.categoria or "", m.descricao or "", round(m.valor or 0, 2), STATUS.get(m.status, m.status),
                   m.conferido_por or ""])
    for nome, dados in (("Por obra", r["por_cc"]), ("Por categoria", r["por_cat"])):
        w = wb.create_sheet(nome)
        w.append([nome.replace("Por ", "").capitalize(), "Total"])
        for k, v in dados:
            w.append([k, round(v, 2)])
    for w in wb.worksheets:
        for cel in w[1]:
            cel.font = Font(bold=True, color="FFFFFF")
            cel.fill = PatternFill("solid", fgColor="00304E")
        for col in w.columns:
            w.column_dimensions[col[0].column_letter].width = max(12, min(45, max(len(str(x.value or "")) for x in col) + 2))
        for row in w.iter_rows(min_row=2):
            for cel in row:
                if isinstance(cel.value, float):
                    cel.number_format = "#,##0.00"
                elif isinstance(cel.value, date):
                    cel.number_format = "DD/MM/YYYY"
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
