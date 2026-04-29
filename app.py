import streamlit as st
import numpy as np
import numpy_financial as npf
import pandas as pd
import plotly.graph_objects as go
import io
import json
from pathlib import Path

PROJETOS_FILE = Path(__file__).parent / "projetos.json"
CENARIOS_FILE_LEGADO = Path(__file__).parent / "cenarios_salvos.json"


# ── Helpers de serialização ────────────────────────────────────────────────────
def _serializar(p: dict) -> dict:
    return {**p, "ipca_anual": {str(k): v for k, v in p["ipca_anual"].items()}}


def _deserializar(p: dict) -> dict:
    return {**p, "ipca_anual": {int(k): v for k, v in p["ipca_anual"].items()}}


# ── Storage ────────────────────────────────────────────────────────────────────
def salvar_projetos(projetos: dict):
    dados = {
        proj: {nome: _serializar(p) for nome, p in sims.items()}
        for proj, sims in projetos.items()
    }
    PROJETOS_FILE.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def carregar_projetos_disco() -> dict:
    if PROJETOS_FILE.exists():
        try:
            dados = json.loads(PROJETOS_FILE.read_text(encoding="utf-8"))
            return {
                proj: {nome: _deserializar(p) for nome, p in sims.items()}
                for proj, sims in dados.items()
            }
        except Exception:
            pass
    # Migração do formato legado (v1)
    if CENARIOS_FILE_LEGADO.exists():
        try:
            dados = json.loads(CENARIOS_FILE_LEGADO.read_text(encoding="utf-8"))
            cenarios = {nome: _deserializar(p) for nome, p in dados.items()}
            if cenarios:
                projetos = {"Projeto Inicial": cenarios}
                salvar_projetos(projetos)
                return projetos
        except Exception:
            pass
    return {}


# ── Supabase ───────────────────────────────────────────────────────────────────
def _supabase_client():
    try:
        if "supabase" not in st.secrets:
            return None
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        if not url or not key:
            return None
        from supabase import create_client
        return create_client(url, key)
    except Exception:
        return None


def salvar_projeto_nuvem(nome_proj: str, simulacoes: dict):
    client = _supabase_client()
    if client is None:
        return
    try:
        dados_ser = {nome: _serializar(p) for nome, p in simulacoes.items()}
        client.table("projetos").upsert(
            {"nome": nome_proj, "dados": dados_ser},
            on_conflict="nome",
        ).execute()
    except Exception:
        pass


def deletar_projeto_nuvem(nome_proj: str):
    client = _supabase_client()
    if client is None:
        return
    try:
        client.table("projetos").delete().eq("nome", nome_proj).execute()
    except Exception:
        pass


def carregar_projetos_nuvem() -> dict | None:
    client = _supabase_client()
    if client is None:
        return None
    try:
        resp = client.table("projetos").select("nome, dados").execute()
        return {
            row["nome"]: {nome: _deserializar(p) for nome, p in row["dados"].items()}
            for row in resp.data
        }
    except Exception:
        return None


def carregar_todos_projetos() -> dict:
    nuvem = carregar_projetos_nuvem()
    if nuvem is not None:
        if len(nuvem) == 0:
            local = carregar_projetos_disco()
            if local:
                for nome_proj, sims in local.items():
                    salvar_projeto_nuvem(nome_proj, sims)
            return local
        return nuvem
    return carregar_projetos_disco()


def salvar_simulacao(nome_proj: str, todos_projetos: dict):
    salvar_projetos(todos_projetos)  # sempre salva local primeiro
    client = _supabase_client()
    if client is not None:
        salvar_projeto_nuvem(nome_proj, todos_projetos.get(nome_proj, {}))


# ── Defaults & widget keys ─────────────────────────────────────────────────────
IPCA_BBA_DEFAULT = {ano: 4.10 for ano in range(1, 31)}
IPCA_BBA_DEFAULT[1] = 4.20

CORES = ["#3B82F6", "#EF4444", "#22C55E", "#F59E0B", "#8B5CF6", "#EC4899"]

_DEFAULTS_WIDGETS = {
    "w_valor_total": 60_000_000.0,
    "w_area_m2": 407_014.69,
    "w_sinal_pct": 10,
    "w_sinal_mes": 4,
    "w_parcela_inicio": 23,
    "w_n_parcelas": 80,
    "w_valor_venda": 0.0,
    "w_mes_venda": 120,
    "w_tma": 14.5,
    "w_ipca_mode": "Padrão (BBA da planilha)",
    "w_ipca_y1": 4.20,
    "w_ipca_y2": 4.10,
    "w_ipca_y6": 4.10,
    "w_cap_ativo": False,
    "w_ipca_cap_valor": 6.0,
}

for _k, _v in _DEFAULTS_WIDGETS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


def _aplicar_params_pendentes():
    """Aplica parâmetros pendentes nos widgets ANTES de renderizá-los."""
    p = st.session_state.pop("_pending_load", None)
    if p is None:
        return
    st.session_state["w_valor_total"] = float(p.get("valor_total", _DEFAULTS_WIDGETS["w_valor_total"]))
    st.session_state["w_area_m2"] = float(p.get("area_m2", _DEFAULTS_WIDGETS["w_area_m2"]))
    st.session_state["w_sinal_pct"] = int(p.get("sinal_pct", _DEFAULTS_WIDGETS["w_sinal_pct"]))
    st.session_state["w_sinal_mes"] = int(p.get("sinal_mes", _DEFAULTS_WIDGETS["w_sinal_mes"]))
    st.session_state["w_parcela_inicio"] = int(p.get("parcela_inicio", _DEFAULTS_WIDGETS["w_parcela_inicio"]))
    st.session_state["w_n_parcelas"] = int(p.get("n_parcelas", _DEFAULTS_WIDGETS["w_n_parcelas"]))
    st.session_state["w_valor_venda"] = float(p.get("valor_venda", _DEFAULTS_WIDGETS["w_valor_venda"]))
    st.session_state["w_mes_venda"] = int(p.get("mes_venda", _DEFAULTS_WIDGETS["w_mes_venda"]))
    st.session_state["w_tma"] = float(p.get("tma", _DEFAULTS_WIDGETS["w_tma"]))
    st.session_state["w_cap_ativo"] = p.get("ipca_cap") is not None
    st.session_state["w_ipca_cap_valor"] = float(p.get("ipca_cap") or 6.0)
    ipca = p.get("ipca_anual", IPCA_BBA_DEFAULT)
    if ipca == IPCA_BBA_DEFAULT:
        st.session_state["w_ipca_mode"] = "Padrão (BBA da planilha)"
    else:
        st.session_state["w_ipca_mode"] = "Manual"
        st.session_state["w_ipca_y1"] = float(ipca.get(1, 4.20))
        st.session_state["w_ipca_y2"] = float(ipca.get(2, 4.10))
        st.session_state["w_ipca_y6"] = float(ipca.get(6, 4.10))


