from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from .. import perfil_requerido
from ..extensions import db
from ..models import PERFIS, PERFIS_APROVADORES, Usuario

bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")

PERMISSOES = {
    "admin": "Tudo, inclusive usuários, depósitos e integrações.",
    "almoxarife": "Estoque central, entradas, transferências, inventário, separar e enviar solicitações.",
    "encarregado": "Criar solicitações para as obras, pedir compra do que não tem, ver estoque por obra e registrar consumo.",
    "consulta": "Só consulta: resumo, obras, estoque central e por obra, insumos e materiais a comprar. Pode pedir compra.",
    "almox_compras": "Tudo do Almoxarife e tudo de Compras (para quem faz as duas funções).",
    "compras": "Materiais a comprar: recebe os pedidos (com aviso no WhatsApp), cota, autoriza e registra o recebimento. Vê o DDA (boletos a lançar).",
    "motorista": "Só a Rota do motorista: entregas por dia, endereço de cada obra (com link do mapa), quem recebe e o material.",
}


def editor_permissoes():
    """Usuário que travou para si o controle do que cada um vê (menu, perfil e alçada). None = qualquer admin."""
    from ..models import Configuracao
    v = (Configuracao.obter("permissoes_editor") or "").strip()
    return int(v) if v.isdigit() else None


def pode_permissoes(u=None):
    u = u or current_user
    ed = editor_permissoes()
    return u.is_authenticated and u.perfil == "admin" and (ed is None or ed == u.id)


@bp.route("/")
@perfil_requerido()
def lista():
    from ..views.menu import menu_oculto
    ed = editor_permissoes()
    return render_template("usuarios/lista.html", usuarios=Usuario.query.order_by(Usuario.nome).all(),
                           perfis=PERFIS, permissoes=PERMISSOES, menu_oculto=menu_oculto,
                           editor=db.session.get(Usuario, ed) if ed else None, pode_perm=pode_permissoes())


@bp.route("/travar-permissoes", methods=["POST"])
@perfil_requerido()
def travar_permissoes():
    """Só eu altero o que cada usuário vê (ou libero de novo para os outros administradores)."""
    from ..models import Configuracao
    if not pode_permissoes():
        flash("Só quem travou as permissões pode mudar isso.", "danger")
        return redirect(url_for("usuarios.lista"))
    if request.form.get("acao") == "liberar":
        Configuracao.definir("permissoes_editor", "")
        flash("Os outros administradores voltam a poder mudar menus, perfis e alçadas.", "success")
    else:
        Configuracao.definir("permissoes_editor", str(current_user.id))
        flash("Pronto: só você altera o menu, o perfil e a alçada de cada usuário.", "success")
    db.session.commit()
    return redirect(url_for("usuarios.lista"))


