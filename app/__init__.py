import os
from datetime import timezone
from functools import wraps
from zoneinfo import ZoneInfo

import click
from flask import Flask, abort, flash, redirect, request, url_for
from flask_login import current_user

from .config import Config
from .extensions import db, login_manager

FUSO = ZoneInfo("America/Recife")


def perfil_requerido(*perfis):
    """Libera a rota para admin + perfis listados."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            if not current_user.pode(*perfis):
                abort(403)
            return fn(*a, **kw)
        return wrapper
    return deco


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # Render: links com https
    app.config.from_object(Config)
    if config:
        app.config.update(config)

    db.init_app(app)
    login_manager.init_app(app)

    from .models import Usuario

    @login_manager.user_loader
    def carregar(uid):
        u = db.session.get(Usuario, int(uid))
        return u if u and u.ativo else None

    @login_manager.unauthorized_handler
    def nao_autenticado():
        return redirect(url_for("auth.login", proximo=request.full_path.rstrip("?")))

    from .views import registrar_blueprints
    registrar_blueprints(app)
    _filtros(app)
    from .versao import VERSAO
    app.jinja_env.globals["VSTATIC"] = VERSAO  # ?v=1.19.0 nos .js/.css: o navegador pega o arquivo novo a cada versão

    def _omie_info(nota):
        from .services import omie_receb
        info = {"modo": omie_receb.modo(), "etapa": omie_receb.etapa_conferido(), "departamento": None, "deps": [],
                "faltam": []}
        try:
            if nota.empresa and nota.empresa.sistema == "omie":
                info["deps"] = omie_receb.departamentos(nota.empresa)
                if not info["deps"]:  # nunca copiados do Omie: busca agora (uma vez por hora no máximo)
                    info["deps"] = omie_receb.garantir_departamentos(nota.empresa)
                info["departamento"] = omie_receb.departamento_da_nota(nota)
                info["faltam"] = omie_receb.obras_sem_departamento(nota)
        except Exception:  # noqa: BLE001 — a tela da nota não pode cair por causa do Omie
            pass
        return info
    app.jinja_env.globals["omie_info"] = _omie_info
    _cli(app)

    @app.before_request
    def exigir_troca_de_senha():
        from flask_login import current_user as cu
        livres = {"auth.minha_senha", "auth.sair", "static", "main.saude"}  # meu perfil só depois da senha
        if cu.is_authenticated and cu.trocar_senha and request.endpoint not in livres:
            flash("Por segurança, crie a sua senha pessoal antes de continuar.", "warning")
            return redirect(url_for("auth.minha_senha"))

    @app.after_request
    def alertas_estoque_critico(resposta):
        from flask import g
        ids = g.pop("checar_criticos", None)
        if ids:
            try:
                # Envio em segundo plano: a tela responde na hora, sem esperar o WhatsApp.
                from .services.alertas import processar
                from .services.notificacoes import em_segundo_plano
                em_segundo_plano(processar, set(ids), url_for("estoque.central", ver="baixo", _external=True))
            except Exception:  # alerta nunca pode derrubar a operação do usuário
                app.logger.exception("Falha ao processar alerta de estoque crítico")
        return resposta

    @app.before_request
    def menu_por_usuario():
        """Tela escondida do menu do usuário pelo administrador também não abre pelo endereço."""
        from flask_login import current_user as _cu
        if request.method == "GET" and _cu.is_authenticated and request.endpoint:
            from .views.menu import bloqueado
            if bloqueado(_cu, request.endpoint, request.view_args):
                flash("Esta tela não está liberada para o seu usuário. Fale com o administrador.", "warning")
                return redirect(url_for("main.dashboard"))

    @app.after_request
    def registrar_acesso_recente(resposta):
        """Guarda as telas do menu que cada usuário abre (Acesso rápido do Início)."""
        try:
            from flask_login import current_user as _cu
            if (request.method == "GET" and resposta.status_code == 200 and _cu.is_authenticated
                    and not getattr(_cu, "simulando", None)):
                from .views.menu import chave_acesso, registrar_acesso
                chave = chave_acesso(request.endpoint, request.view_args)
                if chave:
                    registrar_acesso(_cu, chave)
        except Exception:  # noqa: BLE001
            app.logger.exception("Falha ao registrar acesso recente")
        return resposta

    _redefinir_senha_admin(app)

    @app.errorhandler(403)
    def proibido(_):
        flash("Seu perfil não tem acesso a essa área.", "warning")
        return redirect(url_for("main.dashboard"))

    return app


def _redefinir_senha_admin(app):
    """Recuperação de acesso: se ADMIN_REDEFINIR_SENHA estiver no Render, redefine a senha do usuário
    ADMIN_LOGIN (padrão "admin") ao iniciar. Depois de entrar, APAGUE a variável no Render."""
    nova = (os.environ.get("ADMIN_REDEFINIR_SENHA") or "").strip()
    if not nova or app.config.get("TESTING"):
        return
    login = (os.environ.get("ADMIN_LOGIN") or "admin").strip().lower()
    try:
        with app.app_context():
            from .models import LogIntegracao, Usuario
            u = Usuario.query.filter_by(login=login).first() or Usuario.query.filter_by(login="admin").first()
            if not u:
                u = Usuario(login=login, nome=os.environ.get("ADMIN_NOME", "Administrador"), perfil="admin")
                db.session.add(u)
            u.definir_senha(nova)
            u.ativo, u.trocar_senha, u.perfil = True, False, "admin"
            db.session.add(LogIntegracao(sistema="sistema", operacao="Senha do admin redefinida", sucesso=True,
                                         mensagem=f"Senha do usuário '{u.login}' redefinida pela variável "
                                                  "ADMIN_REDEFINIR_SENHA. Apague a variável no Render."))
            db.session.commit()
            app.logger.warning("Senha do admin '%s' redefinida por ADMIN_REDEFINIR_SENHA — apague a variável.", u.login)
    except Exception:  # banco ainda não criado etc. — nunca impede o sistema de subir
        app.logger.exception("Não foi possível redefinir a senha do admin")


def _filtros(app):
    from .services.estoque import fmt_qtd

    @app.template_filter("qtd")
    def qtd(v):
        return fmt_qtd(v)

    @app.template_filter("moeda")
    def moeda(v):
        v = v or 0
        return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def _local(dt):
        return dt.replace(tzinfo=timezone.utc).astimezone(FUSO) if dt else None

    @app.template_filter("pct")
    def pct(v):
        return f"{v or 0:.1f}".replace(".", ",") + "%"

    @app.template_filter("valorbr")
    def valorbr(v):
        """2000 -> 2.000,00 (para campos de formulário)"""
        return f"{v or 0:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    @app.template_filter("datahora")
    def datahora(dt):
        return _local(dt).strftime("%d/%m/%Y %H:%M") if dt else "—"

    @app.template_filter("data")
    def data(dt):
        return _local(dt).strftime("%d/%m/%Y") if dt else "—"

    @app.template_filter("slug")
    def slug(s):
        import re
        import unicodedata
        s = unicodedata.normalize("NFD", str(s)).encode("ascii", "ignore").decode()
        return re.sub(r"[^a-zA-Z0-9]+", "-", s)

    @app.context_processor
    def contexto():
        from .versao import texto_versao
        from .views.menu import menu_do_usuario
        return {"versao": texto_versao(), "menu": menu_do_usuario(), "empresa": app.config["EMPRESA"], "sistema": app.config.get("SISTEMA", "Sistema de Gestão Vieira Diniz"),
                "logo_existe": os.path.exists(os.path.join(app.static_folder, "img", "logo-vieira-diniz.png"))}


def _cli(app):
    @app.cli.command("init-db")
    def init_db():
        """Cria as tabelas; no primeiro uso carrega o inventário inicial e o admin."""
        from .models import Insumo
        from .services.importacao import carregar_inventario_inicial, carregar_usuarios_iniciais, garantir_admin
        db.create_all()
        _migrar()
        if not Insumo.query.first():
            r = carregar_inventario_inicial()
            click.echo(f"Inventário inicial carregado: {r}")
        login = os.environ.get("ADMIN_LOGIN", "admin")
        senha = os.environ.get("ADMIN_SENHA")
        if senha:
            _, criado = garantir_admin(login, senha, os.environ.get("ADMIN_NOME", "Administrador"))
            if criado:
                click.echo(f"Usuário administrador '{login}' criado.")
        n = carregar_usuarios_iniciais()
        if n:
            click.echo(f"{n} colaborador(es) criado(s) com senha provisória.")
        _aprovadores_iniciais()
        db.session.commit()
        from .services.compras_mc import carregar_seed
        r = carregar_seed()
        if r:
            click.echo(f"Compras do Mais Controle carregadas: {r}")
        _estoque_mc_inicial()
        _inventario_mc_inicial()
        from .services.categorias import carregar_seed as _cat_seed
        r_cat = _cat_seed()
        if r_cat is not None:
            click.echo(f"Categorias de gasto (padrão Mais Controle): {r_cat} nova(s).")
        from .services.importacao import carregar_cadastro_insumos_seed
        r = carregar_cadastro_insumos_seed()
        if r:
            click.echo(f"Cadastro de insumos do Mais Controle: {r}")
        try:
            from .services.demandas import carregar_seed as _dem_seed
            if _dem_seed():
                click.echo("Painel de demandas carregado.")
        except Exception as e:  # noqa: BLE001
            db.session.rollback()
            click.echo(f"Painel de demandas: {e}")
        try:
            from .services.fin_dados import materializar_se_preciso
            r = materializar_se_preciso()
            if r:
                click.echo(f"Base financeira montada: {r}")
        except Exception as e:  # nunca impede o sistema de subir
            db.session.rollback()
            click.echo(f"Base financeira: não montada agora ({e}). Use Integrações > Buscar dados agora.")
        click.echo("Banco pronto.")

    @app.cli.command("carregar-compras-mc")
    def carregar_compras_mc():
        """Recarrega OCs, cotações e solicitações de seed/compras_mc.json (substitui as atuais)."""
        from .services.compras_mc import carregar_seed
        click.echo(str(carregar_seed(forcar=True)))

    @app.cli.command("criar-admin")
    @click.argument("login")
    @click.argument("senha")
    def criar_admin(login, senha):
        from .services.importacao import garantir_admin
        _, criado = garantir_admin(login, senha)
        db.session.commit()
        click.echo("Criado." if criado else "Já existia.")

    @app.cli.command("demo")
    def demo():
        """Cria usuários de demonstração (um por perfil), senha 123456. Só para testes."""
        from .models import Usuario
        for login, nome, perfil in [("almoxarife", "Carlos Lima", "almoxarife"),
                                    ("thanielle", "Thanielle Alves", "encarregado"),
                                    ("compras", "Juliana Prado", "compras")]:
            if not Usuario.query.filter_by(login=login).first():
                u = Usuario(login=login, nome=nome, perfil=perfil)
                u.definir_senha("123456")
                db.session.add(u)
        db.session.commit()
        click.echo("Usuários de demonstração criados (senha 123456).")


def _migrar():
    """Acrescenta colunas novas em bancos já existentes (create_all não altera tabelas)."""
    from sqlalchemy import inspect, text
    insp = inspect(db.engine)
    novas = [
        ("boletos_dda", "documento", "VARCHAR(60)"),
        ("boletos_dda", "conferir", "INTEGER DEFAULT 0"),
        ("boletos_dda", "pagador", "VARCHAR(200)"),
        ("boletos_dda", "tipo", "VARCHAR(60)"),
        ("boletos_dda", "banco", "VARCHAR(5)"),
        ("usuarios", "telefone", "VARCHAR(30)"),
        ("usuarios", "callmebot_apikey", "VARCHAR(60)"),
        ("compras", "descricao", "VARCHAR(255)"),
        ("compras", "unidade", "VARCHAR(20)"),
        ("compras", "solicitante_id", "INTEGER REFERENCES usuarios(id)"),
        ("compras", "observacao", "TEXT"),
        ("usuarios", "trocar_senha", "BOOLEAN DEFAULT FALSE"),
        ("usuarios", "aprova_ate", "FLOAT"),
        ("usuarios", "aprova_sem_limite", "BOOLEAN DEFAULT FALSE"),
        ("usuarios", "alerta_estoque", "BOOLEAN DEFAULT FALSE"),
        ("usuarios", "aviso_compras", "BOOLEAN DEFAULT FALSE"),
        ("usuarios", "aviso_reserva", "BOOLEAN DEFAULT FALSE"),
        ("solicitacoes", "prioridade", "VARCHAR(20) DEFAULT 'Normal'"),
        ("solicitacoes", "precisa_ate", "DATE"),
        ("solicitacao_itens", "qtd_cancelada", "FLOAT DEFAULT 0"),
        ("movimentacoes", "estorno_de_id", "INTEGER REFERENCES movimentacoes(id)"),
        ("movimentacoes", "estornada_em", "TIMESTAMP"),
        ("movimentacoes", "estorno_motivo", "VARCHAR(255)"),
        ("movimentacoes", "nota_id", "INTEGER REFERENCES notas_fiscais(id)"),
        ("compras", "nota_id", "INTEGER REFERENCES notas_fiscais(id)"),
        ("inventario_itens", "contado_em", "TIMESTAMP"),
        ("inventario_itens", "mov_apos_contagem", "FLOAT"),
        ("insumos", "alerta_critico_em", "TIMESTAMP"),
        ("compras", "valor_unitario", "FLOAT"),
        ("compras", "aprovacao_status", "VARCHAR(30)"),
        ("compras", "alcada_id", "INTEGER REFERENCES alcadas(id)"),
        ("compras", "aprovador_id", "INTEGER REFERENCES usuarios(id)"),
        ("compras", "aprovado_em", "TIMESTAMP"),
        ("compras", "aprovacao_obs", "TEXT"),
        ("notas_fiscais", "obra_id", "INTEGER REFERENCES obras(id)"),
        ("notas_fiscais", "centro_custo", "VARCHAR(200)"),
        ("insumos", "grupo", "VARCHAR(30)"),
        ("insumos", "tipo", "VARCHAR(80)"),
        ("insumos", "preco_referencia", "FLOAT"),
        ("solicitacoes", "entrega_hora", "VARCHAR(5)"),
        ("solicitacoes", "entrega_contato", "VARCHAR(120)"),
        ("compras", "precisa_ate", "DATE"),
        ("compras", "entrega_hora", "VARCHAR(5)"),
        ("obras", "endereco", "VARCHAR(255)"),
        ("obras", "bairro", "VARCHAR(120)"),
        ("obras", "cidade", "VARCHAR(120)"),
        ("obras", "referencia", "VARCHAR(255)"),
        ("obras", "contato_obra", "VARCHAR(120)"),
        ("obras", "status_conferido_em", "TIMESTAMP"),
        ("movimentacoes", "nota_item_id", "INTEGER REFERENCES nota_itens(id)"),
        ("notas_fiscais", "omie_receb_id", "VARCHAR(30)"),
        ("notas_fiscais", "omie_status", "VARCHAR(255)"),
        ("notas_fiscais", "omie_status_em", "TIMESTAMP"),
        ("notas_fiscais", "omie_concluido", "BOOLEAN DEFAULT FALSE"),
        ("notas_fiscais", "omie_conferido", "BOOLEAN DEFAULT FALSE"),
        ("titulos_financeiros", "valor_desconto", "FLOAT DEFAULT 0"),
        ("usuarios", "menu_oculto", "TEXT"),
        ("solicitacoes", "ordem_entrega", "INTEGER"),
        ("funcionarios_obra", "proximas", "VARCHAR(255)"),
        ("nota_itens", "destino", "VARCHAR(220)"),
        ("nfse_emitidas", "chave", "VARCHAR(60)"),
        ("nfse_emitidas", "xml_nacional", "TEXT"),
    ]
    for tabela, coluna, tipo in novas:
        if coluna not in {c["name"] for c in insp.get_columns(tabela)}:
            db.session.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}"))
            click.echo(f"Coluna criada: {tabela}.{coluna}")
    if db.engine.dialect.name == "postgresql":
        db.session.execute(text("ALTER TABLE compras ALTER COLUMN insumo_id DROP NOT NULL"))
    db.session.commit()
    from .models import Compra, Configuracao as _Cfg
    if not _Cfg.obter("corrigir_compras_canceladas"):
        for c in Compra.query.filter(Compra.status == "Cancelado", Compra.item_id.isnot(None)).all():
            it = c.item
            resto = max(0.0, (c.qtd_comprar or 0) - (c.qtd_recebida or 0))
            if it and (it.qtd_pendente_compra or 0) > 0:
                baixa = min(resto, it.qtd_pendente_compra)
                it.qtd_pendente_compra -= baixa
                it.qtd_cancelada = (it.qtd_cancelada or 0) + baixa
        _Cfg.definir("corrigir_compras_canceladas", "ok")
        db.session.commit()
    from .models import Empresa
    if not Empresa.query.first():
        db.session.add(Empresa(nome="F. Diniz Engenharia Ltda", cnpj="56160494000126", sistema="omie",
                               prefixo_obras="FDINIZ"))
        db.session.add(Empresa(nome="Ramos Diniz Serviços de Engenharia Ltda", cnpj="27396528000188",
                               sistema="maiscontrole", prefixo_obras="RAMOS"))
        db.session.commit()
        click.echo("Empresas cadastradas: F. Diniz (Omie) e Ramos Diniz (Mais Controle).")
    # valor a partir do qual o pedido precisa de aprovação (ajustável na tela Aprovação de Compras)
    from .models import Configuracao
    if Configuracao.obter("aprovacao_minimo") is None:
        Configuracao.definir("aprovacao_minimo", 2000.0)
        db.session.commit()


def _estoque_mc_inicial():
    """Uma única vez: aplica o Relatório de Disponíveis do Mais Controle de 27/09/2026 (modo inventário)."""
    from .models import Configuracao
    from .services import importacao as imp
    chave = "estoque_mc_2026_09_27"
    caminho = os.path.join(os.path.dirname(os.path.dirname(__file__)), "seed", "estoque_mc_2026-09-27.xlsx")
    if Configuracao.obter(chave) or not os.path.exists(caminho):
        return
    regs, _ = imp.analisar_estoque(caminho)
    r = imp.aplicar_estoque(regs, "Importação automática (Mais Controle 27/09/2026)", modo="substituir")
    from .models import LogIntegracao
    db.session.add(LogIntegracao(sistema="maiscontrole", operacao="Importar estoque (27/09/2026)", sucesso=True,
                                 mensagem=f"{len(regs)} linhas; {r['saldos_alterados']} saldo(s) atualizados, "
                                          f"{r['zerados']} zerado(s), {r['insumos_criados']} insumo(s) e "
                                          f"{r['depositos_criados']} depósito(s) novos.", usuario="Sistema"))
    Configuracao.definir(chave, "ok")
    db.session.commit()
    click.echo(f"Estoque do Mais Controle de 27/09/2026 aplicado: {r['saldos_alterados']} saldo(s).")


def _inventario_mc_inicial():
    """Uma única vez: registra o inventário VALIDADO do relatório do Mais Controle de 27/09/2026 como
    inventário FINALIZADO (com as quantidades contadas) em cada depósito. Os saldos já foram aplicados por
    _estoque_mc_inicial; aqui não há movimentação, só o registro fechado. Inventários abertos e vazios
    (nenhum item contado) desses depósitos são cancelados."""
    from datetime import datetime
    from .models import Configuracao, Deposito, Insumo, Inventario, InventarioItem, LogIntegracao
    from .services import importacao as imp
    from .services import estoque as est
    chave = "inventario_mc_2026_09_27"
    caminho = os.path.join(os.path.dirname(os.path.dirname(__file__)), "seed", "estoque_mc_2026-09-27.xlsx")
    if Configuracao.obter(chave) or not os.path.exists(caminho):
        return
    regs, _ = imp.analisar_estoque(caminho)
    central = est.deposito_central()
    deps = {imp.norm(d.nome): d for d in Deposito.query.all()}
    insumos = Insumo.query.all()
    cod = {i.codigo_mc: i for i in insumos if i.codigo_mc}
    nomes = {imp.norm(i.nome): i for i in insumos}
    por_dep = {}
    for r in regs:
        n = imp.norm(r["deposito"])
        dep = central if n in imp.NOMES_CENTRAL else deps.get(n)
        ins = imp._achar_insumo(cod, nomes, r)
        if not dep or not ins:
            continue
        itens = por_dep.setdefault(dep.id, (dep, {}))[1]
        q, c = itens.get(ins.id, (0.0, None))
        itens[ins.id] = (q + (r["quantidade"] or 0), r["custo"] or c)
    quando = datetime(2026, 9, 27, 15, 0)   # 12:00 em Recife
    criados, cancelados = 0, 0
    for dep, itens in por_dep.values():
        for aberto in Inventario.query.filter_by(deposito_id=dep.id, status="Em contagem").all():
            if not aberto.contados:
                aberto.status = "Cancelado"
                aberto.observacao = ((aberto.observacao or "") + " · cancelado: substituído pelo inventário validado de 27/09/2026")[:255]
                cancelados += 1
        inv = Inventario(deposito=dep, status="Finalizado", criado_em=quando, finalizado_em=quando,
                         criado_por="Mais Controle (validado)", finalizado_por="Importação do inventário validado",
                         observacao="Inventário validado — Relatório de insumos disponíveis do Mais Controle de 27/09/2026")
        db.session.add(inv)
        for iid, (q, c) in itens.items():
            inv.itens.append(InventarioItem(insumo_id=iid, contagem=q, saldo_sistema=q, diferenca=0.0, anterior=q,
                                            custo_medio=c or 0.0, entradas=0.0, recebido_transf=0.0,
                                            saida_solicitacoes=0.0, saida_transf=0.0, consumo=0.0, outros=0.0,
                                            contado_em=quando, mov_apos_contagem=0.0))
        criados += 1
    db.session.add(LogIntegracao(sistema="maiscontrole", operacao="Inventário validado 27/09/2026", sucesso=True,
                                 usuario="Sistema",
                                 mensagem=f"{criados} inventário(s) finalizado(s) registrado(s); {cancelados} inventário(s) "
                                          "aberto(s) e vazio(s) cancelado(s)."))
    Configuracao.definir(chave, "ok")
    db.session.commit()
    click.echo(f"Inventário validado de 27/09/2026 registrado em {criados} depósito(s).")


def _aprovadores_iniciais():
    """Uma única vez: Fredy Henrique (gestor) aprova sem limite. Depois disso vale o que o admin ajustar."""
    from .models import Configuracao, Usuario
    if not Configuracao.obter("alerta_estoque_inicial"):
        for u in Usuario.query.filter(Usuario.perfil.in_(["admin", "almoxarife", "compras", "almox_compras"])):
            u.alerta_estoque = True
        Configuracao.definir("alerta_estoque_inicial", "ok")
        click.echo("Alerta de estoque crítico ligado para administradores, almoxarifes e compras.")
    if not Configuracao.obter("aviso_compras_inicial"):
        for u in Usuario.query.filter(Usuario.perfil.in_(["compras", "almox_compras"])):
            u.aviso_compras = True
        Configuracao.definir("aviso_compras_inicial", "ok")
        click.echo("Aviso de pedidos de compra ligado para o perfil Compras.")
    if not Configuracao.obter("aviso_reserva_inicial"):
        for u in Usuario.query.filter(Usuario.perfil.in_(["almoxarife", "almox_compras"])):
            u.aviso_reserva = True
        Configuracao.definir("aviso_reserva_inicial", "ok")
        db.session.commit()
        click.echo("Aviso de reserva de material ligado para o almoxarifado.")
    if Configuracao.obter("aprovadores_iniciais"):
        return
    fredy = Usuario.query.filter_by(login="fredy.henrique").first()
    if fredy:
        fredy.aprova_sem_limite = True
        Configuracao.definir("aprovadores_iniciais", "ok")
        click.echo("Fredy Henrique definido como aprovador sem limite.")
