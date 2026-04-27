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

Este documento no describe una instancia concreta. Para eso se utiliza una plantilla independiente de configuración de instancia. Este documento describe la lógica general del generador.

---

## 2. Contexto del problema

El problema tratado es una versión modificada del problema SIPA (*Student–Industry Placement Allocation*). En esta versión se consideran: estudiantes, plazas de prácticas, empresas, centros educativos y profesores supervisores. Por tanto, una instancia del problema debe contener, como mínimo:

- Estudiantes.
- Empresas.
- Plazas de prácticas.
- Competencias de estudiantes.
- Preferencias de estudiantes.
- Necesidades de competencias de las plazas.
- Cuotas mínimas y máximas de empresas.
- Dependencias entre plazas.
- Centros educativos.
- Profesores.
- Capacidades de supervisión.
- Matrices de distancia.

El generador se diseña para producir instancias factibles por construcción, es decir, instancias que permitan asignar todos los estudiantes respetando las restricciones estructurales principales del modelo.

## 3. Parámetros de entrada por línea de comandos

Los argumentos de línea de comandos se convierten en un objeto `GeneratorConfig`. El comando general es:

```bash
python random_instance_creator.py <result_path> <start_size> <end_size> <number_instances> <surplus> <slack_ratio> <placement_dep_prob> <number_competences> <most_important_competences> [seed]
```

```bash
python random_instance_creator.py output 200 600 3 20 0.0 30 6 2 1234
```

| Argumento | Descripción |
|---|---|
| `result_path` | Carpeta donde se guardan los ficheros generados. |
| `start_size` | Primer tamaño de estudiantes considerado. |
| `end_size` | Último tamaño de estudiantes considerado. |
| `number_instances` | Número de instancias generadas para cada tamaño de estudiantes. |
| `surplus` | Porcentaje de plazas adicionales respecto al número de estudiantes. |
| `slack_ratio` | Holgura adicional usada al ajustar capacidades de empresas y profesores. |
| `placement_dep_prob` | Parámetro usado para generar dependencias entre plazas. |
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
| `n_centers_min` | `2` | Número mínimo de centros educativos. |
| `n_centers_max` | `6` | Número máximo de centros educativos. |
| `prof_capacity_min` | `5` | Capacidad mínima de supervisión de un profesor. |
| `prof_capacity_max` | `25` | Capacidad máxima de supervisión de un profesor. |
| `ORS_AVAILABLE` | `False` | Indica si el script tiene disponible ORS. |
| `use_ors` | `False` | Indica si se usan distancias reales mediante ORS. |
| Distancia sintética | `max(1.0, Normal(1500, 250))` | Distribución usada para generar distancias cuando ORS está desactivado. |

---

## 5. Datos externos utilizados

El generador utiliza una carpeta `data/` con información geográfica auxiliar (también generada sintéticamente).

| Fichero o carpeta | Uso |
|---|---|
| `data/proportion_home.csv` | Distribución de probabilidad de las localizaciones de vivienda de los estudiantes. |
| `data/placement_locations.csv` | Coordenadas posibles para las empresas. |
| `data/points/*.geojson` | Puntos geográficos usados para ubicar estudiantes y centros educativos. |

---

## 6. Lógica de tamaños e instancias

La generación de tamaños se controla mediante:

```python
for n_students in range(cfg.start_size, cfg.end_size + 100, 200):
```

Esto significa que el número de estudiantes avanza en saltos fijos de `200`.

El parámetro `number_instances` no indica cuántos tamaños se generan. Indica cuántas instancias distintas se generan para cada tamaño.

Por tanto:

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

###############################################

## 7. Política de reproducibilidad

El generador utiliza dos fuentes de aleatoriedad:

- `random` de Python,
- `np.random` de NumPy.

Para asegurar reproducibilidad, ambas fuentes se inicializan antes de generar cada instancia concreta.

La política actual es:

```text
instance_seed = base_seed + global_instance_idx
```

donde:

- `base_seed` es la semilla opcional pasada por línea de comandos,
- `global_instance_idx` es un contador global de instancias generadas,
- la primera instancia tiene `global_instance_idx = 0`.

Ejemplo con:

```text
base_seed = 1234
```

