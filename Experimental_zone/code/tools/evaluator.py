# Evalúa un objeto Solution que contenga el resultado de una asignación, calculando su función objetivo.
# Se define una evaluación multiobjetiva pura (4 elementos por separado) y una monobjetivo escalar (combinación de los objetivos)


# Librerías
from dataclasses import dataclass
import math
import numpy as np


@dataclass
class ObjectiveWeights:
    alpha: float = 0.25
    beta: float = 0.25
    gamma: float = 0.25
    delta: float = 0.25
    
    # Se asegura de que los pesos estén en [0,1] y sumen 1
    def validate(self):
        for name, v in [("alpha", self.alpha), ("beta", self.beta), ("gamma", self.gamma), ("delta", self.delta)]:
            if v < 0 or v > 1:
                raise ValueError(f"{name} must be in [0,1], got {v}")
        s = self.alpha + self.beta + self.gamma + self.delta
        if abs(s - 1.0) > 1e-9:
            raise ValueError(f"alpha+beta+gamma+delta must be 1. Got {s}")


def evaluate_solution_multi(sol, normalize_student_dist=True, normalize_supervision_dist=True):
                            # Objeto Solution a evaluar, booleano que indica si las distancias estudiante-empresa se normalizan a [0,1],
                            # booleano que indica si las distancias de supervisión se normalizan a [0,1]
    """
    Calcula y devuelve por separado los 4 componentes de la función objetivo:
    - tau_sum   (maximizar)
    - eta_sum   (maximizar)
    - lbar_sum  (minimizar)
    - sigma_sum (minimizar)

    No agrega los objetivos con pesos
    """
    p = sol.problem

    # Validación de la solución
    if not sol.validate():
        return {"valid": False, "reason": "Solution is not valid according to sol.validate()"}

    # tau_ij y eta_ij
    tau_sum, eta_sum = _compute_student_and_company_utilities(sol, normalize_student_dist=normalize_student_dist)

    # Lbar_t
    lbar_by_t = _compute_lbar_by_professor(sol, normalize_supervision_dist=normalize_supervision_dist)
    lbar_sum = float(sum(lbar_by_t))

    # sigma_e
    sigma_by_e = _compute_sigma_by_center(sol)
    sigma_sum = float(sum(sigma_by_e))

    # Resultado multiobjetivo puro
    return {
        "valid": True,
        "components": {
            "tau_sum": float(tau_sum),
            "eta_sum": float(eta_sum),
            "lbar_sum": float(lbar_sum),
            "sigma_sum": float(sigma_sum),
        },
        "details": {
            "lbar_by_professor": lbar_by_t,
            "sigma_by_center": sigma_by_e,
        }
    }  # dict con los 4 objetivos por separado


def evaluate_solution_scalar(sol, weights, normalize_student_dist=True, normalize_supervision_dist=True):
                            # Objeto Solution a evaluar, pesos de la función objetivo, booleano que indica si las distancias estudiante-empresa
                            # se normalizan a [0,1], booleano que indica si las distancias de supervisión se normalizan a [0,1]
    """
    Calcula la versión escalar monobjetivo de la evaluación:
    α * tau_sum + β * eta_sum - γ * lbar_sum - δ * sigma_sum

    Se apoya en evaluate_solution_multi(...) para obtener primero
    los 4 componentes por separado
    """
    weights.validate()

    # Evaluación multiobjetivo previa
    multi_eval = evaluate_solution_multi(sol, normalize_student_dist=normalize_student_dist, normalize_supervision_dist=normalize_supervision_dist)

    # Si la solución no es válida, devuelve fitness inválido
    if not multi_eval["valid"]:
        return {"valid": False, "objective_value": float("-inf"), "reason": multi_eval["reason"]}

    # Extraer componentes
    tau_sum = multi_eval["components"]["tau_sum"]
    eta_sum = multi_eval["components"]["eta_sum"]
    lbar_sum = multi_eval["components"]["lbar_sum"]
    sigma_sum = multi_eval["components"]["sigma_sum"]

    # Función objetivo escalarizada
    obj = (
        weights.alpha * tau_sum
        + weights.beta * eta_sum
        - weights.gamma * lbar_sum
        - weights.delta * sigma_sum
    )

    # Resultado escalar, manteniendo también componentes y detalles
    return {
        "valid": True,
        "objective_value": float(obj),
        "components": multi_eval["components"],
        "details": multi_eval["details"],
    }  # dict con componentes y fitness final


