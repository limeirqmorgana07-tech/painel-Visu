"""Modelo de dados do Estoque de Obras — Vieira Diniz.

Conceito central: todo saldo mora em um DEPÓSITO. Existe um depósito do tipo
"central" (o almoxarifado / ESCRITORIO do Mais Controle) e um depósito por obra.
Isso espelha o "Relatório de Estoque Disponíveis" do Mais Controle e o conceito
de "local de estoque" do Omie, o que simplifica as duas integrações.
"""
from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def agora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


PERFIS = {
    "admin": "Administrador",
    "almoxarife": "Almoxarife",
    "encarregado": "Encarregado/Engenheiro",
    "compras": "Compras",
    "almox_compras": "Almoxarife e Compras",
    "consulta": "Consulta (RH, Financeiro…)",
    "motorista": "Motorista",
}
# perfil combinado: tem as permissões dos dois
COMBINADOS = {"almox_compras": ("almoxarife", "compras")}
# perfis que podem ter limite de aprovação de compras
PERFIS_APROVADORES = ("admin", "consulta")


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    login = db.Column(db.String(60), unique=True, nullable=False, index=True)
    email = db.Column(db.String(160))
    cargo = db.Column(db.String(120))
    telefone = db.Column(db.String(30))          # WhatsApp, com DDD
    callmebot_apikey = db.Column(db.String(60))  # só se usar o aviso gratuito via CallMeBot
    perfil = db.Column(db.String(20), nullable=False, default="encarregado")
    senha_hash = db.Column(db.String(255), nullable=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    trocar_senha = db.Column(db.Boolean, default=False)  # obriga a trocar a senha provisória no 1º acesso
    # Alçada de aprovação de compras (só admin e consulta/financeiro)
    aprova_ate = db.Column(db.Float)                       # aprova pedidos até este valor
    aprova_sem_limite = db.Column(db.Boolean, default=False)
    alerta_estoque = db.Column(db.Boolean, default=False)  # recebe alerta de estoque crítico no WhatsApp
    aviso_compras = db.Column(db.Boolean, default=False)   # recebe aviso de novos pedidos de compra
    aviso_reserva = db.Column(db.Boolean, default=False)   # recebe aviso de reserva de material
    criado_em = db.Column(db.DateTime, default=agora)
    menu_oculto = db.Column(db.Text)   # itens do menu escondidos pelo administrador (JSON)

    def definir_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def confere_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

    @property
    def is_active(self):
        return self.ativo

    @property
    def simulando(self):
        """Perfil que o administrador escolheu para 'ver como' (ou None)."""
        if self.perfil != "admin":
            return None
        try:
            from flask import session
            from flask_login import current_user
            if not current_user or current_user.get_id() != str(self.id):
                return None  # só vale para o próprio administrador logado
            p = session.get("ver_como")
        except RuntimeError:  # fora de uma requisição
            return None
        return p if p in PERFIS and p != "admin" else None

    @property
    def perfil_ativo(self):
        return self.simulando or self.perfil

    @property
    def perfil_label(self):
        return PERFIS.get(self.perfil_ativo, self.perfil_ativo)

    def tem_perfil(self, perfis):
        p = self.perfil_ativo
        return p in perfis or any(x in perfis for x in COMBINADOS.get(p, ()))

    def pode(self, *perfis):
        return self.perfil_ativo == "admin" or self.tem_perfil(perfis)

    @property
    def limite_aprovacao(self):
        """Até quanto aprova (float('inf') = sem limite; None = não aprova)."""
        if self.perfil not in PERFIS_APROVADORES or not self.ativo:
            return None
        if self.aprova_sem_limite:
            return float("inf")
        return self.aprova_ate if self.aprova_ate and self.aprova_ate > 0 else None


class Obra(db.Model):
    __tablename__ = "obras"
    id = db.Column(db.Integer, primary_key=True)
    codigo_mc = db.Column(db.String(40), unique=True, index=True)  # id no Mais Controle (ex.: O99720)
    omie_codigo_projeto = db.Column(db.String(40))
    nome = db.Column(db.String(255), nullable=False)
    tipo = db.Column(db.String(60))
    responsavel = db.Column(db.String(120))
    arquiteto = db.Column(db.String(160))
    area = db.Column(db.Float, default=0)
    cliente = db.Column(db.String(200))
    status = db.Column(db.String(40), default="Em andamento")
    criado_em = db.Column(db.DateTime, default=agora)
    # Endereço de entrega (rota do motorista)
    endereco = db.Column(db.String(255))        # rua, número, complemento / apto
    bairro = db.Column(db.String(120))
    cidade = db.Column(db.String(120))
    referencia = db.Column(db.String(255))      # ponto de referência / portaria / como chegar
    contato_obra = db.Column(db.String(120))    # quem recebe na obra + telefone
    status_conferido_em = db.Column(db.DateTime)  # quando a situação foi classificada/confirmada

    deposito = db.relationship("Deposito", back_populates="obra", uselist=False)

    @property
    def endereco_completo(self):
        partes = [self.endereco, self.bairro, self.cidade]
        return ", ".join(p.strip() for p in partes if p and p.strip()) or None

    @property
    def link_mapa(self):
        """Link do Google Maps (abre o app no celular do motorista)."""
        from urllib.parse import quote
        e = self.endereco_completo
        return f"https://www.google.com/maps/search/?api=1&query={quote(e)}" if e else None

    @property
    def em_andamento(self):
        return (self.status or "Em andamento") == "Em andamento"


class Insumo(db.Model):
    __tablename__ = "insumos"
    id = db.Column(db.Integer, primary_key=True)
    codigo_mc = db.Column(db.String(40), unique=True, index=True)  # id no Mais Controle (ex.: M555)
    omie_codigo_produto = db.Column(db.String(40))
    nome = db.Column(db.String(255), nullable=False)
    nome_busca = db.Column(db.String(255), index=True)  # nome sem acentos, maiúsculo — usado na busca
    unidade = db.Column(db.String(20), default="UN")
    estoque_minimo = db.Column(db.Float, default=0)
    grupo = db.Column(db.String(30), index=True)        # Material | Equipamento | Mão de obra | Outros (Mais Controle)
    tipo = db.Column(db.String(80))                     # ex.: MATERIAL ELÉTRICO, MAQUINÁRIO, FERRAMENTA, EPI
    preco_referencia = db.Column(db.Float)              # "Preço ou Salário" do cadastro do Mais Controle
    alerta_critico_em = db.Column(db.DateTime)  # quando avisou que ficou abaixo do mínimo (limpa ao repor)
    ativo = db.Column(db.Boolean, default=True)

    @property
    def codigo(self):
        return self.codigo_mc or f"VD{self.id}"

    @property
    def grupo_label(self):
        return self.grupo or "Material"

    @property
    def unidade_suspeita(self):
        u = (self.unidade or "").strip()
        return not u or not u.replace(",", "").replace(".", "").replace("²", "").replace("³", "").isalnum()


def _texto_busca(t):
    import unicodedata
    return unicodedata.normalize("NFD", str(t or "")).encode("ascii", "ignore").decode().upper()


@db.event.listens_for(Insumo, "before_insert")
@db.event.listens_for(Insumo, "before_update")
def _insumo_nome_busca(mapper, connection, target):
    target.nome_busca = _texto_busca(target.nome)


GRUPOS_INSUMO = ["Material", "Equipamento", "Mão de obra", "Outros"]


TIPOS_DEPOSITO = {"central": "Estoque Central", "almoxarifado": "Almoxarifado", "obra": "Obra"}


class Deposito(db.Model):
    __tablename__ = "depositos"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(255), unique=True, nullable=False)
    tipo = db.Column(db.String(20), nullable=False, default="obra")  # central | almoxarifado | obra
    obra_id = db.Column(db.Integer, db.ForeignKey("obras.id"), unique=True)
    omie_local_estoque = db.Column(db.String(40))
    obra = db.relationship("Obra", back_populates="deposito")

    @property
    def tipo_label(self):
        return TIPOS_DEPOSITO.get(self.tipo, self.tipo)


class Saldo(db.Model):
    __tablename__ = "saldos"
    __table_args__ = (db.UniqueConstraint("deposito_id", "insumo_id", name="uq_saldo"),)
    id = db.Column(db.Integer, primary_key=True)
    deposito_id = db.Column(db.Integer, db.ForeignKey("depositos.id"), nullable=False, index=True)
    insumo_id = db.Column(db.Integer, db.ForeignKey("insumos.id"), nullable=False, index=True)
    quantidade = db.Column(db.Float, nullable=False, default=0)
    reservada = db.Column(db.Float, nullable=False, default=0)
    custo_medio = db.Column(db.Float, default=0)
    atualizado_em = db.Column(db.DateTime, default=agora, onupdate=agora)

    deposito = db.relationship("Deposito")
    insumo = db.relationship("Insumo")

    @property
    def disponivel(self):
        return max(0.0, (self.quantidade or 0) - (self.reservada or 0))


