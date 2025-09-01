import os
import pandas as pd
import tkinter as tk
from tkinter import ttk

# Rutas
carpeta_matches = "gronestats/data/Liga 1 Peru/2025"
archivo_maestro = "gronestats/data/master_data/Partidos_Liga 1 Peru_2025_limpio.xlsx"
archivo_salida = "gronestats/data/Liga 1 Peru/Partidos_detalles_faltantes_2025.xlsx"

# 1. Archivos en carpeta
archivos = [f for f in os.listdir(carpeta_matches) if f.startswith("Sofascore_") and f.endswith(".xlsx")]
match_ids = [int(f.replace("Sofascore_", "").replace(".xlsx", "")) for f in archivos]
df_archivos = pd.DataFrame({"match_id": match_ids})

# 2. Cargar maestro
df_maestro = pd.read_excel(archivo_maestro)

cols_needed = ["match_id", "home", "away", "round_number", "resultado_final", "tournament", "fecha"]
df_final = df_archivos.merge(df_maestro[cols_needed], on="match_id", how="left")

# 3. Marcar errores
df_final["error"] = df_final["home"].isna()

# 4. Ordenar
df_final = df_final.sort_values(by=["tournament", "round_number"]).reset_index(drop=True)

# ==== Resumen en terminal ====
detected = df_final[~df_final["error"]].groupby("tournament")["match_id"].count()
totales = df_maestro.groupby("tournament")["match_id"].count()
faltantes = totales - detected

print("=== RESUMEN DE PARTIDOS ===")
resumen = pd.DataFrame({"detectados": detected, "totales": totales, "faltantes": faltantes}).fillna(0).astype(int)
print(resumen)

# ==== Partidos faltantes ====
df_faltantes = df_maestro[~df_maestro["match_id"].isin(df_archivos["match_id"])]
df_faltantes = df_faltantes[cols_needed].sort_values(by=["tournament", "round_number"]).reset_index(drop=True)

# Exportar a Excel
df_faltantes.to_excel(archivo_salida, index=False)
print(f"\nArchivo exportado: {archivo_salida}")

# ==== Ventana 1: partidos detectados ====
root1 = tk.Tk()
root1.title("Datos Liga 1 2025 - Detectados")

frame1 = ttk.Frame(root1)
frame1.pack(fill="both", expand=True)

tree1 = ttk.Treeview(frame1, columns=list(df_final.columns), show="headings")

for col in df_final.columns:
    tree1.heading(col, text=col)
    tree1.column(col, width=120)

for _, row in df_final.iterrows():
    tree1.insert("", "end", values=list(row))

tree1.pack(fill="both", expand=True)

# ==== Ventana 2: partidos faltantes ====
root2 = tk.Toplevel(root1)
root2.title("Partidos Faltantes (no scrapeados)")

frame2 = ttk.Frame(root2)
frame2.pack(fill="both", expand=True)

tree2 = ttk.Treeview(frame2, columns=list(df_faltantes.columns), show="headings")

for col in df_faltantes.columns:
    tree2.heading(col, text=col)
    tree2.column(col, width=120)

for _, row in df_faltantes.iterrows():
    tree2.insert("", "end", values=list(row))

tree2.pack(fill="both", expand=True)

root1.mainloop()
