# Diseño del generador de instancias

## 1. Objetivo del documento

Describir el diseño y funcionamiento del generador de instancias `random_instance_creator.py`, utilizado para crear los ficheros de entrada del problema SIPA modificado. El objetivo es documentar:
- Qué entidades genera.
- Qué parámetros controla.
- Cómo se ejecuta.
- Cómo se generan las instancias.
- Cómo se garantiza la factibilidad estructural.
- Cómo se asegura la reproducibilidad.
- Qué datos externos utiliza.
- Qué formato tienen los ficheros `.txt` resultantes.

Este documento describe la lógica general del generador de instancias del modelo SIPA adaptado a un único centro educativo. La configuración concreta y las características de las 20 instancias sintéticas definitivas se recogen en un documento PDF independiente, que complementa esta explicación técnica.

---

## 2. Contexto del problema

El problema tratado es una versión modificada del problema SIPA (*Student–Industry Placement Allocation*). Una instancia del problema debe contener, como mínimo:

- Estudiantes.
- Empresas.
- Plazas de prácticas.
- Competencias de estudiantes.
- Preferencias de estudiantes.
- Necesidades de competencias de las plazas.
- Cuotas mínimas y máximas de empresas.
- Dependencias entre plazas.
- Ubicación del centro educativo.
- Profesores.
- Capacidades de supervisión.
- Matrices de coste.

El generador se diseña para producir instancias factibles por construcción, es decir, instancias que permitan asignar todos los estudiantes respetando las restricciones estructurales principales del modelo.

La instancia considera un único centro educativo al que pertenecen todos los supervisores. Cada profesor dispone de una capacidad individual de supervisión que se genera en función del número de estudiantes y de la capacidad docente total requerida.

## 3. Parámetros de entrada por línea de comandos

Los argumentos de línea de comandos se convierten en un objeto `GeneratorConfig`. El comando general es:

```bash
python random_instance_creator.py <result_path> <start_size> <end_size> <number_instances> <surplus> <slack_ratio> <placement_dep_prob> <number_competences> <most_important_competences> [seed]
```

```bash
python random_instance_creator.py output 200 1000 4 20 0.2 30 6 2 1234
```

Esta configuración utilizada genera cuatro instancias para cada uno de los tamaños 200, 400, 600, 800 y 1000 estudiantes, obteniendo un total de 20 instancias mediante una única ejecución.

| Argumento | Descripción |
|---|---|
| `result_path` | Carpeta donde se guardan los ficheros generados. |
| `start_size` | Primer tamaño de estudiantes considerado. |
| `end_size` | Último tamaño de estudiantes considerado. |
| `number_instances` | Número de instancias generadas para cada tamaño de estudiantes. |
| `surplus` | Porcentaje de plazas adicionales respecto al número de estudiantes. |
| `slack_ratio` | Porcentaje de capacidad adicional de supervisión docente respecto al número de estudiantes. |
| `placement_dep_prob` | Porcentaje global de plazas que formarán parte de algún grupo de dependencias. |
| `number_competences` | Número de competencias base por perfil académico. |
| `most_important_competences` | Número de competencias principales en las necesidades de una plaza. |
| `seed` | Semilla base opcional para asegurar reproducibilidad. |

La semilla es opcional. Si no se proporciona, las instancias siguen siendo aleatorias, pero no reproducibles.

---

## 4. Parámetros internos fijos

Además de los argumentos de entrada, el generador contiene parámetros internos definidos en el propio código. Si alguno de estos valores cambia en el código, debe considerarse una configuración de generación distinta.

