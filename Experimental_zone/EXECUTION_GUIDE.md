# Execution Guide — SIPA Experimental Zone

## 1. General notices

The folder should have the following structure:

```text
Experimental_zone/
├── code/
│   ├── run_general.py
│   ├── run_hypervolume.py
│   ├── metaheuristics/
│   │   ├── run_ga_nsga3.py
│   │   ├── run_grasp.py
│   │   ├── run_hh_lap_sipa_v0.py
│   │   ├── run_hh_lap_sipa_v1.py
│   │   ├── run_random_baseline.py
│   │   └── scripts/
│   │       ├── ga_nsga3.py
│   │       ├── grasp.py
│   │       ├── hh_lap_sipa_v0.py
│   │       ├── hh_lap_sipa_v1.py
│   │       └── random_feasible_fixing.py
│   └── tools/
│       ├── evaluator.py
│       ├── hypervolume.py
│       ├── multiobjective_search.py
│       ├── pareto_front.py
│       ├── problem.py
│       ├── solution.py
│       └── solution_export.py
├── instances/
│   ├── problem_instance_ext_200_0.txt
│   ├── ...
│   └── problem_instance_ext_1000_3.txt
├── requirements.txt
├── README.md
└── EXECUTION_GUIDE.md
```

The `results/` folder is created automatically when experiments are executed.

All commands in this guide should be executed from the root of `Experimental_zone`, unless explicitly stated otherwise.

The original experiments were executed using Python 3.6.9. Other Python versions may work, but dependency compatibility, especially `lapjv`, should be checked.

Regarding the setup:

```text
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## 2. Available instances

The experimental zone includes 20 instances:

```text
5 instance sizes: 200, 400, 600, 800, and 1000 students
4 instances per size
20 instances in total
```

---

## 3. Available algorithms

The general launcher supports the following algorithm names:

```text
random      -> Random feasible baseline
nsga3       -> NSGA-III
grasp       -> GRASP
hh_lap_v0   -> HH-LAP-SIPA-Lite
hh_lap_v1   -> HH-LAP-SIPA-Intensive
```

The main launcher is:

```text
code/run_general.py
```

The hypervolume script is:

```text
code/run_hypervolume.py
```

---

## 4. Check what will be executed

Before launching real experiments, use `--dry_run`.

```bash
python code/run_general.py \
  --runs 30 \
  --algorithms random nsga3 grasp hh_lap_v0 hh_lap_v1 \
  --results_dir results/final_sequential \
  --resume \
  --dry_run
```

The output should confirm:

```text
Instances dir: .../Experimental_zone/instances
Results dir: .../Experimental_zone/results/final_sequential
Algorithms: random, nsga3, grasp, hh_lap_v0, hh_lap_v1
Runs per algorithm/instance: 30
Number of instances found: 20
The job lines should be numbered from [1/3000] to [3000/3000] for the full configuration.
```

When running:

```bash
python code/run_general.py --results_dir results/final_sequential
```

This output folder is created as:

```text
Experimental_zone/results/final_sequential/
```

---

## 5. Launch the full experiment

This is the simplest command. It keeps the process attached to the terminal:

```bash
python code/run_general.py \
  --runs 30 \
  --algorithms random nsga3 grasp hh_lap_v0 hh_lap_v1 \
  --results_dir results/final_sequential \
  --resume
```

Background execution option:

```bash
mkdir -p results/logs

nohup python code/run_general.py \
  --runs 30 \
  --algorithms random nsga3 grasp hh_lap_v0 hh_lap_v1 \
  --results_dir results/final_sequential \
  --resume \
  > results/logs/final_sequential.out 2>&1 &
```

Meaning of the main options:

```text
--runs N                 -> number of independent repetitions per algorithm and instance
--algorithms A1 A2 ...   -> algorithms to execute. Available options: random, nsga3, grasp, hh_lap_v0, hh_lap_v1
--sizes S1 S2 ...        -> instance sizes to execute. Available options: 200, 400, 600, 800, 1000
--instances_dir PATH     -> directory containing the instance .txt files. Default: instances
--results_dir PATH       -> output directory where results will be stored
--resume                 -> skip executions already marked as completed with a .done checkpoint. Allows resuming executions that have been interrupted.
--dry_run                -> show what would be executed without running the algorithms
--verbose                -> show internal algorithm progress during execution
--stop_on_error          -> stop the whole experiment if one execution fails
--save_assignments       -> save complete assignment details for each Pareto solution in JSON format

