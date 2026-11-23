"""
Gera a base FICTÍCIA de um almoxarifado industrial:
  - materiais.csv        cadastro de ~320 itens (categoria, custo, estoque mínimo)
  - movimentacoes.csv    entradas e saídas diárias em 2025
  - inventario.csv       contagem física de dez/2025 x saldo do sistema

Uso:  python src/gerar_dados.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(7)
DATA = Path(__file__).resolve().parents[1] / "data"
DATA.mkdir(exist_ok=True)

# categoria: (qtd itens, custo médio R$, sigma log, unidade, prefixo de descrição)
categorias = {
    "Fixadores":           (70, 3.5, 0.9, "UN", ["Parafuso", "Porca", "Arruela", "Prisioneiro"]),
    "Vedação":             (55, 45, 1.0, "UN", ["Junta espiral", "Gaxeta", "Anel O-ring", "Junta PTFE"]),
    "Consumíveis de solda": (35, 60, 0.8, "KG", ["Eletrodo E7018", "Arame MIG", "Vareta TIG", "Disco de corte"]),
    "Tubos e conexões":    (45, 180, 1.1, "UN", ["Tubo aço carbono", "Flange", "Curva 90°", "Niple"]),
    "Peças de válvulas":   (60, 420, 1.2, "UN", ["Haste", "Obturador", "Sede", "Mola"]),
    "EPI":                 (30, 38, 0.7, "UN", ["Luva", "Óculos", "Protetor auricular", "Máscara PFF2"]),
    "Ferramentas":         (25, 250, 0.9, "UN", ["Chave", "Broca", "Macho", "Lima"]),
}
# itens de alto valor giram menos; fixadores e EPI giram muito
consumo_base = {"Fixadores": 60, "Vedação": 12, "Consumíveis de solda": 18, "Tubos e conexões": 3,
                "Peças de válvulas": 1.2, "EPI": 25, "Ferramentas": 0.8}

MEDIDAS = {
    "Fixadores": ["M8", "M10", "M12", "M16", "M20", "1/2\"", "5/8\""],
    "Vedação": ["DN25", "DN50", "DN80", "DN100", "1/2\"", "1\""],
    "Consumíveis de solda": ["2,5 mm", "3,2 mm", "4,0 mm", "1,0 mm", "7\""],
    "Tubos e conexões": ["DN25", "DN50", "DN80", "DN100", "DN150"],
    "Peças de válvulas": ["DN25", "DN50", "DN80", "DN100", "DN150", "classe 300", "classe 600"],
    "EPI": ["Tam. P", "Tam. M", "Tam. G", "Tam. GG", "CA padrão"],
    "Ferramentas": ["10 mm", "13 mm", "17 mm", "19 mm", "1/2\"", "3/4\""],
}
materiais = []
cod = 10000
for cat, (n, custo, sig, un, nomes) in categorias.items():
    for _ in range(n):
        cod += 1
        custo_unit = round(float(rng.lognormal(np.log(custo), sig)), 2)
        consumo_mes = max(0.0, rng.gamma(1.2, consumo_base[cat] / 1.2))
        if rng.random() < 0.12:            # itens obsoletos: sem consumo
            consumo_mes = 0.0
        materiais.append({
            "codigo": f"MAT-{cod}",
            "descricao": f"{rng.choice(nomes)} {rng.choice(MEDIDAS[cat])}",
            "categoria": cat,
            "unidade": un,
            "custo_unitario": custo_unit,
            "estoque_minimo": int(np.ceil(consumo_mes * 0.5)),
            "consumo_sim": consumo_mes,
        })
mat = pd.DataFrame(materiais)

# ---------------------------------------------------------- movimentações
movs = []
dias = pd.date_range("2025-01-02", "2025-12-30", freq="B")
saldo_inicial = {}
for m in mat.itertuples():
    saldo = int(np.ceil(m.consumo_sim * rng.uniform(1.5, 4))) + (int(rng.integers(5, 40)) if m.consumo_sim == 0 else 0)
    saldo_inicial[m.codigo] = saldo
    taxa_dia = m.consumo_sim / 21
    for d in dias:
        q = rng.poisson(taxa_dia) if taxa_dia > 0 else 0
        if q > 0:
            q = min(q, saldo)              # não sai mais do que tem (ruptura)
            if q > 0:
                movs.append((d.date(), m.codigo, "SAIDA", q))
                saldo -= q
        # reposição quando cai abaixo do mínimo, com lead time de compra embutido na chance
        if m.consumo_sim > 0 and saldo <= m.estoque_minimo and rng.random() < 0.35:
            lote = int(np.ceil(m.consumo_sim * rng.uniform(1.0, 2.5)))
            movs.append((d.date(), m.codigo, "ENTRADA", lote))
            saldo += lote

mov = pd.DataFrame(movs, columns=["data", "codigo", "tipo", "quantidade"])
mat["saldo_inicial"] = mat["codigo"].map(saldo_inicial)

# saldo final de sistema
sinal = np.where(mov["tipo"] == "ENTRADA", 1, -1)
saldo_final = (mov.assign(q=sinal * mov["quantidade"]).groupby("codigo")["q"].sum()
               .reindex(mat["codigo"]).fillna(0).values + mat["saldo_inicial"].values)

# ---------------------------------------------------------- inventário físico
inv = pd.DataFrame({"codigo": mat["codigo"], "saldo_sistema": saldo_final.astype(int)})
erro = np.zeros(len(inv), dtype=int)
tem_erro = rng.random(len(inv)) < np.where(mat["categoria"].isin(["Fixadores", "Consumíveis de solda"]), 0.22, 0.07)
erro[tem_erro] = rng.integers(-4, 3, tem_erro.sum())
inv["contagem_fisica"] = np.maximum(0, inv["saldo_sistema"] + erro)
inv["data_contagem"] = "2025-12-30"

mat.drop(columns="consumo_sim").to_csv(DATA / "materiais.csv", index=False)
mov.to_csv(DATA / "movimentacoes.csv", index=False)
inv.to_csv(DATA / "inventario.csv", index=False)
print(f"{len(mat)} materiais, {len(mov)} movimentações, inventário de {len(inv)} itens")
