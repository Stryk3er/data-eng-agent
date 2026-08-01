.PHONY: install extract-open-meteo extract-banxico extract-all dbt-build dbt-test chaos clean

install:
	pip install -r requirements.txt
	dbt deps --project-dir dbt_project

extract-open-meteo:
	python -m extraction.extract --source open_meteo --mode incremental

extract-banxico:
	python -m extraction.extract --source banxico --mode incremental

extract-all: extract-open-meteo extract-banxico

dbt-build:
	dbt build --project-dir dbt_project --profiles-dir dbt_project

dbt-test:
	dbt test --project-dir dbt_project --profiles-dir dbt_project

chaos:
	python scripts/chaos.py --mode $(or $(MODE),business_rule)

clean:
	rm -f data/warehouse.duckdb data/warehouse.duckdb.wal
