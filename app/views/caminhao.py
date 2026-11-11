"""Logística → Planejamento do caminhão, no formato da Programação diária (09/11/2026).

No alto ficam as OBRAS (na cor do encarregado): escolhe a obra e clica no dia de qualquer semana para incluir uma
entrega provisionada — vale mesmo sem solicitação no sistema. Embaixo, um bloco por encarregado com os dias do
período, juntando: entregas provisionadas (à mão e as fixas, ex.: Thanielle toda terça e sexta em rosa),
solicitações com data de entrega, retiradas de material e de entulho do motorista.
Filtros: semana ou período (De / Até), encarregado, obra e busca rápida. Saídas: WhatsApp (por encarregado),
PDF e Excel, sempre com os filtros da tela.

Editam só o administrador (Fredy) e o motorista (Lucas). Os outros perfis só veem."""
from collections import defaultdict
from datetime import date, timedelta
import io
import unicodedata

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user

from .. import perfil_requerido
from ..extensions import db
from ..models import Obra, PlanEncarregado, PlanObra, Solicitacao, agora

bp = Blueprint("caminhao", __name__, url_prefix="/caminhao")

VER = ("almoxarife", "encarregado", "motorista", "compras", "conferente")
EDITAR = ("motorista",)   # 09/11/2026 (reunião 05/11): só Fredy (administrador) e Lucas (motorista) alteram
DIAS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
ROSA = "#F9A8D4"
CORES = {"solicitacao": "#BFDBFE", "retirada": "#BBF7D0", "entulho": "#FDE68A"}
ROTULOS = {"provisionada": "Provisionada", "fixa": "Provisionada fixa", "solicitacao": "Solicitação",
           "retirada": "Retirada de material", "entulho": "Entulho"}


class CaminhaoRegra(db.Model):
    """Entrega provisionada fixa: encarregado (e, se quiser, uma obra dele) em dias certos da semana."""
    __tablename__ = "caminhao_regras"
    id = db.Column(db.Integer, primary_key=True)
    encarregado_id = db.Column(db.Integer, db.ForeignKey("plan_encarregados.id"), nullable=False, index=True)
    obra_id = db.Column(db.Integer, db.ForeignKey("obras.id"))
    plan_obra_id = db.Column(db.Integer, db.ForeignKey("plan_obras.id"))
    dias = db.Column(db.String(20), nullable=False, default="1,4")   # 0 = segunda … 5 = sábado
    cor = db.Column(db.String(9), default=ROSA)
    obs = db.Column(db.String(200))
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=agora)
    criado_por = db.Column(db.String(120))

    encarregado = db.relationship("PlanEncarregado")
    obra = db.relationship("Obra")
    plan_obra = db.relationship("PlanObra")

    @property
    def dias_lista(self):
        return [int(x) for x in (self.dias or "").split(",") if x.strip().isdigit()]

    @property
    def dias_txt(self):
        return " e ".join(DIAS[d] for d in self.dias_lista if d < len(DIAS))

    @property
    def obra_nome(self):
        return self.plan_obra.nome if self.plan_obra else (self.obra.nome if self.obra else "")


class CaminhaoViagem(db.Model):
    """Entrega provisionada num dia (obra do Planejamento) — ou 'pular' = tira a fixa só desse dia."""
    __tablename__ = "caminhao_viagens"
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False, index=True)
    encarregado_id = db.Column(db.Integer, db.ForeignKey("plan_encarregados.id"), index=True)
    obra_id = db.Column(db.Integer, db.ForeignKey("obras.id"))
    plan_obra_id = db.Column(db.Integer, db.ForeignKey("plan_obras.id"))
    regra_id = db.Column(db.Integer, db.ForeignKey("caminhao_regras.id"))
    tipo = db.Column(db.String(10), default="viagem")    # viagem | pular
    ordem = db.Column(db.Integer)                        # sequência de entrega no dia (rota do caminhão)
    descricao = db.Column(db.String(200))
    cor = db.Column(db.String(9))
    criado_em = db.Column(db.DateTime, default=agora)
    criado_por = db.Column(db.String(120))

    encarregado = db.relationship("PlanEncarregado")
    obra = db.relationship("Obra")
    plan_obra = db.relationship("PlanObra")


class CaminhaoEncaixe(db.Model):
    """Solicitação encaixada numa vaga (pré-reserva) do caminhão."""
    __tablename__ = "caminhao_encaixes"
    id = db.Column(db.Integer, primary_key=True)
    viagem_id = db.Column(db.Integer, db.ForeignKey("caminhao_viagens.id", ondelete="CASCADE"), nullable=False, index=True)
    solicitacao_id = db.Column(db.Integer, db.ForeignKey("solicitacoes.id", ondelete="CASCADE"), nullable=False, index=True)
    criado_em = db.Column(db.DateTime, default=agora)
    criado_por = db.Column(db.String(120))

    viagem = db.relationship("CaminhaoViagem", backref=db.backref("encaixes", cascade="all, delete-orphan",
                                                                  order_by="CaminhaoEncaixe.id"))
    solicitacao = db.relationship("Solicitacao")


