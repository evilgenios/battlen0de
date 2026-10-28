import { describe, expect, it, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '@/test/test-utils';
import { LinkAccountWizard } from './LinkAccountWizard';
import { ApiError } from '@/lib/api/client';

const { requestLinkCodeMock, verifyLinkCodeMock, pushMock } = vi.hoisted(() => ({
  requestLinkCodeMock: vi.fn(),
  verifyLinkCodeMock: vi.fn(),
  pushMock: vi.fn(),
}));

vi.mock('@/lib/api/link', () => ({
  requestLinkCode: requestLinkCodeMock,
  verifyLinkCode: verifyLinkCodeMock,
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock }),
}));

const CHALLENGE_ID = 'challenge-abc-123';

beforeEach(() => {
  requestLinkCodeMock.mockReset();
  verifyLinkCodeMock.mockReset();
  pushMock.mockReset();
});

async function advanceToCodeStep(user: ReturnType<typeof userEvent.setup>) {
  requestLinkCodeMock.mockResolvedValue({
    challenge_id: CHALLENGE_ID,
    email: 'player@example.com',
    expires_in_seconds: 600,
  });
  await user.type(screen.getByLabelText(/email/i), 'player@example.com');
  await user.click(screen.getByRole('button', { name: /send verification code/i }));
  await screen.findByText(/check your email/i);
}

describe('LinkAccountWizard — step 1 (email)', () => {
  it('shows validation error and does not call the API for an invalid email', async () => {
    const user = userEvent.setup();
    renderWithProviders(<LinkAccountWizard />);

    await user.type(screen.getByLabelText(/email/i), 'not-an-email');
    await user.click(screen.getByRole('button', { name: /send verification code/i }));

    expect(await screen.findByText(/valid email/i)).toBeInTheDocument();
    expect(requestLinkCodeMock).not.toHaveBeenCalled();
  });

  it('sends the code and advances to step 2 on success', async () => {
    const user = userEvent.setup();
    renderWithProviders(<LinkAccountWizard />);

    await advanceToCodeStep(user);

    expect(requestLinkCodeMock).toHaveBeenCalledWith({ email: 'player@example.com' });
    expect(screen.getByText(/player@example\.com/)).toBeInTheDocument();
  });

  it('shows a network-error message when the backend is unreachable', async () => {
    requestLinkCodeMock.mockRejectedValue(new ApiError(0, null, 'Could not reach the dashboard server.'));
    const user = userEvent.setup();
    renderWithProviders(<LinkAccountWizard />);

    await user.type(screen.getByLabelText(/email/i), 'player@example.com');
    await user.click(screen.getByRole('button', { name: /send verification code/i }));

    expect(await screen.findByText(/network error/i)).toBeInTheDocument();
  });

  it('shows a service-unavailable message (e.g. no bootstrap vehicle yet)', async () => {
    requestLinkCodeMock.mockRejectedValue(
      new ApiError(503, 'No Warpath account is available yet to authorize linking a new one.'),
    );
    const user = userEvent.setup();
    renderWithProviders(<LinkAccountWizard />);

    await user.type(screen.getByLabelText(/email/i), 'player@example.com');
    await user.click(screen.getByRole('button', { name: /send verification code/i }));

    expect(await screen.findByText(/service unavailable/i)).toBeInTheDocument();
  });

  it('prevents duplicate submissions while the request is in flight', async () => {
    let resolveRequest: (value: unknown) => void = () => {};
    requestLinkCodeMock.mockReturnValue(new Promise((resolve) => { resolveRequest = resolve; }));
    const user = userEvent.setup();
    renderWithProviders(<LinkAccountWizard />);

    await user.type(screen.getByLabelText(/email/i), 'player@example.com');
    const sendButton = screen.getByRole('button', { name: /send verification code/i });
    await user.click(sendButton);
    await user.click(sendButton);
    await user.click(sendButton);

    resolveRequest({ challenge_id: CHALLENGE_ID, email: 'player@example.com', expires_in_seconds: 600 });
    await waitFor(() => expect(requestLinkCodeMock).toHaveBeenCalledTimes(1));
  });
});

