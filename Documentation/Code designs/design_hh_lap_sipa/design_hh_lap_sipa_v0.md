# Diseño conceptual del HH-LAP-SIPA v0 (Heurística Híbrida con LAP para el modelo SIPA extendido)

## 1. Objetivo del documento

Este documento define el diseño de la heurística híbrida con LAP propuesta, la cual se basa en el siguiente esquema conceptual:

```text
Selección aleatoria factible de prácticas P'
        ↓
Asignación práctica-profesor mediante construcción guiada
        ↓
Resolución LAP estudiante-práctica maximizando tau
        ↓
Solución orientada a estudiantes

Resolución LAP estudiante-práctica maximizando eta
        ↓
Solución orientada a empresas

Evaluación multiobjetivo
        ↓
Actualización del Pareto externo
```

---

## 2. Objetivo del algoritmo

El objetivo del algoritmo es buscar soluciones factibles y de alta calidad para el modelo SIPA extendido, considerando simultáneamente los intereses de estudiantes, empresas, profesores y centros educativos. En particular, aunque la selección inicial de prácticas y la asignación de profesores se abordan mediante procedimientos heurísticos, la asignación estudiante-práctica se resuelve de forma exacta para cada subconjunto factible de prácticas \(P'\). Esto significa que la heurística no garantiza optimalidad global sobre todo el espacio de soluciones del modelo extendido, pero sí incorpora optimalidad local en los subproblemas LAP que resuelve en cada iteración.

Para ello, combina:

- Selección aleatoria factible de subconjuntos de prácticas.
- Asignación práctica-profesor mediante construcción guiada.
- Resolución exacta de subproblemas de asignación estudiante-práctica.
- Evaluación multiobjetivo.
- Mantenimiento de una frontera de Pareto con soluciones no dominadas.

En lugar de construir directamente una solución completa `x_ijt`, la heurística divide el proceso en tres capas:

```text
Capa 1: selección de prácticas P'
Capa 2: asignación práctica-profesor
Capa 3: asignación estudiante-práctica
```

La primera capa genera un subconjunto `P'` de prácticas de forma aleatoria, pero siempre respetando las restricciones estructurales del problema. La segunda capa asigna profesores a las prácticas seleccionadas mediante una estrategia de construcción guiada (no se resuelve mediante LAP, ya que un profesor puede supervisar varias prácticas y su coste depende del conjunto completo de prácticas asignadas). La tercera capa resuelve la asignación estudiante-práctica mediante dos problemas LAP usando `lapjv`:

- Un LAP maximizando `tau`, que genera una solución orientada a estudiantes.
- Un LAP maximizando `eta`, que genera una solución orientada a empresas.

Para cada subconjunto `P'`, la asignación práctica-profesor se calcula una única vez y se combina con cada una de las asignaciones estudiante-práctica devueltas por `lapjv`. Así se obtienen dos soluciones completas: `Solución_tau` y `Solución_eta`.

Ambas soluciones se validan frente a las restricciones del modelo y se evalúan con los cuatro objetivos. Si son factibles y no están dominadas, se incorporan al Pareto externo.

---

## 3. Selección inicial de prácticas \(P'\)

La selección inicial de prácticas no busca elegir directamente las "mejores" prácticas, ya que la calidad de una práctica depende del estudiante y del profesor al que se asigne. En particular, las utilidades `tau_ij` y `eta_ij` dependen del par estudiante-práctica, no de la práctica de forma aislada; del mismo modo, los componentes `lbar_sum` y `sigma_sum` dependen de cómo se asignan las prácticas a los profesores.

Por tanto, en esta fase no se pretende optimizar directamente la calidad final de las prácticas seleccionadas, sino generar un subconjunto `P'` que sea factible desde el punto de vista estructural.

Además, el subconjunto `P'` debe cumplir que \(|P'| = |S|\), de forma que pueda construirse una asignación uno-a-uno entre estudiantes y prácticas. Asimismo, debe respetar las restricciones estructurales del problema asociadas a cuotas de empresa y dependencias entre prácticas.

La calidad real de `P'` se determina posteriormente, al combinar dicho subconjunto con una asignación práctica-profesor, resolver los LAP estudiante-práctica y evaluar las soluciones completas resultantes.

---

## 4. Asignación práctica-profesor

Una vez seleccionado el subconjunto de prácticas `P'`, se debe asignar un profesor a cada práctica seleccionada. Esta fase no se resolverá mediante LAP, ya que la asignación profesor-práctica no es un problema uno-a-uno (un profesor puede supervisar varias prácticas, tiene una capacidad máxima `C_t`, y el coste de supervisión depende del conjunto completo de prácticas que se le asignan). Por tanto, la asignación práctica-profesor se abordará mediante una estrategia heurística de construcción guiada.

El aspecto importante de esta fase es que la asignación de profesores no depende del estudiante concreto que ocupe cada práctica, ya que para el profesorado importa qué prácticas están cubiertas, dónde están ubicadas, cuántas prácticas supervisa cada profesor, qué dispersión geográfica tiene su conjunto de prácticas y cómo queda equilibrada la carga entre profesores. En cambio, no importa qué alumno concreto está asignado a cada práctica.

Por este motivo, para un mismo subconjunto `P'`, la asignación práctica-profesor se calcula una única vez y se reutiliza en las dos soluciones generadas posteriormente mediante LAP: `Solución_tau` y `Solución_eta`.

Dado `P'`, la estrategia inicial será:

1. Inicializar todos los profesores sin prácticas asignadas.
2. Recorrer las prácticas seleccionadas.
3. Para cada práctica:
      - Buscar profesores con capacidad disponible.
      - Estimar el incremento de coste si se asigna a cada profesor.
      - Asignar la práctica al profesor con menor incremento.
4. Si no se puede completar una asignación factible, descartar el subconjunto `P'` y continuar con la siguiente iteración.
5. Validar que todas las prácticas seleccionadas tengan profesor y que ningún profesor supere su capacidad.

El coste incremental podrá tener en cuenta el aumento de `lbar_sum` y una penalización asociada al desequilibrio de carga `sigma_sum`. En cualquier caso, la asignación resultante deberá garantizar siempre la factibilidad respecto a la capacidad máxima de supervisión de los profesores.

---

## 5. Asignación estudiante-práctica mediante LAP

Una vez fijado el subconjunto de prácticas `P'`, la asignación estudiante-práctica se convierte en un problema de asignación lineal uno-a-uno. Esto es posible porque la selección inicial de prácticas fuerza que `|P'| = |S|`, de modo que existe el mismo número de prácticas seleccionadas que de estudiantes.

Sobre este conjunto `P'`, se construyen dos matrices de beneficio: Tau[i][j] = tau_ij, Eta[i][j] = eta_ij; donde `i` representa un estudiante y `j` una práctica perteneciente a `P'`. A partir de estas matrices se resuelven dos problemas LAP independientes mediante `lapjv`:

- Un LAP maximizando `tau`, que obtiene la asignación estudiante-práctica óptima desde el punto de vista de los estudiantes.
- Un LAP maximizando `eta`, que obtiene la asignación estudiante-práctica óptima desde el punto de vista de las empresas/prácticas.

Cada una de estas asignaciones se combina con la asignación práctica-profesor calculada previamente para `P'`. De este modo, para cada subconjunto `P'` se generan dos soluciones completas:

```text
Solución_tau = P' + asignación práctica-profesor + asignación estudiante-práctica max tau
Solución_eta = P' + asignación práctica-profesor + asignación estudiante-práctica max eta
```

Ambas soluciones comparten el mismo subconjunto de prácticas seleccionadas y la misma asignación de profesores, pero difieren en la asignación estudiante-práctica devuelta por `lapjv`.

---

## 6. Uso del LAP en la heurística

La heurística utiliza problemas LAP para resolver de forma exacta la asignación estudiante-práctica una vez fijado el subconjunto de prácticas `P'`. El solver principal será `lapjv`, ya que el repositorio `src-d/lapjv` (https://github.com/src-d/lapjv) implementa un solver del Linear Assignment Problem basado en el algoritmo Jonker-Volgenant.

Además, el repositorio comparativo `berhane/LAP-solvers` (https://github.com/berhane/LAP-solvers) se utilizará como referencia para justificar la elección de `lapjv`, ya que compara distintas implementaciones para resolver problemas LAP y señala esta alternativa como una de las más eficientes.

No obstante, se contempla mantener una alternativa basada en `scipy.optimize.linear_sum_assignment` en caso de que `lapjv` presente problemas de instalación, configuración o compatibilidad en el entorno de ejecución.

Desde el punto de vista del algoritmo, los dos LAP que se resuelven son problemas de maximización (de `tau` y `eta`). Sin embargo, muchos solvers LAP están formulados como problemas de minimización. Por ello, la maximización se transforma en minimización cambiando el signo de la matriz de beneficios:

```python
cost_tau = -tau_matrix # maximizar tau equivale a minimizar -tau
row_ind, col_ind, _ = lapjv(cost_tau)

cost_eta = -eta_matrix # maximizar eta equivale a minimizar -eta
row_ind, col_ind, _ = lapjv(cost_eta)
```

Por tanto, `lapjv` se usará como subrutina exacta para resolver la asignación estudiante-práctica dentro de la heurística, mientras que el resto de decisiones del problema, como la selección de prácticas y la asignación práctica-profesor, se resolverán mediante procedimientos heurísticos.

---

## 7. Flujo completo de la heurística

El flujo completo de la heurística se resume en el siguiente pseudocódigo:

```text
HH-LAP-SIPA(problem, time_limit, max_iterations, base_seed):

    pareto_set ← ∅

    while not stopping_condition:

        P' ← generate_random_feasible_placements(problem)

        professor_assignment ← assign_professors_with_guided_construction(problem, P')
        if professor_assignment is not feasible:
            continue

        tau_matrix ← build_tau_matrix(problem, P')
        assignment_tau ← solve_lapjv_max(tau_matrix)
        sol_tau ← build_solution(P', professor_assignment, assignment_tau)
        if validate(sol_tau):
            evaluate_and_update_pareto(pareto_set, sol_tau)

        eta_matrix ← build_eta_matrix(problem, P')
        assignment_eta ← solve_lapjv_max(eta_matrix)
        sol_eta ← build_solution(P', professor_assignment, assignment_eta)
        if validate(sol_eta):
            evaluate_and_update_pareto(pareto_set, sol_eta)

    return pareto_set
```

El criterio de parada principal será el tiempo de ejecución, fijado inicialmente en 300 segundos para los experimentos comparativos. Este criterio permite comparar HH-LAP-SIPA con otras heurísticas bajo las mismas condiciones computacionales. Adicionalmente, la implementación podrá contemplar otros criterios, como número máximo de iteraciones, número de subconjuntos generados o número de soluciones factibles evaluadas.

En cada iteración, el algoritmo genera un subconjunto factible de prácticas, calcula una asignación práctica-profesor y construye dos soluciones candidatas mediante LAP: una optimizando `tau` y otra optimizando `eta`. Cada solución se valida frente a las restricciones del modelo SIPA extendido antes de poder incorporarse al Pareto externo.

---

## 8. Relación con el código actual

La implementación de la heurística se apoyará en las estructuras ya existentes del proyecto. En particular:

- `Problem`: representación de la instancia del problema.
- `Solution`: representación de una solución completa.
- `evaluate_solution_multi`: evaluación multiobjetivo de una solución.
- `evaluate_solution_scalar`: evaluación escalar auxiliar.
- `register_solution_in_pareto`: evaluación, validación y registro de soluciones en el Pareto externo.

La principal adaptación será separar la lógica actual de generación de soluciones factibles. En lugar de generar directamente una solución completa, la nueva heurística deberá generar primero un subconjunto factible de prácticas `P'`, asignar profesores a dichas prácticas y, posteriormente, delegar la asignación estudiante-práctica en `lapjv`.

Para ello, se prevé incorporar o adaptar los siguientes componentes:

- `generate_random_feasible_placements(problem)`: genera un subconjunto factible de prácticas `P'`.
- `assign_professors_with_guided_construction(problem, selected_placements)`: asigna profesores a las prácticas seleccionadas mediante construcción guiada.
- `build_tau_matrix(problem, selected_placements)`: construye la matriz de beneficios `tau` para el LAP orientado a estudiantes.
- `build_eta_matrix(problem, selected_placements)`: construye la matriz de beneficios `eta` para el LAP orientado a empresas.
- `solve_lapjv_max(matrix)`: resuelve un problema LAP de maximización usando `lapjv`.
- `build_solution_from_lap_assignment(...)`: construye una solución completa combinando `P'`, la asignación práctica-profesor y la asignación estudiante-práctica devuelta por `lapjv`.
- `hh_lap_sipa.py`: contiene la implementación principal del algoritmo HH-LAP-SIPA.
- `run_hh_lap_sipa.py`: script de ejecución encargado de cargar la instancia, configurar parámetros, lanzar la heurística y guardar/mostrar resultados.

El objetivo es aprovechar la infraestructura existente, pero modificando el flujo de construcción de soluciones para que el LAP sea quien determine la asignación estudiante-práctica dentro de cada subconjunto `P'`.

---

## 9. Diferencias respecto a la baseline aleatoria

La baseline aleatoria actual construye soluciones generando una selección factible de prácticas y asignando posteriormente estudiantes y profesores mediante procedimientos aleatorios o de reparación. La heurística HH-LAP-SIPA mantiene la selección inicial aleatoria factible de prácticas, pero modifica la forma de construir la solución completa. En concreto:

- La asignación práctica-profesor se realiza mediante construcción guiada.
- La asignación estudiante-práctica deja de ser aleatoria y se resuelve de forma exacta mediante LAP.
- Para cada subconjunto `P'`, se generan dos soluciones candidatas: una maximizando `tau` y otra maximizando `eta`.

---

## 10. Salidas esperadas

La heurística devolverá como resultado principal el conjunto de soluciones no dominadas encontrado durante la ejecución, junto con estadísticas asociadas:

- `pareto_set` (assignments): conjunto Pareto externo con las soluciones no dominadas.
- `stats` (statistics): estadísticas de ejecución de la heurística.

Las estadísticas mínimas que se registrarán serán:

- `iterations`: número de iteraciones ejecutadas.
- `generated_subsets`: número de subconjuntos `P'` generados.
- `professor_assignment_failures`: número de fallos al construir la asignación práctica-profesor.
- `lap_tau_solutions`: número de soluciones generadas mediante el LAP que maximiza `tau`.
- `lap_eta_solutions`: número de soluciones generadas mediante el LAP que maximiza `eta`.
- `feasible_solutions`: número de soluciones factibles evaluadas.
- `inserted_into_pareto`: número de soluciones incorporadas al Pareto externo.
- `pareto_size`: tamaño final del Pareto externo.
- `elapsed_seconds`: tiempo total de ejecución.

Además, se podrá guardar un resumen del Pareto final con indicadores agregados de calidad, como máximos o medias de los objetivos considerados.

---

## 11. Decisiones de diseño fijadas

Las decisiones de diseño fijadas para la (primera) definición del algoritmo HH-LAP-SIPA son:

- La selección inicial de prácticas `P'` será aleatoria factible.
- La asignación práctica-profesor no se resolverá mediante LAP.
- La asignación práctica-profesor se realizará mediante construcción guiada.
- La asignación estudiante-práctica sí se resolverá mediante LAP.
- El solver LAP principal será `lapjv`.
- Para cada subconjunto `P'`, se resolverán exactamente dos LAP:
  - uno maximizando `tau`;
  - otro maximizando `eta`.
- No se usarán combinaciones ponderadas de `tau` y `eta`.
- Cada subconjunto `P'` generará como máximo dos soluciones completas:
  - `Solución_tau`: combinación de `P'`, la asignación práctica-profesor y la asignación estudiante-práctica devuelta por `lapjv` al maximizar `tau`.
  - `Solución_eta`: combinación de `P'`, la asignación práctica-profesor y la asignación estudiante-práctica devuelta por `lapjv` al maximizar `eta`.
- Las dos soluciones comparten el mismo subconjunto `P'` y la misma asignación práctica-profesor.
- Las dos soluciones difieren en la asignación estudiante-práctica devuelta por `lapjv`.
- Toda solución debe cumplir las restricciones del modelo SIPA extendido antes de evaluarse.
- El Pareto externo se actualiza únicamente con soluciones válidas y no dominadas.

---

## 12. Posibles mejoras futuras

Quedan identificadas varias extensiones posibles:

- Selección guiada de prácticas: en lugar de seleccionar `P'` de forma aleatoria, se podría sesgar la selección usando una puntuación aproximada del potencial de cada práctica, por ejemplo combinando su mejor ajuste posible respecto a `tau` y `eta`.

- Búsqueda local sobre `P'`: una vez generado un subconjunto de prácticas, se podrían aplicar movimientos como eliminar una práctica, añadir otra, intercambiar prácticas o reparar cuotas y dependencias. Tras cada modificación, se resolverían de nuevo los LAP y se conservaría la solución si mejora el Pareto.

- Repair de la asignación práctica-profesor: si en versiones futuras se incorporan restricciones adicionales sobre qué profesores pueden supervisar determinadas prácticas, o si la construcción guiada empieza a descartar demasiados subconjuntos `P'`, se podría añadir una fase de repair que intente recolocar prácticas entre profesores para completar una asignación factible antes de descartar el subconjunto.

- Mejora local de profesores: después de la construcción inicial de profesores, se podrían probar movimientos como mover una práctica de un profesor a otro o intercambiar prácticas entre profesores, con el objetivo de reducir `lbar_sum` y `sigma_sum`.