function Credits() {
  const contributors = [
    'Nathan Seth De Guzman',
    'Mark Erwin Pesino',
    'Nathan Pabico',
    'Roy Kevin Navarro',
    'Yvan Luis Senen',
  ];

const datasets = [
  {
    title: 'DOH-Epi Dengue Data 2016–2021',
    url: 'https://data.humdata.org/dataset/philippine-dengue-cases-and-deaths',
    description: 'Dengue Cases per City/Municipality with Date',
  },
  {
    title: 'DOH EB Weekly Surveillance Report Clustering',
    url: 'https://docs.google.com/spreadsheets/d/1jsQ3vkuUZYJ9UUKrBbnIQmnn9AoOnpc7a_yt7XxJZFs/edit?gid=2046215490#gid=2046215490',
    description: 'Dengue / Leptospirosis Cases per City/Municipality with Date',
  },
  {
    title: 'NOAH Hazard Maps',
    url: 'https://huggingface.co/datasets/bettergovph/project-noah-hazard-maps',
    description: 'GeoJSON Format Flood Hazard Map (Hazard Level 1-3)',
  },
  {
    title: 'Philippines – Subnational Administrative Boundaries',
    url: 'https://data.humdata.org/dataset/cod-ab-phl',
    description: 'Subnational Administrative Codes and Boundaries, Philippines',
  },
  {
    title: 'Open-Meteo Historical Weather API',
    url: 'https://open-meteo.com/en/docs/historical-weather-api?hourly=rain&start_date=2000-01-01&end_date=2009-12-31',
    description: 'Complete Geographical Region Rainfall Data',
  },
];

  return (
    <main className="min-h-[calc(100vh-5.5rem)] bg-[#f4f6fb] px-4 py-10 font-['Montserrat',sans-serif] sm:px-6 sm:py-14">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-10">
        {/* Page heading */}
        <header className="text-center">

          <h1 className="text-[clamp(2rem,4vw,3rem)] font-bold leading-tight tracking-[-0.04em] text-[#080f43]">
            Credits
          </h1>
        </header>

        {/* Contributors */}
        <section aria-labelledby="contributors-heading">
          <div className="mb-5 flex items-center gap-3">

            <div>
              <h2
                id="contributors-heading"
                className="text-xl font-bold text-[#080f43]"
              >
                Contributors
              </h2>
            </div>
          </div>

          <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {contributors.map((name, index) => (
              <li
                key={name}
                className="group flex items-center gap-4 rounded-2xl border border-[#e1e6f0] bg-white p-4 shadow-[0_4px_18px_rgba(8,15,67,0.04)] transition duration-200 hover:-translate-y-1 hover:border-[#cdd5ff] hover:shadow-[0_8px_24px_rgba(52,73,163,0.10)]"
              >
                <span className="text-sm font-semibold leading-6 text-[#1d2648]">
                  {name}
                </span>
              </li>
            ))}
          </ul>
        </section>

        {/* Dataset references */}
        <section aria-labelledby="datasets-heading">
          <div className="mb-5 flex items-center gap-3">        

            <div>
              <h2
                id="datasets-heading"
                className="text-xl font-bold text-[#080f43]"
              >
                Data Sources
              </h2>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {datasets.map((dataset) => (
              <article
                key={dataset.title}
                className="group flex flex-col justify-between gap-5 rounded-2xl border border-[#e1e6f0] bg-white p-5 shadow-[0_4px_18px_rgba(8,15,67,0.04)] transition duration-200 hover:-translate-y-1 hover:border-[#cdd5ff] hover:shadow-[0_8px_24px_rgba(52,73,163,0.10)] sm:p-6"
              >
          <h3 className="text-base font-bold leading-6 text-[#080f43]">
            {dataset.title}
          </h3>

          <p className="mt-3 flex-1 whitespace-pre-line text-sm leading-6 text-[#68708b]">
            {dataset.description}
          </p>

          <a
            href={dataset.url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-5 inline-flex w-fit items-center gap-2 rounded-xl border border-[#dfe5ff] bg-[#f7f8ff] px-4 py-2.5 text-sm font-semibold text-[#3449a3] transition hover:border-[#bfcaff] hover:bg-[#eef1ff] focus:outline-none focus:ring-2 focus:ring-[#7185e8] focus:ring-offset-2"
          >
            View dataset
            <span aria-hidden="true">↗</span>
          </a>
              </article>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}

export default Credits;