class Solicitacao(db.Model):
    __tablename__ = "solicitacoes"
    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey("obras.id"), nullable=False)
    solicitante_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    criada_em = db.Column(db.DateTime, default=agora, index=True)
    observacao = db.Column(db.Text)
    prioridade = db.Column(db.String(20), default="Normal")  # Normal | Alta | Urgente
    precisa_ate = db.Column(db.Date)                          # data em que a obra precisa do material
    entrega_hora = db.Column(db.String(5))                    # horário pedido para a entrega (HH:MM)
    entrega_contato = db.Column(db.String(120))               # quem recebe na obra / telefone / instrução
    cancelada = db.Column(db.Boolean, default=False)
    entrega_confirmada = db.Column(db.Boolean, default=False)
    ordem_entrega = db.Column(db.Integer)                     # sequência definida à mão no quadro das entregas

    obra = db.relationship("Obra")
    solicitante = db.relationship("Usuario")
    itens = db.relationship("SolicitacaoItem", back_populates="solicitacao", order_by="SolicitacaoItem.id",
                            cascade="all, delete-orphan")
    historico = db.relationship("HistoricoSolicitacao", order_by="HistoricoSolicitacao.id",
                                cascade="all, delete-orphan")

    @property
    def numero(self):
        return f"S-{self.id:04d}"

    def total(self, campo):
        return sum(getattr(i, campo) or 0 for i in self.itens)

    @property
    def status(self):
        if self.cancelada:
            return "Cancelada"
        solicitada = self.total("qtd_solicitada")
        atendida = self.total("qtd_atendida")
        if solicitada and atendida >= solicitada:
            return "Entregue" if self.entrega_confirmada else "Enviada"
        if atendida > 0:
            return "Parcialmente atendida"
        if self.total("qtd_reservada") > 0:
            return "Em separação"
        if self.total("qtd_pendente_compra") > 0:
            return "Aguardando compra"
        if self.total("qtd_cancelada") > 0:
            return "Compra cancelada"
        return "Solicitada"

    @property
    def prioridade_ok(self):
        return self.prioridade or "Normal"

    @property
    def entrega_texto(self):
        """Ex.: "30/09 até 09:00" · "30/09" · "até 14:00" · None"""
        d = self.precisa_ate.strftime("%d/%m") if self.precisa_ate else ""
        h = f"até {self.entrega_hora}" if self.entrega_hora else ""
        return " ".join(x for x in (d, h) if x) or None

    @property
    def pct_atendida(self):
        s = self.total("qtd_solicitada")
        return round(self.total("qtd_atendida") / s * 100) if s else 0


class SolicitacaoItem(db.Model):
    __tablename__ = "solicitacao_itens"
    id = db.Column(db.Integer, primary_key=True)
    solicitacao_id = db.Column(db.Integer, db.ForeignKey("solicitacoes.id"), nullable=False)
    insumo_id = db.Column(db.Integer, db.ForeignKey("insumos.id"), nullable=False)
    qtd_solicitada = db.Column(db.Float, nullable=False)
    qtd_reservada = db.Column(db.Float, default=0)
    qtd_atendida = db.Column(db.Float, default=0)
    qtd_pendente_compra = db.Column(db.Float, default=0)
    qtd_cancelada = db.Column(db.Float, default=0)  # parte cuja compra foi cancelada/reprovada
    separado = db.Column(db.Boolean, default=False)
    observacao = db.Column(db.String(255))

    solicitacao = db.relationship("Solicitacao", back_populates="itens")
    insumo = db.relationship("Insumo")


class HistoricoSolicitacao(db.Model):
    __tablename__ = "historico_solicitacoes"
    id = db.Column(db.Integer, primary_key=True)
    solicitacao_id = db.Column(db.Integer, db.ForeignKey("solicitacoes.id"), nullable=False)
    data = db.Column(db.DateTime, default=agora)
    usuario = db.Column(db.String(120))
    acao = db.Column(db.String(80))
    detalhe = db.Column(db.Text)


STATUS_COMPRA = ["Pendente de compra", "Em cotação", "Compra autorizada", "Comprado", "Recebido", "Cancelado"]
PRIORIDADES = ["Normal", "Alta", "Urgente"]


class Compra(db.Model):
    """Item em 'Materiais a Comprar'.

    Nasce de duas formas: (1) falta de saldo numa solicitação de materiais;
    (2) pedido avulso feito na consulta de estoque ("não encontrei o item") —
    nesse caso pode nem existir insumo cadastrado, e vale a descrição digitada.
    """
    __tablename__ = "compras"
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("solicitacao_itens.id"))
    insumo_id = db.Column(db.Integer, db.ForeignKey("insumos.id"))
    descricao = db.Column(db.String(255))
    unidade = db.Column(db.String(20))
    solicitante_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    observacao = db.Column(db.Text)
    valor_unitario = db.Column(db.Float)  # estimado no pedido ou cotado pelo comprador
    nota_id = db.Column(db.Integer, db.ForeignKey("notas_fiscais.id"))  # NF do recebimento
    # Aprovação por alçada (None = não requer)
    aprovacao_status = db.Column(db.String(30))  # Aguardando aprovação | Aprovada | Reprovada
    alcada_id = db.Column(db.Integer, db.ForeignKey("alcadas.id"))
    aprovador_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    aprovado_em = db.Column(db.DateTime)
    aprovacao_obs = db.Column(db.Text)
    obra_id = db.Column(db.Integer, db.ForeignKey("obras.id"))
    qtd_comprar = db.Column(db.Float, nullable=False)
    qtd_recebida = db.Column(db.Float, default=0)
    prioridade = db.Column(db.String(20), default="Normal")
    precisa_ate = db.Column(db.Date)            # pedido avulso: data de entrega pedida
    entrega_hora = db.Column(db.String(5))      # pedido avulso: horário pedido (HH:MM)
    status = db.Column(db.String(30), default="Pendente de compra", index=True)
    fornecedor = db.Column(db.String(160))
    criada_em = db.Column(db.DateTime, default=agora)

    item = db.relationship("SolicitacaoItem")
    insumo = db.relationship("Insumo")
    obra = db.relationship("Obra")
    solicitante = db.relationship("Usuario", foreign_keys=[solicitante_id])
    nota = db.relationship("NotaFiscal")
    aprovador = db.relationship("Usuario", foreign_keys=[aprovador_id])
    alcada = db.relationship("Alcada")

    @property
    def numero(self):
        return f"MC-{self.id:04d}"

    @property
    def aprovacao(self):
        return self.aprovacao_status or "Não requer"

    @property
    def liberada(self):
        """Pode ser autorizada/comprada/recebida?"""
        return self.aprovacao in ("Não requer", "Aprovada")

    @property
    def nome_item(self):
        return self.insumo.nome if self.insumo else (self.descricao or "—")

    @property
    def unidade_item(self):
        return self.insumo.unidade if self.insumo else (self.unidade or "UN")

    @property
    def avulsa(self):
        return self.item_id is None

    @property
    def qtd_restante(self):
        return max(0.0, (self.qtd_comprar or 0) - (self.qtd_recebida or 0))

    @property
    def entrega_data(self):
        return self.precisa_ate or (self.item.solicitacao.precisa_ate if self.item else None)

    @property
    def entrega_texto(self):
        h = self.entrega_hora or (self.item.solicitacao.entrega_hora if self.item else None)
        d = self.entrega_data
        return " ".join(x for x in ((d.strftime("%d/%m") if d else ""), (f"até {h}" if h else "")) if x) or None


TIPOS_MOV = {
    "entrada": "Entrada",
    "saida": "Saída / consumo",
    "transferencia": "Transferência",
    "ajuste": "Ajuste de inventário",
    "importacao": "Carga de importação",
    "estorno": "Estorno",
}
TIPOS_ESTORNAVEIS = ("entrada", "saida", "transferencia", "ajuste")


