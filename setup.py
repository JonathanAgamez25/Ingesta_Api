from setuptools import setup, find_packages

setup(
    name="ea1-ingestion-api",
    version="0.1.0",
    description="EA1 Proyecto integrador — Ingestión de datos desde el API de CoinGecko hacia SQLite",
    author="Jonatan Dair Ávila Agamez",
    packages=find_packages(),
    install_requires=[
        "requests>=2.31",
        "pandas>=2.0",
        "openpyxl>=3.1",
    ],
    python_requires=">=3.10",
)