class CaminhaoItem(db.Model):
    """O que vai na vaga do caminhão: item do estoque (insumo) ou item comprado por fora (texto livre)."""
    __tablename__ = "caminhao_itens"
    id = db.Column(db.Integer, primary_key=True)
    viagem_id = db.Column(db.Integer, db.ForeignKey("caminhao_viagens.id", ondelete="CASCADE"), nullable=False, index=True)
    insumo_id = db.Column(db.Integer, db.ForeignKey("insumos.id"))
    descricao = db.Column(db.String(200))          # item de fora (ou o nome do insumo, guardado)
    quantidade = db.Column(db.Float)
    unidade = db.Column(db.String(20))
    criado_por = db.Column(db.String(120))

    viagem = db.relationship("CaminhaoViagem", backref=db.backref("itens", cascade="all, delete-orphan",
                                                                  order_by="CaminhaoItem.id"))
    insumo = db.relationship("Insumo")

    @property
    def fora(self):
        return not self.insumo_id

    @property
    def texto(self):
        q = (f"{self.quantidade:g} {self.unidade or ''} ".replace(".", ",") if self.quantidade else "")
        nome = self.insumo.nome if self.insumo else (self.descricao or "")
        return (q + nome).strip() + (" (comprar por fora)" if self.fora else "")


def _n(t):
    return " ".join(unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().upper().split())


def pode_editar():
    return current_user.pode(*EDITAR)


def _contraste(cor):
    from ..services import planejamento as pl
    return pl.texto_contraste(cor or "#FFFFFF")


def _meu_encarregado():
    """Encarregado do Planejamento que é o usuário logado (pelo nome), para abrir já filtrado."""
    if not current_user.so_encarregado:
        return None
    meu = _n(current_user.nome).split(" ")
    for e in PlanEncarregado.query.filter_by(ativo=True).all():
        en = _n(e.nome).split(" ")
        if en and meu and en[0] == meu[0] and (len(en) == 1 or len(meu) == 1 or en[1] == meu[1]):
            return e.id
    return None


# ---------------------------------------------------------------- filtros e montagem

def filtros():
    """Lê os filtros da tela (os mesmos no PDF, Excel e WhatsApp)."""
    a = request.args

    def _dt(v):
        try:
            return date.fromisoformat(v) if v else None
        except ValueError:
            return None
    ref = _dt(a.get("semana")) or date.today()
    seg = ref - timedelta(days=ref.weekday())
    de, ate = _dt(a.get("de")), _dt(a.get("ate"))
    periodo = bool(de or ate)
    if periodo:
        de, ate = de or ate, ate or de
        if ate < de:
            de, ate = ate, de
        ate = min(ate, de + timedelta(days=62))
        seg = de - timedelta(days=de.weekday())
    else:
        de, ate = seg, seg + timedelta(days=5)
    dom = a.get("dom") == "1"
    dias = [de + timedelta(days=i) for i in range((ate - de).days + 1)]
    dias = [d for d in dias if dom or d.weekday() != 6]
    enc_id = a.get("enc", type=int)
    if enc_id is None and "enc" not in a:
        enc_id = _meu_encarregado()
    tipos = [t for t in a.getlist("tipo") if t in ROTULOS] or list(ROTULOS)
    return {"seg": seg, "de": de, "ate": ate, "periodo": periodo, "dom": dom, "dias": dias, "enc_id": enc_id,
            "obra_id": a.get("obra", type=int), "q": (a.get("q") or "").strip(), "tipos": tipos}


def _args(f, **extra):
    """Os filtros como parâmetros de URL (para os botões PDF / Excel / WhatsApp e a navegação)."""
    out = {"semana": f["seg"].isoformat(), "enc": f["enc_id"] or "", "obra": f["obra_id"] or "",
           "q": f["q"] or None, "dom": "1" if f["dom"] else None}
    if f["periodo"]:
        out.update(de=f["de"].isoformat(), ate=f["ate"].isoformat())
    if set(f["tipos"]) != set(ROTULOS):
        out["tipo"] = f["tipos"]
    out.update(extra)
    return {k: v for k, v in out.items() if v not in (None,)}


_cache_obra = {}


def _obra_sistema(po):
    """Obra do sistema (para a solicitação) de uma obra do Planejamento sem ligação: pelo nome do rateio / nome."""
    if po is None:
        return None
    if po.id in _cache_obra:
        return _cache_obra[po.id]
    achou = None
    alvos = [_n(x) for x in (po.centro_custo, po.nome) if x]
    for o in Obra.query.filter(Obra.status == "Em andamento").all():
        on = _n(o.nome)
        if any(a and (a == on or (len(a) >= 5 and a in on)) for a in alvos):
            achou = o.id
            break
    _cache_obra[po.id] = achou
    return achou


def _sol_aberta(s):
    return not getattr(s, "cancelada", False) and not getattr(s, "finalizada_em", None) and s.status != "Cancelada"


