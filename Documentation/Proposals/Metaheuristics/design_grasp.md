# Diseño conceptual del GRASP

## 1. Objetivo del algoritmo

Desarrollar una heurística GRASP que se establezca como una baseline multiobjetivo para el problema SIPA modificado, capaz de generar soluciones factibles de calidad mediante una construcción más informada que la búsqueda aleatoria, incorporando además una mejora local sencilla y efectiva, e integrándose con el Pareto externo ya existente en el proyecto para permitir una evaluación adecuada.

Además, debe optimizar simultáneamente:

- ↑ `tau_sum` (satisfacción estudiantes)
- ↑ `eta_sum` (satisfacción empresas)
- ↓ `lbar_sum` (coste de supervisión)
- ↓ `sigma_sum` (desequilibrio entre profesores)

---

## 2. Representación de la solución

La representación principal de la solución será `student_to_placement`.

Durante la construcción y la búsqueda local se trabajará únicamente con la asignación estudiante–plaza, ya que introducir simultáneamente la asignación estudiante–plaza–profesor aumentaría mucho la complejidad del algoritmo y no resulta necesario para una baseline. Esta asignación de profesores no se codifica directamente, sino que se reconstruye posteriormente, reduciendo la complejidad y manteniendo coherencia con la estructura actual del proyecto.

---

## 3. Fase constructiva

La fase constructiva seguirá un esquema greedy-randomized sobre asignaciones estudiante–plaza.

La idea general será construir una solución de forma incremental. En cada paso, se seleccionará aleatoriamente una asignación factible estudiante–plaza entre un conjunto de candidatas bien valoradas (RCL) según una función greedy. La construcción trabajará únicamente sobre la parte `student_to_placement`. Una vez completada la asignación de todos los estudiantes a plazas, se reconstruirá la asignación de profesores.

### 3.1. Criterio greedy

La puntuación greedy de una asignación candidata `(i, j)` se basará únicamente en la utilidad local estudiante–plaza y empresa–estudiante, es decir, en la parte del modelo relacionada con `tau` y `eta`. De esta forma, la construcción favorecerá asignaciones que: sean buenas para el estudiante, sean buenas para la empresa y no comprometan la factibilidad estructural.

### 3.2. Definición del score greedy

Para cada asignación candidata `(i, j)`, se definirá un score greedy local:

- `g(i,j) = 0.5 * tau_ij + 0.5 * eta_ij`, donde `tau_ij` representa la utilidad de la plaza `j` para el estudiante `i`, `eta_ij` representa la utilidad del estudiante `i` para la plaza o empresa asociada a `j`, y los 0.5 representan la asignación del mismo peso a la perspectiva del estudiante y a la de la empresa.

El score greedy se utilizará únicamente para ordenar candidatas factibles dentro del proceso constructivo. Las restricciones estructurales del problema no se incorporarán como términos adicionales del score, sino como condiciones de factibilidad que una candidata debe respetar para poder ser considerada.

### 3.3. Exclusión de `lbar` y `sigma`

En esta fase constructiva no se usarán `lbar` ni `sigma` en la función greedy.

La razón es que ambos componentes dependen de la asignación de profesores y de la estructura global de supervisión, no de una decisión local aislada estudiante–plaza. Introducirlos en la fase constructiva obligaría a estimar continuamente efectos indirectos y globales que aún no están definidos en ese momento de la construcción. Además, complicaría mucho el diseño del score greedy, encarecería el coste de construcción y mezclaría demasiado pronto la capa de supervisión con la capa principal de asignación.

Por tanto, la construcción se centrará en `tau` y `eta`, mientras que `lbar` y `sigma` quedarán incorporados en la evaluación completa de la solución, una vez reconstruida la asignación de profesores.

### 3.4. Control de factibilidad

Durante la fase constructiva se aplicará un control de factibilidad en dos niveles:

1. Filtro local de factibilidad: solo se considerarán asignaciones `(i,j)` que no violen restricciones básicas (ocupación única de plaza, no superar máximos de empresa, consistencia con dependencias ya activadas).
2. Validación y reconstrucción final: una vez completada la asignación `student_to_placement`, se reconstruirá la solución completa (incluyendo profesores) y se validará globalmente.

### 3.5. Control temporal del constructivo y fallback factible

