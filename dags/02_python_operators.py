"""
DAG 02: Python Operators - Running Python Code in Airflow
==========================================================

LEARNING OBJECTIVES:
1. PythonOperator for running Python functions
2. Passing parameters with op_kwargs and op_args
3. XCom for passing data between tasks
4. Template variables (Jinja templating)

KEY CONCEPTS:
- PythonOperator: Runs a Python callable (function)
- XCom: Cross-communication - how tasks share data
- Templates: Dynamic values using Jinja2 ({{ ds }}, {{ execution_date }}, etc.)
- Context: Runtime information passed to your functions

XCOMS EXPLAINED:
- Tasks are isolated - they can't share variables directly
- XCom (cross-communication) is Airflow's way to pass small data between tasks
- Use ti.xcom_push() to store data, ti.xcom_pull() to retrieve
- Return values from Python functions are automatically pushed to XCom
"""

import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

# Add include folder to path for our custom modules
sys.path.insert(0, str(Path(__file__).parent.parent / "include"))


def greet_user(name: str, greeting: str = "Hello") -> str:
    """
    Simple function demonstrating op_kwargs.
    Arguments come from the operator's op_kwargs parameter.
    """
    message = f"{greeting}, {name}! Welcome to Airflow."
    print(message)
    return message  # Return value is automatically pushed to XCom


def get_current_info(**context: Any) -> dict[str, Any]:
    """
    Function demonstrating context access.
    The **context gives you access to runtime info.

    Available context keys:
    - ds: Execution date as string (YYYY-MM-DD)
    - execution_date: Execution datetime object
    - ti: Task instance (for XCom operations)
    - dag: The DAG object
    - task: The task object
    - params: User-defined params from DAG run
    - And many more...
    """
    # Access context variables
    ds = context["ds"]                    # e.g., "2024-01-15"
    ti = context["ti"]                    # Task instance
    dag_id = context["dag"].dag_id

    info = {
        "execution_date": ds,
        "dag_id": dag_id,
        "task_id": ti.task_id,
        "run_id": context["run_id"],
        "timestamp": datetime.now().isoformat()
    }

    print(f"Execution Info: {json.dumps(info, indent=2)}")

    # Manually push to XCom (alternative to returning)
    ti.xcom_push(key="execution_info", value=info)

    return info


def process_with_xcom(**context: Any) -> dict[str, Any]:
    """
    Function demonstrating XCom pull.
    Retrieves data pushed by previous tasks.
    """
    ti = context["ti"]

    # Pull XCom from a specific task
    # By default, pulls the return value (key="return_value")
    greeting_message = ti.xcom_pull(task_ids="greet")
    print(f"Retrieved greeting: {greeting_message}")

    # Pull with specific key
    exec_info = ti.xcom_pull(task_ids="get_info", key="execution_info")
    print(f"Retrieved execution info: {exec_info}")

    # Process the data
    summary = {
        "greeting": greeting_message,
        "execution_date": exec_info.get("execution_date"),
        "processed_at": datetime.now().isoformat()
    }

    return summary


def demonstrate_templates(templated_param: str, **context: Any) -> None:
    """
    Function receiving templated parameters.
    Templates are rendered BEFORE the function is called.
    """
    print(f"Received templated param: {templated_param}")
    print(f"Param type: {type(templated_param)}")

    # The ds from context should match
    print(f"Execution date from context: {context['ds']}")


# Default args
default_args = {
    "owner": "airflow-learner",
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="02_python_operators",
    default_args=default_args,
    description="Learn PythonOperator, XCom, and templating",
    schedule="0 10 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["learning", "python"],
) as dag:

    # Task 1: Simple function with keyword arguments
    greet = PythonOperator(
        task_id="greet",
        python_callable=greet_user,
        op_kwargs={                       # Keyword arguments passed to function
            "name": "Airflow Learner",
            "greeting": "Welcome"
        },
    )

    # Task 2: Function with context access
    get_info = PythonOperator(
        task_id="get_info",
        python_callable=get_current_info,
        # No op_kwargs needed - context is passed via **context
    )

    # Task 3: XCom demonstration
    process_xcoms = PythonOperator(
        task_id="process_xcoms",
        python_callable=process_with_xcom,
    )

    # Task 4: Templated parameters
    # Templates use Jinja2 syntax {{ variable }}
    # Common templates: {{ ds }}, {{ execution_date }}, {{ params.x }}
    templated_task = PythonOperator(
        task_id="templated_task",
        python_callable=demonstrate_templates,
        op_kwargs={
            # This value is templated - rendered at runtime
            "templated_param": "Run date: {{ ds }}, DAG: {{ dag.dag_id }}"
        },
        # Must specify which kwargs should be templated
        templates_dict=None,  # Alternative way to pass templates
    )

    # Dependencies
    greet >> get_info >> process_xcoms >> templated_task
