import Map from './components/Map.tsx';
import Navbar from './components/NavBar.tsx'
import { Routes, Route, Outlet, Navigate } from 'react-router';

function App() {
  return (
    <>
      <Routes>
        <Route element={<Navbar/>}>
          <Route path="/" element={<Map/>} />
        </Route>
      </Routes>
    </>
  );
}

export default App