| Parámetro | Valor actual | Descripción |
|---|---:|---|
| `number_profiles` | `8` | Número de perfiles académicos o bloques competenciales. |
| `p_excellent_student` | `0.05` | Probabilidad de generar un estudiante excelente. |
| `p_notable_student` | `0.25` | Probabilidad de generar un estudiante notable. |
| `prof_capacity_min` | `5` | Capacidad mínima de supervisión de un profesor. |
| `prof_capacity_max` | `25` | Capacidad máxima de supervisión de un profesor. |
| `ORS_AVAILABLE` | `False` | Indica si el script tiene disponible ORS. |
| `use_ors` | `False` | Indica si se usan distancias reales mediante ORS. |
| Rango del peso de distancia del estudiante | `[0.0, 0.5]` | Rango usado para generar el peso de distancia del estudiante (`w_distance`). |
| Factor de recorrido sintético | `1.3` | Factor multiplicativo sobre la distancia Haversine. |
| Velocidad media supuesta | `30 km/h` | Velocidad utilizada para estimar tiempos de desplazamiento. |
| Tamaño de grupos dependientes | `2 o más` | Número de plazas por grupo de dependencia. |

---

## 5. Datos externos utilizados

El generador utiliza datos geográficos sintéticos preparados previamente (carpeta `data/`). Se dispone de 5000 puntos residenciales candidatos repartidos entre Valencia (2000), Alboraya (1500) y Paterna (1500), así como de 600 ubicaciones empresariales candidatas. La distribución residencial establecida es del 40%, 30% y 30%, respectivamente.

| Fichero o carpeta | Uso |
|---|---|
| `data/proportion_home.csv` | Distribución de probabilidad de las localizaciones de vivienda de los estudiantes. |
| `data/placement_locations.csv` | Coordenadas posibles para las empresas. |
| `data/points/*.geojson` | Puntos geográficos usados para ubicar estudiantes y el centro educativo. |

Estos datos se generan con `generate_spatial_data.py`, utilizando la semilla 32. Los puntos residenciales se generan alrededor de referencias geográficas con un radio máximo de 350 metros, mientras que las ubicaciones empresariales utilizan un radio máximo de 450 metros (los detalles se documentan en `Code/inst_creator/data/README_data.md`). Cabe destacar que los archivos GeoJSON se interpretan internamente en orden [latitud, longitud].

---

## 6. Lógica de tamaños e instancias

La generación de tamaños se controla mediante:

```python
for n_students in range(cfg.start_size, cfg.end_size + 100, 200):
```

Esto significa que el número de estudiantes avanza en saltos fijos de `200`. Por ejemplo:

```text
start_size = 200
end_size = 600
```

genera:

```text
200, 400, 600
```

El parámetro `number_instances` no indica cuántos tamaños se generan, sino cuántas instancias distintas se generan para cada tamaño. Por tanto:

```text
start_size = 200
end_size = 600
number_instances = 3
```

produce:

```text
problem_instance_ext_200_0.txt
problem_instance_ext_200_1.txt
problem_instance_ext_200_2.txt

problem_instance_ext_400_0.txt
problem_instance_ext_400_1.txt
problem_instance_ext_400_2.txt

problem_instance_ext_600_0.txt
problem_instance_ext_600_1.txt
problem_instance_ext_600_2.txt
```

El nombre de salida sigue el formato:

```text
problem_instance_ext_<n_students>_<n_instance>.txt
```

donde:

- `<n_students>` es el tamaño de estudiantes,
- `<n_instance>` es el índice de instancia dentro de ese tamaño.

---

## 7. Política de reproducibilidad

El generador utiliza dos fuentes de aleatoriedad: `random` de Python y `np.random` de NumPy. Para asegurar reproducibilidad, ambas fuentes se inicializan antes de generar cada instancia concreta. La política actual es: `instance_seed` = `base_seed` + `global_instance_idx`, donde:

- `base_seed` es la semilla (opcional) pasada por línea de comandos.
- `global_instance_idx` es un contador global de instancias generadas (la primera instancia tiene `global_instance_idx = 0`).

Por ejemplo, para `base_seed` = 1234, las semillas de las instancias serían: `problem_instance_ext_200_0.txt` = 1234, `problem_instance_ext_200_1.txt` = 1235, etc. Dadas estas semillas, antes de generar cada instancia, el código las fija para asociarlas a cada fichero:

```python
random.seed(instance_seed)
np.random.seed(instance_seed)
```

De esta forma, se garantiza que, dado el mismo input (código, carpeta `data/`, argumentos de generación, parámetros internos y seed de instancia), la instancia es reproducible (al igual que la ejecución entera dada la misma semilla inicial).

