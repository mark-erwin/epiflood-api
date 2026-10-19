# msynk-pjdsc-2026

## How to Run:
- Create a Virtual Environment `python -m venv ./venv`
- Activate Virtual Environment `venv\Scripts\activate`
- Install Requirements `pip install requirements.txt`
- Test pdf_reader.py `cd pdf_reader_module` `python pdf_reader.py`

## File Structure:
- `app/` ReactJS, Tailwind CSS, Leaflet Dashboard Frontend
    - `src/`
        - `components/` React Components to Build the App
- `api/` FastAPI, DuckDB Backend
    - `client`
    - `core`
    - `data`
    - `db`
    - `middleware`
    - `models`
    - `pipelines`
    - `routes`
    - `schemas`
    - `services`
    - `tests`
    - `utils`
    - `api.py` Main file to run the API