class Movimentacao(db.Model):
    __tablename__ = "movimentacoes"
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False)
    insumo_id = db.Column(db.Integer, db.ForeignKey("insumos.id"), nullable=False)
    origem_id = db.Column(db.Integer, db.ForeignKey("depositos.id"))
    destino_id = db.Column(db.Integer, db.ForeignKey("depositos.id"))
    quantidade = db.Column(db.Float, nullable=False)
    custo_unitario = db.Column(db.Float)
    documento = db.Column(db.String(80))
    observacao = db.Column(db.String(255))
    solicitacao_id = db.Column(db.Integer, db.ForeignKey("solicitacoes.id"))
    usuario = db.Column(db.String(120))
    data = db.Column(db.DateTime, default=agora, index=True)
    # Integração: quando enviada ao Omie guardamos o id retornado
    omie_enviado_em = db.Column(db.DateTime)
    omie_id = db.Column(db.String(60))
    # Estorno (cancelamento): a movimentação original fica marcada e ligada ao estorno
    estorno_de_id = db.Column(db.Integer, db.ForeignKey("movimentacoes.id"))
    estornada_em = db.Column(db.DateTime)
    estorno_motivo = db.Column(db.String(255))
    nota_id = db.Column(db.Integer, db.ForeignKey("notas_fiscais.id"))
    nota_item_id = db.Column(db.Integer, db.ForeignKey("nota_itens.id"), index=True)  # item da NF que gerou a entrada

    insumo = db.relationship("Insumo")
    origem = db.relationship("Deposito", foreign_keys=[origem_id])
    destino = db.relationship("Deposito", foreign_keys=[destino_id])

    @property
    def tipo_label(self):
        return TIPOS_MOV.get(self.tipo, self.tipo)

    @property
    def estornavel(self):
        return self.tipo in TIPOS_ESTORNAVEIS and not self.estornada_em


class LogIntegracao(db.Model):
    __tablename__ = "log_integracoes"
    id = db.Column(db.Integer, primary_key=True)
    sistema = db.Column(db.String(30))  # omie | maiscontrole
    operacao = db.Column(db.String(80))
    sucesso = db.Column(db.Boolean, default=True)
    mensagem = db.Column(db.Text)
    usuario = db.Column(db.String(120))
    data = db.Column(db.DateTime, default=agora, index=True)


class Alcada(db.Model):
    """Faixa de valor de um pedido de compra e quem precisa aprová-la.

    Ex.: Gerência de R$ 2.000,00 até R$ 10.000,00 (aprovador: gerente);
         Diretoria a partir de R$ 10.000,00, sem teto (aprovador: diretor).
    """
    __tablename__ = "alcadas"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    valor_minimo = db.Column(db.Float, nullable=False, default=0)
    valor_maximo = db.Column(db.Float)  # vazio = sem limite
    aprovador_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    ativo = db.Column(db.Boolean, default=True)

    aprovador = db.relationship("Usuario")

    def cobre(self, valor):
        return valor >= self.valor_minimo and (self.valor_maximo is None or valor < self.valor_maximo)


class Configuracao(db.Model):
    """Parâmetros que o administrador ajusta pela tela (ex.: valor mínimo que exige aprovação)."""
    __tablename__ = "configuracoes"
    chave = db.Column(db.String(60), primary_key=True)
    valor = db.Column(db.String(255))

    @staticmethod
    def obter(chave, padrao=None):
        c = db.session.get(Configuracao, chave)
        return c.valor if c and c.valor not in (None, "") else padrao

    @staticmethod
    def definir(chave, valor):
        c = db.session.get(Configuracao, chave) or Configuracao(chave=chave)
        c.valor = str(valor)
        db.session.add(c)


class Inventario(db.Model):
    """Contagem física de um depósito (ex.: inventário semanal do Estoque Central)."""
    __tablename__ = "inventarios"
    id = db.Column(db.Integer, primary_key=True)
    deposito_id = db.Column(db.Integer, db.ForeignKey("depositos.id"), nullable=False)
    status = db.Column(db.String(20), default="Em contagem")  # Em contagem | Finalizado | Cancelado
    criado_em = db.Column(db.DateTime, default=agora)
    criado_por = db.Column(db.String(120))
    finalizado_em = db.Column(db.DateTime, index=True)
    finalizado_por = db.Column(db.String(120))
    observacao = db.Column(db.String(255))

    deposito = db.relationship("Deposito")
    itens = db.relationship("InventarioItem", back_populates="inventario", cascade="all, delete-orphan",
                            order_by="InventarioItem.id")

    @property
    def numero(self):
        return f"INV-{self.id:04d}"

    @property
    def contados(self):
        return [i for i in self.itens if i.contagem is not None]

    @property
    def divergentes(self):
        return [i for i in self.contados if i.diferenca and abs(i.diferenca) > 1e-9]


class InventarioItem(db.Model):
    __tablename__ = "inventario_itens"
    __table_args__ = (db.UniqueConstraint("inventario_id", "insumo_id", name="uq_inv_item"),)
    id = db.Column(db.Integer, primary_key=True)
    inventario_id = db.Column(db.Integer, db.ForeignKey("inventarios.id"), nullable=False, index=True)
    insumo_id = db.Column(db.Integer, db.ForeignKey("insumos.id"), nullable=False)
    contagem = db.Column(db.Float)          # None = não contado
    saldo_sistema = db.Column(db.Float)     # saldo do sistema no fechamento
    diferenca = db.Column(db.Float)         # contagem - sistema
    custo_medio = db.Column(db.Float)
    # composição do período desde o inventário anterior (para o comparativo)
    anterior = db.Column(db.Float)
    entradas = db.Column(db.Float)
    recebido_transf = db.Column(db.Float)
    saida_solicitacoes = db.Column(db.Float)
    saida_transf = db.Column(db.Float)
    consumo = db.Column(db.Float)
    outros = db.Column(db.Float)            # ajustes manuais, estornos, importações
    contado_em = db.Column(db.DateTime)     # quando a quantidade foi lançada
    mov_apos_contagem = db.Column(db.Float) # movimentação líquida do item entre a contagem e o fechamento

    inventario = db.relationship("Inventario", back_populates="itens")
    insumo = db.relationship("Insumo")


class NotaFiscal(db.Model):
    """NF-e de compra: lida pelo código de barras do DANFE (chave de 44 dígitos) e/ou pelo XML."""
    __tablename__ = "notas_fiscais"
    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(44), unique=True, index=True, nullable=False)
    numero = db.Column(db.String(20))
    serie = db.Column(db.String(5))
    emitente_cnpj = db.Column(db.String(14), index=True)
    emitente_nome = db.Column(db.String(200))
    destinatario_cnpj = db.Column(db.String(14))
    emissao = db.Column(db.DateTime, index=True)
    valor_total = db.Column(db.Float)
    condicao = db.Column(db.String(60))   # ex.: "À vista", "30/60/90"
    tem_xml = db.Column(db.Boolean, default=False)
    xml = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=agora)
    criado_por = db.Column(db.String(120))
    obra_id = db.Column(db.Integer, db.ForeignKey("obras.id"), index=True)   # obra / centro de custo da nota
    centro_custo = db.Column(db.String(200))
    # Recebimento da NF-e no Omie (F. Diniz): concluído a partir da entrada no estoque daqui
    omie_receb_id = db.Column(db.String(30))
    omie_status = db.Column(db.String(255))
    omie_status_em = db.Column(db.DateTime)
    omie_conferido = db.Column(db.Boolean, default=False)   # card na etapa Conferido do Omie (modo padrão)
    omie_concluido = db.Column(db.Boolean, default=False)  # quando não é obra: "Empresa" (administrativo) ou texto livre

    obra = db.relationship("Obra")
    itens = db.relationship("NotaItem", back_populates="nota", cascade="all, delete-orphan", order_by="NotaItem.id")
    parcelas = db.relationship("NotaParcela", back_populates="nota", cascade="all, delete-orphan",
                               order_by="NotaParcela.vencimento")
    rateios = db.relationship("NotaRateio", cascade="all, delete-orphan", order_by="NotaRateio.id")

    @property
    def rateio_lista(self):
        """[(rótulo, obra, %)] — nota com mais de uma obra: o % sai do valor dos itens indicados para cada obra
        (item sem indicação fica na 1ª); senão a obra / centro único com 100%."""
        if len(self.rateios) > 1:
            chaves = [r.chave for r in self.rateios]
            soma = {k: 0.0 for k in chaves}
            for it in self.itens:
                k = it.destino if it.destino in soma else chaves[0]
                soma[k] += float(it.valor_total or 0)
            total = sum(soma.values())
            return [(r.label, r.obra, (soma[r.chave] / total * 100) if total else 100.0 / len(chaves))
                    for r in self.rateios]
        return [(self.centro_custo_label, self.obra, 100.0)] if self.centro_custo_label else []

    def destino_item(self, item):
        """Chave da obra / centro de custo do item (1ª obra quando não foi indicado)."""
        if len(self.rateios) > 1:
            chaves = [r.chave for r in self.rateios]
            return item.destino if item.destino in chaves else chaves[0]
        return None

    @property
    def fornecedor(self):
        return self.emitente_nome or fmt_cnpj(self.emitente_cnpj)

    @property
    def centro_custo_label(self):
        return self.obra.nome if self.obra else (self.centro_custo or None)

    @property
    def empresa(self):
        """Empresa do grupo a que a nota se refere (pelo CNPJ do destinatário)."""
        c = "".join(ch for ch in str(self.destinatario_cnpj or "") if ch.isdigit())
        return Empresa.query.filter_by(cnpj=c).first() if len(c) == 14 else None

    @property
    def empresa_curta(self):
        e = self.empresa
        if not e:
            return None
        return "F. Diniz" if e.sistema == "omie" else ("Ramos Diniz" if e.sistema == "maiscontrole" else e.nome)

    @property
    def emissao_txt(self):
        """Data de emissão como está na nota (sem conversão de fuso).

        Só pela chave, a SEFAZ informa apenas mês/ano (a chave não tem o dia): mostra "09/2026".
        """
        if not self.emissao:
            return "—"
        if not self.tem_xml and self.emissao.day == 1 and not self.emissao.hour and not self.emissao.minute:
            return self.emissao.strftime("%m/%Y")
        return self.emissao.strftime("%d/%m/%Y")


