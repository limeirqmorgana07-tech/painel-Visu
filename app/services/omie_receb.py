"""Recebimento da NF-e no Omie (F. Diniz) a partir da entrada no estoque feita no sistema.

API "Recebimento de Nota Fiscal" (produtos/recebimentonfe):
  - ConsultarRecebimento {"cChaveNfe": chave} -> devolve o nIdReceb do recebimento que o Omie já importou
    (pelo Agente/E-mail da NF-e);
  - ConcluirRecebimento {"nIdReceb": id} -> conclui: o card vai para "Recebido", entra no estoque do Omie
    e o contas a pagar é criado.
Se a conta do Omie não aceitar concluir pela API, o sistema registra isso e avisa para clicar em
Concluir no Omie (sem repetir a tentativa, para não cair no bloqueio de 30 min por erros repetidos).

v1.35 — modo padrão "conferido": em vez de concluir, o sistema
  - AlterarRecebimento: departamento (obra / centro de custo da nota, rateio 100%) e projeto (infoAdicionais.nIdProjeto);
  - AlterarEtapaRecebimento {"nIdReceb", "cEtapa"}: põe o card na etapa "Conferido" (código configurado em
    Notas fiscais → Omie: etapas; o Omie não publica a lista de códigos, o sistema mostra as etapas em uso).
  O "Recebido" (estoque e contas a pagar no Omie) fica para quem conclui no Omie.
"""
import re
import unicodedata
from difflib import SequenceMatcher
from ..extensions import db
from ..models import Configuracao, DadoImportado, LogIntegracao, Movimentacao, agora
from .omie import OmieClient, OmieErro

MODULO = "produtos/recebimentonfe"


def _achar(d, chave):
    """Procura uma chave em qualquer nível da resposta do Omie."""
    if isinstance(d, dict):
        if chave in d and d[chave] not in (None, "", 0):
            return d[chave]
        for v in d.values():
            r = _achar(v, chave)
            if r not in (None, "", 0):
                return r
    elif isinstance(d, list):
        for v in d:
            r = _achar(v, chave)
            if r not in (None, "", 0):
                return r
    return None


def _cliente(empresa):
    from .financeiro import credenciais
    cred = credenciais(empresa)
    if not cred:
        raise OmieErro("Chaves do Omie da F. Diniz não configuradas no Render (OMIE_FDINIZ_APP_KEY/SECRET).")
    return OmieClient(*cred)


def aplicavel(nota):
    e = nota.empresa
    return bool(e and e.sistema == "omie")


def entrada_completa(nota):
    from .nfe import ja_entrou
    return bool(nota.itens) and all(ja_entrou(i) >= (i.quantidade or 0) - 1e-6 for i in nota.itens)


def _status(nota, texto, concluido=None):
    nota.omie_status = texto[:255]
    nota.omie_status_em = agora()
    if concluido is not None:
        nota.omie_concluido = concluido


def modo():
    # v1.43.1: volta ao padrão "concluir" (card em Recebido); a etapa Conferido só se for escolhida de novo
    return Configuracao.obter("omie_receb_modo_v2", "concluir")


def etapa_conferido():
    return (Configuracao.obter("omie_etapa_conferido") or "").strip() or None


def _norm(t):
    t = unicodedata.normalize("NFD", str(t or "")).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9]+", " ", t).strip()


def _lista(d):
    out = []
    if isinstance(d, dict):
        for v in d.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                out.extend(v)
    return out


def atualizar_departamentos(empresa):
    """Copia o cadastro de departamentos do Omie (usados como obra / centro de custo)."""
    cli = _cliente(empresa)
    regs, pagina, total = [], 1, 1
    while pagina <= min(total, 20):
        d = cli.chamar("geral/departamentos", "ListarDepartamentos", {"pagina": pagina, "registros_por_pagina": 500})
        total = int(d.get("total_de_paginas") or 1) if isinstance(d, dict) else 1
        regs.extend(_lista(d))
        pagina += 1
    DadoImportado.query.filter_by(empresa_id=empresa.id, tabela="departamentos_omie").delete()
    for i, r in enumerate(regs):
        cod = str(r.get("codigo") or r.get("cCodigo") or r.get("codigo_departamento") or i)
        db.session.add(DadoImportado(empresa_id=empresa.id, tabela="departamentos_omie", chave=cod[:120], dados=r))
    db.session.commit()
    return len(regs)


