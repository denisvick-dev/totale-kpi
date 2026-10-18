from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def test_botao_limpar_filtros_redefine_todos_os_seletores():
    dados = pd.DataFrame(
        {
            "CódAuxEquipe": ["1", "2"],
            "Nome Equipe": ["Equipe A", "Equipe B"],
            "Supervisor": ["Sup A", "Sup B"],
            "Projeto": ["Projeto A", "Projeto B"],
            "Pontos": [300, 450],
        }
    )
    app = AppTest.from_file(ROOT / "pages" / "pontos.py")
    app.session_state["dados_prod"] = {
        "Prod": dados,
        "Gpon": dados.iloc[0:0].copy(),
    }

    app.run()
    assert not app.exception

    valores = {
        "sel_Projeto": "Projeto A",
        "sel_Supervisor": "Sup A",
        "sel_Nome Equipe": "Equipe A",
    }
    for chave, valor in valores.items():
        app.session_state[chave] = valor
    app.run()
    assert not app.exception
    assert all(app.session_state[chave] == valor for chave, valor in valores.items())

    botao_limpar = next(
        botao for botao in app.button if "Limpar Filtros" in botao.label
    )
    botao_limpar.click().run()

    assert not app.exception
    assert all(app.session_state[chave] == "Todos" for chave in valores)