def montar(f):
    """{dia: [itens]} já filtrado (o calendário do caminhão, sem coluna de encarregado).
    Itens: vaga (pré-reserva — em branco ou com obra, com as solicitações encaixadas), fixa, solicitação ainda não
    encaixada, retirada de material, entulho."""
    dias = f["dias"]
    d0, d1 = dias[0], dias[-1]
    po_por_obra = {}
    for po in PlanObra.query.filter(PlanObra.tipo == "obra").all():
        if po.obra_id and (po.ativo or po.obra_id not in po_por_obra):
            po_por_obra[po.obra_id] = po
    encs = {e.id: e for e in PlanEncarregado.query.all()}
    grade = defaultdict(list)
    filtro_po = db.session.get(PlanObra, f["obra_id"]) if f["obra_id"] else None

    def add(po, eid, d, item, obra_sistema=None, vaga_branca=False):
        if d not in dias:
            return
        t = "provisionada" if item["tipo"] in ("vaga", "fixa") else item["tipo"]
        if t not in f["tipos"]:
            return
        eid = eid if eid is not None else (po.encarregado_id if po else None)
        if not vaga_branca:   # vaga em branco aparece em qualquer filtro (é para encaixar)
            if f["enc_id"] and eid != f["enc_id"]:
                return
            if filtro_po and not (po and po.id == filtro_po.id) and not (obra_sistema and obra_sistema == filtro_po.obra_id):
                return
        item.setdefault("obra", po.nome if po else "")
        item.setdefault("cor", po.cor_final if po else "#FFFFFF")
        item["enc"] = encs[eid].nome if eid in encs else ""
        item["busca"] = _n(" ".join([item["obra"], item["rot"], item.get("sub", ""), item["enc"]]
                                    + [x["rot"] + " " + x["obra"] for x in item.get("encaixes", [])]))
        if f["q"] and _n(f["q"]) not in item["busca"] and not vaga_branca:
            return
        grade[d].append(item)

    def sol_item(s, po):
        return {"tipo": "solicitacao", "sid": s.id, "cor": CORES["solicitacao"], "rot": f"📦 {s.numero}",
                "sub": " · ".join(x for x in [s.entrega_hora or "", s.status] if x),
                "obra": s.obra.nome if s.obra else (po.nome if po else ""),
                "link": url_for("solicitacoes.detalhe", sid=s.id)}

    # 1) vagas (pré-reservas) e dias pulados das fixas
    pulos, encaixadas = set(), set()
    for v in CaminhaoViagem.query.filter(CaminhaoViagem.data >= d0, CaminhaoViagem.data <= d1) \
            .order_by(CaminhaoViagem.ordem.is_(None), CaminhaoViagem.ordem, CaminhaoViagem.id).all():
        if v.tipo == "pular":
            pulos.add((v.regra_id, v.data))
            continue
        po = v.plan_obra or (po_por_obra.get(v.obra_id) if v.obra_id else None)
        encx = []
        for e in v.encaixes:
            s = e.solicitacao
            if s is None:
                continue
            encaixadas.add(s.id)
            it = sol_item(s, po_por_obra.get(s.obra_id))
            it["eid"] = e.id
            encx.append(it)
        branca = not po and not v.obra_id
        nome = po.nome if po else (v.obra.nome if v.obra else "")
        add(po, v.encarregado_id if not po else None, v.data,
            {"tipo": "vaga", "id": v.id, "branca": branca, "obra_id": v.obra_id or _obra_sistema(po), "seq": 0, "encaixes": encx, "obra": nome, "obs": v.descricao or "",
             "itens": [{"id": i.id, "texto": i.texto, "fora": i.fora, "insumo_id": i.insumo_id, "descricao": i.descricao if i.fora else (i.insumo.nome if i.insumo else ""),
                        "quantidade": i.quantidade, "unidade": i.unidade or ""} for i in v.itens],
             "cor": "#FFFFFF" if branca else (po.cor_final if po else "#E5E7EB"),
             "rot": ("⬜ Vaga do caminhão" if branca else "📌 " + nome),
             "sub": v.descricao or "", "por": v.criado_por or ""}, v.obra_id, vaga_branca=branca)
    # 2) fixas antigas (se alguma ainda estiver ligada)
    for rg in CaminhaoRegra.query.filter_by(ativo=True).all():
        po = rg.plan_obra or (po_por_obra.get(rg.obra_id) if rg.obra_id else None)
        for d in dias:
            if d.weekday() in rg.dias_lista and (rg.id, d) not in pulos:
                add(po, rg.encarregado_id, d, {"tipo": "fixa", "regra": rg.id, "cor": rg.cor or ROSA,
                                               "rot": "📌 " + (po.nome if po else "Entrega provisionada"),
                                               "sub": rg.obs or f"fixa: toda {rg.dias_txt}", "obra": rg.obra_nome}, rg.obra_id)
    # 3) solicitações com data de entrega que ainda não foram encaixadas numa vaga
    for s in Solicitacao.query.filter(Solicitacao.precisa_ate >= d0, Solicitacao.precisa_ate <= d1).all():
        if _sol_aberta(s) and s.id not in encaixadas:
            po = po_por_obra.get(s.obra_id)
            add(po, None, s.precisa_ate, sol_item(s, po), s.obra_id)
    # 4) retiradas do motorista
    try:
        from .retirada_material import RetiradaMaterial
        for r in RetiradaMaterial.query.filter(RetiradaMaterial.data >= d0, RetiradaMaterial.data <= d1,
                                               RetiradaMaterial.status != "Cancelada").all():
            ob = db.session.get(Obra, r.obra_id) if r.obra_id else None
            add(po_por_obra.get(r.obra_id), None, r.data, {"tipo": "retirada", "cor": CORES["retirada"], "rot": f"♻ {r.numero}",
                                                           "sub": "retirada de material · " + r.status, "obra": ob.nome if ob else "",
                                                           "link": url_for("solicitacoes.retirada.lista")}, r.obra_id)
    except Exception:  # noqa: BLE001 — a tela nunca cai por causa de um módulo
        db.session.rollback()
    try:
        from .entulho import RetiradaEntulho
        for r in RetiradaEntulho.query.filter(RetiradaEntulho.status != "Cancelada",
                                              db.or_(RetiradaEntulho.data.between(d0, d1),
                                                     RetiradaEntulho.data_agendada.between(d0, d1))).all():
            if (r.retirado_por or "motorista") != "motorista":
                continue   # terceirizado não ocupa o caminhão
            ob = db.session.get(Obra, r.obra_id) if r.obra_id else None
            add(po_por_obra.get(r.obra_id), None, r.data_agendada or r.data,
                {"tipo": "entulho", "cor": CORES["entulho"], "rot": f"🚛 {r.numero}", "sub": "entulho · " + r.status,
                 "obra": ob.nome if ob else r.cc, "link": url_for("solicitacoes.entulho.lista")}, r.obra_id)
    except Exception:  # noqa: BLE001
        db.session.rollback()
    ordem = {"vaga": 0, "fixa": 1, "solicitacao": 2, "retirada": 3, "entulho": 4}
    for d in grade:   # vagas na ordem da rota (arrastada pelo gestor); o resto depois
        grade[d].sort(key=lambda i: (ordem.get(i["tipo"], 9), 0 if i["tipo"] == "vaga" else (i.get("branca", False), _n(i.get("obra")))))
        n = 0
        for i in grade[d]:
            if i["tipo"] == "vaga":
                n += 1
                i["seq"] = n
    return grade


