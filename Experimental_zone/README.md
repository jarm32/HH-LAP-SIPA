# Experimental Zone — SIPA Extended Model

This folder contains the minimum files required to run the experimental algorithms for the extended Student–Industry Placement Allocation (SIPA) model.

It is intended as a self-contained experimental package (after extracting `Experimental_zone.zip`, users can install the dependencies, run the provided algorithms on the included instances, and compute the hypervolume indicators).

## Contents

```text
Experimental_zone/
├── code/                 # execution scripts, algorithms, and common tools
├── instances/            # problem instances used in the experiments
├── requirements.txt      # Python dependencies
├── README.md             # short overview of this package
└── EXECUTION_GUIDE.md    # detailed execution instructions
```

## Algorithms

The following algorithms can be executed through `code/run_general.py`:

```text
random      -> Random feasible baseline
nsga3       -> NSGA-III
grasp       -> GRASP
hh_lap_v0   -> HH-LAP-SIPA-Lite
hh_lap_v1   -> HH-LAP-SIPA-Intensive
```

## Instances

The `instances/` folder contains 20 instances:

```text
5 sizes: 200, 400, 600, 800, and 1000 students
4 instances per size
```

## Quick start

From the root of `Experimental_zone`, install the dependencies.

```powershell
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Run a small test:

```bash
python code/run_general.py \
  --runs 1 \
  --algorithms random \
  --sizes 200 \
  --results_dir results/test_random_200 \
  --resume
```

Run the full experimental configuration:

```bash
python code/run_general.py \
  --runs 30 \
  --algorithms random nsga3 grasp hh_lap_v0 hh_lap_v1 \
  --results_dir results/final_sequential \
  --resume
```

After the executions finish, compute hypervolume:

```bash
python code/run_hypervolume.py --results_dir results/final_sequential
```

## Outputs

The `results/final_sequential` directory is created automatically when experiments are executed. The main outputs are:

```text
statistics/statistics_all.csv
pareto/*.csv
checkpoints/*.done
logs/run_general.log
hypervolume/hypervolume_by_run.csv
hypervolume/hypervolume_summary.csv
```