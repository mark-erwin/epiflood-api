function ExploreDatasets() {
    return (
    <div className="api-docs-page">
      <iframe
        src="http://localhost:8000/docs"
        title="FastAPI Documentation"
        className="api-docs-frame"
      />
    </div>
    );
}

export default ExploreDatasets;