---

## 8. Estructura general del proceso de generación

Para cada instancia generada, el flujo general es:

1. Cargar datos geográficos externos.
2. Definir perfiles académicos y probabilidades base de tipos de estudiante.
3. Generar la semilla específica de la instancia.
4. Generar estudiantes.
5. Generar plazas.
6. Generar empresas.
7. Repartir plazas entre empresas.
8. Generar dependencias entre plazas.
9. Generar cuotas mínimas y máximas de empresas.
10. Generar el centro educativo y el conjunto de profesores supervisores.
11. Generar matrices de coste.
12. Escribir la instancia en un fichero `.txt`.

---

## 9. Generación de estudiantes

Cada estudiante se genera aleatoriamente con:

- Localización geográfica.
- Peso asociado a distancia.
- Peso asociado a desarrollo profesional.
- Vector de desarrollo de competencias.
- Vector de preferencias de competencias.

### 9.1. Perfiles académicos

El generador utiliza `number_profiles`, donde cada perfil representa un bloque distinto de competencias. La probabilidad de pertenecer a cada perfil se genera aleatoriamente para cada instancia y se normaliza para sumar 1. 

Cada estudiante pertenece a un único perfil. Por ello, sus vectores de competencias se expanden a una dimensión total igual a `number_profiles` * `number_competences`. Solo el bloque correspondiente al perfil del estudiante contiene valores no nulos. El resto se rellena con ceros.

### 9.2. Tipo de estudiante

El generador distingue tres tipos de estudiantes:

| Tipo | Probabilidad | Descripción |
|---|---:|---|
| Excelente | `0.05` | Alto desarrollo en la mayoría de competencias de su perfil. |
| Notable | `0.25` | Desarrollo alto en pocas competencias, medio en algunas y bajo en el resto. |
| Resto | `0.70` | Desarrollo medio/bajo en la mayoría de competencias. |

Según el tipo, las competencias se generan en rangos distintos (Alto, [0.7, 1.0]; Medio, [0.4, 0.7]; o Bajo, [0.0, 0.4]). Después se barajan para evitar posiciones fijas.

### 9.3. Preferencias de competencias

Cada estudiante tiene también un vector de preferencias. El generador selecciona una competencia fuerte usando como probabilidad el propio vector de desarrollo del estudiante. Esa competencia recibe preferencia máxima (1). El resto de preferencias se inicializa con valores bajos (entre 0 y 0.3).

Después, el vector se baraja y se expande al bloque del perfil correspondiente.

### 9.4. Localización y pesos

Cada estudiante recibe una localización geográfica según la distribución de probabilidades definida en `data/proportion_home.csv`. Además, se generan un peso asociado a la distancia (`w_distance`) y un peso asociado al desarrollo profesional (`w_development` = 1 - `w_distance`).

---

## 10. Generación de plazas

Primeramente, se necesita que el número de plazas sea igual o superior al número de estudiantes. Para ello, el número de plazas se calcula mediante:

```text
n_placements = ceil(n_students * (1 + surplus / 100))
```

Además, cada plaza recibe un vector de necesidades de competencias. Este vector se genera de dos formas:

1. Reutilizando y perturbando preferencias de estudiantes ya generadas.
2. Creando nuevos vectores de necesidad competencial.

Cuando se crea un nuevo vector, las `most_important_competences` competencias reciben valor `1.0`, una competencia secundaria recibe valor `0.5`, y el resto recibe valor `0.0`. Después se baraja y se expande al bloque del perfil académico seleccionado.

Independientemente del procedimiento utilizado para generar las necesidades de una plaza, el vector resultante se normaliza dividiendo cada componente entre la suma total de sus componentes. De este modo, todos los vectores de necesidades tienen suma 1 antes de su almacenamiento, evitando diferencias artificiales de escala entre plazas. Los valores se escriben con seis decimales para reducir los errores de redondeo.

---

## 11. Generación de empresas

El número de empresas se selecciona aleatoriamente a partir del número de plazas. Se define:

```text
lower = max(2, n_placements // 10)
upper = max(2, int(placement_dep_prob / 100 * n_placements / 2))
upper = max(upper, lower)

n_companies ∈ [lower, upper]
```

Una vez fijado `n_companies`, las plazas se distribuyen entre empresas. Primero se calcula: base = n_placements // n_companies, y después se reparte el excedente de plazas mediante una regla aleatoria sesgada, para que algunas empresas puedan concentrar más plazas.

---

## 12. Dependencias entre plazas

Las dependencias se generan sobre un porcentaje global de las plazas disponibles en cada instancia, definido mediante `placement_dep_prob`. El número de plazas dependientes se obtiene aplicando dicho porcentaje sobre el total de plazas y redondeando hacia abajo cuando sea necesario.

Las plazas seleccionadas se organizan aleatoriamente en grupos de interdependencia de tamaño variable, sin establecer un límite máximo fijo. Cada grupo contiene al menos dos plazas pertenecientes a una misma empresa, y ninguna plaza puede aparecer en más de un grupo.

Las plazas pertenecientes a un mismo grupo deben ocuparse conjuntamente o permanecer todas desocupadas. Las plazas que no pertenecen a ningún grupo se consideran independientes.

---

## 13. Cuotas de empresas

Cada empresa tiene cuota mínima `q_k` y cuota máxima `Q_k`.

### 13.1. Cuota máxima

La cuota máxima de cada empresa (`Q_k`) coincide con el número de plazas de prácticas que ofrece, evitando así que ninguna empresa pueda recibir más estudiantes que plazas disponibles.

### 13.2. Cuota mínima

La cuota mínima se genera inicialmente a partir de bloques completos de plazas. Un bloque puede ser:

- Una plaza individual no dependiente.
- Un grupo completo de plazas interdependientes.

De esta forma, las cuotas mínimas iniciales tienen en cuenta las dependencias entre plazas. Sin embargo, si la suma de cuotas mínimas supera el número de estudiantes, el generador reduce algunas cuotas hasta cumplir dicho límite. Este ajuste final no garantiza que cada cuota mínima siga siendo exactamente la suma de bloques completos, por lo que se comprueba posteriormente la factibilidad de las instancias generadas.

---

## 14. Centro educativo y profesores

Se considera un único centro educativo por instancia al que pertenecen todos los profesores supervisores.

### 14.1. Centro

La ubicación del centro se selecciona aleatoriamente entre los puntos geográficos residenciales disponibles para Valencia, Alboraya y Paterna. De esta forma, constituye el origen de los desplazamientos de supervisión de cada profesor.

### 14.2. Número de profesores

El número de profesores se determina en función del número de estudiantes y de la capacidad total de supervisión requerida.

Primero se calcula la capacidad docente total objetivo, incorporando la holgura definida mediante `slack_ratio`:

\[
C_{\text{objetivo}}=\left\lceil S(1+\text{slack\_ratio})\right\rceil
\]

donde \(S\) representa el número de estudiantes. A partir de esta capacidad, el generador determina un intervalo de posibles cantidades de profesores, considerando que cada uno puede supervisar entre 5 y 25 estudiantes. Para obtener cantidades razonables, se utiliza como referencia una capacidad media aproximada de entre 10 y 22 estudiantes por profesor.

Finalmente, el número de profesores se selecciona aleatoriamente dentro de dicho intervalo, y sus capacidades individuales se generan y ajustan posteriormente para que la suma coincida con la capacidad docente total objetivo.

### 14.3. Ajuste de capacidad docente

Cada profesor recibe inicialmente una capacidad aleatoria dentro de los límites establecidos (la dispersión de las capacidades también varía entre instancias). A continuación, el generador ajusta las capacidades individuales hasta conseguir:

\[
\sum_{t=1}^{T} C_t=C_{\text{objetivo}}
\]

Con slack_ratio = 0.2, la capacidad docente total equivale al 120 % del número de estudiantes, lo que permite contar con profesores de diferentes capacidades sin perder la holgura requerida.

---

## 15. Matrices de costes de desplazamiento

Cada instancia contiene tres estructuras de costes de desplazamiento, calculadas a partir de las coordenadas geográficas de estudiantes, empresas y del centro educativo.

