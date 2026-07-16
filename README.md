# VRAIN-practicas

Este repositorio contiene el código desarrollado para estudiar una versión extendida del problema **Student–Industry Placement Allocation (SIPA)**. El objetivo principal es asignar estudiantes a prácticas en empresas teniendo en cuenta no solo la utilidad para estudiantes y empresas, sino también la capa de supervisión académica por parte de profesores.

El proyecto parte de un modelo SIPA basado en competencias y lo amplía incorporando profesores, centros educativos, capacidades de supervisión, distancias de supervisión y balance de carga docente.

## Descripción general

El problema abordado consiste en construir asignaciones factibles entre:
- Estudiantes.
- Plazas de prácticas ofertadas por empresas.
- Profesores supervisores.
- Centros educativos.

Cada solución debe respetar restricciones:
- Cada estudiante debe recibir una plaza.
- Cada plaza puede ser ocupada como máximo por un estudiante.
- Las empresas tienen cuotas mínimas y máximas.
- Algunas plazas pueden tener dependencias y deben asignarse conjuntamente.
- Cada profesor tiene una capacidad máxima de supervisión.

Además, las soluciones se evalúan mediante cuatro objetivos:
- Utilidad para los estudiantes.
- Utilidad para las empresas.
- Coste/dispersion de supervisión.
- Balance de carga entre profesores.

## Algoritmos incluidos

El repositorio contiene varios métodos de búsqueda y comparación:
- **Random feasible baseline**: genera soluciones factibles de forma aleatoria usando mecanismos de reparación.
- **NSGA-III**: algoritmo genético multiobjetivo adaptado al problema SIPA extendido.
- **GRASP**: método constructivo multiarranque con criterios heurísticos.
- **HH-LAP-SIPA-Lite**: variante híbrida ligera basada en selección factible de plazas, asignación de profesores y resolución exacta del subproblema estudiante-plaza.
- **HH-LAP-SIPA-Intensive**: variante híbrida más intensiva, con una construcción más elaborada de la capa de supervisión.

Todos los algoritmos generan soluciones factibles, las evalúan según los cuatro objetivos del modelo y mantienen un frente de Pareto externo con las soluciones no dominadas encontradas.

## Estructura general del repositorio

La carpeta principal del proyecto es `Code`, organizada actualmente de la siguiente forma:

```text
Code/
├── inst_creator/       # generación de instancias utilizadas en los experimentos
├── metaheuristics/     # algoritmos implementados y scripts de ejecución
├── results/            # resultados producidos por los experimentos y análisis posterior
└── tools/              # carga de instancias, soluciones, evaluación y frente de Pareto
```