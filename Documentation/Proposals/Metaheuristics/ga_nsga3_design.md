# Diseño conceptual del GA multiobjetivo (NSGA-III)

## 1. Objetivo del algoritmo

Desarrollar un algoritmo genético multiobjetivo que genere soluciones factibles de alta calidad para el problema SIPA modificado, optimizando simultáneamente:

- ↑ `tau_sum` (satisfacción estudiantes)
- ↑ `eta_sum` (satisfacción empresas)
- ↓ `lbar_sum` (coste de supervisión)
- ↓ `sigma_sum` (desequilibrio entre profesores)

---

## 2. Representación del individuo

- Cromosoma principal:  
  `student_to_placement[i] = j`

- La asignación de profesores no se codifica directamente, sino que se reconstruye después. Así se reduce la complejidad y encaja con la representación de la solución (Solution).

---

## 3. Población inicial

- Se generan individuos con:
  `generate_random_feasible_fixing` --> Aseguran factibilidad inicial.

---

## 4. Evaluación

- Evaluación principal: `evaluate_solution_multi`
- Objetivos:
  - max: `tau_sum`, `eta_sum`
  - min: `lbar_sum`, `sigma_sum`

- Evaluación escalar (`evaluate_solution_scalar`):
  - solo como apoyo para desempates, análisis o poda auxiliar, no como criterio principal.

---

#################################################

## 5. Selección

- Método: **NSGA-II**
- Basado en:
  - dominancia Pareto
  - diversidad entre soluciones

Compatible con tu gestión actual del Pareto.

---

## 6. Cruce

- Combina asignaciones de dos padres por subconjuntos de estudiantes
- Puede generar soluciones inválidas → requiere reparación

No se usa codificación tipo `xijt` por complejidad.

---

## 7. Mutación

Mutaciones locales:

- mover estudiante a otra plaza
- intercambiar estudiantes
- modificar bloques de dependencias

Siempre seguida de **repair**.

---

## 8. Repair

Clave del algoritmo. Dos fases:

### 1. Estudiante → plaza
- unicidad de plazas
- min/max empresas
- dependencias

### 2. Plaza → profesor
- asignar profesores
- respetar capacidades

Se reutiliza lógica de `random_feasible_fixing`.

---

## 9. Reemplazo

- Esquema elitista tipo NSGA-II:
  - padres + hijos
  - selección por frentes no dominados
  - mantener diversidad

---

## 10. Pareto global

Se mantiene un conjunto externo de soluciones no dominadas usando:

- `update_pareto_set`
- `prune_pareto_set_by_size`

---

## 11. Criterio de parada

Inicialmente:

- límite de tiempo (ej. 60s)

Opcional:
- nº generaciones
- estancamiento

---

## 12. Parámetros iniciales

- población: 50
- cruce: 0.8
- mutación: 0.2
- generaciones: 100
- pareto max: 50
- seed: 1234

---

## 13. Evaluación frente a baseline

Comparar con búsqueda aleatoria en:

- tamaño del Pareto
- calidad de soluciones
- diversidad
- mejor valor escalar
- tiempo

Baseline actual: `random_search_pareto`

---

## 14. Decisiones clave

- GA multiobjetivo desde el inicio
- cromosoma: `student_to_placement`
- profesores → reconstrucción (no genética)
- uso de soluciones factibles desde el inicio
- NSGA-II como base
- repair obligatorio tras variación