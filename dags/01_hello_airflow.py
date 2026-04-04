"""
DAG 01: Hello Airflow - Understanding the Basics
=================================================

LEARNING OBJECTIVES:
1. DAG definition and parameters
2. Task dependencies with >> operator
3. BashOperator basics
4. Scheduling with cron expressions

KEY CONCEPTS:
- DAG: Directed Acyclic Graph - a collection of tasks with dependencies
- Operator: A template for a task (BashOperator runs shell commands)
- Task: An instance of an operator in your DAG
- Schedule: When the DAG runs (cron expression or timedelta)

RUN THIS DAG:
1. Start Airflow: ./scripts/start_airflow.sh
2. Go to http://localhost:8080
3. Enable the DAG "01_hello_airflow"
4. Trigger it manually or wait for schedule
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator

# DAG default arguments - inherited by all tasks
default_args = {
    "owner": "airflow-learner",           # Who owns this DAG
    "depends_on_past": False,             # Don't wait for previous run to succeed
    "email_on_failure": False,            # Don't email on failure (for now)
    "email_on_retry": False,              # Don't email on retry
    "retries": 1,                         # Retry failed tasks once
    "retry_delay": timedelta(minutes=5),  # Wait 5 min before retry
}

# Define the DAG
# The DAG context manager automatically assigns tasks to this DAG
with DAG(
    dag_id="01_hello_airflow",            # Unique identifier
    default_args=default_args,
    description="Learn Airflow basics with simple bash tasks",
    schedule="0 9 * * *",                 # Run daily at 9 AM (cron expression)
    start_date=datetime(2024, 1, 1),      # DAG start date (historical runs possible)
    catchup=False,                        # Don't run missed schedules
    tags=["learning", "basics"],          # Tags for filtering in UI
) as dag:

    # Task 1: Simple echo command
    # BashOperator runs a shell command
    hello_task = BashOperator(
        task_id="say_hello",              # Unique task identifier within DAG
        bash_command='echo "Hello from Airflow! Current time: $(date)"',
    )

    # Task 2: Check system info
    system_info = BashOperator(
        task_id="system_info",
        bash_command='echo "Running on: $(uname -a)"',
    )

    # Task 3: Create a timestamp file
    create_timestamp = BashOperator(
        task_id="create_timestamp",
        bash_command='echo "DAG ran at: $(date)" >> /tmp/airflow_hello.log',
    )

    # Task 4: Show the log
    show_log = BashOperator(
        task_id="show_log",
        bash_command='cat /tmp/airflow_hello.log | tail -5',
    )

    # Define task dependencies using >> (bitshift) operator
    # This creates: hello_task -> system_info -> create_timestamp -> show_log
    #
    # Alternative syntaxes:
    # - hello_task.set_downstream(system_info)
    # - system_info.set_upstream(hello_task)
    # - [task1, task2] >> task3  (parallel tasks feeding into one)

    hello_task >> system_info >> create_timestamp >> show_log

    # You can also create parallel execution:
    # [hello_task, system_info] >> create_timestamp
    # This would run hello_task and system_info in parallel, then create_timestamp
