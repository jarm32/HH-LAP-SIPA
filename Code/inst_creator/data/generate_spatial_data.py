# Genera una vez los CSV y GeoJSON de localizaciones sintéticas SIPA.
# python generate_spatial_data.py

import json
import math
import random
from pathlib import Path

RUTA_DATOS = Path(__file__).resolve().parent
SEMILLA = 32
aleatorio = random.Random(SEMILLA)

# Referencias residenciales (latitud, longitud) de cada localidad

# Coordenadas de referencia (latitud, longitud).
# Se conservan las dos originales de cada localidad.
# Las restantes son referencias sintéticas aproximadas.

REFERENCIAS_RESIDENCIALES = {
    "Valencia": [(39.4699, -0.3763), (39.4705, -0.3800), (39.4850, -0.3950), (39.4850, -0.3650),
                 (39.4740, -0.3400), (39.4520, -0.3500), (39.4510, -0.3900), (39.4680, -0.4100)],
    "Alboraya": [(39.5000, -0.3500), (39.4950, -0.3400), (39.5040, -0.3560), (39.5040, -0.3330), (39.4900, -0.3480), (39.5090, -0.3450)],
    "Paterna": [(39.5020, -0.4400), (39.5050, -0.4300), (39.5140, -0.4490), (39.4980, -0.4490), (39.5120, -0.4230), (39.4950, -0.4220)]
}

# Coordenadas de referencia para ubicaciones empresariales
REFERENCIAS_EMPRESARIALES = {"Valencia": [(39.4699, -0.3763), (39.4705, -0.3800), (39.4800, -0.3650), (39.4600, -0.3500), (39.4550, -0.3400)],
                             "Alboraya": [(39.5050, -0.3500), (39.4950, -0.3400)],
                             "Paterna": [(39.5100, -0.4450), (39.4950, -0.4350)]}

NUMERO_RESIDENCIAS = {"Valencia": 2000, "Alboraya": 1500, "Paterna": 1500}
NUMERO_EMPRESAS = {"Valencia": 300, "Alboraya": 150, "Paterna": 150}
PROPORCION_RESIDENCIAS = {"Valencia": 0.4, "Alboraya": 0.3, "Paterna": 0.3}
RADIO_RESIDENCIAS_METROS = 350
RADIO_EMPRESAS_METROS = 450


def generar_punto_cercano(referencia, radio_maximo_metros):
    """
    Genera un punto aleatorio dentro de un círculo centrado en la referencia dada
    """
    latitud, longitud = referencia
    radio = radio_maximo_metros * math.sqrt(aleatorio.random())
    angulo = aleatorio.uniform(0.0, 2.0 * math.pi)
    desplazamiento_norte = radio * math.cos(angulo)
    desplazamiento_este = radio * math.sin(angulo)
    nueva_latitud = latitud + desplazamiento_norte / 111195.0
    nueva_longitud = longitud + desplazamiento_este / (111195.0 * math.cos(math.radians(latitud)))

    return round(nueva_latitud, 7), round(nueva_longitud, 7)


def generar_coordenadas(referencias, cantidad, radio_metros, utilizadas=None):
    """
    Incluye las referencias originales y completa con puntos únicos
    """
    if utilizadas is None:
        utilizadas = set()
    coordenadas = []
    
    for indice in range(cantidad):
        referencia = referencias[indice % len(referencias)]
        coordenada = (referencia if indice < len(referencias) else generar_punto_cercano(referencia, radio_metros))
        
        while coordenada in utilizadas:
            coordenada = generar_punto_cercano(referencia, radio_metros)
        coordenadas.append(coordenada)
        utilizadas.add(coordenada)

    return coordenadas


def main():
    (RUTA_DATOS / "points").mkdir(parents=True, exist_ok=True)

    for localidad, referencias in REFERENCIAS_RESIDENCIALES.items():
        coordenadas = generar_coordenadas(referencias, NUMERO_RESIDENCIAS[localidad], RADIO_RESIDENCIAS_METROS
                                          )
        # Se respeta (lat, lon) para GeoJSON, aunque el CSV es (lon, lat)
        contenido = {"features": [{"geometry": {"coordinates": [latitud, longitud]}} for latitud, longitud in coordenadas]}
        (RUTA_DATOS / "points" / f"{localidad}.geojson").write_text(json.dumps(contenido, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    (RUTA_DATOS / "proportion_home.csv").write_text("".join(f"{localidad};{proporcion}\n" for localidad, proporcion in PROPORCION_RESIDENCIAS.items()), encoding="utf-8")

    coordenadas_empresas = []
    utilizadas_empresas = set()
    for localidad, referencias in REFERENCIAS_EMPRESARIALES.items():
        coordenadas_empresas.extend(generar_coordenadas(referencias, NUMERO_EMPRESAS[localidad], RADIO_EMPRESAS_METROS, utilizadas_empresas))
    aleatorio.shuffle(coordenadas_empresas)

    # Formato CSV (longitud;latitud).
    (RUTA_DATOS / "placement_locations.csv").write_text("".join(f"{longitud:.7f};{latitud:.7f}\n" for latitud, longitud in coordenadas_empresas), encoding="utf-8")

    assert len(coordenadas_empresas) == 600
    assert len(set(coordenadas_empresas)) == 600
    print("Datos generados correctamente:")
    print("  600 ubicaciones empresariales únicas")
    print("  5000 puntos residenciales: 2000 Valencia, 1500 Alboraya, 1500 Paterna")
    print(f"  Semilla: {SEMILLA}")


if __name__ == "__main__":
    main()