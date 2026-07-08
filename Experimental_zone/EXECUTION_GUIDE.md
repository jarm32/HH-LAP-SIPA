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

### 4.1 Parameter glossary

To make all examples reusable and configurable, this guide uses the following placeholders:

```text
<RUNS>                -> number of repetitions per algorithm, instance, and time limit
<ALGORITHMS>          -> list of algorithms to execute
<SIZES>               -> list of instance sizes to execute
<TIME_LIMITS>         -> list of custom time limits in seconds
<RESULTS_DIR>         -> output directory for the experiment (results/...)
<INSTANCES_COUNT>     -> number of selected instances
<ALGORITHMS_COUNT>    -> number of selected algorithms
<TIME_LIMITS_COUNT>   -> number of time limits; use 1 if --time_limits_seconds is not specified
<EXPERIMENT_NAME>     -> experiment identifier used in paths
```

### 4.2 Generic dry run

Before launching real experiments, use `--dry_run`. The dry run does not execute the algorithms. It only prints the jobs that would be launched, including the selected algorithms, instances, repetitions, time limits, and output directory.

If `--time_limits_seconds` is not provided, `run_general.py` uses the default time limit associated with each instance size. These default values are defined in `TIME_LIMITS_SECONDS` inside `code/run_general.py`. 

If `--time_limits_seconds` is provided, the launcher executes every selected algorithm, instance, and repetition once for each specified time limit.

```bash
python code/run_general.py \
  --runs <RUNS> \
  --algorithms <ALGORITHMS> \
  --sizes <SIZES> \
  --time_limits_seconds <TIME_LIMITS> \
  --results_dir <RESULTS_DIR> \
  --resume \
  --dry_run
```

Remove the --time_limits_seconds line when using the default TIME_LIMITS_SECONDS values.
Remove the --sizes line when all available instance sizes should be used.

General formula:

```text
number of executions = <INSTANCES_COUNT> × <RUNS> × <ALGORITHMS_COUNT> × <TIME_LIMITS_COUNT>
```

If `--time_limits_seconds` is not used, <TIME_LIMITS_COUNT> = 1.

---

## 5. Launch experiments

### 5.1 General launcher

The main launcher is:

```text
code/run_general.py
```

Foreground execution:

```bash
python code/run_general.py \
  --runs <RUNS> \
  --algorithms <ALGORITHMS> \
  --sizes <SIZES> \
  --time_limits_seconds <TIME_LIMITS> \
  --results_dir <RESULTS_DIR> \
  --resume
```

Background execution:

```bash
mkdir -p results/logs_<EXPERIMENT_NAME>

nohup python code/run_general.py \
  --runs <RUNS> \
  --algorithms <ALGORITHMS> \
  --sizes <SIZES> \
  --time_limits_seconds <TIME_LIMITS> \
  --results_dir <RESULTS_DIR> \
  --resume \
  > results/logs_<EXPERIMENT_NAME>/<EXPERIMENT_NAME>.out 2>&1 &
```

Remove the --time_limits_seconds line when using the default TIME_LIMITS_SECONDS values.
Remove the --sizes line when all available instance sizes should be used.

In custom time-limit mode, output filenames include the time limit. For example:

```text
hh_lap_v0__problem_instance_ext_1000_0__t300s__run_00.done
hh_lap_v0__problem_instance_ext_1000_0__t600s__run_00.done
hh_lap_v1__problem_instance_ext_1000_3__t1200s__run_09.csv
```

This prevents checkpoints and Pareto files from different time budgets from overwriting each other.

### 5.2 Meaning of the main options

```text
--runs N                    -> number of independent repetitions
--algorithms A1 A2 ...      -> algorithms to execute
--sizes S1 S2 ...           -> instance sizes to execute; if omitted, all available sizes are used
--time_limits_seconds T ... -> custom time limits in seconds; if omitted, TIME_LIMITS_SECONDS is used
--instances_dir PATH        -> directory containing the instance .txt files; default: instances
--results_dir PATH          -> output directory where results will be stored
--resume                    -> skip executions already marked as completed with a .done checkpoint
--dry_run                   -> show what would be executed without running the algorithms
--verbose                   -> show internal algorithm progress during execution
--stop_on_error             -> stop the whole experiment if one execution fails
--save_assignments          -> save complete assignment details for each Pareto solution in JSON format

nohup                      -> keep the process running after closing the session
&                          -> run the process in the background
file 2>&1                  -> redirect both standard output and standard error to a log file
```

---

## 6. Output structure

Each experiment writes results to the directory passed through `--results_dir`. If the directory was not created previously, the launcher creates it automatically.

Expected structure:

```text
<RESULTS_DIR>/
├── assignments/    # JSON assignment files if --save_assignments is used
├── checkpoints/    # .done markers for completed executions
├── logs/           # internal run_general.py log
├── pareto/         # Pareto fronts, one CSV per execution
└── statistics/     # global execution statistics
```

Main files:

```text
<RESULTS_DIR>/statistics/statistics_all.csv
  -> Global execution summary. Contains one row per execution, including algorithm, instance, run, seed, time limit, elapsed time, status, Pareto size, and algorithm-specific statistics.

<RESULTS_DIR>/logs/run_general.log
  -> Internal execution log generated by run_general.py. It records the start, end, skipped executions, completed runs, errors, elapsed times, and Pareto sizes.

<RESULTS_DIR>/pareto/
  -> Pareto-front CSV files. In default time-limit mode, filenames identify algorithm, instance, and run. In custom time-limit mode, filenames also include the time limit.

<RESULTS_DIR>/checkpoints/
  -> Completion markers used by --resume. In custom time-limit mode, checkpoint filenames include the time limit.
```

If `--save_assignments` is not used, `assignments/` remains empty.

After computing hypervolume, an additional folder is created:

```text
<RESULTS_DIR>/hypervolume/
```

---

## 7. Monitor execution

Check whether the launcher is still running:

```bash
ps aux | grep "run_general.py"
```

If only the `grep` process appears, the execution has finished.

Follow the external log generated by `nohup`:

```bash
tail -f results/logs_<EXPERIMENT_NAME>/<EXPERIMENT_NAME>.out
```

The external nohup log is only used to capture console output and unexpected stderr messages. The main execution progress is recorded in the internal log, which could be followed by:

```bash
tail -n 50 <RESULTS_DIR>/logs/run_general.log
```

Check available memory:

```bash
free -h
```

---

## 8. Check for errors

Check the internal log:

```bash
grep -i "error\|traceback\|failed" <RESULTS_DIR>/logs/run_general.log
```

If using `nohup`, also check the external log:

```bash
grep -i "error\|traceback\|failed" results/logs_<EXPERIMENT_NAME>/<EXPERIMENT_NAME>.out
```

In a correct execution, these commands should not return relevant errors.

---

## 9. Verify that all executions finished

Total checkpoints:

```bash
find <RESULTS_DIR>/checkpoints -type f | wc -l
```

Total Pareto files:

```bash
find <RESULTS_DIR>/pareto -type f | wc -l
```

Check checkpoints by algorithm:

```bash
find <RESULTS_DIR>/checkpoints -type f -name "random__*.done" | wc -l
find <RESULTS_DIR>/checkpoints -type f -name "nsga3__*.done" | wc -l
find <RESULTS_DIR>/checkpoints -type f -name "grasp__*.done" | wc -l
find <RESULTS_DIR>/checkpoints -type f -name "hh_lap_v0__*.done" | wc -l
find <RESULTS_DIR>/checkpoints -type f -name "hh_lap_v1__*.done" | wc -l
```

Expected total number of completed executions:

```text
<INSTANCES_COUNT> × <RUNS> × <ALGORITHMS_COUNT> × <TIME_LIMITS_COUNT>
```

The number of checkpoint files and Pareto files should match this value.

For custom time-limit experiments, checkpoints must be checked by time limit. Example:

```bash
find <RESULTS_DIR>/checkpoints -type f -name "*__t<TIME_LIMIT>s__*.done" | wc -l
```

---

## 10. Compute hypervolume

The hypervolume is computed after `run_general.py` has finished.

Run from the root of `Experimental_zone`:

```bash
python code/run_hypervolume.py --results_dir <RESULTS_DIR>
```

The script reads Pareto CSV files from:

```text
<RESULTS_DIR>/pareto/
```

and writes:

```text
<RESULTS_DIR>/hypervolume/hypervolume_summary.csv
<RESULTS_DIR>/hypervolume/hypervolume_by_run.csv
```

Main columns in `hypervolume_by_run.csv` include:

```text
algorithm, instance, n_students, run_id, pareto_points, hypervolume,
min_tau, min_eta, min_lbar, min_sigma,
max_tau, max_eta, max_lbar, max_sigma
```

Important note for custom time-limit experiments:

```text
If the current version of run_hypervolume.py groups results only by algorithm, instance, and run_id, it should be updated before computing hypervolume for time-budget experiments. Otherwise, results with the same algorithm, instance, and run_id but different time limits may be mixed.
```

After the execution and hypervolume computation, results can be packaged for storage or analysis:

```bash
tar -czvf <EXPERIMENT_NAME>_results.tar.gz <RESULTS_DIR>
```

---

## 11. Completion criteria

An experimental run can be considered complete when all of the following conditions are satisfied:

```text
1. No active run_general.py process remains.
2. No relevant errors appear in the internal or external logs.
3. The number of checkpoint files is correct.
4. The number of Pareto CSV files is correct.
5. <RESULTS_DIR>/statistics/statistics_all.csv exists.
6. If hypervolume is required, hypervolume_by_run.csv and hypervolume_summary.csv exist.
7. The generated results can be packaged.
```

---

## 12. Parameter values used in executed experiments

This section records the parameter values of the main experiments executed in this project. It is intended as a quick reference for reproducing previous executions or defining similar experiments in the future.

### 12.1 Full sequential experiment

Purpose:

```text
Main comparison among all implemented algorithms over all available instances.
```

Parameter values:

```text
<EXPERIMENT_NAME> = final_sequential

<RUNS> = 30
<ALGORITHMS> = random nsga3 grasp hh_lap_v0 hh_lap_v1
<SIZES> = omitted; all available sizes are used
<TIME_LIMITS> = omitted; default TIME_LIMITS_SECONDS values are used

<RESULTS_DIR> = results/final_sequential
External log = results/logs/final_sequential.out
This experiment used the original external log path results/logs/final_sequential.out instead of the generic results/logs_<EXPERIMENT_NAME>/<EXPERIMENT_NAME>.out pattern. This is kept here to document the actual command used in the original execution.

<INSTANCES_COUNT> = 20
<ALGORITHMS_COUNT> = 5
<TIME_LIMITS_COUNT> = 1

Total executions = 20 × 30 × 5 × 1 = 3000
```

Dry run:

```bash
python code/run_general.py \
  --runs 30 \
  --algorithms random nsga3 grasp hh_lap_v0 hh_lap_v1 \
  --results_dir results/final_sequential \
  --resume \
  --dry_run
```

Background execution:

```bash
mkdir -p results/logs

nohup python code/run_general.py \
  --runs 30 \
  --algorithms random nsga3 grasp hh_lap_v0 hh_lap_v1 \
  --results_dir results/final_sequential \
  --resume \
  > results/logs/final_sequential.out 2>&1 &
```

Expected output counts:

```text
checkpoints/ -> 3000 files
pareto/      -> 3000 files
statistics/  -> statistics_all.csv
logs/        -> run_general.log
```

Expected checkpoints by algorithm:

```text
random      -> 600
nsga3       -> 600
grasp       -> 600
hh_lap_v0   -> 600
hh_lap_v1   -> 600
```

```text
tar -czvf final_sequential_results_with_hypervolume.tar.gz results/final_sequential
```

### 12.2 HH-LAP-SIPA time-budget experiment

Purpose:

```text
Analyze whether the execution time affects the comparison between HH-LAP-SIPA-Lite and HH-LAP-SIPA-Intensive.
```

Parameter values:

```text
<EXPERIMENT_NAME> = time_budget_1000

<RUNS> = 10
<ALGORITHMS> = hh_lap_v0 hh_lap_v1
<SIZES> = 1000
<TIME_LIMITS> = 300 600 900 1200

<RESULTS_DIR> = results/time_budget_1000
External log = results/logs_time_budget_1000/time_budget_1000.out

<INSTANCES_COUNT> = 4
<ALGORITHMS_COUNT> = 2
<TIME_LIMITS_COUNT> = 4

Total executions = 4 × 10 × 2 × 4 = 320
```

Dry run:

```bash
python code/run_general.py \
  --runs 10 \
  --algorithms hh_lap_v0 hh_lap_v1 \
  --sizes 1000 \
  --time_limits_seconds 300 600 900 1200 \
  --results_dir results/time_budget_1000 \
  --resume \
  --dry_run
```

Background execution:

```bash
mkdir -p results/logs_time_budget_1000

nohup python code/run_general.py \
  --runs 10 \
  --algorithms hh_lap_v0 hh_lap_v1 \
  --sizes 1000 \
  --time_limits_seconds 300 600 900 1200 \
  --results_dir results/time_budget_1000 \
  --resume \
  > results/logs_time_budget_1000/time_budget_1000.out 2>&1 &
```

Expected output counts:

```text
checkpoints/ -> 320 files
pareto/      -> 320 files
statistics/  -> statistics_all.csv
logs/        -> run_general.log
```

Expected checkpoints by algorithm:

```text
hh_lap_v0 -> 160
hh_lap_v1 -> 160
```

Expected checkpoints by time limit:

```text
t300s  -> 80
t600s  -> 80
t900s  -> 80
t1200s -> 80
```

If this experiment is repeated in the future with 20 instances of 1000 students, the expected number of executions would be:

```text
20 × 10 × 2 × 4 = 1600
```

```text
tar -czvf time_budget_1000_results.tar.gz results/time_budget_1000
```