def garantir_departamentos(empresa):
    """Copia os departamentos do Omie se ainda não houver nenhum (tenta no máximo uma vez por hora)."""
    from datetime import timedelta
    ult = Configuracao.obter("omie_deps_tentativa")
    try:
        if ult and agora() - __import__("datetime").datetime.fromisoformat(ult) < timedelta(hours=1):
            return departamentos(empresa)
    except ValueError:
        pass
    Configuracao.definir("omie_deps_tentativa", agora().isoformat())
    db.session.commit()
    try:
        atualizar_departamentos(empresa)
    except Exception:  # noqa: BLE001
        db.session.rollback()
    return departamentos(empresa)


def obras_sem_departamento(nota):
    """Obras / centros de custo da nota (uma ou várias) sem departamento correspondente no Omie."""
    opcoes = departamentos(nota.empresa) if nota.empresa else []
    if not opcoes:
        return []
    return [nome for nome, _, _ in nota.rateio_lista if nome and not _achar_por_nome(nome, opcoes, "omie_dep:")]


def departamentos(empresa):
    out = []
    for (d,) in db.session.query(DadoImportado.dados).filter_by(empresa_id=empresa.id, tabela="departamentos_omie"):
        d = d or {}
        cod = d.get("codigo") or d.get("cCodigo") or d.get("codigo_departamento")
        nome = d.get("descricao") or d.get("cDescricao") or d.get("nome")
        if cod and nome and str(d.get("inativo") or "N").upper() != "S":
            out.append((str(cod), str(nome)))
    return sorted(out, key=lambda x: _norm(x[1]))


def projetos(empresa):
    out = []
    for (d,) in db.session.query(DadoImportado.dados).filter_by(empresa_id=empresa.id, tabela="projetos"):
        d = d or {}
        if d.get("codigo") and d.get("nome") and str(d.get("inativo") or "N").upper() != "S":
            out.append((int(d["codigo"]), str(d["nome"])))
    return out


def _achar_por_nome(nome, opcoes, mapa_chave):
    """Código pelo nome da obra/centro de custo: vínculo salvo à mão > nome igual > nome muito parecido."""
    if not nome:
        return None
    manual = Configuracao.obter(mapa_chave + _norm(nome)[:40])
    if manual:
        return manual
    alvo = _norm(nome)
    for cod, n in opcoes:
        if _norm(n) == alvo:
            return cod
    melhor = max(opcoes, key=lambda o: SequenceMatcher(None, _norm(o[1]), alvo).ratio(), default=None)
    if melhor and SequenceMatcher(None, _norm(melhor[1]), alvo).ratio() >= 0.88:
        return melhor[0]
    return None


def departamento_da_nota(nota):
    return _achar_por_nome(nota.centro_custo_label, departamentos(nota.empresa), "omie_dep:")


def projeto_da_nota(nota):
    return _achar_por_nome(nota.centro_custo_label, projetos(nota.empresa), "omie_proj:")


def vincular_departamento(nota, codigo, nome=None):
    """Liga a obra / centro de custo (da nota ou o nome informado) a um departamento do Omie (vale para as próximas)."""
    Configuracao.definir("omie_dep:" + _norm(nome or nota.centro_custo_label)[:40], str(codigo))


def etapas_em_uso(empresa, paginas=4):
    """As etapas (colunas) que aparecem no Recebimento de NF-e do Omie, com notas de exemplo de cada uma."""
    cli = _cliente(empresa)
    et = {}
    for p in range(1, paginas + 1):
        d = cli.chamar(MODULO, "ListarRecebimentos", {"nPagina": p, "nRegistrosPorPagina": 100})
        for r in (d.get("recebimentos") or []) if isinstance(d, dict) else []:
            c = r.get("cabec") or {}
            ic = r.get("infoCadastro") or {}
            e = str(c.get("cEtapa") or "?")
            x = et.setdefault(e, {"etapa": e, "qtd": 0, "recebidas": 0, "exemplos": []})
            x["qtd"] += 1
            if str(ic.get("cRecebido") or "").upper() == "S":
                x["recebidas"] += 1
            if len(x["exemplos"]) < 4:
                x["exemplos"].append(f"NF {c.get('cNumeroNFe') or '?'} · {(c.get('cNome') or c.get('cRazaoSocial') or '')[:30]} · {c.get('dEmissaoNFe') or ''}")
        if not isinstance(d, dict) or p >= int(d.get("nTotalPaginas") or 1):
            break
    return sorted(et.values(), key=lambda x: x["etapa"])


