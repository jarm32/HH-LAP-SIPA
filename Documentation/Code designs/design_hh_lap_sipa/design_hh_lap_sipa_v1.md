# Diseño conceptual del HH-LAP-SIPA v1 (Heurística Híbrida con LAP, cargas objetivo, clústeres y path relinking para el modelo SIPA extendido)

## 1. Objetivo del documento

Este documento define el diseño de la versión v1 de la heurística híbrida con LAP propuesta para el modelo SIPA extendido. Esta mantiene la estructura general de la v0, pero modifica la capa de asignación práctica-profesor.

El objetivo principal de esta nueva versión es mejorar la calidad de las soluciones en los componentes asociados a profesores y centros educativos, especialmente la dispersión geográfica de supervisión (`lbar_sum`) y el equilibrio de carga entre profesores (`sigma_sum`). Para ello, la versión v1 incorpora las siguientes ideas adicionales:

- Cálculo previo de una carga objetivo para cada profesor.
- Preclusterización espacial de las prácticas y uso, en cada iteración, de los clústeres correspondientes a las prácticas seleccionadas.
- Construcción de una asignación profesor-práctica basada en clústeres.
- Construcción de una asignación guía orientada a las cargas objetivo de los profesores.
- Path relinking entre la asignación inicial y la asignación guía.
- Evaluación de las soluciones intermedias generadas durante el path relinking.

El esquema conceptual de HH-LAP-SIPA v1 es:

```text
Cálculo previo de cargas objetivo por profesor
        ↓
Preclusterización espacial de prácticas
        ↓
Selección aleatoria factible de prácticas P'
        ↓
Extracción de clústeres activos dentro de P'
        ↓
Asignación práctica-profesor por clústeres
        ↓
Construcción de asignación guía orientada a cargas objetivo
        ↓
Path relinking entre asignaciones profesor-práctica
        ↓
Resolución LAP estudiante-práctica maximizando tau
        ↓
Soluciones orientadas a estudiantes para cada asignación profesor-práctica generada

Resolución LAP estudiante-práctica maximizando eta
        ↓
Soluciones orientadas a empresas para cada asignación profesor-práctica generada

Evaluación multiobjetivo
        ↓
Actualización del Pareto externo
```

---

## 2. Objetivo del algoritmo