def _compute_student_and_company_utilities(sol, normalize_student_dist):
                                          # objeto Solution, booleano que indica si las distancias estudiante-empresa se normalizan a [0,1]
    """
    Calcula sum τ_ij y sum η_ij por alumno asignado
    """
    p = sol.problem

    # Matrices/vectores necesarios
    dist = np.asarray(p.student_company_dist, dtype=np.float64)   # [n_students, n_companies]
    if normalize_student_dist:
        dist_norm = _minmax_normalize_rows(dist)
    else:
        dist_norm = dist

    # Φ_j (por plaza)
    if not hasattr(p, "placement_comp_needs") or len(p.placement_comp_needs) != p.n_placements:
        raise ValueError("Problem is missing placement_comp_needs (Φ_j) for each placement. Update problem.py loader.")

    Phi = np.asarray(p.placement_comp_needs, dtype=np.float64)    # [n_placements, n_competences]
    Theta = np.asarray(p.student_pref, dtype=np.float64)          # [n_students, n_competences]
    Psi = np.asarray(p.student_dev, dtype=np.float64)             # [n_students, n_competences]

    # Asignaciones estudiante -> plaza
    student_to_placement = np.asarray(sol.student_to_placement, dtype=np.int64)  # [n_students]

    # Filtrar solo estudiantes realmente asignados
    assigned_mask = student_to_placement != -1
    if not np.any(assigned_mask):
        return 0.0, 0.0

    assigned_students = np.nonzero(assigned_mask)[0]              # índices i asignados
    assigned_placements = student_to_placement[assigned_mask]     # plaza j de cada i
    assigned_companies = np.asarray(p.placement_company, dtype=np.int64)[assigned_placements]  # empresa k de cada j

    # Pesos por estudiante asignado
    w_dist = np.asarray(p.student_w_distance, dtype=np.float64)[assigned_mask]
    w_comp = np.asarray(p.student_w_dev, dtype=np.float64)[assigned_mask]

    # Distancia normalizada d_ij usando empresa de la plaza asignada
    dij = dist_norm[assigned_students, assigned_companies]

    # Submatrices relevantes
    Phi_assigned = Phi[assigned_placements]       # [n_assigned, n_competences]
    Theta_assigned = Theta[assigned_students]     # [n_assigned, n_competences]
    Psi_assigned = Psi[assigned_students]         # [n_assigned, n_competences]

    # Productos fila a fila:
    # pref_match[r] = Phi[j_r] · Theta[i_r]
    # comp_match[r] = Phi[j_r] · Psi[i_r]
    pref_match = np.einsum("ij,ij->i", Phi_assigned, Theta_assigned)
    comp_match = np.einsum("ij,ij->i", Phi_assigned, Psi_assigned)

    # τ_ij = w_dist*(1-dij) + w_comp*(Φ_j · Θ_i)
    tau_values = w_dist * (1.0 - dij) + w_comp * pref_match

    # η_ij = Φ_j · Ψ_i
    eta_values = comp_match

    tau_sum = float(np.sum(tau_values))
    eta_sum = float(np.sum(eta_values))

    return tau_sum, eta_sum


