"""
DAG 03: TaskFlow API - Modern Airflow (2.0+)
=============================================

LEARNING OBJECTIVES:
1. @task decorator for cleaner Python tasks
2. Automatic XCom handling (no manual push/pull)
3. Type hints and return values
4. Mixing TaskFlow with traditional operators

KEY CONCEPTS:
- @task: Decorator that turns a Python function into an Airflow task
- Automatic XCom: Return values are automatically passed to downstream tasks
- @dag: Optional decorator for defining DAGs (cleaner syntax)
- Traditional operators still work alongside TaskFlow

WHY TASKFLOW?
Before (traditional):
    def my_func(**context):
        ti = context['ti']
        data = ti.xcom_pull(task_ids='upstream')
        result = process(data)
        ti.xcom_push(key='result', value=result)

    task = PythonOperator(task_id='x', python_callable=my_func)

After (TaskFlow):
    @task
    def my_func(data):
        return process(data)

    result = my_func(upstream_task())  # Automatic XCom!
"""

import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from airflow.sdk import dag, task
from airflow.providers.standard.operators.bash import BashOperator

# Add include folder to path
sys.path.insert(0, str(Path(__file__).parent.parent / "include"))


# Using @dag decorator (optional but cleaner)
@dag(
    dag_id="03_taskflow_api",
    schedule="0 11 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["learning", "taskflow"],
    default_args={
        "owner": "airflow-learner",
        "retries": 1,
    },
)
def taskflow_demo():
    """
    DAG demonstrating the TaskFlow API.

    The @dag decorator turns this function into a DAG.
    Tasks are defined inside using @task decorator.
    Dependencies are inferred from function calls!
    """

    # Task 1: Generate some data
    @task
    def extract_data() -> dict:
        """
        Extract task - simulates fetching data.

        The return value is automatically pushed to XCom.
        Type hints are optional but recommended.
        """
        data = {
            "users": ["alice", "bob", "charlie"],
            "counts": [10, 25, 15],
            "timestamp": datetime.now().isoformat()
        }
        print(f"Extracted data: {data}")
        return data

    # Task 2: Transform the data
    @task
    def transform_data(raw_data: dict) -> dict:
        """
        Transform task - processes the extracted data.

        Notice: raw_data parameter receives the XCom from extract_data
        automatically! No xcom_pull needed.
        """
        # Process the data
        transformed = {
            "total_users": len(raw_data["users"]),
            "total_count": sum(raw_data["counts"]),
            "users_upper": [u.upper() for u in raw_data["users"]],
            "extracted_at": raw_data["timestamp"],
            "transformed_at": datetime.now().isoformat()
        }
        print(f"Transformed data: {transformed}")
        return transformed

    # Task 3: Load/save the data
    @task
    def load_data(transformed_data: dict) -> str:
        """
        Load task - saves the processed data.

        Returns a status message.
        """
        # In real scenario, this would save to database/file
        output_path = Path("/tmp/taskflow_output.json")
        with open(output_path, "w") as f:
            json.dump(transformed_data, f, indent=2)

        message = f"Saved {transformed_data['total_users']} users to {output_path}"
        print(message)
        return message

    # Task 4: Multiple inputs example
    @task
    def summarize(load_status: str, raw_data: dict) -> dict:
        """
        Task receiving multiple XCom inputs.

        Both parameters are automatically pulled from their respective tasks.
        """
        summary = {
            "status": load_status,
            "original_user_count": len(raw_data["users"]),
            "pipeline_complete": True,
            "completed_at": datetime.now().isoformat()
        }
        print(f"Pipeline summary: {summary}")
        return summary

    # Task 5: Mixing with traditional operators
    # You can still use BashOperator, etc. alongside TaskFlow
    show_result = BashOperator(
        task_id="show_result",
        bash_command='echo "Pipeline complete! Check /tmp/taskflow_output.json"',
    )

    # Define the workflow by calling tasks
    # Dependencies are AUTOMATICALLY inferred from the function calls!
    raw = extract_data()
    transformed = transform_data(raw)
    load_status = load_data(transformed)
    summary = summarize(load_status, raw)

    # For traditional operators, use >> to set dependency
    summary >> show_result


# Instantiate the DAG
# When using @dag decorator, you must call the function
taskflow_demo_dag = taskflow_demo()


# =============================================================================
# BONUS: TaskFlow with multiple outputs
# =============================================================================

@dag(
    dag_id="03b_taskflow_multiple_outputs",
    schedule=None,  # Manual trigger only
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["learning", "taskflow", "advanced"],
)
def taskflow_multiple_outputs():
    """Demonstrates tasks with multiple outputs."""

    @task(multiple_outputs=True)
    def get_user_stats() -> dict[str, Any]:
        """
        Task with multiple outputs.

        When multiple_outputs=True, each dict key becomes a separate XCom.
        Downstream tasks can pull individual keys.
        """
        return {
            "user_count": 100,
            "active_users": 75,
            "new_users": 10
        }

    @task
    def process_active(active_count: int) -> str:
        return f"Processing {active_count} active users"

    @task
    def process_new(new_count: int) -> str:
        return f"Welcoming {new_count} new users"

    # Access individual outputs using dict-like syntax
    stats = get_user_stats()
    active_result = process_active(stats["active_users"])
    new_result = process_new(stats["new_users"])


taskflow_multiple_outputs_dag = taskflow_multiple_outputs()
