
import { useEffect, useState } from 'react';
import { Link } from 'react-router';

const rainfallGifs = [
  'https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExZWlhYXJ1YmdoYzM4em8yYnJldXA3eGh6dXE2NGo3N3ZsbXd6b2x4ciZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/qHWAmPd3SWyY0/giphy.gif',

  'https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExdWl2bmZ3cW1zdGhmN3NtOXJkc3FxOXhkZWFvYnI0cXg5aHh2Ynd3YiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/jd3lQvdBZOCNG/giphy.gif',

    'https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3dGVkb3V4MnNudjF1dmJhbWRreGQ5cW82ZW9vdnRzaDN1d2M1Nm9icCZlcD12MV9naWZzX3JlbGF0ZWQmY3Q9Zw/eaGYPsglb5X0I/giphy.gif',

  'https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExZnhzZzUyN3FjdzR6emVxMW15azNkZDVvdm5yeTlyY2JkM2Fya2M3NCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/Cc7G0JSDmQtI4/giphy.gif',

  'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExeDd1czM0cmNlcnU1YXh2dDNjM2lteDQzZzh3cXpwbWVjZ241Nm91ZSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/2Q5tDFr07UgV2/giphy.gif'

];



function Home() {
  const [gifIndex, setGifIndex] = useState(() =>
    Math.floor(Math.random() * rainfallGifs.length),
  );

    useEffect(() => {
    const interval = window.setInterval(() => {
        setGifIndex((currentIndex) => (currentIndex + 1) % rainfallGifs.length);
    }, 3500); // Change GIF every 3.5 seconds

    return () => window.clearInterval(interval);
    }, []);

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#080f43] px-6 py-12 font-['Montserrat',sans-serif] text-[#f4f6fb]">
      {/* Shuffling animated background */}
      {rainfallGifs.map((gif, index) => (
        <img
          key={gif}
          src={gif}
          alt=""
          aria-hidden="true"
          className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-1000 ${
            index === gifIndex ? 'opacity-30' : 'opacity-0'
          }`}
        />
      ))}

      {/* Dark overlay */}
      <div className="absolute inset-0 bg-[#080f43]/75" />

      {/* Title content */}
      <div className="relative z-10 mx-auto flex max-w-3xl flex-col items-center text-center">

        <h1 className="text-6xl font-extrabold tracking-[-0.06em] sm:text-8xl">
          EpiFlood
          <span className="text-[#9baafc]"> API</span>
        </h1>


        <p className="mt-8 text-sm font-semibold tracking-wide text-[#aab7ff] sm:text-base">
            Tracking Flood-Related Diseases, Supporting Open Data
        </p>

        <p className="mx-auto mt-7 max-w-xl text-base leading-7 text-[#c2c9e6] sm:text-lg">
          Interfacing FastAPI, Flood Hazard, and Rainfall Data for Mapping
          and Predictive Modeling of Dengue and Leptospirosis Cases in Laguna
        </p>


        <Link
          to="/map"
          className="mt-10 inline-flex items-center gap-3 rounded-xl bg-[#5269c7] px-8 py-4 text-sm font-semibold text-white shadow-[0_8px_24px_rgba(0,0,0,0.25)] transition hover:-translate-y-0.5 hover:bg-[#7185e8] focus:outline-none focus:ring-2 focus:ring-[#9baafc] focus:ring-offset-2 focus:ring-offset-[#080f43]"
        >
          Start Exploring
        </Link>
      </div>
    </main>
  );
}

export default Home;