def fmt_cnpj(c):
    c = "".join(ch for ch in str(c or "") if ch.isdigit())
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c) == 14 else (c or "—")


class NotaItem(db.Model):
    __tablename__ = "nota_itens"
    id = db.Column(db.Integer, primary_key=True)
    nota_id = db.Column(db.Integer, db.ForeignKey("notas_fiscais.id"), nullable=False, index=True)
    codigo = db.Column(db.String(60))
    descricao = db.Column(db.String(255))
    ncm = db.Column(db.String(10))
    unidade = db.Column(db.String(10))
    quantidade = db.Column(db.Float)
    valor_unitario = db.Column(db.Float)
    valor_total = db.Column(db.Float)
    insumo_id = db.Column(db.Integer, db.ForeignKey("insumos.id"))
    destino = db.Column(db.String(220))   # nota com mais de uma obra: "obra:<id>" | "empresa" | "outro:<centro de custo>"

    nota = db.relationship("NotaFiscal", back_populates="itens")
    insumo = db.relationship("Insumo")


class NotaRateio(db.Model):
    """Nota com mais de uma obra / centro de custo (a 1ª é a obra principal); cada item indica a sua (NotaItem.destino)."""
    __tablename__ = "nota_rateios"
    id = db.Column(db.Integer, primary_key=True)
    nota_id = db.Column(db.Integer, db.ForeignKey("notas_fiscais.id", ondelete="CASCADE"), nullable=False, index=True)
    obra_id = db.Column(db.Integer, db.ForeignKey("obras.id"))
    centro_custo = db.Column(db.String(200))
    percentual = db.Column(db.Float, default=0)

    obra = db.relationship("Obra")

    @property
    def label(self):
        return self.obra.nome if self.obra else (self.centro_custo or None)

    @property
    def chave(self):
        if self.obra_id:
            return f"obra:{self.obra_id}"
        return "empresa" if self.centro_custo == "Empresa" else f"outro:{self.centro_custo}"


class NotaParcela(db.Model):
    __tablename__ = "nota_parcelas"
    id = db.Column(db.Integer, primary_key=True)
    nota_id = db.Column(db.Integer, db.ForeignKey("notas_fiscais.id"), nullable=False, index=True)
    numero = db.Column(db.String(20))
    vencimento = db.Column(db.Date, index=True)
    valor = db.Column(db.Float)
    pago_em = db.Column(db.Date)
    pago_por = db.Column(db.String(120))

    nota = db.relationship("NotaFiscal", back_populates="parcelas")


class Empresa(db.Model):
    """Empresas do grupo e de onde vêm os dados financeiros de cada uma."""
    __tablename__ = "empresas"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    cnpj = db.Column(db.String(14), unique=True)
    sistema = db.Column(db.String(20))        # omie | maiscontrole
    prefixo_obras = db.Column(db.String(20))  # ex.: FDINIZ_ / RAMOS_
    ultima_sincronizacao = db.Column(db.DateTime)


class LancamentoFinanceiro(db.Model):
    """Contas a pagar importadas do Omie / Mais Controle (base do painel de compras e pagamentos)."""
    __tablename__ = "lancamentos_financeiros"
    __table_args__ = (db.UniqueConstraint("empresa_id", "id_externo", name="uq_lanc_externo"),)
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True)
    id_externo = db.Column(db.String(60), nullable=False)
    fornecedor = db.Column(db.String(200), index=True)
    documento = db.Column(db.String(60))
    categoria = db.Column(db.String(120))
    obra = db.Column(db.String(200))
    emissao = db.Column(db.Date, index=True)
    vencimento = db.Column(db.Date, index=True)
    valor = db.Column(db.Float)
    valor_pago = db.Column(db.Float)
    pago_em = db.Column(db.Date)
    status = db.Column(db.String(40))
    atualizado_em = db.Column(db.DateTime, default=agora, onupdate=agora)

    empresa = db.relationship("Empresa")

    @property
    def em_aberto(self):
        return not self.pago_em and (self.status or "").upper() not in ("PAGO", "LIQUIDADO", "CANCELADO", "QUITADO")


class DadoImportado(db.Model):
    """Cópia fiel de cada linha recebida das APIs (Mais Controle / Omie), para montar os painéis financeiros."""
    __tablename__ = "dados_importados"
    __table_args__ = (db.UniqueConstraint("empresa_id", "tabela", "chave", name="uq_dado_importado"),)
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True)
    tabela = db.Column(db.String(60), nullable=False, index=True)   # ex.: medicoes, recebimentos, contas_receber
    chave = db.Column(db.String(120), nullable=False)
    dados = db.Column(db.JSON)
    atualizado_em = db.Column(db.DateTime, default=agora, onupdate=agora)

    empresa = db.relationship("Empresa")


# ---------------------------------------------------------------- compras do Mais Controle (importadas por PDF)

class OrdemCompraMC(db.Model):
    """Ordens de compra do Mais Controle (relatório impresso em PDF). Base do painel de compras."""
    __tablename__ = "mc_ordens_compra"
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, unique=True, nullable=False)
    fornecedor = db.Column(db.String(200), index=True)
    valor = db.Column(db.Float, default=0)
    data = db.Column(db.Date, index=True)              # data de criação da OC
    centro_custo = db.Column(db.Text)                  # um ou mais centros de custo, separados por " | "
    solicitacao = db.Column(db.String(60))             # número(s) da solicitação de origem
    cotacao = db.Column(db.String(60))                 # número da cotação de origem
    status = db.Column(db.String(40))
    criado_por = db.Column(db.String(120))
    cond_pgto = db.Column(db.String(80))
    importado_em = db.Column(db.DateTime, default=agora)


class CotacaoMC(db.Model):
    __tablename__ = "mc_cotacoes"
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, unique=True, nullable=False)
    centro_custo = db.Column(db.String(200))
    itens = db.Column(db.Integer)
    fornecedores = db.Column(db.Integer)
    solicitacao = db.Column(db.String(60))
    ordens = db.Column(db.String(200))                 # OCs geradas, separadas por vírgula
    status = db.Column(db.String(40))
    importado_em = db.Column(db.DateTime, default=agora)


class SolicitacaoMC(db.Model):
    __tablename__ = "mc_solicitacoes"
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, unique=True, nullable=False)
    data = db.Column(db.Date, index=True)              # "Em:" (data em que foi solicitada)
    importado_em = db.Column(db.DateTime, default=agora)


class PedidoERP(db.Model):
    """Pedido (ordem) de compra que existe no ERP — hoje, pedidos de compra do Omie (F. Diniz).

    Copiado do Omie pela rotina produtos/pedidocompra PesquisarPedCompra. As notas fiscais recebidas
    são vinculadas aos itens destes pedidos (NotaPedidoItem).
    """
    __tablename__ = "pedidos_erp"
    __table_args__ = (db.UniqueConstraint("sistema", "id_externo", name="uq_pedido_erp"),)
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), index=True)
    sistema = db.Column(db.String(20), nullable=False, default="omie")
    id_externo = db.Column(db.String(40), nullable=False)       # nCodPed
    numero = db.Column(db.String(40), index=True)               # cNumero
    fornecedor_codigo = db.Column(db.String(40))                # nCodFor
    fornecedor_cnpj = db.Column(db.String(14), index=True)
    fornecedor_nome = db.Column(db.String(200))
    emissao = db.Column(db.Date)
    previsao = db.Column(db.Date)
    etapa = db.Column(db.String(40))
    projeto = db.Column(db.String(60))
    observacao = db.Column(db.Text)
    valor_total = db.Column(db.Float)
    dados = db.Column(db.JSON)
    atualizado_em = db.Column(db.DateTime, default=agora, onupdate=agora)

    empresa = db.relationship("Empresa")
    itens = db.relationship("PedidoERPItem", back_populates="pedido", cascade="all, delete-orphan",
                            order_by="PedidoERPItem.id")

    @property
    def rotulo(self):
        return f"PC {self.numero or self.id_externo}"

    @property
    def fornecedor(self):
        return self.fornecedor_nome or fmt_cnpj(self.fornecedor_cnpj) or "—"

    @property
    def qtd_total(self):
        return sum(i.quantidade or 0 for i in self.itens)

    @property
    def qtd_pendente(self):
        return sum(i.qtd_pendente for i in self.itens)

    @property
    def situacao(self):
        total, pend = self.qtd_total, self.qtd_pendente
        if total and pend <= 1e-9:
            return "Recebido"
        if pend < total - 1e-9:
            return "Recebido parcial"
        return "Em aberto"

    @property
    def notas(self):
        vistas = {}
        for it in self.itens:
            for v in it.vinculos:
                vistas[v.nota_id] = v.nota
        return list(vistas.values())