# ── Session state ──────────────────────────────────────────────────────────────
if "projetos_carregados" not in st.session_state:
    st.session_state.projetos = carregar_todos_projetos()
    st.session_state.projetos_carregados = True
    st.session_state.projeto_ativo = next(iter(st.session_state.projetos), "")
    st.session_state.simulacao_em_exibicao = ""
elif "projetos" not in st.session_state:
    st.session_state.projetos = {}
    st.session_state.projeto_ativo = ""
    st.session_state.simulacao_em_exibicao = ""

if "simulacao_em_exibicao" not in st.session_state:
    st.session_state.simulacao_em_exibicao = ""

# Aplica parâmetros de simulação carregada ANTES de qualquer widget ser renderizado
_aplicar_params_pendentes()


def _cenarios_ativos() -> dict:
    return st.session_state.projetos.get(st.session_state.projeto_ativo, {})


# ── Funções utilitárias ────────────────────────────────────────────────────────
def brl(valor: float, prefixo: str = "R$ ") -> str:
    formatado = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{prefixo}{formatado}"


# ── Funções Financeiras ────────────────────────────────────────────────────────
def ipca_acumulado_por_mes(n_meses: int, ipca_anual: dict, cap_pct: float | None = None) -> list[float]:
    acc_fator = 1.0
    resultado = []
    for m in range(n_meses + 1):
        if m > 0 and m % 12 == 0:
            ano = m // 12
            taxa = ipca_anual.get(ano, list(ipca_anual.values())[-1]) / 100
            if cap_pct is not None:
                taxa = min(taxa, cap_pct / 100)
            acc_fator *= (1 + taxa)
        resultado.append((acc_fator - 1) * 100)
    return resultado


def montar_fluxo(
    valor_total: float,
    sinal_pct: float,
    sinal_mes: int,
    parcela_inicio: int,
    n_parcelas: int,
    valor_venda: float,
    mes_venda: int,
    ipca_anual: dict,
    ipca_cap: float | None = None,
) -> pd.DataFrame:
    horizonte = max(mes_venda + 1, parcela_inicio + n_parcelas + 1, 221)
    sinal_valor = valor_total * sinal_pct / 100
    saldo_restante = valor_total - sinal_valor
    parcela_nominal = saldo_restante / n_parcelas if n_parcelas > 0 else 0.0
    fluxo_nom = np.zeros(horizonte)
    if sinal_pct > 0 and sinal_mes < horizonte:
        fluxo_nom[sinal_mes] -= sinal_valor
    for i in range(n_parcelas):
        mes = parcela_inicio + i
        if mes < horizonte:
            fluxo_nom[mes] -= parcela_nominal
    if valor_venda > 0 and mes_venda < horizonte:
        fluxo_nom[mes_venda] += valor_venda
    ipca_acc = ipca_acumulado_por_mes(horizonte - 1, ipca_anual, cap_pct=ipca_cap)
    fatores = np.array([(1 + v / 100) for v in ipca_acc])
    fluxo_cor = fluxo_nom * fatores
    df = pd.DataFrame({
        "Mês": np.arange(horizonte),
        "Fluxo Nominal": fluxo_nom,
        "IPCA Acc. (%)": ipca_acc,
        "Fluxo Corrigido": fluxo_cor,
    })
    df["Fluxo Acum."] = df["Fluxo Corrigido"].cumsum()
    return df


def calcular_retornos(df: pd.DataFrame, tma_anual: float) -> dict:
    fluxo = df["Fluxo Corrigido"].values
    try:
        tir_mensal = npf.irr(fluxo)
        tir_anual = (1 + tir_mensal) ** 12 - 1 if not np.isnan(tir_mensal) else None
    except Exception:
        tir_anual = None
    taxa_mensal = (1 + tma_anual / 100) ** (1 / 12) - 1
    vpl = float(npf.npv(taxa_mensal, fluxo))
    acum = df["Fluxo Acum."].values
    ficou_negativo = False
    payback = None
    for i, v in enumerate(acum):
        if v < 0:
            ficou_negativo = True
        if ficou_negativo and v >= 0:
            payback = int(i)
            break
    saidas = abs(df.loc[df["Fluxo Corrigido"] < 0, "Fluxo Corrigido"].sum())
    entradas = df.loc[df["Fluxo Corrigido"] > 0, "Fluxo Corrigido"].sum()
    multiplo = entradas / saidas if saidas > 0 else None
    return {
        "tir_anual": tir_anual,
        "vpl": vpl,
        "payback": payback,
        "saidas": saidas,
        "entradas": entradas,
        "multiplo": multiplo,
    }


def parse_ipca_csv(uploaded) -> dict | None:
    try:
        df = pd.read_csv(uploaded, header=0)
        col_ipca = df.iloc[:, 3]
        ipca_por_mes = (
            col_ipca.astype(str)
            .str.replace("%", "", regex=False)
            .str.replace(",", ".", regex=False)
            .astype(float)
        )
        ipca_dict = {}
        for mes_idx, taxa in enumerate(ipca_por_mes):
            if taxa > 0:
                ano = mes_idx // 12 + 1
                ipca_dict[ano] = taxa
        return ipca_dict if ipca_dict else None
    except Exception:
        return None


