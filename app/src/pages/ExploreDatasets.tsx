function ExploreDatasets() {
  return (
    <div className="h-[calc(100vh-70px)] w-full">
      <iframe
        src="http://localhost:8000/docs"
        title="FastAPI Documentation"
        className="block h-full w-full border-none"
      />
    </div>
  );
}

export default ExploreDatasets;