class PedidoERPItem(db.Model):
    __tablename__ = "pedidos_erp_itens"
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedidos_erp.id"), nullable=False, index=True)
    id_externo = db.Column(db.String(40))           # nCodItem
    produto_codigo = db.Column(db.String(40))       # nCodProd (código do produto no Omie)
    produto_integracao = db.Column(db.String(60))   # cCodIntProd (= código do Mais Controle, ex. M555)
    codigo = db.Column(db.String(60))               # cProduto
    descricao = db.Column(db.String(255))
    unidade = db.Column(db.String(20))
    quantidade = db.Column(db.Float, default=0)
    qtd_recebida_erp = db.Column(db.Float, default=0)   # já recebida no próprio Omie
    valor_unitario = db.Column(db.Float)

    pedido = db.relationship("PedidoERP", back_populates="itens")
    vinculos = db.relationship("NotaPedidoItem", back_populates="pedido_item", cascade="all, delete-orphan")

    @property
    def qtd_vinculada(self):
        return sum(v.quantidade or 0 for v in self.vinculos)

    @property
    def qtd_pendente(self):
        return max(0.0, (self.quantidade or 0) - max(self.qtd_recebida_erp or 0, self.qtd_vinculada))


class NotaPedidoItem(db.Model):
    """Vínculo: quanto de um item do pedido de compra chegou em qual nota fiscal."""
    __tablename__ = "notas_pedidos_itens"
    id = db.Column(db.Integer, primary_key=True)
    nota_id = db.Column(db.Integer, db.ForeignKey("notas_fiscais.id"), nullable=False, index=True)
    pedido_item_id = db.Column(db.Integer, db.ForeignKey("pedidos_erp_itens.id"), nullable=False, index=True)
    nota_item_id = db.Column(db.Integer, db.ForeignKey("nota_itens.id"))
    quantidade = db.Column(db.Float, nullable=False)
    valor_unitario = db.Column(db.Float)
    movimentacao_id = db.Column(db.Integer, db.ForeignKey("movimentacoes.id"))  # entrada gerada no estoque
    criado_em = db.Column(db.DateTime, default=agora)
    criado_por = db.Column(db.String(120))

    nota = db.relationship("NotaFiscal", backref=db.backref("vinculos_pedido", cascade="all, delete-orphan"))
    pedido_item = db.relationship("PedidoERPItem", back_populates="vinculos")
    nota_item = db.relationship("NotaItem")
    movimentacao = db.relationship("Movimentacao")



class NotaOrdemMC(db.Model):
    """Vínculo nota fiscal x Ordem de Compra do Mais Controle (pelo NÚMERO da OC, que é estável:
    a lista de OCs é recarregada inteira a cada importação de PDF)."""
    __tablename__ = "notas_ordens_mc"
    __table_args__ = (db.UniqueConstraint("nota_id", "ordem_numero", name="uq_nota_ordem_mc"),)
    id = db.Column(db.Integer, primary_key=True)
    nota_id = db.Column(db.Integer, db.ForeignKey("notas_fiscais.id"), nullable=False, index=True)
    ordem_numero = db.Column(db.Integer, nullable=False, index=True)
    valor = db.Column(db.Float)          # parte do valor da nota atribuída a esta OC
    criado_em = db.Column(db.DateTime, default=agora)
    criado_por = db.Column(db.String(120))

    nota = db.relationship("NotaFiscal", backref=db.backref("vinculos_mc", cascade="all, delete-orphan"))

    @property
    def ordem(self):
        return OrdemCompraMC.query.filter_by(numero=self.ordem_numero).first()


# ---------------------------------------------------------------- mapa de cotação (feito no sistema)

class Cotacao(db.Model):
    """Mapa de cotação: itens de 'Materiais a Comprar' x fornecedores, com preço de cada um e o vencedor."""
    __tablename__ = "cotacoes"
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200))
    observacao = db.Column(db.Text)
    status = db.Column(db.String(20), default="Aberta", index=True)   # Aberta | Finalizada | Cancelada
    criada_em = db.Column(db.DateTime, default=agora, index=True)
    criado_por = db.Column(db.String(120))
    finalizada_em = db.Column(db.DateTime)
    finalizada_por = db.Column(db.String(120))

    itens = db.relationship("CotacaoItem", back_populates="cotacao", cascade="all, delete-orphan",
                            order_by="CotacaoItem.id")
    fornecedores = db.relationship("CotacaoFornecedor", back_populates="cotacao", cascade="all, delete-orphan",
                                   order_by="CotacaoFornecedor.id")

    @property
    def numero(self):
        return f"C-{self.id:04d}"

    def total_fornecedor(self, forn):
        """(total, itens cotados) do fornecedor."""
        total, n = 0.0, 0
        for it in self.itens:
            p = it.preco_de(forn)
            if p and p.valor_unitario:
                total += p.valor_unitario * (it.quantidade or 0)
                n += 1
        return total, n

    @property
    def total_vencedores(self):
        return sum((it.preco_vencedor or 0) * (it.quantidade or 0) for it in self.itens)


class CotacaoItem(db.Model):
    __tablename__ = "cotacao_itens"
    id = db.Column(db.Integer, primary_key=True)
    cotacao_id = db.Column(db.Integer, db.ForeignKey("cotacoes.id"), nullable=False, index=True)
    compra_id = db.Column(db.Integer, db.ForeignKey("compras.id"), index=True)
    descricao = db.Column(db.String(255), nullable=False)
    unidade = db.Column(db.String(20))
    quantidade = db.Column(db.Float, default=0)
    vencedor_id = db.Column(db.Integer, db.ForeignKey("cotacao_fornecedores.id"))

    cotacao = db.relationship("Cotacao", back_populates="itens")
    compra = db.relationship("Compra", backref=db.backref("cotacao_itens", lazy="dynamic"))
    vencedor = db.relationship("CotacaoFornecedor", foreign_keys=[vencedor_id])
    precos = db.relationship("CotacaoPreco", back_populates="item", cascade="all, delete-orphan")

    def preco_de(self, forn):
        return next((p for p in self.precos if p.fornecedor is forn or (forn.id and p.fornecedor_id == forn.id)), None)

    @property
    def menor(self):
        validos = [p for p in self.precos if p.valor_unitario]
        return min(validos, key=lambda p: p.valor_unitario) if validos else None

    @property
    def preco_vencedor(self):
        p = self.preco_de(self.vencedor) if self.vencedor else None
        return p.valor_unitario if p else None


class CotacaoFornecedor(db.Model):
    __tablename__ = "cotacao_fornecedores"
    id = db.Column(db.Integer, primary_key=True)
    cotacao_id = db.Column(db.Integer, db.ForeignKey("cotacoes.id"), nullable=False, index=True)
    nome = db.Column(db.String(200), nullable=False)
    cnpj = db.Column(db.String(14))
    contato = db.Column(db.String(120))
    prazo_entrega = db.Column(db.String(60))
    condicao = db.Column(db.String(60))
    frete = db.Column(db.Float)
    observacao = db.Column(db.String(255))

    cotacao = db.relationship("Cotacao", back_populates="fornecedores")


class CotacaoPreco(db.Model):
    __tablename__ = "cotacao_precos"
    __table_args__ = (db.UniqueConstraint("item_id", "fornecedor_id", name="uq_cotacao_preco"),)
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("cotacao_itens.id"), nullable=False, index=True)
    fornecedor_id = db.Column(db.Integer, db.ForeignKey("cotacao_fornecedores.id"), nullable=False, index=True)
    valor_unitario = db.Column(db.Float)

    item = db.relationship("CotacaoItem", back_populates="precos")
    fornecedor = db.relationship("CotacaoFornecedor")


