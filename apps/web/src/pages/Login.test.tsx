import '@testing-library/jest-dom/vitest';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Login } from './Login'; 

vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
}));

const mockLogin = vi.fn();
vi.mock('../contexts/useAuth', () => ({
  useAuth: () => ({
    login: mockLogin,
  }),
}));

describe('Página Login (Suite S2-085 integrada con S2-080)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('muestra validación de campos vacíos nativa de HTML5 y no invoca el login', async () => {
    render(<Login />);
    const user = userEvent.setup();

    const submitButton = screen.getByRole('button', { name: /ingresar/i });
    await user.click(submitButton);

    expect(mockLogin).not.toHaveBeenCalled();
  });

  it('muestra el mensaje estándar de credenciales inválidas al fallar la autenticación', async () => {
    mockLogin.mockRejectedValueOnce(new Error('AuthError'));

    render(<Login />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/correo electrónico/i), 'test@aquabloom.cl');
    await user.type(screen.getByLabelText(/contraseña/i), 'clave123');
    await user.click(screen.getByRole('button', { name: /ingresar/i }));

    expect(await screen.findByText(/credenciales inválidas\. verifica tu correo y contraseña\./i)).toBeInTheDocument();
  });

  it('llama al hook de autenticación cuando el formato de credenciales es válido', async () => {
    mockLogin.mockResolvedValueOnce({});

    render(<Login />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/correo electrónico/i), 'usuario@aquabloom.cl');
    await user.type(screen.getByLabelText(/contraseña/i), 'PasswordSegura123!');
    await user.click(screen.getByRole('button', { name: /ingresar/i }));

    expect(mockLogin).toHaveBeenCalledTimes(1);
    expect(mockLogin).toHaveBeenCalledWith({
      email: 'usuario@aquabloom.cl',
      password: 'PasswordSegura123!',
    });
  });
});