# ── Página ─────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Simulador de Terreno 2.0",
    page_icon="🏗️",
    layout="wide",
)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:

    # ── Gerenciamento de Projetos ──────────────────────────────────────────────
    st.header("📁 Projetos")

    projetos_lista = list(st.session_state.projetos.keys())

    # Criar novo projeto
    with st.form("form_novo_projeto", clear_on_submit=True):
        col_pj1, col_pj2 = st.columns([3, 1])
        nome_novo_proj = col_pj1.text_input(
            "Nome", placeholder="Ex: SC03, Nova Odessa…", label_visibility="collapsed"
        )
        col_pj2.write("")
        criar_proj = st.form_submit_button("➕ Criar", use_container_width=True)
        if criar_proj:
            nome_novo_proj = nome_novo_proj.strip()
            if nome_novo_proj and nome_novo_proj not in st.session_state.projetos:
                st.session_state.projetos[nome_novo_proj] = {}
                st.session_state.projeto_ativo = nome_novo_proj
                salvar_projetos(st.session_state.projetos)
                st.rerun()
            elif nome_novo_proj in st.session_state.projetos:
                st.warning("Já existe.")

    if projetos_lista:
        idx_proj = (
            projetos_lista.index(st.session_state.projeto_ativo)
            if st.session_state.projeto_ativo in projetos_lista
            else 0
        )
        projeto_sel = st.selectbox(
            "Projeto ativo", projetos_lista, index=idx_proj, key="select_projeto"
        )
        if projeto_sel != st.session_state.projeto_ativo:
            st.session_state.projeto_ativo = projeto_sel
            st.session_state.simulacao_em_exibicao = ""
            st.rerun()

        n_sims = len(_cenarios_ativos())
        st.caption(f"💾 {n_sims} simulação(ões) salva(s) neste projeto")

        if st.button(
            f"🗑️ Excluir projeto '{st.session_state.projeto_ativo}'",
            type="secondary",
            use_container_width=True,
        ):
            proj_excluir = st.session_state.projeto_ativo
            del st.session_state.projetos[proj_excluir]
            salvar_projetos(st.session_state.projetos)
            client = _supabase_client()
            if client:
                deletar_projeto_nuvem(proj_excluir)
            lista_restante = list(st.session_state.projetos.keys())
            st.session_state.projeto_ativo = lista_restante[0] if lista_restante else ""
            st.rerun()
    else:
        st.info("Crie um projeto para começar.")

    st.markdown("---")

    # ── Parâmetros do terreno ──────────────────────────────────────────────────
    st.header("⚙️ Parâmetros")

    st.subheader("🏔️ Terreno")
    valor_total = st.number_input(
        "Valor Total (R$)", min_value=0.0, step=1_000_000.0, format="%.2f",
        key="w_valor_total",
    )
    st.caption(f"✏️ {brl(valor_total)}")
    area_m2 = st.number_input("Área (m²)", min_value=0.0, format="%.2f", key="w_area_m2")
    st.caption(f"✏️ {brl(area_m2, prefixo='')}" + (" m²" if area_m2 > 0 else ""))
    if area_m2 > 0:
        st.caption(f"Preço/m²: **{brl(valor_total / area_m2)}**")

    st.subheader("💰 Pagamento")
    sinal_pct = st.slider("Sinal (%)", 0, 50, key="w_sinal_pct", step=5)
    sinal_mes = st.number_input("Mês do Sinal", min_value=0, max_value=120, key="w_sinal_mes")
    parcela_inicio = st.number_input(
        "Início das Parcelas (mês)", min_value=0, max_value=120, key="w_parcela_inicio"
    )
    n_parcelas = st.number_input(
        "Nº de Parcelas", min_value=1, max_value=240, key="w_n_parcelas"
    )

    sinal_valor = valor_total * sinal_pct / 100
    parcela_val = (valor_total - sinal_valor) / n_parcelas if n_parcelas > 0 else 0
    parcela_fim = int(parcela_inicio) + int(n_parcelas) - 1
    st.caption(f"Sinal: **{brl(sinal_valor)}**")
    st.caption(f"Parcela: **{brl(parcela_val)}** | Fim: mês **{parcela_fim}**")

    st.subheader("📊 IPCA (Itaú BBA)")
    ipca_mode = st.radio(
        "Fonte", ["Padrão (BBA da planilha)", "Upload CSV", "Manual"], key="w_ipca_mode"
    )

    if ipca_mode == "Upload CSV":
        csv_file = st.file_uploader("CSV da aba economics", type="csv")
        ipca_anual = parse_ipca_csv(csv_file) if csv_file else IPCA_BBA_DEFAULT
        if csv_file and ipca_anual is None:
            st.warning("Não foi possível ler o IPCA do CSV. Usando padrão.")
            ipca_anual = IPCA_BBA_DEFAULT
    elif ipca_mode == "Manual":
        ipca_y1 = st.number_input("Ano 1 (%)", 0.0, 20.0, step=0.1, key="w_ipca_y1")
        ipca_y2 = st.number_input("Anos 2–5 (%)", 0.0, 20.0, step=0.1, key="w_ipca_y2")
        ipca_y6 = st.number_input("Anos 6+ (%)", 0.0, 20.0, step=0.1, key="w_ipca_y6")
        ipca_anual = (
            {1: ipca_y1}
            | {a: ipca_y2 for a in range(2, 6)}
            | {a: ipca_y6 for a in range(6, 31)}
        )
    else:
        ipca_anual = IPCA_BBA_DEFAULT

    st.markdown("**🔒 Cap de Inflação**")
    col_cap1, col_cap2 = st.columns([2, 3])
    with col_cap1:
        cap_ativo = st.toggle("Ativar cap", key="w_cap_ativo")
    with col_cap2:
        ipca_cap_valor = st.number_input(
            "Cap (% a.a.)", min_value=0.1, max_value=20.0, step=0.1, key="w_ipca_cap_valor"
        )

    if cap_ativo:
        ipca_cap = ipca_cap_valor
        anos_limitados = sum(1 for t in ipca_anual.values() if t > ipca_cap)
        if anos_limitados:
            st.caption(f"⚠️ Cap aplicado em **{anos_limitados}** ano(s)")
        else:
            st.caption("✅ Nenhum ano supera o cap")
    else:
        ipca_cap = None
        st.caption("🔓 Cap desativado — IPCA integral")

    st.subheader("💹 Taxa de Desconto (TMA)")
    tma = st.number_input(
        "TMA (% a.a.)", min_value=0.0, max_value=50.0, step=0.5, key="w_tma"
    )

    st.subheader("📈 Receita / Venda")
    valor_venda = st.number_input(
        "Valor de Venda (R$)", min_value=0.0, step=1_000_000.0, format="%.2f",
        key="w_valor_venda",
    )
    if valor_venda > 0:
        st.caption(f"✏️ {brl(valor_venda)}")
    mes_venda = st.number_input(
        "Mês da Venda/Receita", min_value=0, max_value=360, key="w_mes_venda"
    )

    # ── Simulações do projeto ──────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📂 Simulações")

    if not st.session_state.projeto_ativo:
        st.warning("Crie ou selecione um projeto primeiro.")
    else:
        nome_simulacao = st.text_input(
            "Nome da Simulação", "Base", key="w_nome_simulacao"
        )
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if st.button("💾 Salvar", use_container_width=True):
                novo = dict(
                    valor_total=valor_total, area_m2=area_m2,
                    sinal_pct=sinal_pct, sinal_mes=int(sinal_mes),
                    parcela_inicio=int(parcela_inicio), n_parcelas=int(n_parcelas),
                    valor_venda=valor_venda, mes_venda=int(mes_venda),
                    tma=tma, ipca_anual=ipca_anual, ipca_cap=ipca_cap,
                )
                if st.session_state.projeto_ativo not in st.session_state.projetos:
                    st.session_state.projetos[st.session_state.projeto_ativo] = {}
                st.session_state.projetos[st.session_state.projeto_ativo][nome_simulacao] = novo
                st.session_state.simulacao_em_exibicao = nome_simulacao
                salvar_simulacao(st.session_state.projeto_ativo, st.session_state.projetos)
                st.success(f"'{nome_simulacao}' salvo!")
        with col_s2:
            if st.button("🗑️ Apagar todas", use_container_width=True,
                         help="Remove todas as simulações deste projeto"):
                proj = st.session_state.projeto_ativo
                st.session_state.projetos[proj] = {}
                salvar_projetos(st.session_state.projetos)
                client = _supabase_client()
                if client:
                    salvar_projeto_nuvem(proj, {})
                st.session_state.simulacao_em_exibicao = ""
                st.rerun()

        cenarios = _cenarios_ativos()
        if cenarios:
            usando_nuvem = _supabase_client() is not None
            st.markdown(f"**Simulações salvas** {'☁️' if usando_nuvem else '💾'}:")
            for nome_salvo in list(cenarios.keys()):
                is_ativa = nome_salvo == st.session_state.simulacao_em_exibicao
                col_btn, col_del = st.columns([5, 1])
                if col_btn.button(
                    f"{'▶ ' if is_ativa else '📋 '}{nome_salvo}",
                    key=f"view_{nome_salvo}",
                    use_container_width=True,
                    type="primary" if is_ativa else "secondary",
                    help="Clique para exibir esta simulação",
                ):
                    st.session_state["_pending_load"] = cenarios[nome_salvo]
                    st.session_state.simulacao_em_exibicao = nome_salvo
                    st.rerun()
                if col_del.button(
                    "🗑️", key=f"del_{nome_salvo}", help=f"Excluir '{nome_salvo}'"
                ):
                    del st.session_state.projetos[st.session_state.projeto_ativo][nome_salvo]
                    if st.session_state.simulacao_em_exibicao == nome_salvo:
                        st.session_state.simulacao_em_exibicao = ""
                    salvar_simulacao(st.session_state.projeto_ativo, st.session_state.projetos)
                    st.rerun()