def a_encaixar(f):
    """Solicitações em aberto que ainda não estão em nenhuma vaga do caminhão (para arrastar)."""
    ja = {e.solicitacao_id for e in CaminhaoEncaixe.query.all()}
    po_por_obra = {po.obra_id: po for po in PlanObra.query.filter(PlanObra.obra_id.isnot(None)).all()}
    out = []
    for s in Solicitacao.query.filter(Solicitacao.cancelada.isnot(True), Solicitacao.finalizada_em.is_(None)) \
            .order_by(Solicitacao.precisa_ate.is_(None), Solicitacao.precisa_ate, Solicitacao.id).limit(300).all():
        if s.id in ja or not _sol_aberta(s) or s.status in ("Entregue", "Atendida"):
            continue
        po = po_por_obra.get(s.obra_id)
        if f["enc_id"] and not (po and po.encarregado_id == f["enc_id"]):
            continue
        if f["obra_id"] and not (po and po.id == f["obra_id"]):
            continue
        out.append({"sid": s.id, "num": s.numero, "obra": s.obra.nome if s.obra else "", "quando": s.precisa_ate,
                    "status": s.status, "cor": po.cor_final if po else "#E5E7EB",
                    "busca": _n(f"{s.numero} {s.obra.nome if s.obra else ''} {s.status}")})
    return out


# ---------------------------------------------------------------- tela

@bp.route("/")
@perfil_requerido(*VER)
def semana():
    from ..services import planejamento as pl
    f = filtros()
    grade = montar(f)
    grupos = pl.obras_por_encarregado()
    if f["enc_id"]:
        grupos = [(e, obs) for e, obs in grupos if e and e.id == f["enc_id"]] or grupos
    total = sum(len(v) for v in grade.values())
    antigas = PlanObra.query.filter(PlanObra.tipo == "obra", PlanObra.ativo.isnot(True)).order_by(PlanObra.nome).all()
    return render_template("caminhao/semana.html", f=f, grade=grade, grupos=grupos, total=total, antigas=antigas, pendentes=a_encaixar(f),
                           encs=PlanEncarregado.query.filter_by(ativo=True).order_by(PlanEncarregado.nome).all(),
                           todas_obras=sorted(pl.obras_plan("obra"), key=lambda o: _n(o.nome)),
                           regras=CaminhaoRegra.query.filter_by(ativo=True).all(), editar=pode_editar(),
                           hoje=date.today(), DIAS=DIAS, ROSA=ROSA, ROTULOS=ROTULOS, CORES=CORES,
                           contraste=_contraste, args=_args, timedelta=timedelta)


def _volta():
    v = request.form.get("volta") or ""
    return redirect(v if v.startswith("/") and not v.startswith("//") else url_for("caminhao.semana"))


@bp.route("/marcar", methods=["POST"])
@perfil_requerido(*EDITAR)
def marcar():
    """Pincel: obra escolhida no alto + clique no dia = inclui a entrega provisionada (clicar de novo tira)."""
    po = db.session.get(PlanObra, request.form.get("obra", type=int) or 0)
    try:
        d = date.fromisoformat(request.form.get("data") or "")
    except ValueError:
        return jsonify(ok=False, msg="Dia inválido.")
    if request.form.get("vaga"):   # vaga em branco: o caminhão fica pré-reservado no dia, a obra entra depois
        db.session.add(CaminhaoViagem(data=d, criado_por=current_user.nome))
        db.session.commit()
        return jsonify(ok=True, msg=f"Vaga do caminhão aberta em {DIAS[d.weekday()]} {d:%d/%m} — arraste a obra ou a solicitação para dentro.")
    if not po:
        return jsonify(ok=False, msg="Escolha a obra no alto primeiro.")
    pos = request.form.get("pos", type=int)
    existe = None if pos is not None else CaminhaoViagem.query.filter_by(tipo="viagem", plan_obra_id=po.id, data=d).first()
    if pos is not None:   # arrastou a obra para o meio das vagas do dia: abre uma vaga NOVA ali (não troca a outra)
        nova = CaminhaoViagem(data=d, plan_obra_id=po.id, obra_id=po.obra_id, encarregado_id=po.encarregado_id,
                              criado_por=current_user.nome)
        db.session.add(nova)
        db.session.flush()
        outras = CaminhaoViagem.query.filter(CaminhaoViagem.data == d, CaminhaoViagem.tipo == "viagem",
                                             CaminhaoViagem.id != nova.id) \
            .order_by(CaminhaoViagem.ordem.is_(None), CaminhaoViagem.ordem, CaminhaoViagem.id).all()
        pos = max(0, min(pos, len(outras)))
        outras.insert(pos, nova)
        for k, x in enumerate(outras, 1):
            x.ordem = k
        db.session.commit()
        return jsonify(ok=True, msg=f"{po.nome}: {pos + 1}ª entrega de {DIAS[d.weekday()]} {d:%d/%m}.")
    if existe:
        db.session.delete(existe)
        msg = f"{po.nome}: entrega de {d:%d/%m} tirada."
    else:
        db.session.add(CaminhaoViagem(data=d, plan_obra_id=po.id, obra_id=po.obra_id, encarregado_id=po.encarregado_id,
                                      descricao=(request.form.get("descricao") or "").strip()[:200] or None,
                                      criado_por=current_user.nome))
        msg = f"{po.nome}: entrega provisionada em {DIAS[d.weekday()]} {d:%d/%m}."
    db.session.commit()
    return jsonify(ok=True, msg=msg, tirou=bool(existe))


