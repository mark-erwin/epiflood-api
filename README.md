# msynk-pjdsc-2026

## How to Run:
- Create a Virtual Environment `python -m venv ./venv`
- Activate Virtual Environment `venv\Scripts\activate`
- Install Requirements `pip install requirements.txt`
- Test pdf_reader.py `cd pdf_reader_module` `python pdf_reader.py`

## Project Structure:
```
msynk-pjdsc-2026/
├── api/
│   ├── api.py                  # API Entry Point
│   │
│   ├── core/                   
│   │   ├── config.py           # Settings, Path helpers
│   │   ├── constants.py
│   │   └── errors.py           # Exception Handlers
│   │
│   ├── data/
│   │   ├── epidemiology/       # Dengue, Leptospirosis Data
│   │   ├── gis/                # Geo Data
│   │   └── rainfall/           # Rainfall Data
│   │
│   ├── db/
│   │   ├── connect.py          # DuckDB connection
│   │   ├── database.duckdb     # Persistent Database File
│   │   └── init_db.py          # Build Tables
│   │
│   ├── middleware/
│   │   └── request_context.py  # request ID, timing, logging
│   │
│   ├── models/                 # Pydantic Schemas
│   │
│   ├── routes/
│   │   ├── cases.py            # Cases Routes
│   │   ├── export.py           # Export Routes
│   │   ├── map_layers.py       # Map Layer Routes
│   │   ├── meta.py             # Metadata Routes
│   │   ├── predict.py          # Prediction Routes (ML) (Dead)
│   │   ├── rainfall.py         # Rainfall Routes
│   │   └── reference.py        # Lookup Routes
│   │
│   ├── tests/                  # Endpoint Tests
│   │   ├── conftest.py
│   │   ├── test_meta.py
│   │   └── test_reference.py
│   │
│   └── utils/
│       ├── data_preprocessor.py
│       ├── laguna_bounds.py
│       ├── requirements.txt
│       └── test_json.py
│
└── app/
    └── src/
        ├── components/         # Elements, React Components
        └── pages/              # App Pages
```