| Instancia | `global_instance_idx` | Seed usada |
|---|---:|---:|
| `problem_instance_ext_200_0.txt` | 0 | 1234 |
| `problem_instance_ext_200_1.txt` | 1 | 1235 |
| `problem_instance_ext_200_2.txt` | 2 | 1236 |
| `problem_instance_ext_400_0.txt` | 3 | 1237 |
| `problem_instance_ext_400_1.txt` | 4 | 1238 |
| `problem_instance_ext_400_2.txt` | 5 | 1239 |
| `problem_instance_ext_600_0.txt` | 6 | 1240 |
| `problem_instance_ext_600_1.txt` | 7 | 1241 |
| `problem_instance_ext_600_2.txt` | 8 | 1242 |

Antes de generar cada instancia, el código fija:

```python
random.seed(instance_seed)
np.random.seed(instance_seed)
```

Esto permite asociar cada fichero generado a una semilla concreta.

### Qué garantiza esta política

Dado el mismo:

- código,
- carpeta `data/`,
- argumentos de generación,
- parámetros internos,
- y seed de instancia,

la instancia es reproducible.

La ejecución completa también es reproducible usando la misma semilla base y el mismo comando.

---

## 9. Estructura general del proceso de generación

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
10. Generar centros educativos y profesores.
11. Generar matrices de distancia.
12. Escribir la instancia en un fichero `.txt`.

---

## 10. Generación de estudiantes

Cada estudiante se genera aleatoriamente con:

- localización geográfica,
- disponibilidad de coche,
- peso asociado a distancia,
- peso asociado a desarrollo profesional,
- vector de desarrollo de competencias,
- vector de preferencias de competencias.

### 10.1. Perfiles académicos

El generador utiliza:

```text
number_profiles = 8
```

Cada perfil representa un bloque distinto de competencias.

La probabilidad de pertenecer a cada perfil se genera aleatoriamente para cada instancia y se normaliza para sumar 1.

Cada estudiante pertenece a un único perfil. Por ello, sus vectores de competencias se expanden a una dimensión total igual a:

```text
number_profiles * number_competences
```

Solo el bloque correspondiente al perfil del estudiante contiene valores no nulos. El resto se rellena con ceros.

### 10.2. Tipo de estudiante

El generador distingue tres tipos de estudiantes:

| Tipo | Probabilidad | Descripción |
|---|---:|---|
| Excelente | `0.05` | Alto desarrollo en la mayoría de competencias de su perfil. |
| Notable | `0.25` | Desarrollo alto en pocas competencias, medio en algunas y bajo en el resto. |
| Resto | `0.70` | Desarrollo medio/bajo en la mayoría de competencias. |

Según el tipo, las competencias se generan en rangos distintos:

- alto: `[0.7, 1.0]`,
- medio: `[0.4, 0.7]`,
- bajo: `[0.0, 0.4]`.

Después se barajan para evitar posiciones fijas.

### 10.3. Preferencias de competencias

Cada estudiante tiene también un vector de preferencias.

El generador selecciona una competencia fuerte usando como probabilidad el propio vector de desarrollo del estudiante. Esa competencia recibe preferencia máxima:

```text
1.0
```

El resto de preferencias se inicializa con valores bajos:

```text
[0.0, 0.3]
```

Después, el vector se baraja y se expande al bloque del perfil correspondiente.

### 10.4. Localización, coche y pesos

Cada estudiante recibe una localización según `data/proportion_home.csv`.

Además:

```text
P(has_car = True) = 0.65
```

El peso asociado a la distancia se genera como:

```text
w_distance ∈ [0.0, 0.5]
```

El peso asociado al desarrollo profesional es:

```text
w_development = 1 - w_distance
```

---

## 11. Generación de plazas

El número de plazas se calcula mediante:

```text
n_placements = ceil(n_students * (1 + surplus / 100))
```

Esto garantiza que el número de plazas sea igual o superior al número de estudiantes.

Cada plaza recibe un vector de necesidades de competencias.

Este vector se genera de dos formas:

1. reutilizando y perturbando preferencias de estudiantes ya generadas;
2. creando nuevos vectores de necesidad competencial.

Cuando se crea un nuevo vector:

- `most_important_competences` competencias reciben valor `1.0`,
- una competencia secundaria recibe valor `0.5`,
- el resto recibe valor `0.0`.

