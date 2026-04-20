# Diseño conceptual del GRASP

## 1. Objetivo del algoritmo

El objetivo de esta heurística GRASP es generar una **baseline multiobjetivo** para el problema SIPA modificado, de forma que pueda compararse posteriormente con metaheurísticas más elaboradas o con una heurística propia diseñada específicamente para el problema.

Esta baseline debe cumplir cuatro condiciones:

- generar soluciones factibles de forma estable;
- incorporar una construcción más informada que la búsqueda aleatoria;
- incluir una mejora local sencilla pero real;
- integrarse con el Pareto externo ya existente en el proyecto.

Por tanto, este GRASP no se plantea como una heurística excesivamente sofisticada ni específica, sino como una referencia sólida, coherente y reutilizable dentro de la arquitectura actual del proyecto.

---

## 2. Representación de la solución

La representación principal de la solución será:

- `student_to_placement`

Es decir, durante la construcción y la búsqueda local, la heurística trabajará únicamente con la asignación de cada estudiante a una plaza.

No se utilizará una representación completa del tipo `xijt`, ya que introducir simultáneamente la asignación estudiante–plaza–profesor aumentaría mucho la complejidad del algoritmo y no resulta necesario para una baseline.

La asignación de profesores se reconstruirá después, una vez fijada la asignación estudiante–plaza, reutilizando el mecanismo ya disponible en el proyecto.

Esta decisión mantiene coherencia con el diseño seguido hasta ahora y permite aprovechar la infraestructura existente sin duplicar lógica.

---

## 3. Fase constructiva

La fase constructiva seguirá un esquema **greedy-randomized sobre asignaciones estudiante–plaza**.

La idea general será construir una solución de forma incremental. En cada paso, se seleccionará una asignación factible estudiante–plaza entre un conjunto de candidatas bien valoradas según una función greedy, introduciendo aleatoriedad controlada mediante una RCL.

La construcción trabajará únicamente sobre la parte `student_to_placement`. Una vez completada la asignación de todos los estudiantes a plazas, se reconstruirá la asignación de profesores.

### 3.1. Criterio greedy

La puntuación greedy de una asignación candidata `(i, j)` se basará únicamente en la utilidad local estudiante–plaza y empresa–estudiante, es decir, en la parte del modelo relacionada con:

- `tau`
- `eta`

De forma conceptual, la construcción favorecerá asignaciones que:

- sean buenas para el estudiante;
- sean buenas para la empresa;
- y no comprometan la factibilidad estructural.

### 3.2. Definición del score greedy

Para cada asignación candidata `(i, j)`, se definirá un score greedy local:

`g(i,j) = lambda_tau * tau_ij + lambda_eta * eta_ij`

donde `tau_ij` representa la utilidad de la plaza `j` para el estudiante `i`, y `eta_ij` representa la utilidad del estudiante `i` para la plaza o empresa asociada a `j`.

Para esta baseline se fija:

- `lambda_tau = 0.5`
- `lambda_eta = 0.5`

Esta elección da el mismo peso a la perspectiva del estudiante y a la de la empresa, manteniendo una construcción equilibrada y fácil de justificar.

El score greedy se utilizará únicamente para ordenar candidatas factibles dentro del proceso constructivo. Las restricciones estructurales del problema no se incorporarán como términos adicionales del score, sino como condiciones de factibilidad que una candidata debe respetar para poder ser considerada.

### 3.3. Exclusión de `lbar` y `sigma`

En esta fase constructiva **no se usarán `lbar` ni `sigma`** en la función greedy.

La razón es que ambos componentes dependen de la asignación de profesores y de la estructura global de supervisión, no de una decisión local aislada estudiante–plaza. Introducirlos en la fase constructiva obligaría a estimar continuamente efectos indirectos y globales que aún no están definidos en ese momento de la construcción.

Eso tendría tres consecuencias no deseables para una baseline:

