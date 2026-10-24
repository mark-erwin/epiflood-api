import Map from './components/map/Map.tsx';
import Navbar from './components/NavBar.tsx';
import Credits from './pages/Credits.tsx';
import ExploreData from './pages/ExploreData.tsx';
import { Routes, Route } from 'react-router';
import Home from './pages/Home.tsx';
import Documentation from './pages/Documentation.tsx';
import Dashboard from './pages/Dashboard.tsx';

function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />

      <Route element={<Navbar />}>
        <Route path="/map" element={<Map />} />
        <Route path="/dashboard" element={<Dashboard />} />

        <Route path="/explore" element={<ExploreData />} />

        <Route path="/credits" element={<Credits />} />
        <Route path="/documentation" element={<Documentation />} />
      </Route>
    </Routes>
  );
}

export default App;