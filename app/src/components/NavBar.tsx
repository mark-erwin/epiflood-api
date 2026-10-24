import logo from '../../public/logo.png';
import { Outlet, Link } from 'react-router';

export default function Navbar() {
  const linkClass = 'text-[0.9rem] hover:underline hover:underline-offset-[0.2em]';

  return (
    <>
      <nav className="w-full bg-[#080f43] text-[#f8f8f8]">
        <div className="flex min-h-[5.5rem] items-center gap-5 px-5 py-2">
          <div className="flex h-16 w-16 flex-none basis-16 items-center justify-center">
            <img
              src={logo}
              alt="APILogo"
              className="block h-[120%] w-[120%] max-w-none object-contain"
            />
          </div>

          <div className="flex min-w-0 flex-auto flex-col justify-center gap-1 self-stretch">
            <div>
              <h1 className="font-['Montserrat',sans-serif] text-[1.75rem] font-normal leading-[1.2]">
                EpiFlood API
              </h1>
            </div>

            <div className="flex flex-row">
              <div className="flex items-center gap-5">
                <Link className={linkClass} to="/">Home</Link>
                <Link className={linkClass} to="/exploredata">Explore Data</Link>
                <Link className={linkClass} to="/exploredatasets">Datasets</Link>
                <Link className={linkClass} to="/credits">Credits</Link>
              </div>

              <div className="ml-auto flex items-center gap-5 self-end pb-[0.15rem]">
                <a
                  className={linkClass}
                  href="https://github.com/mark-erwin/msynk-pjdsc-2026"
                  target="_blank"
                  rel="noreferrer"
                >
                  Documentation
                </a>
              </div>
            </div>
          </div>
        </div>
      </nav>
      <Outlet />
    </>
  );
}