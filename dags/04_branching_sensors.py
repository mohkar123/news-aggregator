"""
DAG 04: Branching and Sensors - Conditional Workflows
======================================================

LEARNING OBJECTIVES:
1. BranchPythonOperator for conditional execution
2. Sensors for waiting on conditions
3. Trigger rules for complex dependencies
4. Short-circuit operator for early termination

KEY CONCEPTS:
- Branching: Execute different paths based on conditions
- Sensors: Tasks that wait for an external condition
- Trigger Rules: When should a task run based on upstream status
- Short-circuit: Stop downstream tasks if condition fails

TRIGGER RULES:
- all_success (default): Run if ALL upstream succeeded
- all_failed: Run if ALL upstream failed
- all_done: Run when ALL upstream complete (any state)
- one_success: Run if ANY upstream succeeded
- one_failed: Run if ANY upstream failed
- none_failed: Run if NO upstream failed (success or skipped OK)
- none_skipped: Run if NO upstream was skipped
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import random
from typing import Any

from airflow import DAG
from airflow.sdk import task
from airflow.providers.standard.operators.python import (
    PythonOperator,
    BranchPythonOperator,
    ShortCircuitOperator,
)
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.empty import EmptyOperator
from airflow.providers.standard.sensors.filesystem import FileSensor
from airflow.providers.standard.sensors.time import TimeSensor
from airflow.providers.standard.sensors.python import PythonSensor

# Add include folder
sys.path.insert(0, str(Path(__file__).parent.parent / "include"))


# =============================================================================
# Helper Functions
# =============================================================================

def decide_branch(**context: Any) -> str:
    """
    Branch decision function.

    Returns the task_id of the branch to execute.
    Can return a single task_id or list of task_ids.
    """
    # Get current hour to decide branch
    current_hour = datetime.now().hour

    if current_hour < 12:
        print("Morning detected - taking morning branch")
        return "morning_tasks"
    elif current_hour < 18:
        print("Afternoon detected - taking afternoon branch")
        return "afternoon_tasks"
    else:
        print("Evening detected - taking evening branch")
        return "evening_tasks"


def check_data_ready(**context: Any) -> bool:
    """
    Sensor poke function.

    Returns True when condition is met, False otherwise.
    Sensor will keep checking until True or timeout.
    """
    # Simulate checking if data is ready
    # In real scenarios, this might check a database, API, or file
    ready = random.random() > 0.3  # 70% chance of being ready
    print(f"Data ready check: {ready}")
    return ready


def should_continue(**context: Any) -> bool:
    """
    Short-circuit decision function.

    If returns False, all downstream tasks are skipped.
    If returns True, downstream tasks run normally.
    """
    # Example: Only continue on weekdays
    is_weekday = datetime.now().weekday() < 5
    print(f"Is weekday: {is_weekday}")
    return is_weekday


# =============================================================================
# DAG Definition
# =============================================================================

default_args = {
    "owner": "airflow-learner",
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}

with DAG(
    dag_id="04_branching_sensors",
    default_args=default_args,
    description="Learn branching, sensors, and trigger rules",
    schedule="0 */4 * * *",  # Every 4 hours
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["learning", "branching", "sensors"],
) as dag:

    # Starting task
    start = EmptyOperator(task_id="start")

    # =========================================================================
    # SECTION 1: Branching
    # =========================================================================

    # Branch operator - decides which path to take
    branch = BranchPythonOperator(
        task_id="branch_by_time",
        python_callable=decide_branch,
    )

    # Branch options - only ONE will execute per run
    morning = BashOperator(
        task_id="morning_tasks",
        bash_command='echo "Good morning! Running morning workflow..."',
    )

    afternoon = BashOperator(
        task_id="afternoon_tasks",
        bash_command='echo "Good afternoon! Running afternoon workflow..."',
    )

    evening = BashOperator(
        task_id="evening_tasks",
        bash_command='echo "Good evening! Running evening workflow..."',
    )

    # Join after branching
    # IMPORTANT: Use trigger_rule="none_failed_min_one_success"
    # This allows the join to run even if some branches are skipped
    join = EmptyOperator(
        task_id="join_branches",
        trigger_rule="none_failed_min_one_success",
    )

    # Set up branching flow
    start >> branch >> [morning, afternoon, evening] >> join

    # =========================================================================
    # SECTION 2: Sensors
    # =========================================================================

    # Python Sensor - waits for a Python function to return True
    wait_for_data = PythonSensor(
        task_id="wait_for_data",
        python_callable=check_data_ready,
        poke_interval=10,          # Check every 10 seconds
        timeout=60,                # Give up after 60 seconds
        mode="poke",               # "poke" (sync) or "reschedule" (async)
        soft_fail=True,            # Don't fail DAG if timeout, just skip
    )

    # File Sensor - waits for a file to exist
    # (Create /tmp/airflow_data_ready.txt to trigger)
    wait_for_file = FileSensor(
        task_id="wait_for_file",
        filepath="/tmp/airflow_data_ready.txt",
        poke_interval=15,
        timeout=120,
        mode="reschedule",         # Free up worker while waiting
        soft_fail=True,
    )

    process_data = BashOperator(
        task_id="process_data",
        bash_command='echo "Processing data that sensors found..."',
        trigger_rule="none_failed",  # Run if no upstream failed
    )

    # Sensors flow (parallel sensors, then process)
    join >> [wait_for_data, wait_for_file] >> process_data

    # =========================================================================
    # SECTION 3: Short-Circuit
    # =========================================================================

    # Short-circuit - if returns False, skip ALL downstream
    check_continue = ShortCircuitOperator(
        task_id="check_if_weekday",
        python_callable=should_continue,
    )

    weekday_task = BashOperator(
        task_id="weekday_only_task",
        bash_command='echo "This only runs on weekdays!"',
    )

    process_data >> check_continue >> weekday_task

    # =========================================================================
    # SECTION 4: End with summary
    # =========================================================================

    end = BashOperator(
        task_id="end",
        bash_command='echo "DAG complete at $(date)"',
        trigger_rule="all_done",  # Always run, regardless of upstream status
    )

    weekday_task >> end


# =============================================================================
# BONUS: TaskFlow Branching (Airflow 2.3+)
# =============================================================================

from airflow.sdk import dag as dag_decorator

@dag_decorator(
    dag_id="04b_taskflow_branching",
    schedule=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["learning", "branching", "taskflow"],
)
def taskflow_branching():
    """Modern branching with TaskFlow API."""

    @task.branch
    def choose_path() -> str:
        """TaskFlow branch - return task_id to execute."""
        value = random.randint(1, 100)
        if value > 50:
            return "high_value_path"
        return "low_value_path"

    @task
    def high_value_path():
        print("High value detected!")
        return "high"

    @task
    def low_value_path():
        print("Low value detected!")
        return "low"

    @task(trigger_rule="none_failed_min_one_success")
    def final_task(result: str = None):
        print(f"Final task received: {result}")

    # Define flow - note the branch returns task_id, not result
    branch_result = choose_path()

    # Both possible paths
    high = high_value_path()
    low = low_value_path()

    # Set dependencies manually for branching
    branch_result >> [high, low]

    final_task()


taskflow_branching_dag = taskflow_branching()
