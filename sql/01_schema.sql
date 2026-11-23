-- Modelo de dados do almoxarifado (SQLite)

CREATE TABLE materiais (
    codigo          TEXT PRIMARY KEY,
    descricao       TEXT NOT NULL,
    categoria       TEXT NOT NULL,
    unidade         TEXT NOT NULL,
    custo_unitario  REAL NOT NULL,
    estoque_minimo  INTEGER NOT NULL,
    saldo_inicial   INTEGER NOT NULL
);

CREATE TABLE movimentacoes (
    data        DATE    NOT NULL,
    codigo      TEXT    NOT NULL REFERENCES materiais (codigo),
    tipo        TEXT    NOT NULL CHECK (tipo IN ('ENTRADA', 'SAIDA')),
    quantidade  INTEGER NOT NULL CHECK (quantidade > 0)
);

CREATE TABLE inventario (
    codigo           TEXT PRIMARY KEY REFERENCES materiais (codigo),
    saldo_sistema    INTEGER NOT NULL,
    contagem_fisica  INTEGER NOT NULL,
    data_contagem    DATE    NOT NULL
);

CREATE INDEX ix_mov_codigo ON movimentacoes (codigo);
CREATE INDEX ix_mov_data   ON movimentacoes (data);