def _compute_lbar_by_professor(sol, normalize_supervision_dist):
                              # objeto Solution, booleano que indica si las distancias supervisión se normalizan a [0,1]
    """
    Calcula Lbar_t por profesor
    """
    p = sol.problem

    # Distancias base (centro-empresa y empresa-empresa)
    center_company = np.asarray(p.center_company_dist, dtype=np.float64)   # [n_centers, n_companies]
    company_company = np.asarray(p.company_company_dist, dtype=np.float64) # [n_companies, n_companies]

    if normalize_supervision_dist:
        # Normaliza globalmente ambas matrices juntas a [0,1]
        cc_min = float(min(center_company.min(), company_company.min()))
        cc_max = float(max(center_company.max(), company_company.max()))
        if cc_max > cc_min:
            center_company = (center_company - cc_min) / (cc_max - cc_min)
            company_company = (company_company - cc_min) / (cc_max - cc_min)
        else:
            center_company = np.zeros_like(center_company)
            company_company = np.zeros_like(company_company)

    # Plazas supervisados por profesor
    placements_by_t = [[] for _ in range(p.n_professors)]
    for j in range(p.n_placements):
        if sol.placement_filled[j]:
            t = sol.placement_to_professor[j]
            placements_by_t[t].append(j)

    # Calcula Lbar_t para cada profesor t
    lbar = [0.0] * p.n_professors
    for t in range(p.n_professors):
        supervised = placements_by_t[t]
        Nt = len(supervised)
        if Nt == 0:
            lbar[t] = 0.0
            continue

        center = p.prof_center[t]

        # nodos --> 0 será el origen, 1..Nt serán placements
        # distancia entre nodos a,b:
        # - si ambos placements: company_company[comp(a)][comp(b)]
        # - si uno es origen: center_company[center][comp(placement)]
        comps = [p.placement_company[j] for j in supervised]

        def d(a: int, b: int) -> float:
            if a == 0 and b == 0:
                return 0.0
            if a == 0:
                return float(center_company[center, comps[b - 1]])
            if b == 0:
                return float(center_company[center, comps[a - 1]])
            return float(company_company[comps[a - 1], comps[b - 1]])

        Lt = _prim_mst_length(num_nodes=Nt + 1, dist_fn=d)
        lbar[t] = float(Lt / Nt)

    return lbar


def _compute_sigma_by_center(sol): # objeto Solution
    """
    Calcula σ_e por centro
    """
    p = sol.problem

    Nt = sol.professor_load[:]
    Ct = p.prof_capacity

    # Agrupar profesores por centro
    profs_by_center = [[] for _ in range(p.n_centers)]
    for t in range(p.n_professors):
        e = p.prof_center[t]
        profs_by_center[e].append(t)
    
    # Para cada centro, calcula σ_e
    sigma = [0.0] * p.n_centers
    for e in range(p.n_centers):
        Ts = profs_by_center[e]
        if not Ts:
            sigma[e] = 0.0
            continue

        ps = []
        for t in Ts:
            cap = Ct[t]
            ps.append((Nt[t] / cap) if cap > 0 else 0.0)

        pbar = sum(ps) / len(ps)
        var = sum((x - pbar) ** 2 for x in ps) / len(ps)
        sigma[e] = float(math.sqrt(var))

    return sigma


def _minmax_normalize_rows(a): # matriz numérica cuyas filas se quieren normalizar a [0,1]
    """
    Min-max por fila a [0,1]. Si una fila es constante, devuelve 0
    """
    mins = a.min(axis=1, keepdims=True)
    maxs = a.max(axis=1, keepdims=True)
    denom = maxs - mins
    out = np.zeros_like(a, dtype=float)
    mask = denom[:, 0] > 1e-12
    out[mask] = (a[mask] - mins[mask]) / denom[mask]
    return out # matriz normalizada con mismo shape que a, filas normalizadas a [0,1]


def _prim_mst_length(num_nodes, dist_fn): # número de nodos, función que devuelve la distancia entre nodos a y b
    """
    Longitud del MST con Prim en un grafo completo implícito de num_nodes
    """
    in_mst = [False] * num_nodes
    min_edge = [float("inf")] * num_nodes

    min_edge[0] = 0.0
    total = 0.0

    for _ in range(num_nodes):
        # elegir nodo fuera del MST con menor coste
        u = -1
        best = float("inf")
        for v in range(num_nodes):
            if not in_mst[v] and min_edge[v] < best:
                best = min_edge[v]
                u = v

        if u == -1:
            break
        in_mst[u] = True
        total += best

        # actualizar distancias
        for v in range(num_nodes):
            if not in_mst[v]:
                w = dist_fn(u, v)
                if w < min_edge[v]:
                    min_edge[v] = w

    return float(total)