Después se baraja y se expande al bloque del perfil académico seleccionado.

---

## 12. Generación de empresas

El número de empresas se selecciona aleatoriamente a partir del número de plazas.

Se define:

```text
lower = max(2, n_placements // 10)
upper = max(2, int(placement_dep_prob / 100 * n_placements / 2))
upper = max(upper, lower)
```

Después se selecciona:

```text
n_companies ∈ [lower, upper]
```

Una vez fijado `n_companies`, las plazas se distribuyen entre empresas.

Primero se calcula:

```text
base = n_placements // n_companies
```

Después se reparte el excedente de plazas mediante una regla aleatoria sesgada, para que algunas empresas puedan concentrar más plazas.

---

## 13. Dependencias entre plazas

Las dependencias se generan empresa por empresa.

Para cada empresa:

1. se obtiene la lista de plazas de esa empresa;
2. se selecciona un porcentaje de plazas según `placement_dep_prob`;
3. las plazas seleccionadas se agrupan en grupos de tamaño mayor o igual que 2;
4. cada grupo se registra como una dependencia.

Una dependencia:

```text
[j1, j2, ..., jr]
```

significa que esas plazas deben activarse conjuntamente.

Si una empresa tiene menos de dos plazas, no se generan dependencias para ella.

---

## 14. Cuotas de empresas

Cada empresa tiene:

- cuota mínima `q_k`,
- cuota máxima `Q_k`.

### 14.1. Cuota máxima

La cuota máxima se genera inicialmente entre la mitad de las plazas de la empresa y el total de plazas de esa empresa.

Después se ajusta para garantizar que la suma de cuotas máximas permite asignar todos los estudiantes.

El ajuste respeta:

- ninguna cuota máxima puede superar las plazas reales de la empresa;
- la suma total debe ser suficiente para cubrir a todos los estudiantes;
- si se usa `slack_ratio`, se intenta añadir holgura adicional sin superar las plazas disponibles.

### 14.2. Cuota mínima

La cuota mínima se genera a partir de bloques completos.

Un bloque puede ser:

- una plaza individual no dependiente,
- un grupo completo de dependencias.

Esto evita exigir solo una parte de un grupo dependiente.

Si la suma de cuotas mínimas supera el número de estudiantes, el generador reduce cuotas mínimas hasta recuperar factibilidad.

---

## 15. Centros educativos y profesores

La versión modificada del modelo requiere generar centros educativos y profesores supervisores.

### 15.1. Centros

El número de centros se genera en:

```text
[n_centers_min, n_centers_max]
```

Por defecto:

```text
[2, 6]
```

Las coordenadas se muestrean desde los puntos disponibles en `data/points/`.

### 15.2. Profesores

El número de profesores se genera en:

```text
[n_centers, 3 * n_centers]
```

Cada profesor se asigna aleatoriamente a un centro.

Cada profesor recibe una capacidad:

```text
C_t ∈ [prof_capacity_min, prof_capacity_max]
```

Por defecto:

```text
[5, 25]
```

### 15.3. Ajuste de capacidad docente

Después de generar profesores, se comprueba:

```text
sum(C_t) >= ceil(n_students * (1 + slack_ratio))
```

Si no se cumple, el generador incrementa capacidades hasta alcanzar la capacidad mínima necesaria.

---

## 16. Matrices de distancia

Cada instancia contiene tres matrices:

| Matriz | Dimensión | Uso |
|---|---:|---|
| Estudiante → Empresa | `n_students x n_companies` | Distancia o tiempo entre cada estudiante y cada empresa. |
| Centro → Empresa | `n_centers x n_companies` | Distancia o tiempo entre cada centro y cada empresa. |
| Empresa → Empresa | `n_companies x n_companies` | Distancia o tiempo entre empresas. |

Actualmente ORS está desactivado, por lo que se generan distancias sintéticas:

```text
d = max(1.0, Normal(1500, 250))
```

Estas matrices son usadas posteriormente por el evaluador y pueden normalizarse en la fase de evaluación.

---

## 17. Escritura del fichero de instancia

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
| `n_centers` | Número de centros educativos. |
| `n_professors` | Número de profesores. |
| `CENTER_LOCATIONS` | Coordenadas de centros educativos. |
| `PROFESSOR_INFO` | Centro y capacidad de cada profesor. |
| `CENTER_COMPANY_DISTANCE` | Matriz centro-empresa. |
| `COMPANY_COMPANY_DISTANCE` | Matriz empresa-empresa. |