describe('LinkAccountWizard — step 2 (code)', () => {
  it('verifies the code and shows a success state before redirecting', async () => {
    verifyLinkCodeMock.mockResolvedValue({ id: 'new-account-id', label: 'player@example.com' });
    const user = userEvent.setup();
    renderWithProviders(<LinkAccountWizard />);
    await advanceToCodeStep(user);

    await user.type(screen.getByLabelText(/verification code/i), '123456');
    await user.click(screen.getByRole('button', { name: /verify & link account/i }));

    expect(verifyLinkCodeMock).toHaveBeenCalledWith({ challenge_id: CHALLENGE_ID, code: '123456' });
    // "Account linked" appears twice (the success card's own heading AND
    // the toast notification) — assert on the card's more specific
    // subtitle instead of risking an ambiguous multi-match query.
    expect(await screen.findByText(/taking you to the account/i)).toBeInTheDocument();

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith('/accounts/new-account-id'), { timeout: 3000 });
  });

  it('shows an invalid-code error and stays on step 2 for a wrong code', async () => {
    verifyLinkCodeMock.mockRejectedValue(new ApiError(422, 'verification failed: incorrect code'));
    const user = userEvent.setup();
    renderWithProviders(<LinkAccountWizard />);
    await advanceToCodeStep(user);

    await user.type(screen.getByLabelText(/verification code/i), '000000');
    await user.click(screen.getByRole('button', { name: /verify & link account/i }));

    // "incorrect code" appears in both the error title and its detail
    // sentence — match the title exactly rather than risking a
    // multi-element match.
    expect(await screen.findByText('Incorrect code')).toBeInTheDocument();
    expect(screen.getByText(/check your email/i)).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });

  it('shows an expired-code error', async () => {
    verifyLinkCodeMock.mockRejectedValue(new ApiError(410, 'This verification request was not found or has expired.'));
    const user = userEvent.setup();
    renderWithProviders(<LinkAccountWizard />);
    await advanceToCodeStep(user);

    await user.type(screen.getByLabelText(/verification code/i), '123456');
    await user.click(screen.getByRole('button', { name: /verify & link account/i }));

    expect(await screen.findByText(/code expired/i)).toBeInTheDocument();
  });

  it('shows a rate-limit error after too many attempts', async () => {
    verifyLinkCodeMock.mockRejectedValue(new ApiError(429, 'Too many incorrect attempts. Request a new verification code.'));
    const user = userEvent.setup();
    renderWithProviders(<LinkAccountWizard />);
    await advanceToCodeStep(user);

    await user.type(screen.getByLabelText(/verification code/i), '999999');
    await user.click(screen.getByRole('button', { name: /verify & link account/i }));

    expect(await screen.findByText(/too many attempts/i)).toBeInTheDocument();
  });

  it('lets the user resend the code', async () => {
    const user = userEvent.setup();
    renderWithProviders(<LinkAccountWizard />);
    await advanceToCodeStep(user);

    requestLinkCodeMock.mockClear();
    requestLinkCodeMock.mockResolvedValue({
      challenge_id: 'challenge-resent-456',
      email: 'player@example.com',
      expires_in_seconds: 600,
    });

    // The resend button starts on a cooldown right after the first send —
    // this is the expected, deliberate rate-limit-avoidance UX.
    expect(screen.getByRole('button', { name: /resend code/i })).toBeDisabled();
  });

  it('lets the user go back and change the email', async () => {
    const user = userEvent.setup();
    renderWithProviders(<LinkAccountWizard />);
    await advanceToCodeStep(user);

    await user.click(screen.getByRole('button', { name: /use a different email/i }));

    expect(await screen.findByText(/link a warpath account/i)).toBeInTheDocument();
  });

  it('prevents duplicate verify submissions while in flight', async () => {
    let resolveVerify: (value: unknown) => void = () => {};
    verifyLinkCodeMock.mockReturnValue(new Promise((resolve) => { resolveVerify = resolve; }));
    const user = userEvent.setup();
    renderWithProviders(<LinkAccountWizard />);
    await advanceToCodeStep(user);

    await user.type(screen.getByLabelText(/verification code/i), '123456');
    const verifyButton = screen.getByRole('button', { name: /verify & link account/i });
    await user.click(verifyButton);
    await user.click(verifyButton);

    resolveVerify({ id: 'new-account-id', label: 'player@example.com' });
    await waitFor(() => expect(verifyLinkCodeMock).toHaveBeenCalledTimes(1));
  });

  it('never displays or requires any Warpath credential fields', async () => {
    const user = userEvent.setup();
    const { container } = renderWithProviders(<LinkAccountWizard />);
    await advanceToCodeStep(user);

    const text = container.textContent ?? '';
    for (const forbidden of ['App Token', 'Device ID', 'App UID', 'Package Version', 'Channel ID']) {
      expect(text).not.toContain(forbidden);
    }
  });
});
