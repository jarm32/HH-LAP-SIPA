

---

## 2. Representación del individuo

### 2.1 Decisión de diseño

El individuo del GA se representará principalmente mediante un vector:

- `student_to_placement[i] = j`

es decir, una asignación directa de cada estudiante `i` a una plaza `j`.

No se empleará como representación genética principal una codificación completa sobre variables `xijt`, porque esa codificación introduce demasiada dimensionalidad y complica innecesariamente los operadores genéticos y la reparación. En el modelo modificado, `xijt` es útil como formulación matemática, pero no es la representación más práctica para una metaheurística evolutiva. :contentReference[oaicite:4]{index=4}

### 2.2 Justificación

Esta representación es la más adecuada por tres razones:

1. La estructura principal del problema está en decidir qué plazas ocupan los estudiantes.
2. La asignación de profesores puede tratarse después como una segunda fase de reconstrucción o reparación.
3. La implementación actual ya separa internamente ambas capas:  
   - `student_to_placement`
   - `placement_to_professor` :contentReference[oaicite:5]{index=5}

Además, el generador factible actual sigue exactamente esa lógica: primero decide plazas factibles para los estudiantes y después asigna profesores con un proceso de reparación. :contentReference[oaicite:6]{index=6}

### 2.3 Representación derivada

A partir del cromosoma principal, se reconstruirán las estructuras auxiliares necesarias para formar un objeto `Solution` completo:

- `placement_filled`
- `company_load`
- `placement_to_professor`
- `professor_load`

Por tanto, el cromosoma no será una `Solution` completa, sino una representación compacta a partir de la cual se generará o reparará una `Solution` válida.

---

## 3. Población inicial

La población inicial se generará con la heurística ya disponible:

- `generate_random_feasible_fixing(problem, seed=...)`

Cada individuo inicial será, por tanto, una solución factible completa obtenida mediante el generador aleatorio con reparación. Después, de esa solución se extraerá el cromosoma `student_to_placement`. :contentReference[oaicite:7]{index=7}

### 3.1 Ventajas de esta decisión

- Se parte desde soluciones factibles desde la primera generación.
- Se reutiliza una pieza ya validada del proyecto.
- Se evita perder tiempo generando individuos inviables al azar.
- La baseline aleatoria pasa a actuar también como constructor inicial del GA.

### 3.2 Tamaño inicial propuesto

Como primera versión del algoritmo, se propone usar una población moderada, por ejemplo:

- `population_size = 50`

Este valor podrá ajustarse posteriormente según el tiempo medio por evaluación y la diversidad observada.

---

## 4. Evaluación fitness

### 4.1 Evaluación principal

La evaluación principal del individuo será multiobjetivo pura, usando la función ya implementada:

- `evaluate_solution_multi(sol)`

Esta función devuelve las cuatro componentes separadas:

- `tau_sum`
- `eta_sum`
- `lbar_sum`
- `sigma_sum` :contentReference[oaicite:8]{index=8}

### 4.2 Sentido de los objetivos

Los sentidos de optimización son:

- `tau_sum`: maximizar
- `eta_sum`: maximizar
- `lbar_sum`: minimizar
- `sigma_sum`: minimizar

Esto coincide con la lógica ya implementada en la gestión del conjunto de Pareto. :contentReference[oaicite:9]{index=9}

### 4.3 Evaluación auxiliar escalar

Además de la evaluación multiobjetivo, se calculará un valor escalar auxiliar mediante:

- `evaluate_solution_scalar(sol, weights)`

Este valor **no** será el criterio principal del algoritmo, sino un apoyo para:

- desempates,
- poda de soluciones muy similares,
- ranking secundario cuando sea necesario. :contentReference[oaicite:10]{index=10} :contentReference[oaicite:11]{index=11}

Por tanto, el enfoque del GA será desde el principio **multiobjetivo real**, no una simple escalarización.

---

## 5. Selección

La estrategia de selección prevista para esta metaheurística será **NSGA-II**.

### 5.1 Justificación

NSGA-II es adecuada porque:

