# Datos geográficos sintéticos SIPA

Este directorio contiene los datos geográficos sintéticos empleados para generar las ubicaciones de estudiantes, empresas y un centro educativo por instancia. El objetivo es construir escenarios espaciales coherentes y reproducibles para evaluar los algoritmos de asignación SIPA.

## 1. Archivos

- `generate_spatial_data.py`: genera los archivos geográficos a partir de referencias y parámetros predefinidos.
- `proportion_home.csv`: establece las probabilidades de residencia de los estudiantes por localidad.
- `placement_locations.csv`: contiene las coordenadas de las empresas.
- `points/*.geojson`: contiene las coordenadas utilizadas para seleccionar residencias y la ubicación del centro educativo.

Los archivos geográficos se generan una sola vez y son leídos posteriormente por `random_instance_creator.py`. No es necesario ejecutar `generate_spatial_data.py` cada vez que se genera una instancia.

## 2. Distribución geográfica

Se consideran tres localidades del entorno metropolitano de Valencia.

| Localidad | Proporción residencial | Puntos residenciales | Ubicaciones empresariales |
|---|---:|---:|---:|
| Valencia | 40 % | 2000 | 300 (50 %) |
| Alboraya | 30 % | 1500 | 150 (25 %) |
| Paterna | 30 % | 1500 | 150 (25 %) |
| **Total** | **100 %** | **5000** | **600** |

Las proporciones son supuestos experimentales. Se busca reducir la repetición de ubicaciones con una mayor cantidad de puntos residenciales, así como proporcionar mayor diversidad espacial en las instancias de hasta 1000 estudiantes.

Los porcentajes obtenidos en cada instancia pueden diferir ligeramente de las proporciones establecidas.

## 3. Referencias geográficas y generación de coordenadas

El generador utiliza 20 referencias residenciales y 9 empresariales. Se conservan los puntos de referencia y se generan coordenadas adicionales mediante desplazamientos aleatorios alrededor de ellos.

Se utilizan los siguientes parámetros:

- Radio máximo residencial: 350 metros.
- Radio máximo empresarial: 450 metros.
- Distribución espacial: muestreo uniforme sobre el área de un disco.
- Semilla de generación geográfica: `32`.

La ampliación residencial se consigue aumentando el número y la dispersión de las referencias, manteniendo el radio de generación original.

Se evitan coordenadas duplicadas dentro de los conjuntos generados, ya que el generador de instancias selecciona ubicaciones empresariales sin reemplazo cuando existen suficientes posiciones candidatas.

Los estudiantes sí pueden compartir una misma coordenada, puesto que sus ubicaciones se seleccionan con reemplazo.

## 4. Centro educativo y costes de desplazamiento

Cada instancia contiene un centro educativo cuya ubicación se selecciona aleatoriamente entre los puntos residenciales disponibles. Todos los profesores de una misma instancia comparten las coordenadas de ese centro, que se utiliza como origen para calcular el coste de supervisión (y no se modelan domicilios particulares del profesorado, ya que se considera que salen del centro).

Los costes de desplazamiento se calculan mediante una estimación basada en la distancia geográfica Haversine, un factor de recorrido de 1,3 y una velocidad supuesta de 30 km/h. Los resultados son tiempos (costes) sintéticos expresados en segundos y no equivalen a tiempos reales.

## 5. Formato de los archivos

- `proportion_home.csv`: localidad;probabilidad.
- `placement_locations.csv`: longitud;latitud.
- `points/*.geojson`: coordenadas en orden [latitud, longitud].

## 6. Limitaciones y justificación

Las ubicaciones utilizadas son sintéticas y se generan a partir de referencias geográficas originales y adicionales, distribuidas en distintas zonas del área de estudio. La ampliación del número de puntos residenciales y su dispersión geográfica permite obtener una mayor variedad de ubicaciones y reducir la repetición de coordenadas entre estudiantes, sin pretender reproducir con exactitud la distribución real de viviendas y empresas.

Los radios de generación, las proporciones geográficas y los parámetros de desplazamiento se han definido como parte de un entorno experimental controlado y reproducible, diseñado para proporcionar escenarios diversos y geográficamente coherentes. Esta aproximación permite verificar el correcto funcionamiento del modelo, comprobar el cumplimiento de sus restricciones y analizar el comportamiento de los algoritmos ante diferentes configuraciones del problema.

Por tanto, el objetivo de estos datos no es representar fielmente la movilidad real, sino disponer de un conjunto de instancias sintéticas suficientemente variadas y consistentes para llevar a cabo la evaluación experimental del modelo y de los métodos de resolución desarrollados.