# ── Cálculo do cenário atual ───────────────────────────────────────────────────
df = montar_fluxo(
    valor_total=valor_total,
    sinal_pct=sinal_pct,
    sinal_mes=int(sinal_mes),
    parcela_inicio=int(parcela_inicio),
    n_parcelas=int(n_parcelas),
    valor_venda=valor_venda,
    mes_venda=int(mes_venda),
    ipca_anual=ipca_anual,
    ipca_cap=ipca_cap,
)
ret = calcular_retornos(df, tma)


# ── Cabeçalho ─────────────────────────────────────────────────────────────────
col_titulo, col_projeto = st.columns([3, 1])
with col_titulo:
    st.title("🏗️ Simulador de Compra de Terreno 2.0")
    st.caption("Análise de fluxo de caixa com correção IPCA (Itaú BBA) e cálculo de TIR/VPL")
with col_projeto:
    if st.session_state.projeto_ativo:
        st.markdown(
            f"<div style='text-align:right; padding-top:18px'>"
            f"<span style='font-size:0.85rem; color:#6B7280'>Projeto ativo</span><br>"
            f"<span style='font-size:1.2rem; font-weight:700; color:#3B82F6'>"
            f"📁 {st.session_state.projeto_ativo}</span></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='text-align:right; padding-top:24px'>"
            "<span style='color:#EF4444'>⚠️ Nenhum projeto selecionado</span></div>",
            unsafe_allow_html=True,
        )

st.markdown("---")

# ── Banner da simulação em exibição ───────────────────────────────────────────
sim_ativa = st.session_state.simulacao_em_exibicao
if sim_ativa:
    col_banner, col_nova = st.columns([5, 1])
    with col_banner:
        st.info(
            f"📋 **{sim_ativa}** &nbsp;·&nbsp; "
            f"Projeto: **{st.session_state.projeto_ativo}**",
            icon="▶",
        )
    with col_nova:
        if st.button("✏️ Nova simulação", use_container_width=True, help="Limpar e começar do zero"):
            st.session_state.simulacao_em_exibicao = ""
            st.session_state["_pending_load"] = _DEFAULTS_WIDGETS
            st.rerun()