En instancias grandes, la fase constructiva greedy-randomized puede consumir una parte excesiva del tiempo intentando completar una solución factible, especialmente cuando existen muchas empresas, plazas y bloques de dependencias. Para evitar que una única llamada al constructivo agote todo el tiempo de ejecución, se incorpora un límite temporal local para cada fase constructiva (`constructive_time_limit_seconds = 30`), además del límite global del algoritmo. Por otro lado, el número máximo de intentos constructivos por iteración se fija en `constructive_max_attempts = 5`, con el objetivo de evitar trayectorias constructivas demasiado largas y favorecer más reinicios dentro del mismo presupuesto temporal.

Si el constructivo GRASP no consigue generar una solución inicial factible dentro de ese límite local, se activa un mecanismo de respaldo basado en la generación aleatoria factible ya existente (`generate_random_feasible_fixing`). Esta solución de respaldo no se registra directamente en el Pareto, sino que se utiliza como punto de partida para la misma búsqueda local del GRASP.

Este mecanismo no convierte el algoritmo en una búsqueda aleatoria, ya que el fallback solo actúa como generador de una solución inicial cuando el constructivo GRASP falla. La mejora local y el registro multiobjetivo posterior siguen siendo los mismos.

---

## 4. Definición de la RCL

La Restricted Candidate List (RCL) se construirá a partir de las mejores asignaciones candidatas disponibles en cada paso de la construcción. El procedimiento será:

1. Generar el conjunto de movimientos factibles estudiante–plaza.
2. Calcular la puntuación greedy de cada uno.
3. Seleccionar las candidatas cuya puntuación supere un umbral relativo respecto a la mejor.
4. Elegir aleatoriamente una candidata dentro de esa RCL (introduce diversidad).

### 4.1. Parámetro de la RCL

Para este algoritmo se usará una RCL por umbral relativo, ya que se adapta mejor a instancias de distinto tamaño o escala que una RCL de tamaño fijo. Este umbral irá controlado por un parámetro `alpha_rcl = 0.5` (introduce un nivel moderado de aleatoriedad, facilitando la exploración para encontrar soluciones factibles en instancias difíciles). No se empleará una RCL de cardinalidad fija, ya que ese enfoque depende más del tamaño concreto del conjunto candidato en cada iteración y resulta menos adaptable entre instancias.

Además, sea:

- `g_max` la mejor puntuación greedy disponible en el conjunto de candidatas.
- `g_min` la peor puntuación.

Se incluirán en la RCL todas las candidatas que cumplan:

`g(i,j) >= g_max - alpha_rcl * (g_max - g_min)`

---

## 5. Búsqueda local

La búsqueda local se definirá mediante un único vecindario: el swap entre dos estudiantes. Esto implica que, a partir de una solución construida, se explorarán vecinos generados al intercambiar las plazas asignadas a dos estudiantes.

Aunque existen vecindarios más potentes, también son bastante más complejos y específicos del problema. Para una baseline, no compensa aumentar tanto la complejidad.

### 5.1 Aceptación de vecinos

La búsqueda local aceptará un vecino cuando la solución resultante siga siendo válida y mejore un valor escalar auxiliar normalizado de la evaluación. Es decir, la mejora local usará una guía monobjetivo auxiliar para decidir avances, mientras que la calidad final del algoritmo seguirá midiéndose mediante Pareto externo multiobjetivo.

El criterio escalar auxiliar se emplea en lugar de la dominancia Pareto dentro de la búsqueda local porque proporciona una dirección clara de mejora en cada movimiento. Si se utilizara dominancia Pareto como criterio de aceptación, muchos vecinos resultarían no comparables con la solución actual, lo que dificultaría el avance de la búsqueda y podría bloquearla prematuramente. Por tanto, el valor escalar auxiliar se emplea únicamente como criterio de movimiento dentro de la búsqueda local, mientras que la selección multiobjetivo real de soluciones se delega en el Pareto externo.

Dado que `tau_sum` y `eta_sum` son sumas sobre estudiantes, mientras que `lbar_sum` y `sigma_sum` son agregados asociados a profesores y centros, sus magnitudes son muy diferentes. Para evitar que las utilidades estudiante–empresa dominen completamente el criterio de aceptación, la búsqueda local utilizará una versión normalizada del valor escalar auxiliar.

Conceptualmente, el score de aceptación será: `score = alpha * tau_norm + beta * eta_norm - gamma * lbar_norm - delta * sigma_norm`, donde:

- `tau_norm = tau_sum / n_students`
- `eta_norm = eta_sum / n_students`
- `lbar_norm = lbar_sum / n_professors`
- `sigma_norm = sigma_sum / n_centers`

De esta forma, el constructivo GRASP se mantiene guiado por `tau` y `eta`, al operar únicamente sobre asignaciones estudiante–plaza, mientras que la búsqueda local incorpora de forma más equilibrada los cuatro objetivos una vez reconstruida la asignación de profesores.

