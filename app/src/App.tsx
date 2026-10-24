import Map from './components/map/Map.tsx';
import Navbar from './components/NavBar.tsx'
import Credits from './pages/Credits.tsx'
import ExploreDatasets from './pages/ExploreDatasets.tsx'
import ExploreData from './pages/ExploreData.tsx'
import { Routes, Route, Outlet, Navigate } from 'react-router';

function App() {
  return (
    <>
      <Routes>
        <Route element={<Navbar/>}>
          <Route path="/" element={<Map/>} />
          <Route path="/credits" element={<Credits/>}/>
          <Route path="/exploredata" element={<ExploreData/>}/>
          <Route path="/exploredatasets" element={<ExploreDatasets/>}/>
        </Route>
      </Routes>
    </>
  );
}

export default App
