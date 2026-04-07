import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './pages/Layout';
import { Dashboard } from './pages/Dashboard';
import { Inventario } from './pages/Inventario';
import { Tareas } from './pages/Tareas';
import { Computadoras } from './pages/Computadoras';
import './App.css';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="inventario" element={<Inventario />} />
          <Route path="tareas" element={<Tareas />} />
          <Route path="computadoras" element={<Computadoras />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
