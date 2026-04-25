# Diseño del generador de instancias

## 1. Objetivo del documento

Este documento describe el diseño del generador de instancias utilizado para crear los ficheros de entrada del problema SIPA modificado. Su objetivo es documentar cómo se construyen las instancias antes de ser empleadas por las heurísticas y metaheurísticas del proyecto.

El documento no pretende describir una instancia concreta. Para eso se utiliza una ficha independiente de configuración de instancia. Este archivo describe la lógica general del generador: qué entidades crea, qué parámetros controla, cómo garantiza la factibilidad estructural y qué información escribe en cada fichero de instancia.

---

## 2. Contexto del problema

El problema tratado es una versión modificada del problema SIPA (*Student–Industry Placement Allocation*). En el modelo original se consideran principalmente estudiantes, plazas de prácticas y empresas. La versión modificada incorpora también centros educativos y profesores supervisores, de forma que una solución debe decidir no solo qué estudiante se asigna a qué plaza, sino también qué profesor supervisa cada práctica.

Por tanto, una instancia del problema debe contener, como mínimo:

- estudiantes,
- empresas,
- plazas de prácticas,
- competencias de estudiantes,
- preferencias de estudiantes,
- necesidades de competencias de las plazas,
- cuotas mínimas y máximas de empresas,
- dependencias entre plazas,
- centros educativos,
- profesores,
- capacidades de supervisión,
- matrices de distancia.

El generador se diseña para producir instancias factibles por construcción, es decir, instancias que permitan asignar todos los estudiantes respetando las restricciones estructurales principales del modelo.

---

## 3. Parámetros generales del generador

El generador recibe una configuración global que determina el tamaño de las instancias y sus principales características estructurales.

| Parámetro | Descripción |
|---|---|
| `result_path` | Carpeta donde se guardan los ficheros generados. |
| `start_size` | Primer tamaño de estudiantes considerado. |
| `end_size` | Último tamaño de estudiantes considerado. |
| `number_instances` | Número de instancias generadas por cada tamaño de estudiantes. |
| `surplus` | Porcentaje de plazas adicionales respecto al número de estudiantes. |
| `slack_ratio` | Holgura adicional usada al ajustar capacidades de empresas y profesores. |
| `placement_dep_prob` | Parámetro empleado para generar dependencias entre plazas. |
| `number_competences` | Número de competencias base por perfil académico. |
| `most_important_competences` | Número de competencias principales en las necesidades de una plaza. |
| `n_centers_min` | Número mínimo de centros educativos. |
| `n_centers_max` | Número máximo de centros educativos. |
| `prof_capacity_min` | Capacidad mínima de supervisión de un profesor. |
| `prof_capacity_max` | Capacidad máxima de supervisión de un profesor. |
| `use_ors` | Indica si se usan distancias reales mediante ORS o distancias sintéticas. |

Por defecto, el generador trabaja con distancias sintéticas, ya que `ORS_AVAILABLE` está desactivado y `use_ors` se fija como `False` en la configuración construida desde línea de comandos.

---

## 4. Datos externos utilizados

El generador utiliza una carpeta `data` con información geográfica auxiliar. En concreto, se emplean:

| Fichero o carpeta | Uso |
|---|---|
| `data/proportion_home.csv` | Distribución de probabilidad de las localizaciones de vivienda de los estudiantes. |
| `data/placement_locations.csv` | Coordenadas posibles para las empresas. |
| `data/points/*.geojson` | Conjunto de puntos geográficos asociados a las localizaciones disponibles. |

La distribución de viviendas se usa para decidir de qué zona procede cada estudiante. Las localizaciones de empresas se muestrean desde el fichero de coordenadas de empresas. Los puntos GeoJSON se usan tanto para ubicar estudiantes como para muestrear centros educativos.

---

## 5. Estructura general del proceso de generación

El generador sigue el siguiente flujo general:

1. Cargar las distribuciones de localización de estudiantes.
2. Cargar las localizaciones posibles de empresas.
3. Definir los perfiles académicos y probabilidades base de tipos de estudiante.
4. Para cada tamaño de estudiantes:
   1. Generar varias instancias independientes.
   2. Generar estudiantes.
   3. Generar plazas.
   4. Generar empresas.
   5. Asignar plazas a empresas.
   6. Generar dependencias entre plazas.
   7. Definir cuotas mínimas y máximas por empresa.
   8. Generar centros educativos y profesores.
   9. Generar matrices de distancia.
   10. Escribir la instancia en un fichero `.txt`.

