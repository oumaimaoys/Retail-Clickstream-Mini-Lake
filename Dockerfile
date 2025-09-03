FROM astrocrpublic.azurecr.io/runtime:3.0-10

RUN python -m venv dbt-venv && source dbt-venv/bin/activate && \
    pip install --no-cache-dir dbt-redshift && deactivate