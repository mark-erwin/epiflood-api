// import { useState } from 'react';

// import logo from 'filename.png';

import '../styles/NavBar.css';

export default function Navbar() {
  return (
    <nav className="navbar">
        <div className="navbar-container">
            <div className="navbar-logo">
                {/* <img src={logo} alt="APILogo" className="logo-image" /> */}
            </div>

            <div className="navbar-name-and-options">
                <div className="navbar-name">
                    <h1>EpiFlood API</h1>
                </div>

                <div className="navbar-options">
                    <div className="navbar-options-main">
                        <a href="#/home">Home</a>
                        <a href="#/explore">Explore Data</a>
                        <a href="#/datasets">Datasets</a>
                        <a href='#/credits'>Credits</a>
                    </div>

                    <div className="navbar-options-sub">
                        <a href="#/documentation">Documentation</a>
                    </div>
                </div>  
            </div>
        </div>
    </nav>
  );
}
