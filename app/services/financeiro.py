"""Importação das contas a pagar de cada empresa para o painel de indicadores.

F. Diniz Engenharia  -> Omie        (API JSON: financas/contapagar ListarContasPagar
                                      + geral/clientes ListarClientesResumido para o nome do fornecedor)
Ramos Diniz          -> Mais Controle (API para Relatórios: https://api-clientes.maiscontroleerp.com.br/data-exports/...)

Credenciais ficam SÓ no Render (Environment), nunca no código:
  OMIE_FDINIZ_APP_KEY / OMIE_FDINIZ_APP_SECRET   (se vazias, usa OMIE_APP_KEY / OMIE_APP_SECRET)
  MAISCONTROLE_API_USUARIO / MAISCONTROLE_API_SENHA

A sincronização roda em segundo plano (pode levar alguns minutos) e grava o resultado em
Integrações -> Registro. A API do Mais Controle no plano gratuito é atualizada aos domingos.
"""
import csv
import io
import os
import threading
import unicodedata
from datetime import date, datetime

import requests

from ..extensions import db
from ..models import DadoImportado, Empresa, LancamentoFinanceiro, LogIntegracao, agora

MC_BASE = "https://api-clientes.maiscontroleerp.com.br/data-exports/"
MC_TABELAS = ["pagamentos", "lancamentos"]
# todas as tabelas da "API para Relatórios" do Mais Controle
MC_TODAS = {"lancamentos": "lancamentos", "pagamentos": "pagamentos", "faturamentos": "faturamentos",
            "recebimentos": "recebimentos", "obras": "obras", "cronogramas": "cronogramas",
            "orcamentos": "items-orcamentos", "medicoes": "medicoes", "propostas": "propostas"}
# rotinas do Omie para o painel financeiro: (módulo, método, lista na resposta, campo-chave)
OMIE_TODAS = {
    "contas_pagar": ("financas/contapagar", "ListarContasPagar", "conta_pagar_cadastro", "codigo_lancamento_omie"),
    "contas_receber": ("financas/contareceber", "ListarContasReceber", "conta_receber_cadastro", "codigo_lancamento_omie"),
    "categorias": ("geral/categorias", "ListarCategorias", "categoria_cadastro", "codigo"),
    "projetos": ("geral/projetos", "ListarProjetos", "cadastro", "codigo"),
    "fornecedores_clientes": ("geral/clientes", "ListarClientesResumido", "clientes_cadastro_resumido", "codigo_cliente"),
}

_em_andamento = set()


