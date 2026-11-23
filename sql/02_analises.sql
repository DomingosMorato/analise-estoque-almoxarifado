-- Consultas analíticas do almoxarifado. Cada bloco começa com "-- name:".

-- name: base_itens
-- Visão por item: consumo anual, valor consumido, estoque final, giro e cobertura.
-- É a base para a curva ABC (classificação feita no Python e na consulta curva_abc).
WITH consumo AS (
    SELECT codigo, SUM(quantidade) AS qtd_consumida
    FROM movimentacoes WHERE tipo = 'SAIDA'
    GROUP BY codigo
)
SELECT
    m.codigo, m.descricao, m.categoria, m.custo_unitario,
    COALESCE(c.qtd_consumida, 0)                                   AS qtd_consumida,
    ROUND(COALESCE(c.qtd_consumida, 0) * m.custo_unitario, 2)      AS valor_consumido,
    i.saldo_sistema                                                AS estoque_final,
    ROUND(i.saldo_sistema * m.custo_unitario, 2)                   AS valor_estoque,
    -- giro = consumo anual / estoque médio (aprox. média entre saldo inicial e final)
    ROUND(COALESCE(c.qtd_consumida, 0) * 1.0
          / NULLIF((m.saldo_inicial + i.saldo_sistema) / 2.0, 0), 1) AS giro_anual,
    -- cobertura = quantos dias o estoque atual dura no ritmo de consumo médio
    ROUND(i.saldo_sistema / NULLIF(COALESCE(c.qtd_consumida, 0) / 250.0, 0), 0) AS cobertura_dias
FROM materiais m
JOIN inventario i USING (codigo)
LEFT JOIN consumo c USING (codigo);

-- name: curva_abc
-- Curva ABC por valor consumido usando função de janela (A = até 80%, B = até 95%, C = resto)
WITH consumo AS (
    SELECT m.codigo, m.categoria,
           COALESCE(SUM(mv.quantidade), 0) * m.custo_unitario AS valor
    FROM materiais m
    LEFT JOIN movimentacoes mv ON mv.codigo = m.codigo AND mv.tipo = 'SAIDA'
    GROUP BY m.codigo
),
acumulado AS (
    SELECT codigo, categoria, valor,
           SUM(valor) OVER (ORDER BY valor DESC ROWS UNBOUNDED PRECEDING)
             / SUM(valor) OVER () AS pct_acum
    FROM consumo
)
SELECT
    CASE WHEN pct_acum <= 0.80 THEN 'A' WHEN pct_acum <= 0.95 THEN 'B' ELSE 'C' END AS classe,
    COUNT(*)                                                   AS itens,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)         AS pct_itens,
    ROUND(SUM(valor), 2)                                       AS valor_consumido,
    ROUND(100.0 * SUM(valor) / SUM(SUM(valor)) OVER (), 1)     AS pct_valor
FROM acumulado
GROUP BY classe
ORDER BY classe;

-- name: itens_sem_giro
-- Itens sem nenhuma saída no ano: capital parado e candidatos a obsolescência
SELECT
    m.categoria,
    COUNT(*)                                        AS itens_sem_saida,
    ROUND(SUM(i.saldo_sistema * m.custo_unitario), 2) AS valor_parado
FROM materiais m
JOIN inventario i USING (codigo)
WHERE NOT EXISTS (SELECT 1 FROM movimentacoes mv
                  WHERE mv.codigo = m.codigo AND mv.tipo = 'SAIDA')
GROUP BY m.categoria
ORDER BY valor_parado DESC;

-- name: abaixo_minimo
-- Itens com saldo abaixo do estoque mínimo no fechamento (risco de ruptura)
SELECT m.codigo, m.descricao, m.categoria, i.saldo_sistema, m.estoque_minimo
FROM materiais m
JOIN inventario i USING (codigo)
WHERE i.saldo_sistema < m.estoque_minimo
ORDER BY m.categoria, m.codigo;

-- name: acuracidade
-- Acuracidade do inventário: % de itens em que a contagem física bate com o sistema
SELECT
    m.categoria,
    COUNT(*)                                                       AS itens_contados,
    SUM(i.contagem_fisica = i.saldo_sistema)                       AS itens_corretos,
    ROUND(100.0 * SUM(i.contagem_fisica = i.saldo_sistema) / COUNT(*), 1) AS acuracidade_pct,
    ROUND(SUM((i.contagem_fisica - i.saldo_sistema) * m.custo_unitario), 2) AS divergencia_valor
FROM materiais m
JOIN inventario i USING (codigo)
GROUP BY m.categoria
ORDER BY acuracidade_pct;

-- name: consumo_mensal
-- Valor consumido por mês (tendência de demanda do almoxarifado)
SELECT strftime('%Y-%m', mv.data) AS mes,
       ROUND(SUM(mv.quantidade * m.custo_unitario), 2) AS valor_consumido
FROM movimentacoes mv
JOIN materiais m USING (codigo)
WHERE mv.tipo = 'SAIDA'
GROUP BY mes
ORDER BY mes;