nohup                   -> keep the process running after closing the session
&                       -> run the process in the background
file 2>&1               -> redirects both standard output and error output to a log file
```

Custom experiments can be configured by combining these options.

---

## 6. Output structure

The full execution writes results to:

```text
results/final_sequential/
```

Expected structure:

```text
results/final_sequential/
├── assignments/    # JSON assignment files if --save_assignments is used
├── checkpoints/    # .done markers for completed executions
├── logs/           # internal run_general.py log
├── pareto/         # Pareto fronts, one CSV per algorithm-instance-run
└── statistics/     # global execution statistics
```

After computing hypervolume, an additional folder is created:

```text
results/final_sequential/hypervolume/
```

Main files:

```text
results/final_sequential/statistics/statistics_all.csv
  └── Global execution summary. Contains one row per algorithm-instance-run execution, including seed, time limit, elapsed time, status, Pareto size, and algorithm-specific statistics.

results/final_sequential/logs/run_general.log
  └── Internal execution log generated by run_general.py. It records the start, end, skipped executions, completed runs, errors, elapsed times, and Pareto sizes.

results/final_sequential/hypervolume/hypervolume_by_run.csv
  └── Hypervolume results at run level. Contains one row per algorithm, instance, and run, together with the number of Pareto points and the normalization bounds used for that instance.

results/final_sequential/hypervolume/hypervolume_summary.csv
  └── Aggregated hypervolume summary by algorithm and instance. Reports mean, standard deviation, minimum, and maximum hypervolume values by algorithm and instance.
```

For a full 30-run execution over all included algorithms and instances, the expected number of files is:

```text
checkpoints/ -> 3000 files
pareto/      -> 3000 files
statistics/  -> 1 file
logs/        -> 1 file
```

If `--save_assignments` is not used, `assignments/` remains empty.

---

## 7. Monitor execution

Check whether the launcher is still running:

```bash
ps aux | grep "run_general.py"
```

If only the `grep` process appears, the execution has finished.

Follow the external and internal log respectively (when using `nohup`):

```bash
tail -f results/logs/final_sequential.out
tail -n 50 results/final_sequential/logs/run_general.log
```

Check available memory:

```bash
free -h
```

---

## 8. Check for errors

```bash
grep -i "error\|traceback\|failed" results/final_sequential/logs/run_general.log
```

If using `nohup`, also check:

```bash
grep -i "error\|traceback\|failed" results/logs/final_sequential.out
```

In a correct execution, these commands should not return relevant errors.

---

## 9. Verify that all executions finished

Total checkpoints:

```bash
find results/final_sequential/checkpoints -type f | wc -l
```

Check checkpoints by algorithm:

```bash
find results/final_sequential/checkpoints -type f -name "random__*.done" | wc -l
find results/final_sequential/checkpoints -type f -name "nsga3__*.done" | wc -l
find results/final_sequential/checkpoints -type f -name "grasp__*.done" | wc -l
find results/final_sequential/checkpoints -type f -name "hh_lap_v0__*.done" | wc -l
find results/final_sequential/checkpoints -type f -name "hh_lap_v1__*.done" | wc -l
```

Check Pareto files:

```bash
find results/final_sequential/pareto -type f | wc -l
```

Expected result for each algorithm is 600, and for the Pareto file and completed jobs, it is 3000.

---

## 10. Compute hypervolume

The hypervolume is computed after `run_general.py` has finished. Run from the root of `Experimental_zone`:

```bash
python code/run_hypervolume.py --results_dir results/final_sequential
```

The script reads Pareto CSV files from:

```text
results/final_sequential/pareto/
```

and writes:

```text
results/final_sequential/hypervolume/hypervolume_summary.csv
results/final_sequential/hypervolume/hypervolume_by_run.csv
  └── Main columns: algorithm, instance, n_students, run_id, pareto_points, hypervolume, min_tau, min_eta, min_lbar, min_sigma, max_tau, max_eta, max_lbar, max_sigma, 
```

After the execution and hypervolume computation, results can be packaged for storage or analysis.

```bash
tar -czvf final_sequential_results_with_hypervolume.tar.gz results/final_sequential
```

---

## 11. Completion criteria

The full experimental run can be considered complete when all of the following conditions are satisfied:

```text
1. No active run_general.py process remains.
2. No relevant errors appear in run_general.log.
3. There are N checkpoint files and N Pareto CSV files, where N = number of algorithms × number of selected instances × number of runs. For the full configuration, N = 3000.
4. statistics_all.csv, hypervolume_by_run.csv and hypervolume_summary.csv exist.
5. The generated results can be packaged.
```