class CategoriaGasto(db.Model):
    """Classificação dos gastos no padrão do Mais Controle (Configurações > Categorias):
    categoria -> plano de contas -> resultado (DRE) e 'Classificação em Gestão de Obra'.
    Vale para os dois sistemas: categorias do Omie são classificadas pelo nome (ou manualmente)."""
    __tablename__ = "categorias_gasto"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    nome_norm = db.Column(db.String(200), unique=True, index=True, nullable=False)
    plano_conta = db.Column(db.String(120))
    resultado = db.Column(db.String(60))        # Despesas Operacionais | Despesas Variáveis | Resultado Financeiro ...
    classificacao = db.Column(db.String(60))    # Materiais | Equipamentos | Mão de Obra (...) | Compra de Terreno | Outros | Oculta na Gestão
    origem = db.Column(db.String(20), default="maiscontrole")   # maiscontrole | manual
    atualizado_em = db.Column(db.DateTime, default=agora, onupdate=agora)


# ---------------------------------------------------------------- base financeira unificada (pagar e receber)

class TituloFinanceiro(db.Model):
    """Uma PARCELA a pagar ou a receber, montada a partir das tabelas copiadas das APIs.

    Mais Controle: lancamentos + pagamentos (pagar) e faturamentos + recebimentos (receber), chave
    id + nº da parcela. Omie: contas_pagar / contas_receber. Reconstruída a cada atualização das APIs.
    Base do fluxo de caixa projetado, do BI Financeiro, do Multiobras e do BI Compras (com/sem OC)."""
    __tablename__ = "titulos_financeiros"
    __table_args__ = (db.UniqueConstraint("empresa_id", "tipo", "chave", name="uq_titulo_fin"),)
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True)
    tipo = db.Column(db.String(8), nullable=False, index=True)        # pagar | receber
    origem = db.Column(db.String(12))                                  # maiscontrole | omie
    chave = db.Column(db.String(80), nullable=False)
    nome = db.Column(db.String(200), index=True)                       # fornecedor / cliente
    documento = db.Column(db.String(80))
    descricao = db.Column(db.String(255))
    centro_custo = db.Column(db.String(200), index=True)
    obra_ext = db.Column(db.String(40), index=True)                    # id da obra no Mais Controle
    categoria = db.Column(db.String(160))
    grupo = db.Column(db.String(60))                                   # grupo do Mais Controle (Materiais, ...)
    plano = db.Column(db.String(160))
    natureza = db.Column(db.String(80))                                # receitas: Contrato, Empréstimo...
    ordem_compra = db.Column(db.String(40))                            # OC do Mais Controle / pedido do Omie
    conta_bancaria = db.Column(db.String(120))
    parcela = db.Column(db.String(20))
    competencia = db.Column(db.Date, index=True)
    vencimento = db.Column(db.Date, index=True)
    valor = db.Column(db.Float, default=0)
    valor_baixado = db.Column(db.Float, default=0)                     # pago / recebido
    valor_desconto = db.Column(db.Float, default=0)                    # desconto / retenção dado na baixa
    baixado_em = db.Column(db.Date, index=True)
    aberto = db.Column(db.Boolean, default=True, index=True)
    status = db.Column(db.String(40))

    empresa = db.relationship("Empresa")

    @property
    def saldo(self):
        return max(0.0, (self.valor or 0) - (self.valor_baixado or 0) - (self.valor_desconto or 0)) if self.aberto else 0.0


class ObraResumoMC(db.Model):
    """Resumo de cada obra do Mais Controle (orçamento, medições, cronograma) calculado na atualização."""
    __tablename__ = "mc_obras_resumo"
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), index=True)
    obra_ext = db.Column(db.String(40), index=True, nullable=False)
    nome = db.Column(db.String(200))
    status = db.Column(db.String(40))
    tipo = db.Column(db.String(40))
    cliente = db.Column(db.String(200))
    area = db.Column(db.Float)
    dados = db.Column(db.JSON)       # orçamento por tipo, medições, cronograma, etapas


class BoletoDDA(db.Model):
    """Boleto do DDA (arquivo exportado do banco) e o título do sistema a que corresponde."""
    __tablename__ = "boletos_dda"
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), index=True)
    beneficiario = db.Column(db.String(200))
    cnpj = db.Column(db.String(14))
    vencimento = db.Column(db.Date, index=True)
    valor = db.Column(db.Float)
    linha = db.Column(db.String(60))
    documento = db.Column(db.String(60))       # nº do documento do boleto
    pagador = db.Column(db.String(200))        # como veio no DDA (F. DINIZ, VIEIRA DINIZ, RAMOS...)
    tipo = db.Column(db.String(60))            # DM duplicata mercantil, DS serviço, RC recibo...
    banco = db.Column(db.String(5))
    arquivo = db.Column(db.String(200))
    importado_em = db.Column(db.DateTime, default=agora)
    # o título é reconstruído a cada atualização das APIs: o vínculo é pela chave, não pelo id
    titulo_empresa_id = db.Column(db.Integer)
    titulo_chave = db.Column(db.String(80))
    manual = db.Column(db.Boolean, default=False)      # vínculo/ignorar feito à mão
    conferir = db.Column(db.Integer, default=0)        # >1: há N contas a pagar possíveis — escolher à mão
    ignorado = db.Column(db.Boolean, default=False)

    empresa = db.relationship("Empresa")

    @property
    def titulo(self):
        if not self.titulo_chave:
            return None
        return TituloFinanceiro.query.filter_by(empresa_id=self.titulo_empresa_id, tipo="pagar",
                                                chave=self.titulo_chave).first()


# ---------------------------------------------------------------- painel de demandas (implantação)

class Demanda(db.Model):
    """Lista de demandas da implantação (o que já foi feito e o que falta), por setor. Pode ser excluída no fim."""
    __tablename__ = "demandas"
    id = db.Column(db.Integer, primary_key=True)
    setor = db.Column(db.String(40), nullable=False, index=True)
    item = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(30), default="Falta")      # Feito | Validar | Parcial | Falta | Depende de dados
    prioridade = db.Column(db.Boolean, default=False)          # marcado (marca-texto) na folha
    onde = db.Column(db.String(200))                           # onde está no sistema
    obs = db.Column(db.Text)
    ordem = db.Column(db.Integer, default=0)
    atualizado_em = db.Column(db.DateTime, default=agora, onupdate=agora)
    atualizado_por = db.Column(db.String(120))


# ---------------------------------------------------------------- pagamento em lote (remessa ao banco)

class LotePagamento(db.Model):
    __tablename__ = "lotes_pagamento"
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), index=True)
    data_pagamento = db.Column(db.Date)
    criado_em = db.Column(db.DateTime, default=agora)
    criado_por = db.Column(db.String(120))
    sequencial = db.Column(db.Integer)          # nº do arquivo de remessa
    status = db.Column(db.String(30), default="Gerado")   # Gerado | Enviado ao banco | Cancelado
    total = db.Column(db.Float, default=0)
    obs = db.Column(db.String(255))

    empresa = db.relationship("Empresa")
    itens = db.relationship("LotePagamentoItem", back_populates="lote", cascade="all, delete-orphan",
                            order_by="LotePagamentoItem.id")

    @property
    def numero(self):
        return f"LOTE-{self.id:04d}"


class LotePagamentoItem(db.Model):
    __tablename__ = "lotes_pagamento_itens"
    id = db.Column(db.Integer, primary_key=True)
    lote_id = db.Column(db.Integer, db.ForeignKey("lotes_pagamento.id"), nullable=False, index=True)
    titulo_empresa_id = db.Column(db.Integer)
    titulo_chave = db.Column(db.String(80), index=True)
    nome = db.Column(db.String(200))
    documento = db.Column(db.String(80))
    centro_custo = db.Column(db.String(200))
    vencimento = db.Column(db.Date)
    valor = db.Column(db.Float)
    linha = db.Column(db.String(60))            # linha digitável / código de barras (boleto)
    forma = db.Column(db.String(20))            # boleto_itau | boleto_outros | sem_codigo

    lote = db.relationship("LotePagamento", back_populates="itens")


# ---------------------------------------------------------------- SEFAZ: certificado A1 e NF-e recebidas

class CertificadoDigital(db.Model):
    """Certificado A1 (.pfx) de cada empresa, guardado CRIPTOGRAFADO. A senha fica só no Render (variável)."""
    __tablename__ = "certificados_digitais"
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), unique=True, nullable=False)
    arquivo = db.Column(db.LargeBinary, nullable=False)       # .pfx criptografado
    nome_arquivo = db.Column(db.String(200))
    titular = db.Column(db.String(200))
    cnpj = db.Column(db.String(14))
    valido_ate = db.Column(db.DateTime)
    enviado_em = db.Column(db.DateTime, default=agora)
    enviado_por = db.Column(db.String(120))

    empresa = db.relationship("Empresa")