El nombre de salida sigue el formato:

```text
problem_instance_ext_<n_students>_<n_instance>.txt
```

Por ejemplo:

```text
problem_instance_ext_400_2.txt
```

representa la tercera instancia generada para el tamaño de 400 estudiantes.

---

## 6. Generación de estudiantes

Cada estudiante se genera de forma aleatoria a partir de los parámetros de perfil académico, localización y preferencias.

Para cada estudiante se definen:

- localización geográfica,
- disponibilidad de coche,
- peso asignado a la distancia,
- peso asignado al desarrollo profesional,
- vector de desarrollo de competencias,
- vector de preferencias de competencias.

### 6.1. Perfiles académicos

El generador utiliza un número fijo de perfiles académicos:

```text
number_profiles = 8
```

Cada perfil representa un bloque distinto de competencias. La probabilidad de pertenecer a cada perfil se genera aleatoriamente para cada instancia y se normaliza para que la suma de probabilidades sea igual a 1.

Cada estudiante pertenece a un único perfil. Por ello, sus vectores de competencias se expanden a una dimensión total igual a:

```text
number_profiles * number_competences
```

Solo el bloque correspondiente al perfil del estudiante contiene valores distintos de cero. El resto de bloques se rellenan con ceros.

### 6.2. Tipos de estudiantes según desarrollo competencial

El generador distingue tres tipos generales de estudiantes:

| Tipo | Probabilidad | Descripción |
|---|---:|---|
| Excelente | 0.05 | Alto desarrollo en la mayoría de competencias de su perfil. |
| Notable | 0.25 | Desarrollo alto en pocas competencias, medio en algunas y bajo en el resto. |
| Resto | 0.70 | Desarrollo medio/bajo en la mayoría de competencias. |

La asignación del tipo de estudiante se realiza aleatoriamente. Según el tipo, se generan valores de desarrollo competencial en rangos distintos:

- valores altos entre 0.7 y 1.0,
- valores medios entre 0.4 y 0.7,
- valores bajos entre 0.0 y 0.4.

Después, el vector se baraja para evitar que las competencias fuertes estén siempre en las mismas posiciones.

### 6.3. Preferencias de competencias

Además del desarrollo real de competencias, cada estudiante tiene un vector de preferencias. Este vector representa qué competencias desea desarrollar durante la práctica.

El generador selecciona una competencia fuerte del estudiante usando como probabilidad su propio vector de desarrollo competencial. Esa competencia recibe preferencia máxima:

```text
preference = 1.0
```

El resto de preferencias se inicializan con valores bajos en el intervalo:

```text
[0.0, 0.3]
```

Después, el vector de preferencias también se baraja y se expande al bloque del perfil académico correspondiente.

### 6.4. Localización, coche y pesos de preferencia

Cada estudiante recibe una localización según la distribución definida en `data/proportion_home.csv`.

Además, se genera un atributo booleano que indica si tiene coche:

```text
P(has_car = True) = 0.65
```

El peso asociado a la distancia se genera en el intervalo:

```text
w_distance ∈ [0.0, 0.5]
```

El peso asociado al desarrollo profesional se calcula como complemento:

```text
w_development = 1 - w_distance
```

De este modo, cada estudiante pondera de forma distinta la cercanía de la empresa y el interés competencial de la plaza.

---

## 7. Generación de plazas

El número de plazas depende del número de estudiantes y del porcentaje de surplus.

La fórmula usada es:

```text
n_placements = ceil(n_students * (1 + surplus / 100))
```

Esto garantiza que el número de plazas sea igual o superior al número de estudiantes.

### 7.1. Necesidades de competencias de las plazas

Cada plaza tiene un vector de necesidades de competencias. Este vector representa la importancia de cada competencia para desarrollar correctamente la práctica.

El generador construye estos vectores de dos formas:

1. reutilizando y perturbando perfiles de preferencias de estudiantes ya generados;
2. creando nuevos vectores de necesidad competencial.

