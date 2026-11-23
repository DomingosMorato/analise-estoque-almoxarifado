"""
Carrega os CSVs em SQLite, executa sql/02_analises.sql e gera os gráficos em img/.

Uso:  python src/analise.py
"""
import re
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
DATA, SQL, IMG = BASE / "data", BASE / "sql", BASE / "img"
IMG.mkdir(exist_ok=True)

AZUL, LARANJA, CINZA, VERMELHO, VERDE = "#1f4e79", "#e07b24", "#8c8c8c", "#c0392b", "#2e8b57"
plt.rcParams.update({"figure.dpi": 120, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titleweight": "bold", "axes.titlesize": 12})


def brl(v: float) -> str:
    """Formata número no padrão brasileiro: R$ 1.234,56"""
    return "R$ " + f"{v:,.0f}".replace(",", ".")


def carregar_banco() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.executescript((SQL / "01_schema.sql").read_text(encoding="utf-8"))
    for tabela in ("materiais", "movimentacoes", "inventario"):
        pd.read_csv(DATA / f"{tabela}.csv").to_sql(tabela, con, if_exists="append", index=False)
    return con


def ler_consultas() -> dict[str, str]:
    texto = (SQL / "02_analises.sql").read_text(encoding="utf-8")
    partes = re.split(r"^-- name:\s*(\w+)\s*$", texto, flags=re.M)
    return {partes[i]: partes[i + 1] for i in range(1, len(partes), 2)}


def salvar(fig, nome):
    fig.tight_layout()
    fig.savefig(IMG / nome, bbox_inches="tight")
    plt.close(fig)


def main():
    con = carregar_banco()
    q = {nome: pd.read_sql(sql, con) for nome, sql in ler_consultas().items()}
    for nome, df in q.items():
        if nome not in ("base_itens", "abaixo_minimo"):
            print(f"\n=== {nome} ===\n{df.to_string(index=False)}")

    itens = q["base_itens"]
    print(f"\nValor total em estoque: {brl(itens['valor_estoque'].sum())}")
    print(f"Itens abaixo do mínimo: {len(q['abaixo_minimo'])}")

    # 1. Curva ABC (Pareto acumulado)
    abc = itens.sort_values("valor_consumido", ascending=False).reset_index(drop=True)
    abc["pct_itens"] = (abc.index + 1) / len(abc) * 100
    abc["pct_valor"] = abc["valor_consumido"].cumsum() / abc["valor_consumido"].sum() * 100
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    ax.plot(abc["pct_itens"], abc["pct_valor"], color=AZUL, lw=2.5)
    limites = q["curva_abc"].set_index("classe")["pct_itens"].cumsum()
    for classe, cor, ini in (("A", VERMELHO, 0), ("B", LARANJA, limites["A"]), ("C", VERDE, limites["B"])):
        ax.axvspan(ini, limites[classe], color=cor, alpha=0.12)
        ax.text((ini + limites[classe]) / 2, 8, classe, ha="center", fontsize=16, fontweight="bold", color=cor)
    ax.set_xlabel("% dos itens"), ax.set_ylabel("% do valor consumido")
    ax.set_xlim(0, 100), ax.set_ylim(0, 102)
    ax.set_title("Curva ABC: poucos itens concentram a maior parte do valor")
    salvar(fig, "01_curva_abc.png")

    # 2. Valor em estoque x valor consumido por categoria
    cat = itens.groupby("categoria")[["valor_estoque", "valor_consumido"]].sum().sort_values("valor_estoque")
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    y = range(len(cat))
    ax.barh([i + 0.2 for i in y], cat["valor_consumido"] / 1000, height=0.4, color=AZUL, label="Consumido no ano")
    ax.barh([i - 0.2 for i in y], cat["valor_estoque"] / 1000, height=0.4, color=LARANJA, label="Em estoque (31/12)")
    ax.set_yticks(list(y), cat.index)
    ax.set_xlabel("R$ mil")
    ax.legend(frameon=False, loc="lower right")
    ax.set_title("Valor em estoque x consumo anual por categoria")
    salvar(fig, "02_estoque_vs_consumo.png")

    # 3. Capital parado (itens sem saída)
    parado = q["itens_sem_giro"].sort_values("valor_parado")
    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    barras = ax.barh(parado["categoria"], parado["valor_parado"], color=VERMELHO)
    ax.bar_label(barras, labels=[f"{brl(v)} ({n} itens)" for v, n in
                                 zip(parado["valor_parado"], parado["itens_sem_saida"])], padding=3, fontsize=9)
    ax.set_xlim(0, parado["valor_parado"].max() * 1.45)
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.set_title("Capital parado: itens sem nenhuma saída em 2025")
    salvar(fig, "03_capital_parado.png")

    # 4. Acuracidade do inventário por categoria
    acu = q["acuracidade"].sort_values("acuracidade_pct")
    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    cores = [VERMELHO if v < 95 else AZUL for v in acu["acuracidade_pct"]]
    barras = ax.barh(acu["categoria"], acu["acuracidade_pct"], color=cores)
    ax.bar_label(barras, fmt="%.1f%%", padding=3)
    ax.axvline(95, ls="--", color=CINZA)
    ax.text(95.3, -0.6, "meta 95%", color=CINZA, fontsize=9)
    ax.set_xlim(60, 102)
    ax.set_title("Acuracidade do inventário por categoria (%)")
    salvar(fig, "04_acuracidade.png")

    print(f"\nGráficos salvos em {IMG}")


if __name__ == "__main__":
    main()