class NFeRecebida(db.Model):
    """NF-e emitida CONTRA o CNPJ da empresa, trazida da SEFAZ (distribuição de documentos fiscais)."""
    __tablename__ = "nfe_recebidas"
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), index=True)
    chave = db.Column(db.String(44), unique=True, index=True, nullable=False)
    nsu = db.Column(db.String(20))
    emitente_cnpj = db.Column(db.String(14), index=True)
    emitente_nome = db.Column(db.String(200))
    emissao = db.Column(db.DateTime, index=True)
    valor = db.Column(db.Float)
    situacao = db.Column(db.String(20))          # Autorizada | Cancelada | Denegada
    xml = db.Column(db.Text)                     # procNFe completo (depois da Ciência da Operação)
    manifestada_em = db.Column(db.DateTime)
    manifesto_msg = db.Column(db.String(255))
    ignorada = db.Column(db.Boolean, default=False)
    recebida_em = db.Column(db.DateTime, default=agora)

    empresa = db.relationship("Empresa")


# ---------------------------------------------------------------- saldos bancários

class ContaBancaria(db.Model):
    """Conta bancária de uma empresa com o último saldo conhecido (Omie, extrato OFX do banco ou digitado)."""
    __tablename__ = "contas_bancarias"
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), index=True)
    origem = db.Column(db.String(10))                  # omie | ofx | manual
    chave = db.Column(db.String(80), unique=True)      # omie:<nCodCC> | ofx:<banco>:<agencia>:<conta>
    nome = db.Column(db.String(120))
    banco = db.Column(db.String(10))
    agencia = db.Column(db.String(20))
    conta = db.Column(db.String(30))
    saldo = db.Column(db.Float)
    saldo_em = db.Column(db.Date)
    ativa = db.Column(db.Boolean, default=True)
    atualizado_em = db.Column(db.DateTime, default=agora, onupdate=agora)
    obs = db.Column(db.String(255))

    empresa = db.relationship("Empresa")
    movimentos = db.relationship("MovimentoBancario", back_populates="conta_bancaria", cascade="all, delete-orphan")


class MovimentoBancario(db.Model):
    """Lançamento do extrato do banco (importado do OFX)."""
    __tablename__ = "movimentos_bancarios"
    __table_args__ = (db.UniqueConstraint("conta_id", "fitid", name="uq_mov_banco"),)
    id = db.Column(db.Integer, primary_key=True)
    conta_id = db.Column(db.Integer, db.ForeignKey("contas_bancarias.id"), index=True, nullable=False)
    fitid = db.Column(db.String(80), nullable=False)
    data = db.Column(db.Date, index=True)
    valor = db.Column(db.Float)                        # + crédito / − débito
    descricao = db.Column(db.String(255))

    conta_bancaria = db.relationship("ContaBancaria", back_populates="movimentos")


class FotoEntrega(db.Model):
    """Foto do material: no carregamento do caminhão (almoxarife/motorista) ou no recebimento na obra (encarregado)."""
    __tablename__ = "fotos_entrega"
    id = db.Column(db.Integer, primary_key=True)
    solicitacao_id = db.Column(db.Integer, db.ForeignKey("solicitacoes.id"), index=True, nullable=False)
    tipo = db.Column(db.String(20), default="carregamento")     # carregamento | recebimento
    imagem = db.Column(db.LargeBinary, nullable=False)          # JPEG reduzido
    obs = db.Column(db.String(255))
    criado_em = db.Column(db.DateTime, default=agora)
    criado_por = db.Column(db.String(120))

    solicitacao = db.relationship("Solicitacao", backref=db.backref("fotos", order_by="FotoEntrega.id",
                                                                      cascade="all, delete-orphan"))


class NFSeEmitida(db.Model):
    """Nota fiscal de SERVIÇO emitida pela empresa (prefeitura do Recife, webservice ABRASF com o certificado A1)."""
    __tablename__ = "nfse_emitidas"
    __table_args__ = (db.UniqueConstraint("empresa_id", "numero", name="uq_nfse_emitida"),)
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True)
    numero = db.Column(db.String(20), nullable=False)
    codigo_verificacao = db.Column(db.String(40))
    data_emissao = db.Column(db.DateTime, index=True)
    competencia = db.Column(db.Date, index=True)
    rps = db.Column(db.String(30))
    tomador_nome = db.Column(db.String(200), index=True)
    tomador_doc = db.Column(db.String(14))
    discriminacao = db.Column(db.Text)
    item_servico = db.Column(db.String(10))
    valor_servicos = db.Column(db.Float, default=0)
    valor_deducoes = db.Column(db.Float, default=0)
    valor_pis = db.Column(db.Float, default=0)
    valor_cofins = db.Column(db.Float, default=0)
    valor_inss = db.Column(db.Float, default=0)
    valor_ir = db.Column(db.Float, default=0)
    valor_csll = db.Column(db.Float, default=0)
    iss_retido = db.Column(db.Boolean, default=False)
    aliquota = db.Column(db.Float)
    valor_iss = db.Column(db.Float, default=0)
    valor_liquido = db.Column(db.Float, default=0)
    cancelada = db.Column(db.Boolean, default=False, index=True)
    cancelada_em = db.Column(db.DateTime)
    obra = db.Column(db.String(200))          # obra / centro de custo informado à mão
    xml = db.Column(db.Text)
    chave = db.Column(db.String(60), index=True)   # chave de acesso nacional (Emissor Nacional, desde 2026 no Recife)
    xml_nacional = db.Column(db.Text)              # XML da NFS-e nacional (ADN): base do DANFSe no padrão nacional
    atualizado_em = db.Column(db.DateTime, default=agora, onupdate=agora)

    empresa = db.relationship("Empresa")

    @property
    def retencoes(self):
        return round((self.valor_pis or 0) + (self.valor_cofins or 0) + (self.valor_inss or 0) + (self.valor_ir or 0)
                     + (self.valor_csll or 0) + ((self.valor_iss or 0) if self.iss_retido else 0), 2)


class FornecedorBase(db.Model):
    """Cadastro de fornecedores para as cotações (planilha importada do Mais Controle ou incluídos aqui)."""
    __tablename__ = "fornecedores_base"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False, index=True)
    cnpj = db.Column(db.String(14), index=True)
    contato = db.Column(db.String(120))
    telefone = db.Column(db.String(40))
    email = db.Column(db.String(160))
    segmento = db.Column(db.String(120))
    origem = db.Column(db.String(30))          # planilha | manual
    ativo = db.Column(db.Boolean, default=True)
    atualizado_em = db.Column(db.DateTime, default=agora, onupdate=agora)


class NFSeRecebida(db.Model):
    """NFS-e em que a empresa é TOMADORA (serviço contratado) — Ambiente de Dados Nacional (ADN), com o certificado A1."""
    __tablename__ = "nfse_recebidas"
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True)
    chave = db.Column(db.String(60), unique=True, index=True, nullable=False)
    nsu = db.Column(db.BigInteger, index=True)
    numero = db.Column(db.String(20))
    data_emissao = db.Column(db.DateTime, index=True)
    competencia = db.Column(db.Date, index=True)
    prestador_nome = db.Column(db.String(200), index=True)
    prestador_doc = db.Column(db.String(14), index=True)
    municipio = db.Column(db.String(120))
    servico = db.Column(db.String(255))
    discriminacao = db.Column(db.Text)
    valor_servicos = db.Column(db.Float, default=0)
    valor_iss = db.Column(db.Float, default=0)
    iss_retido = db.Column(db.Boolean, default=False)
    valor_retencoes = db.Column(db.Float, default=0)
    valor_liquido = db.Column(db.Float, default=0)
    cancelada = db.Column(db.Boolean, default=False, index=True)
    obra = db.Column(db.String(200))
    xml = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=agora)

    empresa = db.relationship("Empresa")


class BaixaFinanceira(db.Model):
    """Cada recebimento / pagamento de uma parcela, com a data em que aconteceu (uma parcela pode ser
    recebida em várias vezes). Base do realizado mês a mês. Reconstruída junto com os títulos."""
    __tablename__ = "baixas_financeiras"
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True)
    tipo = db.Column(db.String(8), nullable=False)
    chave = db.Column(db.String(80), nullable=False, index=True)       # chave do TituloFinanceiro
    data = db.Column(db.Date, nullable=False, index=True)
    valor = db.Column(db.Float, default=0)


class AcessoRecente(db.Model):
    """Telas que cada usuário abriu (para o Acesso rápido do Início)."""
    __tablename__ = "acessos_recentes"
    __table_args__ = (db.UniqueConstraint("usuario_id", "endpoint", name="uq_acesso_recente"),)
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, index=True)
    endpoint = db.Column(db.String(120), nullable=False)
    contagem = db.Column(db.Integer, default=0)
    ultimo_em = db.Column(db.DateTime, default=agora, index=True)