Cuando se reutilizan preferencias de estudiantes, se añade una perturbación normal pequeña a los valores no nulos y después se normaliza el vector.

Cuando se crea un nuevo vector, se asignan:

- `most_important_competences` competencias con valor 1.0,
- una competencia secundaria con valor 0.5,
- el resto de competencias con valor 0.0.

Después, el vector se baraja y se expande al bloque del perfil académico seleccionado.

---

## 8. Generación de empresas

El número de empresas se selecciona aleatoriamente a partir del número de plazas. El generador define un rango mínimo y máximo:

```text
lower = max(2, n_placements // 10)
upper = max(2, int(placement_dep_prob / 100 * n_placements / 2))
upper = max(upper, lower)
```

Después se selecciona:

```text
n_companies ∈ [lower, upper]
```

Esta regla evita generar un número demasiado bajo de empresas y relaciona parcialmente la estructura de empresas con el parámetro usado para dependencias.

### 8.1. Distribución de plazas entre empresas

Una vez fijado el número de empresas, las plazas se reparten entre ellas.

Primero se calcula un número base de plazas por empresa:

```text
base = n_placements // n_companies
```

Después se reparte el excedente de plazas de forma sesgada. El objetivo es evitar que todas las empresas tengan exactamente el mismo tamaño y permitir que algunas empresas concentren más plazas que otras.

El procedimiento parte de una distribución uniforme y asigna el surplus de plazas con mayor probabilidad a un subconjunto de empresas consideradas principales.

---

## 9. Dependencias entre plazas

Algunas plazas de una misma empresa pueden depender entre sí. Esto representa situaciones en las que varias prácticas están asociadas a un mismo proyecto o actividad, de modo que deben cubrirse conjuntamente.

Las dependencias se generan empresa por empresa. Para cada empresa:

1. se obtiene la lista de plazas que pertenecen a dicha empresa;
2. se selecciona un porcentaje de plazas según `placement_dep_prob`;
3. las plazas seleccionadas se dividen en grupos de tamaño igual o superior a 2;
4. cada grupo se registra como un bloque de dependencia.

Una dependencia tiene la forma:

```text
[j1, j2, ..., jr]
```

y significa que esas plazas deben activarse o no activarse conjuntamente.

Si una empresa tiene menos de dos plazas, no se generan dependencias para ella.

---

## 10. Cuotas de empresas

Cada empresa tiene dos cuotas:

- cuota mínima `q_k`,
- cuota máxima `Q_k`.

Estas cuotas limitan cuántos estudiantes pueden ser asignados a cada empresa.

### 10.1. Cuota máxima

La cuota máxima se genera inicialmente en función del número de plazas de la empresa. Si la empresa tiene más de una plaza, se escoge aleatoriamente un valor entre la mitad de sus plazas y el total de plazas disponibles en esa empresa.

Después, las cuotas máximas se ajustan para garantizar que la suma total de capacidades sea suficiente para asignar a todos los estudiantes.

El ajuste respeta dos condiciones:

- ninguna cuota máxima puede superar el número real de plazas de la empresa;
- la suma de cuotas máximas debe permitir asignar todos los estudiantes, considerando la holgura si procede.

### 10.2. Cuota mínima

La cuota mínima se genera a partir de bloques completos de plazas. Estos bloques pueden ser:

- plazas individuales no dependientes,
- grupos completos de dependencias.

Esta decisión es importante porque evita exigir como mínimo una parte de un bloque dependiente. Es decir, si varias plazas dependen entre sí, el mínimo de empresa no debería forzar una asignación incompatible con esas dependencias.

Si la suma total de cuotas mínimas supera el número de estudiantes, el generador reduce aleatoriamente algunas cuotas mínimas hasta recuperar la factibilidad.

---

## 11. Centros educativos y profesores

La versión modificada del problema incorpora profesores supervisores y centros educativos.

### 11.1. Centros educativos

El número de centros se genera aleatoriamente dentro del rango:

```text
n_centers ∈ [n_centers_min, n_centers_max]
```

Por defecto:

```text
n_centers_min = 2
n_centers_max = 6
```

Las coordenadas de los centros se muestrean desde los puntos geográficos disponibles en los ficheros GeoJSON.