@bp.route("/encaixar", methods=["POST"])
@perfil_requerido(*EDITAR)
def encaixar():
    """Arrastar para dentro da vaga: obra (preenche a vaga em branco / troca a obra) ou solicitação (encaixa o
    pedido na pré-reserva). Solicitação solta num dia sem vaga abre a vaga da obra dela nesse dia."""
    fm = request.form
    v = db.session.get(CaminhaoViagem, fm.get("vaga", type=int) or 0)
    po = db.session.get(PlanObra, fm.get("obra", type=int) or 0)
    sol = db.session.get(Solicitacao, fm.get("sol", type=int) or 0)
    if v is None:
        try:
            d = date.fromisoformat(fm.get("data") or "")
        except ValueError:
            return jsonify(ok=False, msg="Solte dentro de uma vaga ou de um dia.")
        if not sol:
            return jsonify(ok=False, msg="Nada para encaixar.")
        po_s = PlanObra.query.filter_by(obra_id=sol.obra_id).first() if sol.obra_id else None
        v = CaminhaoViagem(data=d, plan_obra_id=po_s.id if po_s else None, obra_id=sol.obra_id,
                           encarregado_id=po_s.encarregado_id if po_s else None, criado_por=current_user.nome)
        db.session.add(v)
        db.session.flush()
    msgs = []
    if po:
        v.plan_obra_id, v.obra_id, v.encarregado_id = po.id, po.obra_id, po.encarregado_id
        msgs.append(f"vaga de {v.data:%d/%m} agora é {po.nome}")
    if sol:
        CaminhaoEncaixe.query.filter_by(solicitacao_id=sol.id).delete()   # sai de outra vaga, se estava
        db.session.add(CaminhaoEncaixe(viagem_id=v.id, solicitacao_id=sol.id, criado_por=current_user.nome))
        if not v.plan_obra_id and not v.obra_id:   # vaga em branco assume a obra do pedido
            po_s = PlanObra.query.filter_by(obra_id=sol.obra_id).first() if sol.obra_id else None
            v.obra_id = sol.obra_id
            if po_s:
                v.plan_obra_id, v.encarregado_id = po_s.id, po_s.encarregado_id
        from ..services import estoque as est
        est.historico(sol, "Encaixada no caminhão", f"vaga de {DIAS[v.data.weekday()]} {v.data:%d/%m/%Y}", current_user.nome)
        msgs.append(f"{sol.numero} encaixada no caminhão de {v.data:%d/%m}")
    db.session.commit()
    return jsonify(ok=True, msg=("; ".join(msgs) or "Nada mudou.").capitalize())


@bp.route("/vaga/<int:vid>/itens", methods=["POST"])
@perfil_requerido(*EDITAR)
def vaga_itens(vid):
    """Observação e itens da vaga (a obra e o dia já são os da vaga): itens do estoque e itens comprados por fora."""
    import json
    from ..models import Insumo
    v = db.get_or_404(CaminhaoViagem, vid)
    v.descricao = (request.form.get("obs") or "").strip()[:200] or None
    try:
        linhas = json.loads(request.form.get("itens") or "[]")
    except ValueError:
        return jsonify(ok=False, msg="Itens inválidos.")
    for i in list(v.itens):
        db.session.delete(i)
    n = 0
    for ln in linhas[:60]:
        ins = db.session.get(Insumo, int(ln.get("insumo_id") or 0)) if str(ln.get("insumo_id") or "").isdigit() else None
        desc = " ".join(str(ln.get("descricao") or "").split())[:200]
        if not ins and not desc:
            continue
        try:
            qtd = float(str(ln.get("quantidade") or "").replace(",", ".")) or None
        except ValueError:
            qtd = None
        db.session.add(CaminhaoItem(viagem_id=v.id, insumo_id=ins.id if ins else None, descricao=ins.nome if ins else desc,
                                    quantidade=qtd, unidade=(ins.unidade if ins else (ln.get("unidade") or "").strip()[:20]) or None,
                                    criado_por=current_user.nome))
        n += 1
    db.session.commit()
    return jsonify(ok=True, msg=f"Vaga de {v.data:%d/%m}: observação e {n} item(ns) salvos.")


