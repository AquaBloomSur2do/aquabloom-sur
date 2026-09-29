import '@testing-library/jest-dom/vitest';
import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import LoginForm from './LoginForm';
import { supabase } from '../lib/supabase';

// 1. Simulamos el módulo de Supabase para evitar llamadas reales a la red
vi.mock('../lib/supabase', () => ({
  supabase: {
    auth: {
      signInWithPassword: vi.fn(),
    },
  },
}));

describe('Componente LoginForm', () => {
  beforeEach(() => {
    vi.clearAllMocks(); // Limpia el historial del mock
  });

  afterEach(() => {
    cleanup(); // <-- ESTA ES LA MAGIA: Limpia el DOM después de cada test
  });

  it('muestra validación de campos vacíos y no envía credenciales inválidas', async () => {
    render(<LoginForm />);
    const user = userEvent.setup();

    // Interacción: clic en el botón de envío sin llenar campos
    const submitButton = screen.getByRole('button', { name: /ingresar/i });
    await user.click(submitButton);

    // Verificación de validación vacía según los textos exactos
    expect(await screen.findByText(/el correo y la contraseña son obligatorios/i)).toBeInTheDocument();
    
    // Verificación crítica: garantizamos que la API de Supabase no fue invocada
    expect(supabase.auth.signInWithPassword).not.toHaveBeenCalled();
  });

  it('muestra mensaje específico de credenciales incorrectas', async () => {
    // Simulamos que Supabase rechaza las credenciales
    vi.mocked(supabase.auth.signInWithPassword).mockResolvedValueOnce({
      data: { user: null, session: null },
      error: { message: 'Invalid login credentials', status: 400, name: 'AuthError' },
    } as never); 

    render(<LoginForm />);
    const user = userEvent.setup();

    // Llenamos el formulario
    await user.type(screen.getByLabelText(/correo electrónico/i), 'test@aquabloom.cl');
    await user.type(screen.getByLabelText(/contraseña/i), 'clave123');
    await user.click(screen.getByRole('button', { name: /ingresar/i }));
    
    // Verificamos que tu componente captura el error de Supabase
    expect(await screen.findByText(/el correo o la contraseña son incorrectos/i)).toBeInTheDocument();
  });

  it('permite el envío cuando las credenciales tienen formato válido', async () => {
    // Simulamos un inicio de sesión exitoso
    vi.mocked(supabase.auth.signInWithPassword).mockResolvedValueOnce({
      data: { user: { id: '123' }, session: {} },
      error: null,
    } as never); 

    render(<LoginForm />);
    const user = userEvent.setup();

    // Interacción del usuario
    await user.type(screen.getByLabelText(/correo electrónico/i), 'usuario@aquabloom.cl');
    await user.type(screen.getByLabelText(/contraseña/i), 'PasswordSegura123!');
    await user.click(screen.getByRole('button', { name: /ingresar/i }));

    // Verificamos que se llamó a la API con los datos exactos
    expect(supabase.auth.signInWithPassword).toHaveBeenCalledTimes(1);
    expect(supabase.auth.signInWithPassword).toHaveBeenCalledWith({
      email: 'usuario@aquabloom.cl',
      password: 'PasswordSegura123!'
    });
  });
});