- trabaja directamente con varios objetivos,
- usa dominancia no dominada,
- incorpora diversidad en el frente,
- encaja con la estructura Pareto ya existente en el proyecto. :contentReference[oaicite:12]{index=12}

### 5.2 Decisión práctica

Aunque el algoritmo se implemente con DEAP, la lógica conceptual será:

1. ordenar individuos por frentes no dominados,
2. priorizar los mejores frentes,
3. usar una medida de diversidad dentro del frente para mantener variedad.

En una primera versión, puede aceptarse que DEAP gestione esta parte internamente mediante sus utilidades de NSGA-II.

---

## 6. Operador de cruce

### 6.1 Idea general

El cruce combinará asignaciones estudiante→plaza de dos padres para producir uno o dos descendientes, pero no se aceptará el resultado directamente: tras el cruce será obligatorio aplicar reconstrucción y reparación.

### 6.2 Diseño conceptual del cruce

El cruce inicial propuesto será de tipo **mezcla parcial por estudiantes**:

1. se selecciona un subconjunto de estudiantes,
2. el descendiente hereda para esos estudiantes la plaza del padre A,
3. para el resto intenta heredar la plaza del padre B,
4. si aparecen conflictos o inconsistencias, se repara.

### 6.3 Problemas que puede generar el cruce

El cruce puede romper:

- unicidad de plazas,
- cuotas mínimas y máximas por empresa,
- bloques de dependencias,
- completitud de asignación.

Por ello, tras el cruce no se evaluará directamente el descendiente, sino que pasará antes por un procedimiento de `repair`.

### 6.4 Razón para no usar cruce directo sobre `xijt`

Cruzar directamente una estructura tridimensional estudiante-plaza-profesor complicaría mucho la herencia y generaría una gran cantidad de inviabilidad. Dado que el proyecto ya trabaja de forma natural con la capa estudiante→plaza y luego reconstruye profesores, esa segunda capa se seguirá tratando como derivada y no como genética principal. :contentReference[oaicite:13]{index=13} :contentReference[oaicite:14]{index=14}

---

## 7. Operador de mutación

### 7.1 Idea general

La mutación deberá ser local y controlada. No interesa alterar demasiados genes a la vez, porque se perdería estructura útil y aumentaría el coste de reparación.

### 7.2 Mutaciones iniciales propuestas

Se propone empezar con una o varias de estas mutaciones:

- **move mutation**: mover un estudiante a otra plaza libre o intercambiable,
- **swap mutation**: intercambiar las plazas de dos estudiantes,
- **block-aware mutation**: activar o desactivar un bloque de dependencias y reconstruir la parte afectada,
- **company-balance mutation**: modificar localmente asignaciones para aliviar empresas cerca de máximos o reforzar mínimos.

### 7.3 Tratamiento posterior

Toda mutación irá seguida de reparación, ya que un pequeño cambio local puede dejar la solución en estado no válido respecto a dependencias, cuotas o supervisión.

---

## 8. Repair

El operador de reparación será una de las piezas centrales del algoritmo.

### 8.1 Objetivo

Transformar un descendiente parcial o inconsistente en una solución completamente factible antes de evaluarlo.

### 8.2 Repair en dos fases

#### Fase 1: reparación estudiante→plaza

Debe garantizar:

- que cada estudiante tenga exactamente una plaza,
- que cada plaza esté ocupada a lo sumo por un estudiante,
- que se respeten los mínimos y máximos por empresa,
- que los bloques de dependencias se asignen completos o no se asignen.

Estas condiciones coinciden con la estructura del modelo original y con la validación actual de las soluciones. :contentReference[oaicite:15]{index=15} :contentReference[oaicite:16]{index=16}

#### Fase 2: reparación plaza→profesor

Una vez cerrada la parte estudiante-plaza, se reasignarán profesores a las plazas ocupadas garantizando:

- que toda plaza ocupada tenga profesor,
- que ningún profesor exceda su capacidad,
- que la solución siga siendo válida. :contentReference[oaicite:17]{index=17} :contentReference[oaicite:18]{index=18}

### 8.3 Reutilización del código existente