### 11.2. Profesores

El número de profesores se genera en función del número de centros:

```text
n_professors ∈ [n_centers, 3 * n_centers]
```

Cada profesor se asigna aleatoriamente a un centro educativo.

Además, cada profesor recibe una capacidad de supervisión:

```text
C_t ∈ [prof_capacity_min, prof_capacity_max]
```

Por defecto:

```text
prof_capacity_min = 5
prof_capacity_max = 25
```

### 11.3. Ajuste de capacidad docente

Después de generar los profesores, se comprueba si la capacidad total de supervisión es suficiente:

```text
sum(C_t) >= n_students * (1 + slack_ratio)
```

Si no lo es, el generador incrementa capacidades de profesores hasta cubrir la demanda mínima necesaria.

Esto garantiza que la instancia no sea infactible por falta de capacidad docente.

---

## 12. Matrices de distancia

Cada instancia contiene tres matrices de distancia:

| Matriz | Dimensión | Uso |
|---|---:|---|
| Estudiante → Empresa | `n_students x n_companies` | Evaluar el coste de desplazamiento del estudiante. |
| Centro → Empresa | `n_centers x n_companies` | Evaluar el esfuerzo de supervisión desde centros educativos. |
| Empresa → Empresa | `n_companies x n_companies` | Evaluar la dispersión entre prácticas supervisadas por un profesor. |

### 12.1. Distancias reales con ORS

El generador contempla la posibilidad de usar OpenRouteService para obtener matrices de tiempos reales. Sin embargo, en la configuración actual esta opción está desactivada.

### 12.2. Distancias sintéticas

Cuando ORS no se usa, cada distancia se genera sintéticamente mediante:

```text
d = max(1.0, Normal(1500, 250))
```

Esto evita distancias negativas o nulas y proporciona valores simulados de desplazamiento.

Estas distancias pueden normalizarse posteriormente durante la evaluación de soluciones para que los distintos términos de la función objetivo sean comparables.

---

## 13. Escritura del fichero de instancia

Cada instancia se escribe en un fichero `.txt` estructurado por bloques.

El fichero contiene la siguiente información:

| Bloque | Contenido |
|---|---|
| `n_students` | Número total de estudiantes. |
| `n_companies` | Número total de empresas. |
| `n_placements` | Número total de plazas. |
| `n_competences` | Número total de competencias tras expandir perfiles. |
| `n_dependent` | Número de grupos de dependencia. |
| `STUDENT_INFO` | Pesos, desarrollo competencial y preferencias de cada estudiante. |
| `COMPANY_INFO` | Cuotas mínima y máxima de cada empresa. |
| `PLACEMENT_INFO` | Empresa asociada a cada plaza y vector de necesidades. |
| `PLACEMENT_DEPENDENCIES` | Grupos de plazas dependientes. |
| `DISTANCE_MATRIX` | Matriz estudiante-empresa. |
| `COMPANY_LOCATIONS` | Coordenadas de empresas. |
| `n_centers` | Número de centros educativos. |
| `n_professors` | Número de profesores. |
| `CENTER_LOCATIONS` | Coordenadas de centros educativos. |
| `PROFESSOR_INFO` | Centro y capacidad de cada profesor. |
| `CENTER_COMPANY_DISTANCE` | Matriz centro-empresa. |
| `COMPANY_COMPANY_DISTANCE` | Matriz empresa-empresa. |

Este formato es posteriormente leído por el cargador de instancias (`problem.py`) para construir la representación interna del problema.

---

## 14. Factibilidad por construcción

El generador intenta crear instancias factibles por construcción. Para ello se controlan varias condiciones:

1. El número de plazas es igual o superior al número de estudiantes.
2. Las cuotas máximas de empresas se ajustan para que puedan cubrir a todos los estudiantes.
3. Las cuotas mínimas se reducen si su suma supera el número de estudiantes.
4. Las dependencias se generan siempre dentro de una misma empresa.
5. Las cuotas mínimas se calculan considerando bloques completos de dependencias.
6. La capacidad total de profesores se incrementa si no es suficiente.
7. Las matrices de distancia se generan siempre con valores positivos.

Estas medidas no optimizan la instancia, pero sí evitan que el problema sea inviable por errores estructurales básicos.