El objetivo del algoritmo es buscar soluciones factibles y de alta calidad para el modelo SIPA extendido, considerando simultáneamente los intereses de estudiantes, empresas, profesores y centros educativos. En particular, aunque la selección inicial de prácticas y la asignación de profesores se abordan mediante procedimientos heurísticos, la asignación estudiante-práctica se resuelve de forma exacta para cada subconjunto factible de prácticas \(P'\). Esto significa que la heurística no garantiza optimalidad global sobre todo el espacio de soluciones del modelo extendido, pero sí incorpora optimalidad local en los subproblemas LAP que resuelve en cada iteración.

Para ello, combina:

- Selección aleatoria factible de subconjuntos de prácticas.
- Cálculo previo de cargas objetivo para los profesores.
- Preclusterización espacial de prácticas y extracción de los clústeres activos para cada subconjunto `P'`.
- Asignación práctica-profesor mediante construcción guiada por clústeres.
- Generación de asignaciones profesor-práctica alternativas mediante path relinking.
- Resolución exacta de subproblemas de asignación estudiante-práctica.
- Evaluación multiobjetivo.
- Mantenimiento de una frontera de Pareto con soluciones no dominadas.

En lugar de construir directamente una solución completa `x_ijt`, la heurística divide el proceso en tres capas:

```text
Capa 1: selección de prácticas P'
Capa 2: asignación práctica-profesor
Capa 3: asignación estudiante-práctica
```

La primera capa genera un subconjunto `P'` de prácticas de forma aleatoria, pero siempre respetando las restricciones estructurales del problema. La segunda capa asigna profesores a las prácticas seleccionadas mediante una estrategia más elaborada que en v0: primero se construye una asignación orientada a clústeres, después se construye una asignación guía orientada a cargas objetivo y finalmente se exploran asignaciones intermedias mediante path relinking. La tercera capa resuelve la asignación estudiante-práctica sobre `P'` mediante dos problemas LAP usando `lapjv`:

- Un LAP maximizando `tau`, que genera una asignación orientada a estudiantes.
- Un LAP maximizando `eta`, que genera una asignación orientada a empresas.

Para cada subconjunto `P'`, los dos LAP se resuelven una sola vez. Sus resultados se combinan con cada una de las asignaciones profesor-práctica generadas durante el path relinking. Así, a diferencia de la v0, cada subconjunto `P'` puede producir más de dos soluciones completas.

Las soluciones se validan frente a las restricciones del modelo y se evalúan con los cuatro objetivos. Si son factibles y no están dominadas, se incorporan al Pareto externo.

---

## 3. Selección inicial de prácticas \(P'\)

La selección inicial de prácticas no busca elegir directamente las "mejores" prácticas, ya que la calidad de una práctica depende del estudiante y del profesor al que se asigne. En particular, las utilidades `tau_ij` y `eta_ij` dependen del par estudiante-práctica, no de la práctica de forma aislada; del mismo modo, los componentes `lbar_sum` y `sigma_sum` dependen de cómo se asignan las prácticas a los profesores.

Por tanto, en esta fase no se pretende optimizar directamente la calidad final de las prácticas seleccionadas, sino generar un subconjunto `P'` que sea factible desde el punto de vista estructural.

Además, el subconjunto `P'` debe cumplir que \(|P'| = |S|\), de forma que pueda construirse una asignación uno-a-uno entre estudiantes y prácticas. Asimismo, debe respetar las restricciones estructurales del problema asociadas a cuotas de empresa y dependencias entre prácticas.

La calidad real de `P'` se determina posteriormente, al combinar dicho subconjunto con una asignación práctica-profesor, resolver los LAP estudiante-práctica y evaluar las soluciones completas resultantes.

---

## 4. Cálculo previo de cargas objetivo por profesor

Antes del bucle principal, la heurística v1 calcula una carga objetivo para cada profesor. Esta carga representa cuántas prácticas debería supervisar idealmente cada profesor si el trabajo se reparte de forma proporcional a su capacidad máxima.

Sea:

- `S`: conjunto de estudiantes.
- `T`: conjunto de profesores.
- `M_k`: capacidad máxima del profesor `k`.
- `A_k`: carga objetivo del profesor `k`.

La carga ideal proporcional se define como:

```text
A_k* = (M_k · |S|) / sum(M_h), para todo h en T
```

Como la carga final debe ser entera, se construye un vector entero `A_k` que cumpla:

```text
0 <= A_k <= M_k, para todo k en T
sum(A_k) = |S|
```

Conceptualmente, este cálculo puede interpretarse como un pequeño modelo auxiliar de reparto justo de carga entre profesores, cuyo objetivo es minimizar la desviación respecto a la carga proporcional ideal:

```text
min Z = sum(N_k + P_k), con k en T
```

sujeto a:

```text
m_k <= A_k <= M_k, para todo k en T

A_k + N_k - P_k = (M_k · |S|) / sum(M_h), con h en T y para todo k en T

sum(A_k) = |S|, sumando para todo k en T
```

Donde:

- `N_k`: variable de holgura negativa del profesor `k`.
- `P_k`: variable de holgura positiva del profesor `k`.
- `m_k`: mínimo número de prácticas deseado para el profesor `k`.

En la primera implementación de v1 no es necesario resolver este modelo con un solver exacto. Se utilizará como inspiración conceptual y se implementará mediante una función determinista de reparto proporcional entero. En ausencia de cotas mínimas explícitas por profesor, se tomará `m_k = 0`.

El reparto proporcional entero se calcula de la siguiente forma:

1. Calcular `A_k*` para cada profesor.
2. Asignar inicialmente `A_k = floor(A_k*)`.
3. Calcular cuántas prácticas faltan para llegar a `|S|`.
4. Repartir las prácticas restantes entre los profesores con mayor parte decimal pendiente.
5. No permitir que ningún profesor supere su capacidad máxima `M_k`.

Este cálculo solo debe ejecutarse una vez al principio, ya que depende únicamente del número total de estudiantes y de las capacidades máximas de los profesores. No depende del subconjunto concreto de prácticas seleccionado en cada iteración.

La finalidad de estas cargas objetivo es guiar la asignación profesor-práctica hacia una distribución más equilibrada, reduciendo el componente `sigma_sum` de la evaluación multiobjetivo.

---

## 5. Preclusterización espacial y extracción de clústeres activos

Antes del bucle principal, la versión v1 realiza una preclusterización espacial de las prácticas disponibles. Posteriormente, en cada iteración, una vez seleccionado el subconjunto factible de prácticas `P'`, se extraen los clústeres activos correspondientes a las prácticas seleccionadas. El objetivo de esta fase es favorecer que un mismo profesor supervise prácticas geográficamente cercanas, reduciendo así la dispersión de supervisión medida mediante `lbar_sum`.

Como las instancias actuales asocian cada práctica a una empresa y disponen de matrices de distancia entre empresas, la primera versión de clustering se basará en agrupar prácticas por empresa (densidad): cada clúster contendrá las prácticas pertenecientes a una misma empresa.

Después, para cada subconjunto `P'`, se filtran esos clústeres globales y se conservan únicamente las prácticas seleccionadas. Los clústeres activos se ordenarán por tamaño descendente. Por ejemplo:

```text
P' = [3, 7, 8, 10, 15]

Empresa 0: prácticas seleccionadas [3, 8]
Empresa 1: prácticas seleccionadas [7]
Empresa 2: prácticas seleccionadas [10, 15]

Clústeres activos:
C1 = [3, 8]
C2 = [10, 15]
C3 = [7]

Ordenados de forma que:
|C1| >= |C2| >= ... >= |Cr|
```

Asignar primero los clústeres más grandes ayuda a controlar mejor la capacidad de los profesores y favorece configuraciones más compactas.

---

## 6. Asignación práctica-profesor en v1

Una vez seleccionado el subconjunto de prácticas `P'`, se debe asignar un profesor a cada práctica seleccionada. Esta fase no se resuelve mediante LAP, ya que la asignación profesor-práctica no es un problema uno-a-uno: un profesor puede supervisar varias prácticas, tiene una capacidad máxima `C_t`, y el coste de supervisión depende del conjunto completo de prácticas que se le asignan.

El aspecto importante de esta fase es que la asignación de profesores no depende del estudiante concreto que ocupe cada práctica. Para el profesorado importa qué prácticas están cubiertas, dónde están ubicadas, cuántas prácticas supervisa cada profesor, qué dispersión geográfica tiene su conjunto de prácticas y cómo queda equilibrada la carga entre profesores. En cambio, no importa qué alumno concreto está asignado a cada práctica.

En la versión v1, en lugar de construir una única asignación mediante una decisión práctica a práctica, para cada subconjunto `P'` se generan varias asignaciones profesor-práctica:

- Una asignación inicial construida por clústeres, orientada a favorecer la proximidad geográfica de las prácticas supervisadas por cada profesor.
- Una asignación guía orientada a las cargas objetivo, cuyo propósito es aproximar la carga de cada profesor a la distribución proporcional calculada previamente.
- Varias asignaciones intermedias generadas mediante path relinking entre la asignación inicial y la asignación guía.

Todas las asignaciones profesor-práctica generadas deben respetar la capacidad máxima de los profesores y asignar exactamente un profesor a cada práctica seleccionada en `P'`. Posteriormente, cada una de estas asignaciones se combina con las dos asignaciones estudiante-práctica obtenidas mediante LAP.

---

## 7. Construcción inicial profesor-práctica por clústeres

La primera asignación profesor-práctica de v1 se construye usando los clústeres activos de prácticas seleccionadas para el subconjunto `P'`. Esta asignación inicial no es necesariamente la asignación definitiva de profesores, sino el punto de partida del path relinking. Su objetivo es generar una configuración factible y geográficamente compacta, procurando además acercarse de forma aproximada a las cargas objetivo de los profesores.

La idea principal es asignar tantas prácticas como sea posible de un mismo clúster a un mismo profesor, siempre que:

- El profesor tenga capacidad disponible.
- Se intente respetar su carga objetivo.
- Se favorezca la proximidad geográfica.
- La asignación siga siendo factible.

El procedimiento conceptual es:

```text
Ordenar C = {C1, C2, ..., Cr} de acuerdo con |C_l| descendente
Ordenar profesores de acuerdo con carga objetivo restante descendente

while existan prácticas por asignar:
    Seleccionar siguiente clúster C_l
    Seleccionar siguiente profesor k
    Asignar tantas prácticas de C_l como sea posible al profesor k
    Actualizar carga del profesor k
    Actualizar prácticas pendientes en C_l
    Actualizar orden de profesores
    Actualizar orden de clústeres
```

El resultado de esta fase es start_professor_assignment (placement -> professor).

La carga objetivo restante de un profesor se define como: `R_k = A_k - load_k`, donde `A_k` es la carga objetivo del profesor `k`, y `load_k` es el número de prácticas ya asignadas al profesor `k`.

Se priorizan profesores con mayor carga objetivo restante. En caso de empate, se puede usar como criterio secundario la distancia entre el centro educativo del profesor y la empresa asociada al clúster. Si un clúster contiene más prácticas de las que caben en el profesor seleccionado, se asigna solo una parte del clúster y el resto queda pendiente. Si un profesor alcanza su capacidad máxima, deja de ser candidato.

Esta asignación inicial está orientada principalmente a la proximidad espacial y al respeto aproximado de las cargas objetivo. Posteriormente, se utilizará como asignación de partida en el path relinking frente a una asignación guía orientada al equilibrio de carga.

---

## 8. Construcción de asignación guía orientada a cargas objetivo

Además de la asignación inicial por clústeres, HH-LAP-SIPA v1 construye una segunda asignación profesor-práctica que actúa como asignación guía para el path relinking. Esta tiene como objetivo aproximarse al vector de cargas objetivo `A_k`. A diferencia de la asignación inicial por clústeres, que prioriza la proximidad espacial de las prácticas asignadas a cada profesor, la asignación guía prioriza que cada profesor termine con un número de prácticas cercano a su carga objetivo.

El procedimiento conceptual es:

```text
Inicializar todos los profesores sin prácticas asignadas
Ordenar profesores según A_k descendente
Ordenar prácticas seleccionadas usando un criterio espacial o aleatorio controlado

Para cada profesor k:
    asignar prácticas pendientes hasta alcanzar A_k o hasta agotar prácticas

Si quedan prácticas pendientes:
    asignarlas a profesores con capacidad disponible
```

El resultado de esta fase es guide_professor_assignment (placement -> professor)

Esta asignación debe cumplir:

- Toda práctica seleccionada en `P'` tiene exactamente un profesor asignado.
- Ningún profesor supera su capacidad máxima.
- La suma total de cargas coincide con el número de prácticas seleccionadas.

La asignación guía no sustituye directamente a la asignación inicial. Su función es proporcionar un destino hacia el que mover gradualmente la asignación inicial mediante path relinking. Por tanto, esta fase está orientada principalmente a mejorar el equilibrio de carga entre profesores y a reducir el componente `sigma_sum`.

---

## 9. Path relinking entre asignaciones profesor-práctica

Dado un mismo subconjunto `P'`, se dispone de dos asignaciones profesor-práctica: start_professor_assignment y guide_professor_assignment. La primera procede de la construcción por clústeres y está más orientada a la proximidad espacial. La segunda está más orientada a cumplir las cargas objetivo de los profesores.

El path relinking genera una secuencia de asignaciones intermedias que transforman progresivamente la asignación inicial en la asignación guía.

El procedimiento conceptual es:

```text
current_assignment <- start_professor_assignment
Guardar current_assignment

while current_assignment != guide_professor_assignment and steps < max_steps:

    Identificar prácticas cuyo profesor actual difiere del profesor guía

    Seleccionar un movimiento candidato:
        mover una práctica j desde su profesor actual al profesor guía

    Aceptar el movimiento si:
        no supera la capacidad del profesor destino
        mantiene todas las prácticas asignadas
        produce una asignación válida

    Actualizar current_assignment
    Guardar current_assignment
```

De esta forma, cada asignación intermedia genera una nueva configuración profesor-práctica para el mismo subconjunto `P'`. Si un movimiento directo hacia la guía no es factible porque el profesor destino está lleno, se podrá saltar ese movimiento y probar otro. Si no quedan movimientos factibles, el path relinking termina.

La utilidad de esta fase es explorar soluciones que representan diferentes compromisos entre la proximidad geográfica y el equilibrio de carga, pero siempre asegurando la factibilidad respecto a capacidades y la calidad final tras combinarse con los LAP estudiante-práctica.

---

## 10. Asignación estudiante-práctica y generación de soluciones completas

Una vez fijado el subconjunto de prácticas `P'`, la asignación estudiante-práctica se convierte en un problema de asignación lineal uno-a-uno. Esto es posible porque la selección inicial de prácticas fuerza que `|P'| = |S|`, de modo que existe el mismo número de prácticas seleccionadas que de estudiantes.

Sobre este conjunto `P'`, se construyen dos matrices de beneficio: Tau[i][j] = tau_ij, Eta[i][j] = eta_ij; donde `i` representa un estudiante y `j` una práctica perteneciente a `P'`. A partir de estas matrices se resuelven dos problemas LAP independientes mediante `lapjv`:

- Un LAP maximizando `tau`, que obtiene la asignación estudiante-práctica óptima desde el punto de vista de los estudiantes.
- Un LAP maximizando `eta`, que obtiene la asignación estudiante-práctica óptima desde el punto de vista de las empresas/prácticas.

Para cada subconjunto `P'`, estos dos LAP se resuelven una sola vez (assignment_tau = LAP max tau y assignment_eta = LAP max eta).

Estos LAP dependen únicamente de:

- El conjunto de estudiantes.
- El subconjunto de prácticas seleccionadas `P'`.
- Las matrices `tau` y `eta`.

No dependen de la asignación de profesores, ya que los profesores afectan a `lbar_sum` y `sigma_sum`, pero no modifican las utilidades estudiante-práctica `tau_ij` ni empresa-práctica `eta_ij`. Por tanto, para ahorrar tiempo computacional, v1 reutiliza `assignment_tau` y `assignment_eta` para todas las asignaciones profesor-práctica generadas durante el path relinking.

Para cada asignación profesor-práctica generada (`professor_assignment_m`), se construyen dos soluciones completas:

```text
Solucion_tau_m = P' + professor_assignment_m + assignment_tau
Solucion_eta_m = P' + professor_assignment_m + assignment_eta
```

Cada solución completa se valida frente a las restricciones del modelo. Si es válida, se evalúa con los cuatro objetivos (tau_sum, eta_sum, lbar_sum, sigma_sum). Después, se intenta insertar en el Pareto externo si no está dominada por soluciones ya existentes.

De este modo, cada iteración puede generar más de dos soluciones candidatas, a diferencia de v0, donde cada subconjunto `P'` generaba como máximo dos soluciones completas. Las soluciones de una misma iteración comparten el mismo subconjunto de prácticas seleccionadas y las mismas asignaciones LAP, pero difieren en la asignación práctica-profesor generada durante el path relinking.

---

## 11. Uso del LAP en la heurística

La heurística utiliza problemas LAP para resolver de forma exacta la asignación estudiante-práctica una vez fijado el subconjunto de prácticas `P'`. El solver principal será `lapjv`, ya que el repositorio `src-d/lapjv` implementa un solver del Linear Assignment Problem basado en el algoritmo Jonker-Volgenant.

Además, el repositorio comparativo `berhane/LAP-solvers` se utilizará como referencia para justificar la elección de `lapjv`, ya que compara distintas implementaciones para resolver problemas LAP y señala esta alternativa como una de las más eficientes.

No obstante, se contempla mantener una alternativa basada en `scipy.optimize.linear_sum_assignment` en caso de que `lapjv` presente problemas de instalación, configuración o compatibilidad en el entorno de ejecución.

Desde el punto de vista del algoritmo, los dos LAP que se resuelven son problemas de maximización de `tau` y `eta`. Sin embargo, muchos solvers LAP están formulados como problemas de minimización. Por ello, la maximización se transforma en minimización cambiando el signo de la matriz de beneficios:

```python
cost_tau = -tau_matrix  # maximizar tau equivale a minimizar -tau
row_ind, col_ind, _ = lapjv(cost_tau)

cost_eta = -eta_matrix  # maximizar eta equivale a minimizar -eta
row_ind, col_ind, _ = lapjv(cost_eta)
```

Por tanto, `lapjv` se usará como subrutina exacta para resolver la asignación estudiante-práctica dentro de la heurística, mientras que el resto de decisiones del problema, como la selección de prácticas y la asignación práctica-profesor, se resolverán mediante procedimientos heurísticos.

En esta versión, los LAP se resuelven una sola vez por subconjunto `P'`, y sus resultados se reutilizan para todas las asignaciones profesor-práctica generadas mediante path relinking.

---

## 12. Flujo completo de la heurística

El flujo completo de la heurística se resume en el siguiente pseudocódigo:

```text
HH-LAP-SIPA-v1(problem, time_limit, max_iterations, base_seed):

    pareto_set ← ∅

    target_loads ← compute_target_professor_loads(problem)

    while not stopping_condition:

        P' ← generate_random_feasible_placements(problem)

        clusters ← build_selected_placement_clusters(problem, P')

        start_professor_assignment ← assign_professors_by_clusters(
            problem,
            P',
            clusters,
            target_loads
        )

        if start_professor_assignment is not feasible:
            continue

        guide_professor_assignment ← build_load_balanced_professor_assignment(
            problem,
            P',
            target_loads
        )

        if guide_professor_assignment is not feasible:
            continue

        professor_assignments ← path_relink_professor_assignments(
            problem,
            P',
            start_professor_assignment,
            guide_professor_assignment
        )

        tau_matrix ← build_tau_matrix(problem, P')
        assignment_tau ← solve_lapjv_max(tau_matrix)

        eta_matrix ← build_eta_matrix(problem, P')
        assignment_eta ← solve_lapjv_max(eta_matrix)

        for professor_assignment in professor_assignments:

            sol_tau ← build_solution(P', professor_assignment, assignment_tau)
            if validate(sol_tau):
                evaluate_and_update_pareto(pareto_set, sol_tau)

            sol_eta ← build_solution(P', professor_assignment, assignment_eta)
            if validate(sol_eta):
                evaluate_and_update_pareto(pareto_set, sol_eta)

    return pareto_set
```

El criterio de parada principal será el tiempo de ejecución, fijado inicialmente en 300 segundos para los experimentos comparativos. Este criterio permite comparar HH-LAP-SIPA v1 con HH-LAP-SIPA v0 y con otras heurísticas bajo las mismas condiciones computacionales. Adicionalmente, la implementación podrá contemplar otros criterios, como número máximo de iteraciones, número de subconjuntos generados o número de soluciones factibles evaluadas.

--- 

## 13. Relación con el código actual

La implementación de la heurística se apoyará en las estructuras ya existentes del proyecto. En particular:

- `Problem`: representación de la instancia del problema.
- `Solution`: representación de una solución completa.
- `evaluate_solution_multi`: evaluación multiobjetivo de una solución.
- `evaluate_solution_scalar`: evaluación escalar auxiliar.
- `register_solution_in_pareto`: evaluación, validación y registro de soluciones en el Pareto externo.

La versión v1 reutilizará componentes ya definidos en v0:

- `generate_random_feasible_placements(problem)`: genera un subconjunto factible de prácticas `P'`.
- `build_tau_matrix(problem, selected_placements)`: construye la matriz de beneficios `tau` para el LAP orientado a estudiantes.
- `build_eta_matrix(problem, selected_placements)`: construye la matriz de beneficios `eta` para el LAP orientado a empresas.
- `solve_lapjv_max(matrix)`: resuelve un problema LAP de maximización usando `lapjv`.
- `build_solution_from_lap_assignment(...)`: construye una solución completa combinando `P'`, la asignación práctica-profesor y la asignación estudiante-práctica devuelta por `lapjv`.

Además, añadirá los siguientes componentes:

- `compute_target_professor_loads(problem)`: calcula las cargas objetivo por profesor.
- `build_selected_placement_clusters(problem, selected_placements)`: agrupa las prácticas seleccionadas en clústeres.
- `assign_professors_by_clusters(problem, selected_placements, clusters, target_loads, rng)`: construye la asignación inicial por clústeres.
- `build_load_balanced_professor_assignment(problem, selected_placements, target_loads, rng)`: construye la asignación guía orientada a cargas objetivo.
- `path_relink_professor_assignments(problem, selected_placements, start_assignment, guide_assignment, max_steps, rng)`: genera asignaciones intermedias mediante path relinking.
- `run_hh_lap_sipa_v1(...)`: ejecuta el bucle principal de la versión v1.

---

## 14. Relación con las baselines

HH-LAP-SIPA v1 se comparará principalmente con dos referencias: la baseline aleatoria y HH-LAP-SIPA v0. La baseline aleatoria permite medir si la heurística aporta valor frente a una generación factible sin optimización estructurada, mientras que v0 permite comprobar si las nuevas decisiones de diseño de v1 mejoran, empeoran o mantienen la calidad de la versión predecesora.

Respecto a la baseline aleatoria, v1 mantiene la selección inicial factible de prácticas `P'`, pero modifica la forma de construir la solución completa. La asignación práctica-profesor deja de ser aleatoria o puramente reparadora y pasa a estar guiada por cargas objetivo, clústeres espaciales y path relinking. Además, la asignación estudiante-práctica se resuelve de forma exacta mediante LAP, en lugar de construirse de forma aleatoria.

Respecto a HH-LAP-SIPA v0, la diferencia principal está en la capa de asignación práctica-profesor. En v0, para cada subconjunto `P'`, se construía una única asignación profesor-práctica mediante una decisión guiada práctica a práctica. En v1, para cada `P'`, se construye una asignación inicial por clústeres, una asignación guía orientada a cargas objetivo y varias asignaciones intermedias mediante path relinking.

```text
Baseline aleatoria:
    P' factible
        ↓
    asignación aleatoria/reparadora de estudiantes y profesores
        ↓
    solución factible

HH-LAP-SIPA v0:
    P' factible
        ↓
    asignación profesor-práctica guiada práctica a práctica
        ↓
    LAP tau + LAP eta
        ↓
    como máximo dos soluciones por iteración

HH-LAP-SIPA v1:
    cargas objetivo por profesor
        ↓
    preclusterización espacial de prácticas
        ↓
    P' factible
        ↓
    extracción de clústeres activos
        ↓
    asignación inicial por clústeres
        ↓
    asignación guía por cargas objetivo
        ↓
    path relinking
        ↓
    LAP tau + LAP eta
        ↓
    varias soluciones por iteración
```

Por tanto, v1 no debe entenderse como una búsqueda aleatoria pura, sino como una heurística híbrida que combina aleatoriedad controlada, conocimiento estructural del problema, construcción guiada por clústeres, equilibrio de carga objetivo, path relinking, optimización exacta mediante LAP y actualización del Pareto externo.

La comparación experimental permitirá comprobar si estas incorporaciones producen una mejora real respecto a la baseline aleatoria y respecto a HH-LAP-SIPA v0. En síntesis, HH-LAP-SIPA v1 se plantea como una evolución de v0, no como una sustitución directa, y v0 se conserva como baseline interna de comparación.

---

## 15. Salidas esperadas

La heurística devolverá como resultado principal el conjunto de soluciones no dominadas encontrado durante la ejecución, junto con estadísticas asociadas:

- `pareto_set` (assignments): conjunto Pareto externo con las soluciones no dominadas.
- `stats` (statistics): estadísticas de ejecución de la heurística.

Las estadísticas mínimas que se registrarán serán:

- `iterations`: número de iteraciones ejecutadas.
- `generated_subsets`: número de subconjuntos `P'` generados.
- `cluster_assignment_failures`: número de fallos al construir la asignación por clústeres.
- `guide_assignment_failures`: número de fallos al construir la asignación guía.
- `path_relinking_runs`: número de ejecuciones de path relinking.
- `path_relinking_assignments`: número total de asignaciones profesor-práctica generadas mediante path relinking.
- `lap_tau_solutions`: número de soluciones generadas usando el LAP que maximiza `tau`.
- `lap_eta_solutions`: número de soluciones generadas usando el LAP que maximiza `eta`.
- `feasible_solutions`: número de soluciones completas factibles evaluadas.
- `invalid_solutions`: número de soluciones descartadas por no ser válidas.
- `inserted_into_pareto`: número de soluciones incorporadas al Pareto externo.
- `pareto_size`: tamaño final del Pareto externo.
- `elapsed_seconds`: tiempo total de ejecución.
- `generation_failures`: número de fallos al generar `P'`.
- `lap_solver`: solver usado para resolver los LAP.
- `time_limit_seconds`: límite de tiempo usado.
- `max_iterations`: límite de iteraciones, si se proporciona.
- `max_path_relinking_steps`: número máximo de pasos permitido en el path relinking.

Además, se podrá guardar un resumen del Pareto final con indicadores agregados de calidad, como máximos o medias de los objetivos considerados.

---

## 16. Decisiones de diseño fijadas

Las decisiones de diseño fijadas para HH-LAP-SIPA v1 son:

- HH-LAP-SIPA v0 se conserva como baseline independiente para comparar resultados.
- La selección inicial de prácticas `P'` sigue siendo aleatoria factible y debe cumplir `|P'| = |S|`.
- La asignación práctica-profesor no se resuelve mediante LAP, sino mediante una estrategia heurística basada en cargas objetivo, clústeres y path relinking.
- Antes del bucle principal se calcula una carga objetivo por profesor, proporcional a su capacidad máxima.
- En la primera implementación, las cargas objetivo se calculan mediante reparto proporcional entero, sin resolver un ILP auxiliar.
- Antes del bucle principal se realiza una preclusterización espacial de prácticas. En v1, esta preclusterización se basa en agrupar prácticas por empresa.
- Para cada subconjunto `P'`, se extraen los clústeres activos correspondientes a las prácticas seleccionadas.
- Para cada `P'`, se construye una asignación inicial profesor-práctica orientada a clústeres y proximidad geográfica.
- Para cada `P'`, se construye una asignación guía orientada a aproximar las cargas de los profesores a sus cargas objetivo.
- Se aplica path relinking entre la asignación inicial y la asignación guía.
- Solo se aceptan movimientos de path relinking que mantengan factibilidad inmediata.
- La asignación estudiante-práctica se resuelve mediante LAP usando `lapjv` como solver principal.
- Para cada subconjunto `P'`, se resuelven exactamente dos LAP: uno maximizando `tau` y otro maximizando `eta`.
- Los LAP `tau` y `eta` se resuelven una sola vez por subconjunto `P'` y se reutilizan para todas las asignaciones profesor-práctica generadas mediante path relinking.
- Cada asignación profesor-práctica generada puede producir dos soluciones completas: una combinada con el LAP `tau` y otra combinada con el LAP `eta`.
- Toda solución completa debe validarse antes de evaluarse.
- El Pareto externo se actualiza únicamente con soluciones válidas y no dominadas.

---

## 17. Posibles mejoras futuras

Quedan identificadas varias extensiones posibles para versiones posteriores:

- Selección guiada de prácticas: sustituir o complementar la selección aleatoria de `P'` con una puntuación aproximada basada en el potencial de cada práctica respecto a `tau` y `eta`.

- Búsqueda local sobre `P'`: aplicar movimientos como eliminar, añadir o intercambiar prácticas, reparando cuotas y dependencias cuando sea necesario.

- Clustering espacial real: refinar la preclusterización actual usando `company_company_dist`, agrupando empresas cercanas aunque no sean idénticas. Para v1 se mantiene una estrategia simple, interpretable y robusta basada en empresa.

- Ordenación avanzada de clústeres: ordenar clústeres no solo por tamaño, sino también por distancia media, dispersión, dificultad de asignación o cercanía a centros educativos.

- Mejora de la asignación guía: incorporar criterios espaciales además de las cargas objetivo, para que la guía no solo favorezca equilibrio de carga, sino también menor dispersión.

- Repair avanzado durante path relinking: permitir swaps entre profesores o movimientos en dos pasos cuando un movimiento directo hacia la guía no sea factible.

- Path relinking bidireccional: explorar tanto el camino desde la asignación inicial hacia la guía como desde la guía hacia la inicial.

- LAP ponderado adicional: resolver un tercer LAP maximizando una combinación `lambda * tau + (1 - lambda) * eta`, o varios LAP con distintos valores de `lambda`, para generar soluciones intermedias entre estudiantes y empresas.

- Mejora local de profesores: tras el path relinking, probar movimientos de reasignación o intercambio de prácticas entre profesores para reducir `lbar_sum` y `sigma_sum`.

- Análisis del coste computacional añadido: comprobar experimentalmente si el aumento de soluciones generadas por iteración compensa el coste adicional de clústeres y path relinking.