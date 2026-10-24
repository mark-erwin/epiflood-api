function Documentation() {
  return (
    <div className="h-full w-full">
      <iframe
        src="http://localhost:8000/docs"
        title="FastAPI Documentation"
        className="block h-full w-full border-none"
      />
    </div>
  );
}

export default Documentation;