# ── Comparação de Simulações do Projeto ───────────────────────────────────────
cenarios = _cenarios_ativos()
if cenarios:
    proj_label = f" — {st.session_state.projeto_ativo}" if st.session_state.projeto_ativo else ""
    st.subheader(f"⚖️ Comparação de Simulações{proj_label}")

    col_tma1, col_tma2 = st.columns([1, 3])
    with col_tma1:
        tma_comp = st.number_input(
            "TMA para comparação (% a.a.)",
            min_value=0.0, max_value=50.0, step=0.5,
            value=float(tma),
            key="w_tma_comp",
            help="Substitui a TMA salva em cada simulação para recalcular VP e VPL com a mesma base",
        )
    with col_tma2:
        st.caption(
            "A TMA abaixo substitui a taxa salva em cada simulação — "
            "útil para comparar todas na mesma base de desconto."
        )

    linhas = []
    dfs_cenarios = {}
    retornos_cenarios = {}
    for nome, p in cenarios.items():
        df_c = montar_fluxo(
            valor_total=p["valor_total"], sinal_pct=p["sinal_pct"],
            sinal_mes=p["sinal_mes"], parcela_inicio=p["parcela_inicio"],
            n_parcelas=p["n_parcelas"], valor_venda=p["valor_venda"],
            mes_venda=p["mes_venda"], ipca_anual=p["ipca_anual"],
            ipca_cap=p.get("ipca_cap"),
        )
        dfs_cenarios[nome] = df_c
        r_c = calcular_retornos(df_c, tma_comp)
        retornos_cenarios[nome] = (p, r_c)

        taxa_m = (1 + tma_comp / 100) ** (1 / 12) - 1
        vp = abs(float(npf.npv(taxa_m, df_c["Fluxo Corrigido"].values)))
        sinal_rs = p["valor_total"] * p["sinal_pct"] / 100
        parcela_m = (p["valor_total"] - sinal_rs) / p["n_parcelas"] if p["n_parcelas"] > 0 else 0
        custo_m2 = p["valor_total"] / p["area_m2"] if p["area_m2"] > 0 else 0
        vp_m2 = vp / p["area_m2"] if p["area_m2"] > 0 else 0

        linhas.append({
            "Simulação": nome,
            "Área (m²)": f"{p['area_m2']:,.0f}",
            "Valor Total": f"R$ {p['valor_total'] / 1e6:.1f}M",
            "R$/m²": f"R$ {custo_m2:,.2f}",
            "Mês Sinal": p["sinal_mes"],
            "Sinal": f"{p['sinal_pct']}%  ({brl(sinal_rs)})",
            "Início Parcelas (mês)": p["parcela_inicio"],
            "Parcelas": p["n_parcelas"],
            "Parcela Mensal": brl(parcela_m),
            "Total Desembolsado": brl(r_c["saidas"]),
            "VP do Custo": f"R$ {vp / 1e6:.2f}M",
            "VP/m²": f"R$ {vp_m2:,.2f}",
            "VPL": f"R$ {r_c['vpl'] / 1e6:.2f}M",
            "TMA usada": f"{tma_comp}%",
        })

    st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True)

    nomes = list(retornos_cenarios.keys())
    cores_comp = [CORES[i % len(CORES)] for i in range(len(nomes))]

    st.markdown("**Fluxo Acumulado por Simulação**")
    fig_comp = go.Figure()
    for i, (nome, df_c) in enumerate(dfs_cenarios.items()):
        fig_comp.add_trace(go.Scatter(
            x=df_c["Mês"], y=df_c["Fluxo Acum."] / 1e6,
            mode="lines", name=nome,
            line=dict(color=CORES[i % len(CORES)], width=2),
            hovertemplate=f"<b>{nome}</b><br>Mês %{{x}}<br>R$ %{{y:.2f}}M<extra></extra>",
        ))
    fig_comp.add_hline(y=0, line_dash="dash", line_color="#6B7280")
    fig_comp.update_layout(
        xaxis_title="Mês", yaxis_title="R$ Milhões",
        height=400, margin=dict(t=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    st.plotly_chart(fig_comp, use_container_width=True)

    gc1, gc2 = st.columns(2)

    with gc1:
        st.markdown("**VP do Custo por Simulação** *(R$ M)*")
        vp_vals = []
        for nome, (p, r_c) in retornos_cenarios.items():
            taxa_m = (1 + tma_comp / 100) ** (1 / 12) - 1
            df_c = dfs_cenarios[nome]
            vp_vals.append(abs(float(npf.npv(taxa_m, df_c["Fluxo Corrigido"].values))) / 1e6)

        fig_vp = go.Figure(go.Bar(
            x=nomes, y=vp_vals, marker_color=cores_comp,
            text=[f"R$ {v:.1f}M" for v in vp_vals], textposition="outside",
        ))
        fig_vp.update_layout(
            yaxis_title="R$ Milhões", showlegend=False,
            height=340, margin=dict(t=30, b=10),
            yaxis=dict(range=[0, max(vp_vals) * 1.2]),
        )
        st.plotly_chart(fig_vp, use_container_width=True)

    with gc2:
        st.markdown("**Estrutura de Pagamento** *(Sinal vs Parcelas — R$ M corrigido)*")
        sinais_cor, parcelas_cor = [], []
        for nome, (p, _) in retornos_cenarios.items():
            df_c = dfs_cenarios[nome]
            saidas = df_c[df_c["Fluxo Corrigido"] < 0]["Fluxo Corrigido"]
            sinal_m_idx = int(p["sinal_mes"])
            sinal_cor = abs(df_c.loc[df_c["Mês"] == sinal_m_idx, "Fluxo Corrigido"].sum()) / 1e6
            parc_cor = abs(saidas.sum()) / 1e6 - sinal_cor
            sinais_cor.append(sinal_cor)
            parcelas_cor.append(parc_cor)

        fig_est = go.Figure()
        fig_est.add_trace(go.Bar(
            name="Sinal", x=nomes, y=sinais_cor, marker_color="#EF4444",
            text=[f"R$ {v:.1f}M" for v in sinais_cor], textposition="inside",
        ))
        fig_est.add_trace(go.Bar(
            name="Parcelas", x=nomes, y=parcelas_cor, marker_color="#3B82F6",
            text=[f"R$ {v:.1f}M" for v in parcelas_cor], textposition="inside",
        ))
        fig_est.update_layout(
            barmode="stack", yaxis_title="R$ Milhões (corrigido IPCA)",
            height=340, margin=dict(t=30, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        )
        st.plotly_chart(fig_est, use_container_width=True)

st.markdown("---")

# ── Resultados (expansível) ───────────────────────────────────────────────────
_titulo_resultado = f"📊 Resultados — {sim_ativa}" if sim_ativa else "📊 Resultados — Cenário Atual"
with st.expander(_titulo_resultado, expanded=True):

    sinal_valor_kpi = valor_total * sinal_pct / 100
    parcela_val_kpi = (valor_total - sinal_valor_kpi) / n_parcelas if n_parcelas > 0 else 0

    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    c1.metric("Valor Total", brl(valor_total))
    c2.metric(
        "Área", f"{brl(area_m2, prefixo='')} m²",
        help=f"Preço/m²: {brl(valor_total / area_m2)}" if area_m2 > 0 else None,
    )
    c3.metric("Sinal", f"{sinal_pct}%", help=brl(sinal_valor_kpi))
    c4.metric("Nº de Parcelas", int(n_parcelas))
    c5.metric("Parcela Mensal", brl(parcela_val_kpi), help=f"A partir do mês {parcela_inicio}")
    c6.metric("VPL", brl(ret["vpl"]), help=f"TMA de {tma}% a.a.")
    c7.metric("Total Desembolsado", brl(ret["saidas"]))

    g1, g2 = st.columns(2)

    with g1:
        st.subheader("Fluxo de Caixa Mensal (Corrigido)")
        df_nz = df[df["Fluxo Corrigido"] != 0]
        cores_barra = ["#EF4444" if v < 0 else "#22C55E" for v in df_nz["Fluxo Corrigido"]]
        fig1 = go.Figure(go.Bar(
            x=df_nz["Mês"],
            y=df_nz["Fluxo Corrigido"] / 1e6,
            marker_color=cores_barra,
            hovertemplate="Mês %{x}<br><b>R$ %{y:.2f}M</b><extra></extra>",
        ))
        fig1.update_layout(
            xaxis_title="Mês", yaxis_title="R$ Milhões",
            showlegend=False, height=360, margin=dict(t=20),
        )
        st.plotly_chart(fig1, use_container_width=True)

    with g2:
        st.subheader("Fluxo Acumulado (Corrigido)")
        fig2 = go.Figure(go.Scatter(
            x=df["Mês"],
            y=df["Fluxo Acum."] / 1e6,
            mode="lines",
            line=dict(color="#3B82F6", width=2.5),
            fill="tozeroy",
            fillcolor="rgba(59,130,246,0.08)",
            hovertemplate="Mês %{x}<br><b>R$ %{y:.2f}M</b><extra></extra>",
        ))
        fig2.add_hline(y=0, line_dash="dash", line_color="#6B7280")
        if ret["payback"]:
            fig2.add_vline(
                x=ret["payback"], line_dash="dot", line_color="#22C55E",
                annotation_text=f"Payback: mês {ret['payback']}",
                annotation_position="top right",
            )
        fig2.update_layout(
            xaxis_title="Mês", yaxis_title="R$ Milhões",
            showlegend=False, height=360, margin=dict(t=20),
        )
        st.plotly_chart(fig2, use_container_width=True)


# ── Sensibilidade ─────────────────────────────────────────────────────────────
with st.expander("🎯 Sensibilidade — Custo Total × Estrutura de Pagamento"):

    taxa_mensal_sens = (1 + tma / 100) ** (1 / 12) - 1

    def vp_custo(df_b: pd.DataFrame) -> float:
        return abs(float(npf.npv(taxa_mensal_sens, df_b["Fluxo Corrigido"].values)))

    st.caption(
        "Compara o **Valor Presente do custo de aquisição** (descontado pela TMA) "
        "por estrutura de pagamento."
    )

    sinais_pct = [0, 5, 10, 15, 20, 30]
    parcelas_ops = [24, 36, 48, 60, 80, 100, 120, 150, 180]

    fig_b = go.Figure()
    melhor_vp = {"vp": float("inf"), "sinal": None, "parcelas": None}
    melhor_nom = {"custo": float("inf"), "sinal": None, "parcelas": None}

    for i, sp in enumerate(sinais_pct):
        vps = []
        for np_ in parcelas_ops:
            df_b = montar_fluxo(
                valor_total=valor_total, sinal_pct=sp, sinal_mes=int(sinal_mes),
                parcela_inicio=int(parcela_inicio), n_parcelas=np_,
                valor_venda=0, mes_venda=0, ipca_anual=ipca_anual, ipca_cap=ipca_cap,
            )
            vp = vp_custo(df_b)
            custo_nom = abs(df_b.loc[df_b["Fluxo Corrigido"] < 0, "Fluxo Corrigido"].sum())
            vps.append(vp / 1e6)
            if vp < melhor_vp["vp"]:
                melhor_vp = {"vp": vp, "sinal": sp, "parcelas": np_}
            if custo_nom < melhor_nom["custo"]:
                melhor_nom = {"custo": custo_nom, "sinal": sp, "parcelas": np_}

        fig_b.add_trace(go.Scatter(
            x=parcelas_ops, y=vps,
            mode="lines+markers",
            name=f"Sinal {sp}%",
            line=dict(color=CORES[i % len(CORES)], width=2),
            hovertemplate=f"Sinal {sp}%<br>Parcelas: %{{x}}<br>VP Custo: R$ %{{y:.2f}}M<extra></extra>",
        ))

    fig_b.add_hline(
        y=valor_total / 1e6, line_dash="dot", line_color="#6B7280",
        annotation_text=f"Custo nominal s/IPCA: R$ {valor_total/1e6:.0f}M",
        annotation_position="bottom right",
    )
    fig_b.update_layout(
        xaxis_title="Número de Parcelas",
        yaxis_title="VP do Custo de Aquisição (R$ Milhões)",
        height=380, margin=dict(t=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    st.plotly_chart(fig_b, use_container_width=True)

    h1, h2 = st.columns(2)
    matriz_vp = []
    matriz_nom = []
    for sp in sinais_pct:
        linha_vp, linha_nom = [], []
        for np_ in parcelas_ops:
            df_b = montar_fluxo(
                valor_total=valor_total, sinal_pct=sp, sinal_mes=int(sinal_mes),
                parcela_inicio=int(parcela_inicio), n_parcelas=np_,
                valor_venda=0, mes_venda=0, ipca_anual=ipca_anual, ipca_cap=ipca_cap,
            )
            linha_vp.append(round(vp_custo(df_b) / 1e6, 2))
            linha_nom.append(round(
                abs(df_b.loc[df_b["Fluxo Corrigido"] < 0, "Fluxo Corrigido"].sum()) / 1e6, 2
            ))
        matriz_vp.append(linha_vp)
        matriz_nom.append(linha_nom)

    with h1:
        st.markdown("**VP do Custo** *(descontado pela TMA — comparação correta)*")
        fig_h1 = go.Figure(go.Heatmap(
            z=matriz_vp, x=[str(p) for p in parcelas_ops], y=[f"{s}%" for s in sinais_pct],
            colorscale="RdYlGn_r",
            hovertemplate="Sinal: %{y}<br>Parcelas: %{x}<br>VP: R$ %{z:.2f}M<extra></extra>",
            text=[[f"R${v:.1f}M" for v in row] for row in matriz_vp],
            texttemplate="%{text}", textfont=dict(size=10),
        ))
        fig_h1.update_layout(xaxis_title="Nº Parcelas", yaxis_title="Sinal (%)", height=290, margin=dict(t=10))
        st.plotly_chart(fig_h1, use_container_width=True)

    with h2:
        st.markdown("**Custo Nominal Corrigido** *(soma simples com IPCA — sem desconto)*")
        fig_h2 = go.Figure(go.Heatmap(
            z=matriz_nom, x=[str(p) for p in parcelas_ops], y=[f"{s}%" for s in sinais_pct],
            colorscale="RdYlGn_r",
            hovertemplate="Sinal: %{y}<br>Parcelas: %{x}<br>Custo: R$ %{z:.2f}M<extra></extra>",
            text=[[f"R${v:.1f}M" for v in row] for row in matriz_nom],
            texttemplate="%{text}", textfont=dict(size=10),
        ))
        fig_h2.update_layout(xaxis_title="Nº Parcelas", yaxis_title="Sinal (%)", height=290, margin=dict(t=10))
        st.plotly_chart(fig_h2, use_container_width=True)

    st.info(
        f"**Pelo VP do custo**: a combinação mais eficiente é "
        f"**Sinal {melhor_vp['sinal']}% + {melhor_vp['parcelas']} parcelas** → "
        f"VP de **R$ {melhor_vp['vp'] / 1e6:.2f}M** à TMA de {tma}% a.a."
    )

    st.markdown("**Impacto do Início das Parcelas no Custo Total**")
    inicios = [6, 12, 18, 23, 36, 48]
    rows_inicio = []
    for ini in inicios:
        df_b = montar_fluxo(
            valor_total=valor_total, sinal_pct=sinal_pct, sinal_mes=int(sinal_mes),
            parcela_inicio=ini, n_parcelas=int(n_parcelas),
            valor_venda=0, mes_venda=0, ipca_anual=ipca_anual, ipca_cap=ipca_cap,
        )
        custo = abs(df_b.loc[df_b["Fluxo Corrigido"] < 0, "Fluxo Corrigido"].sum())
        rows_inicio.append({
            "Início das Parcelas (mês)": ini,
            "Custo Total Corrigido": f"R$ {custo / 1e6:.2f}M",
            "IPCA Extra vs Nominal": f"R$ {(custo - valor_total) / 1e6:.2f}M",
            "Custo/m²": f"R$ {custo / area_m2:,.2f}" if area_m2 > 0 else "—",
        })
    st.dataframe(pd.DataFrame(rows_inicio), use_container_width=True, hide_index=True)


# ── Propostas Equivalentes ────────────────────────────────────────────────────
with st.expander("🔁 Propostas Equivalentes — mesmo VPL"):
    vpl_alvo = ret["vpl"]

    if vpl_alvo == 0.0:
        st.info("Configure os parâmetros do cenário atual para calcular propostas equivalentes.")
    else:
        st.caption(
            f"VPL de referência: **{brl(vpl_alvo)}**  "
            f"— valor máximo que pode ser pago mantendo o mesmo custo presente à TMA de {tma}% a.a."
        )

        def bisection_valor_total(vpl_alvo, sinal_pct_b, n_parcelas_b, parcela_inicio_b,
                                   bounds=(1_000, 500_000_000)):
            def diff(vt):
                df_b = montar_fluxo(
                    valor_total=vt, sinal_pct=sinal_pct_b,
                    sinal_mes=int(sinal_mes), parcela_inicio=parcela_inicio_b,
                    n_parcelas=n_parcelas_b, valor_venda=valor_venda,
                    mes_venda=int(mes_venda), ipca_anual=ipca_anual, ipca_cap=ipca_cap,
                )
                return calcular_retornos(df_b, tma)["vpl"] - vpl_alvo

            lo, hi = bounds
            try:
                d_lo, d_hi = diff(lo), diff(hi)
            except Exception:
                return None
            if d_lo * d_hi > 0:
                return None
            for _ in range(60):
                mid = (lo + hi) / 2.0
                if diff(mid) * d_lo <= 0:
                    hi = mid
                else:
                    lo = mid
                if hi - lo < 1.0:
                    break
            return (lo + hi) / 2.0

        sinais_eq = [0, 5, 10, 15, 20, 25, 30]
        parcelas_eq = sorted(set([
            max(1, int(n_parcelas) - 24), max(1, int(n_parcelas) - 12),
            int(n_parcelas),
            int(n_parcelas) + 12, int(n_parcelas) + 24, int(n_parcelas) + 48,
        ]))

        st.markdown("**Heatmap — Valor Máximo do Terreno (R$ M)**")
        matriz_hm, texto_hm = [], []
        for sp in sinais_eq:
            linha_v, linha_t = [], []
            for np_ in parcelas_eq:
                vt_eq = bisection_valor_total(vpl_alvo, sp, np_, int(parcela_inicio))
                linha_v.append(round(vt_eq / 1e6, 2) if vt_eq else None)
                linha_t.append(f"R${vt_eq/1e6:.1f}M" if vt_eq else "N/A")
            matriz_hm.append(linha_v)
            texto_hm.append(linha_t)

        fig_hm = go.Figure(go.Heatmap(
            z=matriz_hm, x=[str(p) for p in parcelas_eq], y=[f"{s}%" for s in sinais_eq],
            colorscale="Greens",
            hovertemplate="Sinal: %{y}<br>Parcelas: %{x}<br>Valor Máx: R$ %{z:.1f}M<extra></extra>",
            text=texto_hm, texttemplate="%{text}", textfont=dict(size=10),
        ))
        fig_hm.update_layout(xaxis_title="Nº de Parcelas", yaxis_title="Sinal (%)", height=310, margin=dict(t=10))
        st.plotly_chart(fig_hm, use_container_width=True)

        st.markdown(f"**Variando o Sinal % — {int(n_parcelas)} parcelas fixas**")
        rows_sinal = []
        for sp in sinais_eq:
            vt_eq = bisection_valor_total(vpl_alvo, sp, int(n_parcelas), int(parcela_inicio))
            delta = (vt_eq - valor_total) if vt_eq else None
            vpl_check = None
            if vt_eq:
                df_check = montar_fluxo(vt_eq, sp, int(sinal_mes), int(parcela_inicio), int(n_parcelas),
                                        valor_venda, int(mes_venda), ipca_anual, ipca_cap)
                vpl_check = calcular_retornos(df_check, tma)["vpl"]
            rows_sinal.append({
                "Sinal (%)": f"{sp}%",
                "Valor Máx. Terreno": brl(vt_eq) if vt_eq else "—",
                "Δ vs Atual": (("+" if delta >= 0 else "") + brl(delta, prefixo="R$ ")) if delta is not None else "—",
                "Sinal (R$)": brl(vt_eq * sp / 100) if vt_eq else "—",
                "Parcela Mensal": brl((vt_eq * (1 - sp/100)) / int(n_parcelas)) if vt_eq else "—",
                "Cenário Atual": "✔ atual" if sp == sinal_pct else "",
                "VPL": brl(vpl_check) if vpl_check is not None else "—",
            })
        st.dataframe(pd.DataFrame(rows_sinal), use_container_width=True, hide_index=True)

        st.markdown(f"**Variando o Nº de Parcelas — sinal {sinal_pct}% fixo**")
        rows_parc = []
        for np_ in parcelas_eq:
            vt_eq = bisection_valor_total(vpl_alvo, sinal_pct, np_, int(parcela_inicio))
            delta = (vt_eq - valor_total) if vt_eq else None
            sv = vt_eq * sinal_pct / 100 if vt_eq else None
            vpl_check = None
            if vt_eq:
                df_check = montar_fluxo(vt_eq, sinal_pct, int(sinal_mes), int(parcela_inicio), np_,
                                        valor_venda, int(mes_venda), ipca_anual, ipca_cap)
                vpl_check = calcular_retornos(df_check, tma)["vpl"]
            rows_parc.append({
                "Nº Parcelas": np_,
                "Valor Máx. Terreno": brl(vt_eq) if vt_eq else "—",
                "Δ vs Atual": (("+" if delta >= 0 else "") + brl(delta, prefixo="R$ ")) if delta is not None else "—",
                "Sinal (R$)": brl(sv) if sv else "—",
                "Parcela Mensal": brl((vt_eq - sv) / np_) if vt_eq else "—",
                "Cenário Atual": "✔ atual" if np_ == int(n_parcelas) else "",
                "VPL": brl(vpl_check) if vpl_check is not None else "—",
            })
        st.dataframe(pd.DataFrame(rows_parc), use_container_width=True, hide_index=True)


# ── IPCA ──────────────────────────────────────────────────────────────────────
with st.expander("📈 Curva IPCA Aplicada"):
    n_show = min(len(df), 121)
    fig_ipca = go.Figure()
    fig_ipca.add_trace(go.Scatter(
        x=df["Mês"][:n_show], y=df["IPCA Acc. (%)"][:n_show],
        mode="lines",
        name="IPCA c/ cap" if cap_ativo else "IPCA acumulado",
        line=dict(color="#F59E0B", width=2.5),
        hovertemplate="Mês %{x}<br>IPCA Acc.: %{y:.2f}%<extra></extra>",
    ))
    if cap_ativo:
        ipca_sem_cap = ipca_acumulado_por_mes(n_show - 1, ipca_anual, cap_pct=None)
        fig_ipca.add_trace(go.Scatter(
            x=list(range(n_show)), y=ipca_sem_cap[:n_show],
            mode="lines", name="IPCA s/ cap (referência)",
            line=dict(color="#94A3B8", width=1.5, dash="dot"),
        ))
    ipca_acc_list = df["IPCA Acc. (%)"].tolist()
    for ano in range(1, (n_show // 12) + 1):
        mes = ano * 12
        if mes >= n_show:
            break
        taxa_ano = ipca_anual.get(ano, list(ipca_anual.values())[-1])
        if cap_ativo:
            taxa_ano = min(taxa_ano, ipca_cap_valor)
        y_val = ipca_acc_list[mes]
        fig_ipca.add_trace(go.Scatter(
            x=[mes], y=[y_val], mode="markers+text",
            marker=dict(color="#F59E0B", size=8),
            text=[f"{taxa_ano:.1f}%"], textposition="top center",
            textfont=dict(size=9, color="#92400E"), showlegend=False,
        ))
    fig_ipca.update_layout(
        xaxis_title="Mês", yaxis_title="IPCA Acumulado (%)",
        height=320, margin=dict(t=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    st.plotly_chart(fig_ipca, use_container_width=True)


# ── Tabela de fluxo ────────────────────────────────────────────────────────────
with st.expander("📋 Fluxo de Caixa Detalhado"):
    df_show = df[df["Fluxo Nominal"] != 0].copy()
    df_show["Fluxo Nominal"] = df_show["Fluxo Nominal"].map(lambda x: f"R$ {x:,.2f}")
    df_show["Fluxo Corrigido"] = df_show["Fluxo Corrigido"].map(lambda x: f"R$ {x:,.2f}")
    df_show["Fluxo Acum."] = df_show["Fluxo Acum."].map(lambda x: f"R$ {x:,.2f}")
    df_show["IPCA Acc. (%)"] = df_show["IPCA Acc. (%)"].map(lambda x: f"{x:.2f}%")
    st.dataframe(df_show, use_container_width=True, hide_index=True)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, sheet_name="Fluxo")
    proj_label = f"_{st.session_state.projeto_ativo}" if st.session_state.projeto_ativo else ""
    st.download_button(
        "⬇️ Baixar Excel",
        data=buf.getvalue(),
        file_name=f"fluxo_terreno{proj_label}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ── Métricas de Venda ──────────────────────────────────────────────────────────
with st.expander("📊 Métricas de Venda — TIR, Payback e Múltiplo"):
    st.caption("Métricas calculadas sobre o fluxo corrigido completo (saídas + entrada da venda).")
    tir_str = f"{ret['tir_anual'] * 100:.2f}% a.a." if ret["tir_anual"] else "N/A"
    payback_str = f"{ret['payback']} meses" if ret["payback"] is not None else "Não atingido"
    multiplo_str = f"{ret['multiplo']:.2f}×" if ret["multiplo"] else "N/A"
    mv1, mv2, mv3 = st.columns(3)
    mv1.metric("TIR", tir_str)
    mv2.metric("Payback", payback_str)
    mv3.metric("Múltiplo", multiplo_str)


