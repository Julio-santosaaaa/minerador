"""Esvazia a tabela `offers` (ofertas pendentes, ainda não enviadas ao Notion).
Não toca em `synced` nem em `offer_history`. Uso: .venv/bin/python scripts/clear_pending.py"""
import sqlite3
from pathlib import Path

db = Path(__file__).resolve().parent.parent / "data" / "minerador.db"
conn = sqlite3.connect(str(db))
n = conn.execute("SELECT COUNT(*) FROM offers").fetchone()[0]
conn.execute("DELETE FROM offers")
conn.commit()
conn.close()
print(f"{n} ofertas pendentes removidas de {db}")