def _enviar_centro_custo(cli, nota, partes):
    """Departamentos (obras da nota, % pelo valor dos itens de cada uma) e projeto no recebimento do Omie."""
    alterar = {"ide": {"nIdReceb": int(nota.omie_receb_id)}}
    proj = projeto_da_nota(nota)
    lista = nota.rateio_lista
    deps, faltam = [], []
    opcoes = departamentos(nota.empresa) if lista else []
    for nome, _, pct in lista:
        if pct < 0.005:  # obra da nota sem nenhum item indicado
            continue
        cod = _achar_por_nome(nome, opcoes, "omie_dep:")
        if cod:
            deps.append({"cCodDepartamento": str(cod), "pDepartamento": round(pct, 2)})
        else:
            faltam.append(nome)
    if deps and len(deps) > 1:  # arredondamento: a soma precisa dar 100
        deps[-1]["pDepartamento"] = round(100 - sum(d["pDepartamento"] for d in deps[:-1]), 2)
    # o Omie exige também o VALOR de cada departamento ("Valor da distribuição por departamento não pode ser zero")
    total = float(nota.valor_total or 0) or sum(float(i.valor_total or 0) for i in nota.itens)
    for d in deps:
        d["vDepartamento"] = round(total * d["pDepartamento"] / 100, 2)
    if len(deps) > 1:
        deps[-1]["vDepartamento"] = round(total - sum(d["vDepartamento"] for d in deps[:-1]), 2)
    dep = deps if deps and not faltam else None
    if dep:
        alterar["departamentos"] = dep
    if proj:
        alterar["infoAdicionais"] = {"nIdProjeto": int(proj)}
    cc = " + ".join(n for n, _, _ in lista) if len(lista) > 1 else nota.centro_custo_label
    if faltam:
        partes.append("sem departamento no Omie para: " + ", ".join(faltam) + " — escolha na nota (seção Omie)")
    if dep or proj:
        try:
            try:
                cli.chamar(MODULO, "AlterarRecebimento", alterar)
            except OmieErro as e:
                if not dep or not any(x in str(e).lower() for x in ("tag", "estrutura", "vdepartamento", "zero")):
                    raise
                # outra forma de escrever a distribuição (como no contas a pagar do Omie)
                alterar["departamentos"] = [{"cCodDep": d["cCodDepartamento"], "nPerDep": d["pDepartamento"],
                                             "nValDep": d["vDepartamento"]} for d in dep]
                cli.chamar(MODULO, "AlterarRecebimento", alterar)
            partes.append(f"centro de custo “{cc}” enviado (" + ", ".join(
                (["departamento"] if dep else []) + (["projeto"] if proj else [])) + ")")
        except OmieErro as e:
            partes.append(f"o Omie não aceitou o centro de custo: {str(e)[:150]}")
    elif faltam:
        pass
    elif cc:
        partes.append(f"“{cc}” não tem departamento correspondente no Omie — escolha na nota (seção Omie)")
    else:
        partes.append("nota sem obra / centro de custo")


def _conferir(cli, nota):
    """Modo conferido: centro de custo (departamento/projeto) + etapa Conferido. Devolve (ok, mensagem)."""
    partes = []
    _enviar_centro_custo(cli, nota, partes)
    et = etapa_conferido()
    if not et:
        return None, "; ".join(partes + ["código da etapa Conferido não configurado (Notas fiscais → Omie: etapas)"])
    try:
        cli.chamar(MODULO, "AlterarEtapaRecebimento", {"nIdReceb": int(nota.omie_receb_id), "cEtapa": et})
    except OmieErro as e:
        return None, "; ".join(partes + [f"o Omie não mudou a etapa {et}: {str(e)[:150]}"])
    return True, "Conferido no Omie (etapa " + et + "); " + "; ".join(partes) + ". Concluir (Recebido) é feito no Omie."


