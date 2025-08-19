# scripts/mover_a_data.py

import shutil
from pathlib import Path

def mover_archivos():
    # Rutas principales
    base_dir = Path(__file__).resolve().parent.parent  # sube al root del proyecto
    notebooks_dir = base_dir / "notebooks"
    data_dir = base_dir / "data"

    # Crear carpeta data si no existe
    data_dir.mkdir(exist_ok=True)

    # Mover todos los .xlsx
    for file in notebooks_dir.glob("*.xlsx"):
        destino = data_dir / file.name
        if destino.exists():
            destino.unlink()  # eliminar si ya existe
        shutil.move(str(file), destino)

    # Mover .zip
    for file in notebooks_dir.glob("*.zip"):
        destino = data_dir / file.name
        if destino.exists():
            destino.unlink()
        shutil.move(str(file), destino)

    # Mover carpeta matches_details completa
    matches_src = notebooks_dir / "matches_details"
    matches_dst = data_dir / "matches_details"
    if matches_src.exists():
        if matches_dst.exists():
            shutil.rmtree(matches_dst)  # eliminar carpeta destino si ya existe
        shutil.move(str(matches_src), matches_dst)

    print("✅ Archivos y carpeta movidos a /data")

if __name__ == "__main__":
    mover_archivos()