# ================================================================ Planejamento de obras (cronograma, distribuição,
# programação diária dos funcionários e rateio por centro de custo)

class PlanEncarregado(db.Model):
    __tablename__ = "plan_encarregados"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    cor = db.Column(db.String(9), default="#CBD5E1")
    ordem = db.Column(db.Integer, default=0)
    ativo = db.Column(db.Boolean, default=True)


class PlanProcesso(db.Model):
    __tablename__ = "plan_processos"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    cor = db.Column(db.String(9), default="#E2E8F0")
    ordem = db.Column(db.Integer, default=0)
    ativo = db.Column(db.Boolean, default=True)


class PlanStatus(db.Model):
    __tablename__ = "plan_status"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(60), nullable=False)
    cor = db.Column(db.String(9), default="#E2E8F0")
    ordem = db.Column(db.Integer, default=0)


class PlanObra(db.Model):
    """Obra / frente do planejamento (nome curto como na planilha: WEINI, MARCINHO...) ou local que não é obra
    (Escritório, Férias, Dispensado, Feriado)."""
    __tablename__ = "plan_obras"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    encarregado_id = db.Column(db.Integer, db.ForeignKey("plan_encarregados.id"))
    obra_id = db.Column(db.Integer, db.ForeignKey("obras.id"))          # obra do sistema (opcional)
    centro_custo = db.Column(db.String(200))                            # como no financeiro (para o rateio)
    tipo = db.Column(db.String(12), default="obra")                     # obra | escritorio | ausencia
    cor = db.Column(db.String(9))                                       # sem cor = cor do encarregado
    ordem = db.Column(db.Integer, default=0)
    ativo = db.Column(db.Boolean, default=True)

    encarregado = db.relationship("PlanEncarregado")
    obra = db.relationship("Obra")

    @property
    def cor_final(self):
        if self.cor:
            return self.cor
        if self.encarregado and self.encarregado.cor:
            return self.encarregado.cor
        return {"escritorio": "#E5E7EB", "ausencia": "#1D4ED8"}.get(self.tipo, "#E2E8F0")

    @property
    def cc(self):
        return self.centro_custo or (self.obra.nome if self.obra else None) or self.nome


class PlanServico(db.Model):
    """Card do cronograma: um processo numa obra, com a equipe e a situação."""
    __tablename__ = "plan_servicos"
    id = db.Column(db.Integer, primary_key=True)
    plan_obra_id = db.Column(db.Integer, db.ForeignKey("plan_obras.id"), nullable=False, index=True)
    processo_id = db.Column(db.Integer, db.ForeignKey("plan_processos.id"), nullable=False, index=True)
    status_id = db.Column(db.Integer, db.ForeignKey("plan_status.id"))
    equipe = db.Column(db.String(255))
    descricao = db.Column(db.String(255))
    inicio = db.Column(db.Date)
    fim = db.Column(db.Date)
    ordem = db.Column(db.Integer, default=0)
    atualizado_em = db.Column(db.DateTime, default=agora, onupdate=agora)
    atualizado_por = db.Column(db.String(120))

    plan_obra = db.relationship("PlanObra")
    processo = db.relationship("PlanProcesso")
    status = db.relationship("PlanStatus")


class FuncionarioObra(db.Model):
    """Funcionário de obra (pedreiro, servente, pintor...) e onde está alocado agora (distribuição)."""
    __tablename__ = "funcionarios_obra"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    funcao = db.Column(db.String(60))
    plan_obra_id = db.Column(db.Integer, db.ForeignKey("plan_obras.id"))      # distribuição atual
    encarregado_id = db.Column(db.Integer, db.ForeignKey("plan_encarregados.id"))  # volante nas obras do encarregado
    proximas = db.Column(db.String(255))   # sequência das próximas obras do serviço (ex.: SUPERNOVA → BERNADETE)
    processo_id = db.Column(db.Integer, db.ForeignKey("plan_processos.id"))   # frente em que trabalha
    telefone = db.Column(db.String(30))
    ativo = db.Column(db.Boolean, default=True)
    obs = db.Column(db.String(255))
    ordem = db.Column(db.Integer, default=0)

    plan_obra = db.relationship("PlanObra")
    encarregado = db.relationship("PlanEncarregado")
    processo = db.relationship("PlanProcesso")


class AlocacaoDia(db.Model):
    """Programação diária: em que obra o funcionário trabalhou / vai trabalhar no dia (fração se dividiu o dia)."""
    __tablename__ = "alocacoes_dia"
    __table_args__ = (db.UniqueConstraint("funcionario_id", "data", "plan_obra_id", name="uq_alocacao_dia"),)
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey("funcionarios_obra.id"), nullable=False, index=True)
    data = db.Column(db.Date, nullable=False, index=True)
    plan_obra_id = db.Column(db.Integer, db.ForeignKey("plan_obras.id"), nullable=False)
    fracao = db.Column(db.Float, default=1.0)

    plan_obra = db.relationship("PlanObra")


class RateioValor(db.Model):
    """Valores do mês por funcionário (folha, adiantamento, VT, diárias) para o rateio por centro de custo."""
    __tablename__ = "rateio_valores"
    __table_args__ = (db.UniqueConstraint("funcionario_id", "mes", name="uq_rateio_valor"),)
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey("funcionarios_obra.id"), nullable=False)
    mes = db.Column(db.String(7), nullable=False)      # 2026-10
    folha = db.Column(db.Float, default=0)
    adiantamento = db.Column(db.Float, default=0)
    vt = db.Column(db.Float, default=0)
    diarias = db.Column(db.Float, default=0)


# ================================================================ Caixinha (cartão pré-pago dos encarregados)

class CaixaCartao(db.Model):
    """Cartão da caixinha de um encarregado: recargas do financeiro e gastos com foto enviados pelo encarregado."""
    __tablename__ = "caixa_cartoes"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, index=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"))
    descricao = db.Column(db.String(120))          # ex.: "Cartão Caixa final 1234"
    alerta_pct = db.Column(db.Float, default=20)   # avisa quando o saldo chega a X% do valor disponível na última recarga
    alerta_enviado_em = db.Column(db.DateTime)     # zera a cada recarga
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=agora)

    usuario = db.relationship("Usuario")
    empresa = db.relationship("Empresa")
    movimentos = db.relationship("CaixaMovimento", back_populates="cartao", cascade="all, delete-orphan",
                                 order_by="CaixaMovimento.data.desc(), CaixaMovimento.id.desc()")

    @property
    def nome(self):
        return f"{self.usuario.nome if self.usuario else '?'}" + (f" · {self.descricao}" if self.descricao else "")


class CaixaMovimento(db.Model):
    """Recarga (crédito) ou gasto (débito, com foto do comprovante, categoria e obra / centro de custo)."""
    __tablename__ = "caixa_movimentos"
    id = db.Column(db.Integer, primary_key=True)
    cartao_id = db.Column(db.Integer, db.ForeignKey("caixa_cartoes.id"), nullable=False, index=True)
    tipo = db.Column(db.String(10), nullable=False)        # recarga | gasto | ajuste
    data = db.Column(db.Date, nullable=False, index=True)
    valor = db.Column(db.Float, nullable=False)            # sempre positivo (ajuste pode ser negativo)
    categoria = db.Column(db.String(120))
    obra_id = db.Column(db.Integer, db.ForeignKey("obras.id"))
    centro_custo = db.Column(db.String(200))               # quando não é obra (ex.: Empresa)
    descricao = db.Column(db.String(255))                  # onde comprou / o quê
    foto = db.Column(db.LargeBinary)
    status = db.Column(db.String(12), default="enviado")   # gasto: enviado | conferido | devolvido
    obs_conferencia = db.Column(db.String(255))
    conferido_por = db.Column(db.String(120))
    conferido_em = db.Column(db.DateTime)
    criado_por = db.Column(db.String(120))
    criado_em = db.Column(db.DateTime, default=agora)

    cartao = db.relationship("CaixaCartao", back_populates="movimentos")
    obra = db.relationship("Obra")

    @property
    def cc(self):
        return self.obra.nome if self.obra else (self.centro_custo or "—")


class CaixaCategoria(db.Model):
    __tablename__ = "caixa_categorias"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    ordem = db.Column(db.Integer, default=0)
    ativo = db.Column(db.Boolean, default=True)


class PosicaoVeiculo(db.Model):
    """Posição do motorista (GPS do celular, com a Rota do motorista aberta e o compartilhamento ligado)."""
    __tablename__ = "posicoes_veiculo"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, index=True)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    precisao = db.Column(db.Float)          # metros
    velocidade = db.Column(db.Float)        # km/h
    registrado_em = db.Column(db.DateTime, default=agora, index=True)

    usuario = db.relationship("Usuario")