def enviar(nota, usuario):
    """Conclui o recebimento da nota no Omie. Devolve (ok, mensagem). Nunca levanta erro para a tela."""
    if not aplicavel(nota):
        return False, "Só notas da F. Diniz vão para o Omie."
    if nota.omie_concluido:
        return True, "Recebimento já concluído no Omie."
    conferido = modo() == "conferido"
    if not conferido and not entrada_completa(nota):
        _status(nota, "Aguardando: dê entrada de todos os itens da nota para concluir no Omie.")
        return False, nota.omie_status
    try:
        cli = _cliente(nota.empresa)
        if not nota.omie_receb_id:
            try:
                cons = cli.chamar(MODULO, "ConsultarRecebimento", {"cChaveNfe": nota.chave})
            except OmieErro as e:
                _status(nota, f"A nota ainda não está no Omie ({str(e)[:120]}). O Omie importa as notas pelo Agente "
                              f"da NF-e; tente de novo mais tarde.")
                return False, nota.omie_status
            rid = _achar(cons, "nIdReceb")
            if not rid:
                _status(nota, "A nota ainda não apareceu no Recebimento de NF-e do Omie. Tente de novo mais tarde.")
                return False, nota.omie_status
            nota.omie_receb_id = str(rid)
        prefixo = ""
        if conferido:
            ok, msg = _conferir(cli, nota)
            if ok:
                _status(nota, msg)
                nota.omie_conferido = True
                _marcar_movs(nota)
                return True, nota.omie_status
            # sem a etapa Conferido (não configurada ou recusada pelo Omie): conclui como antes ("Recebido")
            if not entrada_completa(nota):
                _status(nota, msg + "; quando todos os itens tiverem entrada, a nota vai para Recebido no Omie.")
                return False, nota.omie_status
            prefixo = msg + " → "
        if not conferido:
            partes = []
            _enviar_centro_custo(cli, nota, partes)
            prefixo = ("; ".join(partes) + " → ") if partes else ""
        if Configuracao.obter("omie_concluir_api") == "indisponivel":
            _status(nota, "Pronto no Omie: abra o card da nota em Compras e clique em Concluir "
                          "(a conta do Omie não aceita concluir pela API).", False)
            return False, nota.omie_status
        try:
            resp = cli.chamar(MODULO, "ConcluirRecebimento", {"nIdReceb": int(nota.omie_receb_id)})
        except OmieErro as e:
            msg = str(e)
            baixo = msg.lower()
            if any(x in baixo for x in ("method", "método", "metodo", "não existe", "nao existe", "invalid call")):
                Configuracao.definir("omie_concluir_api", "indisponivel")
                _status(nota, "Pronto no Omie: abra o card da nota em Compras e clique em Concluir "
                              "(a conta do Omie não aceita concluir pela API).", False)
            elif "conclu" in baixo and ("já" in baixo or "ja " in baixo):
                _status(nota, "Recebimento já estava concluído no Omie.", True)
                _marcar_movs(nota)
                return True, nota.omie_status
            else:
                _status(nota, f"O Omie não concluiu: {msg[:200]}. Ajuste no card da nota (ex.: categoria) e "
                              f"clique em Concluir lá, ou tente de novo aqui.", False)
            return False, nota.omie_status
        _status(nota, prefixo + f"Recebimento concluído no Omie ({(resp or {}).get('cDescStatus') or 'ok'}): "
                      f"card em Recebido, estoque e contas a pagar lançados lá.", True)
        _marcar_movs(nota)
        return True, nota.omie_status
    except OmieErro as e:
        _status(nota, f"Falha ao falar com o Omie: {str(e)[:200]}")
        return False, nota.omie_status
    except Exception as e:  # noqa: BLE001 — rede etc.
        _status(nota, f"Falha ao falar com o Omie: {str(e)[:200]}")
        return False, nota.omie_status
    finally:
        db.session.add(LogIntegracao(sistema="omie", operacao=f"Recebimento NF {nota.numero}/{nota.serie}",
                                     sucesso=bool(nota.omie_concluido or nota.omie_conferido),
                                     mensagem=(nota.omie_status or "")[:4000],
                                     usuario=getattr(usuario, "nome", None)))


def _marcar_movs(nota):
    """As entradas desta nota já estão no Omie pelo recebimento: não mandar como ajuste de estoque."""
    for m in Movimentacao.query.filter_by(nota_id=nota.id).all():
        if not m.omie_enviado_em:
            m.omie_enviado_em = agora()
            m.omie_id = f"receb:{nota.omie_receb_id}"[:60]
