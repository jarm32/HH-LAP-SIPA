# Diseño conceptual del HH-LAP-SIPA (Heurística Híbrida con LAP para el modelo SIPA extendido)

## 1. Objetivo del documento

Este documento define el diseño de la heurística híbrida con LAP propuesta, la cual se basa en el siguiente esquema conceptual:

```text
Selección aleatoria factible de prácticas P'
        ↓
Asignación práctica-profesor mediante repair guiado
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
- Asignación práctica-profesor mediante construcción y repair guiado.
- Resolución exacta de subproblemas de asignación estudiante-práctica.
- Evaluación multiobjetivo.
- Mantenimiento de una frontera de Pareto con soluciones no dominadas.

En lugar de construir directamente una solución completa `x_ijt`, la heurística divide el proceso en tres capas:

```text
Capa 1: selección de prácticas P'
Capa 2: asignación práctica-profesor
Capa 3: asignación estudiante-práctica
```

La primera capa genera un subconjunto `P'` de prácticas de forma aleatoria, pero siempre respetando las restricciones estructurales del problema. La segunda capa asigna profesores a las prácticas seleccionadas mediante una estrategia de construcción y repair guiado (no se resuelve mediante LAP, ya que un profesor puede supervisar varias prácticas y su coste depende del conjunto completo de prácticas asignadas). La tercera capa resuelve la asignación estudiante-práctica mediante dos problemas LAP usando `lapjv`:

- Un LAP maximizando `tau`, que genera una solución orientada a estudiantes.
- Un LAP maximizando `eta`, que genera una solución orientada a empresas.

Para cada subconjunto `P'`, la asignación práctica-profesor se calcula una única vez y se combina con cada una de las asignaciones estudiante-práctica devueltas por `lapjv`. Así se obtienen dos soluciones completas: `Solución_tau` y `Solución_eta`.

Ambas soluciones se validan frente a las restricciones del modelo y se evalúan con los cuatro objetivos. Si son factibles y no están dominadas, se incorporan al Pareto externo.

---


############################################################

## 7. Papel de la selección de prácticas P'

La selección inicial de prácticas no busca elegir directamente las “mejores prácticas”.

Esto es importante porque una práctica no es buena o mala de forma aislada desde el punto de vista de estudiantes o empresas. La utilidad depende del par estudiante-práctica:

```text
tau_ij = utilidad de asignar la práctica j al estudiante i
eta_ij = utilidad que aporta el estudiante i a la práctica j
```

Por tanto, inicialmente se generará un subconjunto `P'` de prácticas que sea factible estructuralmente.

Debe cumplir:

```text
|P'| = |S|
```

y además:

```text
cuotas mínimas de empresa
cuotas máximas de empresa
dependencias completas
```

La calidad real de `P'` se conocerá después de resolver los LAP estudiante-práctica y evaluar las soluciones completas.

---

## 8. Asignación práctica-profesor

La asignación de profesores no se resolverá mediante LAP.

Motivo:

```text
La asignación profesor-práctica no es un problema 1-1.
```

Un profesor puede supervisar varias prácticas, tiene capacidad máxima `C_t`, y su coste depende del conjunto completo de prácticas asignadas, no solo de una pareja profesor-práctica.

Por tanto, se usará una estrategia de construcción/repair guiado.

### 8.1. Principio clave

Al profesor le da igual qué estudiante concreto esté en cada práctica.

Para la parte de profesorado importa:

- qué prácticas están cubiertas;
- dónde están ubicadas;
- cuántas prácticas supervisa cada profesor;
- qué dispersión geográfica tiene cada profesor;
- cómo queda equilibrada la carga entre profesores del mismo centro.

No importa:

```text
qué alumno concreto está asignado a cada práctica.
```

Por tanto, para un mismo subconjunto `P'`, la asignación práctica-profesor puede calcularse una única vez y reutilizarse para las dos soluciones generadas por LAP.

---

### 8.2. Estrategia propuesta para profesores

La estrategia inicial será una asignación mediante repair guiado.

Esquema:

```text
Dado P':

1. Inicializar todos los profesores sin prácticas.
2. Recorrer las prácticas seleccionadas.
3. Para cada práctica:
      buscar profesores con capacidad disponible;
      calcular el incremento de coste si se asigna a cada profesor;
      asignar la práctica al profesor con menor incremento.
4. Si queda alguna práctica sin profesor:
      aplicar repair moviendo prácticas entre profesores.
5. Validar capacidades.
```

