def registrar_blueprints(app):
    from .aprovacoes import bp as aprovacoes
    from .auth import bp as auth
    from .bi import bp as bi
    from .caixinha import bp as caixinha
    from .compras import bp as compras
    from .cotacoes import bp as cotacoes
    from .demandas import bp as demandas
    from .estoque import bp as estoque
    from .financeiro_bi import bp as fin_bi
    from .gerencial import bp as gerencial
    from .integracoes import bp as integracoes
    from .main import bp as main
    from .nfse import bp as nfse
    from .notas import bp as notas
    from .obras import bp as obras
    from .planejamento import bp as planejamento
    from .rastreio import bp as rastreio
    from .sefaz import bp as sefaz
    from .setores import bp as setores
    from .solicitacoes import bp as solicitacoes
    from .usuarios import bp as usuarios

    for bp in (auth, main, bi, gerencial, obras, estoque, solicitacoes, compras, cotacoes, aprovacoes, notas, usuarios, integracoes, setores, fin_bi, demandas, sefaz, nfse, planejamento, caixinha, rastreio):
        app.register_blueprint(bp)