La lógica de reparación deberá inspirarse y, en lo posible, reutilizar funciones ya existentes en el generador actual, especialmente:

- selección y arreglo de dependencias,
- reconstrucción de plazas factibles,
- asignación de profesores con reparación ligera. :contentReference[oaicite:19]{index=19}

---

## 9. Reemplazo

### 9.1 Estrategia general

Se seguirá un esquema elitista tipo NSGA-II:

1. unir población actual y descendencia,
2. ordenar por frentes no dominados,
3. construir la siguiente generación manteniendo primero los mejores frentes,
4. si un frente no cabe completo, usar criterio de diversidad.

### 9.2 Justificación

Este mecanismo:

- conserva élite multiobjetivo,
- evita perder buenas soluciones por azar,
- mantiene variedad en la población,
- es consistente con la filosofía Pareto que ya tiene el proyecto. :contentReference[oaicite:20]{index=20}

---

## 10. Gestión del Pareto global

Además de la población evolutiva interna, el algoritmo mantendrá un **conjunto Pareto global externo** con las mejores soluciones no dominadas encontradas durante toda la ejecución.

### 10.1 Implementación prevista

Se reutilizarán las utilidades ya existentes:

- `EvaluatedSolution`
- `update_pareto_set`
- `prune_pareto_set_by_size` :contentReference[oaicite:21]{index=21}

### 10.2 Objetivo

Esto permitirá:

- registrar las mejores soluciones de toda la ejecución,
- compararlas con la baseline aleatoria,
- exportarlas o inspeccionarlas después,
- desacoplar la población evolutiva del archivo final de resultados.

---

## 11. Criterio de parada

Como primera versión, el algoritmo podrá detenerse por uno o varios de los siguientes criterios:

- número máximo de generaciones,
- límite de tiempo,
- estancamiento del Pareto global durante varias generaciones.

### 11.1 Propuesta inicial

Para mantener coherencia con la baseline actual, el criterio principal inicial será el tiempo:

- `time_limit_seconds = 60`

Más adelante puede añadirse también:

- `max_generations = 100`

La baseline actual ya usa un esquema temporal parecido, por lo que la comparación será directa. :contentReference[oaicite:22]{index=22} :contentReference[oaicite:23]{index=23}

---

## 12. Parámetros iniciales propuestos

Primera configuración tentativa:

- `population_size = 50`
- `offspring_size = 50`
- `cx_prob = 0.8`
- `mut_prob = 0.2`
- `max_generations = 100`
- `time_limit_seconds = 60`
- `max_pareto_size = 50`
- `seed = 1234`

Estos valores no son definitivos; solo sirven para construir una primera versión funcional y comparable con la baseline.

---

## 13. Métricas de comparación frente a la baseline aleatoria

El rendimiento del GA se comparará con la búsqueda aleatoria actual atendiendo a:

- tamaño del Pareto final,
- calidad de las soluciones no dominadas,
- diversidad del frente,
- mejor valor escalar auxiliar alcanzado,
- tiempo de ejecución,
- número de soluciones factibles generadas.

La baseline ya dispone de una estructura de estadísticas y almacenamiento del Pareto que servirá como referencia directa para esta comparación. :contentReference[oaicite:24]{index=24} :contentReference[oaicite:25]{index=25}

---

## 14. Decisiones finales fijadas en esta fase

En esta fase de diseño quedan fijadas las siguientes decisiones:

- el GA será **multiobjetivo desde el inicio**;
- la representación genética principal será `student_to_placement`;
- la asignación de profesores se tratará como parte reconstruida o reparada;
- la población inicial se generará con `generate_random_feasible_fixing`;
- la evaluación principal será `evaluate_solution_multi`;
- el valor escalar se usará solo como apoyo auxiliar;
- la selección y el reemplazo seguirán un enfoque NSGA-II;
- cruce y mutación siempre irán seguidos de reparación;
- se mantendrá un Pareto global externo durante toda la ejecución.

Con esto queda definido el comportamiento conceptual básico del algoritmo, y el siguiente paso será trasladar este diseño a `ga_nsga2.py` mediante una implementación apoyada en DEAP.