---

## 15. Relación con el modelo modificado

Las instancias generadas están alineadas con la versión modificada del modelo SIPA porque incluyen explícitamente:

- centros educativos,
- profesores,
- capacidad máxima de supervisión por profesor,
- distancias centro-empresa,
- distancias empresa-empresa,
- información necesaria para evaluar dispersión geográfica y balance de carga.

Esto permite evaluar soluciones con cuatro componentes principales:

| Componente | Sentido | Interpretación |
|---|---|---|
| `tau_sum` | Maximizar | Utilidad de los estudiantes. |
| `eta_sum` | Maximizar | Utilidad de las empresas. |
| `lbar_sum` | Minimizar | Coste de dispersión/supervisión de profesores. |
| `sigma_sum` | Minimizar | Desequilibrio de carga dentro de los centros. |

Así, el generador no solo crea datos para el modelo original estudiante-empresa, sino también para la capa adicional de supervisión académica.

---

## 16. Diferencias respecto a la generación del modelo original

El generador actual se inspira en la generación de instancias del modelo SIPA original, pero no es idéntico.

Las principales diferencias son:

1. Incorpora centros educativos.
2. Incorpora profesores supervisores.
3. Añade capacidades máximas de profesores.
4. Genera matrices adicionales para evaluar supervisión.
5. Usa perfiles académicos expandidos en bloques de competencias.
6. Permite generar distancias sintéticas cuando no se usa ORS.
7. Está adaptado a la evaluación multiobjetivo de cuatro componentes del modelo modificado.

Por tanto, debe considerarse como un generador específico para el modelo SIPA modificado del proyecto, no como una reproducción exacta del generador experimental del artículo original.

---

## 17. Uso previsto dentro del proyecto

Este generador se utiliza para construir las instancias sobre las que se comparan las heurísticas y metaheurísticas del proyecto.

El flujo de trabajo previsto es:

1. Definir los parámetros de generación.
2. Ejecutar `random_instance_creator.py`.
3. Obtener los ficheros `.txt` de instancia.
4. Cargar cada instancia con `problem.py`.
5. Ejecutar las heurísticas/metaheurísticas sobre cada instancia.
6. Guardar estadísticas y asignaciones resultantes.
7. Comparar resultados entre algoritmos.

La documentación corta en Overleaf debe servir como ficha rápida para consultar los valores concretos usados en un grupo de instancias. Este documento, en cambio, sirve para justificar y entender el diseño general del generador.

---

## 18. Comando de ejecución

El generador espera los parámetros por línea de comandos con el siguiente formato:

```bash
python random_instance_creator.py <result_path> <start_size> <end_size> <number_instances> <surplus> <slack_ratio> <placement_dep_prob> <number_competences> <most_important_competences>
```

Por ejemplo, una ejecución para generar tres instancias por tamaño entre 200 y 600 estudiantes tendría una estructura similar a:

```bash
python random_instance_creator.py output 200 600 3 <surplus> <slack_ratio> <placement_dep_prob> <number_competences> <most_important_competences>
```

Los valores concretos deben documentarse en la ficha de configuración de instancias.

---

## 19. Notas de diseño

- El generador prioriza la factibilidad estructural frente al realismo absoluto de todos los datos.
- Las distancias sintéticas son útiles para experimentar sin depender de servicios externos.
- La existencia de perfiles académicos permite generar compatibilidades parciales entre estudiantes y plazas.
- Las dependencias entre plazas introducen restricciones combinatorias relevantes para las heurísticas.
- La incorporación de profesores y centros aumenta la dificultad del problema y permite evaluar criterios organizativos adicionales.
- La generación aleatoria de varias instancias por tamaño permite comparar algoritmos sin depender de un único caso particular.

---

## 20. Relación con la ficha de configuración

Este documento debe mantenerse separado de la ficha de configuración de instancias.

La separación recomendada es:

| Documento | Propósito |
|---|---|
| `design_instance_creator.md` | Explicar el diseño general del generador. |
| `Instance Configuration` en Overleaf | Resumir rápidamente los valores usados para generar un conjunto concreto de instancias. |

De esta forma, el diseño completo queda documentado sin sobrecargar el PDF de consulta rápida.
