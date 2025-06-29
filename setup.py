"""Setup script for RAG Toolkit."""

from setuptools import setup, find_packages
import pathlib

here = pathlib.Path(__file__).parent.resolve()

# Get the long description from the README file
long_description = (here / "README.md").read_text(encoding="utf-8") if (here / "README.md").exists() else ""

setup(
    name="ragtoolkit",
    version="0.1.0",
    description="Observability and evaluation toolkit for RAG applications",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/ragtoolkit",
    author="Your Name",
    author_email="your.email@example.com",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    keywords="rag, llm, ai, observability, evaluation, retrieval",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "pydantic>=2.0.0",
        "httpx>=0.25.0",
        "sqlalchemy>=2.0.0",
        "psycopg2-binary>=2.9.0",
        "numpy>=1.24.0",
        "scikit-learn>=1.3.0",
        "typer>=0.9.0",
        "rich>=13.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "flake8>=6.0.0",
            "mypy>=1.5.0",
        ],
        "llm": [
            "openai>=1.0.0",
            "anthropic>=0.3.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "ragtoolkit=ragtoolkit.cli.cli:app",
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/yourusername/ragtoolkit/issues",
        "Source": "https://github.com/yourusername/ragtoolkit/",
        "Documentation": "https://ragtoolkit.readthedocs.io/",
    },
) 