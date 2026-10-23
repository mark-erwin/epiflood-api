import Map from './components/Map.tsx';
import Navbar from './components/NavBar.tsx'
import Credits from './pages/Credits.tsx'
import { Routes, Route, Outlet, Navigate } from 'react-router';

function App() {
  return (
    <>
      <Routes>
        <Route element={<Navbar/>}>
          <Route path="/" element={<Map/>} />
          <Route path="/credits" element={<Credits/>}/>
        </Route>
      </Routes>
    </>
  );
}

export default App
