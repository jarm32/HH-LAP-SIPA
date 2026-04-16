# Genera un excel con la solución aleatoria factible creada por random_feasible.py

# Librerías
import os
from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from tools.solution import Solution


def export_solution_xlsx(sol, out_path, overwrite = True): # objeto Solution, ruta de salida, si se permite sobreescribir
    """
    Exporta una Solution a un único .xlsx con 4 hojas:
      - Assignments: una fila por estudiante
      - Companies: resumen por empresa
      - Professors: resumen por profesor
      - Summary: checks y estadísticas rápidas
    """
    if (not overwrite) and os.path.exists(out_path):
        raise FileExistsError(f"File already exists: {out_path}")

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    wb = Workbook()
     
    ws_assign = wb.active
    ws_assign.title = "Assignments"
    _write_assignments_sheet(sol, ws_assign)

    ws_comp = wb.create_sheet("Companies")
    _write_companies_sheet(sol, ws_comp)

    ws_prof = wb.create_sheet("Professors")
    _write_professors_sheet(sol, ws_prof)

    ws_sum = wb.create_sheet("Summary")
    _write_summary_sheet(sol, ws_sum)

    wb.save(out_path)

    return out_path # devuelve la ruta del archivo generado


def _autosize_columns(ws): # archivo
    """
    Ajusta el ancho de las columnas basado en el contenido
    """
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.value is None:
                continue
            max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = min(max_len + 2, 60)


def _write_assignments_sheet(sol, ws): 
    p = sol.problem
    ws.append(["student_id", "placement_id", "company_id", "professor_id"])

    for i in range(p.n_students):
        j = sol.student_to_placement[i]
        if j == -1:
            ws.append([i, -1, -1, -1])
            continue
        k = p.placement_company[j]
        t = sol.placement_to_professor[j]
        ws.append([i, j, k, t])

    _autosize_columns(ws)


def _write_companies_sheet(sol, ws): # objeto Solution, hoja de Excel
    p = sol.problem
    ws.append(["company_id", "assigned", "min", "max", "slack_to_min", "slack_to_max"])

    for k in range(p.n_companies):
        assigned = sol.company_load[k]
        mn = p.company_min[k]
        mx = p.company_max[k]
        ws.append([k, assigned, mn, mx, assigned - mn, mx - assigned])

    _autosize_columns(ws)


def _write_professors_sheet(sol, ws): # objeto Solution, hoja de Excel
    p = sol.problem
    ws.append(["professor_id", "load", "capacity", "remaining"])

    for t in range(p.n_professors):
        load = sol.professor_load[t]
        cap = p.prof_capacity[t]
        ws.append([t, load, cap, cap - load])

    _autosize_columns(ws)


def _write_summary_sheet(sol: Solution, ws): # objeto Solution, hoja de Excel
    p = sol.problem

    complete = sol.is_complete()
    valid = sol.validate()
    n_assigned = sum(1 for x in sol.student_to_placement if x != -1)

    min_ok = all(sol.company_load[k] >= p.company_min[k] for k in range(p.n_companies))
    max_ok = all(sol.company_load[k] <= p.company_max[k] for k in range(p.n_companies))
    prof_ok = all(sol.professor_load[t] <= p.prof_capacity[t] for t in range(p.n_professors))
    deps_ok = sol.dependencies_ok()

    loads = sol.professor_load[:]
    if loads:
        min_load = min(loads)
        max_load = max(loads)
        avg_load = sum(loads) / len(loads)
    else:
        min_load = max_load = avg_load = 0

    rows = [
        ("Complete", complete),
        ("Validate()", valid),
        ("Assigned students", f"{n_assigned} / {p.n_students}"),
        ("", ""),
        ("Company min ok", min_ok),
        ("Company max ok", max_ok),
        ("Professor capacity ok", prof_ok),
        ("Dependencies ok", deps_ok),
        ("", ""),
        ("Professors min load", min_load),
        ("Professors avg load", round(avg_load, 2)),
        ("Professors max load", max_load),
    ]

    for a, b in rows:
        ws.append([a, b])

    _autosize_columns(ws)