- complicaría mucho el diseño del score greedy;
- encarecería el coste de construcción;
- y mezclaría demasiado pronto la capa de supervisión con la capa principal de asignación.

Por tanto, la construcción se centrará en `tau` y `eta`, mientras que `lbar` y `sigma` quedarán incorporados después en la **evaluación completa de la solución**, una vez reconstruida la asignación de profesores.

Esta separación es más limpia, más estable y más adecuada para una baseline.

### 3.4. Control de factibilidad

Durante la fase constructiva se aplicará un control de factibilidad en dos niveles:

1. **Filtro local de factibilidad**  
   Solo se considerarán asignaciones `(i,j)` que no violen restricciones básicas inmediatas, como:
   - asignación única de plaza;
   - no superar el máximo de una empresa;
   - consistencia con dependencias ya parcialmente activadas.

2. **Validación y reconstrucción final**  
   Una vez completada la asignación `student_to_placement`, se reconstruirá la solución completa (incluyendo profesores) y se validará globalmente.

Este enfoque permite mantener la construcción eficiente sin necesidad de garantizar factibilidad completa en cada paso, delegando la validación final en los mecanismos ya existentes del proyecto.

---

## 4. Definición de la RCL

La Restricted Candidate List (RCL) se construirá a partir de las mejores asignaciones candidatas disponibles en cada paso de la construcción.

El procedimiento será:

1. generar el conjunto de movimientos factibles estudiante–plaza;
2. calcular para cada uno su puntuación greedy;
3. seleccionar las candidatas cuya puntuación supere un umbral relativo respecto a la mejor;
4. elegir aleatoriamente una candidata dentro de esa RCL.

La RCL introduce diversidad en las soluciones generadas y evita que el constructivo sea completamente determinista.

Para esta baseline, se usará una **RCL por umbral relativo**, ya que es una opción clásica en GRASP y se adapta mejor a instancias de distinto tamaño o escala que una RCL de tamaño fijo.

### 4.1. Parámetro de la RCL

La RCL se definirá mediante un umbral relativo controlado por un parámetro `alpha_rcl ∈ [0,1]`.

Sea:

- `g_max` la mejor puntuación greedy disponible en el conjunto de candidatas;
- `g_min` la peor puntuación;

Se incluirán en la RCL todas las candidatas que cumplan:

`g(i,j) >= g_max - alpha_rcl * (g_max - g_min)`

Para esta baseline se fija:

- `alpha_rcl = 0.3`

Este valor introduce un nivel moderado de aleatoriedad, manteniendo un equilibrio entre exploración y explotación.

---

## 5. Búsqueda local

La búsqueda local se definirá mediante un único vecindario:

- **swap entre dos estudiantes**

Esto significa que, a partir de una solución construida, se explorarán vecinos generados al intercambiar las plazas asignadas a dos estudiantes.

Esta decisión se adopta como **definitiva** para la baseline.

### Justificación

Este vecindario es adecuado porque:

- es sencillo de implementar;
- mantiene una estructura muy controlada;
- permite mejorar la asignación sin rediseñar por completo la solución;
- y ofrece una mejora local real frente al simple constructivo.

Aunque existen vecindarios más potentes, también son bastante más complejos y específicos del problema. Para una baseline, no compensa aumentar tanto la complejidad.

### Aceptación de vecinos

La búsqueda local aceptará un vecino cuando:

- la solución resultante siga siendo válida;
- y mejore el valor escalar auxiliar de la evaluación.

Es decir, la mejora local usará una guía monobjetivo auxiliar para decidir avances, mientras que la calidad final del algoritmo seguirá midiéndose mediante Pareto externo multiobjetivo.

Esta combinación es razonable porque simplifica mucho la búsqueda local sin romper el enfoque multiobjetivo general del proyecto.

### Estrategia de exploración

La exploración del vecindario se realizará mediante una estrategia de **first improvement**.

Esto implica que, en cada iteración de la búsqueda local:

- se recorren vecinos generados mediante swaps;
- se acepta el primer vecino que mejora la solución actual;
- y se continúa desde esa nueva solución.

Esta elección reduce el coste computacional respecto a una estrategia de *best improvement*, manteniendo una mejora efectiva suficiente para una baseline.

---

## 6. Criterio de parada

El GRASP iterará con el esquema:

- construcción;
- mejora local;
- registro en Pareto;

hasta alcanzar un criterio de parada.

El criterio principal de parada será **límite de tiempo**, para mantener coherencia con el resto de heurísticas ya implementadas en el proyecto.

Opcionalmente, también podrá admitirse un límite máximo de iteraciones como criterio secundario.

Por tanto, el comportamiento general será:

- parar por tiempo;
- o antes si se alcanza un máximo de iteraciones definido explícitamente.

---

## 7. Relación con el Pareto externo

El GRASP se integrará con el Pareto externo ya existente en el proyecto.

En cada iteración se registrará **solo la solución final mejorada**, es decir, la solución obtenida tras aplicar la búsqueda local sobre la construcción inicial.

Esta decisión se toma porque, aunque registrar también la solución construida permitiría analizar con más detalle el efecto de la búsqueda local, hacerlo implicaría un coste adicional de evaluación y actualización del Pareto en cada iteración. En esta baseline, ese coste extra no compensa suficientemente el beneficio analítico.

Por tanto, la solución representativa de cada iteración será la solución final del GRASP, que es la que realmente debe compararse frente al resto de heurísticas del proyecto.

La gestión del Pareto no se implementará dentro de `grasp.py`, sino que reutilizará las utilidades comunes ya existentes para registrar soluciones evaluadas y actualizar el conjunto no dominado.

---

## 8. Reutilización de `_assign_professors_with_repair` o equivalente

La asignación de profesores **no formará parte del constructivo principal** ni del vecindario de búsqueda local.

Una vez construida o modificada una asignación `student_to_placement`, se reconstruirá la parte `placement_to_professor` reutilizando `_assign_professors_with_repair` o una función equivalente ya existente en el proyecto.

Esta decisión permite:

- separar claramente la asignación principal de la capa de supervisión;
- evitar duplicación de lógica;
- mantener consistencia con el resto del código;
- y asegurar que las soluciones finales puedan evaluarse con los cuatro objetivos del modelo.

---

## 9. Papel de esta heurística dentro del proyecto

Este GRASP debe entenderse como una **baseline constructiva con mejora local**, situada entre:

- la baseline puramente aleatoria;
- y metaheurísticas más elaboradas como NSGA-III o una futura heurística propia.

Su finalidad no es agotar el potencial del problema, sino proporcionar una referencia más fuerte que la aleatoria, pero todavía suficientemente simple, interpretable y mantenible.

Por ello, las decisiones de diseño priorizan:

- claridad;
- modularidad;
- reutilización del código existente;
- y equilibrio entre calidad y simplicidad.

En esta baseline no se incorporarán mecanismos adicionales de intensificación o sofisticación, como path relinking, búsqueda local multi-vecindad (VND) o CMSA. Aunque estas extensiones pueden mejorar el rendimiento, también aumentan de forma notable la complejidad del algoritmo y lo alejan del papel de referencia simple y comparativa que debe cumplir esta heurística dentro del proyecto.

---

## 10. Estructura prevista de implementación

La implementación asociada a este diseño se organizará, como mínimo, en:

- `grasp.py`: lógica del algoritmo GRASP;
- `run_grasp.py`: script lanzador;
- reutilización de `multiobjective_search.py` para el registro en Pareto;
- reutilización de `_assign_professors_with_repair` para completar soluciones.

No se prevén modificaciones obligatorias en `multiobjective_search.py` para esta primera versión, salvo que más adelante se quiera factorizar lógica adicional común a varias metaheurísticas iterativas.