@bp.route("/vaga/<int:vid>/mover", methods=["POST"])
@perfil_requerido(*EDITAR)
def vaga_mover(vid):
    """Arrastar a vaga (com tudo que está dentro) para outro dia — como mover a obra de dia na planilha."""
    v = db.get_or_404(CaminhaoViagem, vid)
    try:
        d = date.fromisoformat(request.form.get("data") or "")
    except ValueError:
        return jsonify(ok=False, msg="Dia inválido.")
    de = v.data
    pos = request.form.get("pos", type=int)
    v.data = d
    # reordena as vagas do dia: a arrastada entra na posição solta (1ª, 2ª... entrega da rota)
    outras = [x for x in CaminhaoViagem.query.filter(CaminhaoViagem.data == d, CaminhaoViagem.tipo == "viagem",
                                                     CaminhaoViagem.id != v.id)
              .order_by(CaminhaoViagem.ordem.is_(None), CaminhaoViagem.ordem, CaminhaoViagem.id).all()]
    pos = len(outras) if pos is None else max(0, min(pos, len(outras)))
    outras.insert(pos, v)
    for k, x in enumerate(outras, 1):
        x.ordem = k
    if d == de:
        db.session.commit()
        nome = v.plan_obra.nome if v.plan_obra else (v.obra.nome if v.obra else "Vaga")
        return jsonify(ok=True, msg=f"{nome}: agora é a {pos + 1}ª entrega de {DIAS[d.weekday()]} {d:%d/%m}.")
    from ..services import estoque as est
    for e in v.encaixes:
        if e.solicitacao:
            est.historico(e.solicitacao, "Caminhão remarcado", f"de {de:%d/%m} para {DIAS[d.weekday()]} {d:%d/%m}",
                          current_user.nome)
    db.session.commit()
    nome = v.plan_obra.nome if v.plan_obra else (v.obra.nome if v.obra else "Vaga")
    return jsonify(ok=True, msg=f"{nome}: {DIAS[de.weekday()]} {de:%d/%m} → {DIAS[d.weekday()]} {d:%d/%m}.")


@bp.route("/desencaixar/<int:eid>", methods=["POST"])
@perfil_requerido(*EDITAR)
def desencaixar(eid):
    e = db.get_or_404(CaminhaoEncaixe, eid)
    num = e.solicitacao.numero if e.solicitacao else ""
    db.session.delete(e)
    db.session.commit()
    return jsonify(ok=True, msg=f"{num} saiu da vaga (volta para a lista de solicitações a encaixar).")


@bp.route("/viagem", methods=["POST"])
@perfil_requerido(*EDITAR)
def viagem():
    """Formulário: obra + data (ou vários dias) + o que vai."""
    fm = request.form
    po = db.session.get(PlanObra, fm.get("obra", type=int) or 0)
    datas = []
    for v in fm.getlist("data"):
        try:
            datas.append(date.fromisoformat(v))
        except ValueError:
            pass
    if not po or not datas:
        flash("Escolha a obra e a data.", "danger")
        return _volta()
    for d in datas:
        db.session.add(CaminhaoViagem(data=d, plan_obra_id=po.id, obra_id=po.obra_id, encarregado_id=po.encarregado_id,
                                      descricao=(fm.get("descricao") or "").strip()[:200] or None, criado_por=current_user.nome))
    db.session.commit()
    flash(f"{po.nome}: entrega provisionada em " + ", ".join(f"{d:%d/%m}" for d in datas) + ".", "success")
    return _volta()


@bp.route("/viagem/<int:vid>/excluir", methods=["POST"])
@perfil_requerido(*EDITAR)
def viagem_excluir(vid):
    v = db.get_or_404(CaminhaoViagem, vid)
    for e in list(v.encaixes):
        db.session.delete(e)
    db.session.delete(v)
    db.session.commit()
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify(ok=True, msg="Entrega tirada do planejamento.")
    flash("Entrega tirada do planejamento.", "info")
    return _volta()


@bp.route("/pular", methods=["POST"])
@perfil_requerido(*EDITAR)
def pular():
    """Tira (ou devolve) a entrega fixa só de um dia."""
    rg = db.get_or_404(CaminhaoRegra, request.form.get("regra_id", type=int))
    try:
        d = date.fromisoformat(request.form.get("data") or "")
    except ValueError:
        abort(400)
    existe = CaminhaoViagem.query.filter_by(tipo="pular", regra_id=rg.id, data=d).first()
    if existe:
        db.session.delete(existe)
    else:
        db.session.add(CaminhaoViagem(tipo="pular", regra_id=rg.id, data=d, encarregado_id=rg.encarregado_id,
                                      criado_por=current_user.nome))
    db.session.commit()
    msg = "Entrega fixa " + ("devolvida" if existe else "tirada") + f" em {d:%d/%m}."
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify(ok=True, msg=msg)
    flash(msg, "info")
    return _volta()


@bp.route("/regra", methods=["POST"])
@perfil_requerido(*EDITAR)
def regra():
    fm = request.form
    rid = fm.get("id", type=int)
    if fm.get("acao") == "excluir" and rid:
        rg = db.get_or_404(CaminhaoRegra, rid)
        rg.ativo = False
        db.session.commit()
        flash("Entrega fixa desligada.", "info")
        return _volta()
    po = db.session.get(PlanObra, fm.get("obra", type=int) or 0)
    eid = fm.get("encarregado_id", type=int) or (po.encarregado_id if po else None)
    dias = sorted({int(x) for x in fm.getlist("dias") if x.isdigit() and int(x) < 7})
    if not eid or not dias:
        flash("Escolha o encarregado (ou a obra) e pelo menos um dia da semana.", "danger")
        return _volta()
    rg = db.get_or_404(CaminhaoRegra, rid) if rid else CaminhaoRegra(criado_por=current_user.nome)
    rg.encarregado_id = eid
    rg.plan_obra_id, rg.obra_id = (po.id, po.obra_id) if po else (None, None)
    rg.dias = ",".join(str(d) for d in dias)
    rg.cor = fm.get("cor") or ROSA
    rg.obs = (fm.get("obs") or "").strip()[:200] or None
    rg.ativo = True
    db.session.add(rg)
    db.session.commit()
    flash(f"Entrega fixa salva: {rg.encarregado.nome if rg.encarregado else ''} toda {rg.dias_txt}.", "success")
    return _volta()