### 5.2 Estrategia de exploración

La exploración del vecindario se realizará mediante una estrategia de first improvement para reducir el coste computacional (respecto a best improvement). Esto implica que, en cada iteración de la búsqueda local:

- Se recorren vecinos generados mediante swaps.
- Se acepta el primer vecino que mejora la solución actual.
- Se continúa desde esa nueva solución.

Además, para evitar que una única solución consuma todo el presupuesto temporal del algoritmo, la búsqueda local se encuentra acotada computacionalmente mediante dos límites adicionales:

- Nº máximo de vecinos evaluados por pasada (`max_neighbors_per_pass = 1000`).
- Nº máximo de mejoras aceptadas por solución (`max_local_improvements = 30`).

De esta forma, se evita una intensificación excesiva sobre una sola solución y se favorece la exploración de un mayor número de construcciones GRASP dentro del mismo tiempo total de ejecución. Esto resulta más adecuado para una baseline multiobjetivo, donde interesa combinar calidad individual y diversidad de soluciones.

---

## 6. Criterio de parada

El GRASP iterará con el esquema (construcción, mejora local, registro en Pareto) hasta alcanzar un límite de tiempo establecido, al igual que el resto de heurísticas ya implementadas en el proyecto. También podrá admitirse un límite máximo de iteraciones como criterio secundario.

Además del límite temporal global, se utiliza un límite temporal local para la fase constructiva de cada iteración. Esto evita que una única construcción fallida consuma todo el presupuesto disponible. También se mantiene un número máximo reducido de intentos constructivos por iteración (`constructive_max_attempts = 5`) para favorecer más reinicios y aumentar la robustez del algoritmo.

---

## 7. Relación con el Pareto externo

El GRASP se integrará con el Pareto externo ya existente en el proyecto. En cada iteración se registrará solo la solución final mejorada, es decir, la solución obtenida tras aplicar la búsqueda local sobre la construcción inicial.

Esta decisión se toma porque, aunque registrar también la solución construida permitiría analizar con más detalle el efecto de la búsqueda local, hacerlo implicaría un coste adicional de evaluación y actualización del Pareto en cada iteración. En este caso, ese coste extra no compensa suficientemente el beneficio analítico.

La gestión del Pareto no se implementará dentro de `grasp.py`, sino que reutilizará las utilidades comunes ya existentes para registrar soluciones evaluadas y actualizar el conjunto no dominado.

---

## 8. Reutilización de `_assign_professors_with_repair`

La asignación de profesores no formará parte del constructivo principal ni del vecindario de búsqueda local. Una vez construida o modificada una asignación `student_to_placement`, se reconstruirá la parte `placement_to_professor` reutilizando la función `_assign_professors_with_repair`, definida en `random_feasible_fixing.py` y ya utilizada en otros módulos del proyecto.

Esta decisión permite evitar la duplicidad de la lógica ya validada, mantener consistencia con el resto del código sin depender de implementaciones específicas de otras heurísticas como NSGA-III, y asegurar que las soluciones finales puedan evaluarse correctamente con los cuatro objetivos del modelo.

---

## 9. Papel de esta heurística dentro del proyecto

Este GRASP es una baseline constructiva con mejora local, situada entre la baseline puramente aleatoria y metaheurísticas más elaboradas como NSGA-III. Su finalidad no es agotar el potencial del problema, sino proporcionar una referencia más fuerte que la aleatoria, pero todavía suficientemente simple, interpretable y mantenible.

En esta baseline no se incorporarán mecanismos adicionales de intensificación o sofisticación, como path relinking, búsqueda local multi-vecindad (VND) o CMSA. Aunque estas extensiones pueden mejorar el rendimiento, también aumentan de forma notable la complejidad del algoritmo y lo alejan del papel de referencia simple y comparativa que debe cumplir esta heurística dentro del proyecto.

En las instancias de mayor tamaño, el uso del fallback factible se entiende como una medida de robustez computacional propia de una baseline experimental. Su finalidad es evitar resultados vacíos por fallo del constructivo, no mejorar artificialmente la comparación. Todas las soluciones, tanto si proceden del constructivo GRASP como del fallback, pasan por la misma búsqueda local, validación y registro en Pareto externo.

Por ello, el número de veces que se activa el fallback (`fallback_used`) se registra como estadística de ejecución, permitiendo interpretar correctamente el comportamiento del algoritmo en función del tamaño y dificultad de cada instancia.