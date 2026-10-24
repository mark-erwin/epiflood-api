// import { useState } from 'react';

import logo from '../../public/logo.png';
import {Outlet, Link, useNavigate} from 'react-router'
import '../styles/NavBar.css';

export default function Navbar() {
  return (
    <>
      <nav className="navbar">
          <div className="navbar-container">
              <div className="navbar-logo">
                  <img src={logo} alt="APILogo" className="logo-image" /> 
              </div>

              <div className="navbar-name-and-options">
                  <div className="navbar-name">
                      <h1>EpiFlood API</h1>
                  </div>

                  <div className="navbar-options">
                      <div className="navbar-options-main">
                          <Link to="/">Home</Link>
                          <Link to="/exploredata">Explore Data</Link>
                          <Link to="/exploredatasets">Datasets</Link>
                          <Link to="/credits">Credits</Link>
                      </div>

                      <div className="navbar-options-sub">
                          <Link to="https://github.com/mark-erwin/msynk-pjdsc-2026">Documentation</Link>
                      </div>
                  </div>  
              </div>
          </div>
      </nav>
      <Outlet/>
    </>
  );
}