# ---------------------------------------------------------------- saídas: Excel, PDF e WhatsApp

def _txt(it):
    t = it["rot"].lstrip("📌📦♻🚛⬜ ")
    if it.get("obra") and it["obra"] not in t:
        t += f" ({it['obra']})"
    if it.get("itens"):
        t += " · leva: " + "; ".join(x["texto"] for x in it["itens"])
    if it.get("encaixes"):
        t += " ← " + ", ".join(x["rot"].lstrip("📦 ") + (f" {x['obra']}" if x.get("obra") and x["obra"] not in t else "") for x in it["encaixes"])
    return t


def _itens(f, grade):
    for d in f["dias"]:
        for it in grade.get(d, []):
            yield d, it


@bp.route("/excel")
@perfil_requerido(*VER)
def excel():
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    f = filtros()
    grade = montar(f)
    wb = Workbook()
    ws = wb.active
    ws.title = "Por dia"
    ws.append([f"Planejamento do caminhão · {f['dias'][0]:%d/%m/%Y} a {f['dias'][-1]:%d/%m/%Y}"])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append([])
    ws.append(["Data", "Dia", "Tipo", "Obra", "Item", "Solicitações encaixadas", "Encarregado", "Observação"])
    for c in ws[3]:
        c.font, c.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="00304E")
    for d, it in _itens(f, grade):
        tipo = "Vaga em branco" if it.get("branca") else ("Vaga (provisionada)" if it["tipo"] == "vaga" else ROTULOS.get(it["tipo"], ""))
        ws.append([d, DIAS[d.weekday()], tipo, it.get("obra", ""), it["rot"].lstrip("📌📦♻🚛⬜ "),
                   ", ".join(x["rot"].lstrip("📦 ") + (f" ({x['obra']})" if x.get("obra") else "") for x in it.get("encaixes", [])),
                   it.get("enc", ""), it.get("sub", "")])
        ws.cell(ws.max_row, 1).number_format = "DD/MM/YYYY"
        ws.cell(ws.max_row, 3).fill = PatternFill("solid", fgColor=(it.get("cor") or "#FFFFFF").lstrip("#")[:6])
    for col, larg in zip("ABCDEFGH", (12, 6, 20, 30, 28, 40, 22, 34)):
        ws.column_dimensions[col].width = larg
    g2 = wb.create_sheet("Calendário")
    g2.append([f"{DIAS[d.weekday()]} {d:%d/%m}" for d in f["dias"]])
    for c in g2[1]:
        c.font, c.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="00304E")
    g2.append(["\n".join(_txt(it) for it in grade.get(d, [])) for d in f["dias"]])
    for c in g2[2]:
        c.alignment = Alignment(wrap_text=True, vertical="top")
    for i in range(len(f["dias"])):
        g2.column_dimensions[chr(65 + i) if i < 26 else "Z"].width = 32
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=f"caminhao-{f['dias'][0]:%d.%m.%y}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@bp.route("/pdf")
@perfil_requerido(*VER)
def pdf():
    f = filtros()
    return send_file(io.BytesIO(_pdf_bytes(f)), mimetype="application/pdf", as_attachment=bool(request.args.get("baixar")),
                     download_name=f"caminhao-{f['dias'][0]:%d.%m.%y}.pdf")


def _serial():
    from itsdangerous import URLSafeSerializer
    from flask import current_app
    return URLSafeSerializer(current_app.config["SECRET_KEY"], salt="caminhao-ver")


def link_layout(f, enc_id=None):
    """Link (sem login) que abre o quadro do caminhão no mesmo layout da tela, em PDF."""
    a = _args(f)
    a["enc"] = enc_id or ""
    return url_for("caminhao.ver", token=_serial().dumps(a), _external=True)


@bp.route("/ver/<token>")
def ver(token):
    """Abre o quadro do caminhão enviado pelo WhatsApp (sem login)."""
    from flask import current_app, abort
    try:
        a = _serial().loads(token)
    except Exception:  # noqa: BLE001
        abort(404)
    with current_app.test_request_context(query_string=a):
        f = filtros()
        dados = _pdf_bytes(f, enc_id=f["enc_id"])
    return send_file(io.BytesIO(dados), mimetype="application/pdf", download_name=f"caminhao-{f['dias'][0]:%d.%m.%y}.pdf")