def _norm(t):
    t = unicodedata.normalize("NFD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return "".join(ch if ch.isalnum() else "_" for ch in t).strip("_")


def _data(v):
    if not v:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    try:
        return datetime.strptime(s[:10], "%d/%m/%Y").date()
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(s[:19].replace("Z", "")).date()
    except ValueError:
        return None


def _num(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace("R$", "").strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def credenciais(empresa):
    if empresa.sistema == "omie":
        k = os.environ.get("OMIE_FDINIZ_APP_KEY") or os.environ.get("OMIE_APP_KEY")
        s = os.environ.get("OMIE_FDINIZ_APP_SECRET") or os.environ.get("OMIE_APP_SECRET")
        return (k, s) if k and s else None
    u, p = os.environ.get("MAISCONTROLE_API_USUARIO"), os.environ.get("MAISCONTROLE_API_SENHA")
    return (u, p) if u and p else None


def _log(sistema, operacao, ok, msg):
    db.session.add(LogIntegracao(sistema=sistema, operacao=operacao, sucesso=ok, mensagem=msg[:4000]))
    db.session.commit()


def _gravar(empresa, registros):
    existentes = {l.id_externo: l for l in LancamentoFinanceiro.query.filter_by(empresa_id=empresa.id)}
    novos = 0
    for r in registros:
        if not r.get("id_externo"):
            continue
        l = existentes.get(r["id_externo"])
        if not l:
            l = LancamentoFinanceiro(empresa_id=empresa.id, id_externo=r["id_externo"])
            db.session.add(l)
            existentes[r["id_externo"]] = l
            novos += 1
        for k, v in r.items():
            if k != "id_externo":
                setattr(l, k, v)
    empresa.ultima_sincronizacao = agora()
    db.session.commit()
    return novos


# ---------------------------------------------------------------- Omie

def _omie_paginas(cli, modulo, call, chave_lista, extra=None, max_paginas=60):
    pagina, total = 1, 1
    while pagina <= min(total, max_paginas):
        d = cli.chamar(modulo, call, dict({"pagina": pagina, "registros_por_pagina": 500,
                                           "apenas_importado_api": "N"}, **(extra or {})))
        total = int(d.get("total_de_paginas") or 1)
        for x in d.get(chave_lista) or []:
            yield x
        pagina += 1


def _omie_movimentos(cli, max_paginas=80):
    """Movimentos financeiros (financas/mf ListarMovimentos): o único método do Omie que traz o valor já pago /
    recebido (inclusive baixa parcial) e a data do pagamento de cada título. Guarda só o necessário."""
    pagina, total = 1, 1
    while pagina <= min(total, max_paginas):
        d = cli.chamar("financas/mf/", "ListarMovimentos", {"nPagina": pagina, "nRegPorPagina": 500})
        total = int(d.get("nTotPaginas") or d.get("total_de_paginas") or 1)
        for m in d.get("movimentos") or []:
            det, res = m.get("detalhes") or {}, m.get("resumo") or {}
            if det.get("nCodTitulo"):
                yield {"nCodTitulo": det.get("nCodTitulo"), "cStatus": det.get("cStatus"),
                       "cNatureza": det.get("cNatureza"), "dDtPagamento": det.get("dDtPagamento"),
                       "dDtVenc": det.get("dDtVenc"), "nValorTitulo": det.get("nValorTitulo"),
                       "cLiquidado": res.get("cLiquidado"), "nValPago": res.get("nValPago"),
                       "nValAberto": res.get("nValAberto"), "nDesconto": res.get("nDesconto")}
        pagina += 1


def sincronizar_omie(empresa):
    from .omie import OmieClient
    k, s = credenciais(empresa)
    cli = OmieClient(app_key=k, app_secret=s, timeout=60)
    nomes = {}
    for c in _omie_paginas(cli, "geral/clientes", "ListarClientesResumido", "clientes_cadastro_resumido"):
        nomes[str(c.get("codigo_cliente"))] = c.get("nome_fantasia") or c.get("razao_social")
    regs = []
    for c in _omie_paginas(cli, "financas/contapagar", "ListarContasPagar", "conta_pagar_cadastro"):
        status = (c.get("status_titulo") or "").upper()
        regs.append({
            "id_externo": str(c.get("codigo_lancamento_omie")),
            "fornecedor": nomes.get(str(c.get("codigo_cliente_fornecedor"))) or f"Fornecedor {c.get('codigo_cliente_fornecedor')}",
            "documento": c.get("numero_documento_fiscal") or c.get("numero_documento"),
            "categoria": c.get("codigo_categoria"),
            "emissao": _data(c.get("data_emissao")) or _data(c.get("data_entrada")),
            "vencimento": _data(c.get("data_vencimento")),
            "valor": _num(c.get("valor_documento")),
            "status": status,
            "pago_em": _data(c.get("data_vencimento")) if status in ("PAGO", "LIQUIDADO") else None,
        })
    return regs


# ---------------------------------------------------------------- Mais Controle

ALIASES = {
    "id_externo": ["id", "id_pagamento", "id_lancamento", "codigo", "codigo_lancamento", "id_titulo"],
    "fornecedor": ["fornecedor", "nome_fornecedor", "credor", "favorecido", "razao_social", "nome_credor",
                   "fornecedor_nome", "pessoa", "nome_pessoa"],
    "documento": ["documento", "numero_documento", "nota_fiscal", "numero_nota", "nf", "n_documento"],
    "categoria": ["categoria", "plano_de_contas", "conta", "centro_de_custo_categoria", "grupo"],
    "obra": ["obra", "nome_obra", "centro_de_custo", "centro_custo", "projeto"],
    "emissao": ["data_emissao", "emissao", "data_lancamento", "data_competencia", "competencia", "data"],
    "vencimento": ["data_vencimento", "vencimento", "dt_vencimento"],
    "valor": ["valor", "valor_total", "valor_documento", "valor_lancamento", "valor_parcela", "valor_bruto"],
    "valor_pago": ["valor_pago", "valor_liquidado", "valor_baixado"],
    "pago_em": ["data_pagamento", "data_baixa", "pagamento", "data_liquidacao", "dt_pagamento"],
    "status": ["status", "situacao", "status_pagamento"],
}


def _mc_baixar(tabela, usuario, senha):
    r = requests.get(MC_BASE + tabela, auth=(usuario, senha), timeout=120,
                     headers={"Accept": "application/json, text/csv, */*"})
    if r.status_code in (401, 403):
        raise RuntimeError("Mais Controle recusou o login da API (confira usuário e senha da API para Relatórios).")
    r.raise_for_status()
    tipo = r.headers.get("Content-Type", "")
    if "json" in tipo or r.text.lstrip().startswith(("[", "{")):
        d = r.json()
        if isinstance(d, dict):
            d = next((v for v in d.values() if isinstance(v, list)), [])
        return d
    texto = r.content.decode("utf-8-sig", "ignore")
    dialeto = csv.Sniffer().sniff(texto[:4000], delimiters=";,\t")
    return list(csv.DictReader(io.StringIO(texto), dialect=dialeto))


def _mapear(linha):
    chaves = {_norm(k): v for k, v in linha.items()}
    out = {}
    for campo, nomes in ALIASES.items():
        for n in nomes:
            if n in chaves and chaves[n] not in (None, ""):
                out[campo] = chaves[n]
                break
    return out


def sincronizar_maiscontrole(empresa):
    u, p = credenciais(empresa)
    regs = []
    for tabela in MC_TABELAS:
        for i, linha in enumerate(_mc_baixar(tabela, u, p)):
            m = _mapear(linha)
            if not m.get("valor"):
                continue
            status = str(m.get("status") or "").upper()
            regs.append({
                "id_externo": f"{tabela}:{m.get('id_externo') or i}",
                "fornecedor": str(m.get("fornecedor") or "Sem fornecedor")[:200],
                "documento": str(m.get("documento") or "")[:60] or None,
                "categoria": str(m.get("categoria") or "")[:120] or None,
                "obra": str(m.get("obra") or "")[:200] or None,
                "emissao": _data(m.get("emissao")),
                "vencimento": _data(m.get("vencimento")),
                "valor": abs(_num(m.get("valor")) or 0),
                "valor_pago": _num(m.get("valor_pago")),
                "pago_em": _data(m.get("pago_em")),
                "status": status[:40] or None,
            })
        if regs:
            break  # usa a primeira tabela que trouxer dados (pagamentos; senão lançamentos)
    return regs


def amostra_maiscontrole():
    """Primeiras linhas de cada tabela — para conferir os nomes das colunas."""
    emp = Empresa.query.filter_by(sistema="maiscontrole").first()
    cred = credenciais(emp) if emp else None
    if not cred:
        raise RuntimeError("Defina MAISCONTROLE_API_USUARIO e MAISCONTROLE_API_SENHA no Render.")
    return {t: _mc_baixar(t, *cred)[:3] for t in MC_TABELAS}


# ---------------------------------------------------------------- cópia completa das tabelas (painel financeiro)

def _chave_linha(linha, i, campo=None):
    if campo and linha.get(campo) not in (None, ""):
        return str(linha.get(campo))[:120]
    for k in ("id", "ID", "Id", "codigo", "codigo_lancamento_omie", "id_lancamento"):
        if linha.get(k) not in (None, ""):
            return str(linha[k])[:120]
    return f"linha-{i}"


def _guardar_tabela(empresa, tabela, linhas, campo=None):
    DadoImportado.query.filter_by(empresa_id=empresa.id, tabela=tabela).delete()
    vistos = set()
    for i, linha in enumerate(linhas):
        chave = _chave_linha(linha, i, campo)
        if chave in vistos:
            chave = f"{chave}#{i}"
        vistos.add(chave)
        db.session.add(DadoImportado(empresa_id=empresa.id, tabela=tabela, chave=chave, dados=linha))
    db.session.commit()
    return len(linhas)


def copiar_tudo(empresa):
    """Baixa todas as tabelas disponíveis da empresa. Devolve {tabela: quantidade ou 'erro: ...'}."""
    res = {}
    if empresa.sistema == "maiscontrole":
        u, p = credenciais(empresa)
        for nome, caminho in MC_TODAS.items():
            try:
                res[nome] = _guardar_tabela(empresa, nome, _mc_baixar(caminho, u, p))
            except Exception as e:
                db.session.rollback()
                res[nome] = f"erro: {str(e)[:120]}"
    else:
        from .omie import OmieClient
        k, s = credenciais(empresa)
        cli = OmieClient(app_key=k, app_secret=s, timeout=60)
        for nome, (modulo, metodo, lista, campo) in OMIE_TODAS.items():
            try:
                linhas = list(_omie_paginas(cli, modulo, metodo, lista))
                res[nome] = _guardar_tabela(empresa, nome, linhas, campo)
            except Exception as e:
                db.session.rollback()
                res[nome] = f"erro: {str(e)[:120]}"
        try:
            res["movimentos"] = _guardar_tabela(empresa, "movimentos", list(_omie_movimentos(cli)), "nCodTitulo")
        except Exception as e:  # noqa: BLE001 — sem os movimentos, o sistema usa a situação do título
            db.session.rollback()
            res["movimentos"] = f"erro: {str(e)[:120]}"
    return res


# ---------------------------------------------------------------- disparo em segundo plano

def sincronizar(empresa_id, app):
    with app.app_context():
        emp = db.session.get(Empresa, empresa_id)
        try:
            if emp.sistema == "omie":
                regs = sincronizar_omie(emp)
                novos = _gravar(emp, regs)
                _log(emp.sistema, f"Painel: contas a pagar — {emp.nome}", True,
                     f"{len(regs)} lançamento(s) lidos, {novos} novo(s).")
            tabelas = copiar_tudo(emp)
            ok = all(isinstance(v, int) for v in tabelas.values())
            _log(emp.sistema, f"Cópia das tabelas — {emp.nome}", ok,
                 "\n".join(f"{t}: {v}" + (" linhas" if isinstance(v, int) else "") for t, v in tabelas.items()))
            if emp.sistema == "omie":   # saldos das contas correntes (não derruba a atualização se falhar)
                try:
                    from .saldos import atualizar_omie
                    n = atualizar_omie(emp)
                    _log(emp.sistema, f"Saldos bancários — {emp.nome}", True, f"{n} conta(s) corrente(s) atualizada(s).")
                except Exception as e:  # noqa: BLE001
                    db.session.rollback()
                    _log(emp.sistema, f"Saldos bancários — {emp.nome}", False, str(e)[:300])
            # base unificada (parcelas a pagar e a receber, obras): fluxo de caixa, BI Financeiro, Multiobras
            from .fin_dados import materializar
            r = materializar(emp)
            _log(emp.sistema, f"Base financeira — {emp.nome}", True,
                 f"A pagar: {r['pagar']} parcela(s), {r['pagar_aberto']} em aberto. "
                 f"A receber: {r['receber']} parcela(s), {r['receber_aberto']} em aberto."
                 + (f" Obras resumidas: {r['obras']}." if "obras" in r else ""))
            # DDA conferido de novo com o contas a pagar novo (antes só no botão: boletos lançados ficavam "a lançar")
            try:
                with _lock_dda:
                    from .fin_bi import conciliar
                    conciliar()
                    db.session.commit()
            except Exception:  # noqa: BLE001
                db.session.rollback()
        except Exception as e:  # registra qualquer falha de rede/credencial
            db.session.rollback()
            _log(emp.sistema, f"Painel: contas a pagar — {emp.nome}", False, str(e))
        finally:
            _em_andamento.discard(empresa_id)


def disparar(empresa, app):
    if empresa.id in _em_andamento:
        return False
    if not credenciais(empresa):
        raise RuntimeError(
            "Credenciais não configuradas no Render para " + empresa.nome + ": "
            + ("OMIE_FDINIZ_APP_KEY e OMIE_FDINIZ_APP_SECRET." if empresa.sistema == "omie"
               else "MAISCONTROLE_API_USUARIO e MAISCONTROLE_API_SENHA."))
    _em_andamento.add(empresa.id)
    threading.Thread(target=sincronizar, args=(empresa.id, app), daemon=True).start()
    return True


# ---------------------------------------------------------------- atualização rápida só do contas a pagar (DDA)

_lock_dda = threading.Lock()
TABELAS_PAGAR = {"maiscontrole": ["lancamentos", "pagamentos"], "omie": ["contas_pagar", "fornecedores_clientes"]}


def atualizar_pagar(empresa_id, app, usuario=None):
    """Baixa só as contas a pagar (Omie / Mais Controle), refaz a base e confere o DDA de novo.
    Bem mais rápida que a atualização completa: é o botão do DDA, depois de lançar os títulos que faltavam."""
    with app.app_context():
        emp = db.session.get(Empresa, empresa_id)
        try:
            res = {}
            if emp.sistema == "maiscontrole":
                u, p = credenciais(emp)
                for nome in TABELAS_PAGAR["maiscontrole"]:
                    linhas = _mc_baixar(MC_TODAS[nome], u, p)
                    res[nome] = _guardar_tabela(emp, nome, linhas) if linhas else "vazio (mantido o anterior)"
            else:
                from .omie import OmieClient
                k, sc = credenciais(emp)
                cli = OmieClient(app_key=k, app_secret=sc, timeout=60)
                for nome in TABELAS_PAGAR["omie"]:
                    modulo, metodo, lista, campo = OMIE_TODAS[nome]
                    linhas = list(_omie_paginas(cli, modulo, metodo, lista))
                    res[nome] = _guardar_tabela(emp, nome, linhas, campo) if linhas else "vazio (mantido o anterior)"
            from .fin_dados import materializar
            r = materializar(emp)
            with _lock_dda:
                from .fin_bi import conciliar
                c = conciliar()
                db.session.commit()
            _log(emp.sistema, f"DDA: contas a pagar atualizadas — {emp.nome}", True,
                 f"{', '.join(f'{t}: {v}' for t, v in res.items())}. A pagar: {r['pagar_aberto']} em aberto. "
                 f"DDA: {c['lancados']} lançado(s), {c['faltando']} faltando lançar, {c.get('conferir', 0)} para conferir."
                 + (f" Pedido por {usuario}." if usuario else ""))
        except Exception as e:  # noqa: BLE001
            db.session.rollback()
            _log(emp.sistema, f"DDA: contas a pagar atualizadas — {emp.nome}", False, str(e)[:500])
        finally:
            _em_andamento.discard(empresa_id)


def disparar_pagar(app, usuario=None):
    """Dispara a atualização rápida nas duas empresas. Devolve (disparadas, ocupadas, sem_credencial)."""
    disparadas, ocupadas, sem = [], [], []
    for emp in Empresa.query.filter(Empresa.sistema.in_(["omie", "maiscontrole"])).all():
        if not credenciais(emp):
            sem.append(emp.nome)
            continue
        if emp.id in _em_andamento:
            ocupadas.append(emp.nome)
            continue
        _em_andamento.add(emp.id)
        threading.Thread(target=atualizar_pagar, args=(emp.id, app, usuario), daemon=True).start()
        disparadas.append(emp.nome)
    return disparadas, ocupadas, sem


def atualizando_agora():
    return bool(_em_andamento)


def testar_maiscontrole():
    """Teste rápido da API para Relatórios: baixa a tabela de obras (pequena).
    Devolve (ok, mensagem)."""
    u, p = os.environ.get("MAISCONTROLE_API_USUARIO"), os.environ.get("MAISCONTROLE_API_SENHA")
    if not (u and p):
        return False, ("Faltam as variáveis MAISCONTROLE_API_USUARIO e MAISCONTROLE_API_SENHA no Render "
                       "(Environment). Use o e-mail e a 'Senha da API' de Configurações > Integração do Mais Controle.")
    try:
        linhas = _mc_baixar("obras", u.strip(), p.strip())
    except RuntimeError as e:
        return False, str(e) + " Confira se a senha foi copiada inteira, sem espaço no começo ou no fim."
    except requests.RequestException as e:
        return False, f"Não consegui falar com o Mais Controle ({e.__class__.__name__}). Tente de novo em alguns minutos."
    colunas = sorted((linhas[0] or {}).keys())[:15] if linhas else []
    return True, (f"Conexão OK: {len(linhas)} obra(s) lidas da API do Mais Controle."
                  + (f" Colunas: {', '.join(colunas)}." if colunas else ""))
