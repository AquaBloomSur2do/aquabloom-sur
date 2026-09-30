import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Toaster } from 'sonner';

import { PublicLayout } from './layouts/PublicLayout';
import { PrivateLayout } from './layouts/PrivateLayout';
import { Home } from './pages/Home';
import { Login } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { LakesList } from './pages/LakesList';
import { StationsList } from './pages/StationsList';
import { OrganizationsList } from './pages/OrganizationsList';
import { StationForm } from './pages/StationForm';
import { LakeDetail } from './pages/LakeDetail';
import { NotFound } from './pages/NotFound';
import { ProtectedRoute } from './components/ProtectedRoute';
import LakeCreate from './pages/LakeCreate';

import Error401 from './pages/Error401';
import Error403 from './pages/Error403';


function App() {
  return (
    <>
      <Toaster position="top-right" richColors closeButton expand={false} />
      <BrowserRouter>
        <Routes>
          <Route element={<PublicLayout />}>
            <Route path="/" element={<Home />} />
            <Route path="/login" element={<Login />} />
            <Route path="/401" element={<Error401 />} />
            <Route path="/403" element={<Error403 />} />
          </Route>

          <Route element={<ProtectedRoute />}>
            <Route element={<PrivateLayout />}>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/lakes" element={<LakesList />} />
              <Route path="/stations" element={<StationsList />} />
              <Route path="/organizations" element={<OrganizationsList />} />
              <Route path="/admin" element={<OrganizationsList />} />
              <Route path="/lakes/:lakeId/stations/new" element={<StationForm />} />
              <Route path="/lakes/:lakeId/stations/:stationId/edit" element={<StationForm />} />
              
              {/* INYECCIÓN ESTRATÉGICA: /new debe ir antes de /:id */}
              <Route path="/lakes/new" element={<LakeCreate />} />
              <Route path="/lakes/:id/edit" element={<LakeCreate />} />
              <Route path="/lakes/:id" element={<LakeDetail />} />
            </Route>
          </Route>

          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </>
  );
}

export default App;

