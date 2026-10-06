"""
Interface web da Consulta Meteorológica NASA POWER.

Reaproveita as funções de clima_nasa.py (requisição, processamento,
resumo e gravação no JSON). Este arquivo só cuida da parte visual.

Para executar:  streamlit run app.py
"""

from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

from clima_nasa import (
    CIDADES,
    buscar_dados_nasa,
    calcular_resumo,
    processar_dados,
    salvar_consulta,
)

st.set_page_config(page_title="Clima NASA POWER", layout="wide")

st.title("Consulta Meteorológica — NASA POWER")
st.caption("Dados diários de satélite da NASA para qualquer lugar do planeta · "
           "[Documentação da API](https://power.larc.nasa.gov/docs/services/api/)")


with st.sidebar:
    st.header("Local")
    nomes_cidades = [nome for nome, _, _ in CIDADES.values()]
    escolha = st.selectbox("Cidade", nomes_cidades + ["Outro local (coordenadas)"])

    if escolha in nomes_cidades:
        nome, latitude, longitude = next(c for c in CIDADES.values() if c[0] == escolha)
    else:
        latitude = st.number_input("Latitude", min_value=-90.0, max_value=90.0, value=51.5, step=0.1)
        longitude = st.number_input("Longitude", min_value=-180.0, max_value=180.0, value=-0.12, step=0.1)
        nome = f"Coordenadas ({latitude}, {longitude})"

    st.header("Período")
    ontem = date.today() - timedelta(days=1)
    inicio = st.date_input("Data inicial", ontem - timedelta(days=29),
                           min_value=date(1981, 1, 1), max_value=ontem, format="DD/MM/YYYY")
    fim = st.date_input("Data final", ontem,
                        min_value=date(1981, 1, 1), max_value=ontem, format="DD/MM/YYYY")

    consultar = st.button("Consultar", type="primary", width="stretch")


if consultar:
    if inicio > fim:
        st.error("A data inicial deve ser anterior à data final.")
    elif (fim - inicio).days > 365:
        st.error("Escolha um período de no máximo 1 ano.")
    else:
        try:
            with st.spinner("Buscando dados nos satélites da NASA..."):
                dados_api = buscar_dados_nasa(latitude, longitude, inicio, fim)
                dias = processar_dados(dados_api)
                resumo = calcular_resumo(dias)

            salvar_consulta({
                "local": nome,
                "latitude": latitude,
                "longitude": longitude,
                "periodo": {"inicio": f"{inicio:%d/%m/%Y}", "fim": f"{fim:%d/%m/%Y}"},
                "consultado_em": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "resumo": resumo,
                "dias": dias,
            })
            st.toast("Consulta salva em dados_climaticos.json")

            # Guarda o resultado para ele continuar na tela quando a página atualizar
            st.session_state["resultado"] = {
                "nome": nome, "latitude": latitude, "longitude": longitude,
                "inicio": inicio, "fim": fim,
                "dias": dias, "resumo": resumo, "dados_api": dados_api,
            }
        except RuntimeError as erro:
            st.error(f"Erro: {erro}")


resultado = st.session_state.get("resultado")

if not resultado:
    st.info("Escolha um local e um período na barra lateral e clique em **Consultar**.")
    st.stop()

resumo = resultado["resumo"]
st.subheader(f"{resultado['nome']} · {resultado['inicio']:%d/%m/%Y} a {resultado['fim']:%d/%m/%Y}")

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Temp. média", f"{resumo['temp_media']} °C")
col2.metric("Mais quente", f"{resumo['dia_mais_quente']['temp_max']:.1f} °C",
            resumo["dia_mais_quente"]["data"], delta_color="off")
col3.metric("Mais frio", f"{resumo['dia_mais_frio']['temp_min']:.1f} °C",
            resumo["dia_mais_frio"]["data"], delta_color="off")
col4.metric("Chuva total", f"{resumo['chuva_total_mm']} mm",
            f"{resumo['dias_com_chuva']} dias chuvosos", delta_color="off")
col5.metric("Umidade média", f"{resumo['umidade_media']} %")

if resumo["dias_sem_dados"]:
    st.warning(f"{resumo['dias_sem_dados']} dia(s) ainda sem dados: a NASA leva alguns dias "
               "para processar as imagens de satélite (valor -999 na API).")

# Tabela em formato pandas para os gráficos
tabela = pd.DataFrame(resultado["dias"])
tabela["data"] = pd.to_datetime(tabela["data"], format="%d/%m/%Y")
tabela = tabela.set_index("data")

aba_graficos, aba_tabela, aba_mapa, aba_json = st.tabs(
    ["Gráficos", "Tabela", "Mapa", "JSON da API"])

with aba_graficos:
    st.markdown("**Temperatura (°C)**")
    st.line_chart(
        tabela[["temp_min", "temp_media", "temp_max"]].rename(
            columns={"temp_min": "Mínima", "temp_media": "Média", "temp_max": "Máxima"}),
        color=["#3b82f6", "#22c55e", "#ef4444"],
    )
    esquerda, direita = st.columns(2)
    with esquerda:
        st.markdown("**Chuva (mm/dia)**")
        st.bar_chart(tabela["chuva_mm"], color="#0ea5e9")
    with direita:
        st.markdown("**Umidade relativa (%)**")
        st.area_chart(tabela["umidade"], color="#8b5cf6")

with aba_tabela:
    exibicao = tabela.rename(columns={
        "temp_media": "Média (°C)", "temp_min": "Mín (°C)", "temp_max": "Máx (°C)",
        "chuva_mm": "Chuva (mm)", "umidade": "Umidade (%)", "vento": "Vento (m/s)",
    })
    exibicao.index = exibicao.index.strftime("%d/%m/%Y")
    st.dataframe(exibicao, width="stretch")

with aba_mapa:
    st.map(pd.DataFrame({"lat": [resultado["latitude"]], "lon": [resultado["longitude"]]}), zoom=4)

with aba_json:
    st.caption("Resposta original da NASA POWER: os dados vêm organizados por variável → data → valor.")
    st.json(resultado["dados_api"], expanded=2)
