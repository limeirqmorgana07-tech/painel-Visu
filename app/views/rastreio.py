"""Caminhão ao vivo: o celular do motorista manda a posição (GPS) e o escritório acompanha no mapa."""
from datetime import timedelta

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from .. import FUSO, perfil_requerido
from ..extensions import db
from ..models import PosicaoVeiculo, Usuario, agora

bp = Blueprint("rastreio", __name__, url_prefix="/rastreio")
GUARDAR_DIAS = 30


@bp.route("/posicao", methods=["POST"])
@login_required
def posicao():
    """Recebe a posição do celular do motorista (no máximo uma a cada 20 s por usuário)."""
    if not current_user.pode("motorista", "almoxarife"):
        return jsonify(ok=False, msg="Só o motorista compartilha a localização."), 403
    try:
        lat, lng = float(request.form["lat"]), float(request.form["lng"])
    except (KeyError, ValueError):
        return jsonify(ok=False, msg="Posição inválida."), 400
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return jsonify(ok=False, msg="Posição inválida."), 400
    ult = (PosicaoVeiculo.query.filter_by(usuario_id=current_user.id).order_by(PosicaoVeiculo.id.desc()).first())
    if ult and ult.registrado_em and agora() - ult.registrado_em < timedelta(seconds=20):
        return jsonify(ok=True, msg="ok (aguardando intervalo)")
    vel = request.form.get("vel", type=float)
    db.session.add(PosicaoVeiculo(usuario_id=current_user.id, lat=lat, lng=lng,
                                  precisao=request.form.get("prec", type=float),
                                  velocidade=round(vel * 3.6, 1) if vel is not None and vel >= 0 else None))
    if not ult or ult.id % 200 == 0:   # limpeza de vez em quando
        PosicaoVeiculo.query.filter(PosicaoVeiculo.registrado_em < agora() - timedelta(days=GUARDAR_DIAS)).delete()
    db.session.commit()
    return jsonify(ok=True, msg="Localização enviada.")


def _hora_local(dt):
    from datetime import timezone
    return dt.replace(tzinfo=timezone.utc).astimezone(FUSO) if dt else None


@bp.route("/")
@perfil_requerido("almoxarife")
def mapa():
    return render_template("rastreio/mapa.html")


@bp.route("/dados")
@perfil_requerido("almoxarife")
def dados():
    """Última posição de cada motorista (últimas 12 h) e o trajeto do dia."""
    desde = agora() - timedelta(hours=12)
    ini_dia = _hora_local(agora()).replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timezone
    ini_dia_utc = ini_dia.astimezone(timezone.utc).replace(tzinfo=None)
    saida = []
    ids = [i for (i,) in db.session.query(PosicaoVeiculo.usuario_id).filter(PosicaoVeiculo.registrado_em >= desde).distinct()]
    for uid in ids:
        u = db.session.get(Usuario, uid)
        pts = (PosicaoVeiculo.query.filter(PosicaoVeiculo.usuario_id == uid, PosicaoVeiculo.registrado_em >= ini_dia_utc)
               .order_by(PosicaoVeiculo.registrado_em).all())
        ult = PosicaoVeiculo.query.filter_by(usuario_id=uid).order_by(PosicaoVeiculo.id.desc()).first()
        minutos = int((agora() - ult.registrado_em).total_seconds() // 60)
        saida.append({"nome": u.nome if u else "?", "lat": ult.lat, "lng": ult.lng, "precisao": ult.precisao,
                      "velocidade": ult.velocidade, "hora": _hora_local(ult.registrado_em).strftime("%H:%M"),
                      "minutos": minutos, "ao_vivo": minutos <= 3,
                      "trajeto": [[p.lat, p.lng] for p in pts][-600:]})
    return jsonify(veiculos=saida, agora=_hora_local(agora()).strftime("%H:%M:%S"))