Los costes representan tiempos estimados de desplazamiento (expresados en segundos). Para calcularlos, se utiliza la distancia geográfica Haversine entre dos ubicaciones, multiplicada por un factor de recorrido de `1.3` y convertida a tiempo mediante una velocidad media de `30 km/h`.

La fórmula utilizada es:

\[
t_{uv}=\frac{d_{\text{Haversine}}(u,v)\cdot 1.3}{30}\cdot 3600
\]

donde \(d_{\text{Haversine}}(u,v)\) representa la distancia en kilómetros entre las ubicaciones \(u\) y \(v\), y \(t_{uv}\) es el tiempo estimado de desplazamiento en segundos. Todos los resultados se redondean a dos decimales.

Para ubicaciones diferentes se establece un tiempo mínimo de un segundo, mientras que para coordenadas coincidentes el coste es cero.

Las estructuras generadas son:

| Estructura | Dimensión | Descripción |
|---|---|---|
| Estudiante - Empresa | `n_students × n_companies` | Tiempo estimado de desplazamiento desde la residencia de cada estudiante hasta cada empresa. |
| Centro - Empresa | `n_companies` | Vector de tiempos estimados desde el centro educativo hasta cada empresa. |
| Empresa - Empresa | `n_companies × n_companies` | Matriz de tiempos estimados entre las ubicaciones de las empresas. |

En el caso de la matriz empresa – empresa, cabe destacar que es simétrica y tiene la diagonal igual a cero, debido a que los tiempos se calculan mediante el mismo procedimiento geográfico en ambos sentidos.

La normalización de estos costes se realizará durante el procesamiento de las instancias y la evaluación de soluciones.

---

## 16. Escritura del fichero de instancia

Cada instancia se escribe en un fichero `.txt` con bloques estructurados.

| Bloque | Contenido |
|---|---|
| `n_students` | Número total de estudiantes. |
| `n_companies` | Número total de empresas. |
| `n_placements` | Número total de plazas. |
| `n_competences` | Número total de competencias tras expandir perfiles. |
| `n_dependent` | Número de grupos de dependencia. |
| `STUDENT_INFO` | Pesos, desarrollo competencial y preferencias de cada estudiante. |
| `COMPANY_INFO` | Cuotas mínima y máxima de cada empresa. |
| `PLACEMENT_INFO` | Empresa asociada y vector de necesidades de cada plaza. |
| `PLACEMENT_DEPENDENCIES` | Grupos de plazas dependientes. |
| `DISTANCE_MATRIX` | Matriz estudiante-empresa. |
| `COMPANY_LOCATIONS` | Coordenadas de empresas. |
| `n_professors` | Número de profesores. |
| `CENTER_LOCATION` | Coordenadas del centro educativo. |
| `PROFESSOR_INFO` | Identificador y capacidad de cada profesor. |
| `CENTER_COMPANY_DISTANCE` | Vector de tiempos entre el centro y cada empresa. |
| `COMPANY_COMPANY_DISTANCE` | Matriz empresa-empresa. |

Este formato es posteriormente leído por `problem.py`.

---

## 17. Factibilidad por construcción

El generador intenta producir instancias factibles por construcción.

Los mecanismos principales son:

1. `n_placements >= n_students`.
2. Las cuotas máximas coinciden con el número de plazas ofertadas por cada empresa.
3. Las cuotas mínimas se generan desde bloques completos.
4. Las cuotas mínimas se reducen si su suma supera el número de estudiantes.
5. Las dependencias se generan dentro de una misma empresa.
6. La capacidad docente total se ajusta al objetivo establecido, respetando las capacidades individuales.

Las condiciones anteriores favorecen la factibilidad estructural de las instancias generadas, aunque no garantizan la factibilidad para cualquier combinación de parámetros. En el conjunto definitivo de 20 instancias se ha comprobado la consistencia de las restricciones y la existencia de asignaciones factibles que permiten cubrir a todos los estudiantes respetando las cuotas empresariales, las dependencias entre plazas y las capacidades docentes.