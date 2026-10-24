import { Outlet, Link } from 'react-router';

export default function Navbar() {
  const linkClass = 'text-[0.9rem] hover:underline hover:underline-offset-[0.2em]';

  return (
    <div className="flex h-screen flex-col">
        <nav className="relative z-20 h-22 w-full shrink-0 bg-[#080f43] text-[#f8f8f8]">
            <div className="flex h-full items-center gap-6 px-6">
            {/* Zero-height wrapper: the logo keeps its 10rem size but no longer sets the nav height */}
            <div className="flex h-0 w-40 flex-none items-center justify-center overflow-visible">
                <Link
                to="/"
                aria-label="Go to home page"
                className="flex h-0 w-40 flex-none items-center justify-center overflow-visible"
                >
                <img
                    src="/logo.png"
                    alt="EpiFlood API Logo"
                    className="block h-40 w-40 max-w-none flex-none object-contain"
                />
                </Link>
            </div>

            <div className="flex min-w-0 flex-auto flex-col justify-center gap-2 self-stretch">
                <div className="flex flex-row">
                <div className="flex items-center gap-6">
                    <Link className={linkClass} to="/map">Map</Link>
                    <Link className={linkClass} to="/dashboard">Dashboard</Link>
                    <Link className={linkClass} to="/explore">Explore</Link>
                    
                    <Link
                        className={linkClass}
                        to="/documentation"
                        >
                        Documentation
                    </Link>
                    <Link className={linkClass} to="/credits">Credits</Link>

                </div>

                </div>
            </div>
            </div>
        </nav>
      <div className="relative min-h-0 flex-1 overflow-auto">
        <Outlet />
      </div>
    </div>
  );
}