@bp.route("/novo", methods=["GET", "POST"])
@bp.route("/<int:uid>/editar", methods=["GET", "POST"])
@perfil_requerido()
def form(uid=None):
    u = db.get_or_404(Usuario, uid) if uid else Usuario(perfil="encarregado", ativo=True)
    if request.method == "POST":
        f = request.form
        login = (f.get("login") or "").strip().lower()
        existente = Usuario.query.filter(Usuario.login == login, Usuario.id != (u.id or 0)).first()
        senha = f.get("senha") or ""
        if not f.get("nome") or not login:
            flash("Nome e login são obrigatórios.", "danger")
        elif existente:
            flash("Já existe um usuário com esse login.", "danger")
        elif not uid and len(senha) < 6:
            flash("Defina uma senha com pelo menos 6 caracteres.", "danger")
        elif u.id == current_user.id and f.get("perfil") != "admin":
            flash("Você não pode tirar o seu próprio perfil de administrador.", "danger")
        else:
            u.nome, u.login = f["nome"].strip(), login
            u.email = (f.get("email") or "").strip() or None
            u.cargo = (f.get("cargo") or "").strip() or None
            u.telefone = (f.get("telefone") or "").strip() or None
            from ..services.notificacoes import validar_chave_callmebot
            chave, erro_chave = validar_chave_callmebot(f.get("callmebot_apikey"), u.telefone)
            u.callmebot_apikey = chave
            if erro_chave:
                flash("A chave do CallMeBot não foi salva: " + erro_chave, "warning")
            u.alerta_estoque = bool(f.get("alerta_estoque"))
            u.aviso_compras = bool(f.get("aviso_compras"))
            u.aviso_reserva = bool(f.get("aviso_reserva"))
            trava = not pode_permissoes()
            perfil_antes, sem_limite_antes, ate_antes = u.perfil, u.aprova_sem_limite, u.aprova_ate
            if u.perfil in PERFIS_APROVADORES:
                from .aprovacoes import valor_br
                u.aprova_sem_limite = bool(f.get("aprova_sem_limite"))
                try:
                    u.aprova_ate = None if u.aprova_sem_limite else valor_br(f.get("aprova_ate"))
                except ValueError:
                    u.aprova_ate = None
                    flash("Valor da alçada inválido; use o formato 2.000,00.", "warning")
            else:
                u.aprova_ate, u.aprova_sem_limite = None, False
            u.perfil = f.get("perfil") if f.get("perfil") in PERFIS else "encarregado"
            if trava and uid:   # permissões travadas por outro administrador: perfil e alçada não mudam
                if (u.perfil, u.aprova_sem_limite, u.aprova_ate) != (perfil_antes, sem_limite_antes, ate_antes):
                    flash("Perfil e alçada não foram alterados: só quem travou as permissões pode mudar.", "warning")
                u.perfil, u.aprova_sem_limite, u.aprova_ate = perfil_antes, sem_limite_antes, ate_antes
            elif trava and u.perfil == "admin":
                u.perfil = "consulta"
                flash("Novo usuário não pode ser criado como administrador enquanto as permissões estão travadas.", "warning")
            u.ativo = bool(f.get("ativo")) or u.id == current_user.id
            if senha:
                u.definir_senha(senha)
                u.trocar_senha = u.id != current_user.id  # senha definida pelo admin é provisória
            if not uid:
                db.session.add(u)
            db.session.commit()
            flash("Usuário salvo.", "success")
            return redirect(url_for("usuarios.lista"))
    return render_template("usuarios/form.html", u=u, perfis=PERFIS, perfis_aprovadores=PERFIS_APROVADORES)


@bp.route("/<int:uid>/senha-provisoria", methods=["POST"])
@perfil_requerido()
def senha_provisoria(uid):
    """Gera uma senha provisória, mostra uma única vez ao admin e obriga a troca no primeiro acesso."""
    import secrets

    from ..services.notificacoes import link_whatsapp
    u = db.get_or_404(Usuario, uid)
    if u.id == current_user.id:
        flash("Para a sua própria senha, use Minha conta.", "warning")
        return redirect(url_for("usuarios.lista"))
    alfabeto = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # sem letras e números que se confundem (O/0, I/1)
    senha = "VD-" + "".join(secrets.choice(alfabeto) for _ in range(6))
    u.definir_senha(senha)
    u.trocar_senha = True
    u.ativo = True
    db.session.commit()
    texto = (f"Olá, {u.nome.split()[0]}! Seu acesso ao sistema de estoque da Vieira Diniz:\n"
             f"{url_for('auth.login', _external=True)}\nLogin: {u.login}\nSenha provisória: {senha}\n"
             "No primeiro acesso o sistema pede para você criar a sua senha.")
    link = link_whatsapp(u.telefone, texto) if u.telefone else None
    return render_template("usuarios/senha_gerada.html", u=u, senha=senha, link=link)


@bp.route("/<int:uid>/menu", methods=["GET", "POST"])
@perfil_requerido()
def menu(uid):
    """Escolher quais itens do menu este usuário vê (dentro do que o perfil dele permite)."""
    from ..views.menu import itens_do_perfil, salvar_menu_oculto
    u = db.get_or_404(Usuario, uid)
    if not pode_permissoes():
        ed = db.session.get(Usuario, editor_permissoes())
        flash(f"O menu de cada usuário só pode ser alterado por {ed.nome if ed else 'quem travou as permissões'}.", "warning")
        return redirect(url_for("usuarios.lista"))
    if request.method == "POST":
        mostrar = set(request.form.getlist("mostrar"))
        todos = {it["endpoint"] for _, lst in itens_do_perfil(u) for it in lst if it["permitido"]}
        salvar_menu_oculto(u, todos - mostrar)
        db.session.commit()
        flash(f"Menu de {u.nome} salvo.", "success")
        return redirect(url_for("usuarios.menu", uid=uid))
    return render_template("usuarios/menu.html", u=u, grupos=itens_do_perfil(u))