El coste incremental puede tener en cuenta:

```text
incremento de lbar_sum
+
penalización por desequilibrio de carga sigma_sum
```

La versión inicial puede ser simple, pero debe garantizar siempre que no se supera la capacidad de ningún profesor.

---

## 9. Asignación estudiante-práctica mediante LAP

Una vez fijado `P'`, el problema estudiante-práctica se convierte en un problema de asignación lineal 1-1.

Tenemos:

```text
|S| estudiantes
|P'| prácticas seleccionadas
```

y se fuerza:

```text
|S| = |P'|
```

Por tanto, se puede construir una matriz cuadrada de beneficios. Cada solución completa se obtiene combinando la asignación práctica-profesor calculada previamente para \(P'\) con la asignación estudiante-práctica devuelta por `lapjv`. De este modo, `Solución_tau` se construye uniendo la asignación de profesores con el LAP que maximiza `tau`, mientras que `Solución_eta` se construye uniendo la misma asignación de profesores con el LAP que maximiza `eta`.

---

### 9.1. LAP maximizando tau

Se construye una matriz:

```text
Tau[i][j] = tau_ij
```

donde `j` pertenece a `P'`.

Este LAP busca la asignación estudiante-práctica que maximiza la utilidad total de estudiantes.

Resultado:

```text
Solución_tau
```

Esta solución usa:

```text
mismo P'
misma asignación práctica-profesor
asignación estudiante-práctica óptima respecto a tau
```

---

### 9.2. LAP maximizando eta

Se construye una matriz:

```text
Eta[i][j] = eta_ij
```

donde `j` pertenece a `P'`.

Este LAP busca la asignación estudiante-práctica que maximiza la utilidad total de empresas/prácticas.

Resultado:

```text
Solución_eta
```

Esta solución usa:

```text
mismo P'
misma asignación práctica-profesor
asignación estudiante-práctica óptima respecto a eta
```

---

### 9.3. No se usarán combinaciones tau/eta

En esta primera versión no se resolverán LAP con combinaciones ponderadas del tipo:

```text
lambda * tau + (1 - lambda) * eta
```

La heurística generará exactamente dos soluciones por cada subconjunto `P'`:

```text
una solución maximizando tau
una solución maximizando eta
```

---

## 10. Uso de lapjv

El solver LAP principal será:

```text
lapjv
```

El repositorio `src-d/lapjv` implementa un solver del Linear Assignment Problem basado en el algoritmo Jonker-Volgenant:

```text
https://github.com/src-d/lapjv
```

### 10.1. Integración conceptual

Muchos solvers LAP están formulados como minimización.

Como nuestros dos LAP son de maximización, se transforman así:

```python
cost_tau = -tau_matrix
row_ind, col_ind, _ = lapjv(cost_tau)

cost_eta = -eta_matrix
row_ind, col_ind, _ = lapjv(cost_eta)
```

Maximizar `tau` equivale a minimizar `-tau`.

Maximizar `eta` equivale a minimizar `-eta`.

---

## 11. Papel de LAP-solvers

El repositorio `berhane/LAP-solvers` se usará como referencia comparativa:

```text
https://github.com/berhane/LAP-solvers
```

Su papel dentro del diseño de esta heurística es:

```text
justificar la elección de lapjv como solver LAP eficiente
```

Por tanto:

```text
src-d/lapjv          → implementación que usaremos
berhane/LAP-solvers → referencia comparativa / estado del arte práctico
```

---

## 12. Qué resuelve lapjv y qué no resuelve

### lapjv sí resuelve

```text
Dado S y P' con |S| = |P'|,
encontrar el emparejamiento estudiante-práctica 1-1 óptimo
según una matriz de costes o beneficios.
```

En nuestro caso:

```text
LAP max tau
LAP max eta
```

---

### lapjv no resuelve

`lapjv` no resuelve:

```text
selección de prácticas P'
cuotas mínimas de empresa
cuotas máximas de empresa
dependencias entre prácticas
asignación de profesores
capacidades de profesores
dispersión geográfica de supervisión
equilibrio de carga entre profesores
mantenimiento de la frontera de Pareto
```

Por tanto, `lapjv` será una subrutina interna de la heurística, no la heurística completa.

---

## 13. Flujo completo de la heurística

```text
Entrada:
    problem
    weights
    time_limit
    max_iterations
    base_seed

Inicializar:
    pareto_set = []

Mientras no se cumpla criterio de parada:

    1. Generar P' aleatorio factible
        - |P'| = n_students
        - cuotas de empresa correctas
        - dependencias completas

    2. Asignar profesores a P'
        - construcción/repair guiado
        - respetar prof_capacity
        - obtener placement_to_professor

    3. Construir matriz tau sobre S × P'

    4. Resolver LAP con lapjv usando tau
        - obtener asignación estudiante-práctica
        - construir Solución_tau

    5. Validar Solución_tau
        - R1, R2, R3, R4, R5, R6, R7

    6. Si Solución_tau es válida:
        - evaluar tau_sum, eta_sum, lbar_sum, sigma_sum
        - actualizar Pareto

    7. Construir matriz eta sobre S × P'

    8. Resolver LAP con lapjv usando eta
        - obtener asignación estudiante-práctica
        - construir Solución_eta

    9. Validar Solución_eta
        - R1, R2, R3, R4, R5, R6, R7

    10. Si Solución_eta es válida:
        - evaluar tau_sum, eta_sum, lbar_sum, sigma_sum
        - actualizar Pareto

Salida:
    pareto_set
    estadísticas de ejecución
```

---

## 14. Pseudocódigo

```text
HH-LAP-SIPA(problem, time_limit, weights):

    pareto_set ← ∅

    while not stopping_condition:

        P' ← generate_random_feasible_placements(problem)

        professor_assignment ← assign_professors_with_guided_repair(problem, P')

        if professor_assignment is not feasible:
            continue

        tau_matrix ← build_tau_matrix(problem, P')
        assignment_tau ← solve_lapjv_max(tau_matrix)

        sol_tau ← build_solution(
            problem,
            P',
            professor_assignment,
            assignment_tau
        )

        if validate(sol_tau):
            eval_tau ← evaluate_solution_multi(sol_tau)
            pareto_set ← update_pareto(pareto_set, sol_tau, eval_tau)

        eta_matrix ← build_eta_matrix(problem, P')
        assignment_eta ← solve_lapjv_max(eta_matrix)

        sol_eta ← build_solution(
            problem,
            P',
            professor_assignment,
            assignment_eta
        )

        if validate(sol_eta):
            eval_eta ← evaluate_solution_multi(sol_eta)
            pareto_set ← update_pareto(pareto_set, sol_eta, eval_eta)

    return pareto_set
```

---

## 16. Relación con el código actual

La heurística puede apoyarse en las estructuras actuales:

```text
Problem
Solution
evaluate_solution_multi
evaluate_solution_scalar
update_pareto_set
register_solution_in_pareto
```

Sin embargo, habrá que adaptar o crear funciones específicas:

```text
generate_random_feasible_placements_only(problem)
assign_professors_guided_repair(problem, selected_placements)
build_tau_matrix(problem, selected_placements)
build_eta_matrix(problem, selected_placements)
solve_lapjv_max(matrix)
build_solution_from_lap_assignment(...)
run_hh_lap_sipa(...)
```

El generador actual de soluciones aleatorias ya contiene parte de la lógica de selección de prácticas y reparación de dependencias/cuotas. La nueva heurística deberá separar esa lógica para que primero genere `P'` y después deje que el LAP decida la asignación estudiante-práctica.

---

## 17. Diferencias respecto a la baseline aleatoria

La baseline aleatoria actual hace, conceptualmente:

```text
selección de prácticas
+
asignación estudiante-práctica aleatoria
+
asignación de profesores
```

La nueva heurística hará:

```text
selección de prácticas aleatoria factible
+
asignación de profesores mediante repair guiado
+
asignación estudiante-práctica óptima mediante LAP
```

La mejora principal está en que, para cada subconjunto `P'`, no se asignan los estudiantes de forma aleatoria, sino de forma óptima respecto a `tau` y respecto a `eta`.

---

## 18. Criterios de parada

La heurística podrá usar uno o varios criterios de parada:

```text
límite de tiempo
número máximo de iteraciones
número máximo de soluciones generadas
número máximo de soluciones factibles evaluadas
```

Para experimentos comparativos, el criterio principal debería ser el tiempo, por ejemplo:

```text
60 segundos
300 segundos
900 segundos
```

según el tamaño de instancia.

---

## 19. Salidas esperadas

La heurística debe devolver:

```text
pareto_set
estadísticas de ejecución
```

Las estadísticas mínimas deberían incluir:

```text
iterations
generated_subsets
professor_assignment_failures
lap_tau_solutions
lap_eta_solutions
feasible_solutions
inserted_into_pareto
pareto_size
elapsed_seconds
```

También sería útil guardar un resumen del Pareto:

```text
max_tau
mean_tau
max_eta
mean_eta
min_lbar
mean_lbar
min_sigma
mean_sigma
max_objective_value
mean_objective_value
```

---

## 20. Decisiones de diseño fijadas

Quedan fijadas las siguientes decisiones:

```text
1. La selección inicial de prácticas P' será aleatoria factible.

2. La asignación práctica-profesor no usará LAP.

3. La asignación práctica-profesor se hará mediante construcción/repair guiado.

4. La asignación estudiante-práctica sí usará LAP.

5. El solver LAP principal será lapjv.

6. Se resolverán exactamente dos LAP por cada P':
      - max tau
      - max eta

7. No se usarán combinaciones tau/eta en esta primera versión.

8. Cada \(P'\) genera como máximo dos soluciones completas:
      - `Solución_tau`: combinación de la asignación práctica-profesor de \(P'\) con la asignación estudiante-práctica devuelta por `lapjv` al maximizar `tau`.
      - `Solución_eta`: combinación de la asignación práctica-profesor de \(P'\) con la asignación estudiante-práctica devuelta por `lapjv` al maximizar `eta`.

9. Las dos soluciones comparten:
      - el mismo \(P'\);
      - la misma asignación práctica-profesor.

10. Las dos soluciones difieren en:
      - la asignación estudiante-práctica devuelta por `lapjv`.

11. Toda solución debe cumplir R1–R7 antes de evaluarse.

12. El Pareto se actualiza solo con soluciones válidas.
```

---

## 21. Posibles mejoras futuras

Aunque no forman parte de la primera versión, quedan identificadas posibles extensiones.

### 21.1. Selección guiada de prácticas

En lugar de seleccionar `P'` de forma puramente aleatoria, se podría sesgar la selección usando una puntuación aproximada de potencial:

```text
score(j) = λ * max_i tau_ij + (1 - λ) * max_i eta_ij
```

o usando medias de los mejores `k` estudiantes para cada práctica.

Esta mejora no se implementará en la primera versión.

---

### 21.2. Búsqueda local sobre P'

Una vez generado un subconjunto `P'`, se podrían aplicar movimientos:

```text
eliminar una práctica
añadir otra práctica
intercambiar prácticas
reparar cuotas/dependencias
resolver LAP de nuevo
aceptar si mejora el Pareto
```

Esta mejora tampoco forma parte de la primera versión.

---

### 21.3. Mejora local de profesores

Después del repair inicial de profesores, se podrían probar movimientos locales:

```text
mover una práctica de un profesor a otro
intercambiar prácticas entre profesores
recalcular lbar_sum y sigma_sum
aceptar si mejora la supervisión
```

Esta mejora puede ser útil especialmente para reducir `lbar_sum` y `sigma_sum`.

---

## 22. Resumen final

La heurística HH-LAP-SIPA se define como una heurística híbrida para el modelo SIPA extendido.

Su funcionamiento se basa en:

```text
explorar subconjuntos factibles de prácticas
+
optimizar exactamente la asignación estudiante-práctica con LAP
+
reparar/guiar la asignación práctica-profesor
+
evaluar soluciones en un marco multiobjetivo
+
mantener una frontera de Pareto
```

La selección de prácticas permite explorar diferentes regiones del espacio de soluciones.

El repair de profesores garantiza que la capa de supervisión sea factible y razonable.

El uso de `lapjv` permite que, para cada subconjunto de prácticas, la asignación estudiante-práctica sea óptima respecto a `tau` y respecto a `eta`.

La frontera de Pareto permite conservar soluciones no dominadas considerando simultáneamente estudiantes, empresas, profesores y centros educativos.