def _pdf_bytes(f, enc_id=None):
    from datetime import datetime
    from ..services import plan_pdf as pp
    grade = montar(f)
    if enc_id:   # só o que é daquele encarregado
        e = db.session.get(PlanEncarregado, enc_id)
        if e:
            grade = {d: [it for it in v if it.get("enc") == e.nome] for d, v in grade.items()}
    p = pp._pdf()
    W = 420 - 16
    sub = (f"{f['dias'][0]:%d/%m/%Y} a {f['dias'][-1]:%d/%m/%Y}" + (f" · busca: {f['q']}" if f["q"] else "")
           + f" · gerado em {datetime.now():%d/%m/%Y %H:%M}")
    for i0 in range(0, len(f["dias"]), 7):
        dias = f["dias"][i0:i0 + 7]
        p.add_page()
        pp._titulo(p, "Planejamento do caminhão", sub)
        w = W / len(dias)
        y0 = 20
        p.set_font("dv", "B", 8.5)
        p.set_fill_color(0, 48, 78)
        p.set_text_color(255, 255, 255)
        for i, d in enumerate(dias):
            p.set_xy(8 + i * w, y0)
            p.cell(w, 7, f"{DIAS[d.weekday()]} {d:%d/%m}", border=1, fill=True, align="C")
        for i, d in enumerate(dias):
            x, yy = 8 + i * w, y0 + 8
            for it in grade.get(d, []):
                p.set_font("dv", "B" if it["tipo"] in ("vaga", "fixa") else "", 7)
                txt = pp._linhas(p, _txt(it) + (" · " + it["sub"] if it.get("sub") else ""), w - 3)
                h = 3.4 * len(txt) + 0.8
                if yy + h > 288:
                    break
                cor = it.get("cor") or "#FFFFFF"
                p.set_fill_color(*pp._rgb(cor))
                p.set_draw_color(148, 163, 184)
                p.rect(x + 0.6, yy, w - 1.2, h, style="DF")
                p.set_text_color(*pp._txt(cor))
                for k, ln in enumerate(txt):
                    p.set_xy(x + 1.4, yy + 0.4 + k * 3.4)
                    p.cell(w - 3, 3.4, ln)
                yy += h + 0.8
        p.set_xy(8, 289)
        p.set_font("dv", "", 7)
        p.set_text_color(100, 116, 139)
        p.cell(0, 4, "Vaga = caminhão pré-reservado no dia (em branco até encaixar a obra ou a solicitação) · Solicitação · Retirada de material · Entulho (motorista)")
    return bytes(p.output())


def texto_whatsapp(f, grade, enc_nome=None):
    """Texto do caminhão no período (todo, ou só o que é de um encarregado)."""
    linhas = [f"🚚 *Planejamento do caminhão{(' — ' + enc_nome) if enc_nome else ''}*",
              f"{f['dias'][0]:%d/%m} a {f['dias'][-1]:%d/%m/%Y}", ""]
    tem = False
    for d in f["dias"]:
        its = [it for it in grade.get(d, []) if not enc_nome or it.get("enc") == enc_nome]
        if not its:
            continue
        tem = True
        linhas.append(f"*{DIAS[d.weekday()]} {d:%d/%m}*")
        for it in its:
            sub = f" — {it['sub']}" if it.get("sub") and it["tipo"] == "vaga" else ""
            if it.get("branca") and not it.get("encaixes"):
                txt = "• Vaga do caminhão (obra a definir)" + ((" · leva: " + "; ".join(x["texto"] for x in it["itens"])) if it.get("itens") else "")
            else:
                txt = "• " + _txt(it)
            linhas.append(txt + sub)
        linhas.append("")
    if not tem:
        linhas.append("Sem entregas do caminhão no período.")
    return "\n".join(linhas).strip()


@bp.route("/whatsapp")
@perfil_requerido(*VER)
def whatsapp():
    f = filtros()
    grade = montar(f)
    nomes = sorted({it["enc"] for _d, it in _itens(f, grade) if it.get("enc")})
    encs = {e.nome: e for e in PlanEncarregado.query.filter(PlanEncarregado.nome.in_(nomes or [""])).all()}
    def _msg(nome, eid):
        return (f"🚚 *Planejamento do caminhão{(' — ' + nome) if nome else ''}*\n"
                f"{f['dias'][0]:%d/%m} a {f['dias'][-1]:%d/%m/%Y}\n\n"
                f"Veja o quadro (mesmo layout do sistema):\n{link_layout(f, eid)}")
    textos = [(encs[n], _msg(n, encs[n].id)) for n in nomes if n in encs]
    geral = _msg(None, None)
    from ..services.notificacoes import telefone_internacional
    return render_template("caminhao/whatsapp.html", f=f, textos=textos, geral=geral, args=_args,
                           fone=lambda e: (telefone_internacional(e.telefone) or "").lstrip("+") if e and e.telefone else "")


@bp.route("/whatsapp/enviar", methods=["POST"])
@perfil_requerido(*VER)
def whatsapp_enviar():
    """Envio automático (Evolution / CallMeBot, o que estiver ligado) para o WhatsApp do encarregado."""
    from ..services.notificacoes import _enviar_callmebot
    e = db.session.get(PlanEncarregado, request.form.get("eid", type=int) or 0)
    texto = (request.form.get("texto") or "").strip()
    if not e or not texto:
        return jsonify(ok=False, msg="Encarregado ou texto vazio.")
    try:
        ok, msg = _enviar_callmebot(e, texto[:3500])
    except Exception as ex:  # noqa: BLE001
        ok, msg = False, f"falha no envio ({ex.__class__.__name__})"
    from ..models import LogIntegracao
    db.session.add(LogIntegracao(sistema="whatsapp", operacao="Planejamento do caminhão → WhatsApp", sucesso=ok,
                                 mensagem=f"{e.nome}: {msg}"[:500], usuario=current_user.nome))
    db.session.commit()
    return jsonify(ok=ok, msg=(f"Enviado para {e.nome}." if ok else f"{e.nome}: não enviou — {msg}. Use o botão Abrir no WhatsApp."))
