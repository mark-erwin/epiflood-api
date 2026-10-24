# msynk-pjdsc-2026

## What is EpiFlood API?

EpiFlood API is a RESTful API designed to consolidate publicly available dengue and leptospirosis case data in Laguna, Philippines, with rainfall and flood-hazard data. Built using FastAPI and DuckDB, it provides endpoints for querying, analyzing, and exporting epidemiological and environmental data. The system supports spatiotemporal analysis to examine disease patterns and their potential relationships with rainfall and flood-prone areas. Its data and analytical capabilities are intended to power an interactive dashboard featuring historical trends, geographic maps, and other visualizations to support research and public health decision-making.

## How to Run
1. Create a Virtual Environment
    - Navigate to api folder `cd api`
    - Create a Virtual Environment `python -m venv ./venv`
    - Activate Virtual Environment `venv\Scripts\activate`
    - Install Requirements `pip install -r requirements.txt`
1. Database Seeding
    - Navigate to api folder `cd api`
    - `python -m pipeline.run_all`   
2. API
    - Navigate to api folder `cd api`
    - Run API `uvicorn api:app`
2. Dashboard
    - Navigate to app folder `cd app`
    - Run app `npm run dev`