Este formato es posteriormente leído por `problem.py`.

---

## 18. Factibilidad por construcción

El generador intenta producir instancias factibles por construcción.

Los mecanismos principales son:

1. `n_placements >= n_students`.
2. Las cuotas máximas de empresas se ajustan para cubrir todos los estudiantes.
3. Las cuotas mínimas se generan desde bloques completos.
4. Las cuotas mínimas se reducen si su suma supera el número de estudiantes.
5. Las dependencias se generan dentro de una misma empresa.
6. La capacidad total de profesores se incrementa si no es suficiente.
7. Las matrices de distancia sintéticas tienen valores positivos.

Estas medidas no optimizan la instancia, pero evitan problemas estructurales básicos de inviabilidad.

---

## 19. Relación con el modelo SIPA modificado

Las instancias generadas están alineadas con el modelo SIPA modificado porque incluyen:

- centros educativos,
- profesores,
- capacidades máximas de profesores,
- distancias centro-empresa,
- distancias empresa-empresa,
- información para evaluar dispersión geográfica,
- información para evaluar carga de supervisión.

Esto permite evaluar soluciones con cuatro componentes principales:

| Componente | Sentido | Interpretación |
|---|---|---|
| `tau_sum` | Maximizar | Utilidad de estudiantes. |
| `eta_sum` | Maximizar | Utilidad de empresas. |
| `lbar_sum` | Minimizar | Coste de dispersión o supervisión de profesores. |
| `sigma_sum` | Minimizar | Desequilibrio de carga dentro de centros. |

---

## 20. Diferencias respecto al generador del modelo original

El generador actual no debe entenderse como una reproducción exacta del generador experimental del artículo original.

Sus principales diferencias son:

1. incorpora centros educativos;
2. incorpora profesores supervisores;
3. añade capacidades máximas de profesores;
4. genera matrices adicionales para supervisión;
5. usa perfiles académicos expandidos en bloques de competencias;
6. permite distancias sintéticas;
7. está adaptado a una evaluación multiobjetivo de cuatro componentes;
8. incorpora reproducibilidad mediante seed por instancia.

---

## 21. Uso previsto dentro del proyecto

El flujo de uso previsto es:

1. Definir parámetros de generación.
2. Ejecutar `random_instance_creator.py`.
3. Obtener ficheros `.txt`.
4. Registrar la configuración en la ficha de instancia.
5. Cargar cada instancia con `problem.py`.
6. Ejecutar heurísticas y metaheurísticas.
7. Guardar estadísticas y asignaciones.
8. Comparar algoritmos sobre las mismas instancias.

La ficha de Overleaf debe almacenar solo la información concreta de una generación. Este documento almacena la lógica general del generador.

---

## 22. Relación con la ficha de configuración

La documentación debe dividirse en dos niveles:

| Documento | Propósito |
|---|---|
| `design_random_instance_creator.md` | Explicar el diseño general y funcionamiento del generador. |
| `Instance Configuration` | Registrar los valores concretos usados en una generación. |

La ficha de configuración debería contener únicamente:

- ficheros generados,
- dimensiones finales de cada instancia,
- seed concreta por instancia,
- argumentos del generador,
- parámetros internos relevantes,
- política de semillas,
- notas opcionales.

La información estable del generador, como el uso de `data/` o el funcionamiento interno, debe quedar en este documento para evitar redundancias.

---

## 23. Notas de diseño

- El generador prioriza factibilidad estructural sobre realismo absoluto.
- Las distancias sintéticas permiten experimentar sin depender de servicios externos.
- Los perfiles académicos generan compatibilidades parciales entre estudiantes y plazas.
- Las dependencias entre plazas introducen restricciones combinatorias relevantes.
- La incorporación de profesores y centros aumenta la dificultad y realismo organizativo.
- La seed por instancia permite trazabilidad y reproducibilidad más robustas.
- Si no se proporciona seed, la generación no es reproducible.
- Si cambia el código, la carpeta `data/` o los parámetros internos, las instancias deben considerarse pertenecientes a una configuración distinta.
