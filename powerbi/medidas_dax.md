# Montando o dashboard no Power BI

## 1. Importar e modelar
1. **Obter dados → Texto/CSV**: `materiais.csv`, `movimentacoes.csv`, `inventario.csv`.
2. **Power Query** em `movimentacoes`: coluna `Qtd Assinada` = `if [tipo] = "SAIDA" then -[quantidade] else [quantidade]`.
3. **Relacionamentos**: `materiais[codigo]` (1) → `movimentacoes[codigo]` (*) e `materiais[codigo]` (1) → `inventario[codigo]` (1).
4. Tabela **Calendário** relacionada a `movimentacoes[data]`.

## 2. Medidas DAX

```DAX
Qtd Consumida =
CALCULATE ( SUM ( movimentacoes[quantidade] ), movimentacoes[tipo] = "SAIDA" )

Valor Consumido =
SUMX ( materiais, materiais[custo_unitario] *
       CALCULATE ( SUM ( movimentacoes[quantidade] ), movimentacoes[tipo] = "SAIDA" ) )

Valor em Estoque =
SUMX ( inventario, inventario[saldo_sistema] * RELATED ( materiais[custo_unitario] ) )

Cobertura (meses) = DIVIDE ( [Valor em Estoque], [Valor Consumido] ) * 12

Acuracidade % =
DIVIDE (
    COUNTROWS ( FILTER ( inventario, inventario[contagem_fisica] = inventario[saldo_sistema] ) ),
    COUNTROWS ( inventario ) )

Capital Parado =
SUMX ( FILTER ( materiais, ISBLANK ( [Qtd Consumida] ) ),
       materiais[custo_unitario] * RELATED ( inventario[saldo_sistema] ) )

Itens Abaixo do Mínimo =
COUNTROWS ( FILTER ( materiais, RELATED ( inventario[saldo_sistema] ) < materiais[estoque_minimo] ) )
```

### Classificação ABC (coluna calculada em `materiais`)
```DAX
Valor Consumido Item = [Valor Consumido]

% Acumulado =
VAR ValorItem = materiais[Valor Consumido Item]
VAR Total = SUM ( materiais[Valor Consumido Item] )
RETURN DIVIDE (
    SUMX ( FILTER ( materiais, materiais[Valor Consumido Item] >= ValorItem ),
           materiais[Valor Consumido Item] ), Total )

Classe ABC =
SWITCH ( TRUE (), materiais[% Acumulado] <= 0.80, "A", materiais[% Acumulado] <= 0.95, "B", "C" )
```

## 3. Layout sugerido
| Área | Visual |
|---|---|
| Topo | Cartões: Valor em Estoque, Valor Consumido, Cobertura, Acuracidade %, Capital Parado |
| Esquerda | Gráfico de linhas: % acumulado (curva ABC) com faixas A/B/C |
| Direita | Barras agrupadas: estoque x consumo por categoria |
| Inferior | Tabela de itens sem giro (ordenada por valor) e itens abaixo do mínimo |
| Filtros | Categoria, Classe ABC, Mês |
